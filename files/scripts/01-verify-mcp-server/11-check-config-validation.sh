#!/usr/bin/env bash
set -euo pipefail
# Feature:  Pydantic-settings config validation at startup
# Channel:  Exit code + stderr from main() entrypoint
# Contract: exit code 2 + stderr contains "config validation failed"

VENV="/opt/smart-mcp/venv"
PYTHON="${VENV}/bin/python"
INSTALL_DIR="/opt/smart-mcp"

if [ ! -x "${PYTHON}" ]; then
  echo "FAIL: python not found at ${PYTHON}"
  exit 1
fi

if [ ! -f "${INSTALL_DIR}/pe_mcp/server.py" ]; then
  echo "FAIL: pe_mcp/server.py not found at ${INSTALL_DIR}/pe_mcp/server.py"
  exit 1
fi

echo "=== Test: main() entrypoint exits with code 2 on bad config ==="
set +e
STDERR=$(PE_MCP_PORT=not_a_number PE_MCP_RBAC_TOKEN=dummy PE_MCP_LOG_FILE="" PYTHONPATH="${INSTALL_DIR}" "${PYTHON}" -c "
from pe_mcp.server import main
import sys
sys.exit(main())
" 2>&1 1>/dev/null)
EXIT_CODE=$?
set -e

echo "Exit code: ${EXIT_CODE}"
echo "Stderr: ${STDERR}" | head -5
echo ""

if [ "${EXIT_CODE}" -ne 2 ]; then
  echo "FAIL: main() exited ${EXIT_CODE}, expected exit code 2 on invalid config"
  exit 1
fi

if echo "${STDERR}" | grep -q "config validation failed"; then
  echo "PASS: main() exits 2 with structured validation error"
else
  echo "FAIL: main() exits 2 but stderr missing 'config validation failed'"
  exit 1
fi
