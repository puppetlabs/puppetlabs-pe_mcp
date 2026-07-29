"""Unit tests closing small gaps in core/audit.py and core/deps.py."""

from __future__ import annotations

import pytest
import structlog

from pe_mcp.core.audit import get_actor, set_request_caller
from pe_mcp.core.clients import PuppetDBClient
from pe_mcp.core.deps import InstanceDeps, ServerDeps


def test_get_actor_falls_back_to_contextvars() -> None:
    set_request_caller("")
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(caller_id="from-context")
    assert get_actor() == "from-context"
    structlog.contextvars.clear_contextvars()


def test_get_actor_falls_back_to_unknown() -> None:
    set_request_caller("")
    structlog.contextvars.clear_contextvars()
    assert get_actor() == "unknown"


def test_server_deps_resolve_unknown_instance_raises() -> None:
    instance = InstanceDeps(name="primary", puppetdb=PuppetDBClient(base_client=None))
    deps = ServerDeps(
        instances={"primary": instance},
        primary_name="primary",
        pql_timeout_seconds=10,
        pql_row_cap=100,
    )
    with pytest.raises(KeyError, match="Unknown PE instance"):
        deps.resolve("does-not-exist")
