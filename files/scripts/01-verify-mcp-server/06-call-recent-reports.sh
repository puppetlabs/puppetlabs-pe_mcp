#!/usr/bin/env bash
set -euo pipefail
# Feature:  recent_reports tool (filtered report roll-up)
# Channel:  MCP protocol response (JSON-RPC tools/call)
# Contract: Response contains "reports" array (may be empty),
#           "pql_trace" array, "pe_instance" string.
#           Each report entry must have: certname, status, environment,
#           end_time, report_hash.
#
# Requires: scripts/lib/mcp-session.sh concatenated ahead of this script.
# Run:  cat scripts/lib/mcp-session.sh scripts/01-verify-mcp-server/06-call-recent-reports.sh | bolt command run - --targets=pe_mcp

echo "=== recent_reports: Feature -> Channel -> Contract -> Verify ==="
echo "Establishing MCP session..."
mcp_session_init

echo "Calling recent_reports with defaults (last 24h)..."
RESULT=$(mcp_call "recent_reports" '{}')
echo "$RESULT" | python3 -m json.tool 2>/dev/null || echo "$RESULT"

PASS=true

if ! echo "$RESULT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
content = data.get('result', {}).get('content', [{}])
text = json.loads(content[0].get('text', '{}')) if content else {}
assert 'reports' in text, 'missing reports'
assert isinstance(text['reports'], list), 'reports must be a list'
assert 'pql_trace' in text, 'missing pql_trace'
assert 'pe_instance' in text, 'missing pe_instance'
for r in text['reports'][:3]:
    for field in ('certname', 'status', 'environment', 'end_time', 'report_hash'):
        assert field in r, f'missing {field} in report entry: {r}'
count = len(text['reports'])
print(f'Contract OK: {count} reports, all entries have required fields')
" 2>&1; then
  echo "FAIL: recent_reports response missing contract fields"
  PASS=false
fi

echo ""
if $PASS; then
  echo "PASS: recent_reports contract verified"
else
  echo "FAIL: recent_reports contract violations detected"
  exit 1
fi
