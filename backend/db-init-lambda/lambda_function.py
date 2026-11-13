"""
db-init Lambda — seeds the DynamoDB tables with the sample data.

Replaces the old SQL init Lambda (which ran schema + sample-data SQL
files against RDS). There is no schema to create in DynamoDB — tables
are created by Terraform — so this Lambda only writes the seed items
from seed/*.json (converted 1:1 from the old SQL sample files).

Invoked automatically by:
  1. Terraform `aws_lambda_invocation.db_init` after table creation
     (re-runs whenever the code or a seed file changes), and
  2. the CI/CD pipeline after every deploy (scripts/ensure_db_init_lambda.py).

Idempotent: an item whose key already exists is left untouched
(put with attribute_not_exists), and the id counters are only ever
raised, never lowered — re-running never resets user data.
"""
import json
import os
from decimal import Decimal

from botocore.exceptions import ClientError

from dynamodb import table, set_counter, now

SEED_DIR = os.path.join(os.path.dirname(__file__), "seed")

# logical table key -> seed file
SEEDS = {
    "patients": "patients.json",
    "doctors": "doctors.json",
    "assignments": "doctor_assignments.json",
    "diseases": "diseases.json",
    "bills": "bills.json",
    "payments": "payments.json",
    "lab_tests": "lab_tests.json",
    "lab_orders": "lab_orders.json",
    "medicines": "medicines.json",
    "prescriptions": "prescriptions.json",
}


def _to_ddb(value):
    if isinstance(value, float):
        return Decimal(str(value))
    return value


def _seed_one(logical, filename):
    with open(os.path.join(SEED_DIR, filename), encoding="utf-8") as f:
        data = json.load(f)
    tbl = table(logical)
    pk = data["pk"]
    inserted = skipped = max_id = 0
    for item in data["items"]:
        item = dict(item)
        # MySQL DEFAULT CURRENT_TIMESTAMP equivalents
        if "created_at" not in item:
            item["created_at"] = now()
        if "updated_at" not in item:
            item["updated_at"] = now()
        if logical == "patients" and "registration_date" not in item:
            item["registration_date"] = now()
        item = {k: _to_ddb(v) for k, v in item.items()}
        try:
            tbl.put_item(
                Item=item,
                ConditionExpression=f"attribute_not_exists({pk})",
            )
            inserted += 1
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
                skipped += 1  # already seeded — leave the live row alone
            else:
                raise
        max_id = max(max_id, int(item[pk]))
    if max_id:
        set_counter(logical, max_id)
    return {"inserted": inserted, "skipped": skipped, "max_id": max_id}


def lambda_handler(event, context):
    results = {}
    for logical, filename in SEEDS.items():
        results[logical] = _seed_one(logical, filename)
    total = sum(r["inserted"] for r in results.values())
    return {
        "statusCode": 200,
        "body": json.dumps(
            {"status": "seeded", "inserted": total, "tables": results},
            default=str,
        ),
    }
