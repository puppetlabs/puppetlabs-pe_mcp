#!/usr/bin/env bash
set -euo pipefail
# Feature:  Structured JSON logging via structlog TeeLogger
# Channel:  Log file at PE_MCP_LOG_FILE (default /var/log/smart-mcp/server.jsonl)
# Contract: JSON-lines with event, level, timestamp fields.
#           No fallback to journalctl — if the log file is missing, TeeLogger
#           is not deployed and that is a FAIL.

LOG_FILE="/var/log/smart-mcp/server.jsonl"

echo "=== Channel: log file at ${LOG_FILE} ==="

if [ ! -f "${LOG_FILE}" ]; then
  echo "FAIL: log file ${LOG_FILE} does not exist — TeeLogger not deployed"
  exit 1
fi

LINES=$(tail -20 "${LOG_FILE}" 2>/dev/null || true)

if [ -z "${LINES}" ]; then
  echo "FAIL: log file exists but is empty — no log entries found"
  exit 1
fi

echo "${LINES}" | tail -5
echo ""

JSON_COUNT=0
TOTAL=0
while IFS= read -r line; do
  [ -z "${line}" ] && continue
  TOTAL=$((TOTAL + 1))
  if echo "${line}" | python3 -c "import sys,json; json.load(sys.stdin)" 2>/dev/null; then
    JSON_COUNT=$((JSON_COUNT + 1))
  fi
done <<< "${LINES}"

echo "Checked ${TOTAL} lines, ${JSON_COUNT} valid JSON"
echo ""

if [ "${JSON_COUNT}" -eq 0 ]; then
  echo "FAIL: no JSON log lines found — server is not using structlog"
  exit 1
fi

SAMPLE=$(echo "${LINES}" | grep -m1 '{' || true)
if echo "${SAMPLE}" | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'event' in d and 'level' in d and 'timestamp' in d" 2>/dev/null; then
  echo "PASS: structured JSON logging with event/level/timestamp fields"
else
  echo "FAIL: JSON lines present but missing required contract fields (event, level, timestamp)"
  exit 1
fi
