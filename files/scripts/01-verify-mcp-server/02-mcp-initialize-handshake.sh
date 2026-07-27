#!/usr/bin/env bash
set -euo pipefail
# Feature:  MCP JSON-RPC initialize handshake
# Channel:  HTTP response from localhost:8200/mcp
# Contract: HTTP 200 with "serverInfo" in the body

RESPONSE=$(curl -s http://127.0.0.1:8200/mcp \
  -X POST \
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
  echo "PASS: MCP initialize handshake succeeded"
else
  echo ""
  echo "FAIL: MCP initialize handshake failed (HTTP $HTTP_CODE)"
  exit 1
fi
