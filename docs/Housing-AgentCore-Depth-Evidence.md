# Housing Eligibility Agent — Depth Evidence (runtime trace + OAuth connector)

*Captured live against the deployed agent (us-east-1) with Cedar in **ENFORCE**, 2026-07. Account id is the live deploy; the public repo scrubs it. Together with the red-team harness (`bash lib/engine/redteam.sh agents/housing-assistance`, governance-holds-under-attack), this is the portfolio depth pack applied to this vertical.*

> **Production-build validation evidence (2026-07, newer):** the P0-hardened build was additionally
> validated on the **CDK customer deployment path** in two captured clean-account runs — the full
> governed pipeline SUCCEEDED end-to-end on live services (exactly-once finalize, content-hash-bound
> approval), and the AgentCore Gateway/Cedar attachment reached `CREATE_COMPLETE` in **ENFORCE** as
> pure IaC. A third run validated the **full Gate-B hardening posture live** — private networking
> with a HUD-only egress allowlist, customer-managed KMS, MFA-required identity, tenant pinning,
> 10-way concurrency, an exactly-once replay storm, and a passing PII telemetry canary
> ([`../evidence/GATE-B-VALIDATION.md`](../evidence/GATE-B-VALIDATION.md)). See also
> [`../evidence/GA-4-LIVE-HAPPY-PATH.md`](../evidence/GA-4-LIVE-HAPPY-PATH.md),
> [`../evidence/P0-11-VALIDATION-RUN.md`](../evidence/P0-11-VALIDATION-RUN.md), and
> [`../VALIDATED_RELEASE.md`](../VALIDATED_RELEASE.md).

---

## Item 1 — End-to-end agent runtime trace (Observability / X-Ray)

The Strands agent runs on **AgentCore Runtime** (`housing_runtime_agent`). A housing_specialist authenticates and their access token is the bearer for every governed Gateway (MCP) tool call, so Cedar evaluates the real human principal. With Transaction Search enabled, the per-invocation OTel spans are captured as one X-Ray trace. The captured trace (`1-6a5b0489-5621776f7ceb29be5cbdbb39`, 53.2s) shows the agent autonomously orchestrating each **governed tool through the MCP gateway** and stopping at the human gate:

```
invoke_agent (Strands Agents)                          53.2s
├─ execute_tool  intake_application                         445ms
├─ execute_tool  lookup_income_limit (live HUD)             1243ms
├─ execute_tool  mask_pii                                   3063ms
├─ execute_tool  assess_housing_eligibility                 513ms
├─ execute_tool  draft_notice (guarded Bedrock)             9310ms
├─ execute_tool  write_audit (WORM)                         4232ms
└─ execute_tool  request_signoff (human gate)               3822ms
```

Every `execute_tool` span is a Cedar-authorized call through the governed gateway — including the **live authoritative-data lookup** and the **fail-closed PHI/PII masking** before the model ever drafts. The consequential `finalize_determination` never appears: the agent completes everything it is allowed to do and then **waits on a human** (the sign-off gate is left in PENDING_APPROVAL). An outsider invocation returns `ACCESS DENIED, tools_available: []`.

## Item 2 — Real OAuth connector via AgentCore Identity outbound auth

`verify_source` calls a genuinely **OAuth2-protected** external system of record (`MOCK-EIV-PIC`, an API-Gateway HTTP API that requires a Cognito M2M access token). The outbound token is minted by an **AgentCore Identity** OAuth2 credential provider (client_credentials / M2M) — the tool holds **no secret** (it lives in the Identity token vault). Proven live (`bash lib/connector/prove_connector.sh agents/housing-assistance`):

```
1. the system of record REALLY requires OAuth  -> no-token 401, bad-token 401  (genuinely OAuth-protected)
2. governed tool: housing_specialist calls verify_source; AgentCore Identity mints the outbound token -> verified
   the tool holds NO client secret (it lives in the Identity token vault)
3. deny-by-default extends to the new connector -> outsider DENIED
=== CONNECTOR PROOF: 4 passed, 0 failed ===  CONNECTOR PROOF: PASS
```

Built from the reusable, prefix-parameterized `lib/connector` kit — the same connector applied across the portfolio; swapping the mock system of record for a real one (EIV / SIS-COD / a safety database) is a configuration change, with the governance and secret-handling posture already in place.

## Why this matters

The happy-path demo proves the controls work when everything cooperates. The runtime trace proves it **runs as an autonomous agent** (not a scripted sequence) and produces tamper-evident, hash-chained evidence, the red-team proves it **holds when the agent is adversarial**, and the connector proves it **authenticates to a real dependency without holding a secret**. This vertical carries the same depth as the flagship.
