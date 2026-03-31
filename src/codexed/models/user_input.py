from __future__ import annotations

import base64
from typing import Self

from codexed.models.v2_protocol import (
    ImageUserInput as CodexImageUserInput,
    LocalImageUserInput as CodexLocalImageUserInput,
    MentionUserInput as CodexMentionUserInput,
    SkillUserInput as CodexSkillUserInput,
    TextUserInput as CodexTextUserInput,
)


class TextUserInput(CodexTextUserInput):
    """Text user input."""


class ImageUserInput(CodexImageUserInput):
    """Image URL user input."""

    @classmethod
    def from_bytes(cls, data: bytes, media_type: str) -> Self:
        """Create from raw bytes as a base64 data URI."""
        b64 = base64.b64encode(data).decode()
        data_uri = f"data:{media_type};base64,{b64}"
        return cls(url=data_uri)


class LocalImageUserInput(CodexLocalImageUserInput):
    """Local image file user input."""


class SkillUserInput(CodexSkillUserInput):
    """Skill file user input."""


class MentionUserInput(CodexMentionUserInput):
    """Mention user input."""


# Discriminated union of user input types
UserInput = TextUserInput | ImageUserInput | LocalImageUserInput | SkillUserInput | MentionUserInput
