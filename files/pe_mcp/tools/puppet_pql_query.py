"""puppet_pql_query — raw PQL escape hatch.

Echoes the input PQL verbatim so the operator can copy and rerun
elsewhere. Timeout and row cap are enforced server-side on every call.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from pe_mcp.core.deps import ServerDeps
from pe_mcp.core.errors import ErrorEnvelope, UpstreamError, envelope_from_upstream

NAME = "puppet_pql_query"
DESCRIPTION = (
    "Run a raw PuppetDB PQL query with the operator's RBAC scope. "
    "Returns the rows PuppetDB emitted plus the PQL the server ran, "
    "verbatim. Every invocation is bounded by a server-side timeout "
    "(default 30s) and a row cap (default 10000); exceeding the cap "
    "sets truncated=true on the response."
)


class PQLQueryInput(BaseModel):
    query: str = Field(
        ...,
        min_length=1,
        description="The PQL query to execute.",
        examples=["nodes[certname] { facts.kernel = 'Linux' }"],
    )


class PQLQueryResult(BaseModel):
    pql: str
    rows: list[dict[str, object]] = Field(default_factory=list)
    truncated: bool
    row_cap: int
    pe_instance: str


async def handle(
    deps: ServerDeps, payload: PQLQueryInput,
) -> PQLQueryResult | ErrorEnvelope:
    instance = deps.resolve()
    try:
        result = await instance.puppetdb.query(
            payload.query,
            timeout_seconds=deps.pql_timeout_seconds,
            row_cap=deps.pql_row_cap,
        )
    except UpstreamError as exc:
        return envelope_from_upstream(exc)
    return PQLQueryResult(
        pql=result.pql,
        rows=result.rows,
        truncated=result.truncated,
        row_cap=result.row_cap,
        pe_instance=instance.name,
    )
