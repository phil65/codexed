from __future__ import annotations

from typing import Any, Literal

from mcp.types import ContentBlock  # noqa: TC002
from pydantic import Field

from codexed.models.base import CodexBaseModel
from codexed.models.codex_types import (  # noqa: TC001
    CollabAgentStatus,
    CollabAgentTool,
    CommandExecutionSource,
    CommandExecutionStatus,
    MessagePhase,
    PatchApplyStatus,
    ToolCallStatus,
)
from codexed.models.command_action import CommandAction  # noqa: TC001
from codexed.models.user_input import UserInput  # noqa: TC001
from codexed.models.web_search import WebSearchAction  # noqa: TC001


# ---------------------------------------------------------------------------
# Types shared with misc.py — defined here to avoid circular imports.
# misc.py re-imports these from this module.
# ---------------------------------------------------------------------------


class DynamicToolCallOutputTextItem(CodexBaseModel):
    """Text output content item for dynamic tool call response."""

    type: Literal["inputText"] = "inputText"
    text: str


class DynamicToolCallOutputImageItem(CodexBaseModel):
    """Image output content item for dynamic tool call response."""

    type: Literal["inputImage"] = "inputImage"
    image_url: str


DynamicToolCallOutputContentItem = DynamicToolCallOutputTextItem | DynamicToolCallOutputImageItem


class PatchChangeKind(CodexBaseModel):
    """Kind of file change (nested object in Codex's fileChange item)."""

    kind: Literal["add", "delete", "update"] = Field(validation_alias="type")
    move_path: str | None = None


class FileUpdateChange(CodexBaseModel):
    """File update change."""

    path: str
    kind: PatchChangeKind
    diff: str | None = None  # May be absent in "inProgress" state


class McpToolCallResult(CodexBaseModel):
    """MCP tool call result."""

    content: list[ContentBlock]
    structured_content: Any = None


class McpToolCallError(CodexBaseModel):
    """MCP tool call error."""

    message: str


class CollabAgentState(CodexBaseModel):
    """Collab agent state."""

    status: CollabAgentStatus
    message: str | None = None


class BaseThreadItem(CodexBaseModel):
    """Base class for thread items."""

    id: str


class ThreadItemUserMessage(BaseThreadItem):
    """User message item."""

    type: Literal["userMessage"] = "userMessage"
    content: list[UserInput]


class ThreadItemAgentMessage(BaseThreadItem):
    """Agent message item."""

    type: Literal["agentMessage"] = "agentMessage"
    text: str
    phase: MessagePhase | None = None


class ThreadItemPlan(BaseThreadItem):
    """Plan item."""

    type: Literal["plan"] = "plan"
    text: str


class ThreadItemReasoning(BaseThreadItem):
    """Reasoning item."""

    type: Literal["reasoning"] = "reasoning"
    summary: list[str] = Field(default_factory=list)
    content: list[str] = Field(default_factory=list)


class ThreadItemCommandExecution(BaseThreadItem):
    """Command execution item."""

    type: Literal["commandExecution"] = "commandExecution"
    command: str
    cwd: str
    process_id: str | None = None
    status: CommandExecutionStatus
    source: CommandExecutionSource = "agent"
    command_actions: list[CommandAction] = Field(default_factory=list)
    aggregated_output: str | None = None
    exit_code: int | None = None
    duration_ms: int | None = None

    @property
    def item_summary(self) -> str:
        """Human-readable summary of this command execution."""
        output = self.aggregated_output or ""
        msg = f"[Executed: {self.command}]"
        if output:
            msg += f"\n{output[:200]}"
        return msg


class ThreadItemFileChange(BaseThreadItem):
    """File change item."""

    type: Literal["fileChange"] = "fileChange"
    changes: list[FileUpdateChange]
    status: PatchApplyStatus

    @property
    def item_summary(self) -> str:
        """Human-readable summary of file changes."""
        paths = [c.path for c in self.changes]
        if len(paths) > 3:  # noqa: PLR2004
            return f"[Files: {', '.join(paths[:3])} +{len(paths) - 3} more]"
        return f"[Files: {', '.join(paths)}]"


class ThreadItemMcpToolCall(BaseThreadItem):
    """MCP tool call item."""

    type: Literal["mcpToolCall"] = "mcpToolCall"
    server: str
    tool: str
    status: ToolCallStatus
    arguments: dict[str, Any] | None = None
    result: McpToolCallResult | None = None
    error: McpToolCallError | None = None
    duration_ms: int | None = None

    @property
    def item_summary(self) -> str:
        """Human-readable summary of this MCP tool call."""
        result_text = ""
        if self.result and self.result.content:
            texts = [str(b.model_dump().get("text", "")) for b in self.result.content]
            result_text = " ".join(texts)
        return f"[Tool: {self.tool}] {result_text[:100]}"


class ThreadItemDynamicToolCall(BaseThreadItem):
    """Dynamic tool call item."""

    type: Literal["dynamicToolCall"] = "dynamicToolCall"
    tool: str
    arguments: dict[str, Any] | None = None
    status: ToolCallStatus
    content_items: list[DynamicToolCallOutputContentItem] | None = None
    success: bool | None = None
    duration_ms: int | None = None


class ThreadItemWebSearch(BaseThreadItem):
    """Web search item."""

    type: Literal["webSearch"] = "webSearch"
    query: str
    action: WebSearchAction | None = None

    @property
    def item_summary(self) -> str:
        """Human-readable summary of this web search."""
        return f"[Web Search: {self.query}]"


class ThreadItemImageView(BaseThreadItem):
    """Image view item."""

    type: Literal["imageView"] = "imageView"
    path: str

    @property
    def item_summary(self) -> str:
        """Human-readable summary of this image view."""
        return f"[Viewed Image: {self.path}]"


class ThreadItemEnteredReviewMode(BaseThreadItem):
    """Entered review mode item."""

    type: Literal["enteredReviewMode"] = "enteredReviewMode"
    review: str

    @property
    def item_summary(self) -> str:
        """Human-readable summary of entering review mode."""
        return f"[Entered Review Mode: {self.review}]"


class ThreadItemExitedReviewMode(BaseThreadItem):
    """Exited review mode item."""

    type: Literal["exitedReviewMode"] = "exitedReviewMode"
    review: str

    @property
    def item_summary(self) -> str:
        """Human-readable summary of exiting review mode."""
        return f"[Exited Review Mode: {self.review}]"


class ThreadItemContextCompaction(BaseThreadItem):
    """Context compaction item."""

    type: Literal["contextCompaction"] = "contextCompaction"


class ThreadItemCollabAgentToolCall(BaseThreadItem):
    """Collab agent tool call item."""

    type: Literal["collabAgentToolCall"] = "collabAgentToolCall"
    tool: CollabAgentTool
    status: ToolCallStatus
    sender_thread_id: str
    receiver_thread_ids: list[str] = Field(default_factory=list)
    prompt: str | None = None
    agents_states: dict[str, CollabAgentState] = Field(default_factory=dict)

    @property
    def item_summary(self) -> str:
        """Human-readable summary of this collab agent tool call."""
        first_state = next(iter(self.agents_states.values()), None)
        status = first_state.status if first_state else "unknown"
        receiver_ids = ", ".join(self.receiver_thread_ids)
        return f"[Collab Agent: {self.tool}] {receiver_ids} ({status})"


# Discriminated union of all ThreadItem types
ThreadItem = (
    ThreadItemUserMessage
    | ThreadItemAgentMessage
    | ThreadItemPlan
    | ThreadItemReasoning
    | ThreadItemCommandExecution
    | ThreadItemFileChange
    | ThreadItemMcpToolCall
    | ThreadItemDynamicToolCall
    | ThreadItemCollabAgentToolCall
    | ThreadItemWebSearch
    | ThreadItemImageView
    | ThreadItemEnteredReviewMode
    | ThreadItemExitedReviewMode
    | ThreadItemContextCompaction
)

ThreadItemType = Literal[
    "userMessage",
    "agentMessage",
    "plan",
    "reasoning",
    "commandExecution",
    "fileChange",
    "mcpToolCall",
    "dynamicToolCall",
    "collabAgentToolCall",
    "webSearch",
    "imageView",
    "enteredReviewMode",
    "exitedReviewMode",
    "contextCompaction",
]
