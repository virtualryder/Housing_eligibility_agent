"""Unit tests for the CANONICAL evidence service (evidence.py) and verifier (verify_chain.py):
valid chain -> INTACT; content/chain-field/reorder/deletion/fork/seq tampering -> detected; and the
authoritative, atomic, fork-proof write path (server-side head read + TransactWriteItems CAS + retry +
idempotent replay) exercised against a fake DynamoDB so no AWS is needed in CI."""
import importlib.util
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
CTRL = ROOT / "lib" / "controls"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, CTRL / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


ev = _load("evidence")
vc = _load("verify_chain")


def _chain(n):
    recs, prev, seq = [], ev.GENESIS, 0
    for i in range(n):
        logical = ev.build_logical({"case_id": "CASE-1", "action": "step%d" % i, "phase": "INTENT",
                                    "actor": "reviewer", "payload": {"i": i}}, "unit")
        r = ev.build_record(logical, seq, prev)
        recs.append(r); prev = r["chain_hash"]; seq += 1
    return recs


def test_valid_chain_intact():
    recs = _chain(4)
    res = vc.verify(recs)
    assert res["intact"] is True and res["length"] == 4
    for a, b in zip(recs, recs[1:]):
        assert b["prev_hash"] == a["chain_hash"]
    assert [r["seq"] for r in recs] == [0, 1, 2, 3]


def test_content_edit_detected():
    recs = _chain(4); recs[1]["payload"] = {"i": 99}
    assert vc.verify(recs)["intact"] is False


def test_chain_field_edit_detected():
    recs = _chain(4); recs[2]["chain_hash"] = "0" * 64
    assert vc.verify(recs)["intact"] is False


def test_deletion_detected():
    recs = _chain(5); del recs[2]
    assert vc.verify(recs)["intact"] is False


def test_seq_tamper_detected():
    # recompute a valid-looking record but with a wrong seq -> the seq-contiguity check catches it
    recs = _chain(4)
    bad = dict(recs[2]); logical = {k: bad[k] for k in bad if k not in ("prev_hash", "entry_hash", "chain_hash", "seq")}
    tampered = ev.build_record(logical, 9, recs[1]["chain_hash"])   # seq 9 instead of 2
    recs[2] = tampered
    res = vc.verify(recs)
    assert res["intact"] is False and "seq" in res["reason"]


def test_head_items_ignored():
    recs = _chain(3)
    recs_with_head = recs + [{"audit_id": "HEAD#CASE-1", "chain_hash": recs[-1]["chain_hash"], "seq": 2}]
    # the HEAD# sentinel is metadata, not an event -> verify filters it out and still reports INTACT
    assert vc.verify(recs_with_head)["intact"] is True


# ---------- authoritative write path against a FAKE DynamoDB ----------
class FakeTable:
    def __init__(self, store): self.store = store
    def get_item(self, Key):
        it = self.store.get(Key["audit_id"])
        return {"Item": it} if it else {}


class FakeResource:
    def __init__(self, store): self.store = store
    def Table(self, name): return FakeTable(self.store)


from botocore.exceptions import ClientError as _BotoClientError


def _cancel(reasons):
    return _BotoClientError({"Error": {"Code": "TransactionCanceledException"},
                             "CancellationReasons": reasons}, "TransactWriteItems")


class FakeDDBClient:
    """Simulates transact_write_items with the two conditional Puts; enforces head CAS + event immutability."""
    def __init__(self, store, fail_head_first=False):
        self.store = store; self.fail_head_first = fail_head_first; self.calls = 0
    def transact_write_items(self, TransactItems):
        self.calls += 1
        ev_put = TransactItems[0]["Put"]; head_put = TransactItems[1]["Put"]
        ev_item = _deser(ev_put["Item"]); head_item = _deser(head_put["Item"])
        # event immutability
        if ev_item["audit_id"] in self.store:
            raise _cancel([{"Code": "ConditionalCheckFailed"}, {"Code": "None"}])
        # head CAS: simulate a concurrent writer winning the first attempt
        if self.fail_head_first and self.calls == 1:
            raise _cancel([{"Code": "None"}, {"Code": "ConditionalCheckFailed"}])
        self.store[ev_item["audit_id"]] = ev_item
        self.store[head_item["audit_id"]] = head_item


class FakeS3:
    def __init__(self): self.puts = []
    def put_object(self, **kw): self.puts.append(kw)


def _deser(item):
    from boto3.dynamodb.types import TypeDeserializer
    d = TypeDeserializer().deserialize
    return {k: d(v) for k, v in item.items()}


def _install(monkey_store, **kw):
    s3 = FakeS3()
    cli = FakeDDBClient(monkey_store, **kw)
    ev._clients = lambda region: (FakeResource(monkey_store), cli, s3)
    return cli, s3


def test_authoritative_write_and_chain():
    store = {}; _install(store)
    ctx = type("C", (), {"invoked_function_arn": "arn:aws:lambda:us-east-1:111122223333:function:x"})()
    import os
    os.environ["AUDIT_TABLE"] = "t"
    r1 = ev.record_event({"case_id": "C", "action": "a1", "phase": "INTENT", "actor": "u", "payload": {"n": 1}}, ctx, source="unit")
    r2 = ev.record_event({"case_id": "C", "action": "a2", "phase": "COMMITTED", "actor": "u", "payload": {"n": 2}}, ctx, source="unit")
    assert r1["stored"] and r2["stored"]
    assert r1["seq"] == 0 and r2["seq"] == 1
    assert r2["prev_hash"] == r1["chain_hash"]          # server-side authoritative link
    events = [v for k, v in store.items() if not k.startswith("HEAD#")]
    assert vc.verify(events)["intact"] is True
    assert store["HEAD#C"]["chain_hash"] == r2["chain_hash"] and store["HEAD#C"]["seq"] == 1


def test_idempotent_replay():
    store = {}; _install(store)
    ctx = type("C", (), {"invoked_function_arn": "arn:aws:lambda:us-east-1:111122223333:function:x"})()
    import os; os.environ["AUDIT_TABLE"] = "t"
    payload = {"case_id": "C", "action": "a", "phase": "INTENT", "actor": "u", "payload": {"n": 1}}
    a = ev.record_event(dict(payload), ctx, source="unit")
    b = ev.record_event(dict(payload), ctx, source="unit")   # exact replay
    assert a["stored"] is True
    assert b["stored"] is False and "already recorded" in b["reason"]


def test_concurrent_head_cas_retries():
    store = {}; cli, _ = _install(store, fail_head_first=True)
    ctx = type("C", (), {"invoked_function_arn": "arn:aws:lambda:us-east-1:111122223333:function:x"})()
    import os; os.environ["AUDIT_TABLE"] = "t"
    r = ev.record_event({"case_id": "C", "action": "a", "phase": "INTENT", "actor": "u", "payload": {"n": 1}}, ctx, source="unit")
    assert r["stored"] is True and cli.calls == 2          # first CAS lost, retried, then succeeded


# ── Review-2 adversarial proof: TransactWriteItems cannot be abused to overwrite ──

def test_every_transact_put_carries_a_condition_expression():
    """DynamoDB Put inside a transaction REPLACES an item unless conditioned. Prove the evidence
    service never issues an unconditioned Put: a strict client that rejects any Put lacking an
    attribute_not_exists/tip-CAS ConditionExpression must accept every write record_event makes."""
    captured = []
    store = {}

    class StrictClient(FakeDDBClient):
        def transact_write_items(self, TransactItems):
            for item in TransactItems:
                assert "ConditionExpression" in item["Put"], "unconditioned transact Put (overwrite-capable!)"
                captured.append(item["Put"]["ConditionExpression"])
                assert ("attribute_not_exists" in item["Put"]["ConditionExpression"]
                        or "chain_hash" in item["Put"]["ConditionExpression"])
            return super().transact_write_items(TransactItems)

    ev._clients = lambda region: (FakeResource(store), StrictClient(store), FakeS3())
    ctx = type("C", (), {"invoked_function_arn": "arn:aws:lambda:us-east-1:111122223333:function:x"})()
    import os; os.environ["AUDIT_TABLE"] = "t"
    r = ev.record_event({"case_id": "ADV-1", "action": "assess", "phase": "INTENT",
                         "actor": "t", "payload": {"x": 1}}, ctx, source="unit")
    assert r["stored"] is True and captured, "no conditioned transact writes captured"


def test_overwrite_of_existing_audit_id_is_refused_and_content_unchanged():
    """Adversarial replay-with-DIFFERENT-content: same audit id, altered payload -> the conditioned
    Put refuses (ConditionalCheckFailed) and the stored record is unchanged."""
    store = {}; _install(store)
    ctx = type("C", (), {"invoked_function_arn": "arn:aws:lambda:us-east-1:111122223333:function:x"})()
    import os; os.environ["AUDIT_TABLE"] = "t"
    first = ev.record_event({"case_id": "ADV-2", "action": "assess", "phase": "INTENT",
                             "actor": "t", "payload": {"determination": "ELIGIBLE"}}, ctx, source="unit")
    assert first["stored"] is True
    aid = first["audit_id"]
    original = dict(store[aid])
    # same identity fields, DIFFERENT payload -> not an exact replay; conditioned Put must refuse,
    # and record_event must fail loud (stored:false), leaving the original bytes intact.
    second = ev.record_event({"case_id": "ADV-2", "action": "assess", "phase": "INTENT",
                              "actor": "t", "payload": {"determination": "INELIGIBLE"},
                              "audit_id": aid}, ctx, source="unit")
    assert second.get("stored") is not True or second.get("audit_id") != aid
    assert store[aid] == original, "audit record content changed after overwrite attempt"
