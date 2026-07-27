#!/usr/bin/env bash
set -euo pipefail
# Feature:  pql_query tool (raw PQL escape hatch)
# Channel:  MCP protocol response (JSON-RPC tools/call)
# Contract: Response contains "pql" (echoed query), "rows" array,
#           "truncated" boolean, "row_cap" integer, "pe_instance" string.
#
# Requires: scripts/lib/mcp-session.sh concatenated ahead of this script.
# Run:  cat scripts/lib/mcp-session.sh scripts/01-verify-mcp-server/05-call-pql-query.sh | bolt command run - --targets=pe_mcp

echo "=== pql_query: Feature -> Channel -> Contract -> Verify ==="
echo "Establishing MCP session..."
mcp_session_init

echo "Calling pql_query with 'nodes[certname] { limit 5 }'..."
RESULT=$(mcp_call "pql_query" '{"query": "nodes[certname] { limit 5 }"}')
echo "$RESULT" | python3 -m json.tool 2>/dev/null || echo "$RESULT"

PASS=true

if ! echo "$RESULT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
content = data.get('result', {}).get('content', [{}])
text = json.loads(content[0].get('text', '{}')) if content else {}
assert 'pql' in text, 'missing pql echo'
assert 'rows' in text, 'missing rows'
assert isinstance(text['rows'], list), 'rows must be a list'
assert 'truncated' in text, 'missing truncated'
assert isinstance(text['truncated'], bool), 'truncated must be bool'
assert 'row_cap' in text, 'missing row_cap'
assert isinstance(text['row_cap'], int), 'row_cap must be int'
assert 'pe_instance' in text, 'missing pe_instance'
print(f'Contract OK: pql echoed, {len(text[\"rows\"])} rows, truncated={text[\"truncated\"]}, row_cap={text[\"row_cap\"]}')
" 2>&1; then
  echo "FAIL: pql_query response missing contract fields"
  PASS=false
fi

echo ""
if $PASS; then
  echo "PASS: pql_query contract verified"
else
  echo "FAIL: pql_query contract violations detected"
  exit 1
fi
