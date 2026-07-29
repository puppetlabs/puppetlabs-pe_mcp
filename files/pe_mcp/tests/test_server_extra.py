"""Unit tests closing coverage gaps in server.py: tool registration,
error-mapping middleware, deps construction, and startup/main."""

from __future__ import annotations

import sys
import types
from typing import Any

import pytest
from fastmcp import Client, FastMCP
from pydantic import BaseModel, ValidationError

import pe_mcp.server as server
from pe_mcp.core.config import PEInstance, Settings, StartupConfigError
from pe_mcp.core.deps import InstanceDeps, ServerDeps
from pe_mcp.core.errors import ErrorEnvelope, ToolInternalError
from pe_mcp.tests.support import FakePuppetDBClient, make_deps, run_sync, write_dummy_ca_pem


def test_redact_fact_value_sensitive() -> None:
    value, note = server.redact_fact_value("root_password", "hunter2", frozenset({"root_password"}))
    assert value == server.REDACTED
    assert note is not None and "Sensitive fact" in note


def test_redact_fact_value_not_sensitive() -> None:
    value, note = server.redact_fact_value("osfamily", "RedHat", frozenset({"root_password"}))
    assert value == "RedHat"
    assert note is None


def test_resolve_input_model_raises_when_missing() -> None:
    fake_module = types.SimpleNamespace(__name__="fake_tool_module")
    with pytest.raises(ValueError, match="No \\*Input BaseModel subclass found"):
        server._resolve_input_model(fake_module)


def test_register_tool_propagates_raw_upstream_error() -> None:
    """Covers the `except UpstreamError` branch inside the registered
    tool handler — exercised when a tool's handle() raises instead of
    returning an ErrorEnvelope (defensive path, not the documented
    contract, but real code all the same)."""

    class RaiseInput(BaseModel):
        pass

    async def handle(deps: Any, payload: Any) -> Any:
        raise ToolInternalError("boom")

    module = types.SimpleNamespace(
        NAME="raise_tool",
        DESCRIPTION="raises for testing",
        RaiseInput=RaiseInput,
        handle=handle,
    )

    puppetdb = FakePuppetDBClient()
    deps = make_deps(puppetdb)
    settings = Settings(audit_log_enabled=True)

    app = FastMCP("test")
    server._register_tool(app, deps, "raise_tool", module, settings)

    async def _run() -> Any:
        async with Client(app) as client:
            return await client.call_tool("raise_tool", {})

    result = run_sync(_run())
    assert result.data["error_type"] == "tool_error"


def test_register_tool_success_and_error_envelope_paths() -> None:
    class OkInput(BaseModel):
        fail: bool = False

    async def handle(deps: Any, payload: Any) -> Any:
        if payload.fail:
            return ErrorEnvelope(error_type="tool_error", message="nope", retryable=False)
        return {"ok": True}

    module = types.SimpleNamespace(
        NAME="ok_tool", DESCRIPTION="ok tool", OkInput=OkInput, handle=handle,
    )

    puppetdb = FakePuppetDBClient()
    deps = make_deps(puppetdb)
    settings = Settings(audit_log_enabled=False)

    app = FastMCP("test")
    server._register_tool(app, deps, "ok_tool", module, settings)

    async def _run(fail: bool) -> Any:
        async with Client(app) as client:
            return await client.call_tool("ok_tool", {"fail": fail})

    success = run_sync(_run(False))
    assert success.data == {"ok": True}

    failure = run_sync(_run(True))
    assert failure.data["error_type"] == "tool_error"


def test_load_default_tools_loads_all() -> None:
    tools = server._load_default_tools()
    assert len(tools) == 10
    assert "puppet_node_lookup" in tools


def test_caller_identity_middleware_extracts_header() -> None:
    middleware = server._CallerIdentityMiddleware("X-PE-MCP-Caller-Id")

    class FakeRequest:
        headers = {"X-PE-MCP-Caller-Id": "alice"}

    class FakeContext:
        request = FakeRequest()

    from pe_mcp.core.audit import get_actor

    seen = {}

    async def call_next(ctx: Any) -> str:
        # asyncio tasks copy contextvars on entry, so the caller_id set by
        # the middleware is only observable *inside* this same task/coro,
        # not from the test after run_sync() returns.
        seen["actor"] = get_actor()
        return "called"

    result = run_sync(middleware.on_call_tool(FakeContext(), call_next))
    assert result == "called"
    assert seen["actor"] == "alice"


def test_caller_identity_middleware_no_headers() -> None:
    middleware = server._CallerIdentityMiddleware("X-PE-MCP-Caller-Id")

    class FakeContext:
        pass

    async def call_next(ctx: Any) -> str:
        return "called"

    result = run_sync(middleware.on_call_tool(FakeContext(), call_next))
    assert result == "called"


def test_error_envelope_middleware_maps_unknown_tool() -> None:
    middleware = server._ErrorEnvelopeMiddleware()

    async def call_next(ctx: Any) -> Any:
        raise RuntimeError("Unknown tool 'bogus'")

    result = run_sync(middleware.on_call_tool(object(), call_next))
    assert result.is_error is True
    assert "bogus" in result.content[0].text


def test_error_envelope_middleware_reraises_other_errors() -> None:
    middleware = server._ErrorEnvelopeMiddleware()

    async def call_next(ctx: Any) -> Any:
        raise RuntimeError("something else entirely")

    with pytest.raises(RuntimeError, match="something else entirely"):
        run_sync(middleware.on_call_tool(object(), call_next))


def test_build_deps_constructs_server_deps(tmp_path) -> None:
    ca = tmp_path / "ca.pem"
    write_dummy_ca_pem(ca)
    settings = Settings(pql_timeout_seconds=15, pql_row_cap=500)
    pe = PEInstance(
        name="primary",
        console_url="https://pe.example.com",
        puppetdb_url="https://pe.example.com:8081",
        ca_cert_path=ca,
        rbac_token="tok",
    )
    deps = server._build_deps(settings, pe)
    assert isinstance(deps, ServerDeps)
    assert deps.primary_name == "primary"
    assert deps.pql_timeout_seconds == 15
    assert deps.pql_row_cap == 500
    instance = deps.resolve()
    assert isinstance(instance, InstanceDeps)
    run_sync(instance.puppetdb.aclose())


def test_build_deps_without_ca_cert_path() -> None:
    settings = Settings()
    pe = PEInstance(
        name="primary",
        console_url="https://pe.example.com",
        puppetdb_url="https://pe.example.com:8081",
        ca_cert_path=None,
        rbac_token="tok",
    )
    deps = server._build_deps(settings, pe)
    run_sync(deps.resolve().puppetdb.aclose())


def test_build_app_registers_all_default_tools() -> None:
    puppetdb = FakePuppetDBClient()
    deps = make_deps(puppetdb)
    settings = Settings()
    app = server.build_app(deps, settings)
    assert isinstance(app, FastMCP)


def test_startup_success(monkeypatch, tmp_path) -> None:
    ca = tmp_path / "ca.pem"
    write_dummy_ca_pem(ca)
    monkeypatch.setenv("PE_MCP_RBAC_TOKEN", "tok")
    monkeypatch.setenv("PE_MCP_CA_CERT_PATH", str(ca))
    monkeypatch.setenv("PE_MCP_LOG_FILE", "")

    app, settings = server.startup()
    assert isinstance(app, FastMCP)
    assert isinstance(settings, Settings)


def test_main_reports_startup_config_error(monkeypatch, capsys) -> None:
    def fake_startup() -> Any:
        raise StartupConfigError("no token")

    monkeypatch.setattr(server, "startup", fake_startup)
    code = server.main()
    assert code == 2
    assert "startup failed" in capsys.readouterr().err


def test_main_reports_validation_error(monkeypatch, capsys) -> None:
    def fake_startup() -> Any:
        Settings.model_validate({"pql_timeout_seconds": "not-an-int"})

    monkeypatch.setattr(server, "startup", fake_startup)
    code = server.main()
    assert code == 2
    assert "config validation failed" in capsys.readouterr().err


def test_main_reports_unexpected_error(monkeypatch, capsys) -> None:
    def fake_startup() -> Any:
        raise RuntimeError("kaboom")

    monkeypatch.setattr(server, "startup", fake_startup)
    code = server.main()
    assert code == 2
    assert "unexpected startup error" in capsys.readouterr().err


def test_main_runs_app_on_success(monkeypatch) -> None:
    ran = {"called": False}

    class FakeApp:
        def run(self, **kwargs: Any) -> None:
            ran["called"] = True
            ran["kwargs"] = kwargs

    def fake_startup() -> Any:
        return FakeApp(), Settings(host="0.0.0.0", port=9999)

    monkeypatch.setattr(server, "startup", fake_startup)
    code = server.main()
    assert code == 0
    assert ran["called"] is True
    assert ran["kwargs"]["host"] == "0.0.0.0"
    assert ran["kwargs"]["port"] == 9999
