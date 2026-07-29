"""puppet_node_lookup — list all nodes managed by Puppet Enterprise."""

from __future__ import annotations

from pydantic import BaseModel, Field

from pe_mcp.core.deps import ServerDeps
from pe_mcp.core.errors import ErrorEnvelope, envelope_from_upstream, UpstreamError

NAME = "puppet_node_lookup"
DESCRIPTION = (
    "List all nodes managed by Puppet Enterprise. Returns certnames, "
    "latest report status, and timestamps from PuppetDB."
)


class NodeLookupInput(BaseModel):
    pass


class NodeEntry(BaseModel):
    certname: str | None = None
    latest_report_status: str | None = None
    report_timestamp: str | None = None
    catalog_timestamp: str | None = None


class NodeLookupResult(BaseModel):
    nodes: list[NodeEntry]
    pql_trace: list[dict[str, str]] = Field(default_factory=list)
    pe_instance: str = ""


async def handle(
    deps: ServerDeps, payload: NodeLookupInput,
) -> NodeLookupResult | ErrorEnvelope:
    instance = deps.resolve()
    pql = "nodes {}"
    try:
        result = await instance.puppetdb.query(
            pql,
            timeout_seconds=deps.pql_timeout_seconds,
            row_cap=deps.pql_row_cap,
        )
    except UpstreamError as exc:
        return envelope_from_upstream(exc)

    nodes = [
        NodeEntry(
            certname=n.get("certname"),
            latest_report_status=n.get("latest_report_status"),
            report_timestamp=n.get("report_timestamp"),
            catalog_timestamp=n.get("catalog_timestamp"),
        )
        for n in result.rows
    ]
    return NodeLookupResult(
        nodes=nodes,
        pql_trace=[{"purpose": "List all managed nodes.", "query": pql}],
        pe_instance=instance.name,
    )
