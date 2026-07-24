# Audit retention profiles (P0-12)

*The WORM audit vault's Object Lock mode + retention are a DEPLOY-TIME CHOICE, not a hardcoded value.
The manifest's `GOVERNANCE / 1 day` is a **sandbox demo profile only** — it proves the mechanism while
keeping a throwaway account cleanable. Real deployments select a profile below (deploy env
`OBJECT_LOCK_MODE_OVERRIDE` / `RETENTION_DAYS_OVERRIDE`, or the CDK `retention_*` context).*

| Profile | Mode | Retention | Use |
|---|---|---|---|
| `sandbox-demo` | GOVERNANCE | 1 day | Demos/testing in a disposable account (current manifest default) |
| `pilot` | GOVERNANCE | 90 days | Scoped customer pilot; bypass restricted to a break-glass role, every use CloudTrail-logged |
| `production-reference` | **COMPLIANCE** | per records schedule (e.g. 2,555 days / 7 years) | Operational deployments; NO principal (including root) can shorten or bypass until expiry |

**Choosing the number:** housing-assistance records retention is set by the PHA's state
records-management schedule and program requirements — the customer's records officer supplies the
duration; we supply the mechanism. Document the chosen schedule in the deployment record.

**GOVERNANCE vs COMPLIANCE:** GOVERNANCE is bypassable by principals holding
`s3:BypassGovernanceRetention` (the tool role explicitly Denies it; account admins are restricted by
SCP/break-glass procedure — see below). COMPLIANCE is unbypassable by design; treat enabling it as an
irreversible commitment for the retention window.

**Break-glass (GOVERNANCE profiles only):** a dedicated role, normally unassumable (permission
boundary + MFA + approval), is the only principal allowed `s3:BypassGovernanceRetention`; every
assumption and use is CloudTrail-alarmed. **Legal hold:** apply `s3:PutObjectLegalHold` via the same
break-glass procedure; holds survive retention expiry until released. **Disposition:** on schedule
expiry, deletion is a recorded records-management action, not an operational cleanup.

Related: periodic `verify_chain` runs + signed verification reports, and a dedicated cross-account
archive/logging account, are P1-7 items.
