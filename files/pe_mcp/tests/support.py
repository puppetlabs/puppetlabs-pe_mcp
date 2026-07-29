"""Shared test doubles for plain (non-BDD) unit tests.

Not a test module itself (no test_ prefix) — imported by the
test_*.py files added to raise coverage on the core/tools layer.
"""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from pe_mcp.core.clients import PQLResult
from pe_mcp.core.deps import InstanceDeps, ServerDeps
from pe_mcp.core.errors import UpstreamError


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
    last_pql: str | None = None

    def queue_failure(self, exc: UpstreamError) -> None:
        self._failures.append(exc)

    def set_query_results(self, rows: list[dict[str, object]]) -> None:
        self._query_results = rows

    async def query(
        self, pql: str, timeout_seconds: int, row_cap: int,
    ) -> PQLResult:
        self.last_pql = pql
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


def make_deps(
    puppetdb: FakePuppetDBClient, row_cap: int = 1000, timeout: int = 10,
) -> ServerDeps:
    instance = InstanceDeps(name="test", puppetdb=puppetdb)
    return ServerDeps(
        instances={"test": instance},
        primary_name="test",
        pql_timeout_seconds=timeout,
        pql_row_cap=row_cap,
    )


def write_dummy_ca_pem(path: Any) -> None:
    """Write a throwaway self-signed CA cert to `path`.

    httpx's ssl.create_default_context(cafile=...) requires a
    structurally valid PEM cert (not just any text), since
    BasePEClient's ca_cert_path branch is exercised for real.
    """
    import datetime

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [x509.NameAttribute(x509.oid.NameOID.COMMON_NAME, "test-ca")]
    )
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.UTC))
        .not_valid_after(datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
