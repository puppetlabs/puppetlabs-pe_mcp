"""PE Smart MCP Server — thin entry point.

Imports core modules and tool modules from the pe_mcp package,
constructs dependencies, and registers tools via a discovery loop.
"""

from __future__ import annotations

import importlib
import inspect
import json
import sys
from typing import Any
from uuid import uuid4

from opentelemetry import trace

import structlog
from fastmcp import FastMCP
from fastmcp.server.middleware import Middleware
from pydantic import BaseModel, ValidationError

from pe_mcp.core.audit import emit_audit_event, get_actor, set_request_caller
from pe_mcp.core.clients import BasePEClient, PuppetDBClient
from pe_mcp.core.config import PEInstance, Settings, StartupConfigError, resolve_instance
from pe_mcp.core.deps import InstanceDeps, ServerDeps
from pe_mcp.core.errors import (
    ErrorEnvelope,
    ErrorType,
    UpstreamError,
    envelope_from_upstream,
)
from pe_mcp.core.logging import configure_logging, register_secret
from pe_mcp.core.observability import get_tracer, setup_telemetry
from pe_mcp.tools import DEFAULT_TOOL_NAMES

logger = structlog.get_logger(__name__)


# ------------------------------------------------------------------- #
# Sensitive fact redaction                                              #
# ------------------------------------------------------------------- #


REDACTED = "[redacted]"


def redact_fact_value(
    fact_name: str, value: Any, sensitive_names: frozenset[str],
) -> tuple[Any, str | None]:
    if fact_name in sensitive_names:
        return (
            REDACTED,
            f"Fact {fact_name!r} is a Sensitive fact type; value not returned.",
        )
    return (value, None)


# ------------------------------------------------------------------- #
# Tool registration                                                    #
# ------------------------------------------------------------------- #


def _resolve_input_model(module: Any) -> type[BaseModel]:
    for attr_name in dir(module):
        obj = getattr(module, attr_name)
        if (
            isinstance(obj, type)
            and issubclass(obj, BaseModel)
            and attr_name.endswith("Input")
            and obj is not BaseModel
        ):
            return obj
    raise ValueError(f"No *Input BaseModel subclass found in {module.__name__}")


def _build_tool_signature(input_model: type[BaseModel]) -> inspect.Signature:
    params = []
    for field_name, field_info in input_model.model_fields.items():
        ann = input_model.__annotations__[field_name]
        if field_info.is_required():
            p = inspect.Parameter(
                field_name, inspect.Parameter.POSITIONAL_OR_KEYWORD,
                annotation=ann,
            )
        else:
            p = inspect.Parameter(
                field_name, inspect.Parameter.POSITIONAL_OR_KEYWORD,
                default=field_info.default, annotation=ann,
            )
        params.append(p)
    return inspect.Signature(params)


def _register_tool(
    app: FastMCP,
    deps: ServerDeps,
    name: str,
    module: Any,
    settings: Settings,
) -> None:
    input_model = _resolve_input_model(module)

    tracer = get_tracer(__name__)
    audit_enabled = settings.audit_log_enabled

    async def handler(**kwargs: Any) -> Any:
        with tracer.start_as_current_span(f"tool.{name}") as span:
            span_ctx = span.get_span_context()
            trace_id = format(span_ctx.trace_id, "032x") if span_ctx.trace_id else str(uuid4())

            structlog.contextvars.clear_contextvars()
            structlog.contextvars.bind_contextvars(
                trace_id=trace_id, caller_id=get_actor(),
            )
            span.set_attribute("tool.name", name)

            actor = get_actor()
            span.set_attribute("audit.caller_id", actor)

            logger.info("tool_call_start", tool=name, trace_id=trace_id)

            validated = input_model.model_validate(kwargs)
            try:
                result = await module.handle(deps, validated)
            except UpstreamError as exc:
                span.set_status(trace.StatusCode.ERROR, str(exc))
                span.record_exception(exc)
                span.set_attribute("error.type", exc.error_type.value)
                logger.warning(
                    "tool_call_error", tool=name,
                    error_type=exc.error_type, trace_id=trace_id,
                )
                if audit_enabled:
                    emit_audit_event(
                        logger, tool=name, actor=actor,
                        outcome="error", trace_id=trace_id,
                        error_type=exc.error_type.value,
                    )
                return envelope_from_upstream(exc)

            if isinstance(result, ErrorEnvelope):
                span.set_status(trace.StatusCode.ERROR, result.message)
                span.set_attribute("error.type", result.error_type.value)
                logger.warning(
                    "tool_call_error", tool=name,
                    error_type=result.error_type, trace_id=trace_id,
                )
                if audit_enabled:
                    emit_audit_event(
                        logger, tool=name, actor=actor,
                        outcome="error", trace_id=trace_id,
                        error_type=result.error_type.value,
                    )
            else:
                span.set_status(trace.StatusCode.OK)
                logger.info("tool_call_success", tool=name, trace_id=trace_id)
                if audit_enabled:
                    emit_audit_event(
                        logger, tool=name, actor=actor,
                        outcome="success", trace_id=trace_id,
                    )
            return result

    handler.__name__ = name
    handler.__doc__ = module.DESCRIPTION
    handler.__signature__ = _build_tool_signature(input_model)
    handler.__annotations__ = {
        n: input_model.__annotations__[n] for n in input_model.model_fields
    }
    app.tool(name=name, description=module.DESCRIPTION)(handler)


def _load_default_tools() -> dict[str, Any]:
    tools: dict[str, Any] = {}
    for name in DEFAULT_TOOL_NAMES:
        module = importlib.import_module(f"pe_mcp.tools.{name}")
        assert module.NAME == name, (
            f"Tool module pe_mcp.tools.{name} declares NAME={module.NAME!r}, "
            f"expected {name!r}"
        )
        tools[name] = module
    return tools


# ------------------------------------------------------------------- #
# Error envelope middleware                                             #
# ------------------------------------------------------------------- #


class _CallerIdentityMiddleware(Middleware):
    """Extract per-request caller identity from HTTP headers."""

    def __init__(self, header_name: str) -> None:
        self._header_name = header_name

    async def on_call_tool(self, context, call_next):
        caller_id = None
        if hasattr(context, "request") and hasattr(context.request, "headers"):
            caller_id = context.request.headers.get(self._header_name)
        if caller_id:
            set_request_caller(caller_id)
        return await call_next(context)


class _ErrorEnvelopeMiddleware(Middleware):
    async def on_call_tool(self, context, call_next):
        try:
            return await call_next(context)
        except Exception as exc:
            msg = str(exc)
            if "Unknown tool" in msg or "not found" in msg.lower():
                logger.warning("tool_not_found", error=msg)
                env = ErrorEnvelope(
                    error_type=ErrorType.NOT_FOUND, message=msg, retryable=False,
                )
                from fastmcp.tools import ToolResult
                return ToolResult(content=json.dumps(env.model_dump()), is_error=True)
            raise


# ------------------------------------------------------------------- #
# App factory                                                          #
# ------------------------------------------------------------------- #


def build_app(deps: ServerDeps, settings: Settings) -> FastMCP:
    mcp = FastMCP("PE Smart MCP")
    mcp.add_middleware(_CallerIdentityMiddleware(settings.audit_header_name))
    mcp.add_middleware(_ErrorEnvelopeMiddleware())

    tool_modules = _load_default_tools()
    for name, module in tool_modules.items():
        _register_tool(mcp, deps, name, module, settings)

    logger.info(
        "tools_registered",
        tool_names=list(tool_modules.keys()),
        count=len(tool_modules),
    )
    return mcp


# ------------------------------------------------------------------- #
# Startup                                                              #
# ------------------------------------------------------------------- #


def _build_deps(settings: Settings, pe: PEInstance) -> ServerDeps:
    ca_path = str(pe.ca_cert_path) if pe.ca_cert_path else None
    base_client = BasePEClient(
        base_url=pe.puppetdb_url,
        rbac_token=pe.rbac_token,
        ca_cert_path=ca_path,
        request_timeout_seconds=settings.pql_timeout_seconds,
    )
    puppetdb = PuppetDBClient(base_client)
    instance = InstanceDeps(name=pe.name, puppetdb=puppetdb)
    return ServerDeps(
        instances={pe.name: instance},
        primary_name=pe.name,
        pql_timeout_seconds=settings.pql_timeout_seconds,
        pql_row_cap=settings.pql_row_cap,
    )


def startup() -> tuple[FastMCP, Settings]:
    settings = Settings()
    if settings.rbac_token:
        register_secret(settings.rbac_token)
    configure_logging(settings.log_level, log_file=settings.log_file or None)
    setup_telemetry(settings)

    pe = resolve_instance(settings)
    register_secret(pe.rbac_token)

    deps = _build_deps(settings, pe)

    set_request_caller(f"rbac-token:{pe.name}")

    logger.info(
        "pe_mcp_startup",
        puppetdb_url=pe.puppetdb_url,
        ca_cert_path=str(pe.ca_cert_path),
        pql_timeout=settings.pql_timeout_seconds,
        pql_row_cap=settings.pql_row_cap,
    )
    return build_app(deps, settings), settings


def main() -> int:
    try:
        app, settings = startup()
    except ValidationError as exc:
        count = exc.error_count()
        print(
            f"pe-mcp-server: config validation failed ({count} error(s)):",
            file=sys.stderr,
        )
        for err in exc.errors():
            loc = ".".join(str(part) for part in err["loc"])
            print(f"  {loc}: {err['msg']}", file=sys.stderr)
        return 2
    except StartupConfigError as exc:
        print(f"pe-mcp-server: startup failed: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(
            f"pe-mcp-server: unexpected startup error: "
            f"{exc.__class__.__name__}: {exc}",
            file=sys.stderr,
        )
        return 2
    app.run(transport="http", host=settings.host, port=settings.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
