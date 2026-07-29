"""Unit tests for the BasePEClient/PuppetDBClient HTTP + error-mapping layer."""

from __future__ import annotations

import httpx
import pytest

from pe_mcp.core.clients import BasePEClient, PuppetDBClient, _map_response
from pe_mcp.core.errors import (
    AuthFailedError,
    NotFoundError,
    RateLimitedError,
    TimeoutUpstreamError,
    ToolInternalError,
)
from pe_mcp.tests.support import run_sync, write_dummy_ca_pem


def _client(transport: httpx.MockTransport, ca_cert_path: str | None = None) -> BasePEClient:
    client = BasePEClient(
        base_url="https://pe.example.com:8081",
        rbac_token="tok",
        ca_cert_path=ca_cert_path,
    )
    client._client = httpx.AsyncClient(
        transport=transport, base_url="https://pe.example.com:8081",
    )
    return client


def test_get_json_success_with_body() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    client = _client(httpx.MockTransport(handler))
    result = run_sync(client.get_json("/status"))
    assert result == {"ok": True}


def test_get_json_success_empty_body() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(204, content=b"")

    client = _client(httpx.MockTransport(handler))
    result = run_sync(client.get_json("/status"))
    assert result is None


def test_get_json_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("boom", request=request)

    client = _client(httpx.MockTransport(handler))
    with pytest.raises(TimeoutUpstreamError):
        run_sync(client.get_json("/status"))


def test_get_json_transport_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    client = _client(httpx.MockTransport(handler))
    with pytest.raises(ToolInternalError):
        run_sync(client.get_json("/status"))


def test_post_json_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[{"certname": "a"}])

    client = _client(httpx.MockTransport(handler))
    result = run_sync(client.post_json("/pdb/query/v4", json={"query": "nodes[]{}"}))
    assert result == [{"certname": "a"}]


def test_post_json_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.WriteTimeout("boom", request=request)

    client = _client(httpx.MockTransport(handler))
    with pytest.raises(TimeoutUpstreamError):
        run_sync(client.post_json("/pdb/query/v4", json={}))


def test_post_json_transport_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    client = _client(httpx.MockTransport(handler))
    with pytest.raises(ToolInternalError):
        run_sync(client.post_json("/pdb/query/v4", json={}))


@pytest.mark.parametrize(
    ("status", "exc_type"),
    [
        (401, AuthFailedError),
        (403, AuthFailedError),
        (404, NotFoundError),
        (429, RateLimitedError),
        (500, ToolInternalError),
        (503, ToolInternalError),
        (418, ToolInternalError),
    ],
)
def test_map_response_error_statuses(status: int, exc_type: type) -> None:
    response = httpx.Response(status, text="nope")
    with pytest.raises(exc_type):
        _map_response(response, "/some/path")


def test_ca_cert_path_used_as_verify(tmp_path) -> None:
    # Exercises the ca_cert_path-is-set branch of BasePEClient.__init__
    # (no network call happens).
    ca = tmp_path / "ca.pem"
    write_dummy_ca_pem(ca)

    client = BasePEClient(
        base_url="https://pe.example.com:8081",
        rbac_token="tok",
        ca_cert_path=str(ca),
    )
    run_sync(client.aclose())


def test_puppetdb_client_query_non_array_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"not": "a list"})

    base = _client(httpx.MockTransport(handler))
    puppetdb = PuppetDBClient(base)
    with pytest.raises(ToolInternalError):
        run_sync(puppetdb.query("nodes[]{}", timeout_seconds=10, row_cap=100))


def test_puppetdb_client_query_truncates_and_closes() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[{"certname": "a"}, {"certname": "b"}])

    base = _client(httpx.MockTransport(handler))
    puppetdb = PuppetDBClient(base)
    result = run_sync(puppetdb.query("nodes[]{}", timeout_seconds=10, row_cap=1))
    assert result.truncated is True
    assert len(result.rows) == 1
    run_sync(puppetdb.aclose())
