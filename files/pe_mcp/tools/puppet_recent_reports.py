"""puppet_recent_reports — filtered report roll-up from PuppetDB."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from pydantic import BaseModel, Field

from pe_mcp.core.deps import ServerDeps
from pe_mcp.core.errors import ErrorEnvelope, UpstreamError, envelope_from_upstream

NAME = "puppet_recent_reports"
DESCRIPTION = (
    "Return recent Puppet reports filtered by certname, environment, "
    "status, or time window. The pql_trace field lists the PuppetDB "
    "query the tool ran."
)


class RecentReportsInput(BaseModel):
    certname: str | None = Field(
        default=None,
        description="Filter to reports from this certname.",
    )
    environment: str | None = Field(
        default=None,
        description="Limit to reports from this PE environment.",
    )
    status: str | None = Field(
        default=None,
        description="Report status filter: 'failed', 'changed', or 'unchanged'.",
    )
    since_hours: int = Field(
        default=24,
        ge=1,
        le=720,
        description="Window in hours back from now. Defaults to 24h.",
    )


class ReportEntry(BaseModel):
    certname: str
    status: str
    environment: str
    end_time: str
    report_hash: str


class RecentReportsResult(BaseModel):
    reports: list[ReportEntry]
    pql_trace: list[dict[str, str]] = Field(default_factory=list)
    pe_instance: str
    note: str | None = None


async def handle(
    deps: ServerDeps, payload: RecentReportsInput,
) -> RecentReportsResult | ErrorEnvelope:
    instance = deps.resolve()
    pql = _build_pql(payload)
    try:
        result = await instance.puppetdb.query(
            pql,
            timeout_seconds=deps.pql_timeout_seconds,
            row_cap=deps.pql_row_cap,
        )
    except UpstreamError as exc:
        return envelope_from_upstream(exc)

    reports = [
        ReportEntry(
            certname=_str(r.get("certname")),
            status=_str(r.get("status")),
            environment=_str(r.get("environment")),
            end_time=_str(r.get("end_time")),
            report_hash=_str(r.get("hash")),
        )
        for r in result.rows
    ]
    return RecentReportsResult(
        reports=reports,
        pql_trace=[{
            "purpose": "Roll up recent reports matching supplied filters.",
            "query": pql,
        }],
        pe_instance=instance.name,
        note="No reports matched the filter." if not reports else None,
    )


def _build_pql(payload: RecentReportsInput) -> str:
    clauses: list[str] = []
    if payload.certname:
        clauses.append(f'certname = "{payload.certname}"')
    if payload.environment:
        clauses.append(f'environment = "{payload.environment}"')
    if payload.status:
        clauses.append(f'status = "{payload.status}"')
    cutoff = (datetime.now(UTC) - timedelta(hours=payload.since_hours)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    clauses.append(f'end_time > "{cutoff}"')
    where = " and ".join(clauses)
    return (
        "reports[certname, status, environment, end_time, hash] "
        f"{{ {where} order by end_time desc }}"
    )


def _str(value: object) -> str:
    return value if isinstance(value, str) else ""
