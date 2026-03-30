from __future__ import annotations

from typing import Any

from codexed.models.base import CodexBaseModel
from codexed.models.codex_types import McpServerStartupState, ModelRerouteReason
from codexed.models.misc import Thread, Turn, TurnError, TurnPlanStep
from codexed.models.thread_item import ThreadItem
from codexed.models.thread_status import ThreadStatusValue
from codexed.models.v2_protocol import (
    AccountLoginCompletedNotification,
    AccountRateLimitsUpdatedNotification,
    AccountUpdatedNotification,
    AgentMessageDeltaNotification,
    AppInfo,
    CommandExecutionOutputDeltaNotification,
    ContextCompactedNotification,
    FileChangeOutputDeltaNotification,
    PlanDeltaNotification,
    ReasoningSummaryPartAddedNotification,
    ReasoningSummaryTextDeltaNotification,
    ReasoningTextDeltaNotification,
    ServerRequestResolvedNotification,
    TextRange,
    ThreadTokenUsage,
    ThreadUnarchiveParams,
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


# Item delta notifications


class CommandExecutionTerminalInteractionData(CodexBaseModel):
    """Payload for item/commandExecution/terminalInteraction notification."""

    thread_id: str
    turn_id: str
    item_id: str
    process_id: str
    stdin: str


class McpToolCallProgressData(CodexBaseModel):
    """Payload for item/mcpToolCall/progress notification."""

    thread_id: str
    turn_id: str
    item_id: str
    message: str


# MCP/Account/System notifications


class McpServerStartupStatusUpdatedData(CodexBaseModel):
    """Payload for mcpServer/startupStatus/updated notification."""

    name: str
    status: McpServerStartupState
    error: str | None = None


class McpServerOAuthLoginCompletedData(CodexBaseModel):
    """Payload for mcpServer/oauthLogin/completed notification."""

    name: str
    success: bool
    error: str | None = None


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


class ThreadArchivedData(CodexBaseModel):
    """Payload for thread/archived notification."""

    thread_id: str


class ThreadNameUpdatedData(CodexBaseModel):
    """Payload for thread/name/updated notification."""

    thread_id: str
    thread_name: str | None = None


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


class TurnDiffUpdatedData(CodexBaseModel):
    """Payload for turn/diff/updated notification."""

    thread_id: str
    turn_id: str
    diff: str


class AuthStatusChangeData(CodexBaseModel):
    """Payload for authStatusChange notification (legacy v1)."""

    status: str


class LoginChatGptCompleteData(CodexBaseModel):
    """Payload for loginChatGptComplete notification (legacy v1)."""

    success: bool


class SessionConfiguredData(CodexBaseModel):
    """Payload for sessionConfigured notification."""

    config: dict[str, Any]  # Session config - flexible structure


class DeprecationNoticeData(CodexBaseModel):
    """Payload for deprecationNotice notification."""

    summary: str
    details: str | None = None


class WindowsWorldWritableWarningData(CodexBaseModel):
    """Payload for windows/worldWritableWarning notification."""

    sample_paths: list[str]
    extra_count: int
    failed_scan: bool


class ErrorEventData(CodexBaseModel):
    """Payload for error event."""

    error: TurnError
    will_retry: bool
    thread_id: str
    turn_id: str


class ModelReroutedData(CodexBaseModel):
    """Payload for model/rerouted notification."""

    thread_id: str
    turn_id: str
    from_model: str
    to_model: str
    reason: ModelRerouteReason


class ConfigWarningData(CodexBaseModel):
    """Payload for configWarning notification."""

    summary: str
    details: str | None = None
    path: str | None = None
    range: TextRange | None = None


class AppListUpdatedData(CodexBaseModel):
    """Payload for app/list/updated notification."""

    data: list[AppInfo]


# Union type of all event data
EventData = (
    # Thread lifecycle
    ThreadStartedData
    | ThreadStatusChangedData
    | ThreadArchivedData
    | ThreadUnarchiveParams
    | ThreadNameUpdatedData
    | ThreadTokenUsageUpdatedData
    | ContextCompactedNotification
    # Turn lifecycle
    | TurnStartedData
    | TurnCompletedData
    | TurnErrorData
    | TurnDiffUpdatedData
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
    | CommandExecutionTerminalInteractionData
    # Item deltas - file changes
    | FileChangeOutputDeltaNotification
    # Item deltas - MCP tool calls
    | McpToolCallProgressData
    # MCP server status
    | McpServerStartupStatusUpdatedData
    # MCP OAuth
    | McpServerOAuthLoginCompletedData
    # Account/Auth events
    | AccountUpdatedNotification
    | AccountRateLimitsUpdatedNotification
    | AccountLoginCompletedNotification
    | AuthStatusChangeData
    | LoginChatGptCompleteData
    # System events
    | SessionConfiguredData
    | DeprecationNoticeData
    | WindowsWorldWritableWarningData
    # Error events
    | ErrorEventData
    # New events
    | ModelReroutedData
    | ConfigWarningData
    | AppListUpdatedData
    | ContextCompactedNotification
    | ServerRequestResolvedNotification
)
