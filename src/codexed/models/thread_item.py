from __future__ import annotations

from typing import Any, Literal

from mcp.types import ContentBlock
from pydantic import Field

from codexed.models.base import CodexBaseModel
from codexed.models.v2_protocol import (
    AgentMessageDelivery,
    AgentMessageModeration,
    AsyncUserInputQuestion,
    CollabAgentState,
    CollabAgentTool,
    CollabAgentToolCallStatus,
    CommandAction,
    CommandExecutionSource,
    CommandExecutionStatus,
    DynamicToolCallOutputContentItem,
    DynamicToolCallStatus,
    FileUpdateChange,
    FunctionCallOutputBody,
    HookPromptFragment,
    ImageGenerationFailure,
    ImageGenerationInputImage,
    McpAppUi,
    McpToolCallAppContext,
    McpToolCallError,
    McpToolCallStatus,
    MemoryCitation,
    MessagePhase,
    PatchApplyStatus,
    ReasoningEffort,
    SubAgentActivityKind,
    UserInput,
    WebSearchAction,
)


class McpToolCallResult(CodexBaseModel):
    """MCP tool call result."""

    content: list[ContentBlock]
    structured_content: Any = None
    meta: dict[str, Any] | None = Field(default=None, alias="_meta")
    """MCP `_meta` field of the tool result."""


class BaseThreadItem(CodexBaseModel):
    """Base class for thread items."""

    id: str
    started_at_ms: int | None = None
    """Unix timestamp (in milliseconds) when this item lifecycle started."""
    completed_at_ms: int | None = None
    """Unix timestamp (in milliseconds) when this item lifecycle completed."""

    @property
    def inferred_arguments(self) -> dict[str, Any] | None:
        """Best-effort reconstruction of tool-call-like arguments.

        Returns a dict for tool-like items, None for non-tool items.
        """
        return None


class ThreadItemUserMessage(BaseThreadItem):
    """User message item."""

    type: Literal["userMessage"] = "userMessage"
    content: list[UserInput]
    client_id: str | None = None


class ThreadItemAgentMessage(BaseThreadItem):
    """Agent message item."""

    type: Literal["agentMessage"] = "agentMessage"
    text: str
    phase: MessagePhase | None = None
    delivery: AgentMessageDelivery | None = None
    memory_citation: MemoryCitation | None = None
    moderation: AgentMessageModeration | None = None
    questions: list[AsyncUserInputQuestion] | None = None


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
    def inferred_arguments(self) -> dict[str, Any]:
        return {"command": self.command, "cwd": self.cwd}

    @property
    def item_summary(self) -> str:
        """Human-readable summary of this command execution."""
        msg = f"[Executed: {self.command}]"
        if output := self.aggregated_output:
            msg += f"\n{output[:200]}"
        return msg

    plugin_id: str | None = None
    script_path: str | None = None


class ThreadItemFileChange(BaseThreadItem):
    """File change item."""

    type: Literal["fileChange"] = "fileChange"
    changes: list[FileUpdateChange]
    status: PatchApplyStatus

    @property
    def inferred_arguments(self) -> dict[str, Any]:
        return {"changes": [c.model_dump() for c in self.changes]}

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
    status: McpToolCallStatus
    arguments: dict[str, Any] | None = None
    result: McpToolCallResult | None = None
    error: McpToolCallError | None = None
    duration_ms: int | None = None

    @property
    def inferred_arguments(self) -> dict[str, Any] | None:
        return self.arguments

    @property
    def item_summary(self) -> str:
        """Human-readable summary of this MCP tool call."""
        result_text = ""
        if self.result and self.result.content:
            texts = [str(b.model_dump().get("text", "")) for b in self.result.content]
            result_text = " ".join(texts)
        return f"[Tool: {self.tool}] {result_text[:100]}"

    app_context: McpToolCallAppContext | None = None
    mcp_app_resource_uri: str | None = None
    mcp_app_ui: McpAppUi | None = None
    plugin_id: str | None = None
    read_only_hint: bool | None = None


class ThreadItemDynamicToolCall(BaseThreadItem):
    """Dynamic tool call item."""

    type: Literal["dynamicToolCall"] = "dynamicToolCall"
    tool: str
    arguments: dict[str, Any] | None = None
    status: DynamicToolCallStatus
    content_items: list[DynamicToolCallOutputContentItem] | None = None
    success: bool | None = None
    duration_ms: int | None = None

    @property
    def inferred_arguments(self) -> dict[str, Any] | None:
        return self.arguments

    namespace: str | None = None


class ThreadItemWebSearch(BaseThreadItem):
    """Web search item."""

    type: Literal["webSearch"] = "webSearch"
    query: str
    action: WebSearchAction | None = None

    @property
    def inferred_arguments(self) -> dict[str, Any]:
        return {"query": self.query}

    @property
    def item_summary(self) -> str:
        """Human-readable summary of this web search."""
        return f"[Web Search: {self.query}]"

    results: list[Any] | None = None


class ThreadItemImageView(BaseThreadItem):
    """Image view item."""

    type: Literal["imageView"] = "imageView"
    path: str

    @property
    def inferred_arguments(self) -> dict[str, Any]:
        return {"path": self.path}

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
    status: CollabAgentToolCallStatus
    sender_thread_id: str
    receiver_thread_ids: list[str] = Field(default_factory=list)
    prompt: str | None = None
    agents_states: dict[str, CollabAgentState] = Field(default_factory=dict)

    @property
    def inferred_arguments(self) -> dict[str, Any]:
        args: dict[str, Any] = {"tool": self.tool}
        if self.prompt is not None:
            args["prompt"] = self.prompt
        if self.receiver_thread_ids:
            args["receiver_thread_ids"] = self.receiver_thread_ids
        return args

    @property
    def item_summary(self) -> str:
        """Human-readable summary of this collab agent tool call."""
        first_state = next(iter(self.agents_states.values()), None)
        status = first_state.status if first_state else "unknown"
        receiver_ids = ", ".join(self.receiver_thread_ids)
        return f"[Collab Agent: {self.tool}] {receiver_ids} ({status})"

    model: str | None = None
    reasoning_effort: ReasoningEffort | None = None


# Discriminated union of all ThreadItem types
class ThreadItemFunctionCallOutput(BaseThreadItem):
    """Output of a function call."""

    type: Literal["functionCallOutput"] = "functionCallOutput"
    name: str
    namespace: str | None = None
    output: FunctionCallOutputBody


class ThreadItemHookPrompt(BaseThreadItem):
    """Prompt injected by a hook."""

    type: Literal["hookPrompt"] = "hookPrompt"
    fragments: list[HookPromptFragment]


class ThreadItemImageGeneration(BaseThreadItem):
    """Image generation item."""

    type: Literal["imageGeneration"] = "imageGeneration"
    status: str
    result: str
    failure: ImageGenerationFailure | None = None
    generation_id: str | None = None
    input_images: list[ImageGenerationInputImage] | None = None
    revised_prompt: str | None = None
    saved_path: str | None = None
    transparent_background: bool | None = None


class ThreadItemSleep(BaseThreadItem):
    """Sleep item."""

    type: Literal["sleep"] = "sleep"
    duration_ms: int = Field(ge=0)


class ThreadItemSubAgentActivity(BaseThreadItem):
    """Activity of a sub-agent."""

    type: Literal["subAgentActivity"] = "subAgentActivity"
    agent_path: str
    agent_thread_id: str
    kind: SubAgentActivityKind
    model: str | None = None
    reasoning_effort: ReasoningEffort | None = None


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
    | ThreadItemFunctionCallOutput
    | ThreadItemHookPrompt
    | ThreadItemImageGeneration
    | ThreadItemSleep
    | ThreadItemSubAgentActivity
)
