"""Codex adapter exceptions.

Provides a rich error hierarchy for JSON-RPC errors from the Codex app-server,
with automatic classification of retryable/overload errors.
"""

from __future__ import annotations

from typing import Any


# JSON-RPC 2.0 standard error codes
JSONRPC_PARSE_ERROR = -32700
JSONRPC_INVALID_REQUEST = -32600
JSONRPC_METHOD_NOT_FOUND = -32601
JSONRPC_INVALID_PARAMS = -32602
JSONRPC_INTERNAL_ERROR = -32603
JSONRPC_SERVER_ERROR_MIN = -32099
JSONRPC_SERVER_ERROR_MAX = -32000


class CodexError(Exception):
    """Base exception for Codex adapter errors."""


class CodexProcessError(CodexError):
    """Error starting or communicating with the Codex app-server process."""


class TransportClosedError(CodexProcessError):
    """Raised when the app-server transport closes unexpectedly."""


class CodexRequestError(CodexError):
    """Error from a Codex app-server request (JSON-RPC error response)."""

    def __init__(self, code: int, message: str, data: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data or {}

    def __str__(self) -> str:
        if self.data:
            return f"[{self.code}] {self.message}: {self.data}"
        return f"[{self.code}] {self.message}"


# ============================================================================
# Typed JSON-RPC error subclasses
# ============================================================================


class ParseError(CodexRequestError):
    """JSON-RPC parse error (-32700)."""


class InvalidRequestError(CodexRequestError):
    """JSON-RPC invalid request (-32600)."""


class MethodNotFoundError(CodexRequestError):
    """JSON-RPC method not found (-32601)."""


class InvalidParamsError(CodexRequestError):
    """JSON-RPC invalid params (-32602)."""


class InternalRpcError(CodexRequestError):
    """JSON-RPC internal error (-32603)."""


class ServerBusyError(CodexRequestError):
    """Server is overloaded / unavailable and caller should retry."""


class RetryLimitExceededError(ServerBusyError):
    """Server exhausted internal retry budget for a retryable operation."""


class TurnFailedError(CodexError):
    """Raised when a turn completes with failed status."""

    def __init__(self, message: str, *, turn_id: str) -> None:
        super().__init__(message)
        self.turn_id = turn_id


# ============================================================================
# Error classification helpers
# ============================================================================


def _contains_retry_limit_text(message: str) -> bool:
    lowered = message.lower()
    return "retry limit" in lowered or "too many failed attempts" in lowered


def _is_server_overloaded(data: Any) -> bool:  # noqa: PLR0911
    """Check recursively whether error data indicates server overload."""
    if data is None:
        return False

    if isinstance(data, str):
        return data.lower() == "server_overloaded"

    if isinstance(data, dict):
        direct = data.get("codex_error_info") or data.get("codexErrorInfo") or data.get("errorInfo")
        if isinstance(direct, str) and direct.lower() == "server_overloaded":
            return True
        if isinstance(direct, dict):
            for value in direct.values():
                if isinstance(value, str) and value.lower() == "server_overloaded":
                    return True
        for value in data.values():
            if _is_server_overloaded(value):
                return True

    if isinstance(data, list):
        return any(_is_server_overloaded(value) for value in data)

    return False


def map_jsonrpc_error(  # noqa: PLR0911
    code: int,
    message: str,
    data: dict[str, Any] | None = None,
) -> CodexRequestError:
    """Map a raw JSON-RPC error into a typed SDK exception.

    Args:
        code: JSON-RPC error code.
        message: Error message from the server.
        data: Optional error data payload.

    Returns:
        Appropriately typed CodexRequestError subclass.
    """
    if code == JSONRPC_PARSE_ERROR:
        return ParseError(code, message, data)
    if code == JSONRPC_INVALID_REQUEST:
        return InvalidRequestError(code, message, data)
    if code == JSONRPC_METHOD_NOT_FOUND:
        return MethodNotFoundError(code, message, data)
    if code == JSONRPC_INVALID_PARAMS:
        return InvalidParamsError(code, message, data)
    if code == JSONRPC_INTERNAL_ERROR:
        return InternalRpcError(code, message, data)

    if JSONRPC_SERVER_ERROR_MIN <= code <= JSONRPC_SERVER_ERROR_MAX:
        if _is_server_overloaded(data):
            if _contains_retry_limit_text(message):
                return RetryLimitExceededError(code, message, data)
            return ServerBusyError(code, message, data)
        if _contains_retry_limit_text(message):
            return RetryLimitExceededError(code, message, data)

    return CodexRequestError(code, message, data)


def is_retryable_error(exc: BaseException) -> bool:
    """Check if an exception is a transient overload-style error worth retrying.

    Args:
        exc: The exception to check.

    Returns:
        True if the error is transient and the operation should be retried.
    """
    if isinstance(exc, ServerBusyError):
        return True
    if isinstance(exc, CodexRequestError):
        return _is_server_overloaded(exc.data)
    return False
