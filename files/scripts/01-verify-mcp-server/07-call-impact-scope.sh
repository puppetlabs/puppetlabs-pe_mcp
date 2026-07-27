#!/usr/bin/env bash
set -euo pipefail
# Feature:  impact_scope tool (blast radius of a class/fact change)
# Channel:  MCP protocol response (JSON-RPC tools/call)
# Contract: Response contains "total_affected_node_count" int,
#           "per_environment" array, "pql_trace" array, "pe_instance" string.
#           Each per_environment entry: environment, affected_node_count,
#           sample_certnames.
#
# Requires: scripts/lib/mcp-session.sh concatenated ahead of this script.
# Run:  cat scripts/lib/mcp-session.sh scripts/01-verify-mcp-server/07-call-impact-scope.sh | bolt command run - --targets=pe_mcp

echo "=== impact_scope: Feature -> Channel -> Contract -> Verify ==="
echo "Establishing MCP session..."
mcp_session_init

echo 'Calling impact_scope with puppet_class="Settings"...'
RESULT=$(mcp_call "impact_scope" '{"puppet_class": "Settings"}')
echo "$RESULT" | python3 -m json.tool 2>/dev/null || echo "$RESULT"

PASS=true

if ! echo "$RESULT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
content = data.get('result', {}).get('content', [{}])
text = json.loads(content[0].get('text', '{}')) if content else {}
assert 'total_affected_node_count' in text, 'missing total_affected_node_count'
assert isinstance(text['total_affected_node_count'], int), 'total_affected_node_count must be int'
assert 'per_environment' in text, 'missing per_environment'
assert isinstance(text['per_environment'], list), 'per_environment must be a list'
assert 'pql_trace' in text, 'missing pql_trace'
assert 'pe_instance' in text, 'missing pe_instance'
for env in text['per_environment']:
    for field in ('environment', 'affected_node_count', 'sample_certnames'):
        assert field in env, f'missing {field} in per_environment entry: {env}'
total = text['total_affected_node_count']
envs = len(text['per_environment'])
print(f'Contract OK: {total} affected nodes across {envs} environments')
" 2>&1; then
  echo "FAIL: impact_scope response missing contract fields"
  PASS=false
fi

echo ""
if $PASS; then
  echo "PASS: impact_scope contract verified"
else
  echo "FAIL: impact_scope contract violations detected"
  exit 1
fi
