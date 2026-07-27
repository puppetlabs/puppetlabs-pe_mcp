#!/usr/bin/env bash
set -euo pipefail

# Bolt task: generate PE RBAC token on the primary server.
# Parameters (via environment): PT_admin_password, PT_lifetime

LIFETIME="${PT_lifetime:-7d}"

RESPONSE=$(curl -sk https://localhost:4433/rbac-api/v1/auth/token \
  -X POST \
  -H "Content-Type: application/json" \
  -d "{\"login\":\"admin\",\"password\":\"${PT_admin_password}\",\"lifetime\":\"${LIFETIME}\"}")

echo "$RESPONSE" | python3 -c "
import sys, json
resp = json.load(sys.stdin)
if 'token' not in resp:
    msg = resp.get('msg', resp.get('message', json.dumps(resp)))
    print(json.dumps({'_error': {'msg': f'RBAC API error: {msg}', 'kind': 'task-error'}}))
    sys.exit(1)
print(json.dumps({'token': resp['token']}))
"
