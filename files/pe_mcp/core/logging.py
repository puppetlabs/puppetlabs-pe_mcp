"""Structured logging with secret redaction.

Writes JSON-lines to both stderr and a log file. Redacts PEM blocks,
JWTs, and any registered secret sentinels from all log output.
"""

from __future__ import annotations

import logging
import pathlib
import re
from typing import Any

import structlog

REDACTED = "[redacted]"

_PEM_BLOCK = re.compile(
    r"-----BEGIN[^-]+-----[^-]+-----END[^-]+-----",
    re.DOTALL,
)
_JWT = re.compile(
    r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b",
)

_secret_sentinels: list[str] = []


def register_secret(secret: str) -> None:
    if secret:
        _secret_sentinels.append(secret)


def redact_secrets(text: str) -> str:
    if not text:
        return text
    result = _PEM_BLOCK.sub(REDACTED, text)
    result = _JWT.sub(REDACTED, result)
    for sentinel in _secret_sentinels:
        if sentinel and sentinel in result:
            result = result.replace(sentinel, REDACTED)
    return result


def _scrub(value: Any) -> Any:
    if isinstance(value, str):
        return redact_secrets(value)
    if isinstance(value, dict):
        return {k: _scrub(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_scrub(v) for v in value]
    return value


def _redact_processor(
    _logger: Any, _method: str, event_dict: dict[str, Any],
) -> dict[str, Any]:
    return {k: _scrub(v) for k, v in event_dict.items()}


class _TeeLoggerFactory:
    def __init__(self, log_file: str) -> None:
        pathlib.Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        self._file = open(log_file, "a")  # noqa: SIM115
        self._stderr = structlog.PrintLoggerFactory()

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return _TeeLogger(self._stderr(*args, **kwargs), self._file)


class _TeeLogger:
    def __init__(self, stderr_logger: Any, file_handle: Any) -> None:
        self._stderr = stderr_logger
        self._file = file_handle

    def msg(self, message: str) -> None:
        self._stderr.msg(message)
        self._file.write(message + "\n")
        self._file.flush()

    log = debug = info = warning = warn = error = critical = fatal = msg


def configure_logging(level: str = "INFO", log_file: str | None = None) -> None:
    factory: Any
    if log_file:
        factory = _TeeLoggerFactory(log_file)
    else:
        factory = structlog.PrintLoggerFactory()

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            _redact_processor,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(level.upper())
        ),
        context_class=dict,
        logger_factory=factory,
    )
