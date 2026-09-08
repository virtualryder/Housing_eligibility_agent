"""ComputeStack — the governed tool Lambdas with explicit least-privilege IAM (P0-5/P0-7).

One function per manifest tool target, from a single staged asset bundle (tools + shared controls).
IAM is explicit and minimal per function: the audit writer can only PutItem the ledger + PutObject the
vault (with an explicit Deny on mutation/bypass); mask_pii can only Comprehend-detect + write the
sanitized store; the assessor/guards only read the sanitized store; the drafter only invokes Bedrock.
Exact ARNs are exported — nothing downstream discovers by name (P0-7)."""
import hashlib
import pathlib

import aws_cdk as cdk
from aws_cdk import (aws_ec2 as ec2, aws_iam as iam, aws_kms as kms, aws_lambda as lambda_,
                     aws_logs as logs, aws_secretsmanager as sm)
from constructs import Construct

# ---- #232: policy provenance in every audit record -----------------------------------------------
# governed_core.controls.evidence writes `policy_version`, `rule_version` and `deployment_version`
# into the hashed logical record of EVERY audit row, reading them from the environment and
# defaulting to the string "unset". Nothing in this CDK app set them, so every row written by a
# CDK-deployed Lambda recorded:
#
#     "policy_version": "unset", "rule_version": "unset"
#
# which is exactly what the 2026-09-02 111-gate evidence contains. The legacy shell path
# (lib/engine/deploy.sh) set the literal "v1" - a placeholder, not provenance: it does not change
# when the policies change, so it cannot answer the question the field exists for.
#
# That question is "which policy set decided this case?", and the only honest answer is derived from
# the artefacts actually deployed. These digests are CONTENT-ADDRESSED: they change exactly when the
# Cedar policies or the agent manifest change, and not otherwise.
def _digest_of(paths, label):
    """Stable short digest over a set of files, sorted by name.

    Content, not mtime; the filename is hashed too, so adding or renaming a policy changes the
    digest even when the bytes elsewhere are identical. Newlines are normalised so a CRLF checkout
    and an LF checkout of the same tree produce the SAME provenance - a version string that depends
    on which machine ran `cdk synth` is not provenance either.
    """
    h = hashlib.sha256()
    for p in sorted(paths, key=lambda q: q.name):
        h.update(p.name.encode("utf-8"))
        h.update(b"\0")
        h.update(p.read_bytes().replace(b"\r\n", b"\n"))
        h.update(b"\0")
    return "%s-%s" % (label, h.hexdigest()[:12])


def provenance_env(repo_root):
    """POLICY_VERSION / RULE_VERSION / DEPLOYMENT_VERSION for the tree being synthesized."""
    root = pathlib.Path(repo_root)
    cedar = sorted((root / "policies").glob("*.cedar"))
    manifests = sorted((root / "agents").glob("*/manifest.yaml"))
    try:
        release = (root / "RELEASE").read_text(encoding="utf-8").strip()
    except OSError:
        release = ""
    return {
        # The Cedar policy set the deployed engine authorizes against.
        "POLICY_VERSION": _digest_of(cedar, "cedar") if cedar else "no-policies",
        # The agent manifest: tool list, entitlements, guardrail and model pins - the rules the
        # workflow runs under that are not Cedar.
        "RULE_VERSION": _digest_of(manifests, "manifest") if manifests else "no-manifest",
        # The release this tree claims to be. An untagged working tree says so rather than "v1".
        "DEPLOYMENT_VERSION": release or "untagged-working-tree",
    }


RUNTIME = lambda_.Runtime.PYTHON_3_12


class ComputeStack(cdk.Stack):
    def __init__(self, scope: Construct, cid: str, *, prefix: str, asset_dir: str, data,
                 provenance_secret: str = "", network=None, tenant: str = "", **kw):
        super().__init__(scope, cid, **kw)
        code = lambda_.Code.from_asset(asset_dir)
        # Gate-B (customer-managed KMS): when the DataStack was deployed with kms=customer-managed,
        # the SAME CMK protects this stack's secrets, Lambda environment variables, and log groups —
        # one customer-controlled key over every place case data or key material can rest.
        # IMPORTED by ARN (not the concrete Key object): grants then land on the FUNCTION ROLES in
        # this stack instead of rewriting the key policy in the data stack, which would create a
        # cross-stack dependency cycle. Service principals that need the key policy itself (logs,
        # cloudwatch) are pre-authorized in the DataStack key policy.
        cmk = None
        if getattr(data, "cmk", None) is not None:
            cmk = kms.Key.from_key_arn(self, "DataCmk", data.cmk.key_arn)
        common_env = {
            # #232: content-addressed policy provenance, so every audit row can name the
            # Cedar set and manifest that were actually deployed instead of "unset".
            **provenance_env(pathlib.Path(__file__).resolve().parents[2]),
            "AUDIT_TABLE": data.audit_table.table_name,
            "WORM_BUCKET": data.worm_bucket.bucket_name,
            "SANITIZED_TABLE": data.sanitized_table.table_name,
            "PENDING_TABLE": data.pending_table.table_name,
            "CASE_TABLE": data.case_table.table_name,   # R3-2 pass-by-reference store
        }
        # Gate-B B5: the deployment's pinned tenant (one PHA per isolated deployment). Tenant identity
        # is DERIVED from this, never from any request body (lib/controls/tenancy.py).
        if tenant:
            common_env["TENANT_ID"] = tenant
        # Per-deploy signing secrets (P0-1/P0-3-prov + GA-2 key separation). DEFAULT (Review-2): a
        # generated AWS Secrets Manager secret PER TRUST DOMAIN, referenced by ARN — never plaintext in
        # the template. GA-2: the de-identification proof (mask_pii sanitized_ref) and the
        # authoritative-source proof (HUD limits) are signed with DIFFERENT keys, so neither minter can
        # forge the other's trust statement. A context-supplied plaintext secret remains available for
        # disposable sandbox validation ONLY (shared across domains — acceptable in a throwaway
        # sandbox, never in a pilot). HUD API token is a separate operator-filled secret.
        self.signing_secret_deid = None
        self.signing_secret_hud = None
        if provenance_secret:
            common_env["PROVENANCE_SECRET"] = provenance_secret   # sandbox-only path (shared)
        else:
            gen = sm.SecretStringGenerator(password_length=64, exclude_punctuation=True)
            self.signing_secret_deid = sm.Secret(
                self, "SigningSecretDeid", secret_name=f"{prefix}/provenance-signing-deid",
                description="GA-2 deid-domain HMAC key: signs mask_pii sanitized-artifact refs ONLY (rotate via new version; consumers re-read on cold start)",
                generate_secret_string=gen, encryption_key=cmk)
            self.signing_secret_hud = sm.Secret(
                self, "SigningSecretHud", secret_name=f"{prefix}/provenance-signing-hud",
                description="GA-2 HUD-domain HMAC key: signs authoritative income-limit provenance ONLY (rotate via new version; consumers re-read on cold start)",
                generate_secret_string=gen, encryption_key=cmk)
            common_env["PROVENANCE_SECRET_ARN_DEID"] = self.signing_secret_deid.secret_arn
            common_env["PROVENANCE_SECRET_ARN_HUD"] = self.signing_secret_hud.secret_arn
        self.hud_token_secret = sm.Secret(
            self, "HudTokenSecret", secret_name=f"{prefix}/hud-api-token",
            description="HUD USER API bearer token (operator fills value; register at huduser.gov)",
            encryption_key=cmk,
        )

        def fn(name, handler_module, env=None, timeout=30):
            # Gate-B: with a CMK, each function gets an EXPLICIT CMK-encrypted log group (Lambda's
            # implicit log groups are AES-256 only) and CMK-encrypted environment variables.
            log_group = None
            if cmk is not None:
                log_group = logs.LogGroup(
                    self, name.replace("-", " ").title().replace(" ", "") + "Logs",
                    log_group_name=f"/aws/lambda/{prefix}-{name}",
                    encryption_key=cmk, retention=logs.RetentionDays.ONE_YEAR,
                    removal_policy=cdk.RemovalPolicy.DESTROY)
            # Gate-B (B1): with a NetworkStack, every governed tool runs in the private app subnets
            # behind the egress firewall — no direct internet path exists from any tool.
            net = {}
            if network is not None:
                net = dict(vpc=network.vpc,
                           vpc_subnets=ec2.SubnetSelection(subnet_group_name="app"),
                           security_groups=[network.lambda_sg])
            f = lambda_.Function(
                self, name.replace("-", " ").title().replace(" ", ""),
                function_name=f"{prefix}-{name}", runtime=RUNTIME, code=code,
                handler=f"{handler_module}.handler",
                timeout=cdk.Duration.seconds(timeout), memory_size=256,
                environment={**common_env, **(env or {})},
                environment_encryption=cmk, log_group=log_group, **net,
            )
            if cmk is not None:
                cmk.grant_decrypt(f)   # runtime decrypt of CMK-encrypted env vars (role policy)
            return f

        self.ingest = fn("ingest-case", "ingest_case")   # R3-2: the only door for raw content
        self.intake = fn("intake-application", "intake_application")
        self.lookup = fn("lookup-income-limit", "lookup_income_limit")
        self.mask = fn("mask-pii", "mask_pii")
        self.assess = fn("assess-eligibility", "assess_housing_eligibility")
        self.recertify = fn("recertify", "recertify")
        self.overpayment = fn("detect-overpayment", "overpayment")
        self.core = fn("core-tools", "housing_core", timeout=60)
        self.write_audit = fn("write-audit", "write_audit")
        self.request_signoff = fn("request-signoff", "request_signoff")
        self.signoff_register = fn("signoff-register", "signoff_register")
        self.finalize = fn("finalize", "finalize_signoff")
        self.guards = fn("workflow-guards", "workflow_guards")

        # ── explicit least-privilege wiring ──────────────────────────────────
        # Secrets (Review-2 + GA-2): each domain key readable ONLY by that domain's signer + verifiers.
        # DEID key: mask_pii signs; the sanitized-ref verifiers verify. HUD key: lookup signs; the
        # provenance verifiers (assess, guards) verify. The lookup CANNOT read the deid key and the
        # masker CANNOT read the HUD key — cross-domain forgery is an IAM impossibility, not just a
        # code convention. HUD API token readable ONLY by the lookup. No plaintext in the template.
        if self.signing_secret_deid is not None:
            for f in (self.mask, self.assess, self.recertify, self.overpayment,
                      self.core, self.guards):
                self.signing_secret_deid.grant_read(f)
        if self.signing_secret_hud is not None:
            for f in (self.lookup, self.assess, self.guards):
                self.signing_secret_hud.grant_read(f)
        self.hud_token_secret.grant_read(self.lookup)
        # R3-2 case store: ingest WRITES raw content; intake + mask READ it (the only two consumers
        # of raw text); the drafter WRITES the notice. Nothing else touches raw content.
        data.case_table.grant(self.ingest, "dynamodb:PutItem")
        data.case_table.grant(self.intake, "dynamodb:GetItem")
        data.case_table.grant(self.mask, "dynamodb:GetItem")
        data.case_table.grant(self.core, "dynamodb:PutItem")
        data.pending_table.grant(self.signoff_register, "dynamodb:PutItem")
        data.pending_table.grant_read_write_data(self.finalize)   # marker read path uses audit table; pending read for ops
        self.lookup.add_environment("HUD_API_TOKEN_ARN", self.hud_token_secret.secret_arn)
        # masking: detect PII + write the sanitized store (PutItem only)
        self.mask.add_to_role_policy(iam.PolicyStatement(
            actions=["comprehend:DetectPiiEntities"], resources=["*"]))
        data.sanitized_table.grant(self.mask, "dynamodb:PutItem")
        # sanitized-store readers (content channel)
        for f in (self.core, self.guards):
            data.sanitized_table.grant(f, "dynamodb:GetItem")
        # drafter: Bedrock only (scoped by inference-profile at deploy via env MODEL_ARNS if narrowed)
        self.core.add_to_role_policy(iam.PolicyStatement(
            actions=["bedrock:InvokeModel"], resources=["*"]))
        # audit writer: append-only + WORM put, with explicit tamper Deny
        data.audit_table.grant(self.write_audit, "dynamodb:PutItem",
                               "dynamodb:GetItem", "dynamodb:TransactWriteItems")
        data.worm_bucket.grant_put(self.write_audit)
        self.write_audit.add_to_role_policy(iam.PolicyStatement(
            effect=iam.Effect.DENY,
            actions=["dynamodb:DeleteItem", "dynamodb:UpdateItem",
                     "s3:DeleteObject", "s3:DeleteObjectVersion",
                     "s3:PutObjectRetention", "s3:PutObjectLegalHold",
                     "s3:BypassGovernanceRetention"],
            resources=[data.audit_table.table_arn,
                       data.worm_bucket.bucket_arn, f"{data.worm_bucket.bucket_arn}/*"]))
        # request_signoff also records INTENT evidence + starts the sign-off machine (arn via env at wire-up)
        data.audit_table.grant(self.request_signoff, "dynamodb:PutItem",
                               "dynamodb:GetItem", "dynamodb:TransactWriteItems")
        data.worm_bucket.grant_put(self.request_signoff)
        # finalize: writes the COMMITTED evidence + the exactly-once FINAL# marker (conditional put)
        data.audit_table.grant(self.finalize, "dynamodb:PutItem",
                               "dynamodb:GetItem", "dynamodb:TransactWriteItems")
        data.worm_bucket.grant_put(self.finalize)

        for name, f in {
            "IngestArn": self.ingest,
            "IntakeArn": self.intake, "LookupArn": self.lookup, "MaskArn": self.mask,
            "AssessArn": self.assess, "CoreArn": self.core, "WriteAuditArn": self.write_audit,
            "RequestSignoffArn": self.request_signoff, "GuardsArn": self.guards,
        }.items():
            cdk.CfnOutput(self, name, value=f.function_arn)   # exact ARNs (P0-7)
