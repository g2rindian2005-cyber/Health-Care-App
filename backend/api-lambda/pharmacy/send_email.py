"""
Email helper for the pharmacy Lambda: sends a prescription to the
patient via SES SMTP. Same pattern as
backend/doctor-lambda/send_email.py (loads an HTML template, sends
it with smtp_config.send_email).
"""
import os
from smtp_config import send_email

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")


def _load_template(name):
    path = os.path.join(TEMPLATE_DIR, name)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def send_prescription_email(to_email, patient_name, prescription_id,
                             medicine_name, dosage, frequency,
                             duration_days, quantity, status,
                             prescribed_date, doctor_name, total_amount):
    """Sent when a patient asks for their prescription by email."""
    html = _load_template("prescription.html")
    html = (html.replace("{{patient_name}}", str(patient_name or ""))
               .replace("{{prescription_id}}", str(prescription_id))
               .replace("{{medicine_name}}", str(medicine_name or ""))
               .replace("{{dosage}}", str(dosage or "—"))
               .replace("{{frequency}}", str(frequency or "—"))
               .replace("{{duration_days}}", str(duration_days) if duration_days else "—")
               .replace("{{quantity}}", str(quantity))
               .replace("{{status}}", str(status or ""))
               .replace("{{prescribed_date}}", str(prescribed_date or ""))
               .replace("{{doctor_name}}", str(doctor_name or "—"))
               .replace("{{total_amount}}", str(total_amount or "—")))
    return send_email(to_email, "Your Prescription — Health Care Hospital", html)
