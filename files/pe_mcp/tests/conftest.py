"""Shared pytest fixtures for OpenTelemetry testing."""

from __future__ import annotations

import pytest
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


@pytest.fixture()
def otel_exporter():
    """Provide an InMemorySpanExporter wired to a fresh TracerProvider.

    Resets the global tracer provider before and after each test so
    tests are isolated regardless of execution order.
    """
    exporter = InMemorySpanExporter()
    resource = Resource.create({"service.name": "test-pe-mcp"})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(
        __import__(
            "opentelemetry.sdk.trace.export", fromlist=["SimpleSpanProcessor"]
        ).SimpleSpanProcessor(exporter)
    )
    # trace.set_tracer_provider() is a set-once API; reset its internal guard
    # so each test can install its own provider instead of silently no-op'ing.
    trace._TRACER_PROVIDER_SET_ONCE._done = False
    trace.set_tracer_provider(provider)
    yield exporter
    exporter.shutdown()
    trace._TRACER_PROVIDER_SET_ONCE._done = False
    trace.set_tracer_provider(trace.NoOpTracerProvider())
