# What changed — RDS MySQL → DynamoDB (2026-11-13)

Every file changed for this migration, so you can review it file by
file instead of guessing.

## Design

- **11 DynamoDB tables, PAY_PER_REQUEST** (no instances, no capacity
  planning, no VPC): one table per former MySQL table —
  `hospital-patients`, `hospital-doctors`, `hospital-doctor-assignments`,
  `hospital-diseases`, `hospital-bills`, `hospital-payments`,
  `hospital-lab-tests`, `hospital-lab-orders`, `hospital-medicines`,
  `hospital-prescriptions` — plus `hospital-id-counters`, which replaces
  MySQL AUTO_INCREMENT with an atomic counter (ids stay 1, 2, 3, …).
- **GSIs** (projection ALL) for the foreign-key lookups: assignments by
  patient_id / doctor_id; diseases, bills, lab_orders, prescriptions
  by patient_id; payments by bill_id / patient_id.
- **API contract unchanged**: same routes, same validations, same
  messages, same response keys. The frontend is untouched.
- **MySQL behaviours re-implemented in code**: `net_amount` (was a
  GENERATED column: amount − discount), the payment trigger (bill
  becomes Paid/Partial after a payment), `DEFAULT CURRENT_TIMESTAMP`
  dates, and the pharmacy dispense guard (conditional update —
  stock can never go negative or be cut twice).

## Added

- `backend/*/dynamodb.py` (7 copies, one per Lambda) — shared
  DynamoDB helper: get/scan/query-by-GSI/put/update/delete,
  `fetch_by_ids` (BatchGetItem, replaces the old SQL helper),
  `next_id` / `set_counter`, Decimal normalisation. Replaces
  `db_connection.py`.
- `backend/db-init-lambda/` — seeds the tables: `lambda_function.py`,
  `dynamodb.py`, `requirements.txt`, `seed/*.json` (64 items converted
  1:1 from the old SQL sample files, incl. the 12 lab tests and 12
  medicines). Idempotent — re-running never resets live data.
- `scripts/ensure_db_init_lambda.py` — pipeline step that creates/
  updates the db-init Lambda and invokes it after every deploy.
- `database/README.md` — explains where the SQL files went.
- `DEPLOY_DYNAMODB.md` (this deploy guide) + `CHANGES_DYNAMODB.md`.

## Changed

- `backend/{patient,billing,disease,doctor,lab,pharmacy}-lambda/lambda_function.py`
  — rewritten to DynamoDB via `dynamodb.py`. Also now returns
  **503 `{"error": "Database unavailable"}`** when DynamoDB is down
  instead of a blank 502 (the graceful-error fix from main, which this
  ZIP was missing).
- `backend/*/requirements.txt` — `PyMySQL` → `boto3` (boto3 is already
  in the Lambda runtime; the layer still carries `cryptography`).
- `backend/local_server.py` — loads `dynamodb` instead of
  `db_connection`; supports `DYNAMODB_ENDPOINT_URL` (DynamoDB Local).
- `terraform/main.tf` — RDS instances, DB subnet group, RDS/Lambda
  security groups, private subnets, NAT gateway + EIP, private route
  tables **removed**; `aws_dynamodb_table.hospital` (for_each over the
  11 tables) added; Lambda IAM role now uses
  `AWSLambdaBasicExecutionRole` + a DynamoDB policy (tables + GSIs);
  Lambdas run **outside the VPC** (no `vpc_config`); db-init Lambda +
  `aws_lambda_invocation.db_init` added; table names in `common_env`
  instead of `DB_HOST_*` / `DB_USER` / `DB_PASSWORD`.
- `terraform/variables.tf` — `db_instance_class`,
  `db_allocated_storage`, `db_name`, `db_username`, `db_password`
  removed.
- `terraform/outputs.tf` — `rds_endpoints` → `dynamodb_tables`;
  reminder rewritten (no SQL steps).
- `terraform/terraform.tfvars.example` — RDS section removed.
- `terraform/build_layer.py` — comment updated (boto3, not PyMySQL).
- `.github/workflows/main.yml` — import-tests the db-init handler,
  packages `dist/lambda/db-init.zip`, new deploy step "Ensure db-init
  Lambda and seed DynamoDB", smoke test now also does a real login +
  `GET /patients` (fails CI if the database is empty/dead).
- `email/smtp_config.py` — **SMTP timeout 30s → 5s** (the payment-stall
  fix that was pending; included here, one line — revert it if you
  want the old value).
- `aws/iam/iam-policies.json` — RDSAccess → DynamoDBAccess.
- `aws/ec2/install-nginx.sh` — mysql-client install step removed.
- `README.md` — intro, structure, tables table, tech stack, STEP 3–4
  and STEP 8 rewritten for DynamoDB.
- `docs/MANUAL_DEPLOY.md`, `docs/deployment-guide.md`,
  `docs/architecture.md`, `docs/database-design.md`,
  `docs/api-documentation.md` — migration notice prepended (their
  MySQL content is now historical).

## Deleted

- `database/**/*.sql` — all schema + sample-data SQL files (patients,
  bills, payments, diseases, doctors, doctor_assignments, laboratory,
  pharmacy, sample_data.sql). Their content lives on as
  `backend/db-init-lambda/seed/*.json`.
- `backend/*/db_connection.py` (6 files) — replaced by `dynamodb.py`.

## Unchanged

- `frontend/` — no changes at all.
- `backend/auth-lambda/` — no database, untouched.
- `email/` (except the one-line timeout), `config/`, `aws/` (except the
  two files above), `requirements.txt`, `REDESIGN_AUDIT.md`.

## Behaviour notes (read before deploying)

1. **Money is now a JSON number, not a string.** pymysql returned
   DECIMAL, which the handlers serialised as `"800.00"`; DynamoDB
   numbers normalise to `800` / `800.5`. The frontend parses both
   (`parseFloat` works on numbers), so nothing breaks — but if any
   custom code does string operations on amounts, check it.
2. **No automatic data migration.** `terraform apply` destroys the RDS
   instances. Export old data first if you need it.
3. **Seed items have no `created_at`/`updated_at` from the old SQL**
   (MySQL filled those in); the db-init Lambda stamps the current
   time instead — same as MySQL's `DEFAULT CURRENT_TIMESTAMP`.
4. **NULL columns are now absent attributes.** A field set to `""`
   in an update is REMOVEd from the item (the MySQL equivalent of
   setting it to NULL); the API simply omits the key instead of
   returning `null`. The frontend treats both as empty.

## Verified

- `terraform fmt -check` + `terraform validate` — pass.
- `python -m compileall` on backend + scripts — pass.
- `main.yml` parses as YAML — pass.
- Fake-DynamoDB harness (`~/workspace/harness-dynamodb/run_tests.py`,
  kept outside the ZIP): **77/77 checks pass** — seed (64 items,
  idempotent), every route of all 6 services, dues math, bill
  Paid/Partial trigger, net_amount, pharmacy stock guard (cut once,
  insufficient stock 400), and 503 when DynamoDB is down.
