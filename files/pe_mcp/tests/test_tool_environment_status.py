"""Unit tests for the puppet_environment_status tool handler."""

from __future__ import annotations

from pe_mcp.core.errors import ErrorEnvelope, ToolInternalError
from pe_mcp.tools import puppet_environment_status as tool
from pe_mcp.tests.support import FakePuppetDBClient, make_deps, run_sync


def test_success_sorted_and_filters_bad_rows() -> None:
    puppetdb = FakePuppetDBClient()
    puppetdb.set_query_results([
        {"environment": "production", "max": "2026-07-29T10:00:00Z"},
        {"environment": "staging", "max": 12345},  # non-string max -> None
        {"environment": "", "max": "2026-07-29T10:00:00Z"},  # skipped
        {"environment": None, "max": "x"},  # skipped
    ])
    deps = make_deps(puppetdb)
    result = run_sync(tool.handle(deps, tool.EnvironmentStatusInput()))
    assert isinstance(result, tool.EnvironmentStatusResult)
    assert result.count == 2
    assert [e.environment for e in result.environments] == ["production", "staging"]
    assert result.environments[1].latest_report_time is None


def test_upstream_error_returns_envelope() -> None:
    puppetdb = FakePuppetDBClient()
    puppetdb.queue_failure(ToolInternalError("pdb down"))
    deps = make_deps(puppetdb)
    result = run_sync(tool.handle(deps, tool.EnvironmentStatusInput()))
    assert isinstance(result, ErrorEnvelope)
