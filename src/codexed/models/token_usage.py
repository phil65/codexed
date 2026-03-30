"""Token usage models for Codex."""

from __future__ import annotations

from codexed.models.base import CodexBaseModel


class Usage(CodexBaseModel):
    """Simple token usage (legacy)."""

    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
