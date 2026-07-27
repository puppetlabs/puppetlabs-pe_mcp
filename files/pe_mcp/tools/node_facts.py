"""node_facts — values of chosen facts for one or many nodes."""

from __future__ import annotations

from pydantic import BaseModel, Field

from pe_mcp.core.deps import ServerDeps
from pe_mcp.core.errors import ErrorEnvelope, UpstreamError, envelope_from_upstream, request_error
from pe_mcp.tools import (
    BULK_CERTNAME_CAP,
    is_safe_pql_literal,
    is_valid_fact_name,
    quote_literal,
)

NAME = "node_facts"
DESCRIPTION = (
    "Return the values of a chosen set of facts for one or more nodes, keyed "
    "by certname then fact name. Accepts a single certname or an array of up "
    "to 500 and a non-empty list of fact names (top-level Facter names). "
    "The pql field echoes the PuppetDB query run."
)


class NodeFactsInput(BaseModel):
    certnames: str | list[str] = Field(
        ...,
        description="A single certname or an array of certnames (cap 500).",
    )
    fact_names: list[str] = Field(
        ...,
        min_length=1,
        description="The fact names to project (top-level Facter names).",
    )


class NodeFactsResult(BaseModel):
    facts: dict[str, dict[str, object]] = Field(default_factory=dict)
    pql: str
    truncated: bool
    pe_instance: str = ""


async def handle(
    deps: ServerDeps, payload: NodeFactsInput,
) -> NodeFactsResult | ErrorEnvelope:
    instance = deps.resolve()
    raw = payload.certnames
    certnames = [raw] if isinstance(raw, str) else list(raw)
    if not certnames:
        return request_error("At least one certname is required.")
    if len(certnames) > BULK_CERTNAME_CAP:
        return request_error(
            f"Array input exceeds the bulk cap of {BULK_CERTNAME_CAP}; "
            f"got {len(certnames)}."
        )
    bad_certs = [c for c in certnames if not is_safe_pql_literal(c)]
    if bad_certs:
        return request_error(
            f"Certname(s) violate the PQL literal grammar: {bad_certs!r}."
        )
    bad_names = [n for n in payload.fact_names if not is_valid_fact_name(n)]
    if bad_names:
        return request_error(
            f"Fact name(s) violate the PQL fact-name grammar: {bad_names!r}."
        )

    pql = _build_pql(certnames, payload.fact_names)
    try:
        result = await instance.puppetdb.query(
            pql,
            timeout_seconds=deps.pql_timeout_seconds,
            row_cap=deps.pql_row_cap,
        )
    except UpstreamError as exc:
        return envelope_from_upstream(exc)

    facts: dict[str, dict[str, object]] = {}
    for row in result.rows:
        certname = row.get("certname")
        name = row.get("name")
        if not isinstance(certname, str) or not isinstance(name, str):
            continue
        facts.setdefault(certname, {})[name] = row.get("value")
    return NodeFactsResult(
        facts=facts,
        pql=pql,
        truncated=result.truncated,
        pe_instance=instance.name,
    )


def _build_pql(certnames: list[str], fact_names: list[str]) -> str:
    certs = ", ".join(quote_literal(c) for c in certnames)
    names = ", ".join(quote_literal(n) for n in fact_names)
    return (
        f"facts[certname, name, value] "
        f"{{ certname in [{certs}] and name in [{names}] }}"
    )
