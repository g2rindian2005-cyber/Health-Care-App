"""Local tests for backend/doctor-lambda/cognito_auth.py.

Cognito JWT verification against a STUBBED JWKS — no AWS, no network.
An RSA keypair is generated here; tokens are minted with PyJWT and
the verifier's JWKS fetch is replaced with the stub key. Run:

    python3 tests/test_cognito_auth.py

Exit code 0 = all cases pass.
"""

import base64
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend", "doctor-lambda"))

os.environ["AWS_REGION"] = "us-east-1"
os.environ["COGNITO_USER_POOL_ID"] = "us-east-1_TestPool"
os.environ["COGNITO_CLIENT_ID"] = "test-client-id"

import jwt as pyjwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

import cognito_auth


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def make_keypair():
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = private.public_key()
    numbers = public.public_numbers()
    n = numbers.n.to_bytes((numbers.n.bit_length() + 7) // 8, "big")
    e = numbers.e.to_bytes((numbers.e.bit_length() + 7) // 8, "big")
    jwk = {"kty": "RSA", "kid": "test-key-1", "use": "sig", "alg": "RS256",
           "n": _b64url(n), "e": _b64url(e)}
    pem = private.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return pem, jwk, private


NOW = int(time.time())
ISSUER = "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_TestPool"


def mint(private_pem, **overrides):
    payload = {
        "sub": "user-sub-123",
        "email": "patient@example.com",
        "name": "Test Patient",
        "cognito:groups": ["Patients"],
        "iss": ISSUER,
        "aud": "test-client-id",
        "token_use": "id",
        "iat": NOW - 60,
        "exp": NOW + 3600,
    }
    payload.update(overrides)
    return pyjwt.encode(payload, private_pem, algorithm="RS256",
                        headers={"kid": overrides.pop("kid", "test-key-1")})


def run():
    pem, jwk, _private = make_keypair()
    other_pem, _other_jwk, _other = make_keypair()
    # Stub the JWKS fetch: the verifier only ever sees this one key.
    from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicNumbers
    n = int.from_bytes(base64.urlsafe_b64decode(jwk["n"] + "=" * (-len(jwk["n"]) % 4)), "big")
    e = int.from_bytes(base64.urlsafe_b64decode(jwk["e"] + "=" * (-len(jwk["e"]) % 4)), "big")
    stub_keys = {"test-key-1": RSAPublicNumbers(e, n).public_key()}
    cognito_auth._jwks = stub_keys
    cognito_auth._fetch_jwks = lambda: stub_keys

    cases = []

    def check(name, got, want):
        ok = (got == want)
        cases.append((name, ok, got, want))
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  (got {got!r}, want {want!r})"))

    # 1. Valid token -> payload returned
    p = cognito_auth.verify_token(mint(pem))
    check("valid token accepted", bool(p) and p.get("email") == "patient@example.com", True)
    # 2. Expired -> rejected
    check("expired token rejected", cognito_auth.verify_token(mint(pem, exp=NOW - 10)), None)
    # 3. Wrong issuer -> rejected
    check("wrong issuer rejected",
          cognito_auth.verify_token(mint(pem, iss="https://cognito-idp.us-east-1.amazonaws.com/us-east-1_Other")), None)
    # 4. Forged (signed with a different key) -> rejected
    check("forged token rejected", cognito_auth.verify_token(mint(other_pem)), None)
    # 5. Access token (token_use=access) -> rejected (we only accept id tokens)
    check("access token rejected", cognito_auth.verify_token(mint(pem, token_use="access")), None)
    # 6. Wrong audience -> rejected
    check("wrong audience rejected", cognito_auth.verify_token(mint(pem, aud="other-client")), None)
    # 7. Tampered payload (valid signature over different body) -> rejected
    good = mint(pem)
    head, body, sig = good.split(".")
    tampered = head + "." + _b64url(json.dumps({"email": "admin@example.com", "iss": ISSUER, "aud": "test-client-id", "token_use": "id", "exp": NOW + 3600}).encode()) + "." + sig
    check("tampered token rejected", cognito_auth.verify_token(tampered), None)
    # 8. Unknown kid -> rejected (re-fetch returns the same stub keys)
    check("unknown kid rejected", cognito_auth.verify_token(mint(pem, kid="no-such-key")), None)
    # 9. Garbage -> rejected, no exception
    check("garbage rejected", cognito_auth.verify_token("not.a.token"), None)
    check("empty rejected", cognito_auth.verify_token(""), None)

    # Role mapping
    check("Admins group -> admin",
          cognito_auth.role_from_payload({"cognito:groups": ["Patients", "Admins"]}), "admin")
    check("custom:role admin -> admin",
          cognito_auth.role_from_payload({"custom:role": "admin"}), "admin")
    check("Patients group -> patient",
          cognito_auth.role_from_payload({"cognito:groups": ["Patients"]}), "patient")
    check("no groups, no role -> patient (safe default)",
          cognito_auth.role_from_payload({"email": "x@example.com"}), "patient")

    failed = [c for c in cases if not c[1]]
    print(f"\n{len(cases) - len(failed)}/{len(cases)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(run())
