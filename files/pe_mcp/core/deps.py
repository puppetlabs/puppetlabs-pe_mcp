"""Dependency containers for tool handlers.

ServerDeps holds server-wide config and a dict of InstanceDeps.
InstanceDeps wraps Protocol-typed clients for a single PE instance.
Tools receive ServerDeps and call resolve() to get the right instance.
"""

from __future__ import annotations

from dataclasses import dataclass

from pe_mcp.core.clients import PuppetDBClient


@dataclass(frozen=True)
class InstanceDeps:
    name: str
    puppetdb: PuppetDBClient


@dataclass(frozen=True)
class ServerDeps:
    instances: dict[str, InstanceDeps]
    primary_name: str
    pql_timeout_seconds: int
    pql_row_cap: int

    def resolve(self, name: str | None = None) -> InstanceDeps:
        key = name or self.primary_name
        if key not in self.instances:
            raise KeyError(
                f"Unknown PE instance {key!r}. "
                f"Configured: {', '.join(sorted(self.instances))}"
            )
        return self.instances[key]
