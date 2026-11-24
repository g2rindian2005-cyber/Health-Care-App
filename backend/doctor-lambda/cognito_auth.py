"""Cognito JWT verification (RS256 via JWKS) for the doctor Lambda.

Replaces the old HS256/JWT_SECRET check. The shared Lambda layer
already ships `cryptography`, so no new dependency is needed.

Checks, in order:
  * the token has three parts, header alg is RS256, kid is present
  * the signature verifies against the JWKS key for that kid
    (JWKS fetched once per cold start from the user pool's
    .well-known/jwks.json, re-fetched once on an unknown kid)
  * iss == https://cognito-idp.<region>.amazonaws.com/<pool id>
  * token_use == "id" (the frontend sends the Cognito ID token)
  * aud == the user pool client id
  * exp is in the future (no grace period — both Cognito and
    Lambda run on AWS NTP-synced clocks, so skew is negligible)

Role (used by the appointment ownership check):
  * "admin" when the token's cognito:groups contains "Admins", or
    when the custom:role claim is "admin" (the migration Lambda sets
    it, so a migrated admin has the right role on the very first
    sign-in, before the post-auth trigger has added the group)
  * "doctor" when the token's cognito:groups contains "Doctors", or
    when the custom:role claim is "doctor" (the migration Lambda
    sets it for an email found in hospital-doctors)
  * "patient" otherwise — including when the token carries no groups
    and no role claim. The safe default is patient, never admin.

Configuration (Terraform common_env):
  COGNITO_USER_POOL_ID, COGNITO_CLIENT_ID, AWS_REGION (set by the
  Lambda runtime). When the pool id or client id is missing the
  verifier fails closed: every token is rejected.
"""

import base64
import json
import os
import time
import urllib.request

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicNumbers

REGION = os.environ.get("AWS_REGION", "us-east-1")
POOL_ID = os.environ.get("COGNITO_USER_POOL_ID", "")
CLIENT_ID = os.environ.get("COGNITO_CLIENT_ID", "")
ISSUER = "https://cognito-idp.{}.amazonaws.com/{}".format(REGION, POOL_ID)
JWKS_URL = ISSUER + "/.well-known/jwks.json"

# kid -> RSAPublicKey, fetched once per cold start.
_jwks = None


def _b64url_decode(segment):
    return base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))


def _fetch_jwks():
    global _jwks
    with urllib.request.urlopen(JWKS_URL, timeout=5) as response:
        document = json.loads(response.read().decode("utf-8"))
    keys = {}
    for jwk in document.get("keys", []):
        if jwk.get("kty") != "RSA" or not jwk.get("kid"):
            continue
        n = int.from_bytes(_b64url_decode(jwk["n"]), "big")
        e = int.from_bytes(_b64url_decode(jwk["e"]), "big")
        keys[jwk["kid"]] = RSAPublicNumbers(e, n).public_key()
    _jwks = keys
    return keys


def _key_for(kid):
    keys = _jwks if _jwks is not None else _fetch_jwks()
    key = keys.get(kid)
    if key is None:
        # Key rotation: the kid may be new since the cold start.
        # Re-fetch once, then give up.
        key = _fetch_jwks().get(kid)
    return key


def verify_token(token):
    """Return the Cognito ID-token payload dict, or None if invalid.

    Never raises: any malformed token, fetch failure or bad signature
    is a rejection, not an error.
    """
    if not POOL_ID or not CLIENT_ID:
        return None
    try:
        header_b64, payload_b64, signature_b64 = token.split(".")
        header = json.loads(_b64url_decode(header_b64))
        if header.get("alg") != "RS256" or not header.get("kid"):
            return None
        key = _key_for(header["kid"])
        if key is None:
            return None
        signing_input = "{}.{}".format(header_b64, payload_b64).encode("ascii")
        signature = _b64url_decode(signature_b64)
        key.verify(signature, signing_input, padding.PKCS1v15(), hashes.SHA256())
        payload = json.loads(_b64url_decode(payload_b64))
    except (InvalidSignature, ValueError, KeyError, TypeError, Exception):
        return None
    # Claims — all must hold for the token to be trusted.
    if payload.get("iss") != ISSUER:
        return None
    if payload.get("token_use") != "id":
        return None
    if payload.get("aud") != CLIENT_ID:
        return None
    if int(payload.get("exp", 0)) < int(time.time()):
        return None
    return payload


def role_from_payload(payload):
    """Map a verified Cognito token payload to "admin", "doctor" or "patient"."""
    groups = payload.get("cognito:groups") or []
    if "Admins" in groups:
        return "admin"
    if "Doctors" in groups:
        return "doctor"
    if str(payload.get("custom:role") or "").lower() == "admin":
        return "admin"
    if str(payload.get("custom:role") or "").lower() == "doctor":
        return "doctor"
    return "patient"
