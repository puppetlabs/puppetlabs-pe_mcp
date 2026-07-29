"""Unit tests for pe_mcp OTel observability integration."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from pe_mcp.core.config import Settings
from pe_mcp.core.observability import get_tracer, setup_telemetry


# ------------------------------------------------------------------- #
# setup_telemetry — no-op fallback                                     #
# ------------------------------------------------------------------- #


class TestSetupTelemetryNoOp:
    """When otlp_endpoint is unset, a NoOpTracerProvider is installed."""

    def test_noop_provider_when_endpoint_unset(self):
        settings = Settings(
            otlp_endpoint=None,
            rbac_token="test-token",
        )
        trace.set_tracer_provider(trace.NoOpTracerProvider())
        setup_telemetry(settings)
        provider = trace.get_tracer_provider()
        assert isinstance(provider, trace.NoOpTracerProvider)

    def test_noop_provider_when_endpoint_empty(self):
        settings = Settings(
            otlp_endpoint="",
            rbac_token="test-token",
        )
        trace.set_tracer_provider(trace.NoOpTracerProvider())
        setup_telemetry(settings)
        provider = trace.get_tracer_provider()
        assert isinstance(provider, trace.NoOpTracerProvider)

    def test_noop_tracer_produces_no_spans(self, otel_exporter):
        settings = Settings(
            otlp_endpoint=None,
            rbac_token="test-token",
        )
        setup_telemetry(settings)
        tracer = get_tracer("test")
        with tracer.start_as_current_span("should-not-record"):
            pass
        assert len(otel_exporter.get_finished_spans()) == 0


# ------------------------------------------------------------------- #
# setup_telemetry — active provider                                    #
# ------------------------------------------------------------------- #


class TestSetupTelemetryActive:
    """When otlp_endpoint is set, a real TracerProvider is installed."""

    def test_real_provider_when_endpoint_set(self):
        settings = Settings(
            otlp_endpoint="http://localhost:4318",
            rbac_token="test-token",
        )
        trace.set_tracer_provider(trace.NoOpTracerProvider())
        setup_telemetry(settings)
        provider = trace.get_tracer_provider()
        assert isinstance(provider, TracerProvider)
        provider.shutdown()
        trace.set_tracer_provider(trace.NoOpTracerProvider())

    def test_service_name_resource(self):
        settings = Settings(
            otlp_endpoint="http://localhost:4318",
            otel_service_name="custom-name",
            rbac_token="test-token",
        )
        trace.set_tracer_provider(trace.NoOpTracerProvider())
        setup_telemetry(settings)
        provider = trace.get_tracer_provider()
        assert isinstance(provider, TracerProvider)
        resource_attrs = dict(provider.resource.attributes)
        assert resource_attrs["service.name"] == "custom-name"
        provider.shutdown()
        trace.set_tracer_provider(trace.NoOpTracerProvider())


# ------------------------------------------------------------------- #
# get_tracer                                                           #
# ------------------------------------------------------------------- #


class TestGetTracer:
    """get_tracer returns a tracer bound to the global provider."""

    def test_returns_tracer(self, otel_exporter):
        tracer = get_tracer("pe_mcp.test")
        assert tracer is not None

    def test_tracer_creates_spans(self, otel_exporter):
        tracer = get_tracer("pe_mcp.test")
        with tracer.start_as_current_span("test-span"):
            pass
        spans = otel_exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "test-span"


# ------------------------------------------------------------------- #
# Span attributes — tool call instrumentation pattern                  #
# ------------------------------------------------------------------- #


class TestToolCallSpanAttributes:
    """Verify the span attribute pattern used in server._register_tool."""

    def test_tool_span_has_name_attribute(self, otel_exporter):
        tracer = get_tracer("pe_mcp.server")
        tool_name = "get_puppet_node_facts"
        with tracer.start_as_current_span(f"tool.{tool_name}") as span:
            span.set_attribute("tool.name", tool_name)
        spans = otel_exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == f"tool.{tool_name}"
        assert spans[0].attributes["tool.name"] == tool_name

    def test_tool_span_ok_status(self, otel_exporter):
        tracer = get_tracer("pe_mcp.server")
        with tracer.start_as_current_span("tool.test_tool") as span:
            span.set_status(trace.StatusCode.OK)
        spans = otel_exporter.get_finished_spans()
        assert spans[0].status.status_code == trace.StatusCode.OK

    def test_tool_span_error_status(self, otel_exporter):
        tracer = get_tracer("pe_mcp.server")
        with tracer.start_as_current_span("tool.test_tool") as span:
            span.set_status(trace.StatusCode.ERROR, "upstream timeout")
            span.set_attribute("error.type", "UPSTREAM_ERROR")
        spans = otel_exporter.get_finished_spans()
        assert spans[0].status.status_code == trace.StatusCode.ERROR
        assert spans[0].attributes["error.type"] == "UPSTREAM_ERROR"

    def test_tool_span_records_exception(self, otel_exporter):
        tracer = get_tracer("pe_mcp.server")
        exc = RuntimeError("connection refused")
        with tracer.start_as_current_span("tool.test_tool") as span:
            span.record_exception(exc)
            span.set_status(trace.StatusCode.ERROR, str(exc))
        spans = otel_exporter.get_finished_spans()
        events = spans[0].events
        assert any(e.name == "exception" for e in events)

    def test_nested_spans_parent_child(self, otel_exporter):
        tracer = get_tracer("pe_mcp.server")
        with tracer.start_as_current_span("tool.outer") as outer:
            with tracer.start_as_current_span("db.query") as inner:
                inner.set_attribute("db.statement", "SELECT 1")
        spans = otel_exporter.get_finished_spans()
        assert len(spans) == 2
        inner_span = next(s for s in spans if s.name == "db.query")
        outer_span = next(s for s in spans if s.name == "tool.outer")
        assert inner_span.parent.span_id == outer_span.context.span_id
