"""OpenTelemetry observability with graceful no-op fallback.

When PE_MCP_OTLP_ENDPOINT is configured, initialises a TracerProvider that
exports spans via OTLP/HTTP.  When unset, installs the NoOpTracerProvider
so call-sites can instrument unconditionally without import guards.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pe_mcp.core.config import Settings

_log = logging.getLogger(__name__)


def setup_telemetry(settings: Settings) -> None:
    """Initialise the global OTel TracerProvider based on settings."""
    from opentelemetry import trace

    # trace.set_tracer_provider() only takes effect once per process; reset
    # its internal guard so setup_telemetry() stays idempotent (safe to call
    # again on reconfiguration, and so tests can exercise it repeatedly).
    trace._TRACER_PROVIDER_SET_ONCE._done = False

    endpoint = settings.otlp_endpoint
    if not endpoint:
        trace.set_tracer_provider(trace.NoOpTracerProvider())
        _log.info("OTel disabled (PE_MCP_OTLP_ENDPOINT unset)")
        return

    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
        OTLPSpanExporter,
    )

    resource = Resource.create({"service.name": settings.otel_service_name})
    exporter = OTLPSpanExporter(endpoint=endpoint)
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    _log.info(
        "OTel enabled: exporting to %s as %s",
        endpoint,
        settings.otel_service_name,
    )


def get_tracer(name: str):
    """Return a tracer from the globally configured provider."""
    from opentelemetry import trace

    return trace.get_tracer(name)
