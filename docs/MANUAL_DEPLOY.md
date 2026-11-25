# Manual deployment (from your own machine)

Deploy the whole HealthCare project with Terraform. Current stack:
**12 DynamoDB tables, 7 Lambda services + db-init + Cognito migration
Lambda, API Gateway, S3 + CloudFront, AWS Cognito sign-in (password
only — no OTP at sign-in), patient panel with real video consultation
(Jitsi on meet.ffmuc.net) and a Video Visit page.** No RDS, no EC2, no MySQL,
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

`project_name` must be `"hospital"` — the repo validates it and
`terraform plan` fails otherwise. The S3 bucket name is hardcoded to
`hospital-management-frontend-bucket` in `main.tf` and never changes
with `project_name`, so a second apply can never create a second
bucket. The other values (`aws_region`, `environment`) already have
working defaults.

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

`plan` should show ~190 to add and 0 to destroy. Type `yes` at the
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
aws s3 sync frontend/ s3://hospital-management-frontend-bucket/
```

The bucket name is `<project>-management-frontend-bucket` from your
`project_name`. **Do NOT use `--delete` here** — Terraform already
wrote `js/config.js` into the bucket, and `--delete` would remove it,
leaving the site unable to reach the API. Do NOT edit `js/api.js`
to paste the API URL either — `config.js` is how the site finds it.

Then invalidate CloudFront so the new files show immediately
(otherwise the old cached pages keep serving for a long time):

```bash
aws cloudfront list-distributions --query "DistributionList.Items[].{Id:Id,Origin:Origins.Items[0].DomainName}" --output table
aws cloudfront create-invalidation --distribution-id <the-id-from-above> --paths "/*"
```

Wait for the invalidation to finish before testing
(`aws cloudfront get-invalidation --distribution-id <id> --id
<invalidation-id> --query "Invalidation.Status"` should print
`Completed`).

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
3. **Admin first sign-in — do this once from the CLI.** The admin
   account does not exist in the User Pool until the first sign-in,
   and the browser's sign-in does **not** create it (it only works
   for accounts that already exist). Run this once with your
   `cognito_client_id` from step 4:

   ```bash
   aws cognito-idp initiate-auth --client-id <cognito_client_id> --auth-flow USER_PASSWORD_AUTH --auth-parameters USERNAME=<ses_from_email>,PASSWORD=<auth_admin_password> --region us-east-1
   ```

   It returns tokens and creates the admin account (CONFIRMED, in
   the Admins group). After this one CLI sign-in, the browser sign-in
   works.
4. Sign in as admin in the browser with your **`ses_from_email`
   address** (not the username `admin`) and your
   `auth_admin_password` — the dashboard opens. The login page has a
   Patient / Admin choice, but the **account** decides where you
   land: admin accounts always open the dashboard, patient accounts
   always open the patient panel.
5. If you forget the admin password, use **"Forgot password?"** on
   the login page — Cognito emails a reset code and you set a new
   password there. Two things to know: the reset code only arrives
   if the account already exists **and** its email is verified, and
   the email must be typed with **no spaces** (a leading or trailing
   space fails with a "username failed to satisfy constraint" error).
   (Note: the migration Lambda still holds the old
   `auth_admin_password` for first-time sign-ins of old users, so
   after a reset, update `auth_admin_password` in your tfvars to the
   new password and run `terraform apply` once to keep them in sync.)
6. Book an appointment from the patient panel and check it appears
   in My Appointments. Confirm it (appointment-confirm page), then
   test the **video consultation**: the patient opens the Video
   Visit page (or the Join Video Call button) and the doctor joins
   the same appointment from doctors/appointments — both land in the
   same room. If the video area stays blank or stuck on
   "Connecting..." for 25 seconds, the page shows a "Join directly"
   link — open it in a new tab (or use Copy Call Link) to bypass the
   embed; also try a hard refresh (Ctrl+Shift+R) or Incognito.

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
  `/aws/lambda/hospital-cognito-migration-service` in CloudWatch.
- **AWS Console:** Lambda → a function (e.g. `hospital-patient-service`)
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

This deletes everything the apply created. If destroy fails with
`BucketNotEmpty`, the S3 bucket still holds old object versions
(versioning is on) — delete **all** versions and delete markers
first (the AWS Console S3 bucket → Empty, or a script that deletes
every version), then run `terraform destroy` again. A plain
`aws s3 rm --recursive` is not enough — it only adds delete markers.
