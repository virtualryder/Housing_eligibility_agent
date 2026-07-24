"""P0-5 / P0-2 / P0-6 / P0-7 / P0-12 — the CDK stacks synthesize and carry the controls.

Uses aws_cdk.assertions (pure Python; no CDK CLI, no AWS). Skipped automatically when aws-cdk-lib is
not installed (CI installs it)."""
import json
import os
import pathlib
import sys

import pytest

aws_cdk = pytest.importorskip("aws_cdk")
from aws_cdk.assertions import Template, Match  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cdk"))

from app import stage_lambda_bundle  # noqa: E402
from housing_stacks.data_stack import DataStack  # noqa: E402
from housing_stacks.compute_stack import ComputeStack  # noqa: E402
from housing_stacks.workflow_stack import WorkflowStack  # noqa: E402
from housing_stacks.identity_stack import IdentityStack  # noqa: E402


def _stacks(profile="sandbox-demo", kms="aws-managed"):
    app = aws_cdk.App()
    asset = stage_lambda_bundle()
    data = DataStack(app, "d", prefix="hou-test", retention_profile=profile, kms_mode=kms)
    compute = ComputeStack(app, "c", prefix="hou-test", asset_dir=asset, data=data)
    workflow = WorkflowStack(app, "w", prefix="hou-test", compute=compute, data=data)
    identity = IdentityStack(app, "i", prefix="hou-test")
    return data, compute, workflow, identity


DATA, COMPUTE, WORKFLOW, IDENTITY = _stacks()
T_DATA, T_COMPUTE = Template.from_stack(DATA), Template.from_stack(COMPUTE)
T_WORKFLOW, T_IDENTITY = Template.from_stack(WORKFLOW), Template.from_stack(IDENTITY)


# ── data: retention profiles (P0-12) + sanitized store (P0-1) ────────────────

def test_worm_bucket_object_lock_default_profile():
    T_DATA.has_resource_properties("AWS::S3::Bucket", Match.object_like({
        "ObjectLockEnabled": True,
        "ObjectLockConfiguration": Match.object_like({
            "Rule": {"DefaultRetention": {"Mode": "GOVERNANCE", "Days": 1}}}),
    }))


def test_production_profile_is_compliance_mode():
    d, *_ = _stacks(profile="production-reference")
    Template.from_stack(d).has_resource_properties("AWS::S3::Bucket", Match.object_like({
        "ObjectLockConfiguration": Match.object_like({
            "Rule": {"DefaultRetention": {"Mode": "COMPLIANCE", "Days": 2555}}}),
    }))


def test_unknown_profile_refused():
    with pytest.raises(ValueError):
        _stacks(profile="whatever")


def test_sanitized_artifacts_table_with_ttl():
    T_DATA.has_resource_properties("AWS::DynamoDB::Table", Match.object_like({
        "TableName": "hou-test-sanitized-artifacts",
        "TimeToLiveSpecification": {"AttributeName": "expires_at", "Enabled": True},
    }))


def test_audit_ledger_retained_with_pitr():
    T_DATA.has_resource("AWS::DynamoDB::Table", Match.object_like({
        "DeletionPolicy": "Retain",
        "Properties": Match.object_like({
            "TableName": "hou-test-audit-ledger",
            "PointInTimeRecoverySpecification": {"PointInTimeRecoveryEnabled": True}})}))


# ── compute: explicit IAM (P0-5) + tamper deny + exact-ARN outputs (P0-7) ────

def test_audit_writer_has_explicit_tamper_deny():
    tpl = json.dumps(T_COMPUTE.to_json())
    assert "s3:BypassGovernanceRetention" in tpl and '"Effect": "Deny"' in tpl.replace("'", '"')


def test_exact_arn_outputs_exist():
    outs = T_COMPUTE.to_json().get("Outputs", {})
    for k in ("MaskArn", "AssessArn", "WriteAuditArn", "GuardsArn"):
        assert k in outs, f"exact-ARN output {k} missing (P0-7)"


# ── workflow: deterministic controller shape (P0-2) ──────────────────────────

def _controller_definition():
    """Reassemble the state-machine DefinitionString (an Fn::Join of literals + refs) into JSON."""
    tpl = T_WORKFLOW.to_json()
    for r in tpl["Resources"].values():
        if r["Type"] == "AWS::StepFunctions::StateMachine":
            parts = r["Properties"]["DefinitionString"]["Fn::Join"][1]
            return json.loads("".join(p if isinstance(p, str) else "ARN" for p in parts))
    raise AssertionError("no state machine in workflow stack")


def test_controller_pipeline_order_and_fail_closed_choices():
    doc = _controller_definition()
    # WALK the actual transitions from StartAt along the happy path (a Choice's first `when`).
    state, visited = doc["StartAt"], []
    while state and len(visited) < 40:
        visited.append(state)
        st = doc["States"][state]
        if st["Type"] == "Choice":
            state = st["Choices"][0]["Next"]
        else:
            state = st.get("Next")
    expected = ["Extract", "GuardExtracted", "ExtractedOk",
                "LookupIncomeLimit", "GuardAuthoritative", "AuthoritativeOk",
                "MaskPii", "GuardDeidentified", "DeidentifiedOk",
                "AssessRules", "GuardRulesExecuted", "RulesOk",
                "DraftNotice", "AuditIntent", "HumanSignoff", "Finalize", "Committed"]
    assert visited == expected, f"happy path deviates from the regulated sequence: {visited}"
    # every guard Choice fails closed to ManualReview
    for choice in ("ExtractedOk", "AuthoritativeOk", "DeidentifiedOk", "RulesOk"):
        assert doc["States"][choice]["Default"] == "ManualReview"
    # the human gate is a real waitForTaskToken pause
    assert "waitForTaskToken" in doc["States"]["HumanSignoff"]["Resource"]


# ── identity: no users, no passwords (P0-6) ──────────────────────────────────

def test_identity_creates_no_users_and_no_passwords():
    tpl = T_IDENTITY.to_json()
    types = [r["Type"] for r in tpl.get("Resources", {}).values()]
    assert "AWS::Cognito::UserPoolUser" not in types
    assert "ChangeMe" not in json.dumps(tpl)


def test_no_default_password_anywhere_in_any_template():
    for t in (T_DATA, T_COMPUTE, T_WORKFLOW, T_IDENTITY):
        assert "ChangeMe" not in json.dumps(t.to_json())


# ── Review-2: secrets are Secrets Manager resources, never plaintext env ─────

def test_signing_and_hud_secrets_provisioned_and_no_plaintext():
    tpl = T_COMPUTE.to_json()
    types = [r["Type"] for r in tpl.get("Resources", {}).values()]
    assert types.count("AWS::SecretsManager::Secret") >= 2   # signing + HUD token
    s = json.dumps(tpl)
    assert "PROVENANCE_SECRET_ARN" in s and "HUD_API_TOKEN_ARN" in s
    assert '"PROVENANCE_SECRET"' not in s, "plaintext signing secret must not appear in the template"


# ── GA-6: observability stack — alarms + dashboard exist and page via SNS ────

def test_observability_stack_alarms_and_dashboard():
    from housing_stacks.observability_stack import ObservabilityStack
    app = aws_cdk.App()
    asset = stage_lambda_bundle()
    data = DataStack(app, "od", prefix="hou-obs", retention_profile="sandbox-demo")
    compute = ComputeStack(app, "oc", prefix="hou-obs", asset_dir=asset, data=data)
    workflow = WorkflowStack(app, "ow", prefix="hou-obs", compute=compute, data=data)
    obs = ObservabilityStack(app, "oo", prefix="hou-obs", compute=compute, workflow=workflow)
    tpl = Template.from_stack(obs)
    types = [r["Type"] for r in tpl.to_json().get("Resources", {}).values()]
    assert types.count("AWS::CloudWatch::Alarm") >= 8       # 3 workflow + 5 lambda-error alarms
    assert "AWS::CloudWatch::Dashboard" in types
    assert "AWS::SNS::Topic" in types
    # every alarm pages the ops topic
    s = json.dumps(tpl.to_json())
    assert s.count("AlarmActions") >= 8
