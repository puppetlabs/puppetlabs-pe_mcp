#!/usr/bin/env python3
"""Bolt task: generate a PE RBAC token on the primary server.

Equivalent curl:
  curl -sk https://localhost:4433/rbac-api/v1/auth/token \
    -X POST -H "Content-Type: application/json" \
    -d '{"login":"admin","password":"<password>","lifetime":"7d"}'

Response (JSON): {"token": "<rbac-token-string>"}
"""

import json
import os
import ssl
import sys
import urllib.request

def main():
    password = os.environ.get("PT_admin_password")
    lifetime = os.environ.get("PT_lifetime", "7d")

    if not password:
        print(json.dumps({"_error": {"msg": "PT_admin_password not set", "kind": "task-error"}}))
        sys.exit(1)

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    payload = json.dumps({"login": "admin", "password": password, "lifetime": lifetime}).encode()
    req = urllib.request.Request(
        "https://localhost:4433/rbac-api/v1/auth/token",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, context=ctx) as resp:
            body = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode(errors="replace")
        try:
            detail = json.loads(error_body)
            msg = detail.get("display-name") or detail.get("msg") or detail.get("message") or error_body
        except (json.JSONDecodeError, AttributeError):
            msg = error_body
        print(json.dumps({"_error": {"msg": f"RBAC API {e.code}: {msg}", "kind": "task-error"}}))
        sys.exit(1)
    except urllib.error.URLError as e:
        print(json.dumps({"_error": {"msg": f"Cannot reach RBAC API: {e.reason}", "kind": "task-error"}}))
        sys.exit(1)

    if "token" not in body:
        print(json.dumps({"_error": {"msg": f"No token in response: {json.dumps(body)}", "kind": "task-error"}}))
        sys.exit(1)

    print(json.dumps({"token": body["token"]}))

if __name__ == "__main__":
    main()
