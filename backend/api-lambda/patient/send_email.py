"""
Email helper for the patient Lambda: sends the patient's complete
medical record (patient history) to the patient's email via the
Amazon SES API (boto3) — NOT SMTP.

Why the SES API and not SMTP: SES SMTP needs a username + password
in the Lambda env vars. Those were never set, so SES refused every
send with "530 Authentication required". The SES API needs NO
password at all — the Lambda's IAM role already allows
ses:SendEmail / ses:SendRawEmail (terraform/main.tf, lambda_extras),
so the Lambda authenticates with its own role. Nothing to put in
tfvars, nothing to create in the SES console.

One requirement stays: the sender address (SMTP_FROM_EMAIL env var,
gokul9356782322@gmail.com) must be a verified SES identity, and
while the SES account is in sandbox mode the recipient must be
verified too. SES returns a clear error if either is not verified.

The patient history report is generated from the Patient History page
(all the patient's data in one place) and emailed from there — there
is no separate "report" feature. The template takes pre-built HTML
rows for each section, so the Lambda only fills in the lists.
"""
import os

import boto3

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")
SES_FROM_EMAIL = os.environ.get("SMTP_FROM_EMAIL", "noreply@hospital.com")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

_ses = None


def _ses_client():
    global _ses
    if _ses is None:
        _ses = boto3.client("ses", region_name=AWS_REGION)
    return _ses


def send_email(to_email, subject, html_body):
    """Send one HTML email via the SES API. Raises on failure
    (e.g. sender/recipient not verified in SES) so the caller can
    return a 502."""
    resp = _ses_client().send_email(
        Source=SES_FROM_EMAIL,
        Destination={"ToAddresses": [to_email]},
        Message={
            "Subject": {"Data": subject, "Charset": "UTF-8"},
            "Body": {"Html": {"Data": html_body, "Charset": "UTF-8"}},
        },
    )
    return {"status": "sent", "to": to_email,
            "message_id": resp.get("MessageId")}


def _load_template(name):
    path = os.path.join(TEMPLATE_DIR, name)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def send_registration_email(to_email, patient_name, patient_id):
    """Sent when a new patient is registered."""
    html = _load_template("registration.html")
    html = html.replace("{{patient_name}}", str(patient_name)) \
               .replace("{{patient_id}}", str(patient_id))
    return send_email(to_email, "Welcome to Health Care Hospital", html)


def send_patient_history_email(to_email, patient_name, patient_id,
                               generated_on, appointments_rows,
                               diseases_rows, lab_rows, rx_rows,
                               bills_rows):
    """Sent when the hospital emails the patient's complete medical
    record (patient history) to the patient. Each *_rows argument is
    pre-built HTML <tr> rows for that section (or an empty-state row
    when the section has no records)."""
    html = _load_template("patient-history.html")
    html = (html.replace("{{patient_name}}", str(patient_name or ""))
                .replace("{{patient_id}}", str(patient_id))
                .replace("{{generated_on}}", str(generated_on or ""))
                .replace("{{appointments_rows}}", appointments_rows or "")
                .replace("{{diseases_rows}}", diseases_rows or "")
                .replace("{{lab_rows}}", lab_rows or "")
                .replace("{{rx_rows}}", rx_rows or "")
                .replace("{{bills_rows}}", bills_rows or ""))
    return send_email(to_email, "Your Medical Record — Health Care Hospital", html)
