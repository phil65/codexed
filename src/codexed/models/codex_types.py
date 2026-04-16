"""Codex data types."""

from __future__ import annotations

from typing import Literal


# Type aliases for Codex types
ApprovalDecision = Literal["allow", "allowForSession", "deny", "denyForSession"]
SkillApprovalDecision = Literal["allow", "deny"]
ElicitationAction = Literal["accept", "decline", "cancel"]
