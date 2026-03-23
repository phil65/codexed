"""Hook models for the Codex app-server protocol.

Hooks are user-defined commands that run at specific lifecycle events
(session start, user prompt submit, stop). They can inspect context,
inject system messages, or block operations.

See: https://github.com/openai/codex/tree/main/codex-rs/hooks
"""

from __future__ import annotations

from typing import Literal

from codexed.models.base import CodexBaseModel


# ============================================================================
# Enums / Literal types
# ============================================================================

HookEventName = Literal["sessionStart", "userPromptSubmit", "stop"]
"""Lifecycle event that triggers hooks."""

HookHandlerType = Literal["command", "prompt", "agent"]
"""How the hook is executed. Only 'command' is currently supported."""

HookExecutionMode = Literal["sync", "async"]
"""Whether the hook blocks the operation or runs in the background."""

HookScope = Literal["thread", "turn"]
"""Scope of the hook run."""

HookRunStatus = Literal["running", "completed", "failed", "blocked", "stopped"]
"""Current execution status of a hook run."""

HookOutputEntryKind = Literal["warning", "stop", "feedback", "context", "error"]
"""Kind of output entry produced by a hook."""


# ============================================================================
# Data models
# ============================================================================


class HookOutputEntry(CodexBaseModel):
    """Single output entry from a hook run."""

    kind: HookOutputEntryKind
    text: str


class HookRunSummary(CodexBaseModel):
    """Summary of a hook run, sent with started/completed notifications."""

    id: str
    event_name: HookEventName
    handler_type: HookHandlerType
    execution_mode: HookExecutionMode
    scope: HookScope
    source_path: str
    display_order: int
    status: HookRunStatus
    status_message: str | None = None
    started_at: int
    completed_at: int | None = None
    duration_ms: int | None = None
    entries: list[HookOutputEntry]


# ============================================================================
# Notification data (params for hook/started and hook/completed)
# ============================================================================


class HookStartedData(CodexBaseModel):
    """Data for hook/started notification."""

    thread_id: str
    turn_id: str | None = None
    run: HookRunSummary


class HookCompletedData(CodexBaseModel):
    """Data for hook/completed notification."""

    thread_id: str
    turn_id: str | None = None
    run: HookRunSummary
