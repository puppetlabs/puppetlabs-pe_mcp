#!/usr/bin/env bash
set -euo pipefail
# Feature:  smart-mcp systemd service
# Channel:  systemd status + network socket
# Contract: service is active, port 8200 is listening

echo "=== smart-mcp service status ==="
systemctl is-active smart-mcp && echo "PASS: service active" || { echo "FAIL: service not active"; exit 1; }

echo ""
echo "=== port 8200 binding ==="
ss -tlnp | grep -q ':8200' && echo "PASS: port 8200 listening" || { echo "FAIL: port 8200 not listening"; exit 1; }

echo ""
echo "=== recent logs (last 10 lines) ==="
journalctl -u smart-mcp --no-pager -n 10 2>/dev/null || echo "(no journal entries)"
