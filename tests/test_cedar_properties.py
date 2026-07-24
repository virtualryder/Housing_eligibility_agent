"""GA-9 (Review-2) — Cedar authorization property tests.

Properties proven against the manifest + the shipped .cedar policies:
  P1  Every MCP tool has a DECLARED authorization expectation — a newly added tool FAILS CI until its
      posture is explicitly decided (deny-by-default at the process level, not just the engine level).
  P2  The only permit is the specialist group grant (deny-by-default: no other permit exists), and it
      is gated on the cognito:groups tag.
  P3  Every consequential/human-only tool named in an expectation has a forbid policy naming its
      action; forbid-wins semantics are documented in the policy pack.
  P4  Every masking-gated tool's forbid requires the de-identification claim (`unless ... deidentified`).
  P5  The agent-facing manifest HIDES the human-only tools from the workflow steps (defense in depth).
"""
import pathlib
import re

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
POLICIES = ROOT / "policies"
MANIFEST = (ROOT / "agents" / "housing-assistance" / "manifest.yaml").read_text(encoding="utf-8")
EXPECT = yaml.safe_load((ROOT / "tests" / "authz_expectations.yaml").read_text(encoding="utf-8"))["tools"]


def _manifest_tools():
    return set(re.findall(r"^\s+- name:\s+(\w+)", MANIFEST, flags=re.M))


def _policy(name):
    p = POLICIES / f"{name}.cedar"
    assert p.exists(), f"expected policy file missing: {name}.cedar"
    return p.read_text(encoding="utf-8")


# P1 — new-tool-fails-CI gate
def test_every_tool_has_a_declared_authorization_expectation():
    tools = _manifest_tools()
    missing = sorted(tools - set(EXPECT))
    assert not missing, (
        f"tools without a declared authorization expectation (add them to tests/authz_expectations.yaml "
        f"with an explicit posture before this build can go green): {missing}")
    stale = sorted(set(EXPECT) - tools)
    assert not stale, f"expectations for tools no longer in the manifest: {stale}"


# P2 — deny-by-default: exactly one permit, group-gated
def test_single_group_gated_permit_and_no_other_permits():
    permits = [p for p in POLICIES.glob("*.cedar") if re.search(r"^permit\(", p.read_text(encoding="utf-8"), flags=re.M)]
    assert [p.name for p in permits] == ["housing_specialist_permit.cedar"], \
        f"deny-by-default violated: unexpected permit policies {[p.name for p in permits]}"
    body = _policy("housing_specialist_permit")
    assert 'hasTag("cognito:groups")' in body and "housing_specialist" in body


# P3 — every forbidden/human-only tool has a forbid naming its action
def test_forbidden_tools_have_forbid_policies_naming_the_action():
    for tool, spec in EXPECT.items():
        if "forbid_policy" not in spec:
            continue
        body = _policy(spec["forbid_policy"])
        assert re.search(r"^forbid\(", body, flags=re.M), f"{spec['forbid_policy']} is not a forbid"
        assert tool in body, f"{spec['forbid_policy']}.cedar does not name action {tool}"


# P4 — masking-gated forbids demand the de-identification claim
def test_masking_forbids_require_deidentified_claim():
    for tool, spec in EXPECT.items():
        if spec["access"] != "specialist+masking-forbid":
            continue
        body = _policy(spec["forbid_policy"])
        assert "unless" in body and "deidentified" in body, \
            f"{spec['forbid_policy']} must forbid {tool} unless the de-identification claim is present"


# P4b — human-only forbids are unconditional (no unless escape)
def test_human_only_forbids_are_unconditional():
    for tool, spec in EXPECT.items():
        if spec["access"] != "forbidden-to-all":
            continue
        body = _policy(spec["forbid_policy"])
        assert "unless" not in body, f"{spec['forbid_policy']} must be an unconditional forbid"


# P5 — human-only tools are hidden from the agent's workflow instructions
def test_human_only_tools_hidden_from_workflow_steps():
    steps = MANIFEST.split("workflow:")[1]
    for tool, spec in EXPECT.items():
        if spec["access"] == "forbidden-to-all":
            assert f"{tool} -" not in steps, f"human-only tool {tool} must not appear as a workflow step"
