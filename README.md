# 🏥 AWS Hospital Management System (HealtheCare)

A cloud-native hospital management application — **11 DynamoDB tables**,
**7 serverless Lambda microservices**, **API Gateway**, **S3 + CloudFront**
hosting, **Gmail SMTP OTP login**, and a **patient panel** for online users —
all deployed with **Terraform**.

## What it does

- **Admin dashboard** — patients, billing, diseases, doctors, laboratory,
  pharmacy, reports; live data from Lambda (green status pill on the
  dashboard shows the API is connected).
- **Patient panel** — online users register, sign in, complete their profile,
  book appointments and see their own bookings.
- **Login** — two-step: password + 6-digit OTP sent to the user's email.
  The login page has a **Patient / Admin** choice: Admin opens the
  dashboard, Patient opens the patient panel. (The account itself decides —
  an admin account always opens the dashboard, a patient account always
  opens the patient panel.)

## Tech stack

- **Frontend**: HTML5, CSS3, Vanilla JS (dark mode, OTP + JWT login)
- **Backend**: Python 3.11 AWS Lambda (7 microservices)
- **API**: Amazon API Gateway (REST)
- **Database**: Amazon DynamoDB — 11 tables, PAY_PER_REQUEST
- **Hosting**: Amazon S3 + CloudFront (HTTPS)
- **Email**: Gmail SMTP (OTP codes)
- **Infra**: Terraform

## Project structure

```
├── frontend/            → Website (login, dashboard, patient panel)
│   ├── patient/         → my-appointments, book-appointment, my-profile
│   ├── patients/ billing/ diseases/ doctors/ laboratory/ pharmacy/
│   └── js/              → api.js, ui.js (api.js talks to the API)
├── backend/             → 7 Lambda services + db-init-lambda (seeds sample data)
├── terraform/           → main.tf, variables.tf, outputs.tf
├── docs/                → architecture, API docs, CI/CD
├── config/              → config.py + .env.example
└── .github/workflows/   → CI/CD pipeline
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

Already have it? `git pull` first (if `config/config.py` has local
changes, `git stash` before pulling, then `git stash pop`).

## 2. Fill in your values

```bash
copy terraform.tfvars.example terraform.tfvars
```

Open `terraform.tfvars` in Notepad and fill in:

- `project_name = "hospital2"` — the S3 bucket name is
  `<project>-management-frontend-bucket` and must be globally unique,
  so use something other than `hospital` if that bucket already exists.
- `auth_admin_password = "your-password"` — the admin login password
  (default is `admin123`; change it).
- `jwt_secret` — leave empty, Terraform generates one.
- Gmail SMTP (this is how OTP codes reach the user's inbox) —
  uncomment these lines and fill them in:

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

What gets created: 11 DynamoDB tables, 7 Lambda services + db-init,
API Gateway, S3 bucket, CloudFront distribution, IAM roles.

## 4. Note the URLs

```bash
terraform output
```

Write down `cloudfront_url` (the site) and `api_gateway_url` (the API).

## 5. Upload the frontend to S3

```bash
cd ..
aws s3 sync frontend/ s3://hospital2-management-frontend-bucket/
```

The bucket name is `<project>-management-frontend-bucket` from your
`project_name`. **Do NOT use `--delete` here** — Terraform already
wrote `js/config.js` into the bucket (with the live API URL), and
`--delete` would remove it, leaving the site unable to reach the API.

Data is seeded automatically: the `db-init` Lambda runs once after
`terraform apply` and loads the sample data (5 patients, 5 doctors,
5 diseases, 5 assignments, 5 bills, 12 lab tests, 12 medicines, …).
No SQL, no EC2, no manual step.

## 6. Test it

1. Open the `cloudfront_url` (wait 3–5 minutes for CloudFront first).
2. Register a new account — it becomes a **patient**. Sign in, enter
   the OTP from the email, and the patient panel opens.
3. Sign in as `admin` with your `auth_admin_password` — the dashboard
   opens. The dashboard shows a green pill ("Lambda connected — data
   live") when the API answers.
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
