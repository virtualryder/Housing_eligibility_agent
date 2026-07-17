// housing_specialist_permit  (kind: permit  ·  validation: FAIL_ON_ANY_FINDINGS)
// A housing specialist may use the governed tools. Deny-by-default is automatic at the AgentCore
// Policy engine; this is the only broad grant. The principal is authorized by the Cognito group
// claim surfaced as a tag — no group, no access.
permit(principal, action, resource is AgentCore::Gateway)
when {
  principal.hasTag("cognito:groups") &&
  principal.getTag("cognito:groups") like "*housing_specialist*"
};
