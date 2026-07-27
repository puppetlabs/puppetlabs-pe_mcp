#!/usr/bin/env bash
set -euo pipefail
# Feature:  Error handling and post-error server health
# Channel:  MCP protocol response (JSON-RPC tools/call)
# Contract: (1) Calling a nonexistent tool returns an error (not a crash).
#           (2) The server remains healthy and can serve valid requests afterward.
#
# Requires: scripts/lib/mcp-session.sh concatenated ahead of this script.
# Run:  cat scripts/lib/mcp-session.sh scripts/01-verify-mcp-server/09-verify-error-handling.sh | bolt command run - --targets=pe_mcp

echo "=== error-handling: Feature -> Channel -> Contract -> Verify ==="
echo "Establishing MCP session..."
mcp_session_init

echo ""
echo "=== Step 1: Call nonexistent tool (expect error, not crash) ==="
ERROR_RESULT=$(mcp_call "nonexistent_tool_12345" '{}')
echo "$ERROR_RESULT"

if echo "$ERROR_RESULT" | grep -q '"isError":true'; then
  echo ""
  echo "PASS: nonexistent tool returned error response (not a crash)"
elif echo "$ERROR_RESULT" | grep -q '"error"'; then
  echo ""
  echo "PASS: nonexistent tool returned JSON-RPC error (not a crash)"
else
  echo ""
  echo "FAIL: expected error response for nonexistent tool"
  exit 1
fi

echo ""
echo "=== Step 2: Call node_lookup after error (server still healthy) ==="
HEALTHY_RESULT=$(mcp_call "node_lookup" '{}')
echo "$HEALTHY_RESULT"

if echo "$HEALTHY_RESULT" | grep -q "certname"; then
  echo ""
  echo "PASS: server healthy after error — node_lookup still works"
else
  echo ""
  echo "FAIL: server unhealthy after error — node_lookup broken"
  exit 1
fi
