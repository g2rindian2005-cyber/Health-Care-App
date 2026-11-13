"""
Lambda handler for the DISEASE table (DynamoDB `hospital-diseases`).

Routes:
    GET    /diseases                       -> list all disease records (synced)
    GET    /diseases/{id}                   -> get one disease record
    POST   /diseases                        -> add a disease (validates patient)
    PUT    /diseases/{id}                   -> update a disease
    DELETE /diseases/{id}                   -> delete a disease
    GET    /diseases/patient/{pid}          -> disease history for a patient
    GET    /diseases/active                 -> all active diseases

DynamoDB migration: the old code read MySQL on RDS via db_connection.
All reads/writes now go through dynamodb.py (boto3). Routes,
validations, messages and response shapes are unchanged.
"""
import json
from botocore.exceptions import ClientError

from dynamodb import (
    get_item, scan_all, query_index, put_item, update_item, delete_item,
    fetch_by_ids, full_name, next_id, now,
    PATIENTS, DOCTORS, DISEASES,
)


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
    if len(_seg) == 3 and _seg[0] == "diseases" and _seg[1] == "patient":
        _ppx["patient_id"] = _seg[2]
        resource = "/diseases/patient/{patient_id}"
    elif len(_seg) == 2 and _seg[0] == "diseases" and _seg[1] == "active":
        resource = "/diseases/active"
    elif len(_seg) == 2 and _seg[0] == "diseases" and _seg[1] != "active":
        _ppx["disease_id"] = _seg[1]
        resource = "/diseases/{disease_id}"
    event["pathParameters"] = _ppx

    if method == "OPTIONS":
        return _json(200, {"message": "OK"})

    # ---- ACTIVE DISEASES ----
    if method == "GET" and resource.endswith("/diseases/active"):
        rows = [d for d in scan_all(DISEASES)
                if d.get("status") in ("Active", "Under Treatment")]
        rows = _sort(rows, "follow_up_date", reverse=False)
        _names = fetch_by_ids(PATIENTS, [r["patient_id"] for r in rows])
        active = []
        for d in rows:
            active.append({
                "disease_id": d.get("disease_id"),
                "patient_id": d.get("patient_id"),
                "disease_name": d.get("disease_name"),
                "severity": d.get("severity"),
                "status": d.get("status"),
                "diagnosis_date": d.get("diagnosis_date"),
                "follow_up_date": d.get("follow_up_date"),
                "patient_name": full_name(_names.get(d.get("patient_id"))),
            })
        return _json(200, {"count": len(active), "active_diseases": active})

    # ---- DISEASES FOR PATIENT ----
    if method == "GET" and resource.endswith("/diseases/patient/{patient_id}"):
        pid = int(_pp(event, "patient_id"))
        rows = _sort(query_index(DISEASES, "patient_id-index", "patient_id", pid),
                     "diagnosis_date")
        _docs = fetch_by_ids(DOCTORS, [r.get("diagnosed_by") for r in rows])
        for r in rows:
            _d = _docs.get(r.get("diagnosed_by")) or {}
            r["doctor_name"] = full_name(_d)
            r["specialization"] = _d.get("specialization")
        return _json(200, {"count": len(rows), "diseases": rows})

    # ---- LIST ALL ----
    if method == "GET" and resource.rstrip("/").endswith("/diseases"):
        rows = _sort(scan_all(DISEASES), "diagnosis_date")
        _names = fetch_by_ids(PATIENTS, [r["patient_id"] for r in rows])
        diseases = []
        for d in rows:
            diseases.append({
                "disease_id": d.get("disease_id"),
                "patient_id": d.get("patient_id"),
                "disease_name": d.get("disease_name"),
                "severity": d.get("severity"),
                "status": d.get("status"),
                "diagnosis_date": d.get("diagnosis_date"),
                "follow_up_date": d.get("follow_up_date"),
                "patient_name": full_name(_names.get(d.get("patient_id"))),
            })
        return _json(200, {"count": len(diseases), "diseases": diseases})

    # ---- GET ONE ----
    if method == "GET" and resource.endswith("/diseases/{disease_id}"):
        did = int(_pp(event, "disease_id"))
        disease = get_item(DISEASES, did)
        if not disease:
            return _json(404, {"error": "Disease record not found"})
        return _json(200, {"disease": disease})

    # ---- CREATE ----
    if method == "POST" and resource.endswith("/diseases"):
        d = _body(event)
        if not d.get("patient_id") or not d.get("disease_name") or not d.get("diagnosis_date"):
            return _json(400, {"error": "patient_id, disease_name and diagnosis_date are required"})
        # Synchronisation: validate patient exists
        p = get_item(PATIENTS, int(d["patient_id"]))
        if not p:
            return _json(404, {"error": "Patient not found — cannot add disease"})
        # If diagnosed_by provided, validate doctor exists
        if d.get("diagnosed_by"):
            doc = get_item(DOCTORS, int(d["diagnosed_by"]))
            if not doc:
                return _json(404, {"error": "Doctor not found"})
        new_id = next_id(DISEASES)
        put_item(DISEASES, {
            "disease_id": new_id,
            "patient_id": int(d["patient_id"]),
            "disease_name": d["disease_name"],
            "diagnosis_date": d["diagnosis_date"],
            "severity": d.get("severity", "Mild"),
            "symptoms": d.get("symptoms"),
            "description": d.get("description"),
            "treatment": d.get("treatment"),
            "prescribed_meds": d.get("prescribed_meds"),
            "status": d.get("status", "Active"),
            "diagnosed_by": int(d["diagnosed_by"]) if d.get("diagnosed_by") else None,
            "follow_up_date": d.get("follow_up_date"),
            "created_at": now(),
            "updated_at": now(),
        })
        return _json(201, {"message": "Disease record created", "disease_id": new_id})

    # ---- UPDATE ----
    if method == "PUT" and resource.endswith("/diseases/{disease_id}"):
        did = int(_pp(event, "disease_id"))
        d = _body(event)
        fields = ["disease_name", "severity", "symptoms", "description", "treatment",
                  "prescribed_meds", "status", "diagnosed_by", "follow_up_date"]
        changes = {f: d[f] for f in fields if f in d}
        if not changes:
            return _json(400, {"error": "No fields to update"})
        if "diagnosed_by" in changes and changes["diagnosed_by"]:
            changes["diagnosed_by"] = int(changes["diagnosed_by"])
        update_item(DISEASES, did, changes)
        return _json(200, {"message": "Disease updated", "disease_id": did})

    # ---- DELETE ----
    if method == "DELETE" and resource.endswith("/diseases/{disease_id}"):
        did = int(_pp(event, "disease_id"))
        delete_item(DISEASES, did)
        return _json(200, {"message": "Disease record deleted", "disease_id": did})

    return _json(404, {"error": "Route not found", "resource": resource})
