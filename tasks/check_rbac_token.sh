#!/usr/bin/env bash
set -euo pipefail

# Bolt task: check whether the RBAC token on an MCP node is still valid.
# Reads the token from a local file, uses it as X-Authentication header
# against the PE primary RBAC API users/current endpoint.
# Returns valid/expired/missing status (and token value when valid).
# Parameters (via environment): PT_pe_primary, PT_token_path, PT_ca_cert_path

TOKEN_PATH="${PT_token_path:-/opt/smart-mcp/rbac_token}"
CA_CERT_PATH="${PT_ca_cert_path:-/etc/puppetlabs/puppet/ssl/certs/ca.pem}"

if [ ! -f "$TOKEN_PATH" ]; then
  echo '{"status":"missing","message":"Token file not found","token_path":"'"$TOKEN_PATH"'"}'
  exit 0
fi

TOKEN=$(cat "$TOKEN_PATH" | tr -d '[:space:]')

if [ -z "$TOKEN" ]; then
  echo '{"status":"missing","message":"Token file is empty","token_path":"'"$TOKEN_PATH"'"}'
  exit 0
fi

RESPONSE=$(curl -sk "https://${PT_pe_primary}:4433/rbac-api/v1/users/current" \
  --cacert "$CA_CERT_PATH" \
  -H "X-Authentication: ${TOKEN}" \
  -w "\n%{http_code}" 2>/dev/null)

HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [ "$HTTP_CODE" = "200" ]; then
  echo '{"status":"valid","message":"Token is valid","token_path":"'"$TOKEN_PATH"'","token":"'"$TOKEN"'"}'
elif [ "$HTTP_CODE" = "401" ]; then
  echo '{"status":"expired","message":"Token is expired or revoked","token_path":"'"$TOKEN_PATH"'"}'
else
  echo '{"status":"error","message":"RBAC API returned HTTP '"$HTTP_CODE"'","token_path":"'"$TOKEN_PATH"'","response":'"$(echo "$BODY" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read().strip()))' 2>/dev/null || echo '""')"'}'
fi
