"""
Lambda handler for the DOCTOR tables (DynamoDB `hospital-doctors` and
`hospital-doctor-assignments`).

Routes:
    GET    /doctors                         -> list all doctors
    GET    /doctors/{id}                     -> get one doctor (+ assigned patients)
    POST   /doctors                          -> add a doctor
    PUT    /doctors/{id}                     -> update a doctor
    DELETE /doctors/{id}                     -> delete a doctor

    GET    /assignments                      -> all assignments (synced with all tables)
    GET    /assignments/{id}                 -> one assignment
    GET    /assignments/doctor/{did}         -> assignments for a doctor
    GET    /assignments/patient/{pid}        -> assignments for a patient (patients: own record only)
    POST   /assignments                      -> assign doctor to patient (validates both; patients: own PID only)
    PUT    /assignments/{id}                 -> update an assignment
    DELETE /assignments/{id}                 -> delete an assignment

DynamoDB migration: the old code read MySQL on RDS via db_connection.
All reads/writes now go through dynamodb.py (boto3). Routes,
validations, messages and response shapes are unchanged.
"""
import json

from botocore.exceptions import ClientError

from cognito_auth import role_from_payload
from cognito_auth import verify_token as _verify_token

from dynamodb import (
    get_item, scan_all, query_index, put_item, update_item, delete_item,
    fetch_by_ids, full_name, next_id, now,
    PATIENTS, DISEASES, DOCTORS, ASSIGNMENTS,
)

import sys
import os

# Token verification is Cognito now (see cognito_auth.py): the doctor
# Lambda is the only data Lambda that checks the caller's token, and
# it verifies the RS256 signature against the user pool JWKS, plus
# iss / token_use / aud / exp. The pool id and client id come from
# Terraform common_env on every apply. A missing or invalid token
# fails closed (401) — there is no legacy bypass any more.
# Email helpers (send_email.py + smtp_config.py + templates/) are packaged
# inside this Lambda's own directory, so a plain import works at runtime.
# (The old sys.path hack pointed at repo-root email/, which the Lambda zip
# never contained — the import silently failed and no appointment email
# was ever sent.)
try:
    from send_email import send_appointment_email  # noqa: E402
except Exception:
    send_appointment_email = None


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


def _assignment_auth(event, patient):
    """Ownership check for assignment reads/writes.

    Returns None when the caller may proceed, else an error response
    (a _json dict) the route should return directly.
    Admins may touch any patient; a patient may only touch the
    patient record whose email matches their Cognito token email.
    Admin behaviour is unchanged: a missing patient record is left
    to the route's own handling. The token is verified by
    cognito_auth (RS256/JWKS); a missing or invalid token is a 401.
    """
    headers = event.get("headers") or {}
    auth = headers.get("Authorization") or headers.get("authorization") or ""
    token = auth[7:] if auth.startswith("Bearer ") else ""
    payload = _verify_token(token) if token else None
    if not payload:
        return _json(401, {"error": "Please sign in again"})
    if role_from_payload(payload) == "admin":
        return None
    if not patient:
        return _json(404, {"error": "Patient not found"})
    if str(patient.get("email") or "").strip().lower() != str(payload.get("email") or "").strip().lower():
        return _json(403, {"error": "You can only book appointments for yourself"})
    return None


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
    if len(_seg) == 2 and _seg[0] == "doctors":
        _ppx["doctor_id"] = _seg[1]
        resource = "/doctors/{doctor_id}"
    elif len(_seg) == 3 and _seg[0] == "assignments" and _seg[1] == "doctor":
        _ppx["doctor_id"] = _seg[2]
        resource = "/assignments/doctor/{doctor_id}"
    elif len(_seg) == 3 and _seg[0] == "assignments" and _seg[1] == "patient":
        _ppx["patient_id"] = _seg[2]
        resource = "/assignments/patient/{patient_id}"
    elif len(_seg) == 2 and _seg[0] == "assignments":
        _ppx["assignment_id"] = _seg[1]
        resource = "/assignments/{assignment_id}"
    event["pathParameters"] = _ppx

    if method == "OPTIONS":
        return _json(200, {"message": "OK"})

    # ============================================================
    # DOCTORS
    # ============================================================
    if method == "GET" and resource.rstrip("/").endswith("/doctors"):
        rows = _sort(scan_all(DOCTORS), "doctor_id")
        cols = ["doctor_id", "first_name", "last_name", "specialization",
                "department", "phone", "email", "availability", "consultation_fee"]
        rows = [{k: r[k] for k in cols if k in r} for r in rows]
        return _json(200, {"count": len(rows), "doctors": rows})

    if method == "GET" and resource.endswith("/doctors/{doctor_id}"):
        did = int(_pp(event, "doctor_id"))
        doc = get_item(DOCTORS, did)
        if not doc:
            return _json(404, {"error": "Doctor not found"})
        assigned = _sort(
            query_index(ASSIGNMENTS, "doctor_id-index", "doctor_id", did),
            "appointment_date")
        _pnames = fetch_by_ids(PATIENTS, [r["patient_id"] for r in assigned])
        _dnames = fetch_by_ids(DISEASES, [r.get("disease_id") for r in assigned])
        enriched = []
        for a in assigned:
            enriched.append({
                "assignment_id": a.get("assignment_id"),
                "patient_id": a.get("patient_id"),
                "disease_id": a.get("disease_id"),
                "status": a.get("status"),
                "appointment_date": a.get("appointment_date"),
                "patient_name": full_name(_pnames.get(a.get("patient_id"))),
                "disease_name": (_dnames.get(a.get("disease_id")) or {}).get("disease_name"),
            })
        return _json(200, {"doctor": doc, "assigned_patients": enriched})

    if method == "POST" and resource.endswith("/doctors"):
        d = _body(event)
        if not d.get("first_name") or not d.get("last_name") or not d.get("specialization"):
            return _json(400, {"error": "first_name, last_name and specialization are required"})
        new_id = next_id(DOCTORS)
        put_item(DOCTORS, {
            "doctor_id": new_id,
            "first_name": d["first_name"],
            "last_name": d["last_name"],
            "specialization": d["specialization"],
            "department": d.get("department"),
            "phone": d.get("phone"),
            "email": d.get("email"),
            "license_number": d.get("license_number"),
            "availability": d.get("availability", "Available"),
            "consultation_fee": float(d.get("consultation_fee", 0)),
            "created_at": now(),
            "updated_at": now(),
        })
        return _json(201, {"message": "Doctor added", "doctor_id": new_id})

    if method == "PUT" and resource.endswith("/doctors/{doctor_id}"):
        did = int(_pp(event, "doctor_id"))
        d = _body(event)
        fields = ["first_name", "last_name", "specialization", "department", "phone",
                  "email", "license_number", "availability", "consultation_fee"]
        changes = {f: d[f] for f in fields if f in d}
        if not changes:
            return _json(400, {"error": "No fields to update"})
        if "consultation_fee" in changes:
            changes["consultation_fee"] = float(changes["consultation_fee"])
        update_item(DOCTORS, did, changes)
        return _json(200, {"message": "Doctor updated", "doctor_id": did})

    if method == "DELETE" and resource.endswith("/doctors/{doctor_id}"):
        did = int(_pp(event, "doctor_id"))
        delete_item(DOCTORS, did)
        return _json(200, {"message": "Doctor deleted", "doctor_id": did})

    # ============================================================
    # ASSIGNMENTS (synchronisation hub)
    # ============================================================
    if method == "GET" and resource.rstrip("/").endswith("/assignments"):
        rows = _sort(scan_all(ASSIGNMENTS), "appointment_date")
        _docs = fetch_by_ids(DOCTORS, [r.get("doctor_id") for r in rows])
        _pnames = fetch_by_ids(PATIENTS, [r["patient_id"] for r in rows])
        _dnames = fetch_by_ids(DISEASES, [r.get("disease_id") for r in rows])
        assignments = []
        for a in rows:
            doc = _docs.get(a.get("doctor_id")) or {}
            assignments.append({
                "assignment_id": a.get("assignment_id"),
                "patient_id": a.get("patient_id"),
                "doctor_id": a.get("doctor_id"),
                "doctor_name": full_name(doc),
                "specialization": doc.get("specialization"),
                "disease_id": a.get("disease_id"),
                "appointment_date": a.get("appointment_date"),
                "status": a.get("status"),
                "room_number": a.get("room_number"),
                "notes": a.get("notes"),
                "patient_name": full_name(_pnames.get(a.get("patient_id"))),
                "disease_name": (_dnames.get(a.get("disease_id")) or {}).get("disease_name"),
            })
        return _json(200, {"count": len(assignments), "assignments": assignments})

    if method == "GET" and resource.endswith("/assignments/doctor/{doctor_id}"):
        did = int(_pp(event, "doctor_id"))
        rows = _sort(
            query_index(ASSIGNMENTS, "doctor_id-index", "doctor_id", did),
            "appointment_date")
        _pnames = fetch_by_ids(PATIENTS, [r["patient_id"] for r in rows])
        _dnames = fetch_by_ids(DISEASES, [r.get("disease_id") for r in rows])
        assignments = []
        for a in rows:
            assignments.append({
                "assignment_id": a.get("assignment_id"),
                "patient_id": a.get("patient_id"),
                "disease_id": a.get("disease_id"),
                "appointment_date": a.get("appointment_date"),
                "status": a.get("status"),
                "patient_name": full_name(_pnames.get(a.get("patient_id"))),
                "disease_name": (_dnames.get(a.get("disease_id")) or {}).get("disease_name"),
            })
        return _json(200, {"count": len(assignments), "assignments": assignments})

    if method == "GET" and resource.endswith("/assignments/patient/{patient_id}"):
        pid = int(_pp(event, "patient_id"))
        _auth_err = _assignment_auth(event, get_item(PATIENTS, pid))
        if _auth_err:
            return _auth_err
        rows = _sort(
            query_index(ASSIGNMENTS, "patient_id-index", "patient_id", pid),
            "appointment_date")
        _docs = fetch_by_ids(DOCTORS, [r.get("doctor_id") for r in rows])
        assignments = []
        for a in rows:
            doc = _docs.get(a.get("doctor_id")) or {}
            assignments.append({
                "assignment_id": a.get("assignment_id"),
                "doctor_id": a.get("doctor_id"),
                "doctor_name": full_name(doc),
                "specialization": doc.get("specialization"),
                "disease_id": a.get("disease_id"),
                "appointment_date": a.get("appointment_date"),
                "status": a.get("status"),
                "room_number": a.get("room_number"),
            })
        return _json(200, {"count": len(assignments), "assignments": assignments})

    if method == "GET" and resource.endswith("/assignments/{assignment_id}"):
        aid = int(_pp(event, "assignment_id"))
        row = get_item(ASSIGNMENTS, aid)
        if not row:
            return _json(404, {"error": "Assignment not found"})
        return _json(200, {"assignment": row})

    if method == "POST" and resource.endswith("/assignments"):
        d = _body(event)
        if not d.get("patient_id") or not d.get("doctor_id"):
            return _json(400, {"error": "patient_id and doctor_id are required"})
        # Synchronisation: validate patient + doctor both exist
        p = get_item(PATIENTS, int(d["patient_id"]))
        if not p:
            return _json(404, {"error": "Patient not found"})
        _auth_err = _assignment_auth(event, p)
        if _auth_err:
            return _auth_err
        doc = get_item(DOCTORS, int(d["doctor_id"]))
        if not doc:
            return _json(404, {"error": "Doctor not found"})
        asg_id = next_id(ASSIGNMENTS)
        put_item(ASSIGNMENTS, {
            "assignment_id": asg_id,
            "patient_id": int(d["patient_id"]),
            "doctor_id": int(d["doctor_id"]),
            "disease_id": int(d["disease_id"]) if d.get("disease_id") else None,
            "appointment_date": d.get("appointment_date"),
            "status": d.get("status", "Assigned"),
            "room_number": d.get("room_number"),
            "notes": d.get("notes"),
            "assignment_date": now(),
            "created_at": now(),
            "updated_at": now(),
        })
        if send_appointment_email and p.get("email"):
            try:
                send_appointment_email(p["email"], d["patient_id"], asg_id,
                                       full_name(doc) or "",
                                       d.get("appointment_date", ""))
            except Exception:
                pass
        return _json(201, {"message": "Doctor assigned", "assignment_id": asg_id})

    if method == "PUT" and resource.endswith("/assignments/{assignment_id}"):
        aid = int(_pp(event, "assignment_id"))
        d = _body(event)
        _row = get_item(ASSIGNMENTS, aid)
        _auth_err = _assignment_auth(event, get_item(PATIENTS, _row.get("patient_id")) if _row else None)
        if _auth_err:
            return _auth_err
        fields = ["patient_id", "doctor_id", "disease_id", "appointment_date",
                  "status", "room_number", "notes"]
        changes = {f: d[f] for f in fields if f in d}
        if not changes:
            return _json(400, {"error": "No fields to update"})
        for k in ("patient_id", "doctor_id", "disease_id"):
            if changes.get(k):
                changes[k] = int(changes[k])
        update_item(ASSIGNMENTS, aid, changes)
        # Appointment confirmed -> notify the patient by email ("Your
        # appointment is confirmed"). Best-effort only: a failed email
        # must never break the API response.
        if _row and changes.get("status") == "Confirmed" and send_appointment_email:
            try:
                _p = get_item(PATIENTS, int(_row.get("patient_id")))
                _did = changes.get("doctor_id", _row.get("doctor_id"))
                _doc = get_item(DOCTORS, int(_did)) if _did else None
                _date = changes.get("appointment_date", _row.get("appointment_date"))
                if _p and _p.get("email"):
                    send_appointment_email(_p["email"], _p.get("patient_id", _row.get("patient_id")),
                                           aid, full_name(_doc) or "",
                                           _date or "")
            except Exception:
                pass
        return _json(200, {"message": "Assignment updated", "assignment_id": aid})

    if method == "DELETE" and resource.endswith("/assignments/{assignment_id}"):
        aid = int(_pp(event, "assignment_id"))
        _row = get_item(ASSIGNMENTS, aid)
        _auth_err = _assignment_auth(event, get_item(PATIENTS, _row.get("patient_id")) if _row else None)
        if _auth_err:
            return _auth_err
        delete_item(ASSIGNMENTS, aid)
        return _json(200, {"message": "Assignment deleted", "assignment_id": aid})

    return _json(404, {"error": "Route not found", "resource": resource})
