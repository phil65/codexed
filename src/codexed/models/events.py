"""Codex event types for streaming.

Uses discriminated unions with TypeAdapter for type-safe event parsing.
Each event type is a proper BaseModel with the event_type as the discriminator.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Literal

from pydantic import Field, TypeAdapter

from codexed.models.base import CodexBaseModel
from codexed.models.event_data import (
    ItemCompletedData,
    ItemStartedData,
    RawResponseItemCompletedData,
    ThreadStartedData,
    ThreadStatusChangedData,
    ThreadTokenUsageUpdatedData,
    TurnCompletedData,
    TurnStartedData,
)
from codexed.models.v2_protocol import (
    AccountLoginCompletedMessage,
    AccountRateLimitsUpdatedMessage,
    AccountUpdatedMessage,
    AppListUpdatedMessage,
    CommandExecOutputDeltaMessage,
    ConfigWarningMessage,
    DeprecationNoticeMessage,
    ErrorMessage,
    FsChangedMessage,
    FuzzyFileSearchSessionCompletedMessage,
    FuzzyFileSearchSessionUpdatedMessage,
    HookCompletedMessage,
    HookStartedMessage,
    ItemAgentMessageDeltaNotification,
    ItemCommandExecutionOutputDeltaNotification,
    ItemCommandExecutionTerminalInteractionNotification,
    ItemFileChangeOutputDeltaNotification,
    ItemMcpToolCallProgressNotification,
    ItemPlanDeltaNotification,
    ItemReasoningSummaryPartAddedNotification,
    ItemReasoningSummaryTextDeltaNotification,
    ItemReasoningTextDeltaNotification,
    McpServerOauthLoginCompletedMessage,
    McpServerStartupStatusUpdatedNotification,
    ModelReroutedMessage,
    ServerRequestResolvedMessage,
    ThreadArchivedNotification,
    ThreadCompactedNotification,
    ThreadNameUpdatedNotification,
    ThreadRealtimeClosedMessage,
    ThreadRealtimeErrorMessage,
    ThreadRealtimeItemAddedMessage,
    ThreadRealtimeOutputAudioDeltaMessage,
    ThreadRealtimeStartedMessage,
    ThreadRealtimeTranscriptUpdatedMessage,
    ThreadUnarchiveParams,
    TurnDiffUpdatedNotification,
    TurnPlanUpdatedNotification,
    WindowsWorldWritableWarningMessage,
)


if TYPE_CHECKING:
    from codexed.models import TokenUsageBreakdown


# ============================================================================
# Thread lifecycle events
# ============================================================================


class ThreadStartedEvent(CodexBaseModel):
    """Thread started event."""

    event_type: Literal["thread/started"] = "thread/started"
    data: ThreadStartedData


class ThreadStatusChangedEvent(CodexBaseModel):
    """Thread status changed event."""

    event_type: Literal["thread/status/changed"] = "thread/status/changed"
    data: ThreadStatusChangedData


class ThreadArchivedEvent(CodexBaseModel):
    """Thread archived event."""

    event_type: Literal["thread/archived"] = "thread/archived"
    data: ThreadArchivedNotification


class ThreadUnarchivedEvent(CodexBaseModel):
    """Thread unarchived event."""

    event_type: Literal["thread/unarchived"] = "thread/unarchived"
    data: ThreadUnarchiveParams


class ThreadNameUpdatedEvent(CodexBaseModel):
    """Thread name updated event."""

    event_type: Literal["thread/name/updated"] = "thread/name/updated"
    data: ThreadNameUpdatedNotification


class ThreadTokenUsageUpdatedEvent(CodexBaseModel):
    """Thread token usage updated event."""

    event_type: Literal["thread/tokenUsage/updated"] = "thread/tokenUsage/updated"
    data: ThreadTokenUsageUpdatedData

    @property
    def total(self) -> TokenUsageBreakdown:
        """Total Token usage of the Thread."""
        return self.data.token_usage.total

    @property
    def last(self) -> TokenUsageBreakdown:
        """Token usage of last turn."""
        return self.data.token_usage.last

    @property
    def context_window(self) -> int | None:
        """Model context window."""
        return self.data.token_usage.model_context_window


# ============================================================================
# Turn lifecycle events
# ============================================================================


class TurnStartedEvent(CodexBaseModel):
    """Turn started event."""

    event_type: Literal["turn/started"] = "turn/started"
    data: TurnStartedData


class TurnCompletedEvent(CodexBaseModel):
    """Turn completed event."""

    event_type: Literal["turn/completed"] = "turn/completed"
    data: TurnCompletedData


class TurnDiffUpdatedEvent(CodexBaseModel):
    """Turn diff updated event."""

    event_type: Literal["turn/diff/updated"] = "turn/diff/updated"
    data: TurnDiffUpdatedNotification


class TurnPlanUpdatedEvent(CodexBaseModel):
    """Turn plan updated event."""

    event_type: Literal["turn/plan/updated"] = "turn/plan/updated"
    data: TurnPlanUpdatedNotification


# ============================================================================
# Item lifecycle events
# ============================================================================


class ItemStartedEvent(CodexBaseModel):
    """Item started event."""

    event_type: Literal["item/started"] = "item/started"
    data: ItemStartedData


class ItemCompletedEvent(CodexBaseModel):
    """Item completed event."""

    event_type: Literal["item/completed"] = "item/completed"
    data: ItemCompletedData


class RawResponseItemCompletedEvent(CodexBaseModel):
    """Raw response item completed event."""

    event_type: Literal["rawResponseItem/completed"] = "rawResponseItem/completed"
    data: RawResponseItemCompletedData


# ============================================================================
# Discriminated union of all event types
# ============================================================================


CodexEvent = Annotated[
    # Error events
    ErrorMessage
    # Thread lifecycle
    | ThreadStartedEvent
    | ThreadStatusChangedEvent
    | ThreadArchivedEvent
    | ThreadUnarchivedEvent
    | ThreadNameUpdatedEvent
    | ThreadTokenUsageUpdatedEvent
    # Turn lifecycle
    | TurnStartedEvent
    | TurnCompletedEvent
    | TurnDiffUpdatedEvent
    | TurnPlanUpdatedEvent
    # Hook events
    | HookStartedMessage
    | HookCompletedMessage
    # Realtime voice events (EXPERIMENTAL)
    | ThreadRealtimeStartedMessage
    | ThreadRealtimeItemAddedMessage
    | ThreadRealtimeTranscriptUpdatedMessage
    | ThreadRealtimeOutputAudioDeltaMessage
    | ThreadRealtimeErrorMessage
    | ThreadRealtimeClosedMessage
    # Terminal control events
    | CommandExecOutputDeltaMessage
    # Fuzzy file search events (EXPERIMENTAL)
    | FuzzyFileSearchSessionUpdatedMessage
    | FuzzyFileSearchSessionCompletedMessage
    # Item lifecycle
    | ItemStartedEvent
    | ItemCompletedEvent
    | RawResponseItemCompletedEvent
    # Item deltas - agent messages
    | ItemAgentMessageDeltaNotification
    # Item deltas - plan
    | ItemPlanDeltaNotification
    # Item deltas - reasoning
    | ItemReasoningSummaryTextDeltaNotification
    | ItemReasoningSummaryPartAddedNotification
    | ItemReasoningTextDeltaNotification
    # Item deltas - command execution
    | ItemCommandExecutionOutputDeltaNotification
    | ItemCommandExecutionTerminalInteractionNotification
    # Item deltas - file changes
    | ItemFileChangeOutputDeltaNotification
    # Item deltas - MCP tool calls
    | ItemMcpToolCallProgressNotification
    # MCP server status
    | McpServerStartupStatusUpdatedNotification
    # MCP OAuth
    | McpServerOauthLoginCompletedMessage
    # Account/Auth events
    | AccountUpdatedMessage
    | AccountRateLimitsUpdatedMessage
    | AccountLoginCompletedMessage
    # System events
    | DeprecationNoticeMessage
    | WindowsWorldWritableWarningMessage
    # New events
    | ModelReroutedMessage
    | ConfigWarningMessage
    | AppListUpdatedMessage
    | FsChangedMessage
    | ThreadCompactedNotification
    | ServerRequestResolvedMessage,
    Field(discriminator="event_type"),
]


# TypeAdapter for parsing events
codex_event_adapter: TypeAdapter[CodexEvent] = TypeAdapter(CodexEvent)


# ============================================================================
# Event type literals (for external use)
# ============================================================================


EventType = Literal[
    # Error events
    "error",
    # Thread lifecycle
    "thread/started",
    "thread/status/changed",
    "thread/archived",
    "thread/unarchived",
    "thread/name/updated",
    "thread/tokenUsage/updated",
    "thread/compacted",
    # Turn lifecycle
    "turn/started",
    "turn/completed",
    "turn/error",
    "turn/diff/updated",
    "turn/plan/updated",
    # Hook events
    "hook/started",
    "hook/completed",
    # Realtime voice events (EXPERIMENTAL)
    "thread/realtime/started",
    "thread/realtime/itemAdded",
    "thread/realtime/transcriptUpdated",
    "thread/realtime/outputAudio/delta",
    "thread/realtime/error",
    "thread/realtime/closed",
    # Terminal control events
    "command/exec/outputDelta",
    # Fuzzy file search events (EXPERIMENTAL)
    "fuzzyFileSearch/sessionUpdated",
    "fuzzyFileSearch/sessionCompleted",
    # Item lifecycle
    "item/started",
    "item/completed",
    "rawResponseItem/completed",
    # Item deltas - agent messages
    "item/agentMessage/delta",
    # Item deltas - plan
    "item/plan/delta",
    # Item deltas - reasoning
    "item/reasoning/summaryTextDelta",
    "item/reasoning/summaryPartAdded",
    "item/reasoning/textDelta",
    # Item deltas - command execution
    "item/commandExecution/outputDelta",
    "item/commandExecution/terminalInteraction",
    # Item deltas - file changes
    "item/fileChange/outputDelta",
    # Item deltas - MCP tool calls
    "item/mcpToolCall/progress",
    # MCP server status
    "mcpServer/startupStatus/updated",
    # MCP OAuth
    "mcpServer/oauthLogin/completed",
    # Account/Auth events
    "account/updated",
    "account/rateLimits/updated",
    "account/login/completed",
    "authStatusChange",
    "loginChatGptComplete",
    # System events
    "sessionConfigured",
    "deprecationNotice",
    "windows/worldWritableWarning",
    # New events
    "model/rerouted",
    "configWarning",
    "app/list/updated",
    "fs/changed",
    "thread/compacted/v2",
    "serverRequest/resolved",
]


# Type alias for all delta events
DeltaEvent = (
    ItemAgentMessageDeltaNotification
    | ItemPlanDeltaNotification
    | ItemReasoningTextDeltaNotification
    | ItemReasoningSummaryTextDeltaNotification
    | ItemCommandExecutionOutputDeltaNotification
    | ItemFileChangeOutputDeltaNotification
)
