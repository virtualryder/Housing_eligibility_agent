#!/usr/bin/env bash
# Configure the AgentCore Runtime for an agent. Usage: _configure.sh <agent_dir>
SELF="$(cd "$(dirname "$0")" && pwd)"
AGENT="$(cd "${1:?usage: _configure.sh <agent_dir>}" && pwd)"; cd "$SELF"; source "$SELF/_env.sh"
[ -f "$STATE" ] || { echo "spine-state not found ($STATE). Deploy the spine first (lib/engine/deploy.sh)."; exit 1; }
source "$STATE"   # DISCOVERY, CLIENT_ID, GW_URL
# RT-4 / #233: RESTRICT RUNTIME INVOCATION TO THE GATEWAY.
# Until 2026-09-08 the runtime's authorizer accepted any caller holding a valid JWT for the pool's
# client id - so a token that could reach the gateway could ALSO reach the runtime directly, past
# the gateway's Cedar interceptor. The fourth external review recorded that as R4-2 and the answer
# was "the runtime's own model calls are IAM + guardrail governed, not gateway governed", which is
# true and is not the same as being unreachable.
#
# AWS added the field that closes it. `allowedWorkloadConfiguration` on the customJWTAuthorizer
# "restricts which workloads in the request's identity chain are allowed to invoke the target,
# identified by their hosting environments and workload identities. At launch, this is supported
# only for AgentCore Runtime targets, and the allowed workloads are AgentCore Gateways."
#   https://docs.aws.amazon.com/cli/latest/reference/bedrock-agentcore-control/update-agent-runtime.html
#   https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-oauth.html#deploy-agent-allowed-workload
#
# hostingEnvironments takes the GATEWAY ARN directly, which the spine state already carries as
# GW_ARN - no extra discovery call, no new failure mode.
#
# FAIL LOUD, NOT OPEN. If GW_ARN is absent the runtime would be configured accepting any holder of a
# pool token, which is the posture this exists to remove. Set RT4_ALLOW_UNRESTRICTED=1 to configure
# without it deliberately (a gateway-less experiment); the default refuses.
if [ -n "${GW_ARN:-}" ]; then
  WORKLOAD=",\"allowedWorkloadConfiguration\":{\"hostingEnvironments\":[{\"arn\":\"$GW_ARN\"}]}"
  echo "rt4_gateway_only=$GW_ARN"
elif [ "${RT4_ALLOW_UNRESTRICTED:-0}" = "1" ]; then
  WORKLOAD=""
  echo "rt4_gateway_only=DISABLED (RT4_ALLOW_UNRESTRICTED=1) - the runtime will accept any holder of a pool token"
else
  echo "REFUSED: no GW_ARN in $STATE, so the runtime would be configured to accept ANY caller holding a valid pool JWT - bypassing the gateway's Cedar interceptor entirely (RT-4). Deploy the spine first, or set RT4_ALLOW_UNRESTRICTED=1 to accept that posture deliberately."; exit 1
fi
ACJSON="{\"customJWTAuthorizer\":{\"discoveryUrl\":\"$DISCOVERY\",\"allowedClients\":[\"$CLIENT_ID\"]$WORKLOAD}}"
echo "runtime=$RUNTIME_NAME"
"$AC" configure -c -e agent.py -n "$RUNTIME_NAME" -rf requirements.txt -ecr auto --disable-memory -ac "$ACJSON" -rha Authorization 2>&1 | tail -40
echo "CONFIGURE_EXIT=${PIPESTATUS[0]}"
