from __future__ import annotations

from typing import TYPE_CHECKING, Any

from codexed.models.base import CodexBaseModel
from codexed.models.codex_types import ApprovalDecision, ElicitationAction
from codexed.models.misc import (
    McpServerStatusEntry,
    Thread,
    ToolRequestUserInputAnswer,
    TurnData,
    TurnsPage,
)
from codexed.models.v2_protocol import (
    ActivePermissionProfile,
    ApprovalsReviewer,
    AskForApproval,
    CollaborationMode,
    DynamicToolCallOutputContentItem,
    MultiAgentMode,
    ReasoningEffort,
    SandboxPolicy,
    ThreadReadState,
)


if TYPE_CHECKING:
    from mcp.types import ElicitResult


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

    action: ElicitationAction
    content: Any | None = None
    meta: Any | None = None
    """Optional metadata to include in the response.

    For MCP tool approval responses, this can contain:

    - ``persist`` (str): ``"session"`` to remember the approval for
      the current session, or ``"always"`` to remember permanently.
      Must be one of the options listed in the request's ``meta.persist``.
    """

    def to_mcp(self) -> ElicitResult:
        from mcp.types import ElicitResult

        return ElicitResult(action=self.action, content=self.content, meta=self.meta)

    @classmethod
    def from_mcp(cls, result: ElicitResult) -> McpServerElicitationResponse:
        """Create from MCP ElicitResult."""
        return cls(action=result.action, content=result.content, meta=result.meta)


class ThreadReadResponse(CodexBaseModel):
    """Response for thread/read request."""

    thread: Thread
    read_state: ThreadReadState | None = None


class ThreadResponse(CodexBaseModel):
    """Response for thread/start, thread/resume, and thread/fork."""

    thread: Thread
    model: str
    model_provider: str
    cwd: str
    approval_policy: AskForApproval
    sandbox: SandboxPolicy
    reasoning_effort: ReasoningEffort | None = None
    service_tier: str | None = None
    active_permission_profile: ActivePermissionProfile | None = None
    approvals_reviewer: ApprovalsReviewer | None = None
    collaboration_mode: CollaborationMode | None = None
    """Only returned by thread/resume."""
    disabled_plugin_ids: list[str] | None = None
    initial_turns_page: TurnsPage | None = None
    """Only returned by thread/resume."""
    instruction_sources: list[str] | None = None
    items_backwards_cursor: str | None = None
    """Only returned by thread/resume."""
    multi_agent_mode: MultiAgentMode | None = None
    runtime_workspace_roots: list[str] | None = None
    turns_backwards_cursor: str | None = None
    """Only returned by thread/resume."""


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
    backwards_cursor: str | None = None
    read_states: dict[str, ThreadReadState] | None = None
    """Read state per thread ID."""


class ThreadRevertResponse(CodexBaseModel):
    """Response for thread/revert request."""

    thread: Thread
    """Updated thread metadata. `turns` is always empty; use `thread/turns/list`."""
    items_backwards_cursor: str | None = None
    """Cursor for hydrating paginated items backwards via `thread/items/list`."""
    turns_backwards_cursor: str | None = None
    """Cursor for hydrating paginated turns backwards via `thread/turns/list`."""


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
