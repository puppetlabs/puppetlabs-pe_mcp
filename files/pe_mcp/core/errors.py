"""Five-category error taxonomy with ErrorEnvelope.

Ported from UCF pe-mcp-server error architecture. Every tool returns
ErrorEnvelope on failure instead of raising — keeps MCP responses
structured and retryable where appropriate.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class ErrorType(StrEnum):
    TIMEOUT = "timeout"
    AUTH_FAILED = "auth_failed"
    RATE_LIMITED = "rate_limited"
    NOT_FOUND = "not_found"
    TOOL_ERROR = "tool_error"


class ErrorEnvelope(BaseModel):
    error_type: ErrorType
    message: str
    retryable: bool | None = None


class UpstreamError(Exception):
    error_type: ErrorType = ErrorType.TOOL_ERROR

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class AuthFailedError(UpstreamError):
    error_type = ErrorType.AUTH_FAILED


class NotFoundError(UpstreamError):
    error_type = ErrorType.NOT_FOUND


class RateLimitedError(UpstreamError):
    error_type = ErrorType.RATE_LIMITED


class TimeoutUpstreamError(UpstreamError):
    error_type = ErrorType.TIMEOUT


class ToolInternalError(UpstreamError):
    error_type = ErrorType.TOOL_ERROR


def envelope_from_upstream(exc: UpstreamError) -> ErrorEnvelope:
    retryable: bool | None
    if exc.error_type in (ErrorType.RATE_LIMITED, ErrorType.TIMEOUT):
        retryable = True
    elif exc.error_type in (ErrorType.AUTH_FAILED, ErrorType.NOT_FOUND):
        retryable = False
    else:
        retryable = None
    return ErrorEnvelope(
        error_type=exc.error_type,
        message=exc.message,
        retryable=retryable,
    )


def request_error(message: str) -> ErrorEnvelope:
    return ErrorEnvelope(
        error_type=ErrorType.TOOL_ERROR,
        message=message,
        retryable=False,
    )
