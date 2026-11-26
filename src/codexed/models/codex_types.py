"""Codex data types."""

from typing import Literal


# Type aliases for Codex types
ApprovalDecision = Literal["allow", "allowForSession", "deny", "denyForSession"]
SkillApprovalDecision = Literal["allow", "deny"]
ElicitationAction = Literal["accept", "decline", "cancel"]
