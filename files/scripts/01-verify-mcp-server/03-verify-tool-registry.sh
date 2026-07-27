#!/usr/bin/env bash
set -euo pipefail
# Feature:  Registry-based tool loading
# Channel:  MCP protocol response (JSON-RPC tools/list)
# Contract: All 10 default tools registered: node_lookup, pql_query,
#           recent_reports, resource_events, impact_scope,
#           environment_status, node_facts, nodes_by_class,
#           comply_results, infrastructure_map.
#           Each tool must have "name" and "description" fields.
#
# Requires: scripts/lib/mcp-session.sh concatenated ahead of this script.
# Run:  cat scripts/lib/mcp-session.sh scripts/01-verify-mcp-server/03-verify-tool-registry.sh | bolt command run - --targets=pe_mcp

echo "=== tool-registry: Feature -> Channel -> Contract -> Verify ==="
echo "Establishing MCP session..."
mcp_session_init

echo "Calling tools/list..."
RESULT=$(mcp_tools_list)
echo "$RESULT" | python3 -m json.tool 2>/dev/null || echo "$RESULT"

PASS=true

if ! echo "$RESULT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
tools = data.get('result', {}).get('tools', [])
tool_names = {t['name'] for t in tools}
expected = {'node_lookup', 'pql_query', 'recent_reports', 'resource_events', 'impact_scope', 'environment_status', 'node_facts', 'nodes_by_class', 'comply_results', 'infrastructure_map'}
missing = expected - tool_names
assert not missing, f'missing tools from registry: {missing}'
for t in tools:
    if t['name'] in expected:
        assert 'description' in t and t['description'], f'tool {t[\"name\"]} has no description'
print(f'Contract OK: all {len(expected)} PuppetDB tools registered: {sorted(expected)}')
" 2>&1; then
  echo "FAIL: tool registry missing expected PuppetDB tools"
  PASS=false
fi

echo ""
if $PASS; then
  echo "PASS: tool registry contract verified"
else
  echo "FAIL: tool registry contract violations detected"
  exit 1
fi
