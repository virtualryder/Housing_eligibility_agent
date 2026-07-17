// no_self_commit  (kind: forbid  ·  validation: IGNORE_ALL_FINDINGS)
// Committing a housing-eligibility determination is a HUMAN-ONLY action reachable ONLY through the
// Step Functions sign-off gate. The agent can never call finalize_determination — it is forbidden
// outright and hidden from the agent's tool list. forbid wins over any permit.
forbid(
  principal,
  action == AgentCore::Action::"hou-core___finalize_determination",
  resource == AgentCore::Gateway::"arn:aws:bedrock-agentcore:us-east-1:111122223333:gateway/hou-housing-gw"
);
