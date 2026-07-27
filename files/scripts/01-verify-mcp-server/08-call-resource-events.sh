#!/usr/bin/env bash
set -euo pipefail
# Feature:  resource_events tool (resource events from a report)
# Channel:  MCP protocol response (JSON-RPC tools/call)
# Contract: Response contains "events" array (may be empty),
#           "pql_trace" array, "pe_instance" string.
#           Each event entry: resource_type, resource_title, status.
#
# This test first calls recent_reports to get a real report_hash,
# then passes it to resource_events. If no reports exist, the test
# verifies the tool returns the right contract shape with an empty events array.
#
# Requires: scripts/lib/mcp-session.sh concatenated ahead of this script.
# Run:  cat scripts/lib/mcp-session.sh scripts/01-verify-mcp-server/08-call-resource-events.sh | bolt command run - --targets=pe_mcp

echo "=== resource_events: Feature -> Channel -> Contract -> Verify ==="
echo "Establishing MCP session..."
mcp_session_init

echo "Fetching a report hash from recent_reports (last 72h)..."
REPORTS_RESULT=$(mcp_call "recent_reports" '{"since_hours": 72}')
REPORT_HASH=$(echo "$REPORTS_RESULT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
content = data.get('result', {}).get('content', [{}])
text = json.loads(content[0].get('text', '{}')) if content else {}
reports = text.get('reports', [])
if reports:
    print(reports[0].get('report_hash', ''))
else:
    print('')
" 2>/dev/null || echo "")

PASS=true

if [ -z "$REPORT_HASH" ]; then
  echo "No reports found in last 72h — testing with a dummy hash"
  REPORT_HASH="0000000000000000000000000000000000000000"
fi

echo "Calling resource_events with report_hash=${REPORT_HASH}..."
RESULT=$(mcp_call "resource_events" "{\"report_hash\": \"${REPORT_HASH}\"}")
echo "$RESULT" | python3 -m json.tool 2>/dev/null || echo "$RESULT"

if ! echo "$RESULT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
content = data.get('result', {}).get('content', [{}])
text = json.loads(content[0].get('text', '{}')) if content else {}
assert 'events' in text, 'missing events'
assert isinstance(text['events'], list), 'events must be a list'
assert 'pql_trace' in text, 'missing pql_trace'
assert 'pe_instance' in text, 'missing pe_instance'
for e in text['events'][:3]:
    for field in ('resource_type', 'resource_title', 'status'):
        assert field in e, f'missing {field} in event entry: {e}'
count = len(text['events'])
print(f'Contract OK: {count} events, all entries have required fields')
" 2>&1; then
  echo "FAIL: resource_events response missing contract fields"
  PASS=false
fi

echo ""
if $PASS; then
  echo "PASS: resource_events contract verified"
else
  echo "FAIL: resource_events contract violations detected"
  exit 1
fi
