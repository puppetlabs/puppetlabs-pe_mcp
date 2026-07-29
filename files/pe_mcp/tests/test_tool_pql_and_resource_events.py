"""Unit tests closing small gaps in puppet_pql_query / puppet_resource_events."""

from __future__ import annotations

from pe_mcp.core.errors import ErrorEnvelope, ToolInternalError
from pe_mcp.tools import puppet_pql_query, puppet_resource_events
from pe_mcp.tests.support import FakePuppetDBClient, make_deps, run_sync


def test_pql_query_upstream_error_returns_envelope() -> None:
    puppetdb = FakePuppetDBClient()
    puppetdb.queue_failure(ToolInternalError("pdb down"))
    deps = make_deps(puppetdb)
    result = run_sync(
        puppet_pql_query.handle(deps, puppet_pql_query.PQLQueryInput(query="nodes[]{}"))
    )
    assert isinstance(result, ErrorEnvelope)


def test_pql_query_success_echoes_query_and_rows() -> None:
    puppetdb = FakePuppetDBClient()
    puppetdb.set_query_results([{"certname": "web01"}])
    deps = make_deps(puppetdb, row_cap=1000)
    result = run_sync(
        puppet_pql_query.handle(
            deps, puppet_pql_query.PQLQueryInput(query="nodes[certname]{}"),
        )
    )
    assert isinstance(result, puppet_pql_query.PQLQueryResult)
    assert result.pql == "nodes[certname]{}"
    assert result.rows == [{"certname": "web01"}]
    assert result.truncated is False
    assert result.pe_instance == "test"


def test_resource_events_success_and_status_default() -> None:
    puppetdb = FakePuppetDBClient()
    puppetdb.set_query_results([
        {"resource_type": "Package", "resource_title": "nginx", "status": "failure",
         "message": "boom", "file": "/etc/x.pp", "line": 12},
        {"resource_type": 1, "resource_title": None, "status": None,
         "message": 2, "file": 3, "line": "not-an-int"},
    ])
    deps = make_deps(puppetdb)
    result = run_sync(
        puppet_resource_events.handle(
            deps, puppet_resource_events.ResourceEventsInput(report_hash="abc123"),
        )
    )
    assert isinstance(result, puppet_resource_events.ResourceEventsResult)
    assert len(result.events) == 2
    assert result.events[0].line == 12
    assert result.events[1].line is None
    assert 'status = "failure"' in puppetdb.last_pql
    assert result.note is None


def test_resource_events_no_status_filter_uses_true_clause() -> None:
    puppetdb = FakePuppetDBClient()
    puppetdb.set_query_results([])
    deps = make_deps(puppetdb)
    result = run_sync(
        puppet_resource_events.handle(
            deps,
            puppet_resource_events.ResourceEventsInput(report_hash="abc123", status=None),
        )
    )
    assert "true" in puppetdb.last_pql
    assert result.note == "No resource events matched the filter."


def test_resource_events_upstream_error_returns_envelope() -> None:
    puppetdb = FakePuppetDBClient()
    puppetdb.queue_failure(ToolInternalError("pdb down"))
    deps = make_deps(puppetdb)
    result = run_sync(
        puppet_resource_events.handle(
            deps, puppet_resource_events.ResourceEventsInput(report_hash="abc123"),
        )
    )
    assert isinstance(result, ErrorEnvelope)
