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
    AccountGatewayOAuthChangedNotification,
    AccountLoginCompletedMessage,
    AccountRateLimitsUpdatedMessage,
    AccountUpdatedMessage,
    AppListUpdatedMessage,
    AutoApprovalReviewStrictReviewRequiredNotification,
    CommandExecOutputDeltaMessage,
    ConfigWarningMessage,
    DeprecationNoticeMessage,
    ErrorMessage,
    ExternalAgentConfigImportCompletedMessage,
    ExternalAgentConfigImportProgressMessage,
    FsChangedMessage,
    FuzzyFileSearchSessionCompletedMessage,
    FuzzyFileSearchSessionUpdatedMessage,
    GuardianWarningMessage,
    HookCompletedMessage,
    HookStartedMessage,
    ItemAgentMessageDeltaNotification,
    ItemAutoApprovalReviewCompletedNotification,
    ItemAutoApprovalReviewStartedNotification,
    ItemCommandExecutionOutputDeltaNotification,
    ItemCommandExecutionTerminalInteractionNotification,
    ItemFileChangeOutputDeltaNotification,
    ItemFileChangePatchUpdatedNotification,
    ItemMcpToolCallProgressNotification,
    ItemPlanDeltaNotification,
    ItemReasoningSummaryPartAddedNotification,
    ItemReasoningSummaryTextDeltaNotification,
    ItemReasoningTextDeltaNotification,
    McpServerEventStreamNotificationNotification,
    McpServerOauthLoginCompletedMessage,
    McpServerStartupStatusUpdatedNotification,
    ModelProviderAuthRecoveryCompletedNotification,
    ModelProviderAuthRecoveryStartedNotification,
    ModelReroutedMessage,
    ModelSafetyBufferingUpdatedMessage,
    ModelVerificationMessage,
    ProcessExitedMessage,
    ProcessOutputDeltaMessage,
    ProjectChangedMessage,
    RemoteControlStatusChangedMessage,
    ServerRequestResolvedMessage,
    SkillsChangedMessage,
    ThreadArchivedMessage,
    ThreadAttachmentUpdatedMessage,
    ThreadClosedMessage,
    ThreadCompactedMessage,
    ThreadDeletedMessage,
    ThreadEnvironmentConnectedNotification,
    ThreadEnvironmentDisconnectedNotification,
    ThreadGoalClearedMessage,
    ThreadGoalUpdatedMessage,
    ThreadNameUpdatedMessage,
    ThreadPredictionUpdatedMessage,
    ThreadProjectUpdatedMessage,
    ThreadQueueChangedMessage,
    ThreadReadStateChangedMessage,
    ThreadRealtimeClosedMessage,
    ThreadRealtimeErrorMessage,
    ThreadRealtimeItemAddedMessage,
    ThreadRealtimeItemCompletedMessage,
    ThreadRealtimeItemStartedMessage,
    ThreadRealtimeItemTranscriptDeltaMessage,
    ThreadRealtimeOutputAudioDeltaMessage,
    ThreadRealtimeSdpMessage,
    ThreadRealtimeStartedMessage,
    ThreadRealtimeTranscriptDeltaMessage,
    ThreadRealtimeTranscriptDoneMessage,
    ThreadRevertedMessage,
    ThreadSectionChangedMessage,
    ThreadSettingsUpdatedMessage,
    ThreadStatusChangedMessage,
    ThreadTokenUsageUpdatedNotification,
    ThreadUnarchivedMessage,
    TurnDiffUpdatedMessage,
    TurnModerationMetadataMessage,
    TurnPlanUpdatedMessage,
    WarningMessage,
    WindowsSandboxSetupCompletedMessage,
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


# ============================================================================
# Discriminated union of all event types
# ============================================================================

RealtimeEvent = (
    ThreadRealtimeStartedMessage
    | ThreadRealtimeItemAddedMessage
    | ThreadRealtimeItemStartedMessage
    | ThreadRealtimeItemTranscriptDeltaMessage
    | ThreadRealtimeItemCompletedMessage
    | ThreadRealtimeTranscriptDeltaMessage
    | ThreadRealtimeTranscriptDoneMessage
    | ThreadRealtimeOutputAudioDeltaMessage
    | ThreadRealtimeSdpMessage
    | ThreadRealtimeErrorMessage
    | ThreadRealtimeClosedMessage
)

CodexEvent = Annotated[
    ErrorMessage
    | ThreadStartedEvent
    | ThreadStatusChangedMessage
    | ThreadReadStateChangedMessage
    | ThreadArchivedMessage
    | ThreadDeletedMessage
    | ThreadUnarchivedMessage
    | ThreadClosedMessage
    | ThreadRevertedMessage
    | SkillsChangedMessage
    | ThreadNameUpdatedMessage
    | ThreadSectionChangedMessage
    | ThreadAttachmentUpdatedMessage
    | ThreadGoalUpdatedMessage
    | ThreadPredictionUpdatedMessage
    | ThreadGoalClearedMessage
    | ThreadQueueChangedMessage
    | ProjectChangedMessage
    | ThreadProjectUpdatedMessage
    | ThreadEnvironmentConnectedNotification
    | ThreadEnvironmentDisconnectedNotification
    | ThreadSettingsUpdatedMessage
    | ThreadTokenUsageUpdatedEvent
    | TurnStartedEvent
    | HookStartedMessage
    | TurnCompletedEvent
    | HookCompletedMessage
    | TurnDiffUpdatedMessage
    | TurnPlanUpdatedMessage
    | ItemStartedEvent
    | ItemAutoApprovalReviewStartedNotification
    | ItemAutoApprovalReviewCompletedNotification
    | AutoApprovalReviewStrictReviewRequiredNotification
    | ItemCompletedEvent
    | ItemAgentMessageDeltaNotification
    | ItemPlanDeltaNotification
    | CommandExecOutputDeltaMessage
    | ProcessOutputDeltaMessage
    | ProcessExitedMessage
    | ItemCommandExecutionOutputDeltaNotification
    | ItemCommandExecutionTerminalInteractionNotification
    | ItemFileChangeOutputDeltaNotification
    | ItemFileChangePatchUpdatedNotification
    | ServerRequestResolvedMessage
    | ItemMcpToolCallProgressNotification
    | McpServerOauthLoginCompletedMessage
    | McpServerStartupStatusUpdatedNotification
    | McpServerEventStreamNotificationNotification
    | AccountUpdatedMessage
    | AccountGatewayOAuthChangedNotification
    | AccountRateLimitsUpdatedMessage
    | AppListUpdatedMessage
    | RemoteControlStatusChangedMessage
    | ExternalAgentConfigImportProgressMessage
    | ExternalAgentConfigImportCompletedMessage
    | FsChangedMessage
    | ItemReasoningSummaryTextDeltaNotification
    | ItemReasoningSummaryPartAddedNotification
    | ItemReasoningTextDeltaNotification
    | ThreadCompactedMessage
    | ModelReroutedMessage
    | ModelVerificationMessage
    | ModelProviderAuthRecoveryStartedNotification
    | ModelProviderAuthRecoveryCompletedNotification
    | TurnModerationMetadataMessage
    | ModelSafetyBufferingUpdatedMessage
    | WarningMessage
    | GuardianWarningMessage
    | DeprecationNoticeMessage
    | ConfigWarningMessage
    | FuzzyFileSearchSessionUpdatedMessage
    | FuzzyFileSearchSessionCompletedMessage
    | ThreadRealtimeStartedMessage
    | ThreadRealtimeItemAddedMessage
    | ThreadRealtimeItemStartedMessage
    | ThreadRealtimeItemTranscriptDeltaMessage
    | ThreadRealtimeItemCompletedMessage
    | ThreadRealtimeTranscriptDeltaMessage
    | ThreadRealtimeTranscriptDoneMessage
    | ThreadRealtimeOutputAudioDeltaMessage
    | ThreadRealtimeSdpMessage
    | ThreadRealtimeErrorMessage
    | ThreadRealtimeClosedMessage
    | WindowsWorldWritableWarningMessage
    | WindowsSandboxSetupCompletedMessage
    | AccountLoginCompletedMessage,
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
