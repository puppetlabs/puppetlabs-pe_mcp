"""Unit tests for the puppet_comply_results tool handler."""

from __future__ import annotations

from pe_mcp.core.errors import ErrorEnvelope, ToolInternalError
from pe_mcp.tools import puppet_comply_results as tool
from pe_mcp.tests.support import FakePuppetDBClient, make_deps, run_sync


def test_no_filter_all_nodes() -> None:
    puppetdb = FakePuppetDBClient()
    puppetdb.set_query_results([
        {"certname": "b", "value": {"compliant": True, "scan_date": "2026-07-01", "profile": "cis-1"}},
        {"certname": "a", "value": {"compliant": False}},
    ])
    deps = make_deps(puppetdb)
    result = run_sync(tool.handle(deps, tool.ComplyResultsInput()))
    assert isinstance(result, tool.ComplyResultsResult)
    assert result.count == 2
    assert [r.certname for r in result.results] == ["a", "b"]
    assert result.results[1].profile == "cis-1"


def test_certnames_over_cap_is_request_error() -> None:
    deps = make_deps(FakePuppetDBClient())
    too_many = [f"node{i}" for i in range(501)]
    result = run_sync(tool.handle(deps, tool.ComplyResultsInput(certnames=too_many)))
    assert isinstance(result, ErrorEnvelope)
    assert "exceeds cap" in result.message


def test_unsafe_certname_is_request_error() -> None:
    deps = make_deps(FakePuppetDBClient())
    result = run_sync(tool.handle(deps, tool.ComplyResultsInput(certnames=["bad\nname"])))
    assert isinstance(result, ErrorEnvelope)
    assert "PQL literal grammar" in result.message


def test_upstream_error_returns_envelope() -> None:
    puppetdb = FakePuppetDBClient()
    puppetdb.queue_failure(ToolInternalError("comply not installed"))
    deps = make_deps(puppetdb)
    result = run_sync(tool.handle(deps, tool.ComplyResultsInput()))
    assert isinstance(result, ErrorEnvelope)


def test_non_dict_value_row_still_included() -> None:
    puppetdb = FakePuppetDBClient()
    puppetdb.set_query_results([{"certname": "a", "value": "not-a-dict"}])
    deps = make_deps(puppetdb)
    result = run_sync(tool.handle(deps, tool.ComplyResultsInput(certnames=["a"])))
    assert result.count == 1
    assert result.results[0].compliant is None


def test_row_with_non_string_certname_skipped() -> None:
    puppetdb = FakePuppetDBClient()
    puppetdb.set_query_results([{"certname": 123, "value": {}}])
    deps = make_deps(puppetdb)
    result = run_sync(tool.handle(deps, tool.ComplyResultsInput()))
    assert result.count == 0
