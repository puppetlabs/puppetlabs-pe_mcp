"""pytest-bdd runner for telemetry.feature."""

from __future__ import annotations

from typing import Any

import pytest
from fastmcp import Client, FastMCP
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from pytest_bdd import given, parsers, scenarios, then, when

from pe_mcp.core.errors import RateLimitedError
from pe_mcp.tests.features.conftest import FakePuppetDBClient, run_sync

FEATURE = "telemetry.feature"

pytestmark = pytest.mark.unit

scenarios(FEATURE)


@pytest.fixture
def tel_state() -> dict[str, Any]:
    return {}


@given("the MCP server is running with an OTel span recorder attached")
def _recorder_ready(span_recorder: InMemorySpanExporter, app: FastMCP) -> None:
    return None


@given(parsers.re(r"PE will respond to the next PuppetDB call with (?P<cond>.+)"))
def _seed_failure(cond: str, fake_puppetdb: FakePuppetDBClient) -> None:
    if "429" in cond:
        fake_puppetdb.queue_failure(RateLimitedError("PE rate-limited."))


@when("the MCP client calls node_lookup")
def _call_node_lookup(app: FastMCP, tel_state: dict[str, Any]) -> None:
    async def _run() -> Any:
        async with Client(app) as client:
            return await client.call_tool("node_lookup", {})

    tel_state["result"] = run_sync(_run())


@when(parsers.re(r'the MCP client calls pql_query with query "(?P<q>[^"]+)"'))
def _call_pql(q: str, app: FastMCP, tel_state: dict[str, Any]) -> None:
    async def _run() -> Any:
        async with Client(app) as client:
            return await client.call_tool("pql_query", {"query": q})

    tel_state["result"] = run_sync(_run())


@then("exactly one tool span is recorded")
def _assert_one_span(span_recorder: InMemorySpanExporter) -> None:
    tool_spans = [s for s in span_recorder.get_finished_spans() if s.name.startswith("tool.")]
    assert len(tool_spans) == 1, [s.name for s in span_recorder.get_finished_spans()]


@then(parsers.re(r'the span has attribute "(?P<key>[^"]+)": "(?P<val>[^"]+)"'))
def _assert_span_attr(key: str, val: str, span_recorder: InMemorySpanExporter) -> None:
    tool_spans = [s for s in span_recorder.get_finished_spans() if s.name.startswith("tool.")]
    assert tool_spans, "no tool spans recorded"
    assert tool_spans[0].attributes.get(key) == val, (
        f"expected {key}={val!r}, got {tool_spans[0].attributes}"
    )


@then("the span has a non-zero duration")
def _assert_duration(span_recorder: InMemorySpanExporter) -> None:
    for span in span_recorder.get_finished_spans():
        if span.name.startswith("tool."):
            assert span.end_time - span.start_time > 0


@then(parsers.re(r'the recorded span has status "(?P<status>[^"]+)"'))
def _assert_status(status: str, span_recorder: InMemorySpanExporter) -> None:
    tool_spans = [s for s in span_recorder.get_finished_spans() if s.name.startswith("tool.")]
    assert tool_spans, "no tool spans recorded"
    assert tool_spans[0].status.status_code.name == status
