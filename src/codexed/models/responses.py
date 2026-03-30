from __future__ import annotations

from typing import Any, Literal

import mcp.types

from codexed.models.base import CodexBaseModel
from codexed.models.codex_types import ApprovalDecision, AskForApproval, SandboxPolicy
from codexed.models.misc import (
    McpServerStatusEntry,
    Thread,
    ToolRequestUserInputAnswer,
    Turn,
    TurnData,
)
from codexed.models.v2_protocol import (
    AuthMode,
    DynamicToolCallOutputContentItem,
    ExternalAgentConfigMigrationItem,
    ReasoningEffort,
)


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
    """Optional metadata to include in the response.

    For MCP tool approval responses, this can contain:

    - ``persist`` (str): ``"session"`` to remember the approval for
      the current session, or ``"always"`` to remember permanently.
      Must be one of the options listed in the request's ``meta.persist``.
    """

    def to_mcp(self) -> mcp.types.ElicitResult:
        return mcp.types.ElicitResult(action=self.action, content=self.content)

    @classmethod
    def from_mcp(cls, result: mcp.types.ElicitResult) -> McpServerElicitationResponse:
        """Create from MCP ElicitResult."""
        return cls(action=result.action, content=result.content)


class ThreadReadResponse(CodexBaseModel):
    """Response for thread/read request."""

    thread: Thread


class ThreadResponse(CodexBaseModel):
    """Response for thread/start, thread/resume, and thread/fork."""

    thread: Thread
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


class ReviewStartResponse(CodexBaseModel):
    """Response for review/start request."""

    turn: TurnData
    review_thread_id: str


class ThreadListResponse(CodexBaseModel):
    """Response for thread/list request."""

    data: list[Thread]
    next_cursor: str | None = None


class ThreadRollbackResponse(CodexBaseModel):
    """Response for thread/rollback request."""

    thread: Thread
    turns: list[Turn]


class ThreadUnarchiveResponse(CodexBaseModel):
    """Response for thread/unarchive request."""

    thread: Thread


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


class ListMcpServerStatusResponse(CodexBaseModel):
    """Response for mcpServerStatus/list request."""

    data: list[McpServerStatusEntry]
    next_cursor: str | None = None


# ============================================================================
# Account models
# ============================================================================


class LoginAccountResponse(CodexBaseModel):
    """Response for account/login/start request."""

    type: AuthMode
    login_id: str | None = None
    auth_url: str | None = None


class FeedbackUploadResponse(CodexBaseModel):
    """Response for feedback/upload request."""

    thread_id: str


class ExternalAgentConfigDetectResponse(CodexBaseModel):
    """Response for externalAgentConfig/detect request."""

    items: list[ExternalAgentConfigMigrationItem]
