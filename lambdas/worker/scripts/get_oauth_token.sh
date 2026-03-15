#!/bin/bash
# Exchange Anthropic OAuth refresh token for a short-lived access token.
#
# Usage:
#   export ANTHROPIC_REFRESH_TOKEN="your-refresh-token"
#   eval $(./scripts/get_oauth_token.sh)
#
# Or in one line:
#   eval $(ANTHROPIC_REFRESH_TOKEN="..." ./scripts/get_oauth_token.sh)
#
# This sets ANTHROPIC_AUTH_TOKEN in your shell.

set -euo pipefail

CLIENT_ID="9d1c250a-e61b-44d9-88ed-5944d1962f5e"

if [ -z "${ANTHROPIC_REFRESH_TOKEN:-}" ]; then
  echo "Error: ANTHROPIC_REFRESH_TOKEN not set" >&2
  exit 1
fi

RESPONSE=$(curl -sf -X POST https://console.anthropic.com/v1/oauth/token \
  -H "Content-Type: application/json" \
  -d "{\"grant_type\":\"refresh_token\",\"client_id\":\"${CLIENT_ID}\",\"refresh_token\":\"${ANTHROPIC_REFRESH_TOKEN}\"}" 2>/dev/null)

ACCESS_TOKEN=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])" 2>/dev/null)

if [ -z "$ACCESS_TOKEN" ]; then
  echo "Error: Failed to get access token. Response: $RESPONSE" >&2
  exit 1
fi

echo "export ANTHROPIC_AUTH_TOKEN=\"${ACCESS_TOKEN}\""
echo "# Token obtained successfully" >&2
