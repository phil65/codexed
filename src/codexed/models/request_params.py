from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Annotated, Any, Literal, Required, Self, TypedDict

from pydantic import Discriminator, TypeAdapter

from codexed.models.base import CodexBaseModel
from codexed.models.codex_types import (
    ApprovalDecision,
    ApprovalPolicy,
    ApprovalsReviewer,
    CollaborationMode,
    DynamicToolSpec,
    MergeStrategy,
    Personality,
    ReasoningEffort,
    ReasoningSummary,
    ReviewDelivery,
    SandboxMode,
    ServiceTier,
    ThreadSortKey,
    ThreadSourceKind,
)
from codexed.models.command_action import CommandAction
from codexed.models.misc import (
    ConfigEdit,
    ExecPolicyAmendment,
    ExternalAgentConfigMigrationItem,
    NetworkApprovalContext,
    NetworkPolicyAmendment,
    ToolRequestUserInputQuestion,
)
from codexed.models.response_item import ResponseItem
from codexed.models.user_input import UserInput
from codexed.models.v2_protocol import ClientInfo, CommandExecTerminalSize


if TYPE_CHECKING:
    from mcp.types import ElicitRequestFormParams, ElicitRequestURLParams


LoginType = Literal["apiKey", "chatgpt", "chatgptAuthTokens"]


class InitializeParams(CodexBaseModel):
    """Parameters for initialize request."""

    client_info: ClientInfo

    @classmethod
    def create(cls, name: str, version: str) -> Self:
        return cls(client_info=ClientInfo(name=name, version=version))


class ThreadStartParams(CodexBaseModel):
    """Parameters for thread/start request."""

    cwd: str | None = None
    model: str | None = None
    model_provider: str | None = None
    base_instructions: str | None = None
    developer_instructions: str | None = None
    approval_policy: ApprovalPolicy | None = None
    approvals_reviewer: ApprovalsReviewer | None = None
    sandbox: SandboxMode | None = None
    config: dict[str, Any] | None = None
    service_name: str | None = None
    service_tier: ServiceTier | None = None
    personality: Personality | None = None
    ephemeral: bool | None = None
    dynamic_tools: list[DynamicToolSpec] | None = None
    experimental_raw_events: bool = False
    persist_extended_history: bool = False


class ThreadResumeParams(CodexBaseModel):
    """Parameters for thread/resume request."""

    thread_id: str
    history: list[ResponseItem] | None = None
    path: str | None = None
    cwd: str | None = None
    model: str | None = None
    model_provider: str | None = None
    base_instructions: str | None = None
    developer_instructions: str | None = None
    approval_policy: ApprovalPolicy | None = None
    approvals_reviewer: ApprovalsReviewer | None = None
    sandbox: SandboxMode | None = None
    config: dict[str, Any] | None = None
    service_tier: ServiceTier | None = None
    personality: Personality | None = None
    persist_extended_history: bool = False


class ThreadForkParams(CodexBaseModel):
    """Parameters for thread/fork request."""

    thread_id: str
    path: str | None = None
    cwd: str | None = None
    model: str | None = None
    model_provider: str | None = None
    base_instructions: str | None = None
    developer_instructions: str | None = None
    approval_policy: ApprovalPolicy | None = None
    approvals_reviewer: ApprovalsReviewer | None = None
    sandbox: SandboxMode | None = None
    config: dict[str, Any] | None = None
    service_tier: ServiceTier | None = None
    personality: Personality | None = None
    ephemeral: bool | None = None
    persist_extended_history: bool = False


class ThreadListParams(CodexBaseModel):
    """Parameters for thread/list request."""

    cursor: str | None = None
    limit: int | None = None
    sort_key: ThreadSortKey | None = None
    model_providers: list[str] | None = None
    source_kinds: list[ThreadSourceKind] | None = None
    archived: bool | None = None
    cwd: str | None = None
    search_term: str | None = None


class ThreadReadParams(CodexBaseModel):
    """Parameters for thread/read request."""

    thread_id: str
    include_turns: bool = False


class ThreadArchiveParams(CodexBaseModel):
    """Parameters for thread/archive request."""

    thread_id: str


class ThreadUnarchiveParams(CodexBaseModel):
    """Parameters for thread/unarchive request."""

    thread_id: str


class ThreadSetNameParams(CodexBaseModel):
    """Parameters for thread/name/set request."""

    thread_id: str
    name: str


class ThreadCompactStartParams(CodexBaseModel):
    """Parameters for thread/compact/start request."""

    thread_id: str


class ThreadRollbackParams(CodexBaseModel):
    """Parameters for thread/rollback request."""

    thread_id: str
    turns: int


class ThreadUnsubscribeParams(CodexBaseModel):
    """Parameters for thread/unsubscribe request."""

    thread_id: str


class ThreadLoadedListParams(CodexBaseModel):
    """Parameters for thread/loaded/list request."""


class TurnStartParams(CodexBaseModel):
    """Parameters for turn/start request."""

    thread_id: str
    input: Sequence[UserInput]
    model: str | None = None
    effort: ReasoningEffort | None = None
    approval_policy: ApprovalPolicy | None = None
    approvals_reviewer: ApprovalsReviewer | None = None
    cwd: str | None = None
    sandbox_policy: dict[str, Any] | None = None  # Sandbox config - flexible structure
    service_tier: ServiceTier | None = None
    summary: ReasoningSummary | None = None
    output_schema: dict[str, Any] | None = None  # JSON Schema - arbitrary structure
    personality: Personality | None = None
    collaboration_mode: CollaborationMode | None = None


class TurnSteerParams(CodexBaseModel):
    """Parameters for turn/steer request."""

    thread_id: str
    input: Sequence[UserInput]
    expected_turn_id: str


class TurnInterruptParams(CodexBaseModel):
    """Parameters for turn/interrupt request."""

    thread_id: str
    turn_id: str


class UncommittedChangesTarget(CodexBaseModel):
    """Review the working tree: staged, unstaged, and untracked files."""

    type: Literal["uncommittedChanges"] = "uncommittedChanges"


class BaseBranchTarget(CodexBaseModel):
    """Review changes between the current branch and a base branch."""

    type: Literal["baseBranch"] = "baseBranch"
    branch: str


class CommitTarget(CodexBaseModel):
    """Review the changes introduced by a specific commit."""

    type: Literal["commit"] = "commit"
    sha: str
    title: str | None = None


class CustomTarget(CodexBaseModel):
    """Arbitrary instructions provided by the user."""

    type: Literal["custom"] = "custom"
    instructions: str


ReviewTarget = UncommittedChangesTarget | BaseBranchTarget | CommitTarget | CustomTarget


class ReviewStartParams(CodexBaseModel):
    """Parameters for review/start request."""

    thread_id: str
    target: ReviewTarget
    delivery: ReviewDelivery | None = None


class SkillsListExtraRootsForCwd(CodexBaseModel):
    """Extra user roots to scan for a specific cwd."""

    cwd: str
    extra_user_roots: list[str]


class SkillsListParams(CodexBaseModel):
    """Parameters for skills/list request."""

    cwds: list[str] | None = None
    force_reload: bool | None = None
    per_cwd_extra_user_roots: list[SkillsListExtraRootsForCwd] | None = None


class SkillsConfigWriteParams(CodexBaseModel):
    """Parameters for skills/config/write request."""

    path: str
    enabled: bool


HazelnutScope = Literal["example", "workspace-shared", "all-shared", "personal"]
ProductSurface = Literal["chatgpt", "codex", "api", "atlas"]


class SkillsRemoteListParams(CodexBaseModel):
    """Parameters for skills/remote/list request."""

    hazelnut_scope: HazelnutScope = "example"
    product_surface: ProductSurface = "codex"
    enabled: bool = False


class SkillsRemoteExportParams(CodexBaseModel):
    """Parameters for skills/remote/export request."""

    hazelnut_id: str


class CollaborationModeListParams(CodexBaseModel):
    """Parameters for collaborationMode/list request."""


class CommandExecParams(CodexBaseModel):
    """Parameters for command/exec request."""

    command: list[str]
    process_id: str | None = None
    tty: bool = False
    stream_stdin: bool = False
    stream_stdout_stderr: bool = False
    output_bytes_cap: int | None = None
    disable_output_cap: bool = False
    disable_timeout: bool = False
    timeout_ms: int | None = None
    cwd: str | None = None
    env: dict[str, str | None] | None = None
    size: CommandExecTerminalSize | None = None
    sandbox_policy: dict[str, Any] | None = None


class ModelListParams(CodexBaseModel):
    """Parameters for model/list request."""

    cursor: str | None = None
    limit: int | None = None
    include_hidden: bool | None = None


class McpServerOauthLoginParams(CodexBaseModel):
    """Parameters for mcpServer/oauth/login request."""

    name: str
    scopes: list[str] | None = None
    timeout_secs: int | None = None


class ListMcpServerStatusParams(CodexBaseModel):
    """Parameters for mcpServerStatus/list request."""

    cursor: str | None = None
    limit: int | None = None


class AppsListParams(CodexBaseModel):
    """Parameters for app/list request."""

    cursor: str | None = None
    limit: int | None = None
    thread_id: str | None = None
    force_refetch: bool | None = None


class ExperimentalFeatureListParams(CodexBaseModel):
    """Parameters for experimentalFeature/list request."""

    cursor: str | None = None
    limit: int | None = None


class FeedbackUploadParams(CodexBaseModel):
    """Parameters for feedback/upload request."""

    classification: str
    reason: str | None = None
    thread_id: str | None = None
    include_logs: bool = False
    extra_log_files: list[str] | None = None


class ConfigReadParams(CodexBaseModel):
    """Parameters for config/read request."""

    include_layers: bool
    cwd: str | None = None


class ConfigValueWriteParams(CodexBaseModel):
    """Parameters for config/value/write request."""

    key_path: str
    value: Any
    merge_strategy: MergeStrategy
    file_path: str | None = None
    expected_version: str | None = None


class ConfigBatchWriteParams(CodexBaseModel):
    """Parameters for config/batchWrite request."""

    edits: list[ConfigEdit]
    file_path: str | None = None
    expected_version: str | None = None


class GetAccountParams(CodexBaseModel):
    """Parameters for account/read request."""

    refresh_token: bool


class LoginAccountParams(CodexBaseModel):
    """Parameters for account/login/start request.

    This is a discriminated union - use type field.
    """

    type: LoginType
    api_key: str | None = None
    access_token: str | None = None
    chatgpt_account_id: str | None = None
    chatgpt_plan_type: str | None = None


class CancelLoginAccountParams(CodexBaseModel):
    """Parameters for account/login/cancel request."""

    login_id: str


class ExternalAgentConfigDetectParams(CodexBaseModel):
    """Parameters for externalAgentConfig/detect request."""

    include_home: bool | None = None
    cwds: list[str] | None = None


class ExternalAgentConfigImportParams(CodexBaseModel):
    """Parameters for externalAgentConfig/import request."""

    migration_items: list[ExternalAgentConfigMigrationItem]


# ============================================================================
# Filesystem params
# ============================================================================


class FsReadFileParams(CodexBaseModel):
    """Parameters for fs/readFile request."""

    path: str


class FsWriteFileParams(CodexBaseModel):
    """Parameters for fs/writeFile request."""

    path: str
    data_base64: str


class FsCreateDirectoryParams(CodexBaseModel):
    """Parameters for fs/createDirectory request."""

    path: str
    recursive: bool | None = None


class FsGetMetadataParams(CodexBaseModel):
    """Parameters for fs/getMetadata request."""

    path: str


class FsReadDirectoryParams(CodexBaseModel):
    """Parameters for fs/readDirectory request."""

    path: str


class FsRemoveParams(CodexBaseModel):
    """Parameters for fs/remove request."""

    path: str
    recursive: bool | None = None
    force: bool | None = None


class FsCopyParams(CodexBaseModel):
    """Parameters for fs/copy request."""

    source_path: str
    destination_path: str
    recursive: bool = False


class ThreadShellCommandParams(CodexBaseModel):
    """Parameters for thread/shellCommand request."""

    thread_id: str
    command: str


class FsWatchParams(CodexBaseModel):
    """Parameters for fs/watch request."""

    path: str


class FsUnwatchParams(CodexBaseModel):
    """Parameters for fs/unwatch request."""

    watch_id: str


class CommandExecutionRequestApprovalParams(CodexBaseModel):
    """Parameters for item/commandExecution/requestApproval server request."""

    thread_id: str
    turn_id: str
    item_id: str
    approval_id: str | None = None
    reason: str | None = None
    network_approval_context: NetworkApprovalContext | None = None
    command: str | None = None
    cwd: str | None = None
    command_actions: list[CommandAction] | None = None
    additional_permissions: dict[str, Any] | None = None
    proposed_execpolicy_amendment: ExecPolicyAmendment | None = None
    proposed_network_policy_amendments: list[NetworkPolicyAmendment] | None = None
    available_decisions: list[ApprovalDecision] | None = None


class FileChangeRequestApprovalParams(CodexBaseModel):
    """Parameters for item/fileChange/requestApproval server request."""

    thread_id: str
    turn_id: str
    item_id: str
    reason: str | None = None
    grant_root: str | None = None


class ToolRequestUserInputParams(CodexBaseModel):
    """Parameters for item/tool/requestUserInput server request."""

    thread_id: str
    turn_id: str
    item_id: str
    questions: list[ToolRequestUserInputQuestion]


class SkillRequestApprovalParams(CodexBaseModel):
    """Parameters for skill/requestApproval server request."""

    item_id: str
    skill_name: str


class DynamicToolCallParams(CodexBaseModel):
    """Parameters for item/tool/call server request."""

    thread_id: str
    turn_id: str
    call_id: str
    tool: str
    arguments: Any


PersistOption = Literal["session", "always"]


class ToolApprovalParamDisplay(TypedDict):
    """A rendered tool parameter for display."""

    name: str
    value: Any
    display_name: str


class ToolApprovalMeta(TypedDict, total=False):
    """Metadata for MCP tool approval requests."""

    codex_approval_kind: Required[Literal["mcp_tool_call"]]
    persist: PersistOption | list[PersistOption]
    tool_title: str
    tool_description: str
    tool_params: dict[str, Any]
    tool_params_display: list[ToolApprovalParamDisplay]
    source: Literal["connector"]
    connector_id: str
    connector_name: str
    connector_description: str


class _McpElicitationBase(CodexBaseModel):
    """Common fields for MCP elicitation requests."""

    thread_id: str
    turn_id: str | None = None
    server_name: str
    meta: ToolApprovalMeta | Any | None = None
    """Approval metadata when ``tool_call_mcp_elicitation`` is enabled; otherwise server-defined."""
    message: str


class McpElicitationFormParams(_McpElicitationBase):
    """Form-mode MCP elicitation request."""

    mode: Literal["form"] = "form"
    requested_schema: dict[str, Any]

    def to_mcp(self) -> ElicitRequestFormParams:
        from mcp.types import ElicitRequestFormParams, RequestParams

        params = ElicitRequestFormParams(
            message=self.message,
            requestedSchema=self.requested_schema,
        )
        if self.meta is not None:
            params.meta = RequestParams.Meta(**self.meta)
        return params

    @classmethod
    def from_mcp(
        cls,
        params: ElicitRequestFormParams,
        thread_id: str,
        server_name: str,
        turn_id: str | None = None,
    ) -> McpElicitationFormParams:
        """Create from MCP ElicitRequestFormParams."""
        meta = params.meta.model_dump(exclude={"progressToken"}) if params.meta else None
        return cls(
            message=params.message,
            requested_schema=dict(params.requestedSchema),
            meta=meta,
            thread_id=thread_id,
            server_name=server_name,
            turn_id=turn_id,
        )


class McpElicitationUrlParams(_McpElicitationBase):
    """URL-mode MCP elicitation request (browser-based auth)."""

    mode: Literal["url"] = "url"
    url: str
    elicitation_id: str

    def to_mcp(self) -> ElicitRequestURLParams:
        from mcp.types import ElicitRequestURLParams, RequestParams

        params = ElicitRequestURLParams(
            message=self.message,
            url=self.url,
            elicitationId=self.elicitation_id,
        )
        if self.meta is not None:
            params.meta = RequestParams.Meta(**self.meta)
        return params

    @classmethod
    def from_mcp(
        cls,
        params: ElicitRequestURLParams,
        thread_id: str,
        server_name: str,
        turn_id: str | None = None,
    ) -> McpElicitationUrlParams:
        """Create from MCP ElicitRequestURLParams."""
        meta = params.meta.model_dump(exclude={"progressToken"}) if params.meta else None
        return cls(
            message=params.message,
            url=params.url,
            elicitation_id=params.elicitationId,
            meta=meta,
            thread_id=thread_id,
            server_name=server_name,
            turn_id=turn_id,
        )


McpServerElicitationRequestParams = Annotated[
    McpElicitationFormParams | McpElicitationUrlParams,
    Discriminator("mode"),
]
"""Parameters for mcpServer/elicitation/request, discriminated by mode."""

mcp_elicitation_adapter: TypeAdapter[McpServerElicitationRequestParams] = TypeAdapter(
    McpServerElicitationRequestParams
)
