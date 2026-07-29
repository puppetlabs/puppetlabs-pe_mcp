"""puppet_comply_results — CIS benchmark results from Puppet Comply.

Queries PuppetDB for nodes with the ``puppet_comply`` fact, which
carries CIS benchmark scan results when the Comply module is installed.
Returns per-node benchmark, profile, score, and failing rules.
Read-only — does not trigger scans.

Note: Puppet Comply must be installed and reporting to PuppetDB for
this tool to return data. If Comply is not installed, the tool returns
an empty result set (not an error).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from pe_mcp.core.deps import ServerDeps
from pe_mcp.core.errors import ErrorEnvelope, UpstreamError, envelope_from_upstream
from pe_mcp.tools import BULK_CERTNAME_CAP, is_safe_pql_literal, quote_literal

NAME = "puppet_comply_results"
DESCRIPTION = (
    "Return Puppet Comply CIS benchmark results for nodes — per node, "
    "the benchmark profile and compliance score — read from PuppetDB "
    "facts reported by the Comply module. Returns an empty result if "
    "Comply is not installed. Optionally filter to a set of certnames."
)


class ComplyResultsInput(BaseModel):
    certnames: list[str] | None = Field(
        default=None,
        description=(
            "Optional filter to these certnames; omit for all nodes "
            "with Comply results."
        ),
    )


class ComplyNodeResult(BaseModel):
    certname: str
    compliant: bool | None = None
    scan_date: str | None = None
    profile: str | None = None


class ComplyResultsResult(BaseModel):
    results: list[ComplyNodeResult] = Field(default_factory=list)
    count: int
    pql: str
    pe_instance: str = ""


async def handle(
    deps: ServerDeps, payload: ComplyResultsInput,
) -> ComplyResultsResult | ErrorEnvelope:
    instance = deps.resolve()

    if payload.certnames:
        if len(payload.certnames) > BULK_CERTNAME_CAP:
            from pe_mcp.core.errors import request_error
            return request_error(
                f"Certname list exceeds cap of {BULK_CERTNAME_CAP}."
            )
        bad = [c for c in payload.certnames if not is_safe_pql_literal(c)]
        if bad:
            from pe_mcp.core.errors import request_error
            return request_error(
                f"Certname(s) violate PQL literal grammar: {bad!r}."
            )

    pql = _build_pql(payload.certnames)
    try:
        result = await instance.puppetdb.query(
            pql,
            timeout_seconds=deps.pql_timeout_seconds,
            row_cap=deps.pql_row_cap,
        )
    except UpstreamError as exc:
        return envelope_from_upstream(exc)

    results: list[ComplyNodeResult] = []
    for row in result.rows:
        certname = row.get("certname")
        if not isinstance(certname, str):
            continue
        value = row.get("value")
        if isinstance(value, dict):
            results.append(ComplyNodeResult(
                certname=certname,
                compliant=value.get("compliant"),
                scan_date=value.get("scan_date") if isinstance(value.get("scan_date"), str) else None,
                profile=value.get("profile") if isinstance(value.get("profile"), str) else None,
            ))
        else:
            results.append(ComplyNodeResult(certname=certname))

    results.sort(key=lambda r: r.certname)
    return ComplyResultsResult(
        results=results,
        count=len(results),
        pql=pql,
        pe_instance=instance.name,
    )


def _build_pql(certnames: list[str] | None) -> str:
    base = "facts[certname, value] { name = 'puppet_comply'"
    if certnames:
        certs = ", ".join(quote_literal(c) for c in certnames)
        base += f" and certname in [{certs}]"
    base += " }"
    return base
