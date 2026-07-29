"""Unit tests for the puppet_node_facts tool handler."""

from __future__ import annotations

from pe_mcp.core.errors import ErrorEnvelope, ToolInternalError
from pe_mcp.tools import puppet_node_facts as tool
from pe_mcp.tests.support import FakePuppetDBClient, make_deps, run_sync


def test_single_certname_string_input() -> None:
    puppetdb = FakePuppetDBClient()
    puppetdb.set_query_results([{"certname": "web01", "name": "osfamily", "value": "RedHat"}])
    deps = make_deps(puppetdb)
    result = run_sync(
        tool.handle(deps, tool.NodeFactsInput(certnames="web01", fact_names=["osfamily"]))
    )
    assert isinstance(result, tool.NodeFactsResult)
    assert result.facts == {"web01": {"osfamily": "RedHat"}}


def test_empty_certnames_list_is_request_error() -> None:
    deps = make_deps(FakePuppetDBClient())
    result = run_sync(tool.handle(deps, tool.NodeFactsInput(certnames=[], fact_names=["osfamily"])))
    assert isinstance(result, ErrorEnvelope)
    assert "At least one certname" in result.message


def test_too_many_certnames_is_request_error() -> None:
    deps = make_deps(FakePuppetDBClient())
    too_many = [f"node{i}" for i in range(501)]
    result = run_sync(tool.handle(deps, tool.NodeFactsInput(certnames=too_many, fact_names=["osfamily"])))
    assert isinstance(result, ErrorEnvelope)
    assert "bulk cap" in result.message


def test_unsafe_certname_literal_is_request_error() -> None:
    deps = make_deps(FakePuppetDBClient())
    result = run_sync(
        tool.handle(deps, tool.NodeFactsInput(certnames=["bad\nname"], fact_names=["osfamily"]))
    )
    assert isinstance(result, ErrorEnvelope)
    assert "PQL literal grammar" in result.message


def test_invalid_fact_name_is_request_error() -> None:
    deps = make_deps(FakePuppetDBClient())
    result = run_sync(
        tool.handle(deps, tool.NodeFactsInput(certnames=["web01"], fact_names=["bad name!"]))
    )
    assert isinstance(result, ErrorEnvelope)
    assert "PQL fact-name grammar" in result.message


def test_upstream_error_returns_envelope() -> None:
    puppetdb = FakePuppetDBClient()
    puppetdb.queue_failure(ToolInternalError("pdb down"))
    deps = make_deps(puppetdb)
    result = run_sync(tool.handle(deps, tool.NodeFactsInput(certnames=["web01"], fact_names=["osfamily"])))
    assert isinstance(result, ErrorEnvelope)


def test_rows_with_non_string_fields_skipped() -> None:
    puppetdb = FakePuppetDBClient()
    puppetdb.set_query_results([
        {"certname": "web01", "name": "osfamily", "value": "RedHat"},
        {"certname": 123, "name": "osfamily", "value": "bad"},
        {"certname": "web01", "name": 456, "value": "bad"},
    ])
    deps = make_deps(puppetdb)
    result = run_sync(
        tool.handle(deps, tool.NodeFactsInput(certnames=["web01"], fact_names=["osfamily"]))
    )
    assert result.facts == {"web01": {"osfamily": "RedHat"}}
