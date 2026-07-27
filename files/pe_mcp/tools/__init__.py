"""Tool registry constants and PQL safety helpers."""

from __future__ import annotations

import re

BULK_CERTNAME_CAP = 500

_FACT_NAME_GRAMMAR = re.compile(r"^[a-zA-Z0-9_][a-zA-Z0-9_.\-]*$")

_CLASS_TITLE_GRAMMAR = re.compile(
    r"^[A-Za-z][A-Za-z0-9_]*(::[A-Za-z][A-Za-z0-9_]*)*$"
)


def is_valid_fact_name(name: str) -> bool:
    return bool(_FACT_NAME_GRAMMAR.match(name))


def is_safe_pql_literal(value: str) -> bool:
    return is_valid_fact_name(value) and "\n" not in value and "\r" not in value


def quote_literal(value: str) -> str:
    return f"'{value}'"


def normalize_class_title(raw: str) -> str:
    segments = raw.split("::")
    return "::".join(
        seg[:1].upper() + seg[1:] if seg else seg for seg in segments
    )


def is_safe_class_title(value: str) -> bool:
    return (
        bool(_CLASS_TITLE_GRAMMAR.match(value))
        and "\n" not in value
        and "\r" not in value
    )


DEFAULT_TOOL_NAMES: tuple[str, ...] = (
    "node_lookup",
    "pql_query",
    "recent_reports",
    "resource_events",
    "impact_scope",
    "environment_status",
    "node_facts",
    "nodes_by_class",
    "comply_results",
    "infrastructure_map",
)
