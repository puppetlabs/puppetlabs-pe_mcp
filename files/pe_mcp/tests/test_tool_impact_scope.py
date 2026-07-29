"""Unit tests for the puppet_impact_scope tool handler (extra edge cases)."""

from __future__ import annotations

from pe_mcp.core.errors import ErrorEnvelope, ToolInternalError
from pe_mcp.tools import puppet_impact_scope as tool
from pe_mcp.tests.support import FakePuppetDBClient, make_deps, run_sync


def test_mutually_exclusive_inputs_is_request_error() -> None:
    deps = make_deps(FakePuppetDBClient())
    result = run_sync(
        tool.handle(
            deps,
            tool.ImpactScopeInput(puppet_class="profile::nginx", fact_name="osfamily", fact_value="RedHat"),
        )
    )
    assert isinstance(result, ErrorEnvelope)
    assert "mutually exclusive" in result.message


def test_fact_name_without_value_is_request_error() -> None:
    deps = make_deps(FakePuppetDBClient())
    result = run_sync(tool.handle(deps, tool.ImpactScopeInput(fact_name="osfamily")))
    assert isinstance(result, ErrorEnvelope)
    assert "requires fact_value" in result.message


def test_no_input_is_request_error() -> None:
    deps = make_deps(FakePuppetDBClient())
    result = run_sync(tool.handle(deps, tool.ImpactScopeInput()))
    assert isinstance(result, ErrorEnvelope)
    assert "At least one of" in result.message


def test_fact_based_query_success_with_breakdown() -> None:
    puppetdb = FakePuppetDBClient()
    puppetdb.set_query_results([
        {"certname": "a", "catalog_environment": "production"},
        {"certname": "b", "environment": "staging"},
        {"certname": "c"},  # falls back to "unknown"
    ])
    deps = make_deps(puppetdb)
    result = run_sync(
        tool.handle(deps, tool.ImpactScopeInput(fact_name="osfamily", fact_value="RedHat"))
    )
    assert isinstance(result, tool.ImpactScopeResult)
    assert result.total_affected_node_count == 3
    envs = {e.environment: e.affected_node_count for e in result.per_environment}
    assert envs == {"production": 1, "staging": 1, "unknown": 1}
    assert result.note is None


def test_class_based_query_upstream_error() -> None:
    puppetdb = FakePuppetDBClient()
    puppetdb.queue_failure(ToolInternalError("pdb down"))
    deps = make_deps(puppetdb)
    result = run_sync(tool.handle(deps, tool.ImpactScopeInput(puppet_class="profile::nginx")))
    assert isinstance(result, ErrorEnvelope)


def test_no_matches_sets_note() -> None:
    puppetdb = FakePuppetDBClient()
    puppetdb.set_query_results([])
    deps = make_deps(puppetdb)
    result = run_sync(tool.handle(deps, tool.ImpactScopeInput(puppet_class="profile::nginx")))
    assert result.note == "No nodes matched the impact scope filter."
