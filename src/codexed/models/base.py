import os
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


IS_DEV = os.environ.get("CODEXED_STRICT_MODELS") == "1"
"""Strict models (``extra="forbid"``): set in this repo's tests (``tests/conftest.py``).

Not inferred from ``"pytest" in sys.modules``: any process that imported pytest (another
project's tests, a notebook) would reject events with fields newer than the schema.
"""


class CodexBaseModel(BaseModel):
    """Base model for all Codex API models.

    Provides:
    - Strict validation in tests (``CODEXED_STRICT_MODELS=1``: forbids extra fields to catch
      schema changes)
    - Lenient validation in production (ignores extra fields for forward compat)
    - Snake_case Python fields with camelCase JSON aliases
    - Both field names and aliases accepted for parsing (populate_by_name=True)
    """

    model_config = ConfigDict(
        extra="forbid" if IS_DEV else "ignore",
        populate_by_name=True,
        alias_generator=to_camel,
        defer_build=True,
    )


class JsonRpcRequest(CodexBaseModel):
    """JSON-RPC 2.0 request message."""

    jsonrpc: Literal["2.0"] = "2.0"
    id: int
    method: str
    params: dict[str, Any] = Field(default_factory=dict)  # Method-specific params


class JsonRpcError(CodexBaseModel):
    """JSON-RPC 2.0 error object."""

    code: int
    message: str
    data: Any = None


class JsonRpcResponse(CodexBaseModel):
    """JSON-RPC 2.0 response message."""

    jsonrpc: Literal["2.0"] = "2.0"
    id: int
    result: Any = None
    error: JsonRpcError | None = None


class JsonRpcNotification(CodexBaseModel):
    """JSON-RPC 2.0 notification message (no id)."""

    jsonrpc: Literal["2.0"] = "2.0"
    method: str
    params: dict[str, Any] | None = None  # Event-specific params
