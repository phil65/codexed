"""Pydantic models for Codex JSON-RPC API requests and responses."""

from __future__ import annotations

from typing import Literal

from codexed.models.base import CodexBaseModel


class BaseCommandAction(CodexBaseModel):
    """Base command action model."""

    command: str


class CommandActionRead(BaseCommandAction):
    """Read command action."""

    type: Literal["read"] = "read"
    name: str
    path: str


class CommandActionListFiles(BaseCommandAction):
    """List files command action."""

    type: Literal["listFiles"] = "listFiles"
    path: str | None = None


class CommandActionSearch(BaseCommandAction):
    """Search command action."""

    type: Literal["search"] = "search"
    query: str | None = None
    path: str | None = None


class CommandActionUnknown(BaseCommandAction):
    """Unknown command action."""

    type: Literal["unknown"] = "unknown"


# Discriminated union of command actions
CommandAction = (
    CommandActionRead | CommandActionListFiles | CommandActionSearch | CommandActionUnknown
)
