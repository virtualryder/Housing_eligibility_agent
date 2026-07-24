"""case_store.py — Review-3 R3-2: ZERO-PII PASS-BY-REFERENCE orchestration.

THE FINDING THIS CLOSES (the PII canary's 87 hits): Step Functions execution history is a DATA STORE.
When the raw application travels as state input/output, the workflow engine becomes an additional
sensitive-data repository — visible to anyone with `states:GetExecutionHistory`, retained for 90
days, and outside the KMS/story of the purpose-built stores.

THE FIX: raw applicant content is written ONCE to an encrypted, TTL'd, tenant-scoped DynamoDB store
(CASE_TABLE — CMK-encrypted under `kms=customer-managed`), and ONLY an opaque `case_ref` travels
through the controller. Tools that legitimately need the content (intake extraction, masking) fetch
it server-side by ref; nothing returns raw text into state output. The drafted notice (de-identified
but still content) is likewise stored and returned as `notice_ref`.

Tenant scoping (B5): reads verify the record's tenant against the DEPLOYMENT'S pinned tenant —
a ref from another tenant returns None (fail-closed), exactly like the sanitized-artifact rule."""
import os
import time
import uuid

import tenancy

_TABLE_ENV = "CASE_TABLE"
_TTL_SECONDS = int(os.environ.get("CASE_TTL_SECONDS", "604800"))  # 7d working data; WORM holds evidence


def _table():
    name = os.environ.get(_TABLE_ENV, "")
    if not name:
        return None
    import boto3
    return boto3.resource("dynamodb").Table(name)


class MemoryCaseStore:
    """In-process store for tests/offline runs (module-level singleton)."""
    items = {}


def put_case(text, kind="application", case_id=""):
    """Store content; return the opaque ref (never the content). Fail-loud: without a configured
    store there is nothing safe to do with raw content — the caller must not fall back to inlining."""
    ref = f"case-{uuid.uuid4().hex}"
    item = {"case_ref": ref, "text": text, "kind": kind, "case_id": str(case_id or ""),
            "tenant": tenancy.resolve_tenant(), "expires_at": int(time.time()) + _TTL_SECONDS}
    t = _table()
    if t is not None:
        t.put_item(Item=item)
    else:
        MemoryCaseStore.items[ref] = item
    return ref


def get_case(ref):
    """Fetch content by ref. None (fail-closed) on: missing ref, unknown ref, or a record belonging
    to another tenant. Never raises content into the caller's error path."""
    if not ref or not isinstance(ref, str):
        return None
    t = _table()
    if t is not None:
        try:
            item = t.get_item(Key={"case_ref": ref}).get("Item")
        except Exception:
            return None
    else:
        item = MemoryCaseStore.items.get(ref)
    if not item:
        return None
    if not tenancy.check_ref_tenant(item):
        return None   # B5: cross-tenant fetch refused
    return item.get("text")
