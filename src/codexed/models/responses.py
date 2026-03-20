from __future__ import annotations

from typing import Any, Literal

import mcp.types

from codexed.models.base import CodexBaseModel
from codexed.models.codex_types import (  # noqa: TC001
    ApprovalDecision,
    AskForApproval,
    ModeKind,
    ReasoningEffort,
    SandboxPolicy,
    WriteStatus,
)
from codexed.models.misc import (  # noqa: TC001
    AppInfo,
    ConfigLayer,
    ConfigLayerMetadata,
    ConfigRequirements,
    ExperimentalFeature,
    ExternalAgentConfigMigrationItem,
    McpServerStatusEntry,
    ModelData,
    SkillsContainer,
    ThreadData,
    ToolRequestUserInputAnswer,
    Turn,
    TurnData,
)
from codexed.models.thread_item import DynamicToolCallOutputContentItem  # noqa: TC001


class CommandExecutionRequestApprovalResponse(CodexBaseModel):
    """Response for item/commandExecution/requestApproval server request."""

    decision: ApprovalDecision


class FileChangeRequestApprovalResponse(CodexBaseModel):
    """Response for item/fileChange/requestApproval server request."""

    decision: ApprovalDecision


class ToolRequestUserInputResponse(CodexBaseModel):
    """Response for item/tool/requestUserInput server request."""

    answers: dict[str, ToolRequestUserInputAnswer]


class DynamicToolCallResponse(CodexBaseModel):
    """Response for item/tool/call server request."""

    content_items: list[DynamicToolCallOutputContentItem]
    success: bool


class McpServerElicitationResponse(CodexBaseModel):
    """Response for mcpServer/elicitation/request server request."""

    action: Literal["accept", "decline", "cancel"]
    content: Any | None = None
    meta: Any | None = None

    def to_mcp(self) -> mcp.types.ElicitResult:
        return mcp.types.ElicitResult(action=self.action, content=self.content)

    @classmethod
    def from_mcp(cls, result: mcp.types.ElicitResult) -> McpServerElicitationResponse:
        """Create from MCP ElicitResult."""
        return cls(action=result.action, content=result.content)


class ThreadReadResponse(CodexBaseModel):
    """Response for thread/read request."""

    thread: ThreadData


class ThreadResponse(CodexBaseModel):
    """Response for thread/start, thread/resume, and thread/fork."""

    thread: ThreadData
    model: str
    model_provider: str
    cwd: str
    approval_policy: AskForApproval
    sandbox: SandboxPolicy
    reasoning_effort: ReasoningEffort | None = None
    service_tier: Literal["flex", "fast"] | None = None


class TurnStartResponse(CodexBaseModel):
    """Response for turn/start request."""

    turn: TurnData


class TurnSteerResponse(CodexBaseModel):
    """Response for turn/steer request."""

    turn_id: str


class ReviewStartResponse(CodexBaseModel):
    """Response for review/start request."""

    turn: TurnData
    review_thread_id: str


class ThreadListResponse(CodexBaseModel):
    """Response for thread/list request."""

    data: list[ThreadData]
    next_cursor: str | None = None


class ThreadLoadedListResponse(CodexBaseModel):
    """Response for thread/loaded/list request."""

    data: list[str]


class ThreadRollbackResponse(CodexBaseModel):
    """Response for thread/rollback request."""

    thread: ThreadData
    turns: list[Turn]


class ThreadUnarchiveResponse(CodexBaseModel):
    """Response for thread/unarchive request."""

    thread: ThreadData


class SkillsListResponse(CodexBaseModel):
    """Response for skills/list request."""

    data: list[SkillsContainer]


class SkillsConfigWriteResponse(CodexBaseModel):
    """Response for skills/config/write request."""


class RemoteSkillSummary(CodexBaseModel):
    """Summary of a remote skill."""

    id: str
    name: str
    description: str


class SkillsRemoteListResponse(CodexBaseModel):
    """Response for skills/remote/list request."""

    data: list[RemoteSkillSummary]


class SkillsRemoteExportResponse(CodexBaseModel):
    """Response for skills/remote/export request."""

    id: str
    path: str


class ModelListResponse(CodexBaseModel):
    """Response for model/list request."""

    data: list[ModelData]
    next_cursor: str | None = None


class CommandExecResponse(CodexBaseModel):
    """Response for command/exec request."""

    exit_code: int
    stdout: str = ""
    stderr: str = ""


class ListMcpServerStatusResponse(CodexBaseModel):
    """Response for mcpServerStatus/list request."""

    data: list[McpServerStatusEntry]
    next_cursor: str | None = None


class McpServerOauthLoginResponse(CodexBaseModel):
    """Response for mcpServer/oauth/login request."""

    authorization_url: str


class McpServerRefreshResponse(CodexBaseModel):
    """Response for config/mcpServer/reload request."""


# ============================================================================
# Account models
# ============================================================================


class GetAccountResponse(CodexBaseModel):
    """Response for account/read request."""

    account: dict[str, Any] | None = None  # Account enum - flexible
    requires_openai_auth: bool = False


class LoginAccountResponse(CodexBaseModel):
    """Response for account/login/start request."""

    type: Literal["apiKey", "chatgpt", "chatgptAuthTokens"]
    login_id: str | None = None
    auth_url: str | None = None


CancelLoginAccountStatus = Literal["canceled", "notFound"]


class CancelLoginAccountResponse(CodexBaseModel):
    """Response for account/login/cancel request."""

    status: CancelLoginAccountStatus


class GetAccountRateLimitsResponse(CodexBaseModel):
    """Response for account/rateLimits/read request."""

    rate_limits: dict[str, Any]  # RateLimitSnapshot - flexible
    rate_limits_by_limit_id: dict[str, Any] | None = None


class ConfigReadResponse(CodexBaseModel):
    """Response for config/read request."""

    config: dict[str, Any]
    origins: dict[str, ConfigLayerMetadata] | None = None
    layers: list[ConfigLayer] | None = None


class ConfigWriteResponse(CodexBaseModel):
    """Response for config/value/write and config/batchWrite requests."""

    status: WriteStatus
    version: str
    file_path: str
    overridden_metadata: dict[str, Any] | None = None


class ConfigRequirementsReadResponse(CodexBaseModel):
    """Response for configRequirements/read request."""

    requirements: ConfigRequirements | None = None


class AppsListResponse(CodexBaseModel):
    """Response for app/list request."""

    data: list[AppInfo]
    next_cursor: str | None = None


class ExperimentalFeatureListResponse(CodexBaseModel):
    """Response for experimentalFeature/list request."""

    data: list[ExperimentalFeature]
    next_cursor: str | None = None


class FeedbackUploadResponse(CodexBaseModel):
    """Response for feedback/upload request."""

    thread_id: str


ThreadUnsubscribeStatus = Literal["notLoaded", "notSubscribed", "unsubscribed"]


class ThreadUnsubscribeResponse(CodexBaseModel):
    """Response for thread/unsubscribe request."""

    status: ThreadUnsubscribeStatus


class CollaborationModeMask(CodexBaseModel):
    """Collaboration mode preset metadata."""

    name: str
    mode: ModeKind | None = None
    model: str | None = None
    reasoning_effort: ReasoningEffort | None = None


class CollaborationModeListResponse(CodexBaseModel):
    """Response for collaborationMode/list request."""

    data: list[CollaborationModeMask]


class ExternalAgentConfigDetectResponse(CodexBaseModel):
    """Response for externalAgentConfig/detect request."""

    items: list[ExternalAgentConfigMigrationItem]


# ============================================================================
# Filesystem responses
# ============================================================================


class FsReadFileResponse(CodexBaseModel):
    """Response for fs/readFile request."""

    data_base64: str


class FsWriteFileResponse(CodexBaseModel):
    """Response for fs/writeFile request."""


class FsCreateDirectoryResponse(CodexBaseModel):
    """Response for fs/createDirectory request."""


class FsGetMetadataResponse(CodexBaseModel):
    """Response for fs/getMetadata request."""

    is_directory: bool
    is_file: bool
    created_at_ms: int
    modified_at_ms: int


class FsReadDirectoryEntry(CodexBaseModel):
    """A directory entry returned by fs/readDirectory."""

    file_name: str
    is_directory: bool
    is_file: bool


class FsReadDirectoryResponse(CodexBaseModel):
    """Response for fs/readDirectory request."""

    entries: list[FsReadDirectoryEntry]


class FsRemoveResponse(CodexBaseModel):
    """Response for fs/remove request."""


class FsCopyResponse(CodexBaseModel):
    """Response for fs/copy request."""
