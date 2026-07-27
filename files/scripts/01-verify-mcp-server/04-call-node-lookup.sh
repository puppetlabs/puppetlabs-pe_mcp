#!/usr/bin/env bash
set -euo pipefail
# Feature:  node_lookup tool
# Channel:  MCP protocol response (JSON-RPC tools/call)
# Contract: Response contains "nodes" array where each entry has "certname".
#           Must also contain "pql_trace" and "pe_instance".
#
# Requires: scripts/lib/mcp-session.sh concatenated ahead of this script.
# Run:  cat scripts/lib/mcp-session.sh scripts/01-verify-mcp-server/04-call-node-lookup.sh | bolt command run - --targets=pe_mcp

echo "=== node_lookup: Feature -> Channel -> Contract -> Verify ==="
echo "Establishing MCP session..."
mcp_session_init

echo "Calling node_lookup..."
RESULT=$(mcp_call "node_lookup" '{}')
echo "$RESULT" | python3 -m json.tool 2>/dev/null || echo "$RESULT"

PASS=true

if ! echo "$RESULT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
content = data.get('result', {}).get('content', [{}])
text = json.loads(content[0].get('text', '{}')) if content else {}
nodes = text.get('nodes', [])
assert isinstance(nodes, list), 'nodes must be a list'
assert len(nodes) > 0, 'nodes must not be empty on a live PE'
for n in nodes:
    assert 'certname' in n, f'missing certname in node entry: {n}'
print(f'Contract OK: {len(nodes)} nodes, all have certname')
" 2>&1; then
  echo "FAIL: node_lookup response missing contract fields (nodes[].certname)"
  PASS=false
fi

if ! echo "$RESULT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
content = data.get('result', {}).get('content', [{}])
text = json.loads(content[0].get('text', '{}')) if content else {}
assert 'pql_trace' in text, 'missing pql_trace'
assert 'pe_instance' in text, 'missing pe_instance'
print(f'Contract OK: pql_trace present, pe_instance={text[\"pe_instance\"]}')
" 2>&1; then
  echo "FAIL: node_lookup response missing pql_trace or pe_instance"
  PASS=false
fi

echo ""
if $PASS; then
  echo "PASS: node_lookup contract verified"
else
  echo "FAIL: node_lookup contract violations detected"
  exit 1
fi
