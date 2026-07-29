"""pytest-bdd runner for audit_logging.feature."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
from fastmcp import Client, FastMCP
from pytest_bdd import given, parsers, scenarios, then, when

from pe_mcp.core.errors import NotFoundError
from pe_mcp.tests.features.conftest import FakePuppetDBClient, run_sync

FEATURE = "audit_logging.feature"

pytestmark = pytest.mark.unit

scenarios(FEATURE)


@pytest.fixture
def audit_state() -> dict[str, Any]:
    return {"audit_events": []}


@pytest.fixture(autouse=True)
def _capture_audit_events(audit_state: dict[str, Any]):
    # server.py does `from pe_mcp.core.audit import emit_audit_event`, binding
    # its own module-level name — patching pe_mcp.core.audit.emit_audit_event
    # doesn't affect that already-imported reference, so patch it where it's
    # actually looked up: pe_mcp.server.emit_audit_event.
    import pe_mcp.server as server_mod
    original = server_mod.emit_audit_event

    def capture(logger, *, tool, actor, outcome, trace_id, **extra):
        audit_state["audit_events"].append({
            "tool": tool,
            "actor": actor,
            "outcome": outcome,
            "trace_id": trace_id,
            **extra,
        })
        return original(logger, tool=tool, actor=actor, outcome=outcome, trace_id=trace_id, **extra)

    with patch.object(server_mod, "emit_audit_event", side_effect=capture):
        yield


@given("the MCP server is started with audit logging enabled")
def _started(app: FastMCP) -> None:
    return None


@given(parsers.re(r"PE will respond to the next PuppetDB call with (?P<cond>.+)"))
def _seed_failure(cond: str, fake_puppetdb: FakePuppetDBClient) -> None:
    if "404" in cond:
        fake_puppetdb.queue_failure(NotFoundError("PE returned 404."))


@when("the MCP client calls puppet_node_lookup")
def _call_puppet_node_lookup(app: FastMCP, audit_state: dict[str, Any]) -> None:
    async def _run() -> Any:
        async with Client(app) as client:
            return await client.call_tool("puppet_node_lookup", {})

    audit_state["result"] = run_sync(_run())


@then(parsers.re(
    r'an audit event is emitted with tool "(?P<tool>[^"]+)" and outcome "(?P<outcome>[^"]+)"'
))
def _assert_audit_event(tool: str, outcome: str, audit_state: dict[str, Any]) -> None:
    events = audit_state["audit_events"]
    matching = [e for e in events if e["tool"] == tool and e["outcome"] == outcome]
    assert matching, f"no audit event with tool={tool!r} outcome={outcome!r}, got {events}"


@then("the audit event contains a non-empty trace_id")
def _assert_trace_id(audit_state: dict[str, Any]) -> None:
    events = audit_state["audit_events"]
    assert events, "no audit events recorded"
    assert events[-1]["trace_id"], f"empty trace_id in {events[-1]}"


@then(parsers.re(r'the audit event actor is not "(?P<forbidden>[^"]+)"'))
def _assert_actor_not(forbidden: str, audit_state: dict[str, Any]) -> None:
    events = audit_state["audit_events"]
    assert events, "no audit events recorded"
    actor = events[-1]["actor"]
    assert actor != forbidden, f"actor is {forbidden!r} — identity not bound"


@given(parsers.re(
    r'the request includes header "(?P<header>[^"]+)" with value "(?P<value>[^"]+)"'
))
def _set_caller_header(header: str, value: str) -> None:
    from pe_mcp.core.audit import set_request_caller
    set_request_caller(value)


@then(parsers.re(r'the audit event actor is "(?P<expected>[^"]+)"'))
def _assert_actor_is(expected: str, audit_state: dict[str, Any]) -> None:
    events = audit_state["audit_events"]
    assert events, "no audit events recorded"
    actor = events[-1]["actor"]
    assert actor == expected, f"expected actor {expected!r}, got {actor!r}"
