from __future__ import annotations

from typing import Literal

from pydantic import Field

from codexed.models.base import CodexBaseModel
from codexed.models.codex_types import ThreadActiveFlag


class ThreadStatusNotLoaded(CodexBaseModel):
    """Thread status: not loaded."""

    type: Literal["notLoaded"] = "notLoaded"


class ThreadStatusIdle(CodexBaseModel):
    """Thread status: idle."""

    type: Literal["idle"] = "idle"


class ThreadStatusSystemError(CodexBaseModel):
    """Thread status: system error."""

    type: Literal["systemError"] = "systemError"


class ThreadStatusActive(CodexBaseModel):
    """Thread status: active."""

    type: Literal["active"] = "active"
    active_flags: list[ThreadActiveFlag] = Field(default_factory=list)


ThreadStatusValue = (
    ThreadStatusNotLoaded | ThreadStatusIdle | ThreadStatusSystemError | ThreadStatusActive
)
