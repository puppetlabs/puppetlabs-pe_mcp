"""pytest-bdd runner for error_handling.feature."""

from __future__ import annotations

from typing import Any

import pytest
from fastmcp import Client, FastMCP
from pytest_bdd import given, parsers, scenarios, then, when

from pe_mcp.core.errors import (
    NotFoundError,
    RateLimitedError,
    TimeoutUpstreamError,
    ToolInternalError,
    UpstreamError,
)
from pe_mcp.tests.features.conftest import FakePuppetDBClient, run_sync

FEATURE = "error_handling.feature"

pytestmark = pytest.mark.unit

scenarios(FEATURE)

_TOOL_DEFAULT_ARGS: dict[str, dict[str, Any]] = {
    "node_lookup": {},
    "pql_query": {"query": "nodes {}"},
    "recent_reports": {},
    "resource_events": {"report_hash": "deadbeef"},
    "impact_scope": {"puppet_class": "profile::nginx"},
}


def _exception_for(upstream_condition: str) -> UpstreamError:
    condition = upstream_condition.lower()
    if "404" in condition:
        return NotFoundError("PE returned 404.")
    if "429" in condition:
        return RateLimitedError("PE rate-limited.")
    if "503" in condition:
        return ToolInternalError("PE 503 after retry.")
    if "connection reset" in condition:
        return TimeoutUpstreamError("Connection reset mid-response.")
    return ToolInternalError("PE returned unexpected response.")


@pytest.fixture
def state() -> dict[str, Any]:
    return {}


@given(parsers.re(r"PE will respond to the next PuppetDB call with (?P<cond>.+)"))
def _seed_failure(cond: str, fake_puppetdb: FakePuppetDBClient, state: dict[str, Any]) -> None:
    state["next_exception"] = _exception_for(cond)
    fake_puppetdb.queue_failure(state["next_exception"])


@given("the MCP server is started with mock PE backends")
def _started(app: FastMCP) -> None:
    return None


@when(parsers.re(r"the MCP client calls (?P<tool>\w+)"))
def _call_tool(tool: str, app: FastMCP, state: dict[str, Any]) -> None:
    args = _TOOL_DEFAULT_ARGS.get(tool, {})

    async def _run() -> Any:
        async with Client(app) as client:
            return await client.call_tool(tool, args)

    try:
        state["result"] = run_sync(_run())
    except Exception as exc:
        state["result_error"] = exc


@when("multiple tool invocations are made with various failure modes")
def _bulk_calls(
    fake_puppetdb: FakePuppetDBClient, app: FastMCP, state: dict[str, Any],
) -> None:
    conditions = ["HTTP 404", "HTTP 429", "HTTP 503", "connection reset mid-response"]
    tools = list(_TOOL_DEFAULT_ARGS.keys())
    results: list[Any] = []

    async def _run() -> None:
        async with Client(app) as client:
            for cond in conditions:
                for tool in tools:
                    fake_puppetdb.queue_failure(_exception_for(cond))
                    args = _TOOL_DEFAULT_ARGS.get(tool, {})
                    result = await client.call_tool(tool, args)
                    results.append(result)

    run_sync(_run())
    state["bulk_results"] = results


@then(parsers.re(r'the response is an error with "error_type": "(?P<et>[^"]+)"'))
def _assert_error_type(et: str, state: dict[str, Any]) -> None:
    result = state["result"]
    if hasattr(result, "content"):
        import json
        for item in result.content:
            text = getattr(item, "text", None) or str(item)
            try:
                data = json.loads(text)
                assert data["error_type"] == et, data
                return
            except (json.JSONDecodeError, KeyError, TypeError):
                continue
    assert False, f"Could not find error_type in result: {result}"


@then("the error message contains only curated text")
def _assert_curated(state: dict[str, Any]) -> None:
    result = state["result"]
    import json
    for item in result.content:
        text = getattr(item, "text", None) or str(item)
        try:
            data = json.loads(text)
            msg = data.get("message", "")
            assert "Traceback" not in msg
            return
        except (json.JSONDecodeError, TypeError):
            continue


@then(
    'every error response\'s "error_type" value is one of '
    '"timeout", "auth_failed", "rate_limited", "not_found", "tool_error"'
)
def _assert_categories(state: dict[str, Any]) -> None:
    allowed = {"timeout", "auth_failed", "rate_limited", "not_found", "tool_error"}
    import json
    for result in state["bulk_results"]:
        for item in result.content:
            text = getattr(item, "text", None) or str(item)
            try:
                data = json.loads(text)
                if "error_type" in data:
                    assert data["error_type"] in allowed, data
            except (json.JSONDecodeError, TypeError):
                continue
