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
    TurnErrorData,
    TurnPlanUpdatedData,
    TurnStartedData,
)
from codexed.models.v2_protocol import (
    AccountLoginCompletedMessage,
    AccountRateLimitsUpdatedMessage,
    AccountUpdatedNotification,
    AgentMessageDeltaNotification,
    AppListUpdatedMessage,
    CommandExecOutputDeltaNotification,
    CommandExecutionOutputDeltaNotification,
    ConfigWarningMessage,
    ContextCompactedNotification,
    DeprecationNoticeMessage,
    ErrorNotification,
    FileChangeOutputDeltaNotification,
    FsChangedMessage,
    FuzzyFileSearchSessionCompletedNotification,
    FuzzyFileSearchSessionUpdatedNotification,
    HookCompletedNotification,
    HookStartedNotification,
    McpServerOauthLoginCompletedNotification,
    McpServerStatusUpdatedNotification,
    McpToolCallProgressNotification,
    ModelReroutedMessage,
    PlanDeltaNotification,
    ReasoningSummaryPartAddedNotification,
    ReasoningSummaryTextDeltaNotification,
    ReasoningTextDeltaNotification,
    ServerRequestResolvedMessage,
    TerminalInteractionNotification,
    ThreadArchivedNotification,
    ThreadCompactedNotification,
    ThreadNameUpdatedNotification,
    ThreadRealtimeClosedNotification,
    ThreadRealtimeErrorNotification,
    ThreadRealtimeItemAddedNotification,
    ThreadRealtimeOutputAudioDeltaNotification,
    ThreadRealtimeStartedNotification,
    ThreadRealtimeTranscriptUpdatedNotification,
    ThreadUnarchiveParams,
    TurnDiffUpdatedNotification,
    WindowsWorldWritableWarningMessage,
)


if TYPE_CHECKING:
    from codexed.models import TokenUsageBreakdown


class ErrorEvent(CodexBaseModel):
    """Error event from the Codex server."""

    event_type: Literal["error"] = "error"
    data: ErrorNotification


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


class ThreadCompactedEvent(CodexBaseModel):
    """Thread compacted event."""

    event_type: Literal["thread/compacted"] = "thread/compacted"
    data: ContextCompactedNotification


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


class TurnErrorEvent(CodexBaseModel):
    """Turn error event."""

    event_type: Literal["turn/error"] = "turn/error"
    data: TurnErrorData


class TurnDiffUpdatedEvent(CodexBaseModel):
    """Turn diff updated event."""

    event_type: Literal["turn/diff/updated"] = "turn/diff/updated"
    data: TurnDiffUpdatedNotification


class TurnPlanUpdatedEvent(CodexBaseModel):
    """Turn plan updated event."""

    event_type: Literal["turn/plan/updated"] = "turn/plan/updated"
    data: TurnPlanUpdatedData


# ============================================================================
# Hook events
# ============================================================================


class HookStartedEvent(CodexBaseModel):
    """Hook started event."""

    event_type: Literal["hook/started"] = "hook/started"
    data: HookStartedNotification


class HookCompletedEvent(CodexBaseModel):
    """Hook completed event."""

    event_type: Literal["hook/completed"] = "hook/completed"
    data: HookCompletedNotification


# ============================================================================
# Realtime voice events (EXPERIMENTAL)
# ============================================================================


class RealtimeStartedEvent(CodexBaseModel):
    """Realtime session started event."""

    event_type: Literal["thread/realtime/started"] = "thread/realtime/started"
    data: ThreadRealtimeStartedNotification


class RealtimeItemAddedEvent(CodexBaseModel):
    """Realtime item added event."""

    event_type: Literal["thread/realtime/itemAdded"] = "thread/realtime/itemAdded"
    data: ThreadRealtimeItemAddedNotification


class RealtimeTranscriptUpdatedEvent(CodexBaseModel):
    """Realtime transcript updated event."""

    event_type: Literal["thread/realtime/transcriptUpdated"] = "thread/realtime/transcriptUpdated"
    data: ThreadRealtimeTranscriptUpdatedNotification


class RealtimeOutputAudioDeltaEvent(CodexBaseModel):
    """Realtime output audio delta event."""

    event_type: Literal["thread/realtime/outputAudio/delta"] = "thread/realtime/outputAudio/delta"
    data: ThreadRealtimeOutputAudioDeltaNotification


class RealtimeErrorEvent(CodexBaseModel):
    """Realtime error event."""

    event_type: Literal["thread/realtime/error"] = "thread/realtime/error"
    data: ThreadRealtimeErrorNotification


class RealtimeClosedEvent(CodexBaseModel):
    """Realtime session closed event."""

    event_type: Literal["thread/realtime/closed"] = "thread/realtime/closed"
    data: ThreadRealtimeClosedNotification


# ============================================================================
# Terminal control events
# ============================================================================


class CommandExecOutputDeltaEvent(CodexBaseModel):
    """Command exec output delta event (streaming stdout/stderr)."""

    event_type: Literal["command/exec/outputDelta"] = "command/exec/outputDelta"
    data: CommandExecOutputDeltaNotification


# ============================================================================
# Fuzzy file search events (EXPERIMENTAL)
# ============================================================================


class FuzzyFileSearchSessionUpdatedEvent(CodexBaseModel):
    """Fuzzy file search session updated with results."""

    event_type: Literal["fuzzyFileSearch/sessionUpdated"] = "fuzzyFileSearch/sessionUpdated"
    data: FuzzyFileSearchSessionUpdatedNotification


class FuzzyFileSearchSessionCompletedEvent(CodexBaseModel):
    """Fuzzy file search session completed."""

    event_type: Literal["fuzzyFileSearch/sessionCompleted"] = "fuzzyFileSearch/sessionCompleted"
    data: FuzzyFileSearchSessionCompletedNotification


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
# Item delta events - Agent messages
# ============================================================================


class AgentMessageDeltaEvent(CodexBaseModel):
    """Agent message delta event (streaming text)."""

    event_type: Literal["item/agentMessage/delta"] = "item/agentMessage/delta"
    data: AgentMessageDeltaNotification


# ============================================================================
# Item delta events - Plan
# ============================================================================


class PlanDeltaEvent(CodexBaseModel):
    """Plan delta event (streaming plan text)."""

    event_type: Literal["item/plan/delta"] = "item/plan/delta"
    data: PlanDeltaNotification


# ============================================================================
# Item delta events - Reasoning
# ============================================================================


class ReasoningSummaryTextDeltaEvent(CodexBaseModel):
    """Reasoning summary text delta event."""

    event_type: Literal["item/reasoning/summaryTextDelta"] = "item/reasoning/summaryTextDelta"
    data: ReasoningSummaryTextDeltaNotification


class ReasoningSummaryPartAddedEvent(CodexBaseModel):
    """Reasoning summary part added event."""

    event_type: Literal["item/reasoning/summaryPartAdded"] = "item/reasoning/summaryPartAdded"
    data: ReasoningSummaryPartAddedNotification


class ReasoningTextDeltaEvent(CodexBaseModel):
    """Reasoning text delta event."""

    event_type: Literal["item/reasoning/textDelta"] = "item/reasoning/textDelta"
    data: ReasoningTextDeltaNotification


# ============================================================================
# Item delta events - Command execution
# ============================================================================


class CommandExecutionOutputDeltaEvent(CodexBaseModel):
    """Command execution output delta event."""

    event_type: Literal["item/commandExecution/outputDelta"] = "item/commandExecution/outputDelta"
    data: CommandExecutionOutputDeltaNotification


class CommandExecutionTerminalInteractionEvent(CodexBaseModel):
    """Command execution terminal interaction event."""

    event_type: Literal["item/commandExecution/terminalInteraction"] = (
        "item/commandExecution/terminalInteraction"
    )
    data: TerminalInteractionNotification


# ============================================================================
# Item delta events - File changes
# ============================================================================


class FileChangeOutputDeltaEvent(CodexBaseModel):
    """File change output delta event."""

    event_type: Literal["item/fileChange/outputDelta"] = "item/fileChange/outputDelta"
    data: FileChangeOutputDeltaNotification


# ============================================================================
# Item delta events - MCP tool calls
# ============================================================================


class McpToolCallProgressEvent(CodexBaseModel):
    """MCP tool call progress event."""

    event_type: Literal["item/mcpToolCall/progress"] = "item/mcpToolCall/progress"
    data: McpToolCallProgressNotification


# ============================================================================
# MCP OAuth events
# ============================================================================


class McpServerStartupStatusUpdatedEvent(CodexBaseModel):
    """MCP server startup status updated event."""

    event_type: Literal["mcpServer/startupStatus/updated"] = "mcpServer/startupStatus/updated"
    data: McpServerStatusUpdatedNotification


class McpServerOAuthLoginCompletedEvent(CodexBaseModel):
    """MCP server OAuth login completed event."""

    event_type: Literal["mcpServer/oauthLogin/completed"] = "mcpServer/oauthLogin/completed"
    data: McpServerOauthLoginCompletedNotification


# ============================================================================
# Account/Auth events
# ============================================================================


class AccountUpdatedEvent(CodexBaseModel):
    """Account updated event."""

    event_type: Literal["account/updated"] = "account/updated"
    data: AccountUpdatedNotification


# ============================================================================
# Discriminated union of all event types
# ============================================================================


CodexEvent = Annotated[
    # Error events
    ErrorEvent
    # Thread lifecycle
    | ThreadStartedEvent
    | ThreadStatusChangedEvent
    | ThreadArchivedEvent
    | ThreadUnarchivedEvent
    | ThreadNameUpdatedEvent
    | ThreadTokenUsageUpdatedEvent
    | ThreadCompactedEvent
    # Turn lifecycle
    | TurnStartedEvent
    | TurnCompletedEvent
    | TurnErrorEvent
    | TurnDiffUpdatedEvent
    | TurnPlanUpdatedEvent
    # Hook events
    | HookStartedEvent
    | HookCompletedEvent
    # Realtime voice events (EXPERIMENTAL)
    | RealtimeStartedEvent
    | RealtimeItemAddedEvent
    | RealtimeTranscriptUpdatedEvent
    | RealtimeOutputAudioDeltaEvent
    | RealtimeErrorEvent
    | RealtimeClosedEvent
    # Terminal control events
    | CommandExecOutputDeltaEvent
    # Fuzzy file search events (EXPERIMENTAL)
    | FuzzyFileSearchSessionUpdatedEvent
    | FuzzyFileSearchSessionCompletedEvent
    # Item lifecycle
    | ItemStartedEvent
    | ItemCompletedEvent
    | RawResponseItemCompletedEvent
    # Item deltas - agent messages
    | AgentMessageDeltaEvent
    # Item deltas - plan
    | PlanDeltaEvent
    # Item deltas - reasoning
    | ReasoningSummaryTextDeltaEvent
    | ReasoningSummaryPartAddedEvent
    | ReasoningTextDeltaEvent
    # Item deltas - command execution
    | CommandExecutionOutputDeltaEvent
    | CommandExecutionTerminalInteractionEvent
    # Item deltas - file changes
    | FileChangeOutputDeltaEvent
    # Item deltas - MCP tool calls
    | McpToolCallProgressEvent
    # MCP server status
    | McpServerStartupStatusUpdatedEvent
    # MCP OAuth
    | McpServerOAuthLoginCompletedEvent
    # Account/Auth events
    | AccountUpdatedEvent
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
    AgentMessageDeltaEvent
    | PlanDeltaEvent
    | ReasoningTextDeltaEvent
    | ReasoningSummaryTextDeltaEvent
    | CommandExecutionOutputDeltaEvent
    | FileChangeOutputDeltaEvent
)
