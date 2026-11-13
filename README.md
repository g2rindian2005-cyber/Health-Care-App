# 🏥 AWS Hospital Management System

A cloud-native hospital management application with **11 DynamoDB
tables**, **7 serverless Lambda microservices**, **API Gateway**,
**S3** static hosting, **EC2** (Nginx), **SES SMTP** email, and a
**fully animated 3D frontend** — all deployed with **Terraform**.

## Project Structure
```
AWS-Hospital-Management-System/
│
├── frontend/                    → Website (jo user dekhta hai)
│   ├── patients/                → Add / View / History
│   ├── billing/                 → Create Bill / Payments / Pending Dues
│   ├── diseases/                → Add Disease / History
│   ├── doctors/                 → Add / Assign / Appointments
│   ├── laboratory/              → Lab Orders / Order Test / Test Catalog
│   ├── pharmacy/                → Prescriptions / Add / Medicine Catalog
│   ├── js/                      → api.js (server se baat), ui.js (design + dark mode),
│   │                              patients/billing/diseases/doctors/laboratory/pharmacy.js
│   ├── css/style.css            → pura design
│   ├── dashboard.html           → main dashboard
│   ├── login.html               → OTP + JWT login
│   ├── index.html               → landing page
│   ├── reports.html
│   └── settings.html
│
├── backend/                     → Server-side code (7 Lambda services)
│   ├── auth-lambda/             → Login + OTP + JWT
│   ├── patient-lambda/          → Patients API
│   ├── billing-lambda/          → Bills + Payments API
│   ├── disease-lambda/          → Diseases API
│   ├── doctor-lambda/           → Doctors + Assignments API
│   ├── lab-lambda/              → Laboratory API
│   ├── pharmacy-lambda/         → Pharmacy API
│   └── local_server.py          → computer pe chalane ke liye
│      (har service: lambda_function.py + dynamodb.py — dynamodb.py
│       DynamoDB tables se judta hai, dusre tables ko live padhta hai)
│   ├── db-init-lambda/          → sample data seed karne wala Lambda
│   │   └── seed/*.json          → 64 sample items (patients, bills, …)
│
├── database/                    → purane MySQL schema files hata diye gaye —
│                                  DynamoDB me schema nahi hota; seed data ab
│                                  backend/db-init-lambda/seed/*.json me hai
│
├── terraform/                   → AWS pe deploy karne ka code
│   ├── main.tf                  → VPC, DynamoDB tables, 7× Lambda + db-init, API, S3, EC2 — sab
│   ├── variables.tf
│   ├── outputs.tf               → dynamodb_tables, api_gateway_url, …
│   └── deploy.sh
│
├── aws/                         → AWS guides (api-gateway, ec2, iam, lambda, rds, s3, ses-smtp)
├── docs/                        → MANUAL_DEPLOY.md, architecture, CICD
├── email/                       → Email templates + SMTP (OTP + receipts)
├── config/                      → config.py + .env.example
├── scripts/                     → validate_frontend.py
├── .github/workflows/           → CI/CD pipeline
└── requirements.txt   .gitignore   README.md
```

## The DynamoDB tables (all synchronised via shared `patient_id`)
| # | Table                        | Partition key     | Purpose                                |
|---|------------------------------|-------------------|----------------------------------------|
| 1 | hospital-patients            | patient_id        | Patient names & personal info          |
| 2 | hospital-bills               | bill_id           | Bills (GSI: patient_id)                |
| 3 | hospital-payments            | payment_id        | Payment history (GSIs: bill_id, patient_id) |
| 4 | hospital-diseases            | disease_id        | Patient disease / diagnosis records (GSI: patient_id) |
| 5 | hospital-doctors             | doctor_id         | Doctors                                |
| 6 | hospital-doctor-assignments  | assignment_id     | Doctor↔patient assignments (GSIs: patient_id, doctor_id) |
| 7 | hospital-lab-tests           | test_id           | Lab test catalog                       |
| 8 | hospital-lab-orders          | order_id          | Lab orders (GSI: patient_id)           |
| 9 | hospital-medicines           | medicine_id       | Medicine catalog + stock               |
| 10 | hospital-prescriptions       | prescription_id   | Prescriptions (GSI: patient_id)        |
| 11 | hospital-id-counters         | table_name        | Sequential ids (replaces AUTO_INCREMENT) |

Each former MySQL table is now its own DynamoDB table (PAY_PER_REQUEST
— no instances, no capacity planning, no VPC). Cross-table JOINs do
not exist in DynamoDB, so the Lambdas read each other's data **live**
— every service knows every table's name and attaches names and
summaries per request (BatchGetItem + GSI queries). The shared
`patient_id` key links them together. Ids stay small sequential
numbers (1, 2, 3, …) via an atomic counter — exactly like MySQL
AUTO_INCREMENT.

## Tech Stack
- **Frontend**: HTML5, CSS3 (3D transforms, glassmorphism, animations), Vanilla JS
- **Backend**: Python 3.11 AWS Lambda (7 microservices)
- **API**: Amazon API Gateway (REST, per-base-path proxy)
- **Database**: Amazon DynamoDB — **11 tables, PAY_PER_REQUEST** (one per former MySQL table + id counters)
- **Storage**: Amazon S3 (static website) + EC2/Nginx
- **Email**: Amazon SES SMTP
- **Infra**: Terraform (VPC, DynamoDB, Lambda, API GW, S3, EC2, IAM)

---

# 🚀 Complete Deploy Steps

> 📖 **For the full detailed walkthrough with verification & troubleshooting,
> see [`docs/deployment-guide.md`](docs/deployment-guide.md).**

## Prerequisites
- AWS account with admin access
- Terraform >= 1.3 installed
- AWS CLI configured (`aws configure`)
- Python 3.11+ (for local testing)
- An EC2 key pair named `hospital-key`

## STEP 1 — Create EC2 Key Pair
```bash
aws ec2 create-key-pair --key-name hospital-key \
  --query 'KeyMaterial' --output text > ~/.ssh/hospital-key.pem
chmod 600 ~/.ssh/hospital-key.pem
```

## STEP 2 — Verify an SES Sender Email
```bash
aws ses verify-email-identity --email-address noreply@yourdomain.com --region us-east-1
# Check inbox, click verification link
```
Then generate SMTP credentials:
AWS Console → SES → SMTP Settings → Create My SMTP Credentials
Copy the username + password for `terraform.tfvars`.

## STEP 3 — Deploy Infrastructure with Terraform
```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars: ses creds, ses_from_email (no database password anymore)
terraform init
terraform plan -var-file=terraform.tfvars
terraform apply -var-file=terraform.tfvars
```
Wait ~5 minutes (DynamoDB tables are created in seconds; the EC2
instance takes the longest).

**What gets created:**
- **11 DynamoDB tables — PAY_PER_REQUEST** (`hospital-patients`,
  `hospital-bills`, `hospital-payments`, `hospital-diseases`,
  `hospital-doctors`, `hospital-doctor-assignments`, `hospital-lab-tests`,
  `hospital-lab-orders`, `hospital-medicines`, `hospital-prescriptions`,
  `hospital-id-counters`), each with the GSIs the Lambdas query
- **8 Lambda functions** (auth, patient, billing, disease, doctor, lab,
  pharmacy + **db-init**). The data Lambdas run **outside the VPC**
  (DynamoDB is reached via the AWS API, so no NAT gateway is needed)
  and every Lambda receives all table names as environment variables
- API Gateway (REST, per-base-path proxy routes), S3 website bucket,
  EC2/Nginx frontend host, IAM roles, VPC (public subnets only)

> **Upgrading from the old RDS setup?** `terraform apply` will
> **destroy the 6 RDS instances** (and the NAT gateway, private
> subnets and RDS security groups) and create the DynamoDB tables.
> The data starts empty — STEP 4 seeds it automatically.
> **Your old MySQL data does NOT migrate automatically** — if the old
> account still has live data you need, export it before applying
> (e.g. `mysqldump` per database); there is no automatic MySQL →
> DynamoDB import in this repo.
> If the lab/pharmacy Lambdas were ever created by hand (AWS CLI)
> outside Terraform, delete those two functions and their `/lab` and
> `/pharmacy` API resources first, or the apply will hit name
> conflicts.

## STEP 4 — Data is seeded automatically (no manual step)
The `hospital-db-init-service` Lambda runs once right after
`terraform apply` (via `aws_lambda_invocation`) and loads the sample
data into the tables — **5 patients, 5 doctors, 5 diseases,
5 assignments, 5 bills, 3 payments, 12 lab tests, 6 lab orders,
12 medicines, 6 prescriptions** (64 items, from
`backend/db-init-lambda/seed/*.json`).

Verify it worked:
```bash
aws dynamodb scan --table-name hospital-patients --select COUNT
# → Count: 5
aws lambda invoke --function-name hospital-db-init-service /tmp/db-init.json
cat /tmp/db-init.json   # {"status": "seeded", "inserted": 64, ...}
```
Re-running the seed is safe: items that already exist are left
untouched and the id counters are only ever raised, never lowered.
The CI/CD pipeline also runs the seed after every deploy
(`scripts/ensure_db_init_lambda.py`).

## STEP 5 — Wire the Frontend to API Gateway
```bash
API=$(terraform output -raw api_gateway_url)
echo "API: $API"
# Set it as the default in frontend/js/api.js (the API_BASE_URL fallback),
# or serve a js/config.js that sets window.HMS_CONFIG = { apiBase: "$API" }
# before api.js loads — config.js wins when present.
grep -n "execute-api" frontend/js/api.js   # find the current default
sed -i "s|https://[a-z0-9]*\.execute-api\.[a-z0-9-]*\.amazonaws\.com/prod|$API|g" frontend/js/api.js
```

## STEP 6 — Upload Frontend to S3
```bash
aws s3 sync frontend/ s3://hospital-management-frontend-bucket/ --delete
```
S3 website URL (from outputs):
```bash
terraform output s3_website_url
# → http://hospital-management-frontend-bucket.s3-website-us-east-1.amazonaws.com
```

## STEP 7 — (Optional) Deploy Frontend to EC2/Nginx
The EC2 user-data script already installed Nginx. Sync S3 → EC2:
```bash
EC2IP=$(terraform output -raw ec2_public_ip)
ssh -i ~/.ssh/hospital-key.pem ubuntu@$EC2IP \
  "aws s3 sync s3://hospital-management-frontend-bucket/ /var/www/hospital/ --delete"
echo "Open: http://$EC2IP"
```

## STEP 8 — Test the App (every feature)
1. Open the S3 website URL, the EC2 IP, or the GitHub Pages site.
2. Login with `admin` / `admin123`, then enter the OTP. Until the SES
   sender is verified (STEP 2/9), the code is shown on the login page
   itself; afterwards it arrives by email only.
3. Walk every module once — each one reads/writes its own DynamoDB
   table and pulls names live from the others:
   - **Dashboard** — stat cards and charts load
   - **Patients** — add a patient; open the patient → history shows
     bills, diseases and assignments from the other instances
   - **Doctors** — add a doctor; create an assignment (appointment)
   - **Diseases** — add a diagnosis for the patient
   - **Billing** — create a bill, record a payment, check Pending Dues
   - **Laboratory** — order a test, update its status/result
   - **Pharmacy** — create a prescription, dispense it (stock drops)
   - **Reports** — totals match the data you just entered
4. Check the patient's email for SES notifications (bill / receipt /
   appointment), once SES is verified.

## STEP 9 — Request SES Production Access
While in sandbox, only verified emails can receive notifications.
AWS Console → SES → Account dashboard → Request Production access.

## STEP 10 — Tear Down (stop costs)
Destroys everything, including **all six RDS instances**:
```bash
cd terraform
terraform destroy -var-file=terraform.tfvars
```

---

## Local Development (without AWS)
The frontend ships with a **mock-data fallback** so the UI works
immediately without any backend. Just open `frontend/index.html` in
a browser, or serve the folder:
```bash
cd frontend
python -m http.server 8080
# open http://localhost:8080
```

## Key Files Quick Reference
| What              | Where                                              |
|-------------------|----------------------------------------------------|
| Frontend entry    | `frontend/index.html`                              |
| API client        | `frontend/js/api.js`                               |
| Lambda handlers    | `backend/*/lambda_function.py`                     |
| DB schemas        | `database/*/*.sql`                                 |
| Email templates   | `email/templates/*.html`                           |
| Infra             | `terraform/main.tf`                                |
| API docs          | `docs/api-documentation.md`                        |
| Architecture      | `docs/architecture.md`                             |
