"""Local tests for the doctor Lambda's Cognito ownership check.

Ties cognito_auth.py to lambda_function._assignment_auth with a
real RS256 token minted here and a stubbed JWKS — no AWS, no
network, no DynamoDB (the patient record is passed in directly).

Run:  python3 tests/test_doctor_auth.py
Exit code 0 = all cases pass.
"""

import base64
import os
import sys
import time

HERE = os.path.dirname(__file__)
REPO = os.path.join(os.path.expanduser("~"), "workspace", "hca-main")
# Deliverable first (the edited lambda_function.py + cognito_auth.py),
# repo second (dynamodb.py is unchanged, so it is not duplicated here).
sys.path.insert(0, os.path.join(HERE, "..", "backend", "doctor-lambda"))
sys.path.insert(1, os.path.join(REPO, "backend", "doctor-lambda"))

os.environ["AWS_REGION"] = "us-east-1"
os.environ["COGNITO_USER_POOL_ID"] = "us-east-1_TestPool"
os.environ["COGNITO_CLIENT_ID"] = "test-client-id"

import jwt as pyjwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicNumbers

import cognito_auth
import lambda_function


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


NOW = int(time.time())
ISSUER = "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_TestPool"


def setup_keys():
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    numbers = private.public_key().public_numbers()
    n = numbers.n.to_bytes((numbers.n.bit_length() + 7) // 8, "big")
    e = numbers.e.to_bytes((numbers.e.bit_length() + 7) // 8, "big")
    pem = private.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    stub = {"test-key-1": RSAPublicNumbers(
        int.from_bytes(base64.urlsafe_b64decode(_b64url(e) + "=" * (-len(_b64url(e)) % 4)), "big"),
        int.from_bytes(base64.urlsafe_b64decode(_b64url(n) + "=" * (-len(_b64url(n)) % 4)), "big")).public_key()}
    cognito_auth._jwks = stub
    cognito_auth._fetch_jwks = lambda: stub
    return pem


def mint(pem, email, groups=None, role=None):
    payload = {
        "sub": "user-sub-1", "email": email, "name": "Test",
        "iss": ISSUER, "aud": "test-client-id", "token_use": "id",
        "iat": NOW - 60, "exp": NOW + 3600,
    }
    if groups is not None:
        payload["cognito:groups"] = groups
    if role is not None:
        payload["custom:role"] = role
    return pyjwt.encode(payload, pem, algorithm="RS256", headers={"kid": "test-key-1"})


def event_with(token):
    return {"headers": {"Authorization": "Bearer " + token} if token else {}}


def run():
    pem = setup_keys()
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    other_pem = other.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    patient = {"patient_id": 9, "email": "patient@example.com"}
    cases = []

    def check(name, got, want):
        ok = got == want
        cases.append((name, ok))
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  (got {got!r}, want {want!r})"))

    def status(resp):
        return None if resp is None else resp.get("statusCode")

    # Patient, own record -> proceed
    t = mint(pem, "patient@example.com", groups=["Patients"])
    check("patient, own record -> proceed",
          status(lambda_function._assignment_auth(event_with(t), patient)), None)
    # Patient, someone else's record -> 403
    check("patient, other record -> 403",
          status(lambda_function._assignment_auth(event_with(t), {"patient_id": 3, "email": "other@example.com"})), 403)
    # Patient, no record -> 404
    check("patient, no record -> 404",
          status(lambda_function._assignment_auth(event_with(t), None)), 404)
    # Admin in Admins group -> any patient
    t_admin = mint(pem, "admin@example.com", groups=["Admins"])
    check("admin group -> any patient",
          status(lambda_function._assignment_auth(event_with(t_admin), {"patient_id": 3, "email": "other@example.com"})), None)
    # Migrated admin: no groups yet, custom:role admin -> any patient
    t_migrated = mint(pem, "admin@example.com", role="admin")
    check("migrated admin (custom:role, no groups) -> any patient",
          status(lambda_function._assignment_auth(event_with(t_migrated), {"patient_id": 3, "email": "other@example.com"})), None)
    # No token -> 401
    check("no token -> 401",
          status(lambda_function._assignment_auth(event_with(""), patient)), 401)
    # Forged token -> 401
    t_forged = mint(other_pem, "patient@example.com", groups=["Patients"])
    check("forged token -> 401",
          status(lambda_function._assignment_auth(event_with(t_forged), patient)), 401)

    failed = [c for c in cases if not c[1]]
    print(f"\n{len(cases) - len(failed)}/{len(cases)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(run())
