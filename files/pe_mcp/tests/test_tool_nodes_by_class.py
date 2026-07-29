"""Unit tests for the puppet_nodes_by_class tool handler."""

from __future__ import annotations

from pe_mcp.core.errors import ErrorEnvelope, ToolInternalError
from pe_mcp.tools import puppet_nodes_by_class as tool
from pe_mcp.tests.support import FakePuppetDBClient, make_deps, run_sync


def test_success_with_environment_breakdown_and_dedup() -> None:
    puppetdb = FakePuppetDBClient()
    puppetdb.set_query_results([
        {"certname": "b", "environment": "production"},
        {"certname": "a", "environment": "production"},
        {"certname": "a", "environment": "production"},  # dup, should collapse
        {"certname": "c", "environment": None},  # unknown env
    ])
    deps = make_deps(puppetdb)
    result = run_sync(tool.handle(deps, tool.NodesByClassInput(class_title="profile::nginx")))
    assert isinstance(result, tool.NodesByClassResult)
    assert result.class_title == "Profile::Nginx"
    assert result.certnames == ["a", "b", "c"]
    assert result.count == 3
    assert result.environment_breakdown == {"production": 2, "unknown": 1}


def test_invalid_class_title_is_request_error() -> None:
    deps = make_deps(FakePuppetDBClient())
    result = run_sync(tool.handle(deps, tool.NodesByClassInput(class_title="not valid!!")))
    assert isinstance(result, ErrorEnvelope)
    assert "does not normalize" in result.message


def test_upstream_error_returns_envelope() -> None:
    puppetdb = FakePuppetDBClient()
    puppetdb.queue_failure(ToolInternalError("pdb down"))
    deps = make_deps(puppetdb)
    result = run_sync(tool.handle(deps, tool.NodesByClassInput(class_title="Ntp")))
    assert isinstance(result, ErrorEnvelope)


def test_row_with_empty_certname_skipped() -> None:
    puppetdb = FakePuppetDBClient()
    puppetdb.set_query_results([{"certname": "", "environment": "production"}])
    deps = make_deps(puppetdb)
    result = run_sync(tool.handle(deps, tool.NodesByClassInput(class_title="Ntp")))
    assert result.count == 0
