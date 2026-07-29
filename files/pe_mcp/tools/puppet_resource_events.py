"""puppet_resource_events — resource events from a Puppet report."""

from __future__ import annotations

from pydantic import BaseModel, Field

from pe_mcp.core.deps import ServerDeps
from pe_mcp.core.errors import ErrorEnvelope, UpstreamError, envelope_from_upstream

NAME = "puppet_resource_events"
DESCRIPTION = (
    "List resource-level events from a specific Puppet report, "
    "filtered by event status (failure / success / noop / skipped). "
    "Echoes the PQL that was run in the pql_trace field."
)


class ResourceEventsInput(BaseModel):
    report_hash: str = Field(
        ...,
        description="The report hash to inspect.",
    )
    status: str | None = Field(
        default="failure",
        description=(
            "Event status filter: 'failure', 'success', 'noop', 'skipped'. "
            "Defaults to 'failure'."
        ),
    )


class ResourceEvent(BaseModel):
    resource_type: str
    resource_title: str
    status: str
    message: str | None = None
    file: str | None = None
    line: int | None = None


class ResourceEventsResult(BaseModel):
    events: list[ResourceEvent]
    pql_trace: list[dict[str, str]] = Field(default_factory=list)
    pe_instance: str
    note: str | None = None


async def handle(
    deps: ServerDeps, payload: ResourceEventsInput,
) -> ResourceEventsResult | ErrorEnvelope:
    instance = deps.resolve()
    status_clause = f'status = "{payload.status}"' if payload.status else "true"
    pql = (
        "events[resource_type, resource_title, status, message, file, line] "
        f'{{ report = "{payload.report_hash}" and {status_clause} }}'
    )
    try:
        result = await instance.puppetdb.query(
            pql,
            timeout_seconds=deps.pql_timeout_seconds,
            row_cap=deps.pql_row_cap,
        )
    except UpstreamError as exc:
        return envelope_from_upstream(exc)

    events = [
        ResourceEvent(
            resource_type=_str(r.get("resource_type")),
            resource_title=_str(r.get("resource_title")),
            status=_str(r.get("status")),
            message=_opt_str(r.get("message")),
            file=_opt_str(r.get("file")),
            line=_as_int(r.get("line")),
        )
        for r in result.rows
    ]
    return ResourceEventsResult(
        events=events,
        pql_trace=[{
            "purpose": "Fetch resource events for the selected report and status.",
            "query": pql,
        }],
        pe_instance=instance.name,
        note=None if events else "No resource events matched the filter.",
    )


def _str(v: object) -> str:
    return v if isinstance(v, str) else ""


def _opt_str(v: object) -> str | None:
    return v if isinstance(v, str) else None


def _as_int(v: object) -> int | None:
    return v if isinstance(v, int) else None
