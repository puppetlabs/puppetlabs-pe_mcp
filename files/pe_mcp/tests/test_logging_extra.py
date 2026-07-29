"""Unit tests for structured logging + secret redaction."""

from __future__ import annotations

import structlog

from pe_mcp.core import logging as pe_logging


def test_redact_secrets_empty_string() -> None:
    assert pe_logging.redact_secrets("") == ""


def test_redact_secrets_pem_block() -> None:
    text = "before -----BEGIN PRIVATE KEY-----\nabc123\n-----END PRIVATE KEY----- after"
    result = pe_logging.redact_secrets(text)
    assert "PRIVATE KEY" not in result
    assert result == "before [redacted] after"


def test_redact_secrets_jwt() -> None:
    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
    text = f"token={jwt} end"
    result = pe_logging.redact_secrets(text)
    assert jwt not in result
    assert "[redacted]" in result


def test_redact_secrets_registered_sentinel() -> None:
    pe_logging.register_secret("super-sekret-token")
    pe_logging.register_secret("")  # no-op, must not raise
    result = pe_logging.redact_secrets("caller sent super-sekret-token in header")
    assert "super-sekret-token" not in result
    assert "[redacted]" in result


def test_scrub_nested_structures() -> None:
    event = {
        "msg": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U",
        "nested": {"a": "clean", "b": ["clean-list-item", 123]},
        "count": 5,
    }
    scrubbed = pe_logging._redact_processor(None, "info", event)
    assert scrubbed["count"] == 5
    assert scrubbed["nested"]["b"][1] == 123
    assert "[redacted]" in scrubbed["msg"]


def test_configure_logging_stderr_only() -> None:
    pe_logging.configure_logging(level="DEBUG", log_file=None)
    logger = structlog.get_logger("test-stderr-only")
    logger.info("hello_from_stderr_test")


def test_configure_logging_with_tee_file(tmp_path) -> None:
    log_file = tmp_path / "nested" / "server.jsonl"
    pe_logging.configure_logging(level="INFO", log_file=str(log_file))
    logger = structlog.get_logger("test-tee")
    logger.info("hello_from_tee_test", secret="eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U")

    assert log_file.exists()
    content = log_file.read_text()
    assert "hello_from_tee_test" in content
    assert "[redacted]" in content

    # reset to a plain stderr-only config so later tests aren't affected
    pe_logging.configure_logging(level="INFO", log_file=None)
