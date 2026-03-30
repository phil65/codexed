"""ResponseItem types for the Codex protocol.

These represent the conversation history items used in thread/resume.
Matches the Rust `ResponseItem` discriminated union from the protocol.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Discriminator

from codexed.models.base import CodexBaseModel
from codexed.models.v2_protocol import (
    CompactionResponseItem,
    ContentItem,
    CustomToolCallOutputResponseItem,
    CustomToolCallResponseItem,
    FindInPageResponsesApiWebSearchAction,
    FunctionCallOutputResponseItem,
    FunctionCallResponseItem,
    GhostSnapshotResponseItem,
    ImageGenerationCallResponseItem,
    InputImageFunctionCallOutputContentItem,
    InputTextFunctionCallOutputContentItem,
    LocalShellCallResponseItem,
    OpenPageResponsesApiWebSearchAction,
    OtherResponseItem,
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


WebSearchAction = Annotated[
    SearchResponsesApiWebSearchAction
    | OpenPageResponsesApiWebSearchAction
    | FindInPageResponsesApiWebSearchAction
    | OtherResponsesApiWebSearchAction,
    Discriminator("type"),
]


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


class WebSearchCallResponseItem(CodexBaseModel):
    """Web search call response item."""

    type: Literal["web_search_call"] = "web_search_call"
    status: str | None = None
    action: WebSearchAction | None = None


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
