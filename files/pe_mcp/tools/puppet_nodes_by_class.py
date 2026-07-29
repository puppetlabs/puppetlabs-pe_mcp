"""puppet_nodes_by_class — nodes a catalog Class is applied to."""

from __future__ import annotations

from pydantic import BaseModel, Field

from pe_mcp.core.deps import ServerDeps
from pe_mcp.core.errors import ErrorEnvelope, UpstreamError, envelope_from_upstream, request_error
from pe_mcp.tools import is_safe_class_title, normalize_class_title, quote_literal

NAME = "puppet_nodes_by_class"
DESCRIPTION = (
    "Return the nodes a given Puppet catalog Class is applied to, with a "
    "per-environment breakdown. The class title is normalized to PuppetDB's "
    "stored form (each '::'-separated segment is capitalized). "
    "This is a catalog Class, not a node-classifier group. "
    "The pql field echoes the query run."
)


class NodesByClassInput(BaseModel):
    class_title: str = Field(
        ...,
        min_length=1,
        description="The Puppet class name to search for.",
    )


class NodesByClassResult(BaseModel):
    class_title: str
    certnames: list[str] = Field(default_factory=list)
    count: int
    environment_breakdown: dict[str, int] = Field(default_factory=dict)
    pql: str
    truncated: bool
    pe_instance: str = ""


async def handle(
    deps: ServerDeps, payload: NodesByClassInput,
) -> NodesByClassResult | ErrorEnvelope:
    instance = deps.resolve()
    normalized = normalize_class_title(payload.class_title)
    if not is_safe_class_title(normalized):
        return request_error(
            f"Class title {payload.class_title!r} does not normalize "
            f"to a valid class name."
        )

    pql = _build_pql(normalized)
    try:
        result = await instance.puppetdb.query(
            pql,
            timeout_seconds=deps.pql_timeout_seconds,
            row_cap=deps.pql_row_cap,
        )
    except UpstreamError as exc:
        return envelope_from_upstream(exc)

    certnames: set[str] = set()
    breakdown: dict[str, int] = {}
    for row in result.rows:
        certname = row.get("certname")
        if not isinstance(certname, str) or not certname:
            continue
        if certname in certnames:
            continue
        certnames.add(certname)
        environment = row.get("environment")
        env_key = environment if isinstance(environment, str) and environment else "unknown"
        breakdown[env_key] = breakdown.get(env_key, 0) + 1

    ordered = sorted(certnames)
    return NodesByClassResult(
        class_title=normalized,
        certnames=ordered,
        count=len(ordered),
        environment_breakdown=breakdown,
        pql=pql,
        truncated=result.truncated,
        pe_instance=instance.name,
    )


def _build_pql(normalized_title: str) -> str:
    return (
        "resources[certname, environment] "
        f"{{ type = 'Class' and title = {quote_literal(normalized_title)} }}"
    )
