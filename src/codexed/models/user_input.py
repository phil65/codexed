from __future__ import annotations

import base64
from typing import Literal, Self

from pydantic import Field

from codexed.models.base import CodexBaseModel
from codexed.models.v2_protocol import TextElement


class TextUserInput(CodexBaseModel):
    """Text user input."""

    type: Literal["text"] = "text"
    text: str
    text_elements: list[TextElement] = Field(default_factory=list)


class ImageUserInput(CodexBaseModel):
    """Image URL user input."""

    type: Literal["image"] = "image"
    url: str

    @classmethod
    def from_bytes(cls, data: bytes, media_type: str) -> Self:
        """Create from raw bytes as a base64 data URI."""
        b64 = base64.b64encode(data).decode()
        data_uri = f"data:{media_type};base64,{b64}"
        return cls(url=data_uri)


class LocalImageUserInput(CodexBaseModel):
    """Local image file user input."""

    type: Literal["localImage"] = "localImage"
    path: str


class SkillUserInput(CodexBaseModel):
    """Skill file user input."""

    type: Literal["skill"] = "skill"
    name: str
    path: str


class MentionUserInput(CodexBaseModel):
    """Mention user input."""

    type: Literal["mention"] = "mention"
    name: str
    path: str


# Discriminated union of user input types
UserInput = TextUserInput | ImageUserInput | LocalImageUserInput | SkillUserInput | MentionUserInput
