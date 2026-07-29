"""Unit tests for the puppet_infrastructure_map tool handler."""

from __future__ import annotations

from pe_mcp.core.errors import ErrorEnvelope, ToolInternalError
from pe_mcp.tools import puppet_infrastructure_map as tool
from pe_mcp.tests.support import FakePuppetDBClient, make_deps, run_sync


def test_no_nodes_found() -> None:
    puppetdb = FakePuppetDBClient()
    puppetdb.set_query_results([])
    deps = make_deps(puppetdb)
    result = run_sync(tool.handle(deps, tool.InfrastructureMapInput()))
    assert isinstance(result, tool.InfrastructureMapResult)
    assert result.node_count == 0
    assert "No nodes found" in result.diagram


def test_primary_query_upstream_error_returns_envelope() -> None:
    puppetdb = FakePuppetDBClient()
    puppetdb.queue_failure(ToolInternalError("pdb down"))
    deps = make_deps(puppetdb)
    result = run_sync(tool.handle(deps, tool.InfrastructureMapInput()))
    assert isinstance(result, ErrorEnvelope)


def test_mermaid_output_grouped_by_role_with_facts() -> None:
    puppetdb = FakePuppetDBClient()
    deps = make_deps(puppetdb)

    # First query() call returns nodes, second returns facts —
    # FakePuppetDBClient only knows one result set, so drive it manually.
    nodes = [
        {"certname": f"node{i}", "latest_report_status": "changed", "report_timestamp": "t"}
        for i in range(12)
    ]
    facts = [
        {"certname": f"node{i}", "name": "pp_role", "value": "webserver"}
        for i in range(12)
    ]

    calls = {"n": 0}
    orig_query = puppetdb.query

    async def sequenced_query(pql, timeout_seconds, row_cap):
        calls["n"] += 1
        puppetdb.set_query_results(nodes if calls["n"] == 1 else facts)
        return await orig_query(pql, timeout_seconds, row_cap)

    puppetdb.query = sequenced_query  # type: ignore[method-assign]

    result = run_sync(
        tool.handle(deps, tool.InfrastructureMapInput(format="mermaid", group_by="role"))
    )
    assert isinstance(result, tool.InfrastructureMapResult)
    assert result.node_count == 12
    assert "graph TD" in result.diagram
    assert "webserver" in result.diagram
    assert "+2 more" in result.diagram  # 12 members, only first 10 rendered


def test_text_output_grouped_by_environment_facts_upstream_error() -> None:
    puppetdb = FakePuppetDBClient()
    deps = make_deps(puppetdb)
    nodes = [
        {"certname": "a", "latest_report_status": "unchanged", "report_timestamp": "t1"},
        {"certname": "b", "latest_report_status": "failed", "report_timestamp": "t2"},
    ]

    calls = {"n": 0}

    async def sequenced_query(pql, timeout_seconds, row_cap):
        calls["n"] += 1
        if calls["n"] == 1:
            from pe_mcp.core.clients import PQLResult
            return PQLResult(pql=pql, rows=nodes, truncated=False, row_cap=row_cap)
        raise ToolInternalError("facts query failed")

    puppetdb.query = sequenced_query  # type: ignore[method-assign]

    result = run_sync(
        tool.handle(deps, tool.InfrastructureMapInput(format="text", group_by="environment"))
    )
    assert isinstance(result, tool.InfrastructureMapResult)
    assert "PE Infrastructure Map" in result.diagram
    assert "unknown" in result.diagram  # no facts landed, group falls back
    assert result.node_count == 2


def test_resolve_group_key_defaults_unknown_to_role() -> None:
    assert tool._resolve_group_key("os") == "osfamily"
    assert tool._resolve_group_key("bogus") == "pp_role"


def test_rows_with_non_string_certname_are_skipped() -> None:
    puppetdb = FakePuppetDBClient()
    puppetdb.set_query_results([{"certname": 123}, {"certname": "real"}])
    deps = make_deps(puppetdb)
    result = run_sync(tool.handle(deps, tool.InfrastructureMapInput()))
    assert result.node_count == 1
