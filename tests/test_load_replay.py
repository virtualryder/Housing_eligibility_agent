"""Gate-B B6 — load/replay harness: the verdict logic (offline)."""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import load_replay_test as lr  # noqa: E402


def test_load_verdict_passes_only_on_legal_terminals():
    ok = lr.load_verdict(["SUCCEEDED"] * 25, [30.0] * 25)
    assert ok["verdict"] == "PASS" and ok["executions"] == 25
    bad = lr.load_verdict(["SUCCEEDED"] * 24 + ["FAILED"], [30.0] * 25)
    assert bad["verdict"] == "FAIL" and bad["illegal_terminal"] == {"FAILED": 1}
    assert lr.load_verdict([], [])["verdict"] == "FAIL"          # zero executions is not a pass
    assert lr.load_verdict(["TIMED_OUT"], [1.0])["verdict"] == "FAIL"


def test_percentiles():
    assert lr.percentile([1, 2, 3, 4, 5], 50) == 3
    assert lr.percentile([1, 2, 3, 4, 100], 95) == 100
    assert lr.percentile([], 95) is None


def test_replay_verdict_requires_exactly_once():
    assert lr.replay_verdict(1, 1, 9, 10)["verdict"] == "PASS"
    assert lr.replay_verdict(2, 1, 8, 10)["verdict"] == "FAIL"   # double commit
    assert lr.replay_verdict(1, 2, 9, 10)["verdict"] == "FAIL"   # duplicate FINAL# marker
    assert lr.replay_verdict(0, 0, 10, 10)["verdict"] == "FAIL"  # nothing committed at all
    assert lr.replay_verdict(1, 1, 5, 10)["verdict"] == "FAIL"   # unaccounted attempts
