"""ResponseItem types for the Codex protocol.

These represent the conversation history items used in thread/resume.
Matches the Rust `ResponseItem` discriminated union from the protocol.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Discriminator

from codexed.models.base import CodexBaseModel
from codexed.models.v2_protocol import (
    ContentItem,
    ExecLocalShellAction,
    FindInPageResponsesApiWebSearchAction,
    GhostCommit,
    InputImageFunctionCallOutputContentItem,
    InputTextFunctionCallOutputContentItem,
    OpenPageResponsesApiWebSearchAction,
    OtherResponsesApiWebSearchAction,
    ReasoningTextReasoningItemContent,
    SearchResponsesApiWebSearchAction,
    SummaryTextReasoningItemReasoningSummary,
    TextReasoningItemContent,
)


ReasoningItemContent = Annotated[
    ReasoningTextReasoningItemContent | TextReasoningItemContent,
    Discriminator("type"),
]


FunctionCallOutputContentItem = Annotated[
    InputTextFunctionCallOutputContentItem | InputImageFunctionCallOutputContentItem,
    Discriminator("type"),
]


class FunctionCallOutputPayload(CodexBaseModel):
    """Payload for function call output."""

    body: str | list[FunctionCallOutputContentItem]
    success: bool | None = None


# --- Shell action ---


LocalShellAction = ExecLocalShellAction  # Currently only one variant


# --- Web search action (re-exported from v2_protocol) ---

WebSearchAction = Annotated[
    SearchResponsesApiWebSearchAction
    | OpenPageResponsesApiWebSearchAction
    | FindInPageResponsesApiWebSearchAction
    | OtherResponsesApiWebSearchAction,
    Discriminator("type"),
]


# --- ResponseItem variants ---


class MessageResponseItem(CodexBaseModel):
    """Message response item."""

    type: Literal["message"] = "message"
    role: str
    content: list[ContentItem]
    end_turn: bool | None = None
    phase: Literal["commentary", "final_answer"] | None = None


class ReasoningResponseItem(CodexBaseModel):
    """Reasoning response item."""

    type: Literal["reasoning"] = "reasoning"
    summary: list[SummaryTextReasoningItemReasoningSummary]
    content: list[ReasoningItemContent] | None = None
    encrypted_content: str | None = None


class LocalShellCallResponseItem(CodexBaseModel):
    """Local shell call response item."""

    type: Literal["local_shell_call"] = "local_shell_call"
    call_id: str | None = None
    status: Literal["completed", "in_progress", "incomplete"]
    action: LocalShellAction


class FunctionCallResponseItem(CodexBaseModel):
    """Function call response item."""

    type: Literal["function_call"] = "function_call"
    name: str
    arguments: str
    call_id: str


class FunctionCallOutputResponseItem(CodexBaseModel):
    """Function call output response item."""

    type: Literal["function_call_output"] = "function_call_output"
    call_id: str
    output: FunctionCallOutputPayload


class CustomToolCallResponseItem(CodexBaseModel):
    """Custom tool call response item."""

    type: Literal["custom_tool_call"] = "custom_tool_call"
    status: str | None = None
    call_id: str
    name: str
    input: str


class CustomToolCallOutputResponseItem(CodexBaseModel):
    """Custom tool call output response item."""

    type: Literal["custom_tool_call_output"] = "custom_tool_call_output"
    call_id: str
    output: FunctionCallOutputPayload


class WebSearchCallResponseItem(CodexBaseModel):
    """Web search call response item."""

    type: Literal["web_search_call"] = "web_search_call"
    status: str | None = None
    action: WebSearchAction | None = None


class ImageGenerationCallResponseItem(CodexBaseModel):
    """Image generation call response item."""

    type: Literal["image_generation_call"] = "image_generation_call"
    id: str
    status: str
    revised_prompt: str | None = None
    result: str


class GhostSnapshotResponseItem(CodexBaseModel):
    """Ghost snapshot response item."""

    type: Literal["ghost_snapshot"] = "ghost_snapshot"
    ghost_commit: GhostCommit


class CompactionResponseItem(CodexBaseModel):
    """Compaction response item."""

    type: Literal["compaction"] = "compaction"
    encrypted_content: str


class OtherResponseItem(CodexBaseModel):
    """Other/unknown response item."""

    type: Literal["other"] = "other"


ResponseItem = Annotated[
    MessageResponseItem
    | ReasoningResponseItem
    | LocalShellCallResponseItem
    | FunctionCallResponseItem
    | FunctionCallOutputResponseItem
    | CustomToolCallResponseItem
    | CustomToolCallOutputResponseItem
    | WebSearchCallResponseItem
    | ImageGenerationCallResponseItem
    | GhostSnapshotResponseItem
    | CompactionResponseItem
    | OtherResponseItem,
    Discriminator("type"),
]
