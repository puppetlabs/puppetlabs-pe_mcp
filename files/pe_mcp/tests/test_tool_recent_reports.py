"""Unit tests for the puppet_recent_reports tool handler (extra edge cases)."""

from __future__ import annotations

from pe_mcp.core.errors import ErrorEnvelope, ToolInternalError
from pe_mcp.tools import puppet_recent_reports as tool
from pe_mcp.tests.support import FakePuppetDBClient, make_deps, run_sync


def test_success_with_all_filters_set() -> None:
    puppetdb = FakePuppetDBClient()
    puppetdb.set_query_results([
        {"certname": "a", "status": "failed", "environment": "production", "end_time": "t", "hash": "h1"},
    ])
    deps = make_deps(puppetdb)
    result = run_sync(
        tool.handle(
            deps,
            tool.RecentReportsInput(
                certname="a", environment="production", status="failed", since_hours=48,
            ),
        )
    )
    assert isinstance(result, tool.RecentReportsResult)
    assert len(result.reports) == 1
    assert result.note is None
    assert 'certname = "a"' in puppetdb.last_pql
    assert 'environment = "production"' in puppetdb.last_pql
    assert 'status = "failed"' in puppetdb.last_pql


def test_no_reports_sets_note() -> None:
    puppetdb = FakePuppetDBClient()
    puppetdb.set_query_results([])
    deps = make_deps(puppetdb)
    result = run_sync(tool.handle(deps, tool.RecentReportsInput()))
    assert result.note == "No reports matched the filter."


def test_upstream_error_returns_envelope() -> None:
    puppetdb = FakePuppetDBClient()
    puppetdb.queue_failure(ToolInternalError("pdb down"))
    deps = make_deps(puppetdb)
    result = run_sync(tool.handle(deps, tool.RecentReportsInput()))
    assert isinstance(result, ErrorEnvelope)


def test_missing_fields_default_to_empty_string() -> None:
    puppetdb = FakePuppetDBClient()
    puppetdb.set_query_results([{"certname": None}])
    deps = make_deps(puppetdb)
    result = run_sync(tool.handle(deps, tool.RecentReportsInput()))
    assert result.reports[0].certname == ""
    assert result.reports[0].status == ""
