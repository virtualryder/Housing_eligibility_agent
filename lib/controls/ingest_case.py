"""ingest_case — R3-2: the ONLY door through which raw applicant content enters the system.

Called BEFORE the workflow starts (by the intake API/operator script). Writes the raw application to
the encrypted, TTL'd, tenant-scoped case store and returns an OPAQUE ref — the Step Functions
execution is then started with {case_id, requester, case_ref} and NO raw content ever enters
execution input/output (the canary's strict gate).

The response deliberately echoes only length + ref — never the content."""
import json

import case_store


def _coerce(e):
    e = e or {}
    if isinstance(e, str):
        try:
            return json.loads(e)
        except Exception:
            return {"application": e}
    return e


def handler(event, context):
    e = _coerce(event)
    text = e.get("application", "")
    if not isinstance(text, str):
        text = json.dumps(text, ensure_ascii=False)
    if not text.strip():
        return {"ingested": False, "error": "empty application"}
    ref = case_store.put_case(text, kind="application", case_id=e.get("case_id", ""))
    return {"ingested": True, "case_ref": ref, "case_id": e.get("case_id", ""),
            "chars": len(text),
            "note": "start the workflow with {case_id, requester, case_ref} - raw content never enters Step Functions state"}
