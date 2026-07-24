"""ComputeStack — the governed tool Lambdas with explicit least-privilege IAM (P0-5/P0-7).

One function per manifest tool target, from a single staged asset bundle (tools + shared controls).
IAM is explicit and minimal per function: the audit writer can only PutItem the ledger + PutObject the
vault (with an explicit Deny on mutation/bypass); mask_pii can only Comprehend-detect + write the
sanitized store; the assessor/guards only read the sanitized store; the drafter only invokes Bedrock.
Exact ARNs are exported — nothing downstream discovers by name (P0-7)."""
import aws_cdk as cdk
from aws_cdk import aws_iam as iam, aws_lambda as lambda_
from constructs import Construct

RUNTIME = lambda_.Runtime.PYTHON_3_12


class ComputeStack(cdk.Stack):
    def __init__(self, scope: Construct, cid: str, *, prefix: str, asset_dir: str, data,
                 provenance_secret: str = "", **kw):
        super().__init__(scope, cid, **kw)
        code = lambda_.Code.from_asset(asset_dir)
        common_env = {
            "AUDIT_TABLE": data.audit_table.table_name,
            "WORM_BUCKET": data.worm_bucket.bucket_name,
            "SANITIZED_TABLE": data.sanitized_table.table_name,
        }
        # Per-deploy signing secret binding mask_pii artifacts + HUD provenance (P0-1/P0-3-prov).
        # Sandbox/dev: context-supplied env var. Production posture (P1-2): Secrets Manager + rotation.
        if provenance_secret:
            common_env["PROVENANCE_SECRET"] = provenance_secret

        def fn(name, handler_module, env=None, timeout=30):
            f = lambda_.Function(
                self, name.replace("-", " ").title().replace(" ", ""),
                function_name=f"{prefix}-{name}", runtime=RUNTIME, code=code,
                handler=f"{handler_module}.handler",
                timeout=cdk.Duration.seconds(timeout), memory_size=256,
                environment={**common_env, **(env or {})},
            )
            return f

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

        for name, f in {
            "IntakeArn": self.intake, "LookupArn": self.lookup, "MaskArn": self.mask,
            "AssessArn": self.assess, "CoreArn": self.core, "WriteAuditArn": self.write_audit,
            "RequestSignoffArn": self.request_signoff, "GuardsArn": self.guards,
        }.items():
            cdk.CfnOutput(self, name, value=f.function_arn)   # exact ARNs (P0-7)
