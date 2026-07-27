"""pytest-bdd runner for tool_catalog.feature."""

from __future__ import annotations

from typing import Any

import pytest
from fastmcp import Client, FastMCP
from pytest_bdd import given, parsers, scenarios, then, when

from pe_mcp.tools import DEFAULT_TOOL_NAMES
from pe_mcp.tests.features.conftest import run_sync

FEATURE = "tool_catalog.feature"

pytestmark = pytest.mark.unit

scenarios(FEATURE)


@pytest.fixture
def catalog_state() -> dict[str, Any]:
    return {}


@given("the MCP server is started with mock PE backends")
def _started(app: FastMCP) -> None:
    return None


@when('an MCP client sends "tools/list"')
def _fetch_tools(app: FastMCP, catalog_state: dict[str, Any]) -> None:
    async def _run() -> list[Any]:
        async with Client(app) as client:
            return await client.list_tools()

    catalog_state["tools"] = run_sync(_run())


@then(parsers.parse("the response contains exactly {count:d} tool definitions"))
def _assert_tool_count(count: int, catalog_state: dict[str, Any]) -> None:
    assert len(catalog_state["tools"]) == count


@then("the tool names are:")
def _assert_tool_names(datatable: list[list[str]], catalog_state: dict[str, Any]) -> None:
    expected = [row[0] for row in datatable]
    got = sorted([tool.name for tool in catalog_state["tools"]])
    assert got == sorted(expected), f"catalog diverged: got {got}, expected {expected}"


@then('every tool has a non-empty "description" field')
def _assert_descriptions(catalog_state: dict[str, Any]) -> None:
    for tool in catalog_state["tools"]:
        assert tool.description.strip(), f"{tool.name} has empty description"


@then("every tool declares its input schema")
def _assert_input_schemas(catalog_state: dict[str, Any]) -> None:
    for tool in catalog_state["tools"]:
        schema = tool.inputSchema
        assert schema is not None, f"{tool.name} has no input schema"
