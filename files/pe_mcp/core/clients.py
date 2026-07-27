"""HTTP client layer for PE backend services.

BasePEClient handles RBAC-token-authenticated requests with coarse
error mapping. PuppetDBClient adds PQL query support with row cap.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
import structlog

from pe_mcp.core.errors import (
    AuthFailedError,
    NotFoundError,
    RateLimitedError,
    TimeoutUpstreamError,
    ToolInternalError,
)

logger = structlog.get_logger(__name__)


class BasePEClient:
    def __init__(
        self,
        base_url: str,
        rbac_token: str,
        ca_cert_path: str | None,
        request_timeout_seconds: float = 30.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        verify: bool | str = ca_cert_path if ca_cert_path else True
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(request_timeout_seconds),
            verify=verify,
            headers={
                "X-Authentication": rbac_token,
                "Accept": "application/json",
            },
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def get_json(
        self, path: str, params: dict[str, Any] | None = None,
        timeout_seconds: float | None = None,
    ) -> Any:
        timeout = timeout_seconds or self._client.timeout.read
        try:
            response = await self._client.get(
                path, params=params, timeout=timeout,
            )
        except httpx.TimeoutException as e:
            raise TimeoutUpstreamError(
                f"Upstream unavailable: PE call at {path} exceeded {timeout}s timeout."
            ) from e
        except httpx.HTTPError as e:
            logger.warning(
                "pe_upstream_transport_error",
                path=path, error_class=e.__class__.__name__,
            )
            raise ToolInternalError(
                f"Upstream unavailable: PE call failed ({e.__class__.__name__})."
            ) from e
        return _map_response(response, path)

    async def post_json(
        self, path: str, json: Any,
        timeout_seconds: float | None = None,
    ) -> Any:
        timeout = timeout_seconds or self._client.timeout.read
        try:
            response = await self._client.post(
                path, json=json, timeout=timeout,
            )
        except httpx.TimeoutException as e:
            raise TimeoutUpstreamError(
                f"Upstream unavailable: PE POST to {path} exceeded {timeout}s timeout."
            ) from e
        except httpx.HTTPError as e:
            logger.warning(
                "pe_upstream_transport_error",
                path=path, error_class=e.__class__.__name__,
            )
            raise ToolInternalError(
                f"Upstream unavailable: PE POST failed ({e.__class__.__name__})."
            ) from e
        return _map_response(response, path)


def _map_response(response: httpx.Response, path: str) -> Any:
    status = response.status_code
    if 200 <= status < 300:
        if not response.content:
            return None
        return response.json()
    raw_snippet = response.text[:2048]
    logger.warning(
        "pe_upstream_http_error",
        path=path, http_status=status, raw_body=raw_snippet,
    )
    _raise_for_status(status, path)


def _raise_for_status(status: int, path: str) -> None:
    if status in (401, 403):
        raise AuthFailedError(
            f"Upstream unavailable: PE rejected the RBAC token "
            f"for {path} (HTTP {status})."
        )
    if status == 404:
        raise NotFoundError(
            f"Invalid request: PE reported no entity at {path} (HTTP 404)."
        )
    if status == 429:
        raise RateLimitedError(
            "Upstream unavailable: PE rate limited the operator. "
            "Wait at least 60 seconds before retrying."
        )
    if 500 <= status < 600:
        raise ToolInternalError(
            f"Upstream unavailable: PE returned HTTP {status}."
        )
    raise ToolInternalError(
        f"Upstream unavailable: PE returned unexpected HTTP {status}."
    )


@dataclass(frozen=True)
class PQLResult:
    pql: str
    rows: list[dict[str, object]]
    truncated: bool
    row_cap: int


class PuppetDBClient:
    def __init__(self, base_client: BasePEClient) -> None:
        self._base = base_client

    async def query(
        self, pql: str, timeout_seconds: int, row_cap: int,
    ) -> PQLResult:
        raw = await self._base.post_json(
            "/pdb/query/v4",
            json={"query": pql},
            timeout_seconds=timeout_seconds,
        )
        if not isinstance(raw, list):
            raise ToolInternalError(
                "Upstream unavailable: PuppetDB returned a non-array PQL response."
            )
        rows: list[dict[str, object]] = raw
        truncated = len(rows) > row_cap
        capped = rows[:row_cap]
        return PQLResult(
            pql=pql, rows=capped, truncated=truncated, row_cap=row_cap,
        )

    async def aclose(self) -> None:
        await self._base.aclose()
