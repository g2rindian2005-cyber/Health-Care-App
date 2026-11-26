"""
Lambda handler for the LABORATORY tables (DynamoDB `hospital-lab-tests`
and `hospital-lab-orders`).

Routes:
    GET    /lab/tests                    -> list the test catalog
    POST   /lab/tests                    -> add a test to the catalog
    GET    /lab/tests/{id}               -> get one catalog test
    PUT    /lab/tests/{id}               -> update a catalog test
    DELETE /lab/tests/{id}               -> delete a catalog test
    GET    /lab/orders                   -> list all lab orders (with patient + test)
    POST   /lab/orders                   -> order a test (validates patient + test)
    GET    /lab/orders/{id}              -> get one order
    PUT    /lab/orders/{id}              -> update an order (status / result)
    DELETE /lab/orders/{id}              -> delete an order
    POST   /lab/orders/{id}/send-report  -> email the lab report to the patient
    GET    /lab/orders/patient/{pid}     -> lab history for a patient
    GET    /lab/pending                  -> orders not yet completed

DynamoDB migration: the old code read MySQL on RDS via db_connection.
All reads/writes now go through dynamodb.py (boto3). Routes,
validations, messages and response shapes are unchanged.
"""
import json
from botocore.exceptions import ClientError

from dynamodb import (
    get_item, scan_all, query_index, put_item, update_item, delete_item,
    fetch_by_ids, full_name, next_id, now,
    PATIENTS, DOCTORS, LAB_TESTS, LAB_ORDERS,
)

# Email helper (send_email.py + smtp_config.py + templates/) is
# packaged inside this Lambda's own directory, so a plain import
# works at runtime — same pattern as the doctor Lambda.
try:
    from .send_email import send_lab_report_email  # noqa: E402
except Exception:
    send_lab_report_email = None


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


def _enrich_orders(rows):
    """Attach test fields + patient_name / doctor_name (the old SQL did
    this with LEFT JOINs; DynamoDB has no joins, so it is done in code)."""
    if not rows:
        return rows
    _tests = fetch_by_ids(LAB_TESTS, [r.get("test_id") for r in rows])
    _pnames = fetch_by_ids(PATIENTS, [r["patient_id"] for r in rows])
    _dnames = fetch_by_ids(DOCTORS, [r.get("ordered_by") for r in rows])
    for r in rows:
        t = _tests.get(r.get("test_id")) or {}
        r["test_name"] = t.get("test_name")
        r["test_category"] = t.get("category")
        r["test_price"] = t.get("price")
        r["test_unit"] = t.get("unit")
        r["normal_range"] = t.get("normal_range")
        r["patient_name"] = full_name(_pnames.get(r.get("patient_id")))
        r["doctor_name"] = full_name(_dnames.get(r.get("ordered_by")))
    return rows


def _auto_send_lab_report(oid):
    """Email a completed lab report to the patient automatically, once.

    Called when an order becomes Completed (the report is generated).
    Best-effort by design: it never raises and never fails the update
    that triggered it. Returns True only when SES accepted the email
    and the row was marked sent. Skips silently when there is no
    patient email, the email helper is missing, or the report was
    already sent (so a later edit of a Completed order never
    re-sends it). The admin can always re-send from the Lab Orders
    page (POST /lab/orders/{id}/send-report)."""
    try:
        order = get_item(LAB_ORDERS, oid)
        if not order or order.get("report_sent_at"):
            return False
        if not send_lab_report_email:
            return False
        patient = get_item(PATIENTS, int(order.get("patient_id")))
        email = (patient.get("email") if patient else "") or ""
        email = email.strip()
        if not email:
            return False
        enriched = _enrich_orders([order])[0]
        send_lab_report_email(
            email,
            full_name(patient) or "",
            oid,
            enriched.get("test_name") or "",
            enriched.get("order_date") or "",
            enriched.get("status") or "",
            enriched.get("result_value") or "",
            enriched.get("normal_range") or "",
            enriched.get("test_unit") or "",
            enriched.get("doctor_name") or "",
        )
        update_item(LAB_ORDERS, oid, {"report_sent_at": now(), "report_sent_to": email})
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
    # Shim: terraform routes /lab through {proxy+}, so translate the
    # concrete path back to the route templates matched below.
    _seg = [s for s in (event.get("path") or "").split("/") if s]
    _ppx = dict(event.get("pathParameters") or {})
    if len(_seg) == 4 and _seg[:3] == ["lab", "orders", "patient"]:
        _ppx["patient_id"] = _seg[3]
        resource = "/lab/orders/patient/{patient_id}"
    elif len(_seg) == 4 and _seg[:2] == ["lab", "orders"] and _seg[3] == "send-report":
        _ppx["order_id"] = _seg[2]
        resource = "/lab/orders/{order_id}/send-report"
    elif _seg == ["lab", "tests"]:
        resource = "/lab/tests"
    elif len(_seg) == 3 and _seg[:2] == ["lab", "tests"]:
        _ppx["test_id"] = _seg[2]
        resource = "/lab/tests/{test_id}"
    elif _seg == ["lab", "orders"]:
        resource = "/lab/orders"
    elif len(_seg) == 3 and _seg[:2] == ["lab", "orders"]:
        _ppx["order_id"] = _seg[2]
        resource = "/lab/orders/{order_id}"
    elif _seg == ["lab", "pending"]:
        resource = "/lab/pending"
    event["pathParameters"] = _ppx

    if method == "OPTIONS":
        return _json(200, {"message": "OK"})

    # ================= TEST CATALOG =================
    # ---- LIST TESTS ----
    if method == "GET" and resource.endswith("/lab/tests"):
        rows = sorted(scan_all(LAB_TESTS),
                      key=lambda r: (r.get("category") or "", r.get("test_name") or ""))
        return _json(200, {"count": len(rows), "tests": rows})

    # ---- GET ONE TEST ----
    if method == "GET" and resource.endswith("/lab/tests/{test_id}"):
        tid = int(_pp(event, "test_id"))
        test = get_item(LAB_TESTS, tid)
        if not test:
            return _json(404, {"error": "Lab test not found"})
        return _json(200, {"test": test})

    # ---- CREATE TEST ----
    if method == "POST" and resource.endswith("/lab/tests"):
        d = _body(event)
        if not d.get("test_name"):
            return _json(400, {"error": "test_name is required"})
        new_id = next_id(LAB_TESTS)
        put_item(LAB_TESTS, {
            "test_id": new_id,
            "test_name": d["test_name"],
            "category": d.get("category", "Biochemistry"),
            "sample_type": d.get("sample_type"),
            "unit": d.get("unit"),
            "normal_range": d.get("normal_range"),
            "price": float(d.get("price", 0)),
            "turnaround_hours": int(d.get("turnaround_hours", 24)),
            "is_active": int(d.get("is_active", 1)),
            "created_at": now(),
            "updated_at": now(),
        })
        return _json(201, {"message": "Lab test created", "test_id": new_id})

    # ---- UPDATE TEST ----
    if method == "PUT" and resource.endswith("/lab/tests/{test_id}"):
        tid = int(_pp(event, "test_id"))
        d = _body(event)
        fields = ["test_name", "category", "sample_type", "unit", "normal_range",
                  "price", "turnaround_hours", "is_active"]
        changes = {f: d[f] for f in fields if f in d}
        if not changes:
            return _json(400, {"error": "No fields to update"})
        if "price" in changes:
            changes["price"] = float(changes["price"])
        if "turnaround_hours" in changes:
            changes["turnaround_hours"] = int(changes["turnaround_hours"])
        if "is_active" in changes:
            changes["is_active"] = int(changes["is_active"])
        update_item(LAB_TESTS, tid, changes)
        return _json(200, {"message": "Lab test updated", "test_id": tid})

    # ---- DELETE TEST ----
    if method == "DELETE" and resource.endswith("/lab/tests/{test_id}"):
        tid = int(_pp(event, "test_id"))
        delete_item(LAB_TESTS, tid)
        return _json(200, {"message": "Lab test deleted", "test_id": tid})

    # ================= LAB ORDERS =================
    # ---- PENDING ORDERS ----
    if method == "GET" and resource.endswith("/lab/pending"):
        rows = [o for o in scan_all(LAB_ORDERS)
                if o.get("status") in ("Ordered", "Sample Collected", "Processing")]
        rows = _enrich_orders(_sort(rows, "order_date", reverse=False))
        return _json(200, {"count": len(rows), "orders": rows})

    # ---- ORDERS FOR PATIENT ----
    if method == "GET" and resource.endswith("/lab/orders/patient/{patient_id}"):
        pid = int(_pp(event, "patient_id"))
        rows = _enrich_orders(_sort(
            query_index(LAB_ORDERS, "patient_id-index", "patient_id", pid),
            "order_date"))
        return _json(200, {"count": len(rows), "orders": rows})

    # ---- LIST ORDERS ----
    if method == "GET" and resource.rstrip("/").endswith("/lab/orders"):
        rows = _enrich_orders(_sort(scan_all(LAB_ORDERS), "order_date"))
        return _json(200, {"count": len(rows), "orders": rows})

    # ---- GET ONE ORDER ----
    if method == "GET" and resource.endswith("/lab/orders/{order_id}"):
        oid = int(_pp(event, "order_id"))
        order = get_item(LAB_ORDERS, oid)
        if not order:
            return _json(404, {"error": "Lab order not found"})
        return _json(200, {"order": _enrich_orders([order])[0]})

    # ---- CREATE ORDER ----
    if method == "POST" and resource.endswith("/lab/orders"):
        d = _body(event)
        if not d.get("patient_id") or not d.get("test_id"):
            return _json(400, {"error": "patient_id and test_id are required"})
        # Synchronisation: validate patient + test exist
        p = get_item(PATIENTS, int(d["patient_id"]))
        if not p:
            return _json(404, {"error": "Patient not found — cannot order a lab test"})
        t = get_item(LAB_TESTS, int(d["test_id"]))
        if not t:
            return _json(404, {"error": "Lab test not found"})
        if d.get("ordered_by"):
            doc = get_item(DOCTORS, int(d["ordered_by"]))
            if not doc:
                return _json(404, {"error": "Doctor not found"})
        new_id = next_id(LAB_ORDERS)
        put_item(LAB_ORDERS, {
            "order_id": new_id,
            "patient_id": int(d["patient_id"]),
            "test_id": int(d["test_id"]),
            "ordered_by": int(d["ordered_by"]) if d.get("ordered_by") else None,
            "priority": d.get("priority", "Routine"),
            "status": d.get("status", "Ordered"),
            "remarks": d.get("remarks"),
            "order_date": now(),
            "created_at": now(),
            "updated_at": now(),
        })
        # Created already Completed (report generated at once) — email
        # it to the patient automatically (best-effort).
        emailed = False
        if d.get("status") == "Completed":
            emailed = _auto_send_lab_report(new_id)
        return _json(201, {"message": "Lab test ordered", "order_id": new_id,
                            "report_emailed": emailed})

    # ---- UPDATE ORDER (status / result) ----
    if method == "PUT" and resource.endswith("/lab/orders/{order_id}"):
        oid = int(_pp(event, "order_id"))
        d = _body(event)
        fields = ["status", "result_value", "remarks", "report_date", "priority"]
        changes = {f: d[f] for f in fields if f in d}
        if not changes:
            return _json(400, {"error": "No fields to update"})
        current = get_item(LAB_ORDERS, oid)
        if not current:
            return _json(404, {"error": "Lab order not found"})
        update_item(LAB_ORDERS, oid, changes)
        # Report generated: the order just became Completed — email it
        # to the patient automatically (best-effort, never fails the
        # update). Editing an already-Completed order does not re-send.
        emailed = False
        if changes.get("status") == "Completed" and current.get("status") != "Completed":
            emailed = _auto_send_lab_report(oid)
        return _json(200, {"message": "Lab order updated", "order_id": oid,
                            "report_emailed": emailed})

    # ---- DELETE ORDER ----
    if method == "DELETE" and resource.endswith("/lab/orders/{order_id}"):
        oid = int(_pp(event, "order_id"))
        delete_item(LAB_ORDERS, oid)
        return _json(200, {"message": "Lab order deleted", "order_id": oid})

    # ---- SEND LAB REPORT BY EMAIL ----
    # The patient asked for their lab report by email. The email goes
    # to the address on the patient record — never to a blank address.
    # The row is marked sent only after SES accepts the email, so a
    # failed send never shows as sent.
    if method == "POST" and resource.endswith("/lab/orders/{order_id}/send-report"):
        oid = int(_pp(event, "order_id"))
        order = get_item(LAB_ORDERS, oid)
        if not order:
            return _json(404, {"error": "Lab order not found"})
        patient = get_item(PATIENTS, int(order.get("patient_id")))
        email = (patient.get("email") if patient else "") or ""
        email = email.strip()
        if not email:
            return _json(400, {"error": "The patient has no email address on file — add an email to the patient record first"})
        if not send_lab_report_email:
            return _json(500, {"error": "Email service is not configured"})
        enriched = _enrich_orders([order])[0]
        try:
            send_lab_report_email(
                email,
                full_name(patient) or "",
                oid,
                enriched.get("test_name") or "",
                enriched.get("order_date") or "",
                enriched.get("status") or "",
                enriched.get("result_value") or "",
                enriched.get("normal_range") or "",
                enriched.get("test_unit") or "",
                enriched.get("doctor_name") or "",
            )
        except Exception as exc:
            return _json(502, {"error": f"Could not send the report email: {exc}"})
        sent_at = now()
        update_item(LAB_ORDERS, oid, {"report_sent_at": sent_at, "report_sent_to": email})
        return _json(200, {"message": "Lab report sent", "order_id": oid,
                            "email": email, "report_sent_at": sent_at})

    return _json(404, {"error": "Route not found", "resource": resource})
