#!/usr/bin/env bash
set -euo pipefail
# Feature:  UCF ErrorEnvelope for categorized error responses
# Channel:  MCP protocol response (JSON-RPC tools/call)
# Contract: Error response contains error_type, message, retryable fields.
#           The old server returned bare error strings; UCF uses ErrorEnvelope.
#
# Requires: scripts/lib/mcp-session.sh concatenated ahead of this script.
# Run:  cat scripts/lib/mcp-session.sh scripts/01-verify-mcp-server/12-check-error-envelopes.sh | bolt command run - --targets=pe_mcp

echo "=== error-envelopes: Feature -> Channel -> Contract -> Verify ==="
echo "Establishing MCP session..."
mcp_session_init

echo ""
echo "=== Call non-existent tool (natural error path) ==="
ERROR_RESULT=$(mcp_call "__test_nonexistent_tool" '{}')
echo "${ERROR_RESULT}"
echo ""

echo "${ERROR_RESULT}" | python3 -c "
import sys, json, re

raw = sys.stdin.read()
json_str = raw.strip()
sse_match = re.search(r'^data:\s*(\{.*\})\s*$', raw, re.MULTILINE)
if sse_match:
    json_str = sse_match.group(1)

try:
    data = json.loads(json_str)
except json.JSONDecodeError:
    print('FAIL: could not parse MCP response as JSON')
    sys.exit(1)

if 'error' in data:
    err_msg = str(data['error'].get('message', ''))
    err_data = str(data['error'].get('data', ''))
    combined = err_msg + err_data
    if 'error_type' in combined and 'retryable' in combined:
        print('PASS: error envelope fields (error_type, retryable) found in JSON-RPC error')
        sys.exit(0)
    print('FAIL: JSON-RPC error returned but missing ErrorEnvelope contract fields (error_type, message, retryable)')
    sys.exit(1)

result = data.get('result', {})
if result.get('isError', False):
    content = result.get('content', [{}])
    for c in content:
        text = c.get('text', '')
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict) and 'error_type' in parsed and 'message' in parsed and 'retryable' in parsed:
                print('PASS: ErrorEnvelope contract verified — error_type=' + str(parsed['error_type']) + ', retryable=' + str(parsed['retryable']))
                sys.exit(0)
        except (json.JSONDecodeError, TypeError):
            pass
        if 'error_type' in text and 'retryable' in text:
            print('PASS: ErrorEnvelope contract fields found in error text')
            sys.exit(0)
    print('FAIL: isError=true but response missing ErrorEnvelope contract fields (error_type, message, retryable)')
    sys.exit(1)

print('FAIL: non-existent tool call did not return an error response')
sys.exit(1)
"

echo ""
echo "PASS: UCF error envelope contract verified"
