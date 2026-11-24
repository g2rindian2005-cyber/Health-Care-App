# Lambda test events

Saved test events for the HealtheCare Lambda functions. Each file is a
ready-to-paste API Gateway proxy event — no JWT token needed, the handlers
do not check `Authorization` themselves.

| File | Function | What it tests |
|---|---|---|
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

> Important: paste the file content as-is. A hand-typed event without
> `httpMethod` and `resource`/`path` returns 404 — that means the event
> is wrong, not the Lambda.

## Expected results

- **After the DynamoDB deploy:** `200` with real data (seeded sample data).
- **Database down:** `503 {"error":"Database unavailable"}` — the
  database is down, not the event. The event is correct.

## Do NOT use

- `auth-login.json` — it belonged to the old auth Lambda, which was
  deleted in the Cognito migration (2026-11-18). Login is now Cognito
  password sign-in, there is no OTP step and no `/auth/login` route.
  This file has been deleted from the repo.
