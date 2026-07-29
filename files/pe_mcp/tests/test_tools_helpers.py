"""Unit tests for the PQL-safety/class-title helpers in tools/__init__.py."""

from __future__ import annotations

from pe_mcp.tools import (
    is_safe_class_title,
    is_safe_pql_literal,
    is_valid_fact_name,
    normalize_class_title,
    quote_literal,
)


def test_is_valid_fact_name() -> None:
    assert is_valid_fact_name("osfamily")
    assert is_valid_fact_name("pp_role")
    assert not is_valid_fact_name("bad name")
    assert not is_valid_fact_name("")


def test_is_safe_pql_literal_rejects_newlines() -> None:
    assert is_safe_pql_literal("web01")
    assert not is_safe_pql_literal("web01\n")
    assert not is_safe_pql_literal("web01\r")


def test_quote_literal() -> None:
    assert quote_literal("web01") == "'web01'"


def test_normalize_class_title() -> None:
    assert normalize_class_title("profile::nginx") == "Profile::Nginx"
    assert normalize_class_title("ntp") == "Ntp"
    assert normalize_class_title("a::") == "A::"


def test_is_safe_class_title() -> None:
    assert is_safe_class_title("Profile::Nginx")
    assert not is_safe_class_title("not valid!!")
    assert not is_safe_class_title("Profile::Nginx\n")
