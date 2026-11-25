# 🏥 AWS Hospital Management System (HealthCare)

A cloud-native hospital management application — **12 DynamoDB tables**,
**7 serverless Lambda microservices**, **API Gateway**, **S3 + CloudFront**
hosting, **Cognito login**, a **patient panel** for online users and a
separate **doctor panel** — all deployed with **Terraform**.

## What it does

- **Admin dashboard** — patients, billing, diseases, doctors, laboratory,
  pharmacy, reports; live data from Lambda (green status pill on the
  dashboard shows the API is connected).
- **Patient panel** — online users register, sign in, complete their profile,
  book appointments and see their own bookings.
- **Doctor panel** — doctors sign in with their own email and see only
  their own appointments and patients, join video calls, and get in-app
  notifications (new assignment, patient confirmed, patient waiting for
  the video call). Admins assign doctors; doctors do the consulting.
- **Login** — AWS Cognito: sign-up verifies by email code, sign-in is
  password-only (no OTP step). The login page has a **Patient / Doctor /
  Admin** choice. (The account itself decides — an admin account always
  opens the dashboard, a patient account always opens the patient panel,
  a doctor account always opens the doctor panel.)

## Tech stack

- **Frontend**: HTML5, CSS3, Vanilla JS (dark mode, Cognito login)
- **Backend**: Python 3.11 AWS Lambda (7 microservices)
- **API**: Amazon API Gateway (REST)
- **Database**: Amazon DynamoDB — 12 tables, PAY_PER_REQUEST
- **Hosting**: Amazon S3 + CloudFront (HTTPS)
- **Email**: Amazon SES via SMTP (appointment confirmations, lab reports
  and prescriptions sent to the patient)
- **Infra**: Terraform

## Project structure

```
Health-Care-App/
├── .github/workflows/
│   └── main.yml                    # CI/CD pipeline
├── aws/                            # AWS docs
│   ├── api-gateway/api-routes.md
│   ├── iam/iam-policies.json
│   ├── lambda/deployment-guide.md
│   ├── s3/bucket-configuration.md
│   └── ses-smtp/email-configuration.md
├── backend/                        # 8 Lambdas + helpers
│   ├── billing-lambda/             # dynamodb.py, lambda_function.py
│   ├── cognito-migration-lambda/   # old users migrate to Cognito
│   ├── db-init-lambda/             # seeds sample data (10 seed JSONs)
│   ├── disease-lambda/
│   ├── doctor-lambda/              # + cognito_auth.py (RS256/JWKS)
│   ├── lab-lambda/
│   ├── patient-lambda/
│   ├── pharmacy-lambda/
│   └── test-events/                # ready-to-run Lambda test events
├── docs/
│   ├── CICD.md
│   ├── MANUAL_DEPLOY.md            # manual deploy, step by step
│   ├── api-documentation.md
│   ├── architecture.md
│   └── deployment-guide.md
├── email/                          # email templates + SMTP helpers
│   ├── templates/ (appointment, bill, payment-receipt, registration)
│   ├── send_email.py
│   └── smtp_config.py
├── frontend/                       # website
│   ├── billing/ (create-bill, payment, pending-dues)
│   ├── css/style.css
│   ├── diseases/ (add-disease, disease-history)
│   ├── doctor/ (my-appointments, my-patients, consultation-history)
│   ├── doctors/ (add-doctor, appointments, assign-doctor)
│   ├── js/ (api.js, ui.js, video-call.js, qrcode.min.js, upi-qr.js)
│   ├── laboratory/ (lab-orders, order-test, test-catalog)
│   ├── patient/ (book-appointment, my-appointments, my-profile,
│   │   consultation-history, video-visit, my-reports, appointment-confirm)
│   ├── patients/ (add-patient, patient-history, view-patient)
│   ├── pharmacy/ (add-prescription, medicine-catalog, prescriptions)
│   ├── appointment-card.html       # public scannable appointment card
│   ├── dashboard.html
│   ├── index.html
│   ├── login.html                  # Cognito sign-in, Patient/Doctor/Admin
│   ├── register.html               # Cognito sign-up
│   ├── reports.html
│   ├── settings.html
│   └── video-call.html             # real Jitsi video consultation
├── scripts/
│   ├── ensure_db_init_lambda.py
│   └── validate_frontend.py
├── terraform/                      # infra as code
│   ├── main.tf                     # DynamoDB, Lambdas, API GW, Cognito pool
│   ├── variables.tf
│   ├── outputs.tf
│   ├── terraform.tfvars.example
│   ├── deploy.sh
│   └── build_layer.py
├── tests/                          # NEW — Cognito tests (3 files)
├── .gitignore
└── README.md
```

---

# 🚀 Manual deploy (from your own machine)

## 0. You need

- Git, Terraform ≥ 1.5, AWS CLI, Python 3
- An AWS account + access key with permissions for DynamoDB, Lambda,
  API Gateway, S3, CloudFront and IAM:

```bash
aws configure            # region: us-east-1, output: json
aws sts get-caller-identity   # must print your account id
```

## 1. Get the code

```bash
git clone https://github.com/g2rindian2005-cyber/Health-Care-App.git
cd Health-Care-App/terraform
```

Already have it? `git pull` first. (If you changed `config/config.py`
locally, discard those changes first — that file no longer exists in
the repo.)

## 2. Fill in your values

```bash
copy terraform.tfvars.example terraform.tfvars
```

Open `terraform.tfvars` in Notepad and fill in:

- `project_name = "hospital"` — must be `hospital` (the repo validates
  this). The S3 bucket name is fixed to
  `hospital-management-frontend-bucket` and never changes with
  `project_name`. Do NOT create the bucket by hand (`aws s3 mb`) —
  `terraform apply` creates it.
- `auth_admin_password = "your-password"` — the admin login password
  (default is `admin123`; change it).
- SES SMTP (this is how appointment-confirmation and report emails
  reach the patient's inbox) — uncomment these lines and fill them in:

```hcl
smtp_host       = "smtp.gmail.com"
smtp_port       = "587"
smtp_username   = "gokul9356782322@gmail.com"
smtp_password   = "<16-digit App Password, no spaces>"
smtp_from_email = "gokul9356782322@gmail.com"
```

How to make the App Password: sign in as **gokul9356782322@gmail.com** →
2-Step Verification ON → App passwords → Mail → copy the 16-digit code.

> ⚠️ Never commit `terraform.tfvars` — it holds passwords, so it is
> gitignored. On a fresh clone it does not exist; copy it from
> `terraform.tfvars.example` as above.

## 3. Deploy the infrastructure

```bash
terraform init
terraform plan
terraform apply
```

`plan` should show ~190 to add and 0 to destroy. Type `yes` at the
`apply` prompt. It takes ~10 minutes (CloudFront is the slow part).

What gets created: 12 DynamoDB tables, 7 Lambda services + db-init,
API Gateway, S3 bucket, CloudFront distribution, IAM roles.

## 4. Note the URLs

```bash
terraform output
```

Write down `cloudfront_url` (the site) and `api_gateway_url` (the API).

## 5. Upload the frontend to S3

```bash
cd ..
aws s3 sync frontend/ s3://hospital-management-frontend-bucket/
```
## doctor run this command in bash 
```bash
anil.gupta@hospital.com
aws cognito-idp admin-create-user --user-pool-id us-east-1_mCsP5CiMk --username anil.gupta@hospital.com --user-attributes Name=email,Value=anil.gupta@hospital.com Name=email_verified,Value=true --message-action SUPPRESS --region us-east-1

aws cognito-idp admin-set-user-password --user-pool-id us-east-1_mCsP5CiMk --username anil.gupta@hospital.com --password 123456789 --permanent --region us-east-1
```
The bucket name is always `hospital-management-frontend-bucket`.
**Do NOT use `--delete` here** — Terraform already
wrote `js/config.js` into the bucket (with the live API URL), and
`--delete` would remove it, leaving the site unable to reach the API.

Data is seeded automatically: the `db-init` Lambda runs once after
`terraform apply` and loads the sample data (5 patients, 5 doctors,
5 diseases, 5 assignments, 5 bills, 12 lab tests, 12 medicines, …).
No SQL, no EC2, no manual step.

## 6. Test it

1. Open the `cloudfront_url` (wait 3–5 minutes for CloudFront first).
2. Register a new account — it becomes a **patient**. Cognito emails a
   verification code; enter it to verify, then sign in with your
   password (no OTP step on sign-in) and the patient panel opens.
3. Sign in as the admin with your admin email and your
   `auth_admin_password` — the dashboard opens. The dashboard shows a
   green pill ("Lambda connected — data live") when the API answers.
4. Book an appointment from the patient panel and check it appears in
   My Appointments.

## 7. Tear down (stop costs)

```bash
cd terraform
terraform destroy
```

This deletes everything the apply created.

## Local development (without AWS)

The frontend has an opt-in mock-data fallback for local UI work only
(`HMS_CONFIG.devMock` — never set in production):

```bash
cd frontend
python -m http.server 8080
# open http://localhost:8080
```
