# Manual deployment (from your own machine)

Deploy the whole HealtheCare project with Terraform. Current stack:
**12 DynamoDB tables, 7 Lambda services + db-init + Cognito migration
Lambda, API Gateway, S3 + CloudFront, AWS Cognito sign-in (password
only — no OTP at sign-in), patient panel.** No RDS, no EC2, no MySQL,
no manual SQL — the db-init Lambda seeds the sample data
automatically. The API URL and the Cognito pool/client IDs are written
into `js/config.js` by Terraform on every apply.

> This file matches `README.md` ("Manual deploy"). If the two ever
> disagree, follow `README.md`.

## 0. You need

- Git, Terraform ≥ 1.5, AWS CLI, Python 3
- An AWS account + access key with permissions for DynamoDB, Lambda,
  API Gateway, S3, CloudFront, Cognito and IAM:

```bash
aws configure            # region: us-east-1, output: json
aws sts get-caller-identity   # must print your account id
```

## 1. Get the code

```bash
git clone https://github.com/g2rindian2005-cyber/Health-Care-App.git
cd Health-Care-App/terraform
```

Already have it? `git pull` first. If the pull complains about
`config/config.py`, discard your local changes to that file — it was
deleted from the repo (it did nothing live) and the pull will not
succeed until the local copy is gone:

```bash
git checkout -- config/config.py   # drop local edits, or delete the file
git pull
```

## 2. Fill in your values

```bash
copy terraform.tfvars.example terraform.tfvars
```

Open `terraform.tfvars` in Notepad. Only two values are required —
the rest can stay as they are:

- `ses_from_email = "you@example.com"` — **this is the admin's
  sign-in email.** The admin logs in with this email address, not
  with a username.
- `auth_admin_password = "your-password"` — the admin login password.
  Add this line yourself: it is not in `terraform.tfvars.example`.
  Pick a password you will remember (at least 6 characters).

```hcl
ses_from_email      = "gokul9356782322@gmail.com"
auth_admin_password = "your-password"
```

The other values (`project_name = "hospital2"`, `aws_region`,
`environment`) already have working defaults. The S3 bucket name is
`<project>-management-frontend-bucket` and must be globally unique —
if `hospital2-management-frontend-bucket` already exists in another
account, change `project_name`.

You do **not** need any SMTP / Gmail App Password for sign-in any
more. Cognito sends its own verification and password-reset emails.
The `smtp_*` / `ses_smtp_*` values are leftovers from the old OTP
login and are ignored by sign-in now. Likewise `jwt_secret` and
`auth_admin_username` are unused since the Cognito migration (tokens
are Cognito RS256 JWTs now) — leave them alone.

> ⚠️ Never commit `terraform.tfvars` — it holds passwords, so it is
> gitignored. On a fresh clone it does not exist; copy it from
> `terraform.tfvars.example` as above.

## 3. Deploy the infrastructure

```bash
terraform init
terraform plan
terraform apply
```

`plan` should show ~189 to add and 0 to destroy. Type `yes` at the
`apply` prompt. It takes ~10 minutes (CloudFront is the slow part).

What gets created: 12 DynamoDB tables, 7 Lambda services + db-init +
Cognito migration Lambda, API Gateway, S3 bucket, CloudFront
distribution, Cognito User Pool + app client, IAM roles.
`terraform apply` also writes `js/config.js` into the S3 bucket with
the live API URL and the Cognito pool/client IDs, and sets the same
values on all the Lambdas at once — never set Lambda variables by
hand in the console, the next apply overwrites them.

**If apply stops part-way, just run `terraform apply` again.** The
three things that can bite on a fresh account are already fixed in
this repo, but if they still appear:

- `db-init` fails with `AccessDenied` on DynamoDB — that is IAM
  permissions still propagating. Wait a minute and run
  `terraform apply` again; the second run finishes the seeding.
- Cognito rejects the schema, or the S3 bucket policy is refused —
  both are fixed in `main.tf` (schema name `role`, account-level
  Block Public Access resource). If you are on an old checkout,
  `git pull` first.

If apply stops with "already exists" errors, the account still holds
a previous deployment — change `project_name` and retry, or run
`terraform destroy` on the old one first.

## 4. Note the URLs

```bash
terraform output
```

Write down `cloudfront_url` (the site), `api_gateway_url` (the API),
and `cognito_user_pool_id` / `cognito_client_id`.

## 5. Upload the frontend to S3

```bash
cd ..
aws s3 sync frontend/ s3://hospital2-management-frontend-bucket/
```

The bucket name is `<project>-management-frontend-bucket` from your
`project_name`. **Do NOT use `--delete` here** — Terraform already
wrote `js/config.js` into the bucket, and `--delete` would remove it,
leaving the site unable to reach the API. Do NOT edit `js/api.js`
to paste the API URL either — `config.js` is how the site finds it.

Data is seeded automatically: the `db-init` Lambda runs once after
`terraform apply` and loads the sample data (5 patients, 5 doctors,
5 diseases, 5 assignments, 5 bills, 12 lab tests, 12 medicines, …).
No SQL, no EC2, no manual step.

## 6. Test it

1. Open the `cloudfront_url` (wait 3–5 minutes for CloudFront first).
2. Register a new account — it becomes a **patient**. Cognito emails
   a verification code **once, at sign-up**; enter it and the patient
   panel opens (My Appointments / Book Appointment / My Profile).
   Sign-in after that is password-only — there is no OTP step.
3. Sign in as admin with your **`ses_from_email` address** (not the
   username `admin`) and your `auth_admin_password` — the dashboard
   opens. The login page has a Patient / Admin choice, but the
   **account** decides where you land: admin accounts always open
   the dashboard, patient accounts always open the patient panel.
4. If you forget the admin password, use **"Forgot password?"** on
   the login page — Cognito emails a reset code and you set a new
   password there. (Note: the migration Lambda still holds the old
   `auth_admin_password` for first-time sign-ins of old users, so
   after a reset, update `auth_admin_password` in your tfvars to the
   new password and run `terraform apply` once to keep them in sync.)
5. Book an appointment from the patient panel and check it appears
   in My Appointments.

## 7. How to know Lambda is working

- **Dashboard green pill (easiest):** green
  "● Lambda connected — data live" = Lambda is answering; red
  "● API unreachable" = the API/Lambda is down.
- **Real data on the site:** the Patients page shows real names and
  the dashboard numbers show values, not "—". "Unable to reach the
  server" means the site cannot reach the API at all.
- **Sign-in errors:** "Incorrect username or password" (HTTP 400 in
  the browser console) means the email/password did not match — the
  admin must use the `ses_from_email` address, not `admin`. The
  migration Lambda's log group is
  `/aws/lambda/hospital2-cognito-migration-service` in CloudWatch.
- **AWS Console:** Lambda → a function (e.g. `hospital2-patient-service`)
  → Monitor tab: Invocations going up and Errors at 0 means it runs.
  CloudWatch logs show the reason when something fails.

## 8. The GitHub Actions pipeline (optional)

The repo has a CI/CD workflow (`.github/workflows/main.yml`) that
deploys the frontend and the Lambdas on every push to `main`. It does
**not** run `terraform apply` — infrastructure changes still need the
manual apply above. One catch: the workflow file on `main` is still
the old pre-Cognito version (it tests the retired OTP auth and zips a
deleted Lambda, so it will fail). The Cognito version is kept in this
repo as `docs/ci-cd-cognito-main.yml` — open that file, copy its
contents, and paste them as `.github/workflows/main.yml` in the GitHub
web UI (create the file if it asks). Do this before relying on the
pipeline.

## 9. Tear down (stop costs)

```bash
cd terraform
terraform destroy
```

This deletes everything the apply created.
