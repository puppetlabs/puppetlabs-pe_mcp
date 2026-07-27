#!/usr/bin/env bash
set -euo pipefail
# Feature:  Audit trail attribution logging (AC-09)
# Channel:  JSON-lines log file at PE_MCP_LOG_FILE (default /var/log/smart-mcp/server.jsonl)
# Contract: Each audit event line must contain:
#             "event": "audit_tool_invocation"
#             "tool":      non-empty string
#             "actor":     non-empty string
#             "outcome":   "success" or "error"
#             "trace_id":  non-empty string
#             "audit_ts":  non-empty ISO-8601 timestamp
#           No fallbacks to journalctl, grep, or code inspection.

LOG_FILE="${PE_MCP_LOG_FILE:-/var/log/smart-mcp/server.jsonl}"
MIN_EVENTS="${MIN_AUDIT_EVENTS:-1}"

echo "=== Feature: Audit trail attribution (AC-09) ==="
echo "=== Channel: log file at ${LOG_FILE} ==="
echo ""

if [ ! -f "${LOG_FILE}" ]; then
  echo "FAIL: log file ${LOG_FILE} does not exist — audit logging not deployed"
  exit 1
fi

AUDIT_LINES=$(python3 -c "
import json, sys
with open('${LOG_FILE}') as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if d.get('event') == 'audit_tool_invocation':
            print(line)
" 2>/dev/null || true)

if [ -z "${AUDIT_LINES}" ]; then
  echo "FAIL: no audit_tool_invocation events found in ${LOG_FILE}"
  echo "      The audit logging feature is either not deployed or has not recorded any tool invocations."
  exit 1
fi

EVENT_COUNT=$(echo "${AUDIT_LINES}" | wc -l | tr -d ' ')
echo "Found ${EVENT_COUNT} audit event(s)"
echo ""

if [ "${EVENT_COUNT}" -lt "${MIN_EVENTS}" ]; then
  echo "FAIL: expected at least ${MIN_EVENTS} audit event(s), found ${EVENT_COUNT}"
  exit 1
fi

REQUIRED_FIELDS="tool actor outcome trace_id audit_ts"
FAIL_COUNT=0
CHECKED=0

while IFS= read -r line; do
  [ -z "${line}" ] && continue
  CHECKED=$((CHECKED + 1))

  RESULT=$(python3 -c "
import json, sys

line = sys.stdin.read().strip()
d = json.loads(line)

required = ['tool', 'actor', 'outcome', 'trace_id', 'audit_ts']
missing = [f for f in required if not d.get(f)]
if missing:
    print('MISSING:' + ','.join(missing))
    sys.exit(0)

actor = d['actor']
if actor == 'unknown':
    print('UNKNOWN_ACTOR')
    sys.exit(0)

outcome = d['outcome']
if outcome not in ('success', 'error'):
    print('BAD_OUTCOME:' + outcome)
    sys.exit(0)

print('OK')
" <<< "${line}" 2>/dev/null || echo "PARSE_ERROR")

  case "${RESULT}" in
    OK)
      ;;
    MISSING:*)
      FIELDS="${RESULT#MISSING:}"
      echo "FAIL: audit event #${CHECKED} missing required fields: ${FIELDS}"
      FAIL_COUNT=$((FAIL_COUNT + 1))
      ;;
    UNKNOWN_ACTOR)
      echo "FAIL: audit event #${CHECKED} has actor 'unknown' — caller identity not bound"
      FAIL_COUNT=$((FAIL_COUNT + 1))
      ;;
    BAD_OUTCOME:*)
      VALUE="${RESULT#BAD_OUTCOME:}"
      echo "FAIL: audit event #${CHECKED} has invalid outcome '${VALUE}' (expected 'success' or 'error')"
      FAIL_COUNT=$((FAIL_COUNT + 1))
      ;;
    PARSE_ERROR)
      echo "FAIL: audit event #${CHECKED} could not be parsed as JSON"
      FAIL_COUNT=$((FAIL_COUNT + 1))
      ;;
  esac
done <<< "${AUDIT_LINES}"

echo ""
echo "Validated ${CHECKED} audit event(s), ${FAIL_COUNT} failure(s)"
echo ""

if [ "${FAIL_COUNT}" -gt 0 ]; then
  echo "FAIL: ${FAIL_COUNT} audit event(s) did not meet the contract"
  exit 1
fi

echo "Sample audit event:"
echo "${AUDIT_LINES}" | tail -1 | python3 -c "import json,sys; print(json.dumps(json.load(sys.stdin), indent=2))" 2>/dev/null || echo "${AUDIT_LINES}" | tail -1
echo ""

echo "PASS: audit trail attribution — all ${CHECKED} event(s) contain tool, actor, outcome, trace_id, audit_ts"
