"""Audit trail attribution for tool invocations (AC-09).

Emits structured audit events with caller identity, tool name, outcome,
trace_id, and ISO timestamp to the structlog JSON log stream.
"""

from __future__ import annotations

import contextvars
from datetime import datetime, timezone

import structlog

_request_caller_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "pe_mcp_caller_id", default="",
)


def set_request_caller(caller_id: str) -> None:
    """Set the caller identity for the current execution context."""
    _request_caller_id.set(caller_id)


def get_actor() -> str:
    """Return the caller identity for the current request.

    Checks (in order): the per-request ContextVar (set by middleware or
    startup), then structlog contextvars, then falls back to ``"unknown"``.
    """
    cv = _request_caller_id.get()
    if cv:
        return cv
    ctx = structlog.contextvars.get_contextvars()
    return ctx.get("caller_id", "unknown")


def emit_audit_event(
    logger: structlog.stdlib.BoundLogger,
    *,
    tool: str,
    actor: str,
    outcome: str,
    trace_id: str,
    **extra: object,
) -> None:
    """Emit a structured audit log event for a tool invocation."""
    logger.info(
        "audit_tool_invocation",
        tool=tool,
        actor=actor,
        outcome=outcome,
        trace_id=trace_id,
        audit_ts=datetime.now(timezone.utc).isoformat(),
        **extra,
    )
