"""Local tests for backend/cognito-migration-lambda/lambda_function.py.

Simulates the Cognito trigger events — no AWS, no network.
The DynamoDB table is stubbed with an in-memory dict, and the
test password hashes are produced by the RETIRED auth Lambda's own
_hash_password (loaded from the repo under a distinct module name),
proving the migration Lambda accepts exactly the hashes the old
system stored.

Run:  python3 tests/test_migration_lambda.py
Exit code 0 = all cases pass.
"""

import importlib.util
import os
import sys

HERE = os.path.dirname(__file__)
REPO = os.path.join(os.path.expanduser("~"), "workspace", "hca-main")

os.environ["USERS_TABLE"] = "hospital-users"
os.environ["AUTH_EMAIL"] = "admin@example.com"
os.environ["AUTH_PASSWORD"] = "admin123"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# The retired auth Lambda — only its _hash_password is used, to mint
# test hashes exactly the way the old system stored them.
auth_lambda = load_module(
    "retired_auth_lambda",
    os.path.join(REPO, "backend", "auth-lambda", "lambda_function.py"),
)
migration = load_module(
    "migration_lambda",
    os.path.join(HERE, "..", "backend", "cognito-migration-lambda", "lambda_function.py"),
)


class FakeTable:
    def __init__(self, items):
        self.items = items

    def get_item(self, Key):
        item = self.items.get(Key["email"])
        return {"Item": item} if item else {}


# Test users, hashed with the OLD auth Lambda's function.
USERS = {
    "patient@example.com": {
        "email": "patient@example.com",
        "name": "Test Patient",
        "password_hash": auth_lambda._hash_password("patientpass"),
        "role": "patient",
    },
    "oldadmin@example.com": {
        "email": "oldadmin@example.com",
        "name": "Old Admin",
        "password_hash": auth_lambda._hash_password("oldadminpass"),
        "role": "admin",
    },
}

# Stub the table lookup + the Cognito client used by post-auth.
migration._users = lambda: FakeTable(USERS)

cognito_calls = []


class FakeCognito:
    def admin_add_user_to_group(self, UserPoolId, Username, GroupName):
        cognito_calls.append((UserPoolId, Username, GroupName))


migration.boto3.client = lambda service: FakeCognito()


def migration_event(email, password, source="UserMigration_Authentication"):
    return {
        "triggerSource": source,
        "userName": email,
        "userPoolId": "us-east-1_TestPool",
        "request": {"password": password},
        "response": {},
    }


def post_auth_event(email, groups):
    return {
        "triggerSource": "PostAuthentication_Authentication",
        "userName": email,
        "userPoolId": "us-east-1_TestPool",
        "request": {"groupConfiguration": {"groupsToOverride": groups}},
        "response": {},
    }


def run():
    cases = []

    def check(name, ok, extra=""):
        cases.append((name, ok))
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else "  " + extra))

    # (a) Existing patient, correct password -> migrated, patient role
    try:
        out = migration.lambda_handler(
            migration_event("patient@example.com", "patientpass"), None)
        attrs = out["response"]["userAttributes"]
        check("existing user + correct password migrates",
              attrs.get("email") == "patient@example.com"
              and attrs.get("email_verified") == "true"
              and attrs.get("name") == "Test Patient"
              and attrs.get("custom:role") == "patient"
              and out["response"].get("finalUserStatus") == "CONFIRMED"
              and out["response"].get("messageAction") == "SUPPRESS",
              str(out["response"]))
    except Exception as exc:
        check("existing user + correct password migrates", False, repr(exc))

    # (b) Existing user, wrong password -> failure
    try:
        migration.lambda_handler(
            migration_event("patient@example.com", "wrongpass"), None)
        check("wrong password fails", False, "no exception raised")
    except Exception as exc:
        check("wrong password fails", str(exc) == "Invalid credentials", repr(exc))

    # (c) Unknown email -> failure
    try:
        migration.lambda_handler(
            migration_event("nobody@example.com", "whatever"), None)
        check("unknown email fails", False, "no exception raised")
    except Exception as exc:
        check("unknown email fails", str(exc) == "Invalid credentials", repr(exc))

    # (d) Built-in admin (email + admin password) -> Admins role
    try:
        out = migration.lambda_handler(
            migration_event("admin@example.com", "admin123"), None)
        attrs = out["response"]["userAttributes"]
        check("built-in admin migrates to Admins group",
              attrs.get("custom:role") == "admin"
              and attrs.get("name") == "Administrator"
              and out["response"].get("finalUserStatus") == "CONFIRMED",
              str(out["response"]))
    except Exception as exc:
        check("built-in admin migrates to Admins group", False, repr(exc))

    # (e) Admin email, wrong password -> failure
    try:
        migration.lambda_handler(
            migration_event("admin@example.com", "not-the-password"), None)
        check("admin wrong password fails", False, "no exception raised")
    except Exception as exc:
        check("admin wrong password fails", str(exc) == "Invalid credentials", repr(exc))

    # (f) Pre-panel account with stored role "admin" -> admin role
    try:
        out = migration.lambda_handler(
            migration_event("oldadmin@example.com", "oldadminpass"), None)
        check("stored role admin migrates as admin",
              out["response"]["userAttributes"].get("custom:role") == "admin",
              str(out["response"]))
    except Exception as exc:
        check("stored role admin migrates as admin", False, repr(exc))

    # (g) Forgot-password trigger uses the same verification
    try:
        out = migration.lambda_handler(
            migration_event("patient@example.com", "patientpass",
                            "UserMigration_ForgotPassword"), None)
        check("forgot-password trigger migrates too",
              out["response"].get("finalUserStatus") == "CONFIRMED",
              str(out["response"]))
    except Exception as exc:
        check("forgot-password trigger migrates too", False, repr(exc))

    # (h) Post-auth: no groups + stored admin -> added to Admins,
    # and the token's groups are overridden for this session
    cognito_calls.clear()
    out = migration.lambda_handler(post_auth_event("oldadmin@example.com", []), None)
    check("post-auth adds stored admin to Admins",
          cognito_calls == [("us-east-1_TestPool", "oldadmin@example.com", "Admins")]
          and out["response"].get("groupConfiguration", {}).get("groupsToOverride") == ["Admins"],
          str(cognito_calls) + " " + str(out["response"]))

    # (i) Post-auth: no groups + no row -> added to Patients
    cognito_calls.clear()
    out = migration.lambda_handler(post_auth_event("brandnew@example.com", []), None)
    check("post-auth adds new user to Patients",
          cognito_calls == [("us-east-1_TestPool", "brandnew@example.com", "Patients")]
          and out["response"].get("groupConfiguration", {}).get("groupsToOverride") == ["Patients"],
          str(cognito_calls) + " " + str(out["response"]))

    # (j) Post-auth: already grouped -> no Cognito call
    cognito_calls.clear()
    migration.lambda_handler(post_auth_event("patient@example.com", ["Patients"]), None)
    check("post-auth skips already-grouped user", cognito_calls == [], str(cognito_calls))

    # (k) Unknown trigger source -> event passes through untouched
    event = {"triggerSource": "Something_Else", "response": {}}
    check("unknown trigger passes through",
          migration.lambda_handler(event, None) is event)

    failed = [c for c in cases if not c[1]]
    print(f"\n{len(cases) - len(failed)}/{len(cases)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(run())
