# Lambda test events

Saved test events for the HealtheCare Lambda functions. Each file is a
ready-to-paste API Gateway proxy event — no JWT token needed, the handlers
do not check `Authorization` themselves.

| File | Function | What it tests |
|---|---|---|
| `auth-login.json` | auth | POST /auth/login as admin |
| `patients-list.json` | patient | GET /patients (list) |
| `billing-dues.json` | billing | GET /dues (pending dues) |
| `pharmacy-prescriptions.json` | pharmacy | GET /pharmacy/prescriptions |
| `doctor-assignments.json` | doctor | GET /assignments |
| `lab-orders.json` | lab | GET /lab/orders |
| `diseases-list.json` | disease | GET /diseases |

## How to use (AWS Lambda console)

1. Open the function (e.g. `hospital-patient-service`).
2. **Test** tab → create a new test event → paste the matching file's
   contents → **Save** → **Test**.

## Expected results

- **Before the DynamoDB deploy:** `503 {"error":"Database unavailable"}` —
  the database is down, not the event. The event is correct.
- **After the DynamoDB deploy:** `200` with real data (seeded sample data).
- **Auth login:** returns an OTP challenge. Until the SES sender is
  verified, the code comes back as `dev_otp` in the response; after
  verification it arrives by email only.
