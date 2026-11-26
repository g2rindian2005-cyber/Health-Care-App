"""
Lambda handler for the PATIENT table (DynamoDB `hospital-patients`).

Routes (proxied via API Gateway):
    GET    /patients            -> list all patients
    GET    /patients/{id}       -> get one patient (+ synchronised summary)
    GET    /patients/by-email/{email} -> find a patient by email (patient panel)
    POST   /patients            -> add a patient   (also emails registration)
    PUT    /patients/{id}       -> update a patient
    DELETE /patients/{id}       -> delete a patient

Synchronisation: when a patient is created we store them in
hospital-patients. Their patient_id becomes the shared key used by
hospital-billing, hospital-diseases, and hospital-doctors so every
table stays in sync through the same identifier.

DynamoDB migration: the old code read MySQL on RDS via db_connection.
All reads/writes now go through dynamodb.py (boto3). Routes,
validations, messages and response shapes are unchanged.
"""
import json
from botocore.exceptions import ClientError

from dynamodb import (
    get_item, scan_all, query_index, put_item, update_item, delete_item,
    fetch_by_ids, full_name, next_id, now,
    PATIENTS, BILLS, PAYMENTS, DISEASES, ASSIGNMENTS, DOCTORS,
    LAB_TESTS, LAB_ORDERS, MEDICINES, PRESCRIPTIONS,
)

# Email helper (send_email.py + smtp_config.py + templates/) is
# packaged inside this Lambda's own directory, so a plain import
# works at runtime — same pattern as the doctor/lab/pharmacy
# Lambdas. (The old sys.path hack to the shared email/ folder is
# gone: that folder is never packaged into the Lambda zip, so the
# import silently failed at runtime and no email was ever sent.)
try:
    from .send_email import send_registration_email, send_patient_history_email  # noqa: E402
except Exception:
    send_registration_email = None
    send_patient_history_email = None


def _body(event):
    raw = event.get("body") or "{}"
    if isinstance(raw, (dict, list)):
        return raw
    return json.loads(raw)


def _path_param(event, name):
    pp = event.get("pathParameters") or {}
    return pp.get(name)


def _json(status, payload):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
        },
        "body": json.dumps(payload, default=str),
    }


def _sort(rows, field, reverse=True):
    return sorted(rows, key=lambda r: r.get(field) or "", reverse=reverse)


def lambda_handler(event, context):
    try:
        return _dispatch(event, context)
    except ClientError:
        # DynamoDB unavailable / throttled / missing table — never a blank 502
        return _json(503, {"error": "Database unavailable"})
    except Exception as exc:  # bug in handler code, not the database
        return _json(500, {"error": f"Internal error: {exc}"})


def _dispatch(event, context):
    method = event.get("httpMethod", "GET")
    resource = event.get("resource", event.get("path", ""))
    # Shim: terraform routes child paths via {proxy+}, so translate the
    # concrete path back to the route templates matched below.
    _seg = [s for s in (event.get("path") or "").split("/") if s]
    _ppx = dict(event.get("pathParameters") or {})
    if len(_seg) == 2 and _seg[0] == "patients":
        _ppx["patient_id"] = _seg[1]
        resource = "/patients/{patient_id}"
    event["pathParameters"] = _ppx

    # CORS pre-flight
    if method == "OPTIONS":
        return _json(200, {"message": "OK"})

    # ---- LOOKUP BY EMAIL (patient panel: find my patient record) ----
    # No separate API Gateway route is needed: /patients/{proxy+}
    # already delivers this path to this Lambda. Returns
    # {"patient": {...}} or {"patient": null} when this email has no
    # patient record yet (the panel then asks for the profile fields
    # and creates it with POST /patients).
    if method == "GET" and len(_seg) == 3 and _seg[0] == "patients" and _seg[1] == "by-email":
        from urllib.parse import unquote
        email = unquote(_seg[2]).strip().lower()
        match = next(
            (r for r in scan_all(PATIENTS)
             if str(r.get("email") or "").strip().lower() == email),
            None,
        )
        if not match:
            return _json(200, {"patient": None})
        cols = ["patient_id", "first_name", "last_name", "date_of_birth",
                "gender", "phone", "email", "blood_group", "registration_date",
                "address", "city", "pincode"]
        return _json(200, {"patient": {k: match[k] for k in cols if k in match}})

    # ---- SEND PATIENT HISTORY REPORT BY EMAIL ----
    # The hospital emails the patient's complete medical record
    # (patient history) to the patient. The report is generated from
    # the Patient History page — all the patient's data in one place —
    # and sent from there. The email goes to the address on the
    # patient record — never to a blank address. A failed send
    # returns 502 and nothing is marked sent.
    if method == "POST" and len(_seg) == 3 and _seg[0] == "patients" and _seg[2] == "send-history-report":
        import html as _html
        pid = int(_seg[1])
        patient = get_item(PATIENTS, pid)
        if not patient:
            return _json(404, {"error": "Patient not found"})
        email = (patient.get("email") or "").strip()
        if not email:
            return _json(400, {"error": "The patient has no email address on file — add an email to the patient record first"})
        if not send_patient_history_email:
            return _json(500, {"error": "Email service is not configured"})

        def _esc(v):
            return _html.escape(str(v if v is not None else ""))

        def _row(cells):
            tds = "".join(
                '<td style="padding:8px;border-bottom:1px solid #eee;">%s</td>' % c
                for c in cells)
            return "<tr>%s</tr>" % tds

        def _empty(msg):
            return ('<tr><td colspan="3" style="padding:8px;color:#78909c;">%s</td></tr>'
                    % _esc(msg))

        # Appointments (with doctor names)
        assignments = _sort(
            query_index(ASSIGNMENTS, "patient_id-index", "patient_id", pid),
            "appointment_date")
        _docs = fetch_by_ids(DOCTORS, [a.get("doctor_id") for a in assignments])
        appt_rows = "".join(
            _row([_esc(full_name(_docs.get(a.get("doctor_id")) or "") or "—"),
                  _esc(str(a.get("appointment_date") or "")[:16]),
                  _esc(a.get("status") or "")])
            for a in assignments) or _empty("No appointments")
        # Diseases
        diseases = _sort(
            query_index(DISEASES, "patient_id-index", "patient_id", pid),
            "diagnosis_date")
        dis_rows = "".join(
            _row([_esc(d.get("disease_name") or ""),
                  _esc(d.get("severity") or ""),
                  _esc(d.get("status") or "")])
            for d in diseases) or _empty("No disease records")
        # Lab orders (with test names)
        labs = _sort(
            query_index(LAB_ORDERS, "patient_id-index", "patient_id", pid),
            "order_date")
        _tests = fetch_by_ids(LAB_TESTS, [o.get("test_id") for o in labs])
        lab_rows = "".join(
            _row([_esc((_tests.get(o.get("test_id")) or {}).get("test_name") or ("Test #%s" % o.get("test_id"))),
                  _esc(o.get("result_value") or "Pending"),
                  _esc(o.get("status") or "")])
            for o in labs) or _empty("No lab orders")
        # Prescriptions (with medicine names)
        rxs = _sort(
            query_index(PRESCRIPTIONS, "patient_id-index", "patient_id", pid),
            "prescribed_date")
        _meds = fetch_by_ids(MEDICINES, [r.get("medicine_id") for r in rxs])
        rx_rows = "".join(
            _row([_esc((_meds.get(r.get("medicine_id")) or {}).get("medicine_name") or ("Medicine #%s" % r.get("medicine_id"))),
                  _esc(r.get("dosage") or "—"),
                  _esc(r.get("status") or "")])
            for r in rxs) or _empty("No prescriptions")
        # Bills
        bills = _sort(
            query_index(BILLS, "patient_id-index", "patient_id", pid), "bill_date")
        bill_rows = "".join(
            _row([_esc("#%s" % b.get("bill_id")),
                  _esc(b.get("net_amount") or 0),
                  _esc(b.get("status") or "")])
            for b in bills) or _empty("No billing records")

        try:
            send_patient_history_email(
                email,
                full_name(patient) or "",
                pid,
                now(),
                appt_rows, dis_rows, lab_rows, rx_rows, bill_rows,
            )
        except Exception as exc:
            return _json(502, {"error": f"Could not send the history report email: {exc}"})
        return _json(200, {"message": "Patient history report sent",
                            "patient_id": pid, "email": email,
                            "report_sent_at": now()})

    # ---- LIST ----
    if method == "GET" and resource.rstrip("/").endswith("/patients"):
        rows = _sort(scan_all(PATIENTS), "patient_id")
        cols = ["patient_id", "first_name", "last_name", "date_of_birth",
                "gender", "phone", "email", "blood_group", "registration_date"]
        rows = [{k: r[k] for k in cols if k in r} for r in rows]
        return _json(200, {"count": len(rows), "patients": rows})

    # ---- GET ONE ----
    if method == "GET" and resource.endswith("/patients/{patient_id}"):
        pid = int(_path_param(event, "patient_id"))
        patient = get_item(PATIENTS, pid)
        if not patient:
            return _json(404, {"error": "Patient not found"})
        # Synchronised summary from the other tables
        bills = _sort(
            query_index(BILLS, "patient_id-index", "patient_id", pid), "bill_date")
        bills = [{k: b[k] for k in
                  ["bill_id", "net_amount", "status", "bill_date"] if k in b}
                 for b in bills]
        payments = query_index(PAYMENTS, "patient_id-index", "patient_id", pid)
        total_due = (sum(float(b.get("net_amount") or 0) for b in bills)
                     - sum(float(p.get("amount_paid") or 0) for p in payments))
        diseases = _sort(
            query_index(DISEASES, "patient_id-index", "patient_id", pid),
            "diagnosis_date")
        diseases = [{k: d[k] for k in
                     ["disease_id", "disease_name", "severity", "status",
                      "diagnosis_date"] if k in d} for d in diseases]
        assignments = _sort(
            query_index(ASSIGNMENTS, "patient_id-index", "patient_id", pid),
            "appointment_date")
        _docs = fetch_by_ids(DOCTORS, [a.get("doctor_id") for a in assignments])
        enriched = []
        for a in assignments:
            doc = _docs.get(a.get("doctor_id")) or {}
            enriched.append({
                "assignment_id": a.get("assignment_id"),
                "doctor_id": a.get("doctor_id"),
                "doctor_name": full_name(doc),
                "specialization": doc.get("specialization"),
                "status": a.get("status"),
                "appointment_date": a.get("appointment_date"),
            })
        return _json(200, {
            "patient": patient,
            "synchronised": {
                "total_due": total_due,
                "bills": bills,
                "diseases": diseases,
                "assignments": enriched,
            },
        })

    # ---- CREATE ----
    if method == "POST" and resource.endswith("/patients"):
        d = _body(event)
        required = ["first_name", "last_name", "date_of_birth", "gender", "phone"]
        for r in required:
            if not d.get(r):
                return _json(400, {"error": f"Missing field: {r}"})
        new_id = next_id(PATIENTS)
        put_item(PATIENTS, {
            "patient_id": new_id,
            "first_name": d["first_name"],
            "last_name": d["last_name"],
            "date_of_birth": d["date_of_birth"],
            "gender": d["gender"],
            "phone": d["phone"],
            "email": d.get("email"),
            "address": d.get("address"),
            "blood_group": d.get("blood_group"),
            "emergency_contact": d.get("emergency_contact"),
            "insurance_number": d.get("insurance_number"),
            "registration_date": now(),
            "updated_at": now(),
        })
        # Best-effort registration email
        if send_registration_email and d.get("email"):
            try:
                send_registration_email(d["email"], f"{d['first_name']} {d['last_name']}", new_id)
            except Exception:
                pass
        return _json(201, {"message": "Patient created", "patient_id": new_id})

    # ---- UPDATE ----
    if method == "PUT" and resource.endswith("/patients/{patient_id}"):
        pid = int(_path_param(event, "patient_id"))
        d = _body(event)
        fields = ["first_name", "last_name", "date_of_birth", "gender", "phone",
                  "email", "address", "blood_group", "emergency_contact", "insurance_number"]
        changes = {f: d[f] for f in fields if f in d}
        if not changes:
            return _json(400, {"error": "No fields to update"})
        update_item(PATIENTS, pid, changes)
        return _json(200, {"message": "Patient updated", "patient_id": pid})

    # ---- DELETE ----
    if method == "DELETE" and resource.endswith("/patients/{patient_id}"):
        pid = int(_path_param(event, "patient_id"))
        delete_item(PATIENTS, pid)
        return _json(200, {"message": "Patient deleted", "patient_id": pid})

    return _json(404, {"error": "Route not found", "resource": resource})
