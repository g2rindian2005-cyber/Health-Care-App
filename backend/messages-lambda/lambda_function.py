"""
Lambda handler for patient-doctor messages (DynamoDB `hospital-messages`).

Routes:
    POST /messages            -> send a message
    GET  /messages            -> list messages: a conversation
                                 (?patient_id=X&doctor_id=Y), a doctor's
                                 inbox (?doctor_id=X) or a patient's
                                 threads (?patient_id=X)
    POST /messages/read       -> mark the other side's messages as read

Ownership: the token role comes from cognito_auth.role_from_payload
("admin" / "doctor" / "patient"). A patient is matched to their
patient record by token email and may only touch their own PID; a
doctor is matched to their doctor record by token email and may
only touch their own DID; an admin may touch anything.
"""
import json

from botocore.exceptions import ClientError

from cognito_auth import role_from_payload
from cognito_auth import verify_token as _verify_token

from dynamodb import (
    get_item, scan_all, query_index, put_item, update_item,
    next_id, now,
    PATIENTS, DOCTORS, MESSAGES,
)


def _body(event):
    raw = event.get("body") or "{}"
    return raw if isinstance(raw, (dict, list)) else json.loads(raw)


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


def _caller(event):
    """Verify the caller's Cognito token.

    Returns (payload, role), or (None, None) when there is no token
    or it does not verify. A missing or invalid token fails closed
    (401) on the routes that call this.
    """
    headers = event.get("headers") or {}
    auth = headers.get("Authorization") or headers.get("authorization") or ""
    token = auth[7:] if auth.startswith("Bearer ") else ""
    payload = _verify_token(token) if token else None
    if not payload:
        return None, None
    return payload, role_from_payload(payload)


def _doctor_did_for_email(email):
    """Doctor id for a token email, or None.

    The doctors table has no email index, so this scans it — the
    table is small (one row per doctor) and this is only needed on
    doctor-scoped calls.
    """
    if not email or "@" not in email:
        return None
    wanted = str(email).strip().lower()
    for r in scan_all(DOCTORS):
        if str(r.get("email") or "").strip().lower() == wanted:
            return r.get("doctor_id")
    return None


def _patient_pid_for_email(email):
    """Patient id for a token email, or None."""
    if not email or "@" not in email:
        return None
    wanted = str(email).strip().lower()
    for r in scan_all(PATIENTS):
        if str(r.get("email") or "").strip().lower() == wanted:
            return r.get("patient_id")
    return None


def _messages_auth(event, patient_id, doctor_id):
    """Ownership check for a message thread.

    Returns (payload, role, error_response): error_response is None
    when the caller may proceed, else a _json dict the route should
    return directly. Admins may touch any thread; a patient may only
    touch threads carrying their own PID (patient_id must be given);
    a doctor may only touch threads carrying their own DID
    (doctor_id must be given). A missing or invalid token is a 401.
    """
    payload, role = _caller(event)
    if not payload:
        return None, None, _json(401, {"error": "Please sign in again"})
    if role == "admin":
        return payload, role, None
    if role == "patient":
        if not patient_id:
            return payload, role, _json(403, {"error": "You can only view your own messages"})
        pid = _patient_pid_for_email(payload.get("email"))
        if pid is None or int(pid) != int(patient_id):
            return payload, role, _json(403, {"error": "You can only view your own messages"})
        return payload, role, None
    # doctor
    if not doctor_id:
        return payload, role, _json(403, {"error": "You can only view your own messages"})
    did = _doctor_did_for_email(payload.get("email"))
    if did is None or int(did) != int(doctor_id):
        return payload, role, _json(403, {"error": "You can only view your own messages"})
    return payload, role, None


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
    if len(_seg) == 2 and _seg[0] == "messages" and _seg[1] == "read":
        resource = "/messages/read"
    elif len(_seg) == 1 and _seg[0] == "messages":
        resource = "/messages"

    if method == "OPTIONS":
        return _json(200, {"message": "OK"})

    # ============================================================
    # SEND A MESSAGE
    # ============================================================
    if method == "POST" and resource.rstrip("/").endswith("/messages") \
            and not resource.endswith("/messages/read"):
        d = _body(event)
        pid, did = d.get("patient_id"), d.get("doctor_id")
        sender = str(d.get("sender") or "").strip().lower()
        text = str(d.get("text") or "").strip()
        if not pid or not did:
            return _json(400, {"error": "patient_id and doctor_id are required"})
        if sender not in ("patient", "doctor"):
            return _json(400, {"error": "sender must be patient or doctor"})
        if not text:
            return _json(400, {"error": "Message text is required"})
        payload, role, err = _messages_auth(event, pid, did)
        if err:
            return err
        if role == "patient" and sender != "patient":
            return _json(403, {"error": "You can only send messages as the patient"})
        if role == "doctor" and sender != "doctor":
            return _json(403, {"error": "You can only send messages as the doctor"})
        if not get_item(PATIENTS, int(pid)):
            return _json(404, {"error": "Patient not found"})
        if not get_item(DOCTORS, int(did)):
            return _json(404, {"error": "Doctor not found"})
        mid = next_id(MESSAGES)
        put_item(MESSAGES, {
            "message_id": mid,
            "patient_id": int(pid),
            "doctor_id": int(did),
            "sender": sender,
            "text": text,
            "created_at": now(),
            "read_by_patient": sender == "patient",
            "read_by_doctor": sender == "doctor",
        })
        return _json(201, {"message": "Message sent", "message_id": mid})

    # ============================================================
    # LIST MESSAGES
    # ============================================================
    if method == "GET" and resource.rstrip("/").endswith("/messages"):
        qs = event.get("queryStringParameters") or {}
        pid, did = qs.get("patient_id"), qs.get("doctor_id")
        if not pid and not did:
            return _json(400, {"error": "patient_id or doctor_id is required"})
        payload, role, err = _messages_auth(event, pid, did)
        if err:
            return err
        if pid and did:
            rows = [r for r in query_index(
                MESSAGES, "patient_id-index", "patient_id", int(pid))
                if int(r.get("doctor_id") or 0) == int(did)]
        elif did:
            rows = query_index(MESSAGES, "doctor_id-index", "doctor_id", int(did))
        else:
            rows = query_index(MESSAGES, "patient_id-index", "patient_id", int(pid))
        rows = sorted(rows, key=lambda r: (r.get("created_at") or "", r.get("message_id") or 0))
        return _json(200, {"count": len(rows), "messages": rows})

    # ============================================================
    # MARK AS READ
    # ============================================================
    if method == "POST" and resource.endswith("/messages/read"):
        d = _body(event)
        pid, did = d.get("patient_id"), d.get("doctor_id")
        if not pid or not did:
            return _json(400, {"error": "patient_id and doctor_id are required"})
        payload, role, err = _messages_auth(event, pid, did)
        if err:
            return err
        rows = [r for r in query_index(
            MESSAGES, "patient_id-index", "patient_id", int(pid))
            if int(r.get("doctor_id") or 0) == int(did)]
        marked = 0
        for r in rows:
            if role == "patient" and r.get("sender") == "doctor" and not r.get("read_by_patient"):
                update_item(MESSAGES, r["message_id"], {"read_by_patient": True}, set_updated_at=False)
                marked += 1
            elif role == "doctor" and r.get("sender") == "patient" and not r.get("read_by_doctor"):
                update_item(MESSAGES, r["message_id"], {"read_by_doctor": True}, set_updated_at=False)
                marked += 1
            elif role == "admin" and (not r.get("read_by_patient") or not r.get("read_by_doctor")):
                update_item(MESSAGES, r["message_id"],
                            {"read_by_patient": True, "read_by_doctor": True},
                            set_updated_at=False)
                marked += 1
        return _json(200, {"message": "Messages marked as read", "marked": marked})

    return _json(404, {"error": "Not found"})
