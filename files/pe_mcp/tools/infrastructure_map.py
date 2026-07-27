"""infrastructure_map — Mermaid or text diagram of PE-managed infrastructure."""

from __future__ import annotations

from pydantic import BaseModel, Field

from pe_mcp.core.deps import ServerDeps
from pe_mcp.core.errors import ErrorEnvelope, UpstreamError, envelope_from_upstream

NAME = "infrastructure_map"
DESCRIPTION = (
    "Return a topology diagram of PE-managed infrastructure showing nodes "
    "grouped by role, environment, or OS family. Output format is Mermaid "
    "(default) or plain text. Use as a first step when investigating a PE "
    "environment to see what is managed."
)

_PQL = (
    "nodes[certname, latest_report_status, report_timestamp, "
    "facts_timestamp] {}"
)

_FACTS_PQL_TEMPLATE = (
    "facts[certname, name, value] {{ "
    "name in ['pp_role', 'osfamily', 'pp_environment', 'pe_server_version'] "
    "and certname in [{certs}] }}"
)


class InfrastructureMapInput(BaseModel):
    format: str = Field(
        default="mermaid",
        description="Output format: 'mermaid' or 'text'.",
    )
    group_by: str = Field(
        default="role",
        description="Grouping axis: 'role', 'environment', or 'os'.",
    )


class InfrastructureMapResult(BaseModel):
    diagram: str
    node_count: int
    format: str
    group_by: str
    pe_instance: str = ""


async def handle(
    deps: ServerDeps, payload: InfrastructureMapInput,
) -> InfrastructureMapResult | ErrorEnvelope:
    instance = deps.resolve()

    try:
        nodes_result = await instance.puppetdb.query(
            _PQL,
            timeout_seconds=deps.pql_timeout_seconds,
            row_cap=deps.pql_row_cap,
        )
    except UpstreamError as exc:
        return envelope_from_upstream(exc)

    certnames = []
    node_info: dict[str, dict[str, object]] = {}
    for row in nodes_result.rows:
        cn = row.get("certname")
        if not isinstance(cn, str):
            continue
        certnames.append(cn)
        node_info[cn] = {
            "status": row.get("latest_report_status", "unknown"),
            "report_timestamp": row.get("report_timestamp"),
        }

    if not certnames:
        diagram = "No nodes found in PuppetDB."
        return InfrastructureMapResult(
            diagram=diagram,
            node_count=0,
            format=payload.format,
            group_by=payload.group_by,
            pe_instance=instance.name,
        )

    from pe_mcp.tools import quote_literal
    certs_pql = ", ".join(quote_literal(c) for c in certnames[:500])
    facts_pql = _FACTS_PQL_TEMPLATE.format(certs=certs_pql)
    try:
        facts_result = await instance.puppetdb.query(
            facts_pql,
            timeout_seconds=deps.pql_timeout_seconds,
            row_cap=deps.pql_row_cap,
        )
    except UpstreamError:
        facts_result = None

    if facts_result:
        for row in facts_result.rows:
            cn = row.get("certname")
            name = row.get("name")
            value = row.get("value")
            if isinstance(cn, str) and isinstance(name, str) and cn in node_info:
                node_info[cn][name] = value

    group_key = _resolve_group_key(payload.group_by)
    groups: dict[str, list[str]] = {}
    for cn, info in sorted(node_info.items()):
        key = str(info.get(group_key, "unknown"))
        groups.setdefault(key, []).append(cn)

    if payload.format == "text":
        diagram = _render_text(groups, node_info)
    else:
        diagram = _render_mermaid(groups, node_info, payload.group_by)

    return InfrastructureMapResult(
        diagram=diagram,
        node_count=len(certnames),
        format=payload.format,
        group_by=payload.group_by,
        pe_instance=instance.name,
    )


def _resolve_group_key(group_by: str) -> str:
    return {
        "role": "pp_role",
        "environment": "pp_environment",
        "os": "osfamily",
    }.get(group_by, "pp_role")


def _render_mermaid(
    groups: dict[str, list[str]],
    node_info: dict[str, dict[str, object]],
    group_by: str,
) -> str:
    lines = ["graph TD"]
    lines.append("    PE[PE Infrastructure]")
    for i, (group_name, members) in enumerate(sorted(groups.items())):
        gid = f"G{i}"
        label = f"{group_by}: {group_name}"
        lines.append(f"    {gid}[{label}<br/>{len(members)} nodes]")
        lines.append(f"    PE --> {gid}")
        for j, cn in enumerate(members[:10]):
            nid = f"{gid}N{j}"
            status = node_info.get(cn, {}).get("status", "unknown")
            lines.append(f"    {nid}({cn}<br/>{status})")
            lines.append(f"    {gid} --> {nid}")
        if len(members) > 10:
            lines.append(f"    {gid}More[+{len(members) - 10} more]")
            lines.append(f"    {gid} --> {gid}More")
    return "\n".join(lines)


def _render_text(
    groups: dict[str, list[str]],
    node_info: dict[str, dict[str, object]],
) -> str:
    lines = ["PE Infrastructure Map", "=" * 40]
    for group_name, members in sorted(groups.items()):
        lines.append(f"\n[{group_name}] ({len(members)} nodes)")
        for cn in members:
            status = node_info.get(cn, {}).get("status", "unknown")
            ts = node_info.get(cn, {}).get("report_timestamp", "n/a")
            lines.append(f"  - {cn}  status={status}  last_report={ts}")
    return "\n".join(lines)
