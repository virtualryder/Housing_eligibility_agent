"""GA-5 — exactly-once finalization + duplicate-submission protection. Offline (fake DynamoDB)."""
import importlib.util
import os
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib" / "controls"))
os.environ.setdefault("PROVENANCE_SECRET", "p0-unit-provenance-secret")
os.environ.setdefault("AUDIT_TABLE", "t")


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "lib" / "controls" / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


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
    fz = _load("finalize_signoff")
    recorded = []
    monkeypatch.setattr(fz.evidence, "record_event",
                        lambda ev, ctx, source=None: recorded.append(ev) or
                        {"stored": True, "audit_id": "A1", "chain_hash": "h", "seq": 0, "worm": True})
    r1 = fz.handler({"case_id": "HOU-X", "requester": "req", "approver": "appr-1"}, _ctx())
    assert r1["committed"] is True and not r1.get("idempotent")
    # retried Lambda (same approver) -> idempotent, NO second COMMITTED record
    r2 = fz.handler({"case_id": "HOU-X", "requester": "req", "approver": "appr-1"}, _ctx())
    assert r2["committed"] is True and r2["idempotent"] is True
    assert r2["submission_id"] == r1["submission_id"]
    # a DIFFERENT approval path (different approver) still cannot double-commit
    r3 = fz.handler({"case_id": "HOU-X", "requester": "req", "approver": "appr-2"}, _ctx())
    assert r3["committed"] is True and r3["idempotent"] is True
    assert r3["submission_id"] == r1["submission_id"]   # ORIGINAL submission returned
    assert len(recorded) == 1, "exactly one COMMITTED evidence record"


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
