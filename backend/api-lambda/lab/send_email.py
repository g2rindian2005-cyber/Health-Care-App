"""
Email helper for the lab Lambda: sends a lab report to the patient
via SES SMTP. Same pattern as backend/doctor-lambda/send_email.py
(loads an HTML template, sends it with smtp_config.send_email).
"""
import os
from smtp_config import send_email

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")


def _load_template(name):
    path = os.path.join(TEMPLATE_DIR, name)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def send_lab_report_email(to_email, patient_name, order_id, test_name,
                           order_date, status, result_value, normal_range,
                           unit, doctor_name):
    """Sent when a patient asks for their lab report by email."""
    html = _load_template("lab-report.html")
    html = (html.replace("{{patient_name}}", str(patient_name or ""))
               .replace("{{order_id}}", str(order_id))
               .replace("{{test_name}}", str(test_name or ""))
               .replace("{{order_date}}", str(order_date or ""))
               .replace("{{status}}", str(status or ""))
               .replace("{{result_value}}", str(result_value or "Pending"))
               .replace("{{normal_range}}", str(normal_range or "—"))
               .replace("{{unit}}", str(unit or "—"))
               .replace("{{doctor_name}}", str(doctor_name or "—")))
    return send_email(to_email, "Your Lab Report — Health Care Hospital", html)
