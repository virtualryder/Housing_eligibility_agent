"""tenancy.py — Gate-B B5: tenant identity is DERIVED, never REQUESTED.

THE DEFECT THIS FIXES: mask_pii stamped `tenant` into the signed sanitized_ref straight from the
tool-call BODY (`e.get("tenant", "default")`) — i.e. the caller/model chose its own tenant. In any
multi-tenant (or even multi-program) deployment that lets one tenant mint artifacts that verify as
another tenant's, and lets audit records be mis-attributed. A tenant you can type is not a tenant.

THE MODEL: the pilot posture is ONE PHA PER ISOLATED DEPLOYMENT (PILOT-SCOPE.md — no SaaS
multi-tenancy claims). The deployment's tenant id is pinned at deploy time (CDK context `tenant` →
env TENANT_ID on every governed Lambda) and is the ONLY source of tenant identity:

  * resolve_tenant()          -> the deployment's pinned tenant (request input is IGNORED by design)
  * stamp: mask_pii signs the PINNED tenant into every sanitized_ref (it is part of the HMAC-signed
    field set, so it cannot be altered after minting without breaking the signature)
  * check_ref_tenant(ref)     -> verifiers additionally require ref.tenant == this deployment's
    tenant, so an artifact minted in ANOTHER deployment (even one sharing a signing key by
    misconfiguration) is refused — fail-closed cross-tenant rejection.

Deriving tenant from the authenticated JWT (custom:tenant claim via the gateway) is the multi-tenant
extension and is deliberately NOT implemented until the rest of Gate B lands; until then the pinned
deployment tenant + account isolation IS the boundary."""
import os

_ENV = "TENANT_ID"
DEFAULT_TENANT = "default"


def resolve_tenant(_event=None):
    """The deployment's pinned tenant. The event parameter exists to make call sites explicit that
    request-supplied tenant values are received and IGNORED — identity never comes from the body."""
    return os.environ.get(_ENV) or DEFAULT_TENANT


def check_ref_tenant(ref):
    """True iff the (already signature-verified) ref belongs to THIS deployment's tenant.
    Fail-closed: missing tenant field, or any mismatch, refuses."""
    if not isinstance(ref, dict):
        return False
    return ref.get("tenant") == resolve_tenant()
