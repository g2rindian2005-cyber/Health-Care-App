"""
Lambda handler for the BILLING tables (DynamoDB `hospital-bills` and
`hospital-payments`).

Routes:
    GET    /bills                       -> list all bills (with patient name)
    GET    /bills/{id}                   -> get one bill + its payments
    POST   /bills                        -> create a bill (validates patient exists)
    PUT    /bills/{id}                   -> update a bill
    DELETE /bills/{id}                   -> delete a bill
    GET    /bills/patient/{pid}          -> all bills for a patient
    GET    /payments                     -> all payments
    GET    /payments/patient/{pid}       -> payment history for a patient
    POST   /payments                     -> record a payment (updates bill status)
    GET    /dues                          -> all pending dues (synchronised)

DynamoDB migration: the old code read MySQL on RDS via db_connection.
All reads/writes now go through dynamodb.py (boto3). Routes,
validations, messages and response shapes are unchanged, except money
now arrives as a JSON number (800) instead of a string ("800.00").

MySQL behaviours re-implemented in code:
- `net_amount` was a GENERATED column (amount - discount): computed
  here on create, and recomputed on update when amount/discount change.
- Trigger `trg_payment_after_insert` auto-updated the bill status:
  after a payment is recorded, total paid is summed and the bill is
  set to Paid (>= net) or Partial (> 0).
"""
import json
from botocore.exceptions import ClientError

from dynamodb import (
    get_item, scan_all, query_index, put_item, update_item, delete_item,
    fetch_by_ids, full_name, next_id, now,
    PATIENTS, BILLS, PAYMENTS,
)

try:
    from .send_email import send_bill_email, send_payment_receipt_email  # noqa: E402
except Exception:
    send_bill_email = send_payment_receipt_email = None


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


def _paid_for_bill(bill_id):
    pays = query_index(PAYMENTS, "bill_id-index", "bill_id", bill_id)
    return sum(float(p.get("amount_paid") or 0) for p in pays)


def _refresh_bill_status(bill):
    """MySQL trigger trg_payment_after_insert, in code."""
    total_paid = _paid_for_bill(bill["bill_id"])
    net = float(bill.get("net_amount") or 0)
    if total_paid >= net:
        new_status = "Paid"
    elif total_paid > 0:
        new_status = "Partial"
    else:
        return
    if bill.get("status") != new_status:
        update_item(BILLS, bill["bill_id"], {"status": new_status})


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
    if len(_seg) == 3 and _seg[0] == "bills" and _seg[1] == "patient":
        _ppx["patient_id"] = _seg[2]
        resource = "/bills/patient/{patient_id}"
    elif len(_seg) == 2 and _seg[0] == "bills":
        _ppx["bill_id"] = _seg[1]
        resource = "/bills/{bill_id}"
    elif len(_seg) == 3 and _seg[0] == "payments" and _seg[1] == "patient":
        _ppx["patient_id"] = _seg[2]
        resource = "/payments/patient/{patient_id}"
    event["pathParameters"] = _ppx

    if method == "OPTIONS":
        return _json(200, {"message": "OK"})

    # ---- DUES (must come before generic /bills/{id}) ----
    if method == "GET" and resource.endswith("/dues"):
        rows = [b for b in scan_all(BILLS)
                if b.get("status") in ("Pending", "Partial")]
        rows = _sort(rows, "bill_date")
        _names = fetch_by_ids(PATIENTS, [r["patient_id"] for r in rows])
        dues = []
        for b in rows:
            dues.append({
                "bill_id": b.get("bill_id"),
                "patient_id": b.get("patient_id"),
                "description": b.get("description"),
                "net_amount": b.get("net_amount"),
                "due_amount": float(b.get("net_amount") or 0) - _paid_for_bill(b["bill_id"]),
                "status": b.get("status"),
                "bill_date": b.get("bill_date"),
                "patient_name": full_name(_names.get(b.get("patient_id"))),
            })
        return _json(200, {"count": len(dues), "dues": dues})

    # ---- LIST BILLS ----
    if method == "GET" and resource.rstrip("/").endswith("/bills"):
        rows = _sort(scan_all(BILLS), "bill_date")
        _names = fetch_by_ids(PATIENTS, [r["patient_id"] for r in rows])
        bills = []
        for b in rows:
            bills.append({
                "bill_id": b.get("bill_id"),
                "patient_id": b.get("patient_id"),
                "description": b.get("description"),
                "category": b.get("category"),
                "amount": b.get("amount"),
                "discount": b.get("discount"),
                "net_amount": b.get("net_amount"),
                "status": b.get("status"),
                "bill_date": b.get("bill_date"),
                "patient_name": full_name(_names.get(b.get("patient_id"))),
            })
        return _json(200, {"count": len(bills), "bills": bills})

    # ---- BILLS FOR PATIENT ----
    if method == "GET" and resource.endswith("/bills/patient/{patient_id}"):
        pid = int(_pp(event, "patient_id"))
        rows = _sort(query_index(BILLS, "patient_id-index", "patient_id", pid),
                     "bill_date")
        return _json(200, {"count": len(rows), "bills": rows})

    # ---- GET ONE BILL ----
    if method == "GET" and resource.endswith("/bills/{bill_id}"):
        bid = int(_pp(event, "bill_id"))
        bill = get_item(BILLS, bid)
        if not bill:
            return _json(404, {"error": "Bill not found"})
        pays = _sort(query_index(PAYMENTS, "bill_id-index", "bill_id", bid),
                     "payment_date")
        return _json(200, {"bill": bill, "payments": pays})

    # ---- CREATE BILL ----
    if method == "POST" and resource.endswith("/bills"):
        d = _body(event)
        if not d.get("patient_id") or not d.get("description") or d.get("amount") is None:
            return _json(400, {"error": "patient_id, description and amount are required"})
        # Synchronisation: validate patient exists in hospital-patients
        p = get_item(PATIENTS, int(d["patient_id"]))
        if not p:
            return _json(404, {"error": "Patient not found — cannot create bill"})
        amount = float(d["amount"])
        discount = float(d.get("discount", 0))
        bid = next_id(BILLS)
        put_item(BILLS, {
            "bill_id": bid,
            "patient_id": int(d["patient_id"]),
            "description": d["description"],
            "category": d.get("category", "Consultation"),
            "amount": amount,
            "discount": discount,
            "net_amount": amount - discount,
            "status": d.get("status", "Pending"),
            "bill_date": now(),
            "created_at": now(),
            "updated_at": now(),
        })
        if send_bill_email and p.get("email"):
            try:
                send_bill_email(p["email"], d["patient_id"], bid,
                                d["description"], amount - discount)
            except Exception:
                pass
        return _json(201, {"message": "Bill created", "bill_id": bid})

    # ---- UPDATE BILL ----
    if method == "PUT" and resource.endswith("/bills/{bill_id}"):
        bid = int(_pp(event, "bill_id"))
        d = _body(event)
        fields = ["patient_id", "description", "category", "amount", "discount", "status"]
        changes = {f: d[f] for f in fields if f in d}
        if not changes:
            return _json(400, {"error": "No fields to update"})
        if "amount" in changes:
            changes["amount"] = float(changes["amount"])
        if "discount" in changes:
            changes["discount"] = float(changes["discount"])
        if "patient_id" in changes:
            changes["patient_id"] = int(changes["patient_id"])
        if "amount" in changes or "discount" in changes:
            # net_amount was a GENERATED column — recompute it
            bill = get_item(BILLS, bid) or {}
            amount = changes.get("amount", bill.get("amount", 0))
            discount = changes.get("discount", bill.get("discount", 0))
            changes["net_amount"] = float(amount) - float(discount)
        update_item(BILLS, bid, changes)
        return _json(200, {"message": "Bill updated", "bill_id": bid})

    # ---- DELETE BILL ----
    if method == "DELETE" and resource.endswith("/bills/{bill_id}"):
        bid = int(_pp(event, "bill_id"))
        delete_item(BILLS, bid)
        return _json(200, {"message": "Bill deleted", "bill_id": bid})

    # ---- LIST PAYMENTS ----
    if method == "GET" and resource.rstrip("/").endswith("/payments"):
        rows = _sort(scan_all(PAYMENTS), "payment_date")
        _names = fetch_by_ids(PATIENTS, [r["patient_id"] for r in rows])
        payments = []
        for p in rows:
            payments.append({
                "payment_id": p.get("payment_id"),
                "bill_id": p.get("bill_id"),
                "patient_id": p.get("patient_id"),
                "amount_paid": p.get("amount_paid"),
                "payment_method": p.get("payment_method"),
                "transaction_id": p.get("transaction_id"),
                "payment_date": p.get("payment_date"),
                "patient_name": full_name(_names.get(p.get("patient_id"))),
            })
        return _json(200, {"count": len(payments), "payments": payments})

    # ---- PAYMENTS FOR PATIENT ----
    if method == "GET" and resource.endswith("/payments/patient/{patient_id}"):
        pid = int(_pp(event, "patient_id"))
        rows = _sort(query_index(PAYMENTS, "patient_id-index", "patient_id", pid),
                     "payment_date")
        _bills = fetch_by_ids(BILLS, [r.get("bill_id") for r in rows])
        for p in rows:
            bill = _bills.get(p.get("bill_id")) or {}
            p["bill_description"] = bill.get("description")
            p["net_amount"] = bill.get("net_amount")
        return _json(200, {"count": len(rows), "payments": rows})

    # ---- RECORD PAYMENT ----
    if method == "POST" and resource.endswith("/payments"):
        d = _body(event)
        if not d.get("bill_id") or not d.get("patient_id") or d.get("amount_paid") is None:
            return _json(400, {"error": "bill_id, patient_id and amount_paid are required"})
        # validate bill + patient
        bill = get_item(BILLS, int(d["bill_id"]))
        if not bill:
            return _json(404, {"error": "Bill not found"})
        pay_id = next_id(PAYMENTS)
        put_item(PAYMENTS, {
            "payment_id": pay_id,
            "bill_id": int(d["bill_id"]),
            "patient_id": int(d["patient_id"]),
            "amount_paid": float(d["amount_paid"]),
            "payment_method": d.get("payment_method", "Cash"),
            "transaction_id": d.get("transaction_id"),
            "remarks": d.get("remarks"),
            "payment_date": now(),
        })
        # Trigger trg_payment_after_insert auto-updates bill status
        _refresh_bill_status(bill)
        if send_payment_receipt_email:
            p = get_item(PATIENTS, int(d["patient_id"]))
            if p and p.get("email"):
                try:
                    send_payment_receipt_email(p["email"], pay_id, d["bill_id"], float(d["amount_paid"]))
                except Exception:
                    pass
        return _json(201, {"message": "Payment recorded", "payment_id": pay_id})

    return _json(404, {"error": "Route not found", "resource": resource})
