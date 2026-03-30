"""Pydantic models for Codex JSON-RPC API requests and responses."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from mcp.types import Annotations, Icon, ToolAnnotations
from pydantic import AnyUrl, Field

from codexed.models.base import CodexBaseModel
from codexed.models.codex_types import (
    NetworkApprovalProtocol,
    NetworkPolicyRuleAction,
    SkillApprovalDecision,
)
from codexed.models.thread_item import ThreadItem
from codexed.models.thread_status import ThreadStatus
from codexed.models.v2_protocol import GitInfo, McpAuthStatus, SessionSource, TurnError


if TYPE_CHECKING:
    from mcp.types import Resource, ResourceTemplate, Tool


# Strict validation in tests to catch schema changes, lenient in production

TurnStatusValue = Literal["completed", "interrupted", "failed", "inProgress"]
PlanStepStatus = Literal["pending", "inProgress", "completed"]


# ============================================================================
# Server Request models (server -> client callbacks)
# ============================================================================


class NetworkApprovalContext(CodexBaseModel):
    """Network approval context for command approvals."""

    host: str
    protocol: NetworkApprovalProtocol


class NetworkPolicyAmendment(CodexBaseModel):
    """Proposed network policy amendment."""

    host: str
    action: NetworkPolicyRuleAction


class ExecPolicyAmendment(CodexBaseModel):
    """Proposed execpolicy amendment (prefix rule)."""

    command: list[str]


class ToolRequestUserInputOption(CodexBaseModel):
    """A selectable option for a user input question."""

    label: str
    description: str


class ToolRequestUserInputQuestion(CodexBaseModel):
    """A question in a tool request for user input."""

    id: str
    header: str
    question: str
    is_other: bool = False
    is_secret: bool = False
    options: list[ToolRequestUserInputOption] | None = None

    def to_schema_property(self) -> dict[str, Any]:
        """Convert a Codex user input question to a JSON Schema property.

        Maps question options to enum values, and handles secret/free-text questions.

        Args:
            question: Codex question with optional options list

        Returns:
            JSON Schema property definition
        """
        prop: dict[str, Any] = {"title": self.header or self.id}
        if self.question:
            prop["description"] = self.question

        if self.options and not self.is_other:
            # Question with fixed options -> enum
            prop["type"] = "string"
            prop["enum"] = [opt.label for opt in self.options]
        elif self.options and self.is_other:
            # Options with an "other" free-text fallback -> enum + freeform
            prop["type"] = "string"
            prop["enum"] = [opt.label for opt in self.options]
        else:
            # Free-text question
            prop["type"] = "string"

        if self.is_secret:
            prop["writeOnly"] = True

        return prop


class ToolRequestUserInputAnswer(CodexBaseModel):
    """A user's answer to a request_user_input question."""

    answers: list[str]


class SkillRequestApprovalResponse(CodexBaseModel):
    """Response for skill/requestApproval server request."""

    decision: SkillApprovalDecision


class Turn(CodexBaseModel):
    """Turn data structure."""

    id: str
    items: list[ThreadItem] = Field(default_factory=list)
    status: TurnStatusValue = "inProgress"
    error: TurnError | None = None

    @property
    def final_response(self) -> str | None:
        """Extract the final assistant response text from this turn.

        Looks for the last ``ThreadItemAgentMessage`` with ``phase="final_answer"``.
        Falls back to the last agent message with no phase (for models that don't
        emit phase metadata). Returns None if the turn has no agent messages.

        For structured output turns, this returns the raw JSON string.
        """
        from codexed.models.thread_item import ThreadItemAgentMessage

        last_unphased: str | None = None
        for item in reversed(self.items):
            match item:
                case ThreadItemAgentMessage(phase="final_answer", text=text):
                    return text
                case ThreadItemAgentMessage(phase=None, text=text) if last_unphased is None:
                    last_unphased = text
        return last_unphased


class Thread(CodexBaseModel):
    """Thread data structure (matches upstream Codex Thread type)."""

    id: str
    preview: str = ""
    ephemeral: bool = False
    model_provider: str = "openai"
    created_at: int = 0
    updated_at: int = 0
    status: ThreadStatus | None = None
    path: str | None = None
    cwd: str = ""
    cli_version: str = ""
    source: SessionSource = "appServer"
    agent_nickname: str | None = None
    agent_role: str | None = None
    git_info: GitInfo | None = None
    name: str | None = None
    turns: list[Turn] = Field(default_factory=list)


class TurnData(CodexBaseModel):
    """Turn data in responses."""

    id: str
    status: TurnStatusValue  # always provided by the server
    thread_id: str | None = None
    items: list[ThreadItem] = Field(default_factory=list)
    error: str | None = None


class McpTool(CodexBaseModel):
    """Tool exposed by an MCP server. Mirrors `mcp.types.Tool`."""

    name: str
    title: str | None = None
    description: str | None = None
    input_schema: dict[str, Any]
    output_schema: dict[str, Any] | None = None
    annotations: ToolAnnotations | None = None
    icons: list[Icon] | None = None

    def to_mcp_tool(self) -> Tool:
        from mcp.types import Tool

        return Tool(
            name=self.name,
            title=self.title,
            description=self.description,
            inputSchema=self.input_schema,
            outputSchema=self.output_schema,
            annotations=self.annotations,
            icons=self.icons,
        )


class McpResource(CodexBaseModel):
    """Resource exposed by an MCP server. Mirrors `mcp.types.Resource`."""

    uri: str
    name: str
    title: str | None = None
    description: str | None = None
    mime_type: str | None = None
    size: int | None = None
    annotations: Annotations | None = None
    icons: list[Icon] | None = None

    def to_mcp_resource(self) -> Resource:
        from mcp.types import Resource

        return Resource(
            uri=AnyUrl(self.uri),
            name=self.name,
            title=self.title,
            description=self.description,
            mimeType=self.mime_type,
            size=self.size,
            annotations=self.annotations,
            icons=self.icons,
        )


class McpResourceTemplate(CodexBaseModel):
    """Resource template exposed by an MCP server. Mirrors `mcp.types.ResourceTemplate`."""

    uri_template: str
    name: str
    title: str | None = None
    description: str | None = None
    mime_type: str | None = None
    annotations: Annotations | None = None

    def to_mcp_resource(self) -> ResourceTemplate:
        from mcp.types import ResourceTemplate

        return ResourceTemplate(
            uriTemplate=self.uri_template,
            name=self.name,
            title=self.title,
            description=self.description,
            annotations=self.annotations,
        )


class McpServerStatusEntry(CodexBaseModel):
    """Status of a single MCP server."""

    name: str
    tools: dict[str, McpTool] = Field(default_factory=dict)
    resources: list[McpResource] = Field(default_factory=list)
    resource_templates: list[McpResourceTemplate] = Field(default_factory=list)
    auth_status: McpAuthStatus = "unsupported"
