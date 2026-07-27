"""Configuration via pydantic-settings with PE_MCP_ env prefix."""

from __future__ import annotations

import pathlib
from dataclasses import dataclass

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class StartupConfigError(Exception):
    pass


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PE_MCP_",
        populate_by_name=True,
        extra="ignore",
    )

    pe_console_url: str | None = Field(
        default=None,
        description="PE console base URL (e.g. https://pe.example.com).",
    )
    puppetdb_url: str | None = Field(
        default=None,
        description="PuppetDB base URL (e.g. https://pe.example.com:8081).",
    )
    rbac_token: str | None = Field(
        default=None,
        description="PE RBAC token value. If unset, reads from token_path.",
    )
    ca_cert_path: pathlib.Path | None = Field(
        default=None,
        description="Path to the PE CA cert PEM.",
    )
    token_path: pathlib.Path = Field(
        default=pathlib.Path("/opt/smart-mcp/rbac_token"),
        description="Path to the RBAC token file (fallback when rbac_token is unset).",
    )

    pql_timeout_seconds: int = Field(default=30, ge=1, le=600)
    pql_row_cap: int = Field(default=10000, ge=1, le=1_000_000)

    otlp_endpoint: str | None = Field(
        default=None,
        description=(
            "OTLP HTTP endpoint for trace export "
            "(e.g. http://collector:4318). Disabled when unset."
        ),
    )
    otel_service_name: str = Field(
        default="pe-mcp-server",
        description="OTel service.name resource attribute.",
    )

    log_level: str = Field(default="INFO")
    log_file: str | None = Field(
        default="/var/log/smart-mcp/server.jsonl",
        description="JSON-lines log file path.",
    )
    host: str = Field(default="127.0.0.1")
    port: int = Field(default=8200, ge=1, le=65535)

    audit_log_enabled: bool = Field(
        default=True,
        description="Emit audit_tool_invocation events on every tool call.",
    )
    audit_header_name: str = Field(
        default="X-PE-MCP-Caller-Id",
        description="HTTP header carrying caller identity for audit attribution.",
    )

    sensitive_fact_names: frozenset[str] = frozenset(
        {"ssh_private_key", "root_password", "shadow"}
    )


@dataclass(frozen=True)
class PEInstance:
    name: str
    console_url: str
    puppetdb_url: str
    ca_cert_path: pathlib.Path | None
    rbac_token: str


DEFAULT_CA_CERT = pathlib.Path("/etc/puppetlabs/puppet/ssl/certs/ca.pem")


def resolve_instance(settings: Settings) -> PEInstance:
    token = settings.rbac_token
    if not token:
        try:
            token = settings.token_path.read_text().strip()
        except OSError as e:
            raise StartupConfigError(
                f"Cannot read RBAC token from {settings.token_path}: {e}"
            ) from e
    if not token:
        raise StartupConfigError("RBAC token is empty.")

    import socket

    fqdn = socket.getfqdn()
    console_url = settings.pe_console_url or f"https://{fqdn}"
    puppetdb_url = settings.puppetdb_url or f"https://{fqdn}:8081"
    ca_cert_path = settings.ca_cert_path or DEFAULT_CA_CERT

    if not ca_cert_path.exists():
        raise StartupConfigError(
            f"CA cert path {ca_cert_path} does not exist."
        )

    return PEInstance(
        name="primary",
        console_url=console_url,
        puppetdb_url=puppetdb_url,
        ca_cert_path=ca_cert_path,
        rbac_token=token,
    )
