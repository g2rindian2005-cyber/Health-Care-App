"""
Lambda handler for the PHARMACY tables (DynamoDB `hospital-medicines`
and `hospital-prescriptions`).

Routes:
    GET    /pharmacy/medicines                    -> list the medicine catalog
    POST   /pharmacy/medicines                    -> add a medicine
    GET    /pharmacy/medicines/{id}               -> get one medicine
    PUT    /pharmacy/medicines/{id}               -> update a medicine (incl. stock)
    DELETE /pharmacy/medicines/{id}               -> delete a medicine
    GET    /pharmacy/prescriptions                -> list all prescriptions
    POST   /pharmacy/prescriptions                -> new prescription (stock-checked)
    GET    /pharmacy/prescriptions/{id}           -> get one prescription
    PUT    /pharmacy/prescriptions/{id}           -> update (dispensing cuts stock)
    DELETE /pharmacy/prescriptions/{id}           -> delete a prescription
    POST   /pharmacy/prescriptions/{id}/send-report -> email the prescription to the patient
    GET    /pharmacy/prescriptions/patient/{pid}  -> prescriptions for a patient
    GET    /pharmacy/low-stock                    -> medicines at/below reorder level

DynamoDB migration: the old code read MySQL on RDS via db_connection.
All reads/writes now go through dynamodb.py (boto3). Routes,
validations, messages and response shapes are unchanged.

The dispensing guard is preserved exactly: stock is decremented only
when a prescription moves into Dispensed, and only once — via a
conditional DynamoDB update (stock_quantity >= quantity), so a race
or a double-dispense can never drive stock negative.
"""
import json
from datetime import datetime
from botocore.exceptions import ClientError

from dynamodb import (
    get_item, scan_all, query_index, put_item, update_item, delete_item,
    update_item_conditional, fetch_by_ids, full_name, next_id, now,
    PATIENTS, DOCTORS, MEDICINES, PRESCRIPTIONS,
)

# Email helper (send_email.py + smtp_config.py + templates/) is
# packaged inside this Lambda's own directory, so a plain import
# works at runtime — same pattern as the doctor Lambda.
try:
    from send_email import send_prescription_email  # noqa: E402
except Exception:
    send_prescription_email = None


def _body(event):
    raw = event.get("body") or "{}"
    return raw if isinstance(raw, (dict, list)) else json.loads(raw)


def _pp(event, name):
    return (event.get("pathParameters") or {}).get(name)


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


def _enrich_rx(rows):
    """Attach medicine fields + patient_name / doctor_name (the old SQL
    did this with LEFT JOINs; DynamoDB has no joins, so it is done here)."""
    if not rows:
        return rows
    _meds = fetch_by_ids(MEDICINES, [r.get("medicine_id") for r in rows])
    _pnames = fetch_by_ids(PATIENTS, [r["patient_id"] for r in rows])
    _dnames = fetch_by_ids(DOCTORS, [r.get("doctor_id") for r in rows])
    for r in rows:
        m = _meds.get(r.get("medicine_id")) or {}
        r["medicine_name"] = m.get("medicine_name")
        r["medicine_unit"] = m.get("unit")
        r["unit_price"] = m.get("unit_price")
        r["total_amount"] = (float(m.get("unit_price") or 0)
                             * int(r.get("quantity") or 0))
        r["stock_quantity"] = m.get("stock_quantity")
        r["patient_name"] = full_name(_pnames.get(r.get("patient_id")))
        r["doctor_name"] = full_name(_dnames.get(r.get("doctor_id")))
    return rows


def _auto_send_prescription(rid):
    """Email a dispensed prescription to the patient automatically, once.

    Called when a prescription becomes Dispensed (the prescription is
    ready). Best-effort by design: it never raises and never fails the
    update that triggered it. Returns True only when SES accepted the
    email and the row was marked sent. Skips silently when there is no
    patient email, the email helper is missing, or the prescription
    was already sent (so a later edit of a Dispensed prescription
    never re-sends it). The admin can always re-send from the
    Prescriptions page (POST /pharmacy/prescriptions/{id}/send-report)."""
    try:
        rx = get_item(PRESCRIPTIONS, rid)
        if not rx or rx.get("report_sent_at"):
            return False
        if not send_prescription_email:
            return False
        patient = get_item(PATIENTS, int(rx.get("patient_id")))
        email = (patient.get("email") if patient else "") or ""
        email = email.strip()
        if not email:
            return False
        enriched = _enrich_rx([rx])[0]
        send_prescription_email(
            email,
            full_name(patient) or "",
            rid,
            enriched.get("medicine_name") or "",
            enriched.get("dosage") or "",
            enriched.get("frequency") or "",
            enriched.get("duration_days"),
            enriched.get("quantity") or 0,
            enriched.get("status") or "",
            enriched.get("prescribed_date") or "",
            enriched.get("doctor_name") or "",
            enriched.get("total_amount"),
        )
        update_item(PRESCRIPTIONS, rid, {"report_sent_at": now(), "report_sent_to": email})
        return True
    except Exception:
        return False


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
    # Shim: terraform routes /pharmacy through {proxy+}, so translate the
    # concrete path back to the route templates matched below.
    _seg = [s for s in (event.get("path") or "").split("/") if s]
    _ppx = dict(event.get("pathParameters") or {})
    if len(_seg) == 4 and _seg[:3] == ["pharmacy", "prescriptions", "patient"]:
        _ppx["patient_id"] = _seg[3]
        resource = "/pharmacy/prescriptions/patient/{patient_id}"
    elif len(_seg) == 4 and _seg[:2] == ["pharmacy", "prescriptions"] and _seg[3] == "send-report":
        _ppx["prescription_id"] = _seg[2]
        resource = "/pharmacy/prescriptions/{prescription_id}/send-report"
    elif _seg == ["pharmacy", "medicines"]:
        resource = "/pharmacy/medicines"
    elif len(_seg) == 3 and _seg[:2] == ["pharmacy", "medicines"]:
        _ppx["medicine_id"] = _seg[2]
        resource = "/pharmacy/medicines/{medicine_id}"
    elif _seg == ["pharmacy", "prescriptions"]:
        resource = "/pharmacy/prescriptions"
    elif len(_seg) == 3 and _seg[:2] == ["pharmacy", "prescriptions"]:
        _ppx["prescription_id"] = _seg[2]
        resource = "/pharmacy/prescriptions/{prescription_id}"
    elif _seg == ["pharmacy", "low-stock"]:
        resource = "/pharmacy/low-stock"
    event["pathParameters"] = _ppx

    if method == "OPTIONS":
        return _json(200, {"message": "OK"})

    # ================= MEDICINE CATALOG =================
    # ---- LOW STOCK ----
    if method == "GET" and resource.endswith("/pharmacy/low-stock"):
        rows = [m for m in scan_all(MEDICINES)
                if (m.get("stock_quantity") or 0) <= (m.get("reorder_level") or 0)]
        rows = sorted(rows, key=lambda r: r.get("stock_quantity") or 0)
        return _json(200, {"count": len(rows), "medicines": rows})

    # ---- LIST MEDICINES ----
    if method == "GET" and resource.endswith("/pharmacy/medicines"):
        rows = sorted(scan_all(MEDICINES),
                      key=lambda r: (r.get("category") or "", r.get("medicine_name") or ""))
        return _json(200, {"count": len(rows), "medicines": rows})

    # ---- GET ONE MEDICINE ----
    if method == "GET" and resource.endswith("/pharmacy/medicines/{medicine_id}"):
        mid = int(_pp(event, "medicine_id"))
        med = get_item(MEDICINES, mid)
        if not med:
            return _json(404, {"error": "Medicine not found"})
        return _json(200, {"medicine": med})

    # ---- CREATE MEDICINE ----
    if method == "POST" and resource.endswith("/pharmacy/medicines"):
        d = _body(event)
        if not d.get("medicine_name"):
            return _json(400, {"error": "medicine_name is required"})
        new_id = next_id(MEDICINES)
        put_item(MEDICINES, {
            "medicine_id": new_id,
            "medicine_name": d["medicine_name"],
            "generic_name": d.get("generic_name"),
            "category": d.get("category", "Other"),
            "manufacturer": d.get("manufacturer"),
            "unit": d.get("unit", "Tablet"),
            "unit_price": float(d.get("unit_price", 0)),
            "stock_quantity": int(d.get("stock_quantity", 0)),
            "reorder_level": int(d.get("reorder_level", 20)),
            "expiry_date": d.get("expiry_date") or None,
            "requires_prescription": int(d.get("requires_prescription", 1)),
            "created_at": now(),
            "updated_at": now(),
        })
        return _json(201, {"message": "Medicine created", "medicine_id": new_id})

    # ---- UPDATE MEDICINE ----
    if method == "PUT" and resource.endswith("/pharmacy/medicines/{medicine_id}"):
        mid = int(_pp(event, "medicine_id"))
        d = _body(event)
        fields = ["medicine_name", "generic_name", "category", "manufacturer", "unit",
                  "unit_price", "stock_quantity", "reorder_level", "expiry_date",
                  "requires_prescription"]
        # "" means "clear this field" (MySQL set it to NULL)
        changes = {f: (None if d[f] == "" else d[f]) for f in fields if f in d}
        if not changes:
            return _json(400, {"error": "No fields to update"})
        if "unit_price" in changes and changes["unit_price"] is not None:
            changes["unit_price"] = float(changes["unit_price"])
        for k in ("stock_quantity", "reorder_level", "requires_prescription"):
            if changes.get(k) is not None:
                changes[k] = int(changes[k])
        update_item(MEDICINES, mid, changes)
        return _json(200, {"message": "Medicine updated", "medicine_id": mid})

    # ---- DELETE MEDICINE ----
    if method == "DELETE" and resource.endswith("/pharmacy/medicines/{medicine_id}"):
        mid = int(_pp(event, "medicine_id"))
        delete_item(MEDICINES, mid)
        return _json(200, {"message": "Medicine deleted", "medicine_id": mid})

    # ================= PRESCRIPTIONS =================
    # ---- PRESCRIPTIONS FOR PATIENT ----
    if method == "GET" and resource.endswith("/pharmacy/prescriptions/patient/{patient_id}"):
        pid = int(_pp(event, "patient_id"))
        rows = _enrich_rx(_sort(
            query_index(PRESCRIPTIONS, "patient_id-index", "patient_id", pid),
            "prescribed_date"))
        return _json(200, {"count": len(rows), "prescriptions": rows})

    # ---- LIST PRESCRIPTIONS ----
    if method == "GET" and resource.rstrip("/").endswith("/pharmacy/prescriptions"):
        rows = _enrich_rx(_sort(scan_all(PRESCRIPTIONS), "prescribed_date"))
        return _json(200, {"count": len(rows), "prescriptions": rows})

    # ---- GET ONE PRESCRIPTION ----
    if method == "GET" and resource.endswith("/pharmacy/prescriptions/{prescription_id}"):
        rid = int(_pp(event, "prescription_id"))
        rx = get_item(PRESCRIPTIONS, rid)
        if not rx:
            return _json(404, {"error": "Prescription not found"})
        return _json(200, {"prescription": _enrich_rx([rx])[0]})

    # ---- CREATE PRESCRIPTION (stock-checked) ----
    if method == "POST" and resource.endswith("/pharmacy/prescriptions"):
        d = _body(event)
        if not d.get("patient_id") or not d.get("medicine_id"):
            return _json(400, {"error": "patient_id and medicine_id are required"})
        qty = int(d.get("quantity") or 1)
        if qty < 1:
            return _json(400, {"error": "quantity must be at least 1"})
        p = get_item(PATIENTS, int(d["patient_id"]))
        if not p:
            return _json(404, {"error": "Patient not found — cannot prescribe"})
        med = get_item(MEDICINES, int(d["medicine_id"]))
        if not med:
            return _json(404, {"error": "Medicine not found"})
        if int(med.get("stock_quantity") or 0) < qty:
            return _json(400, {"error": f"Insufficient stock — only {med.get('stock_quantity')} left"})
        if d.get("doctor_id"):
            doc = get_item(DOCTORS, int(d["doctor_id"]))
            if not doc:
                return _json(404, {"error": "Doctor not found"})
        new_id = next_id(PRESCRIPTIONS)
        put_item(PRESCRIPTIONS, {
            "prescription_id": new_id,
            "patient_id": int(d["patient_id"]),
            "doctor_id": int(d["doctor_id"]) if d.get("doctor_id") else None,
            "medicine_id": int(d["medicine_id"]),
            "quantity": qty,
            "dosage": d.get("dosage"),
            "frequency": d.get("frequency"),
            "duration_days": int(d["duration_days"]) if d.get("duration_days") else None,
            "status": d.get("status", "Pending"),
            "remarks": d.get("remarks"),
            "prescribed_date": now(),
            "created_at": now(),
            "updated_at": now(),
        })
        # Created already Dispensed (prescription ready at once) —
        # email it to the patient automatically (best-effort).
        emailed = False
        if d.get("status") == "Dispensed":
            emailed = _auto_send_prescription(new_id)
        return _json(201, {"message": "Prescription created", "prescription_id": new_id,
                            "report_emailed": emailed})

    # ---- UPDATE PRESCRIPTION (dispensing cuts stock once) ----
    if method == "PUT" and resource.endswith("/pharmacy/prescriptions/{prescription_id}"):
        rid = int(_pp(event, "prescription_id"))
        d = _body(event)
        current = get_item(PRESCRIPTIONS, rid)
        if not current:
            return _json(404, {"error": "Prescription not found"})
        # Transition into Dispensed: decrement stock atomically, once.
        if d.get("status") == "Dispensed" and current.get("status") != "Dispensed":
            ok = update_item_conditional(
                MEDICINES, int(current["medicine_id"]),
                "SET stock_quantity = stock_quantity - :q, #upd = :upd",
                {"#upd": "updated_at"},
                {":q": int(current["quantity"]), ":upd": now()},
                "attribute_exists(medicine_id) AND stock_quantity >= :q",
            )
            if not ok:
                return _json(400, {"error": "Insufficient stock to dispense"})
            if not d.get("dispensed_date"):
                d["dispensed_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        fields = ["quantity", "dosage", "frequency", "duration_days", "status",
                  "dispensed_date", "remarks"]
        changes = {f: (None if d[f] == "" else d[f]) for f in fields if f in d}
        if not changes:
            return _json(400, {"error": "No fields to update"})
        if "quantity" in changes and changes["quantity"] is not None:
            changes["quantity"] = int(changes["quantity"])
        if "duration_days" in changes and changes["duration_days"] is not None:
            changes["duration_days"] = int(changes["duration_days"])
        update_item(PRESCRIPTIONS, rid, changes)
        # Prescription ready: it just became Dispensed — email it to
        # the patient automatically (best-effort, never fails the
        # update). Editing an already-Dispensed prescription does not
        # re-send.
        emailed = False
        if changes.get("status") == "Dispensed" and current.get("status") != "Dispensed":
            emailed = _auto_send_prescription(rid)
        return _json(200, {"message": "Prescription updated", "prescription_id": rid,
                            "report_emailed": emailed})

    # ---- DELETE PRESCRIPTION ----
    if method == "DELETE" and resource.endswith("/pharmacy/prescriptions/{prescription_id}"):
        rid = int(_pp(event, "prescription_id"))
        delete_item(PRESCRIPTIONS, rid)
        return _json(200, {"message": "Prescription deleted", "prescription_id": rid})

    # ---- SEND PRESCRIPTION BY EMAIL ----
    # The patient asked for their prescription by email. The email
    # goes to the address on the patient record — never to a blank
    # address. The row is marked sent only after SES accepts the
    # email, so a failed send never shows as sent.
    if method == "POST" and resource.endswith("/pharmacy/prescriptions/{prescription_id}/send-report"):
        rid = int(_pp(event, "prescription_id"))
        rx = get_item(PRESCRIPTIONS, rid)
        if not rx:
            return _json(404, {"error": "Prescription not found"})
        patient = get_item(PATIENTS, int(rx.get("patient_id")))
        email = (patient.get("email") if patient else "") or ""
        email = email.strip()
        if not email:
            return _json(400, {"error": "The patient has no email address on file — add an email to the patient record first"})
        if not send_prescription_email:
            return _json(500, {"error": "Email service is not configured"})
        enriched = _enrich_rx([rx])[0]
        try:
            send_prescription_email(
                email,
                full_name(patient) or "",
                rid,
                enriched.get("medicine_name") or "",
                enriched.get("dosage") or "",
                enriched.get("frequency") or "",
                enriched.get("duration_days"),
                enriched.get("quantity") or 0,
                enriched.get("status") or "",
                enriched.get("prescribed_date") or "",
                enriched.get("doctor_name") or "",
                enriched.get("total_amount"),
            )
        except Exception as exc:
            return _json(502, {"error": f"Could not send the prescription email: {exc}"})
        sent_at = now()
        update_item(PRESCRIPTIONS, rid, {"report_sent_at": sent_at, "report_sent_to": email})
        return _json(200, {"message": "Prescription sent", "prescription_id": rid,
                            "email": email, "report_sent_at": sent_at})

    return _json(404, {"error": "Route not found", "resource": resource})
