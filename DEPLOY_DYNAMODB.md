# Deploy — DynamoDB version

The project no longer uses RDS MySQL. Databases are 11 DynamoDB tables
(PAY_PER_REQUEST). This file is the short deploy guide for this version;
the full steps are in `README.md` (STEP 1–8).

## 0. Replace your repo with this ZIP

Unzip this file over your repo (or copy the changed files in — see
`CHANGES_DYNAMODB.md` for the full list), commit and push to `main`.

> ⚠️ **Old data warning:** `terraform apply` will **destroy the 6 RDS
> instances** and their data. If the current AWS account still has live
> data you need, export it first (`mysqldump` per database). There is
> **no automatic MySQL → DynamoDB import** — the new tables start with
> the 64 sample items only.

## 1. Terraform (fresh account, or the current one)

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars: ses creds + ses_from_email only.
# (There is no db_password anymore.)
terraform init
terraform plan -var-file=terraform.tfvars
terraform apply -var-file=terraform.tfvars
```

Takes ~5 minutes (DynamoDB tables are created in seconds; EC2 takes
the longest). What you get: 11 DynamoDB tables, 8 Lambdas (7 services
+ db-init), API Gateway, S3, EC2, IAM. **No RDS, no NAT gateway, no
private subnets** — the Lambdas run outside the VPC now.

If your Terraform state describes a **dead/old AWS account**, start
with a fresh state (delete `terraform.tfstate*` / re-init) instead of
reusing it — otherwise apply will try to manage resources that no
longer exist.

## 2. Check the data seeded itself

```bash
terraform output dynamodb_tables
terraform output -raw api_gateway_url   # <-- new API URL, save it
aws dynamodb scan --table-name hospital-patients --select COUNT
# → Count: 5
```

If the count is 0, run the seed by hand (it is safe to re-run):
```bash
aws lambda invoke --function-name hospital-db-init-service /tmp/db-init.json
cat /tmp/db-init.json   # {"status": "seeded", "inserted": 64, ...}
```

## 3. Wire the frontend + run the pipeline

1. GitHub repo → Settings → Secrets and variables → **Actions** →
   **Variables** → set `API_BASE_URL` to the new `api_gateway_url`
   (it is a **Variable**, not a Secret).
2. Check the Secrets `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`
   belong to the account you just deployed to.
3. Push to `main` (or Actions → Run workflow). The pipeline deploys
   the Lambda code, runs the db-init seed, publishes the frontend to
   S3 + GitHub Pages, and smoke-tests a real login + `GET /patients`.

## 4. Test

Open the Pages site (or the S3 URL from the outputs), login with
`admin` / `admin123` (+ OTP), and walk every module once: Patients,
Billing (create bill → record payment → dues update), Diseases,
Doctors (assignment), Laboratory (order a test), Pharmacy (prescribe
→ dispense, stock drops by exactly the quantity).

## What changed vs the RDS version

- Money (amounts, prices) now arrives from the API as a JSON **number**
  (`800`) instead of a string (`"800.00"`). The frontend already
  parses both, so nothing breaks.
- The SMTP receipt-email timeout is now 5s (was 30s) — the old value
  could stall a payment past API Gateway's ~29s limit.
- Local dev: `backend/local_server.py` now talks to DynamoDB. Set
  `DYNAMODB_ENDPOINT_URL` to run against DynamoDB Local, otherwise it
  uses the real AWS tables (needs AWS credentials in the environment).
