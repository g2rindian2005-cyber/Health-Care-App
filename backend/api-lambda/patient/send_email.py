"""
Email helper for the patient Lambda: sends the patient's complete
medical record (patient history) and the registration welcome email
via Gmail SMTP — NOT Amazon SES.

Why Gmail SMTP and not SES: the SES account is stuck in sandbox mode
and SES keeps refusing sends with AccessDenied even when sender and
recipient both show Verified (three times now, across two accounts:
533267206558 and 074055094667). Production access is the permanent
SES fix, but it needs AWS access the user does not have right now.
Gmail SMTP needs no SES at all: the Lambda logs in to smtp.gmail.com
with a Gmail App Password and sends from the hospital Gmail address.

Env vars (Lambda env, from Terraform common_env or the Lambda
console): SMTP_HOST (smtp.gmail.com), SMTP_PORT (587),
SMTP_USERNAME (the Gmail address), SMTP_PASSWORD (the 16-digit Gmail
App Password — NOT the Gmail login password), SMTP_FROM_EMAIL (the
Gmail address). smtp_config.py reads all of these and logs in only
when a username + password are set. Without them the send raises,
and the handler returns a 502.

The patient history report is generated from the Patient History page
(all the patient's data in one place) and emailed from there — there
is no separate "report" feature. The template takes pre-built HTML
rows for each section, so the Lambda only fills in the lists.
"""
import os

from smtp_config import send_email

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")


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
