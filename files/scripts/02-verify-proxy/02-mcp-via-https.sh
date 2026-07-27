#!/usr/bin/env bash
set -euo pipefail
# Feature:  MCP handshake through TLS reverse proxy
# Channel:  HTTPS response from localhost:443/mcp (nginx -> smart-mcp :8200)
# Contract: HTTP 200 with "serverInfo" in the body

CA="/etc/puppetlabs/puppet/ssl/certs/ca.pem"

RESPONSE=$(curl -sk --cacert "$CA" \
  -X POST https://localhost/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"verify","version":"0.1"}}}' \
  -w "\n%{http_code}" 2>/dev/null)

HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')

echo "HTTP: $HTTP_CODE"
echo "Body: $BODY"

if [ "$HTTP_CODE" = "200" ] && echo "$BODY" | grep -q '"serverInfo"'; then
  echo ""
  echo "PASS: MCP handshake via HTTPS/nginx succeeded"
else
  echo ""
  echo "FAIL: MCP handshake via HTTPS/nginx failed (HTTP $HTTP_CODE)"
  exit 1
fi
