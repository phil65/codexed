"""Codex event types for streaming.

Uses discriminated unions with TypeAdapter for type-safe event parsing.
Each event type is a proper BaseModel with the method as the discriminator.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Literal

from pydantic import Field, TypeAdapter

from codexed.models.base import CodexBaseModel
from codexed.models.event_data import (
    ItemCompletedData,
    ItemStartedData,
    ThreadStartedData,
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
    RawResponseItemCompletedNotification,
    ServerRequestResolvedMessage,
    ThreadArchivedMessage,
    ThreadCompactedMessage,
    ThreadNameUpdatedMessage,
    ThreadRealtimeClosedMessage,
    ThreadRealtimeErrorMessage,
    ThreadRealtimeItemAddedMessage,
    ThreadRealtimeOutputAudioDeltaMessage,
    ThreadRealtimeStartedMessage,
    ThreadRealtimeTranscriptUpdatedMessage,
    ThreadStatusChangedMessage,
    ThreadTokenUsageUpdatedNotification,
    ThreadUnarchivedMessage,
    TurnDiffUpdatedMessage,
    TurnPlanUpdatedMessage,
    WindowsWorldWritableWarningMessage,
)


if TYPE_CHECKING:
    from codexed.models import TokenUsageBreakdown


# ============================================================================
# Thread lifecycle events
# ============================================================================


class ThreadStartedEvent(CodexBaseModel):
    """Thread started event."""

    method: Literal["thread/started"] = "thread/started"
    params: ThreadStartedData


class ThreadTokenUsageUpdatedEvent(CodexBaseModel):
    """Thread token usage updated event."""

    method: Literal["thread/tokenUsage/updated"] = "thread/tokenUsage/updated"
    params: ThreadTokenUsageUpdatedNotification

    @property
    def total(self) -> TokenUsageBreakdown:
        """Total Token usage of the Thread."""
        return self.params.token_usage.total

    @property
    def last(self) -> TokenUsageBreakdown:
        """Token usage of last turn."""
        return self.params.token_usage.last

    @property
    def context_window(self) -> int | None:
        """Model context window."""
        return self.params.token_usage.model_context_window


# ============================================================================
# Turn lifecycle events
# ============================================================================


class TurnStartedEvent(CodexBaseModel):
    """Turn started event."""

    method: Literal["turn/started"] = "turn/started"
    params: TurnStartedData


class TurnCompletedEvent(CodexBaseModel):
    """Turn completed event."""

    method: Literal["turn/completed"] = "turn/completed"
    params: TurnCompletedData


# ============================================================================
# Item lifecycle events
# ============================================================================


class ItemStartedEvent(CodexBaseModel):
    """Item started event."""

    method: Literal["item/started"] = "item/started"
    params: ItemStartedData


class ItemCompletedEvent(CodexBaseModel):
    """Item completed event."""

    method: Literal["item/completed"] = "item/completed"
    params: ItemCompletedData


class RawResponseItemCompletedEvent(CodexBaseModel):
    """Raw response item completed event."""

    method: Literal["rawResponseItem/completed"] = "rawResponseItem/completed"
    params: RawResponseItemCompletedNotification


# ============================================================================
# Discriminated union of all event types
# ============================================================================


CodexEvent = Annotated[
    # Error events
    ErrorMessage
    # Thread lifecycle
    | ThreadStartedEvent
    | ThreadStatusChangedMessage
    | ThreadArchivedMessage
    | ThreadUnarchivedMessage
    | ThreadNameUpdatedMessage
    | ThreadTokenUsageUpdatedEvent
    # Turn lifecycle
    | TurnStartedEvent
    | TurnCompletedEvent
    | TurnDiffUpdatedMessage
    | TurnPlanUpdatedMessage
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
    | ThreadCompactedMessage
    | ServerRequestResolvedMessage,
    Field(discriminator="method"),
]


# TypeAdapter for parsing events
codex_event_adapter: TypeAdapter[CodexEvent] = TypeAdapter(CodexEvent)


# Type alias for all delta events
DeltaEvent = (
    ItemAgentMessageDeltaNotification
    | ItemPlanDeltaNotification
    | ItemReasoningTextDeltaNotification
    | ItemReasoningSummaryTextDeltaNotification
    | ItemCommandExecutionOutputDeltaNotification
    | ItemFileChangeOutputDeltaNotification
)
