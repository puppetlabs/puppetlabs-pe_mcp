"""environment_status — environments with most-recent report timestamps."""

from __future__ import annotations

from pydantic import BaseModel, Field

from pe_mcp.core.deps import ServerDeps
from pe_mcp.core.errors import ErrorEnvelope, UpstreamError, envelope_from_upstream

NAME = "environment_status"
DESCRIPTION = (
    "Return the environments PuppetDB has reports for, each with the "
    "timestamp of its most-recent report (a report-recency signal, not a "
    "Code-Manager sync state). The pql field echoes the query run."
)

_PQL = "reports[environment, max(receive_time)] { group by environment }"
_MAX_COLUMN = "max"


class EnvironmentStatusInput(BaseModel):
    pass


class EnvironmentRecord(BaseModel):
    environment: str
    latest_report_time: str | None = None


class EnvironmentStatusResult(BaseModel):
    environments: list[EnvironmentRecord] = Field(default_factory=list)
    count: int
    pql: str
    pe_instance: str = ""


async def handle(
    deps: ServerDeps, payload: EnvironmentStatusInput,
) -> EnvironmentStatusResult | ErrorEnvelope:
    del payload
    instance = deps.resolve()
    try:
        result = await instance.puppetdb.query(
            _PQL,
            timeout_seconds=deps.pql_timeout_seconds,
            row_cap=deps.pql_row_cap,
        )
    except UpstreamError as exc:
        return envelope_from_upstream(exc)

    environments: list[EnvironmentRecord] = []
    for row in result.rows:
        environment = row.get("environment")
        if not isinstance(environment, str) or not environment:
            continue
        latest = row.get(_MAX_COLUMN)
        environments.append(
            EnvironmentRecord(
                environment=environment,
                latest_report_time=latest if isinstance(latest, str) else None,
            )
        )
    environments.sort(key=lambda e: e.environment)
    return EnvironmentStatusResult(
        environments=environments,
        count=len(environments),
        pql=_PQL,
        pe_instance=instance.name,
    )
