"""GA-5 — exactly-once finalization + duplicate-submission protection. Offline (fake DynamoDB)."""
import importlib.util
import os
import pathlib
import sys

import pytest

import governed_core

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib" / "controls"))
os.environ.setdefault("PROVENANCE_SECRET", "p0-unit-provenance-secret")
os.environ.setdefault("AUDIT_TABLE", "t")

# finalize_signoff is CORE and now comes from the pinned governed-core package; signoff_register is a
# DECLARED domain override that still lives in lib/controls (see tests/test_core_dependency.py).
# Search the agent's own controls first, then the package — the same precedence the bundler uses.
CORE_CONTROLS = pathlib.Path(governed_core.controls_dir())


def _load(name):
    for base in (ROOT / "lib" / "controls", CORE_CONTROLS):
        p = base / f"{name}.py"
        if p.exists():
            spec = importlib.util.spec_from_file_location(name, p)
            m = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(m)
            return m
    raise FileNotFoundError(name)


class _CondFail(Exception):
    pass


class FakeTable:
    """Enforces real DynamoDB conditional-put semantics for the patterns used here."""
    def __init__(self):
        self.items = {}

    def put_item(self, Item, ConditionExpression=None, ExpressionAttributeNames=None,
                 ExpressionAttributeValues=None):
        key = Item.get("audit_id") or Item.get("case_id")
        exists = key in self.items
        if ConditionExpression and "attribute_not_exists" in ConditionExpression:
            if exists:
                # honour the register's OR-status escape hatch
                if "#s <> :pending" in ConditionExpression and self.items[key].get("status") != "PENDING":
                    pass
                else:
                    from botocore.exceptions import ClientError
                    raise ClientError({"Error": {"Code": "ConditionalCheckFailedException"}}, "PutItem")
        self.items[key] = dict(Item)

    def get_item(self, Key):
        k = list(Key.values())[0]
        return {"Item": self.items.get(k)}


@pytest.fixture()
def fake_ddb(monkeypatch):
    table = FakeTable()

    class _Res:
        def Table(self, name):
            return table

    import boto3
    monkeypatch.setattr(boto3, "resource", lambda *_a, **_k: _Res())
    return table


def _ctx():
    return type("C", (), {"invoked_function_arn": "arn:aws:lambda:us-east-1:111122223333:function:x"})()


# ── finalize: exactly-once ───────────────────────────────────────────────────

def test_finalize_is_exactly_once_across_retries_and_different_approvers(fake_ddb, monkeypatch):
    # governed-core 1.5.0 added G2 approval-path verification to finalize (it now REFUSES an
    # unverified approval); 1.6.0 added tenant binding + evidence-routed ledger. Approval verification
    # and tenant routing have their own coverage; THIS test isolates the exactly-once FINAL# marker, so
    # it uses the handler's documented sandbox escape (SIGNOFF_ALLOW_UNVERIFIED) and stubs the 1.6.0
    # evidence hooks to exercise the commit-once logic directly.
    monkeypatch.setenv("SIGNOFF_ALLOW_UNVERIFIED", "true")
    fz = _load("finalize_signoff")
    recorded = []
    _seen = {}

    def _rec(ev, ctx, source=None):
        import hashlib, json as _j
        eid = hashlib.sha256(_j.dumps(ev, sort_keys=True, default=str).encode("utf-8")).hexdigest()
        if eid in _seen:  # governed-core 1.10.0 (#159): evidence is content-hash idempotent on exact replay
            return {"stored": False, "worm": True, "reason": "append-only: already recorded"}
        recorded.append(ev)
        _seen[eid] = True
        return {"stored": True, "audit_id": "A%d" % len(recorded), "chain_hash": "h", "seq": 0, "worm": True}

    monkeypatch.setattr(fz.evidence, "record_event", _rec, raising=False)
    monkeypatch.setattr(fz.evidence, "bind_tenant", lambda event: None, raising=False)
    monkeypatch.setattr(fz.evidence, "route_table", lambda name, logical: name, raising=False)
    r1 = fz.handler({"case_id": "HOU-X", "requester": "req", "approver": "appr-1"}, _ctx())
    assert r1["committed"] is True and not r1.get("idempotent")
    # retried Lambda (same approver) -> idempotent, NO second COMMITTED record
    r2 = fz.handler({"case_id": "HOU-X", "requester": "req", "approver": "appr-1"}, _ctx())
    assert r2["committed"] is True and r2["idempotent"] is True
    assert r2["submission_id"] == r1["submission_id"]
    # a DIFFERENT approver: the marker still returns the ORIGINAL submission (exactly-once SUBMISSION),
    # idempotent=True. Under #159 the COMMITTED evidence write is evidence-first, so the exact-replay
    # (appr-1) is deduped by the evidence content-hash idempotency; a DIFFERENT approver writes a
    # distinct COMMITTED here ONLY because SIGNOFF_ALLOW_UNVERIFIED bypasses the approval gate - in
    # production G2 approval-path verification refuses a second approver (its own coverage).
    r3 = fz.handler({"case_id": "HOU-X", "requester": "req", "approver": "appr-2"}, _ctx())
    assert r3["committed"] is True and r3["idempotent"] is True
    assert r3["submission_id"] == r1["submission_id"]   # ORIGINAL submission returned
    committed = [r for r in recorded if r.get("phase") == "COMMITTED"]
    assert len(committed) == 2 and {c["actor"] for c in committed} == {"appr-1", "appr-2"}


# ── register: duplicate submission fails closed ──────────────────────────────

def test_duplicate_pending_submission_fails_closed(fake_ddb):
    rg = _load("signoff_register")
    r1 = rg.handler({"case_id": "HOU-Y", "requester": "req", "taskToken": "tok-1",
                     "content_hash": "abc123"}, _ctx())
    assert r1["registered"] is True and r1["content_hash"] == "abc123"
    with pytest.raises(RuntimeError, match="duplicate submission"):
        rg.handler({"case_id": "HOU-Y", "requester": "req", "taskToken": "tok-2"}, _ctx())
    assert fake_ddb.items["HOU-Y"]["task_token"] == "tok-1", "first task token must not be overwritten"


def test_resolved_case_can_be_resubmitted(fake_ddb):
    rg = _load("signoff_register")
    rg.handler({"case_id": "HOU-Z", "requester": "req", "taskToken": "tok-1"}, _ctx())
    fake_ddb.items["HOU-Z"]["status"] = "APPROVED"     # first request resolved out-of-band
    r = rg.handler({"case_id": "HOU-Z", "requester": "req", "taskToken": "tok-2"}, _ctx())
    assert r["registered"] is True                     # non-PENDING prior record may be superseded
