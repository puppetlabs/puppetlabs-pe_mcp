"""impact_scope — blast radius of a Puppet class or fact change."""

from __future__ import annotations

from pydantic import BaseModel, Field

from pe_mcp.core.deps import ServerDeps
from pe_mcp.core.errors import ErrorEnvelope, UpstreamError, envelope_from_upstream, request_error

NAME = "impact_scope"
DESCRIPTION = (
    "Estimate the blast radius of a Puppet class or fact change. "
    "Returns the count of affected nodes, a per-environment breakdown, "
    "and a sample of certnames. Echoes the PQL it ran."
)


class ImpactScopeInput(BaseModel):
    puppet_class: str | None = Field(
        default=None,
        description=(
            "Fully-qualified Puppet class name (e.g. 'profile::nginx'). "
            "Mutually exclusive with fact_name/fact_value."
        ),
    )
    fact_name: str | None = Field(
        default=None,
        description="Fact name to scope the query. Mutually exclusive with puppet_class.",
    )
    fact_value: str | None = Field(
        default=None,
        description="Fact value to scope the query. Required when fact_name is set.",
    )
    sample_size: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum sample certnames to return per environment.",
    )


class EnvironmentImpact(BaseModel):
    environment: str
    affected_node_count: int
    sample_certnames: list[str]


class ImpactScopeResult(BaseModel):
    total_affected_node_count: int
    per_environment: list[EnvironmentImpact]
    pql_trace: list[dict[str, str]] = Field(default_factory=list)
    pe_instance: str
    note: str | None = None


async def handle(
    deps: ServerDeps, payload: ImpactScopeInput,
) -> ImpactScopeResult | ErrorEnvelope:
    if payload.puppet_class and (payload.fact_name or payload.fact_value):
        return request_error(
            "puppet_class is mutually exclusive with fact_name/fact_value."
        )
    if payload.fact_name and not payload.fact_value:
        return request_error("fact_name requires fact_value.")
    if not payload.puppet_class and not payload.fact_name:
        return request_error(
            "At least one of puppet_class or (fact_name + fact_value) is required."
        )

    instance = deps.resolve()

    if payload.puppet_class:
        pql = (
            "resources[certname, environment] "
            f'{{ type = "Class" and title = "{payload.puppet_class}" }}'
        )
        purpose = f"Find every node with Class[{payload.puppet_class}] applied."
    else:
        pql = (
            "nodes[certname, catalog_environment] "
            f'{{ facts.{payload.fact_name} = "{payload.fact_value}" }}'
        )
        purpose = f"Find every node with fact {payload.fact_name} = {payload.fact_value!r}."

    try:
        result = await instance.puppetdb.query(
            pql,
            timeout_seconds=deps.pql_timeout_seconds,
            row_cap=deps.pql_row_cap,
        )
    except UpstreamError as exc:
        return envelope_from_upstream(exc)

    per_env: dict[str, list[str]] = {}
    for row in result.rows:
        certname = _str(row.get("certname"))
        env = _str(
            row.get("environment") or row.get("catalog_environment") or "unknown"
        )
        per_env.setdefault(env, []).append(certname)

    envs = [
        EnvironmentImpact(
            environment=env,
            affected_node_count=len(certs),
            sample_certnames=certs[: payload.sample_size],
        )
        for env, certs in sorted(per_env.items())
    ]

    return ImpactScopeResult(
        total_affected_node_count=sum(e.affected_node_count for e in envs),
        per_environment=envs,
        pql_trace=[{"purpose": purpose, "query": pql}],
        pe_instance=instance.name,
        note=None if envs else "No nodes matched the impact scope filter.",
    )


def _str(v: object) -> str:
    return v if isinstance(v, str) else ""
