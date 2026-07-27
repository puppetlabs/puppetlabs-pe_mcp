#!/usr/bin/env bash
set -euo pipefail
# Feature:  Reverse proxy (nginx) for TLS termination
# Channel:  systemd status + network socket + config syntax
# Contract: nginx is active, config is valid, port 443 is listening

echo "=== nginx service status ==="
systemctl is-active nginx && echo "PASS: nginx active" || { echo "FAIL: nginx not active"; exit 1; }

echo ""
echo "=== nginx config test ==="
nginx -t 2>&1

echo ""
echo "=== port 443 binding ==="
ss -tlnp | grep -q ':443' && echo "PASS: port 443 listening" || { echo "FAIL: port 443 not listening"; exit 1; }

echo ""
echo "=== smart-mcp site config ==="
cat /etc/nginx/sites-enabled/smart-mcp 2>/dev/null || echo "WARN: no smart-mcp site config found"
