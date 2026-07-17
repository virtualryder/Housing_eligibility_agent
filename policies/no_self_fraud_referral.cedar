// no_self_fraud_referral  (kind: forbid  ·  validation: IGNORE_ALL_FINDINGS)
// A fraud referral is a CONSEQUENTIAL, HUMAN-ONLY action. The agent can never refer a case as suspected
// fraud; refer_fraud is forbidden outright and hidden from the agent's tool list. Same deny-by-default
// pattern as no_self_commit — every new high-risk action gets its own forbid.
forbid(
  principal,
  action == AgentCore::Action::"hou-core___refer_fraud",
  resource == AgentCore::Gateway::"arn:aws:bedrock-agentcore:us-east-1:111122223333:gateway/hou-housing-gw"
);
