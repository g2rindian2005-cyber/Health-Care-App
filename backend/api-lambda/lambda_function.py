"""Single API Lambda: routes every API Gateway request to the module
handler for its first path segment.

Consolidated from the 7 per-module API Lambdas (patient, billing,
disease, doctor, lab, pharmacy, messages) so the project deploys with
one API Lambda instead of seven — the Pluralsight Hands-on Playground
suspends the account when ~10 Lambda functions are created at once.
No route, status code, or response shape changed: each module's
handler.py is that module's original lambda_function.py with only its
send_email import rewritten (to the subpackage-relative form), and it
is called here with the original event unchanged. Each module's own
lambda_handler still does its own error handling (ClientError -> 503,
Exception -> 500).

Import layout note: Lambda loads this file as a top-level module and
the zip root is on sys.path, so the subpackages are imported by their
absolute names (billing.handler, ...) and the shared helpers
(dynamodb, cognito_auth, smtp_config) are imported absolutely from the
zip root, exactly as each per-module Lambda did.
"""
import json

from billing.handler import lambda_handler as _billing
from disease.handler import lambda_handler as _disease
from doctor.handler import lambda_handler as _doctor
from lab.handler import lambda_handler as _lab
from messages.handler import lambda_handler as _messages
from patient.handler import lambda_handler as _patient
from pharmacy.handler import lambda_handler as _pharmacy

_ROUTES = {
    "patients": _patient,
    "bills": _billing,
    "payments": _billing,
    "dues": _billing,
    "diseases": _disease,
    "doctors": _doctor,
    "assignments": _doctor,
    "lab": _lab,
    "pharmacy": _pharmacy,
    "messages": _messages,
}


def lambda_handler(event, context):
    path = (event or {}).get("path") or ""
    seg = [s for s in path.split("/") if s]
    handler = _ROUTES.get(seg[0]) if seg else None
    if handler is None:
        return {
            "statusCode": 404,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Not found"}),
        }
    return handler(event, context)
