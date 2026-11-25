"""
Shared DynamoDB data-access helper for the data Lambdas.

Replaces db_connection.py (MySQL/RDS). One DynamoDB table per former
MySQL table, PAY_PER_REQUEST billing — no instances, no VPC, no SQL.

Tables (env var -> default name -> partition key):
    patients      PATIENTS_TABLE       hospital-patients            patient_id
    doctors       DOCTORS_TABLE        hospital-doctors             doctor_id
    assignments   ASSIGNMENTS_TABLE    hospital-doctor-assignments  assignment_id
    diseases      DISEASES_TABLE       hospital-diseases            disease_id
    bills         BILLS_TABLE          hospital-bills               bill_id
    payments      PAYMENTS_TABLE       hospital-payments            payment_id
    lab_tests     LAB_TESTS_TABLE      hospital-lab-tests           test_id
    lab_orders    LAB_ORDERS_TABLE     hospital-lab-orders          order_id
    medicines     MEDICINES_TABLE      hospital-medicines           medicine_id
    prescriptions PRESCRIPTIONS_TABLE  hospital-prescriptions       prescription_id
    messages      MESSAGES_TABLE       hospital-messages            message_id
    counters      COUNTERS_TABLE       hospital-id-counters         table_name (S)

GSIs (field-index, projection ALL):
    assignments: patient_id-index, doctor_id-index
    diseases:    patient_id-index
    bills:       patient_id-index
    payments:    bill_id-index, patient_id-index
    lab_orders:  patient_id-index
    prescriptions: patient_id-index
    messages:    patient_id-index, doctor_id-index

Notes:
- Numbers come back as int/float (Decimal is normalised on read), so
  handlers see the same Python values pymysql used to return.
- Money is stored as DynamoDB Number; on read it normalises to int
  when whole (800) or float otherwise (800.5). The API used to return
  money as a string ("800.00") because pymysql returns Decimal and the
  handlers serialise with default=str; it now arrives as a JSON number.
  The frontend parses both (parseFloat), so nothing breaks.
- DynamoDB cannot store None: None values are dropped on create and
  REMOVEd on update (the MySQL equivalent of setting a column NULL).
- `next_id` replaces AUTO_INCREMENT via an atomic counter item, so
  ids stay small sequential numbers (1, 2, 3, ...) just like MySQL.
- Set DYNAMODB_ENDPOINT_URL to run against DynamoDB Local.
"""
import os
from datetime import datetime
from decimal import Decimal

import boto3


def _is_conditional_failed(exc):
    """True when a DynamoDB conditional write failed its condition.
    Real boto3 raises the modelled ConditionalCheckFailedException;
    a ClientError carries the same code in response['Error']['Code']."""
    if exc.__class__.__name__ == "ConditionalCheckFailedException":
        return True
    resp = getattr(exc, "response", {}) or {}
    return resp.get("Error", {}).get("Code") == "ConditionalCheckFailedException"

# logical key -> (env var, default table name, partition-key attribute)
TABLES = {
    "patients":      ("PATIENTS_TABLE",      "hospital-patients",           "patient_id"),
    "doctors":       ("DOCTORS_TABLE",       "hospital-doctors",            "doctor_id"),
    "assignments":   ("ASSIGNMENTS_TABLE",   "hospital-doctor-assignments", "assignment_id"),
    "diseases":      ("DISEASES_TABLE",      "hospital-diseases",           "disease_id"),
    "bills":         ("BILLS_TABLE",         "hospital-bills",              "bill_id"),
    "payments":      ("PAYMENTS_TABLE",      "hospital-payments",           "payment_id"),
    "lab_tests":     ("LAB_TESTS_TABLE",     "hospital-lab-tests",          "test_id"),
    "lab_orders":    ("LAB_ORDERS_TABLE",    "hospital-lab-orders",         "order_id"),
    "medicines":     ("MEDICINES_TABLE",     "hospital-medicines",          "medicine_id"),
    "prescriptions": ("PRESCRIPTIONS_TABLE", "hospital-prescriptions",      "prescription_id"),
    "messages":      ("MESSAGES_TABLE",      "hospital-messages",           "message_id"),
}

# logical keys, for readable handler code
PATIENTS = "patients"
DOCTORS = "doctors"
ASSIGNMENTS = "assignments"
DISEASES = "diseases"
BILLS = "bills"
PAYMENTS = "payments"
LAB_TESTS = "lab_tests"
LAB_ORDERS = "lab_orders"
MEDICINES = "medicines"
PRESCRIPTIONS = "prescriptions"
MESSAGES = "messages"

COUNTERS_ENV = "COUNTERS_TABLE"
COUNTERS_DEFAULT = "hospital-id-counters"

_dynamodb = None
_tables = {}
_counters_table = None


def _resource():
    global _dynamodb
    if _dynamodb is None:
        _dynamodb = boto3.resource(
            "dynamodb",
            endpoint_url=os.environ.get("DYNAMODB_ENDPOINT_URL") or None,
        )
    return _dynamodb


def _table_name(logical):
    env, default, _pk = TABLES[logical]
    return os.environ.get(env, default)


def table(logical):
    """boto3 Table for a logical table key (cached)."""
    name = _table_name(logical)
    if name not in _tables:
        _tables[name] = _resource().Table(name)
    return _tables[name]


def _counters():
    global _counters_table
    if _counters_table is None:
        name = os.environ.get(COUNTERS_ENV, COUNTERS_DEFAULT)
        _counters_table = _resource().Table(name)
    return _counters_table


def _pk(logical):
    return TABLES[logical][2]


def now():
    """MySQL DATETIME format, e.g. '2026-11-13 11:40:00'."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ------------------------------------------------------------------
# Value conversion
# ------------------------------------------------------------------
def _to_ddb(value):
    """Prepare a value for DynamoDB: drop None, float/int -> Decimal."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    if isinstance(value, Decimal):
        return value
    if isinstance(value, dict):
        return {k: _to_ddb(v) for k, v in value.items() if v is not None}
    if isinstance(value, (list, tuple)):
        return [_to_ddb(v) for v in value]
    return value


def _from_ddb(value):
    """Normalise DynamoDB values back to plain Python (Decimal -> int/float)."""
    if isinstance(value, Decimal):
        return int(value) if value == int(value) else float(value)
    if isinstance(value, dict):
        return {k: _from_ddb(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_from_ddb(v) for v in value]
    return value


# ------------------------------------------------------------------
# CRUD
# ------------------------------------------------------------------
def get_item(logical, key_value):
    """One item by partition key, or None."""
    resp = table(logical).get_item(Key={_pk(logical): key_value})
    item = resp.get("Item")
    return _from_ddb(item) if item else None


def scan_all(logical):
    """Every item in a table (paginated)."""
    tbl = table(logical)
    items, kwargs = [], {}
    while True:
        resp = tbl.scan(**kwargs)
        items.extend(resp.get("Items", []))
        if "LastEvaluatedKey" not in resp:
            break
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
    return [_from_ddb(i) for i in items]


def query_index(logical, index, field, value):
    """All items where a GSI key equals `value` (paginated)."""
    tbl = table(logical)
    items, kwargs = [], {
        "IndexName": index,
        "KeyConditionExpression": "#k = :v",
        "ExpressionAttributeNames": {"#k": field},
        "ExpressionAttributeValues": {":v": _to_ddb(value)},
    }
    while True:
        resp = tbl.query(**kwargs)
        items.extend(resp.get("Items", []))
        if "LastEvaluatedKey" not in resp:
            break
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
    return [_from_ddb(i) for i in items]


def put_item(logical, item):
    """Create an item (None-valued attributes are dropped)."""
    table(logical).put_item(Item=_to_ddb(item))
    return item


def update_item(logical, key_value, fields, set_updated_at=True):
    """Partial update. None-valued fields are REMOVEd (MySQL NULL).
    Returns True if the item existed, False if it did not."""
    sets, removes, names, values = [], [], {}, {}
    for i, (field, value) in enumerate(fields.items()):
        nk, vk = f"#f{i}", f":v{i}"
        names[nk] = field
        if value is None:
            removes.append(nk)
        else:
            sets.append(f"{nk} = {vk}")
            values[vk] = _to_ddb(value)
    if set_updated_at:
        names["#upd"] = "updated_at"
        sets.append("#upd = :upd")
        values[":upd"] = now()
    parts = []
    if sets:
        parts.append("SET " + ", ".join(sets))
    if removes:
        parts.append("REMOVE " + ", ".join(removes))
    if not parts:
        return True
    try:
        table(logical).update_item(
            Key={_pk(logical): key_value},
            UpdateExpression=" ".join(parts),
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=values,
            ConditionExpression=f"attribute_exists({_pk(logical)})",
        )
    except Exception as exc:
        # boto3 raises ConditionalCheckFailedException when the item
        # does not exist; the fake used in tests raises the same class.
        if _is_conditional_failed(exc):
            return False
        raise
    return True


def update_item_conditional(logical, key_value, expression, names, values, condition):
    """Raw conditional update (e.g. the pharmacy stock guard).
    Returns True on success, False when the condition fails."""
    try:
        table(logical).update_item(
            Key={_pk(logical): key_value},
            UpdateExpression=expression,
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=values,
            ConditionExpression=condition,
        )
    except Exception as exc:
        if _is_conditional_failed(exc):
            return False
        raise
    return True


def delete_item(logical, key_value):
    table(logical).delete_item(Key={_pk(logical): key_value})


# ------------------------------------------------------------------
# Cross-table reads + ids
# ------------------------------------------------------------------
def fetch_by_ids(logical, ids):
    """Live cross-table read: fetch rows from ANOTHER table by primary
    key. Returns {id: row-dict} — the DynamoDB equivalent of the old
    fetch_by_ids() SQL helper."""
    ids = sorted({int(i) for i in ids if i is not None})
    if not ids:
        return {}
    pk, tname = _pk(logical), _table_name(logical)
    out, resource = {}, _resource()
    for start in range(0, len(ids), 100):
        keys = [{pk: i} for i in ids[start:start + 100]]
        req = {tname: {"Keys": keys}}
        while req:
            resp = resource.batch_get_item(RequestItems=req)
            for item in resp.get("Responses", {}).get(tname, []):
                item = _from_ddb(item)
                out[item[pk]] = item
            req = resp.get("UnprocessedKeys", {})
    return out


def full_name(item):
    """'First Last' from a patients/doctors row, or None."""
    if not item:
        return None
    return f"{item.get('first_name', '')} {item.get('last_name', '')}".strip() or None


def next_id(logical):
    """Next sequential id for a table (replaces MySQL AUTO_INCREMENT).
    Atomic: concurrent Lambdas can never get the same id."""
    physical = _table_name(logical)
    resp = _counters().update_item(
        Key={"table_name": physical},
        UpdateExpression="SET next_id = if_not_exists(next_id, :zero) + :one",
        ExpressionAttributeValues={":zero": 0, ":one": 1},
        ReturnValues="UPDATED_NEW",
    )
    return int(resp["Attributes"]["next_id"])


def set_counter(logical, value):
    """Raise a table's id counter to at least `value` (used by the
    db-init Lambda after seeding, so new ids never collide with seed
    ids). Never lowers an existing counter."""
    tbl = _counters()
    key = {"table_name": _table_name(logical)}
    try:
        tbl.update_item(
            Key=key,
            UpdateExpression="SET next_id = :v",
            ExpressionAttributeValues={":v": value},
            ConditionExpression="attribute_not_exists(next_id) OR next_id < :v",
        )
    except Exception as exc:
        if _is_conditional_failed(exc):
            return
        raise
