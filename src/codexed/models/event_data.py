from __future__ import annotations

from typing import Any

from codexed.models.base import CodexBaseModel
from codexed.models.misc import Thread, Turn, TurnPlanStep
from codexed.models.thread_item import ThreadItem
from codexed.models.thread_status import ThreadStatusValue
from codexed.models.v2_protocol import (
    AccountLoginCompletedNotification,
    AccountRateLimitsUpdatedNotification,
    AccountUpdatedNotification,
    AgentMessageDeltaNotification,
    AppListUpdatedNotification,
    CommandExecutionOutputDeltaNotification,
    ConfigWarningNotification,
    ContextCompactedNotification,
    DeprecationNoticeNotification,
    ErrorNotification,
    FileChangeOutputDeltaNotification,
    McpServerOauthLoginCompletedNotification,
    McpServerStatusUpdatedNotification,
    McpToolCallProgressNotification,
    ModelReroutedNotification,
    PlanDeltaNotification,
    ReasoningSummaryPartAddedNotification,
    ReasoningSummaryTextDeltaNotification,
    ReasoningTextDeltaNotification,
    ServerRequestResolvedNotification,
    TerminalInteractionNotification,
    ThreadArchivedNotification,
    ThreadNameUpdatedNotification,
    ThreadTokenUsage,
    ThreadUnarchiveParams,
    TurnDiffUpdatedNotification,
    WindowsWorldWritableWarningNotification,
)


class TurnPlanUpdatedData(CodexBaseModel):
    """Payload for turn/plan/updated notification."""

    thread_id: str
    turn_id: str
    explanation: str | None = None
    plan: list[TurnPlanStep]


# Item lifecycle notifications


class ItemStartedData(CodexBaseModel):
    """Payload for item/started notification (V2 protocol)."""

    thread_id: str
    turn_id: str
    item: ThreadItem


class ItemCompletedData(CodexBaseModel):
    """Payload for item/completed notification (V2 protocol)."""

    thread_id: str
    turn_id: str
    item: ThreadItem


class RawResponseItemCompletedData(CodexBaseModel):
    """Payload for rawResponseItem/completed notification."""

    thread_id: str
    turn_id: str
    item: ThreadItem


class ThreadStartedData(CodexBaseModel):
    """Payload for thread/started notification (V2 protocol)."""

    thread: Thread

    @property
    def thread_id(self) -> str:
        """Thread ID derived from the thread object."""
        return self.thread.id


class ThreadStatusChangedData(CodexBaseModel):
    """Payload for thread/status/changed notification."""

    thread_id: str
    status: ThreadStatusValue


class ThreadTokenUsageUpdatedData(CodexBaseModel):
    """Payload for thread/tokenUsage/updated notification (V2 protocol)."""

    thread_id: str
    turn_id: str
    token_usage: ThreadTokenUsage


# Turn lifecycle notifications


class TurnStartedData(CodexBaseModel):
    """Payload for turn/started notification (V2 protocol)."""

    thread_id: str
    turn: Turn


class TurnCompletedData(CodexBaseModel):
    """Payload for turn/completed notification (V2 protocol)."""

    thread_id: str
    turn: Turn


class TurnErrorData(CodexBaseModel):
    """Payload for turn/error notification."""

    thread_id: str
    turn_id: str
    error: str


class SessionConfiguredData(CodexBaseModel):
    """Payload for sessionConfigured notification."""

    config: dict[str, Any]  # Session config - flexible structure


# Union type of all event data
EventData = (
    # Thread lifecycle
    ThreadStartedData
    | ThreadStatusChangedData
    | ThreadArchivedNotification
    | ThreadUnarchiveParams
    | ThreadNameUpdatedNotification
    | ThreadTokenUsageUpdatedData
    | ContextCompactedNotification
    # Turn lifecycle
    | TurnStartedData
    | TurnCompletedData
    | TurnErrorData
    | TurnDiffUpdatedNotification
    | TurnPlanUpdatedData
    # Item lifecycle
    | ItemStartedData
    | ItemCompletedData
    | RawResponseItemCompletedData
    # Item deltas - agent messages
    | AgentMessageDeltaNotification
    # Item deltas - plan
    | PlanDeltaNotification
    # Item deltas - reasoning
    | ReasoningTextDeltaNotification
    | ReasoningSummaryTextDeltaNotification
    | ReasoningSummaryPartAddedNotification
    # Item deltas - command execution
    | CommandExecutionOutputDeltaNotification
    | TerminalInteractionNotification
    # Item deltas - file changes
    | FileChangeOutputDeltaNotification
    # Item deltas - MCP tool calls
    | McpToolCallProgressNotification
    # MCP server status
    | McpServerStatusUpdatedNotification
    # MCP OAuth
    | McpServerOauthLoginCompletedNotification
    # Account/Auth events
    | AccountUpdatedNotification
    | AccountRateLimitsUpdatedNotification
    | AccountLoginCompletedNotification
    # System events
    | SessionConfiguredData
    | DeprecationNoticeNotification
    | WindowsWorldWritableWarningNotification
    # Error events
    | ErrorNotification
    # New events
    | ModelReroutedNotification
    | ConfigWarningNotification
    | AppListUpdatedNotification
    | ContextCompactedNotification
    | ServerRequestResolvedNotification
)
