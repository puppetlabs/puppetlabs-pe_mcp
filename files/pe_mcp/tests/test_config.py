"""Unit tests for Settings/resolve_instance startup config logic."""

from __future__ import annotations

import pathlib

import pytest

from pe_mcp.core.config import Settings, StartupConfigError, resolve_instance


def test_resolve_instance_explicit_token_and_urls(tmp_path: pathlib.Path) -> None:
    ca = tmp_path / "ca.pem"
    ca.write_text("dummy-cert")
    settings = Settings(
        rbac_token="explicit-token",
        pe_console_url="https://console.example.com",
        puppetdb_url="https://pdb.example.com:8081",
        ca_cert_path=str(ca),
    )
    instance = resolve_instance(settings)
    assert instance.name == "primary"
    assert instance.rbac_token == "explicit-token"
    assert instance.console_url == "https://console.example.com"
    assert instance.puppetdb_url == "https://pdb.example.com:8081"
    assert instance.ca_cert_path == ca


def test_resolve_instance_reads_token_from_file(tmp_path: pathlib.Path) -> None:
    ca = tmp_path / "ca.pem"
    ca.write_text("dummy-cert")
    token_file = tmp_path / "rbac_token"
    token_file.write_text("from-file-token\n")
    settings = Settings(
        token_path=str(token_file),
        ca_cert_path=str(ca),
    )
    instance = resolve_instance(settings)
    assert instance.rbac_token == "from-file-token"
    # falls back to fqdn-derived URLs when unset
    assert instance.console_url.startswith("https://")
    assert instance.puppetdb_url.endswith(":8081")


def test_resolve_instance_missing_token_file_raises(tmp_path: pathlib.Path) -> None:
    settings = Settings(
        token_path=str(tmp_path / "does-not-exist"),
    )
    with pytest.raises(StartupConfigError, match="Cannot read RBAC token"):
        resolve_instance(settings)


def test_resolve_instance_empty_token_file_raises(tmp_path: pathlib.Path) -> None:
    token_file = tmp_path / "rbac_token"
    token_file.write_text("   \n")
    settings = Settings(token_path=str(token_file))
    with pytest.raises(StartupConfigError, match="RBAC token is empty"):
        resolve_instance(settings)


def test_resolve_instance_missing_ca_cert_raises(tmp_path: pathlib.Path) -> None:
    settings = Settings(
        rbac_token="tok",
        ca_cert_path=str(tmp_path / "no-such-ca.pem"),
    )
    with pytest.raises(StartupConfigError, match="does not exist"):
        resolve_instance(settings)
