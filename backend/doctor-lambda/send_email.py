"""
High-level email helpers that load HTML templates and send them via SES SMTP.
Each function corresponds to a hospital event and is called by the Lambdas.
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


def send_bill_email(to_email, patient_id, bill_id, description, amount):
    """Sent when a new bill is created for a patient."""
    html = _load_template("bill.html")
    html = (html.replace("{{patient_id}}", str(patient_id))
               .replace("{{bill_id}}", str(bill_id))
               .replace("{{description}}", str(description))
               .replace("{{amount}}", f"{amount:.2f}"))
    return send_email(to_email, f"New Bill #{bill_id} — Health Care Hospital", html)


def send_payment_receipt_email(to_email, payment_id, bill_id, amount):
    """Sent when a payment is recorded."""
    html = _load_template("payment-receipt.html")
    html = (html.replace("{{payment_id}}", str(payment_id))
               .replace("{{bill_id}}", str(bill_id))
               .replace("{{amount}}", f"{amount:.2f}"))
    return send_email(to_email, f"Payment Receipt — Health Care Hospital", html)


def send_appointment_email(to_email, patient_id, assignment_id, doctor_name, appointment_date):
    """Sent when a doctor is assigned to a patient."""
    html = _load_template("appointment.html")
    html = (html.replace("{{patient_id}}", str(patient_id))
               .replace("{{assignment_id}}", str(assignment_id))
               .replace("{{doctor_name}}", str(doctor_name))
               .replace("{{appointment_date}}", str(appointment_date)))
    return send_email(to_email, "Appointment Confirmation — Health Care Hospital", html)


def send_doctor_appointment_email(to_email, doctor_name, patient_name, patient_id,
                                   assignment_id, appointment_date, status,
                                   room_number=None, consultation_fee=None):
    """Sent to the assigned doctor when an appointment is created
    (status "Assigned") or confirmed (status "Confirmed").

    The subject follows the status: a new assignment is
    "New Appointment Assigned", a confirmed one is
    "Appointment Confirmed". The caller is responsible for skipping
    the send when the doctor has no email on file, and for wrapping
    the call so an SES failure never breaks the API response.
    """
    confirmed = str(status).strip().lower() == "confirmed"
    subject = ("Appointment Confirmed — Health Care Hospital"
               if confirmed
               else "New Appointment Assigned — Health Care Hospital")
    heading = ("Appointment Confirmed"
               if confirmed
               else "New Appointment Assigned")
    # The doctor record's name sometimes already starts with "Dr."
    # (the add-doctor form suggests it); strip it so the greeting
    # never reads "Dear Dr. Dr. ...".
    name = str(doctor_name).strip()
    low = name.lower()
    if low.startswith("dr."):
        name = name[3:].strip()
    elif low.startswith("dr "):
        name = name[3:].strip()
    fee = f"₹{float(consultation_fee):,.0f}" if consultation_fee else "—"
    room = str(room_number).strip() if room_number else "Not assigned yet"
    html = _load_template("doctor-appointment.html")
    html = (html.replace("{{doctor_name}}", name)
               .replace("{{heading}}", heading)
               .replace("{{patient_name}}", str(patient_name))
               .replace("{{patient_id}}", str(patient_id))
               .replace("{{assignment_id}}", str(assignment_id))
               .replace("{{appointment_date}}", str(appointment_date))
               .replace("{{room_number}}", room)
               .replace("{{consultation_fee}}", fee)
               .replace("{{status}}", str(status)))
    return send_email(to_email, subject, html)
