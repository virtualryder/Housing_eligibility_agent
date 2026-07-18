const G = require("./guides.js");
const { H1, H2, H3, P, bold, code, bullet, num, codeBlock, callout, table, spacer, coverAndToc, makeDoc, Packer } = G;

const cover = coverAndToc(
  ["Maintenance & Operations Guide"],
  "Housing Eligibility Agent on Amazon Bedrock AgentCore",
  "Day-two operations for the governed Housing Choice Voucher (Section 8) / public-housing eligibility accelerator — routine changes, the Runtime lifecycle, monitoring, audit-evidence handling, teardown/rebuild, and the known toolchain gotchas. Accelerator reference. Version 1.0 · 2026.",
  ["1. Operating model", "2. Routine operations", "3. The Runtime agent lifecycle", "4. Monitoring & observability", "5. Audit-evidence management", "6. Teardown & rebuild", "7. Troubleshooting & known gotchas", "8. Cost & housekeeping"]
);

const body = [
  H1("1. Operating model"),
  P("The deployment has three lifecycles, and keeping them straight is the key to safe operations:"),
  table(["Lifecycle", "What it contains", "Cadence"], [
    [[bold("Identity")], "Cognito pool, app client, users/group", "Stable — changed rarely; survives spine redeploys"],
    [[bold("Governance spine")], "Cedar engine, Gateway, tools, Guardrail, WORM audit, human gate", "Reproducible — redeploy freely; zero-residual teardown"],
    [[bold("Runtime agent")], "Generic Strands agent container on AgentCore Runtime", "Decoupled — survives spine redeploys untouched"],
  ], [1900, 5540, 3000]),
  callout("Why this matters", [["Because identity is stable and the Runtime discovers the gateway from SSM, you can rebuild the entire spine as often as you like without ever redeploying the Runtime or invalidating housing-specialist tokens."]], G.colors.TEAL),

  H1("2. Routine operations"),
  H2("2.1 Refresh the spine"),
  P("The safest way to apply most spine changes is a clean rebuild. Destroy leaves identity intact; deploy reuses it."),
  ...codeBlock(["bash lib/engine/destroy.sh agents/housing-assistance", "bash lib/engine/deploy.sh  agents/housing-assistance", "# re-inject the HUD token (a fresh deploy re-wires the lookup Lambda's env):", "aws lambda update-function-configuration --function-name hou-lookup-income-limit \\", "    --environment \"Variables={HUD_API_TOKEN=<your-token>}\" --region us-east-1", "bash lib/engine/demo.sh    agents/housing-assistance   # smoke test: expect 30/30"]),
  P([bold("Note: "), "run cycles serialized — never two concurrent spine deploys. Re-inject the HUD token after every spine deploy (§2.4)."]),

  H2("2.2 Change the eligibility rules or a tool"),
  P(["The income-category thresholds and eligibility logic live in ", code("agents/housing-assistance/tools/assess_housing_eligibility.py"), " (the 30/50/80% AMI category boundaries, the very-low-income admission threshold, and the extremely-low-income targeting flag). Edit the source, then redeploy the spine, which repackages and updates every tool Lambda. For a fast single-tool iteration you can update just one function's code:"]),
  ...codeBlock(["# fast path — update one Lambda's code in place:", "cd agents/housing-assistance/tools", "cp assess_housing_eligibility.py lambda_function.py", "python -c \"import zipfile;z=zipfile.ZipFile('f.zip','w');z.write('lambda_function.py');z.close()\"", "aws lambda update-function-code --function-name hou-assess-eligibility \\", "    --zip-file fileb://f.zip --region us-east-1"]),
  callout("Illustrative defaults are not admission rules", [["The income limits themselves are fetched live from HUD, but the admission thresholds and local preferences shipped here are illustrative configuration for demonstration. Replace them with the authoritative rules for your PHA and program, under legal review, before any real determination. The rules engine is deliberately deterministic and model-free so a housing specialist can defend each determination at an informal hearing."]], G.colors.AMBER, "FBF3E7"),

  H2("2.3 Change Cedar policies"),
  P(["Policies are declared in the manifest (", code("policies:"), ") and rendered to Cedar statements by ", code("render.py"), ". To add or change a permit/forbid, edit the manifest and redeploy. Two rules to remember:"]),
  bullet([bold("Policies validate against the tool schemas. "), "A policy that references a tool input must match the Gateway's tool definition — deploy the tools before the policies (the engine already orders this)."]),
  bullet([bold("Use the LOG_ONLY → ENFORCE path. "), "The spine attaches the engine in LOG_ONLY, validates, then flips to ENFORCE. For risky policy changes, test in LOG_ONLY first."]),
  P([bold("Cedar reminders: "), code("cognito:groups"), " is a string tag — match with ", code("like \"*housing_specialist*\""), "; scope resources to ", code("AgentCore::Gateway"), "; a blanket forbid (like ", code("no_self_commit"), " or ", code("no_self_fraud_referral"), ") needs ", code("--validation-mode IGNORE_ALL_FINDINGS"), "; ", code("create-policy"), " is asynchronous — poll ", code("get-policy"), "."]),

  H2("2.4 Manage the HUD API token"),
  P([code("lookup_income_limit"), " reads its Bearer token from ", code("HUD_API_TOKEN"), " on the ", code("hou-lookup-income-limit"), " Lambda (env var / Secrets Manager). It is kept OUT of the repo and injected AFTER each spine deploy — the deploy's ", code("wire_env"), " step re-applies the manifest env and would otherwise clobber it. Re-inject after any full deploy:"]),
  ...codeBlock(["aws lambda update-function-configuration --function-name hou-lookup-income-limit \\", "    --environment \"Variables={HUD_API_TOKEN=<your-token>}\" --region us-east-1"]),
  callout("Fails soft, so watch for it", [["If the token is missing or stale, the lookup returns ", code("found: false"), " and the workflow keeps running but WITHOUT an authoritative AMI basis. Treat a ", code("found: false"), " in the logs as a signal to re-inject the token, not as a benign event."]], G.colors.TEAL),

  H2("2.5 Adjust the Bedrock Guardrail"),
  P(["The output guardrail ", code("hou-housing-guardrail"), " (PII anonymize + prompt-attack) is created on first deploy and reused by name thereafter. Update it in place or delete it and let the next deploy recreate it:"]),
  ...codeBlock(["aws bedrock update-guardrail --guardrail-identifier <id> ... --region us-east-1", "# or force recreation on next deploy:", "aws bedrock delete-guardrail --guardrail-identifier <id> --region us-east-1"]),

  H2("2.6 Swap the drafting model"),
  P([code("draft_notice"), " uses the model in ", code("DRAFT_MODEL_ID"), " (from the manifest; default ", code("us.anthropic.claude-sonnet-4-5-20250929-v1:0"), "). Point it at another enabled model via the manifest and redeploy, or update the Lambda config directly. Note that ", code("update-function-code"), " preserves env vars, but a full deploy re-applies them from the manifest via the engine's ", code("wire_env"), " step (which is also why the HUD token needs re-injecting — §2.4)."]),

  H2("2.7 Manage identity"),
  bullet([bold("Add or reset users: "), "the spine deploy creates them idempotently, or use ", code("aws cognito-idp admin-set-user-password"), " to rotate a password."]),
  bullet([bold("Rotate the default passwords "), "before any shared use of the environment."]),
  bullet([bold("Production: "), "federate the housing authority's real identity provider and map housing-specialist roles to the ", code("housing_specialist"), " group / claim, rather than using the built-in test users."]),

  H1("3. The Runtime agent lifecycle"),
  bullet([bold("After an agent or manifest change: "), "from the project root run ", code("bash lib/runtime/_launch.sh agents/housing-assistance"), " — the container rebuilds in CodeBuild and the same Runtime ARN is updated with the re-rendered workflow prompt."]),
  bullet([bold("After a spine redeploy: "), "do nothing (except re-inject the HUD token). The gateway URL rotates, but the agent reads it from SSM ", code("/hou-housing/gateway-url"), " at invoke time, and identity is stable — the Runtime keeps working."]),
  bullet([bold("Only if identity changes "), "(you rebuild the Cognito pool) re-configure the Runtime with the new authorizer and verify with ", code("bash lib/runtime/_verify_rt.sh agents/housing-assistance"), "."]),
  bullet([bold("Verify anytime: "), code("bash lib/runtime/_invoke.sh agents/housing-assistance housing_specialist"), " and the outsider negative case."]),

  H1("4. Monitoring & observability"),
  P("Observability is enabled on the Runtime (OpenTelemetry) and every governed step is logged with the acting identity."),
  bullet([bold("Runtime logs: "), code("aws logs tail /aws/bedrock-agentcore/runtimes/housing_runtime_agent-<id>-DEFAULT --since 1h"), " — per-step, identity-tagged, OTel-correlated (trace/span IDs)."]),
  bullet([bold("GenAI dashboard: "), "the CloudWatch GenAI Observability console surfaces agent/tool spans (requires CloudWatch Transaction Search enabled in the account)."]),
  bullet([bold("Spine smoke test: "), code("bash lib/engine/demo.sh agents/housing-assistance"), " is the fastest health check — 30/30 means the whole governed path is intact."]),
  bullet([bold("Watch for: "), "repeated ", code("ACCESS DENIED"), " (identity/authorization drift), ", code("draft failed"), " (model access or inference-parameter issues), guardrail blocks on the notice, ", code("lookup_income_limit"), " returning ", code("found: false"), " (a missing/stale HUD token), and any ", code("assess"), " call arriving with ", code("deidentified=false"), " (a masking-order regression)."]),

  H1("5. Audit-evidence management"),
  P(["The audit lives in two places: the append-only DynamoDB ledger ", code("hou-audit"), " (point-in-time recovery enabled) and the S3 Object Lock bucket ", code("hou-audit-worm-<acct>-<region>"), ". Together they are the due-process and program-integrity evidence trail — each record stamps the HUD income-limit provenance behind the determination."]),
  bullet([bold("Retention: "), "the reference bucket uses Object Lock in GOVERNANCE mode with a 1-day default retention for easy evaluation. For production, raise the retention period (and consider COMPLIANCE mode) to match your records-retention schedule."]),
  bullet([bold("Export before teardown: "), code("destroy.sh"), " deletes the ledger and bucket. Export first:"]),
  ...codeBlock(["aws dynamodb scan --table-name hou-audit --region us-east-1 > audit-ledger.json", "aws s3 sync s3://hou-audit-worm-<acct>-us-east-1 ./audit-evidence/"]),
  callout("Tamper-evidence is by construction", [["The tool role can write audit records but is denied delete, update, and Object-Lock bypass. Only an administrator with an explicit governance-bypass can remove locked objects — which is exactly what the teardown script does."]], G.colors.TEAL),

  H1("6. Teardown & rebuild"),
  bullet([bold("Spine only (keep identity + Runtime): "), code("bash lib/engine/destroy.sh agents/housing-assistance"), " — zero residual, including the Object-Lock bucket."]),
  bullet([bold("Clean refresh: "), "destroy then deploy (then re-inject the HUD token). Identity and the Runtime are unaffected."]),
  bullet([bold("Full removal: "), "destroy the spine, then from ", code("lib/runtime/"), " run ", code("agentcore destroy"), " (runtime + ECR + CodeBuild), and delete the Cognito pool."]),
  bullet([bold("Stop pending sign-off executions first. "), "If you invoked the agent and left a determination PENDING (never approved), stop that RUNNING Step Functions execution before teardown — otherwise it keeps ", code("hou-signoff"), " stuck DELETING and blocks the next deploy (see §7)."]),

  H1("7. Troubleshooting & known gotchas"),
  table(["Symptom", "Cause & fix"], [
    ["Git-Bash 'cd: …/Housing: No such file or directory'", "The project path contains spaces and PowerShell mangled the quoting. Deploy from a no-space path (e.g. housing_eligibility_agent)."],
    ["Detached deploy/launch produces no log / never runs", "Start-Process with array-joined multi-token args silently drops the command, and native aws.exe/python.exe grandchildren inheriting the console pipe block a synchronous launcher. Launch detached via a single space-free script-path arg: Start-Process bash.exe -ArgumentList '/c/…/runner.sh' (runner.sh cd's to the no-space dir, runs the command, redirects to a log)."],
    ["render.py can't find python / pyyaml (Windows)", "Non-login shells may lack the PATH. Use a login shell (bash -l) and confirm pip show pyyaml."],
    ["Deploy fails: StateMachineDeleting on hou-signoff", "A prior invoke left a waitForTaskToken sign-off execution RUNNING (a PENDING determination that was never approved). It keeps the hou-signoff state machine stuck DELETING, which blocks re-creating one of the same name. Stop the leftover execution (list-executions --status-filter RUNNING → stop-execution), let deletion finish, then redeploy. Stop pending sign-off executions BEFORE teardown to avoid this."],
    ["lookup_income_limit returns found=false", "The HUD USER call failed: the HUD_API_TOKEN is missing/stale (a fresh deploy re-wired the Lambda env and clobbered it — re-inject per §2.4), or the county entityid/FIPS is unknown. The tool fails soft (found=false) so the workflow degrades gracefully — but re-inject the token before a real run so the determination has an authoritative AMI basis."],
    ["ConflictException on the policy engine at deploy", "Two spine deploys overlapped. Run serialized; a fresh destroy → deploy clears it."],
    ["Control Lambda hits the wrong table/bucket (AccessDenied)", "The control's resource env wasn't wired. The engine's wire_env step sets AUDIT_TABLE / AUDIT_BUCKET / PENDING_TABLE / SM_NAME on every control + sign-off Lambda; a full deploy re-applies it."],
    ["Runtime invoke returns 424 / gateway not found", "SSM parameter missing or stale. Confirm /hou-housing/gateway-url exists and matches the live gateway."],
    ["'draft failed: ValidationException ... temperature and top_p'", "The model rejects both parameters together via Converse. Send temperature only."],
    ["demo shows a tool ALLOW but no result field", "The MCP client truncates long output (~200 chars). Put short proof fields first in the tool response, or grep an early field."],
  ], [3100, 7340]),

  H1("8. Cost & housekeeping"),
  bullet([bold("Idle cost is low: "), "Lambdas, DynamoDB (on-demand), and the Gateway are pay-per-use; the largest steady item is the Runtime container and any provisioned observability. The HUD USER API is free."]),
  bullet([bold("Tear down between evaluations "), "to keep costs near zero — ", code("destroy.sh"), " leaves only the stable identity and the (idle) Runtime; remove those too for a full stop."]),
  bullet([bold("CodeBuild & ECR: "), "each Runtime deploy pushes an image tag to ECR; prune old tags periodically."]),
  bullet([bold("Region: "), "keep all components in us-east-1 for the reference deployment — Comprehend, the Bedrock models, and AgentCore are co-located there."]),
  spacer(),
  P([{ text: "End of maintenance guide. See the SA Deployment Runbook for first-time setup and the Regulatory-Adherence Guide for the control mapping.", italics: true, color: G.colors.MUTED }]),
];

const doc = makeDoc(cover, body, "Housing Eligibility AgentCore · Maintenance & Operations Guide");
Packer.toBuffer(doc).then((b) => { require("fs").writeFileSync("Housing-AgentCore-Maintenance.docx", b); console.log("wrote maintenance"); });
