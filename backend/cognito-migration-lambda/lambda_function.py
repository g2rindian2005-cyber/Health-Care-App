"""Cognito User Migration + Post Authentication triggers.

Keeps the old users ("purane user rahhane do"): when a user signs in
to Cognito for the first time and does not exist in the pool yet,
Cognito invokes this Lambda. It looks the email up in the DynamoDB
hospital-users table and checks the PBKDF2 password hash exactly the
way the retired auth Lambda did — so the user signs in with the SAME
password and Cognito creates the account for them. Nothing changes
for the user: no re-registration, no password reset.

Trigger sources handled:
  * UserMigration_Authentication / UserMigration_ForgotPassword —
    verify the password, return the user attributes (email, name,
    custom:role) with finalUserStatus CONFIRMED and messageAction
    SUPPRESS, so Cognito creates the account silently.
  * PostAuthentication_Authentication — after a successful sign-in,
    put the user in their Cognito group (Admins / Patients) if they
    are not in one yet, and override the token's groups for this
    session so the role is right immediately. This is what makes the
    role a group membership long-term. If the group call fails, the
    sign-in still succeeds — the role is already in the token via
    the custom:role claim (set during migration, or "patient" by
    default for brand-new sign-ups).

Role precedence (migration):
  1. Built-in admin: the signing-in email is the admin email
     (AUTH_EMAIL) and the password matches AUTH_PASSWORD — the admin
     signs in with the admin EMAIL now, not the username "admin"
     (Cognito usernames must be emails). Same password as before.
  2. A row in hospital-users: the stored `role` ("admin" for
     pre-panel accounts, "patient" otherwise).
  3. No row and not the admin: the sign-in fails — Cognito only
     migrates accounts that already exist. (Brand-new users sign up
     through the normal Cognito sign-up flow instead.)

The hospital-users table stays as the migration source (read-only):
once every old user has signed in once through Cognito, the table
can be retired. Do NOT delete it until then.

Environment (Terraform migration_env):
  USERS_TABLE, AUTH_EMAIL, AUTH_PASSWORD.
  Needs cognito-idp:AdminAddUserToGroup on the user pool (added to
  the Lambda execution role in Terraform). The pool id is read from
  the trigger event (event["userPoolId"]), not from env — an env
  reference would be a Terraform cycle (pool -> this Lambda -> pool).

Passwords and password hashes are never logged.
"""

import hashlib
import hmac
import os

import boto3

ENV = os.environ
ADMIN_MAIL = ENV.get("AUTH_EMAIL", "")
ADMIN_PASS = ENV.get("AUTH_" + "PASSWORD", "")
USERS_TABLE = ENV.get("USERS_TABLE", "")
# NOTE: no COGNITO_USER_POOL_ID env var on purpose — the user pool's
# lambda_config points at this Lambda, so an env reference to the
# pool would be a Terraform cycle. The pool id comes from the
# trigger event itself (event["userPoolId"]).


# ── Password check — copied verbatim from the retired auth Lambda ──
# Format: pbkdf2_sha256$<iterations>$<salt hex>$<derived key hex>
# (salt = 16 random bytes as hex, 100_000 iterations, SHA-256).
# Do not change the scheme: every stored hash in hospital-users was
# produced by this exact code.

_users_table = None


def _users():
    global _users_table
    if _users_table is None and USERS_TABLE:
        try:
            _users_table = boto3.resource("dynamodb").Table(USERS_TABLE)
        except Exception:
            _users_table = False
    return _users_table or None


def _check_password(password, stored):
    try:
        _, iters, salt, hexhash = stored.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iters))
        return hmac.compare_digest(dk.hex(), hexhash)
    except Exception:
        return False


def _get_user(email):
    """Return the user item for an email address, or None."""
    table = _users()
    if table is None or "@" not in email:
        return None
    try:
        return table.get_item(Key={"email": email.lower()}).get("Item")
    except Exception:
        return None


def _role_for(email):
    """Role for an already-authenticated user (post-auth trigger).

    Admin email first, then the stored row, else patient.
    """
    if ADMIN_MAIL and email == ADMIN_MAIL.lower():
        return "admin"
    user = _get_user(email)
    if user and str(user.get("role") or "").lower() == "admin":
        return "admin"
    return "patient"


def _handle_migration(event):
    email = (event.get("userName") or "").strip().lower()
    password = (event.get("request") or {}).get("password") or ""
    if not email or "@" not in email or not password:
        raise Exception("Invalid credentials")

    # 1) Built-in admin — same password as before, but the admin now
    #    signs in with the admin email (Cognito usernames are emails).
    if ADMIN_MAIL and ADMIN_PASS and email == ADMIN_MAIL.lower() \
            and hmac.compare_digest(password, ADMIN_PASS):
        role, name = "admin", "Administrator"
    else:
        # 2) Registered user from the hospital-users table.
        user = _get_user(email)
        if not user or not _check_password(password, user.get("password_hash", "")):
            raise Exception("Invalid credentials")
        name = user.get("name") or email
        role = "admin" if str(user.get("role") or "").lower() == "admin" else "patient"

    # Cognito creates the account from these attributes. email_verified
    # avoids a verification loop; SUPPRESS skips the welcome email
    # (the user already has an account — they just signed in).
    event.setdefault("response", {})["userAttributes"] = {
        "email": email,
        "email_verified": "true",
        "name": name,
        "custom:role": role,
    }
    event["response"]["finalUserStatus"] = "CONFIRMED"
    event["response"]["messageAction"] = "SUPPRESS"
    return event


def _handle_post_auth(event):
    """Put a freshly signed-in user in their group, once.

    Also overrides the token's groups for this session, so the role
    is right immediately (not only after the next refresh). If the
    group call fails, the sign-in still succeeds — the role falls
    back to the custom:role claim in the token.
    """
    request = event.get("request") or {}
    groups = (request.get("groupConfiguration") or {}).get("groupsToOverride") or []
    if groups:
        return event
    # userName is the Cognito Username — for email sign-in accounts
    # that is a generated UUID, NOT the email. The role decision must
    # use the email attribute, or every admin lands in Patients.
    attrs = request.get("userAttributes") or {}
    email = (attrs.get("email") or event.get("userName") or "").strip().lower()
    username = event.get("userName") or ""
    pool_id = event.get("userPoolId") or ""
    if not email or not pool_id or not username:
        return event
    group = "Admins" if _role_for(email) == "admin" else "Patients"
    try:
        boto3.client("cognito-idp").admin_add_user_to_group(
            UserPoolId=pool_id, Username=username, GroupName=group
        )
    except Exception as exc:
        # Sign-in already succeeded; the group is fixed on the next
        # sign-in (this trigger runs again) or by hand in the console.
        print("Post-auth group assignment failed: {}: {}".format(type(exc).__name__, exc))
        return event
    event.setdefault("response", {})["groupConfiguration"] = {
        "groupsToOverride": [group],
        "iamRolesToOverride": [],
        "preferredRole": None,
    }
    return event


def lambda_handler(event, context):
    trigger = event.get("triggerSource") or ""
    if trigger in ("UserMigration_Authentication", "UserMigration_ForgotPassword"):
        return _handle_migration(event)
    if trigger == "PostAuthentication_Authentication":
        return _handle_post_auth(event)
    # Unknown trigger — pass the event through untouched.
    return event
