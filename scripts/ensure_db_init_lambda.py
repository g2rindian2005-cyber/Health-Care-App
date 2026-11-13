#!/usr/bin/env python3
"""Create or update the hospital-db-init-service Lambda and invoke it
to seed the DynamoDB tables (backend/db-init-lambda/seed/*.json).

Used by the CI/CD pipeline after every deploy. The Lambda is also
created by Terraform (aws_lambda_invocation.db_init); this script is
the pipeline's path for when Terraform has not created it yet (e.g.
the function was deleted, or the deploy ran before `terraform apply`).

Usage: python3 scripts/ensure_db_init_lambda.py dist/lambda/db-init.zip

Environment: AWS credentials + AWS_REGION (set by the workflow's
Configure AWS credentials step), PROJECT_NAME (default "hospital").

Exits non-zero when the function cannot be created/updated or when
the seed run reports an error — a failed seed must fail the deploy.
"""
import json
import os
import subprocess
import sys
import zipfile

TABLES = {
    "PATIENTS_TABLE": "hospital-patients",
    "DOCTORS_TABLE": "hospital-doctors",
    "ASSIGNMENTS_TABLE": "hospital-doctor-assignments",
    "DISEASES_TABLE": "hospital-diseases",
    "BILLS_TABLE": "hospital-bills",
    "PAYMENTS_TABLE": "hospital-payments",
    "LAB_TESTS_TABLE": "hospital-lab-tests",
    "LAB_ORDERS_TABLE": "hospital-lab-orders",
    "MEDICINES_TABLE": "hospital-medicines",
    "PRESCRIPTIONS_TABLE": "hospital-prescriptions",
    "COUNTERS_TABLE": "hospital-id-counters",
}


def aws(*args, input_data=None):
    cmd = ["aws", *args]
    result = subprocess.run(cmd, input=input_data, capture_output=True, text=True)
    return result


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: ensure_db_init_lambda.py <db-init.zip>", file=sys.stderr)
        return 2
    zip_path = sys.argv[1]
    if not zipfile.is_zipfile(zip_path):
        print(f"not a zip file: {zip_path}", file=sys.stderr)
        return 2

    project = os.environ.get("PROJECT_NAME", "hospital")
    function = f"{project}-db-init-service"
    role_name = f"{project}-lambda-role"

    # --- create or update the function -------------------------------
    exists = aws("lambda", "get-function", "--function-name", function)
    env_vars = ",".join(f"{k}={v}" for k, v in TABLES.items())
    if exists.returncode != 0:
        role = aws("iam", "get-role", "--role-name", role_name,
                   "--query", "Role.Arn", "--output", "text")
        if role.returncode != 0:
            print(f"::error::IAM role {role_name} not found — run terraform apply first.",
                  file=sys.stderr)
            return 1
        create = aws(
            "lambda", "create-function",
            "--function-name", function,
            "--runtime", "python3.11",
            "--role", role.stdout.strip(),
            "--handler", "lambda_function.lambda_handler",
            "--zip-file", f"fileb://{zip_path}",
            "--timeout", "300",
            "--memory-size", "256",
            "--environment", f"Variables={{{env_vars}}}",
        )
        if create.returncode != 0:
            print(f"::error::could not create {function}: {create.stderr}", file=sys.stderr)
            return 1
        print(f"Created {function}")
    else:
        update = aws("lambda", "update-function-code",
                     "--function-name", function,
                     "--zip-file", f"fileb://{zip_path}", "--publish")
        if update.returncode != 0:
            print(f"::error::could not update {function}: {update.stderr}", file=sys.stderr)
            return 1
        aws("lambda", "wait", "function-updated", "--function-name", function)
        aws("lambda", "update-function-configuration",
            "--function-name", function,
            "--environment", f"Variables={{{env_vars}}}")
        aws("lambda", "wait", "function-updated", "--function-name", function)
        print(f"Updated {function}")

    # --- invoke it (seeds the tables; idempotent) ----------------------
    out_file = "/tmp/db-init-result.json"
    invoke = aws("lambda", "invoke",
                 "--function-name", function,
                 "--payload", "{}", out_file)
    if invoke.returncode != 0:
        print(f"::error::could not invoke {function}: {invoke.stderr}", file=sys.stderr)
        return 1
    result = json.loads(invoke.stdout)
    if result.get("FunctionError"):
        print(f"::error::db-init failed: {open(out_file).read()}", file=sys.stderr)
        return 1
    body = json.load(open(out_file))
    payload = json.loads(body.get("body", "{}"))
    print(f"db-init seeded: {payload.get('inserted', '?')} items "
          f"({payload.get('tables', {}) and 'see tables' or ''})")
    print(json.dumps(payload.get("tables", {}), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
