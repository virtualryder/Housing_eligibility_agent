"""Gate-B B4 — PII telemetry-leak canary: the offline logic (marker, sweep, verdict).

The live sweeps are thin boto3 wrappers exercised in the Gate-B validation run; everything that
decides PASS/FAIL is proven here."""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import pii_canary as pc  # noqa: E402


def test_marker_unique_and_collision_proof():
    m1, m2 = pc.make_marker(), pc.make_marker()
    assert m1 != m2
    assert m1.startswith("CANARY-") and m1.endswith("-TELEMETRYPROBE")
    assert len(m1) > 25   # cannot occur naturally in a log line


def test_canary_case_carries_marker_in_all_three_pii_shapes():
    m = pc.make_marker()
    case = pc.build_canary_case(m)
    text = case["application_text"]
    assert text.count(m) >= 2                    # name + address
    assert "900-00-" in text                     # SSN-shaped (reserved range, never real)
    assert case["canary"] is True


def test_sweep_counts_case_insensitively_and_handles_empty():
    m = pc.make_marker()
    assert pc.sweep_text(f"a {m} b {m.lower()} c", m) == 2
    assert pc.sweep_text("", m) == 0
    assert pc.sweep_text(None, m) == 0
    assert pc.sweep_text("clean log line", m) == 0


def test_verdict_fails_on_any_must_be_clean_hit():
    assert pc.verdict({"cloudwatch_logs": 1, "stepfunctions_history": 0,
                       "xray": 0, "dlq": 0})["verdict"] == "FAIL"
    assert pc.verdict({"cloudwatch_logs": 0, "xray": 3, "dlq": 0})["verdict"] == "FAIL"
    assert pc.verdict({"dlq": 1})["verdict"] == "FAIL"


def test_verdict_reports_sfn_history_as_finding_not_pass_free():
    v = pc.verdict({"cloudwatch_logs": 0, "stepfunctions_history": 4, "xray": 0, "dlq": 0})
    assert v["verdict"] == "PASS"                        # pilot verdict: must-be-clean are clean
    assert v["known_sensitive_findings"] == {"stepfunctions_history": 4}
    assert "pass-by-reference" in v["note"]              # remediation named, not hidden


def test_strict_verdict_is_the_gate_b_exit():
    assert pc.strict_verdict({"stepfunctions_history": 1})["verdict"] == "FAIL"
    assert pc.strict_verdict({"cloudwatch_logs": 0, "stepfunctions_history": 0,
                              "xray": 0, "dlq": 0})["verdict"] == "PASS"


def test_all_clean_passes_both_modes():
    hits = {d: 0 for d in ("cloudwatch_logs", "stepfunctions_history", "xray", "dlq")}
    assert pc.verdict(hits)["verdict"] == "PASS"
    assert pc.strict_verdict(hits)["verdict"] == "PASS"
