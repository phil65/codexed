"""Pydantic models for Codex JSON-RPC API requests and responses."""

from __future__ import annotations

from typing import Any

from mcp.types import Resource, ResourceTemplate, Tool
from pydantic import Field

from codexed.models.base import CodexBaseModel
from codexed.models.codex_types import SkillApprovalDecision
from codexed.models.thread_item import ThreadItem, ThreadItemAgentMessage
from codexed.models.v2_protocol import (
    AbsolutePathBuf,
    GitInfo,
    McpAuthStatus,
    NetworkApprovalProtocol,
    NetworkDomainPermission,
    SessionSource,
    ThreadStatus,
    TurnError,
    TurnStatus,
)


class NetworkApprovalContext(CodexBaseModel):
    """Network approval context for command approvals."""

    host: str
    protocol: NetworkApprovalProtocol


class NetworkPolicyAmendment(CodexBaseModel):
    """Proposed network policy amendment."""

    host: str
    action: NetworkDomainPermission


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

    completed_at: int | None = None
    """
    Unix timestamp (in seconds) when the turn completed.
    """
    duration_ms: int | None = None
    """
    Duration between turn start and completion in milliseconds, if known.
    """
    error: TurnError | None = None
    """
    Only populated when the Turn's status is failed.
    """
    items: list[ThreadItem]
    """
    Only populated on a `thread/resume` or `thread/fork` response.

    For all other responses and notifications returning a Turn,
    the items field will be an empty list.
    """
    started_at: int | None = None
    """
    Unix timestamp (in seconds) when the turn started.
    """
    status: TurnStatus

    @property
    def final_response(self) -> str | None:
        """Extract the final assistant response text from this turn.

        Looks for the last ``ThreadItemAgentMessage`` with ``phase="final_answer"``.
        Falls back to the last agent message with no phase (for models that don't
        emit phase metadata). Returns None if the turn has no agent messages.

        For structured output turns, this returns the raw JSON string.
        """
        last_unphased: str | None = None
        for item in reversed(self.items):
            match item:
                case ThreadItemAgentMessage(phase="final_answer", text=text):
                    return text
                case ThreadItemAgentMessage(phase=None, text=text) if last_unphased is None:
                    last_unphased = text
        return last_unphased


class Thread(CodexBaseModel):
    agent_nickname: str | None = None
    """
    Optional random unique nickname assigned to an AgentControl-spawned sub-agent.
    """
    agent_role: str | None = None
    """
    Optional role (agent_role) assigned to an AgentControl-spawned sub-agent.
    """
    cli_version: str
    """
    Version of the CLI that created the thread.
    """
    created_at: int
    """
    Unix timestamp (in seconds) when the thread was created.
    """
    cwd: AbsolutePathBuf
    """
    Working directory captured for the thread.
    """
    ephemeral: bool
    """
    Whether the thread is ephemeral and should not be materialized on disk.
    """
    forked_from_id: str | None = None
    """
    Source thread id when this thread was created by forking another thread.
    """
    git_info: GitInfo | None = None
    """
    Optional Git metadata captured when the thread was created.
    """
    id: str
    model_provider: str
    """
    Model provider used for this thread (for example, 'openai').
    """
    name: str | None = None
    """
    Optional user-facing thread title.
    """
    path: str | None = None
    """
    [UNSTABLE] Path to the thread on disk.
    """
    preview: str
    """
    Usually the first user message in the thread, if available.
    """
    source: SessionSource
    """
    Origin of the thread (CLI, VSCode, codex exec, codex app-server, etc.).
    """
    status: ThreadStatus
    """
    Current runtime status for the thread.
    """
    turns: list[Turn]
    """
    Only populated on `thread/resume`, `thread/rollback`, `thread/fork`, and `thread/read`
    (when `includeTurns` is true) responses.
    For all other responses and notifications returning a Thread,
    the turns field will be an empty list.
    """
    updated_at: int
    """
    Unix timestamp (in seconds) when the thread was last updated.
    """


class TurnData(CodexBaseModel):
    """Turn data in responses."""

    id: str
    status: TurnStatus  # always provided by the server
    thread_id: str | None = None
    items: list[ThreadItem] = Field(default_factory=list)
    error: str | None = None


class McpServerStatusEntry(CodexBaseModel):
    """Status of a single MCP server."""

    name: str
    tools: dict[str, Tool] = Field(default_factory=dict)
    resources: list[Resource] = Field(default_factory=list)
    resource_templates: list[ResourceTemplate] = Field(default_factory=list)
    auth_status: McpAuthStatus = "unsupported"
