from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any, Literal, Required, TypedDict

from pydantic import Discriminator, TypeAdapter

from codexed.models.base import CodexBaseModel
from codexed.models.codex_types import ApprovalDecision
from codexed.models.misc import (
    ExecPolicyAmendment,
    NetworkApprovalContext,
    NetworkPolicyAmendment,
    ToolRequestUserInputQuestion,
)
from codexed.models.response_item import ResponseItem
from codexed.models.v2_protocol import (
    ApprovalsReviewer,
    AskForApproval,
    CommandAction,
    Personality,
    SandboxMode,
    ServiceTier,
)


if TYPE_CHECKING:
    from mcp.types import ElicitRequestFormParams, ElicitRequestURLParams


HazelnutScope = Literal["example", "workspace-shared", "all-shared", "personal"]
ProductSurface = Literal["chatgpt", "codex", "api", "atlas"]
PersistOption = Literal["session", "always"]


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
    approval_policy: AskForApproval | None = None
    approvals_reviewer: ApprovalsReviewer | None = None
    sandbox: SandboxMode | None = None
    config: dict[str, Any] | None = None
    service_tier: ServiceTier | None = None
    personality: Personality | None = None
    persist_extended_history: bool = False


class SkillsRemoteListParams(CodexBaseModel):
    """Parameters for skills/remote/list request."""

    hazelnut_scope: HazelnutScope = "example"
    product_surface: ProductSurface = "codex"
    enabled: bool = False


class SkillsRemoteExportParams(CodexBaseModel):
    """Parameters for skills/remote/export request."""

    hazelnut_id: str


# ============================================================================
# Filesystem params
# ============================================================================


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

        return ElicitRequestFormParams(
            message=self.message,
            requestedSchema=self.requested_schema,
            _meta=RequestParams.Meta(**self.meta) if self.meta else None,  # pyright: ignore[reportArgumentType]
        )

    @classmethod
    def from_mcp(
        cls,
        params: ElicitRequestFormParams,
        thread_id: str,
        server_name: str,
        turn_id: str | None = None,
    ) -> McpElicitationFormParams:
        """Create from MCP ElicitRequestFormParams."""
        return cls(
            message=params.message,
            requested_schema=dict(params.requestedSchema),
            meta=params.meta.model_dump(exclude={"progressToken"}) if params.meta else None,
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

        return ElicitRequestURLParams(
            message=self.message,
            url=self.url,
            elicitationId=self.elicitation_id,
            _meta=RequestParams.Meta(**self.meta) if self.meta else None,  # pyright: ignore[reportArgumentType]
        )

    @classmethod
    def from_mcp(
        cls,
        params: ElicitRequestURLParams,
        thread_id: str,
        server_name: str,
        turn_id: str | None = None,
    ) -> McpElicitationUrlParams:
        """Create from MCP ElicitRequestURLParams."""
        return cls(
            message=params.message,
            url=params.url,
            elicitation_id=params.elicitationId,
            meta=params.meta.model_dump(exclude={"progressToken"}) if params.meta else None,
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
