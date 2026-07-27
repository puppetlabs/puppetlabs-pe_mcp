# Audit Logging Verification

Verification scripts for the audit trail attribution feature (AC-09).

## Feature → Channel → Contract → Verify

| Feature | Channel | Contract | Script |
|---------|---------|----------|--------|
| Audit trail attribution | JSON-lines log file (`PE_MCP_LOG_FILE`) | Each `audit_tool_invocation` event has `tool`, `actor`, `outcome`, `trace_id`, `audit_ts` | `01-check-audit-events.sh` |

## Prerequisites

- The pe_mcp server must be deployed and have handled at least one tool invocation.
- The JSON-lines log file must exist at the path configured by `PE_MCP_LOG_FILE` (default: `/var/log/smart-mcp/server.jsonl`).
- `python3` must be available on the target node.

## Usage

```bash
# Run locally (uses default log path)
./scripts/07-verify-audit-logging/01-check-audit-events.sh

# Override log file path
PE_MCP_LOG_FILE=/tmp/server.jsonl ./scripts/07-verify-audit-logging/01-check-audit-events.sh

# Require at least 5 audit events
MIN_AUDIT_EVENTS=5 ./scripts/07-verify-audit-logging/01-check-audit-events.sh
```

## How it works

The script reads the JSON-lines log file, filters for lines with `"event": "audit_tool_invocation"`, and validates that every audit event contains the required fields with valid values. It does not fall back to journalctl, grep for source code, or inspect implementation details.

See `docs/explanation_ucf_feature_testability_design.md` for the design rationale behind this approach.
