"""Shared fixtures for BDD feature tests."""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field
from typing import Any

import pytest
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from pe_mcp.core.clients import PQLResult
from pe_mcp.core.config import Settings
from pe_mcp.core.deps import InstanceDeps, ServerDeps
from pe_mcp.core.errors import UpstreamError
from pe_mcp.server import build_app


def run_sync(coro: Any) -> Any:
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@dataclass
class FakePuppetDBClient:
    _failures: deque[UpstreamError] = field(default_factory=deque)
    _query_results: list[dict[str, object]] = field(default_factory=list)

    def queue_failure(self, exc: UpstreamError) -> None:
        self._failures.append(exc)

    def set_query_results(self, rows: list[dict[str, object]]) -> None:
        self._query_results = rows

    async def query(
        self, pql: str, timeout_seconds: int, row_cap: int,
    ) -> PQLResult:
        if self._failures:
            raise self._failures.popleft()
        return PQLResult(
            pql=pql,
            rows=self._query_results[:row_cap],
            truncated=len(self._query_results) > row_cap,
            row_cap=row_cap,
        )

    async def aclose(self) -> None:
        pass


@pytest.fixture
def fake_puppetdb() -> FakePuppetDBClient:
    return FakePuppetDBClient()


@pytest.fixture
def mock_settings() -> Settings:
    return Settings(
        PE_MCP_RBAC_TOKEN="test-token",
        PE_MCP_PUPPETDB_URL="https://localhost:8081",
        PE_MCP_AUDIT_LOG_ENABLED=True,
    )


@pytest.fixture
def mock_deps(fake_puppetdb: FakePuppetDBClient) -> ServerDeps:
    instance = InstanceDeps(name="test", puppetdb=fake_puppetdb)
    return ServerDeps(
        instances={"test": instance},
        primary_name="test",
        pql_timeout_seconds=10,
        pql_row_cap=1000,
    )


@pytest.fixture
def app(mock_deps: ServerDeps, mock_settings: Settings) -> "FastMCP":
    from fastmcp import FastMCP
    from pe_mcp.core.audit import set_request_caller
    set_request_caller("rbac-token:test")
    return build_app(mock_deps, mock_settings)


@pytest.fixture
def span_recorder() -> InMemorySpanExporter:
    exporter = InMemorySpanExporter()
    resource = Resource.create({"service.name": "test-pe-mcp"})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    # trace.set_tracer_provider() is a set-once API; reset its internal guard
    # so each test can install its own provider instead of silently no-op'ing.
    trace._TRACER_PROVIDER_SET_ONCE._done = False
    trace.set_tracer_provider(provider)
    yield exporter
    exporter.shutdown()
    trace._TRACER_PROVIDER_SET_ONCE._done = False
    trace.set_tracer_provider(trace.NoOpTracerProvider())
