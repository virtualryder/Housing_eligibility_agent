# Key Management — signing keys, rotation, blast radius, monitoring (Review-3 R3-5)

*Covers the HMAC provenance keys (the trust fabric of the governed pipeline) and the customer-managed
KMS key. Written to answer a CISO's four questions: which keys exist, who can touch them, how they
rotate, and what a compromise costs.*

## 1. Key inventory

| Key | Purpose | Store | Signers (only) | Verifiers |
|---|---|---|---|---|
| `hou-<env>/provenance-signing-deid` | Signs mask_pii **sanitized-artifact refs** (proof of masking) | Secrets Manager (CMK-encrypted under `kms=customer-managed`) | `mask-pii` | assess, recertify, overpayment, core, guards |
| `hou-<env>/provenance-signing-hud` | Signs **HUD income-limit provenance** (proof of authoritative source) | Secrets Manager (same) | `lookup-income-limit` | assess, guards |
| `hou-<env>/hud-api-token` | HUD USER API bearer (external credential, not a signing key) | Secrets Manager | — | `lookup-income-limit` only |
| `alias/hou-<env>-data` CMK | Encryption at rest: tables, WORM vault, secrets, Lambda env, log groups, SNS | KMS, **rotation enabled** | — | service principals + granted function roles only |

**Domain separation is enforced by IAM, not convention** (GA-2): the lookup role cannot read the
deid key and the masker cannot read the HUD key — CDK-asserted
(`test_ga2_domain_keys_are_separate_secrets_with_split_grants`). A configured-but-unreadable domain
key **fails closed** and never falls back to a shared key.

**Environment separation:** keys are generated per deployment (`hou-<env>/…`) — dev, pilot, and any
future prod never share key material. **Tenant separation:** one PHA per isolated deployment, so
per-deployment keys ARE per-tenant keys; additionally every artifact carries the HMAC-signed tenant,
and verifiers refuse cross-tenant artifacts even under a shared key (B5, tested).

## 2. Key-version stamping (rotation forensics)

Every token and sanitized ref records `key_version` — `deid:sm:<VersionId>` /` hud:sm:<VersionId>`
for the Secrets Manager path, `<domain>:env` for env-supplied dev keys. The field is INFORMATIONAL
(not part of the signed canon — verification depends on the key itself), and it lets an auditor
answer, for any artifact ever written to the WORM ledger: *which key version minted this, and was
that version current at the time?*

## 3. Rotation procedure

HMAC rotation is deliberately simple and honest about its consequence: **rotating a key invalidates
all in-flight tokens minted under the old version — and every verifier fails closed to
`ManualReview`.** That is safe (never wrong-answer) but disruptive, so rotate between processing
windows.

1. **Drain:** confirm no executions are mid-pipeline
   (`aws stepfunctions list-executions --status-filter RUNNING` on the controller = empty), or
   accept that paused/running cases will route to manual review after step 3.
2. **Rotate the secret value** (new version, same ARN):
   `aws secretsmanager put-secret-value --secret-id hou-<env>/provenance-signing-deid --secret-string "$(openssl rand -hex 48)"`
   (repeat per domain — rotate domains independently; that is what the split is for).
3. **Force consumers to re-read:** values are cached for the Lambda lifetime; publish a no-op env
   change or version bump on the signer + verifier functions to force cold starts
   (`aws lambda update-function-configuration --function-name hou-<env>-mask-pii --environment ...`),
   or simply wait out natural recycling in low-traffic pilots.
4. **Verify:** run a synthetic case end-to-end; confirm the new artifact's `key_version` shows the
   new `VersionId`; confirm an artifact minted BEFORE rotation now fails verification (fail-closed
   demonstration — this is the control working, not an outage).
5. **Record:** note the rotation (date, domains, old/new VersionId) in the deployment record; the
   WORM ledger's stamped `key_version` values partition pre/post-rotation artifacts for audit.

**Cadence:** pilot = per engagement milestone or on personnel change; production reference =
scheduled (e.g., quarterly) + event-driven (suspected exposure, offboarding of anyone with read
access). The KMS CMK rotates automatically (AWS annual rotation, enabled in CDK).

## 4. Blast radius of a compromised key

| Compromised | Attacker can | Attacker canNOT | Contain by |
|---|---|---|---|
| deid key | Mint refs that verify as "masked" for THIS deployment/tenant | Forge HUD provenance; cross into another deployment/tenant (different key + tenant check); alter the WORM ledger; bypass the human gate | Rotate deid key (step 3); prior artifacts auditable by `key_version` |
| HUD key | Mint "authoritative" income limits for THIS deployment | Forge proof-of-masking; commit a determination (human gate + Cedar `no_self_commit` stand) | Rotate HUD key; cross-check suspect determinations against huduser.gov |
| Both | Both of the above — still cannot self-commit, self-refer fraud, or touch the ledger | — | Full rotation + incident response (GATE-B-CHECKLIST IR section) |
| CMK disabled/deleted | Deny service (stores unreadable) | Read plaintext (KMS never releases the key) | KMS 7-day pending-deletion window + alias monitoring |

The human sign-off gate, Cedar deny-by-default, and the hash-chained WORM ledger are all OUTSIDE the
HMAC trust fabric — a total signing-key compromise degrades the system to "everything routes to
manual review or requires a human," never to "wrong determinations committed silently."

## 5. Monitoring

- **Every signing-secret read is CloudTrail-visible** (`secretsmanager:GetSecretValue` on the two
  signing ARNs); alert on reads by ANY principal other than the granted function roles.
- **Guard failures are paged** (`Housing/Governance :: GuardFailed` — R3-3): a forged-ref spike is
  the runtime symptom of key misuse.
- **KMS:** CloudTrail on `ScheduleKeyDeletion`/`DisableKey` for the data CMK (deny-of-service
  attempt); Config rule on rotation staying enabled.

## 6. Known limits (stated, not hidden)

Symmetric HMAC is deliberate for the pilot (signer and verifier share one deployment trust
boundary; see `provenance.py` header). The production-hardening path if a customer requires
asymmetric proof: move minting behind KMS asymmetric sign/verify (`RSASSA_PSS`/`ECDSA`) so no Lambda
ever holds key material — the connector's RS256/JWKS pattern (`lib/connector/`) is the in-repo
reference for that model.
