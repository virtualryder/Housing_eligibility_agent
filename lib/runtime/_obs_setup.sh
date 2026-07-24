#!/usr/bin/env bash
# Grant the Runtime exec role ssm:GetParameter for gateway discovery. Usage: _obs_setup.sh <agent_dir>
#
# P0-7: the runtime exec role must be an EXACT identity from deployment outputs — NEVER discovered by
# name prefix (in an account with several runtimes a prefix search can select and modify the WRONG role).
# Resolution order, fail-loud:
#   1. RUNTIME_EXEC_ROLE_ARN env (preferred: the CDK/launch output)
#   2. .runtime-role-arn file written beside this script by _launch.sh at create-time
# If neither is present the script REFUSES (no fallback discovery).
SELF="$(cd "$(dirname "$0")" && pwd)"; export MSYS_NO_PATHCONV=1
AGENT="$(cd "${1:?usage: _obs_setup.sh <agent_dir>}" && pwd)"; cd "$SELF"; source "$SELF/_env.sh"
ACC="$(aws sts get-caller-identity --query Account --output text | tr -d '\r')"

ROLE_ARN="${RUNTIME_EXEC_ROLE_ARN:-}"
if [ -z "$ROLE_ARN" ] && [ -f "$SELF/.runtime-role-arn" ]; then
  ROLE_ARN="$(tr -d ' \r\n' < "$SELF/.runtime-role-arn")"
fi
if [ -z "$ROLE_ARN" ]; then
  echo "ERROR (P0-7): runtime exec role not specified. Set RUNTIME_EXEC_ROLE_ARN to the exact role ARN" >&2
  echo "from the deployment output (or ensure _launch.sh wrote lib/runtime/.runtime-role-arn)." >&2
  echo "Refusing to discover a role by name prefix — that can modify the wrong role." >&2
  exit 1
fi
ROLE="${ROLE_ARN##*/}"   # role NAME from the exact ARN
echo "runtime exec role (exact, from deployment output): $ROLE_ARN"

SSM_ROOT="$(printf '%s' "$SSM_PARAM" | sed 's#/[^/]*$##')"   # /<root>/gateway-url -> /<root>
printf '%s' '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":["ssm:GetParameter"],"Resource":"arn:aws:ssm:'"$REGION"':'"$ACC"':parameter'"$SSM_ROOT"'/*"}]}' > ssm-pol.json
aws iam put-role-policy --role-name "$ROLE" --policy-name agent-runtime-ssm --policy-document file://ssm-pol.json --region "$REGION" && echo "  attached ssm:GetParameter to $ROLE"
aws xray update-trace-segment-destination --destination CloudWatchLogs --region "$REGION" >/dev/null 2>&1 && echo "  enabled Transaction Search" || echo "  (Transaction Search skipped)"
echo "OBS_SETUP_DONE"
