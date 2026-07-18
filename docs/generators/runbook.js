const G = require("./guides.js");
const { H1, H2, H3, P, bold, code, bullet, num, codeBlock, callout, table, spacer, coverAndToc, makeDoc, Packer } = G;

const cover = coverAndToc(
  ["Housing Eligibility Agent", "on Amazon Bedrock AgentCore"],
  "Solution Architect Deployment Runbook",
  "Step-by-step deployment of the governed Housing Choice Voucher (Section 8) / public-housing eligibility accelerator into an AWS account — identity, governance spine, tools, the live HUD income-limit integration, and the Runtime agent — from one manifest. Region: us-east-1. Every command in this runbook was run end to end to stand the agent up and prove 30/30 in ENFORCE. Accelerator reference; not production-certified. Version 1.1 · 2026.",
  ["1. Overview", "2. Prerequisites", "3. What gets deployed", "4. Deployment procedure", "5. Configuration reference", "6. Validation checklist", "7. Teardown", "8. Windows / Git-Bash operational notes"]
);

const body = [
  H1("1. Overview"),
  P("This runbook stands up the governed Housing Choice Voucher / public-housing eligibility agent in an AWS account. The agent is defined by a single manifest and produced from the reusable governed-hero-agent template; the deployment has three lifecycles that are managed independently:"),
  bullet([bold("Identity stack "), "— a stable Amazon Cognito user pool, app client, and test users. Long-lived; created (or reused) by the spine deploy and not torn down with it."]),
  bullet([bold("Governance spine "), "— the Cedar policy engine, AgentCore Gateway, tool Lambdas, Bedrock Guardrail, WORM audit stores, and the Step Functions human sign-off gate. Reproducible; stood up and torn down as a unit."]),
  bullet([bold("Runtime agent "), "— the generic Strands agent, containerized (ARM64 via CodeBuild) and deployed to AgentCore Runtime with a Cognito JWT inbound authorizer; its workflow prompt is rendered from the manifest."]),
  P(["The whole spine deploys with ", code("deploy.sh"), " (it also creates the stable identity), proves itself with a 30-check governance demo, and tears down with zero residual. Everything is driven from ", code("agents/housing-assistance/manifest.yaml"), " — the engine, control library, and runtime are shared across agents."]),
  callout("Honesty boundary", [["This is an accelerator, not a production-certified system. Program participation, IdP federation, validated connectors to the PHA system of record (EIV / PIC / HMIS), the authoritative admission rules and local preferences, and legal review of notices are housing-authority responsibilities. See the Regulatory-Adherence Guide."]], G.colors.AMBER, "FBF3E7"),

  H1("2. Prerequisites"),
  H2("2.1 AWS account & access"),
  bullet([bold("An AWS account "), "with administrative credentials configured for the AWS CLI (", code("aws sts get-caller-identity"), " must succeed)."]),
  bullet([bold("Region "), "— us-east-1 (the reference deployment; Comprehend, Bedrock models, and AgentCore are all available there)."]),
  bullet([bold("Model access "), "— enable the Anthropic Claude models in Amazon Bedrock (the notice-drafting tool defaults to the ", code("us.anthropic.claude-sonnet-4-5"), " cross-region inference profile)."]),
  bullet([bold("A free HUD USER API token "), "— register at huduser.gov for the Income Limits API Bearer token. It is injected into the lookup Lambda AFTER deploy (Step 1a) and kept OUT of the repo."]),
  H2("2.2 Tooling"),
  table(["Tool", "Version / note"], [
    [code("aws"), "AWS CLI v2.30+ (validated on 2.33)"],
    [code("python"), "3.12 (Lambda runtime is python3.12; the Runtime toolkit needs a 3.12 venv). Confirm python --version resolves to 3.12."],
    [code("pyyaml"), "for render.py: pip install pyyaml (confirm with pip show pyyaml)"],
    ["bash", "Any POSIX shell. On Windows, use Git-Bash (see §8)"],
    [code("agentcore"), "bedrock-agentcore-starter-toolkit (installed into the Runtime venv by setup_venv.sh in Step 4)"],
  ], [2600, 7840]),
  H2("2.3 Project layout"),
  bullet([bold("lib/engine/ "), "— the manifest-driven engine: ", code("render.py"), " plus ", code("deploy.sh"), " / ", code("demo.sh"), " / ", code("destroy.sh"), " / ", code("deploy_identity.sh"), " (a helper the spine calls) and the sign-off state-machine template."]),
  bullet([bold("lib/controls/ "), "— the shared control library: ", code("mask_pii"), ", ", code("write_audit"), ", the sign-off Lambdas, and the MCP client. Reused by every agent."]),
  bullet([bold("lib/runtime/ "), "— the generic Strands agent (", code("agent.py"), ", ", code("Dockerfile"), ", ", code("requirements.txt"), ") and the ", code("setup_venv / _obs_setup / _configure / _launch / _invoke"), " helper scripts (self-locating; run from a fresh clone)."]),
  bullet([bold("agents/housing-assistance/ "), "— the only agent-specific part: ", code("manifest.yaml"), " (single source of truth), ", code("tools/"), " (", code("intake_application.py"), ", ", code("lookup_income_limit.py"), ", ", code("assess_housing_eligibility.py"), ", ", code("recertify.py"), ", ", code("overpayment.py"), ", ", code("housing_core.py"), "), and ", code("demo_extra.sh"), "."]),

  bullet([bold("lib/connector/ "), "— the reusable governed OAuth connector (optional depth add-on): ", code("verify_source"), " (mints an outbound token via AgentCore Identity — no stored secret), ", code("deploy_connector.sh"), " / ", code("prove_connector.sh"), ", and a mock OAuth-protected system of record. Deployed separately from the spine."]),
  H1("3. What gets deployed"),
  table(["Component", "AWS resource(s)", "Lifecycle"], [
    [[bold("Identity")], "Cognito user pool hou-housing, app client hou-gw, users housing_specialist / approver / outsider", "Stable"],
    [[bold("Policy engine")], "AgentCore Policy engine hou_housing_authz (Cedar, deny-by-default)", "Spine"],
    [[bold("Gateway")], "AgentCore Gateway hou-housing-gw (MCP, CUSTOM_JWT, ENFORCE)", "Spine"],
    [[bold("Tools")], "Lambdas: hou-intake-application, hou-lookup-income-limit (HUD USER API), hou-mask-pii, hou-assess-eligibility, hou-recertify, hou-detect-overpayment, hou-core-tools, hou-write-audit, hou-request-signoff (+ 3 sign-off Lambdas)", "Spine"],
    [[bold("Guardrail")], "Bedrock Guardrail hou-housing-guardrail (PII anonymize + prompt-attack)", "Spine"],
    [[bold("WORM audit")], "DynamoDB hou-audit (append-only) + S3 Object Lock bucket hou-audit-worm-<acct>-<region>", "Spine"],
    [[bold("Human gate")], "Step Functions hou-signoff + DynamoDB hou-pending-approvals", "Spine"],
    [[bold("Discovery")], "SSM parameter /hou-housing/gateway-url", "Spine"],
    [[bold("Runtime")], "AgentCore Runtime housing_runtime_agent (ARM64 container via CodeBuild + ECR)", "Runtime"],
  ], [1700, 6300, 1440]),

  P([bold("Optional connector (Step 5). "), "If deployed, the governed OAuth connector adds a mock system-of-record Lambda behind API Gateway (", code("hou-sor-api"), "), an AgentCore Identity OAuth2 credential provider (", code("hou-sor-oauth"), ") and workload identity (", code("hou-verify-source-wi"), "), a Cognito M2M domain and resource server on the agent’s pool, and the governed ", code("verify_source"), " tool. Torn down separately — see §7."]),
  H1("4. Deployment procedure"),
  P([bold("Run the steps in order. "), "All commands assume you are in the project root (the folder containing ", code("lib/"), " and ", code("agents/"), "), with the AWS CLI configured for us-east-1. On Windows, read §8 first — a folder path with spaces will break the tooling."]),

  H2("Step 0 — Confirm the environment"),
  ...codeBlock(["aws sts get-caller-identity          # confirms credentials", "aws configure get region             # should print us-east-1", "python --version                     # 3.12.x", "pip show pyyaml                      # render.py needs pyyaml; pip install pyyaml if missing"]),

  H2("Step 1 — Deploy the governance spine (creates identity + spine)"),
  P(["One idempotent command renders the manifest, creates (or reuses) the stable Cognito identity, and builds the entire spine in the proven order: IAM roles → WORM stores → Guardrail → tool Lambdas (with per-agent resource env wired in) → policy engine → Gateway (LOG_ONLY) → targets → Cedar policies → flip to ENFORCE → human-gate Step Functions → publish the gateway URL to SSM. It writes ", code("identity-state.env"), " and ", code("spine-state.env"), "."]),
  ...codeBlock(["bash lib/engine/deploy.sh agents/housing-assistance"]),
  P([bold("Result: "), "ends with ", code("[deploy] DONE"), " and a line like ", code("Gateway URL: https://hou-housing-gw-….gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp   (mode ENFORCE)"), ". Takes roughly three to four minutes."]),
  callout("Run cycles serialized", [["Do not run two spine deploys concurrently — overlapping runs collide on the policy-engine name. If a deploy is interrupted, run ", code("destroy.sh"), " then re-deploy (the deploy is idempotent and re-uses the pool and IAM roles by name)."]], G.colors.TEAL),

  H2("Step 1a — Inject the HUD API token into the lookup Lambda (AFTER deploy)"),
  P(["The live income-limit lookup needs a free HUD USER Bearer token. Inject it into the ", code("hou-lookup-income-limit"), " Lambda's environment ", bold("after"), " the spine deploy — the deploy's env-wiring step would otherwise clobber it — and keep it OUT of the repo (env var / Secrets Manager):"]),
  ...codeBlock(["aws lambda update-function-configuration --function-name hou-lookup-income-limit \\", "    --environment \"Variables={HUD_API_TOKEN=<your-token>}\" --region us-east-1"]),
  callout("Fails soft by design", [["If the token is absent or the county is unknown, ", code("lookup_income_limit"), " returns ", code("found: false"), " and the workflow degrades gracefully rather than failing hard — but the eligibility determination then has no authoritative AMI basis, so inject the token before a real run. This is the housing counterpart to the financial-aid agent's live College Scorecard lookup: real federal data through a governed tool, never an ungoverned side-channel."]], G.colors.AMBER, "FBF3E7"),

  H2("Step 2 — Prove the governance (30 checks)"),
  P("Mints housing-specialist and outsider tokens and exercises the full governed workflow live, in ENFORCE mode. Expect 30 passed / 0 failed."),
  ...codeBlock(["bash lib/engine/demo.sh agents/housing-assistance"]),
  P("The demo proves deny-by-default (housing_specialist ALLOW / outsider DENY), a LIVE authoritative income-limit lookup from the HUD USER Income Limits API (governed through the Gateway, with the 30/50/80% AMI source and provenance stamped into the determination), the mask-before forbids and no-self-commit (each denial names the exact Cedar policy), real PII masking (name/SSN redaction), the eligibility determination (ELIGIBLE, income category vs AMI + the extremely-low-income targeting flag), a real Bedrock determination notice through the Guardrail, the immutable WORM audit (write-once + duplicate rejection), and the human sign-off gate (separation of duties + single-use token)."),
  P([bold("Deeper caseload workflows (step two). "), "The demo also exercises the deeper workflows, each a governed tool with its own control: ", code("recertify"), " (annual/interim re-certification — an ADVERSE change flags that advance notice and an informal hearing/review right are required before it takes effect, 24 CFR 982.555 / 966; fail-closed via ", code("mask_before_recertify"), "), ", code("detect_overpayment"), " (deterministic subsidy-overpayment math over a recovery period — recovery and referral stay human; fail-closed via ", code("mask_before_overpayment"), "), and ", code("refer_fraud"), " — a consequential, human-only action the agent can never take (forbidden by ", code("no_self_fraud_referral"), "). Every new high-risk action is a tool body plus its own deny-by-default forbid."]),
  P([{ text: "It ends with ", size: 21 }, code("=== 30 passed, 0 failed ===   GOVERNANCE DEMO: PASS"), { text: ".", size: 21 }]),

  H2("Step 3 — Deploy the Runtime agent"),
  P(["Create the Python 3.12 virtual environment and install the toolkit once. ", code("setup_venv.sh"), " builds the venv with the correct per-OS layout (on Windows a venv exposes ", code("Scripts/"), ", not ", code("bin/"), ") and installs ", code("bedrock-agentcore"), ", ", code("bedrock-agentcore-starter-toolkit"), ", ", code("strands-agents"), ", and ", code("strands-agents-tools"), " (a few minutes):"]),
  ...codeBlock(["bash lib/runtime/setup_venv.sh"]),
  P(["Grant the Runtime execution role permission to read the gateway-URL parameter, configure the agent with the Cognito JWT inbound authorizer (and the manifest-rendered workflow prompt), and launch it (ARM64 build runs in CodeBuild — no local Docker needed). Each helper takes the agent directory:"]),
  ...codeBlock(["bash lib/runtime/_obs_setup.sh  agents/housing-assistance   # grants ssm:GetParameter to the runtime role", "bash lib/runtime/_configure.sh  agents/housing-assistance   # agentcore configure -- JWT authorizer (exit 0)", "bash lib/runtime/_launch.sh     agents/housing-assistance   # agentcore launch -- CodeBuild ARM64 -> Runtime"]),
  P([bold("Result: "), "an AgentCore Runtime ", code("housing_runtime_agent-<id>"), " with a Cognito JWT inbound authorizer, OpenTelemetry observability enabled, and the gateway URL discovered from SSM. The launch log ends with ", code("LAUNCH_EXIT=0"), "."]),

  H2("Step 4 — Invoke and verify"),
  P("Invoke as a housing specialist with sample data (full governed workflow) and as an outsider (access denied):"),
  ...codeBlock(["bash invoke_demo.sh                                       # housing_specialist invoke with a sample application", "bash lib/runtime/_invoke.sh agents/housing-assistance outsider ChangeMe-Outsider1!"]),
  P(["Expected: the housing specialist returns a workflow summary (income category vs AMI, eligibility, targeting flag, drafted notice, INTENT audit, PENDING_APPROVAL) and a ", code("tools_available"), " list that does NOT include ", code("finalize_determination"), " — Cedar hides the forbidden tool. The outsider returns ", code("ACCESS DENIED"), " with ", code("tools_available: []"), " and ", code("governed: true"), "."]),

  H2("Step 5 (optional) — Adversarial proof and the governed OAuth connector"),
  P(["Two optional proofs that deepen the evidence. The red-team harness re-runs the governed workflow under adversarial inputs (prompt injection, forbidden-tool coaxing, attempts to act on unmasked data) and shows every control holds — the mask-before forbids and no-self-commit fire by name:"]),
  ...codeBlock(["bash lib/engine/redteam.sh agents/housing-assistance          # adversarial proof: governance holds under attack"]),
  P(["The connector proves the agent authenticates to a real, OAuth2-protected dependency without holding a secret. ", code("deploy_connector.sh"), " stands up a mock system of record (", code("MOCK-EIV-PIC"), ") behind API Gateway, an AgentCore Identity OAuth2 credential provider + workload identity, and the governed ", code("verify_source"), " tool. ", code("prove_connector.sh"), " mints a token through Identity and shows the SoR rejects unauthenticated calls, the tool holds no secret, and Cedar deny-by-default extends to the connector. The mock SoR verifies the token’s ", bold("RS256 signature against the Cognito JWKS"), " (not just its claims), so a forged or tampered token is rejected:"]),
  ...codeBlock(["bash lib/connector/deploy_connector.sh agents/housing-assistance   # mock SoR + Identity OAuth provider + verify_source", "bash lib/connector/prove_connector.sh  agents/housing-assistance   # OAuth + RS256/JWKS + no stored secret + deny-by-default"]),
  H1("5. Configuration reference"),
  table(["Setting", "Where", "Default / value"], [
    ["Region", "agent.region in the manifest", "us-east-1"],
    ["Drafting model", [code("model.draft_model_id"), { text: " in the manifest", size: 19 }], "us.anthropic.claude-sonnet-4-5-20250929-v1:0"],
    ["Guardrail", "hou-housing-guardrail (created in deploy)", "PII=ANONYMIZE + PROMPT_ATTACK HIGH; version DRAFT"],
    ["HUD API token", [code("HUD_API_TOKEN"), { text: " on hou-lookup-income-limit (env / Secrets Manager)", size: 19 }], "injected AFTER deploy (Step 1a); never committed to the repo"],
    ["Cognito users", "identity.users in the manifest", "housing_specialist / approver / outsider; passwords via env (placeholder defaults ChangeMe-*1!)"],
    ["Income categories", [code("assess_housing_eligibility.py"), { text: " (illustrative)", size: 19 }], "EXTREMELY_LOW ≤30% AMI, VERY_LOW ≤50%, LOW ≤80%, else OVER_INCOME; admit ≤50% AMI"],
    ["Gateway URL", "SSM /hou-housing/gateway-url", "published each spine deploy; read by the Runtime agent"],
    ["Housing-specialist group", "Cedar permit condition", "cognito:groups contains housing_specialist"],
    ["Audit stores", "controls + audit in the manifest", "DynamoDB hou-audit + S3 hou-audit-worm-<acct>-<region> (Object Lock GOVERNANCE 1d)"],
  ], [2100, 3540, 4800]),
  callout("Change the passwords, inject the token, and configure the real rules, before any shared use", [["The default test-user passwords are for a private evaluation account only — rotate them (or federate a real IdP) before the environment is shared. The income limits are fetched live from HUD, but the admission thresholds and local preferences in assess_housing_eligibility are illustrative configuration — replace them with the authoritative rules for your PHA and program, under legal review, before any real use."]], G.colors.AMBER, "FBF3E7"),

  H1("6. Validation checklist"),
  bullet([code("deploy.sh"), " → ends with a ", code("Gateway URL: … (mode ENFORCE)"), " line; ", code("identity-state.env"), " + ", code("spine-state.env"), " written."]),
  bullet(["HUD token injected → ", code("lookup_income_limit"), " returns ", code("found: true"), " with real 30/50/80% AMI limits + provenance (not ", code("found: false"), ")."]),
  bullet([code("demo.sh"), " → ", code("30 passed, 0 failed"), " / ", code("GOVERNANCE DEMO: PASS"), "."]),
  bullet(["SSM parameter ", code("/hou-housing/gateway-url"), " exists and matches the live gateway."]),
  bullet(["Runtime invoke: housing_specialist → workflow summary with ", code("finalize_determination"), " absent from tools; outsider → ACCESS DENIED, empty tools."]),
  bullet(["CloudWatch log group ", code("/aws/bedrock-agentcore/runtimes/housing_runtime_agent-*-DEFAULT"), " shows per-step, identity-tagged logs."]),

  H1("7. Teardown"),
  P("The spine tears down with zero residual (including the Object-Lock bucket, which requires an admin governance-bypass the tool role does not have). Identity is preserved by design — remove the pool and the Runtime explicitly for a full teardown."),
  ...codeBlock(["bash lib/engine/destroy.sh agents/housing-assistance         # spine only; leaves identity + Runtime", "# full cleanup (from lib/runtime, with the venv active):", "#   agentcore destroy                                       # runtime + ECR + CodeBuild", "#   aws cognito-idp delete-user-pool --user-pool-id <hou-housing pool id> --region us-east-1"]),
  P([bold("If you deployed the connector (Step 5), "), "tear its resources down too — ", code("destroy.sh"), " removes the ", code("hou-sor-api"), " and ", code("hou-verify-source"), " Lambdas with the spine, but the API, the Identity provider and workload identity, the connector role, and the connector’s Cognito artifacts persist:"]),
  ...codeBlock(["aws apigatewayv2 delete-api --api-id <hou-sor-api id> --region us-east-1", "aws bedrock-agentcore-control delete-oauth2-credential-provider --name hou-sor-oauth --region us-east-1", "aws bedrock-agentcore-control delete-workload-identity --name hou-verify-source-wi --region us-east-1", "aws iam delete-role --role-name hou-connector-exec        # detach its policies first", "# the connector Cognito domain (hou-sor-<acct>), M2M app client, and resource server go with the user pool"]),
  callout("Export evidence first", [["The WORM audit ledger and bucket are deleted by ", code("destroy.sh"), ". Export any audit evidence you need to retain before tearing down (scan ", code("hou-audit"), " and sync ", code("hou-audit-worm-…"), "). See the Maintenance Guide, §5."]], G.colors.TEAL),
  callout("Stop orphaned sign-off executions before teardown", [["The human sign-off gate uses a Step Functions ", code("waitForTaskToken"), " execution that can run for up to a year. If you invoke the agent and leave a determination PENDING (never approved) before tearing down, that RUNNING execution keeps the ", code("hou-signoff"), " state machine stuck in ", code("DELETING"), ", which then blocks the next deploy from re-creating a state machine of the same name (", code("StateMachineDeleting"), "). ", code("destroy.sh"), " stops RUNNING executions before deleting; if a redeploy hits this, stop the leftover execution and let deletion finish:"]], G.colors.AMBER, "FBF3E7"),
  ...codeBlock(["aws stepfunctions list-executions --state-machine-arn arn:aws:states:<region>:<acct>:stateMachine:hou-signoff \\", "    --status-filter RUNNING --region us-east-1 --query 'executions[].executionArn' --output text", "aws stepfunctions stop-execution --execution-arn <arn> --region us-east-1   # then redeploy"]),

  H1("8. Windows / Git-Bash operational notes"),
  P("The reference environment is Windows with Git-Bash driving the native AWS CLI. These matter (some are handled inside the scripts; the first is on you):"),
  bullet([bold("Deploy from a path WITHOUT spaces. "), "A project path like ", code("C:\\...\\Housing Eligibility agent"), " (with spaces) breaks Git-Bash argument quoting when driven from PowerShell. Put the project in a no-space path such as ", code("C:\\...\\housing_eligibility_agent"), " before deploying."]),
  bullet([bold("Path conversion: "), "Git-Bash rewrites arguments that start with ", code("/"), " (e.g. the SSM name) into Windows paths. The scripts set ", code("MSYS_NO_PATHCONV=1"), " where it matters — but ", code("render.py"), " runs under native Python, which cannot take ", code("/c/"), " paths, so ", code("deploy.sh"), " invokes render in a subshell with ", code("MSYS_NO_PATHCONV"), " unset."]),
  bullet([bold("Detached, unattended launches: "), "run the 3–4 minute deploy, the venv build, and the CodeBuild launch detached, then poll a log — a foreground shell can be killed before they finish, and the native ", code("aws.exe"), " / ", code("python.exe"), " grandchildren inherit the console pipe and block a synchronous launcher, so you must detach. The pattern that works from an orchestrator (PowerShell) is a ", bold("single, space-free script-path argument"), ": ", code("Start-Process bash.exe -ArgumentList '/c/…/runner.sh'"), ", where ", code("runner.sh"), " does ", code("cd <no-space dir>"), " then the command and redirects to a log. Then ", code("Get-Content x.log -Tail 20"), " to watch progress. ", bold("Do not"), " pass array-joined multi-token args (e.g. ", code("-ArgumentList '-l','runner.sh'"), ") — they are silently dropped and the command never runs."]),
  bullet([bold("Carriage returns: "), "the CLI ", code("--output text"), " picks up a trailing ", code("\\r"), "; the scripts pipe through ", code("tr -d '\\r'"), " where it matters."]),
  bullet([bold("AgentCore toolkit: "), "export ", code("PYTHONIOENCODING=utf-8"), " and ", code("AGENTCORE_SUPPRESS_RECOMMENDATION=1"), " (already set in the helper scripts) so the rich console output does not crash under the Windows codepage."]),
  spacer(),
  P([{ text: "End of runbook. See the Regulatory-Adherence Guide for the control-to-requirement mapping and the Maintenance Guide for day-two operations.", italics: true, color: G.colors.MUTED }]),
];

const doc = makeDoc(cover, body, "Housing Eligibility AgentCore · SA Deployment Runbook");
Packer.toBuffer(doc).then((b) => { require("fs").writeFileSync("Housing-AgentCore-SA-Runbook.docx", b); console.log("wrote runbook"); });
