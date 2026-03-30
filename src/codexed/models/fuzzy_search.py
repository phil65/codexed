"""Fuzzy file search models for the Codex app-server protocol.

EXPERIMENTAL — Session-based fuzzy file search. Start a session with roots,
update with queries, and receive incremental results via notifications.
Also includes the legacy one-shot search API.
"""

from __future__ import annotations

from codexed.models.base import CodexBaseModel
from codexed.models.v2_protocol import FuzzyFileSearchResult


# ============================================================================
# Supporting types
# ============================================================================


class FuzzyFileSearchResponse(CodexBaseModel):
    """Response for the legacy fuzzyFileSearch request."""

    files: list[FuzzyFileSearchResult]


class FuzzyFileSearchSessionStartResponse(CodexBaseModel):
    """Response for fuzzyFileSearch/sessionStart request."""


class FuzzyFileSearchSessionUpdateResponse(CodexBaseModel):
    """Response for fuzzyFileSearch/sessionUpdate request."""


class FuzzyFileSearchSessionStopResponse(CodexBaseModel):
    """Response for fuzzyFileSearch/sessionStop request."""


class FuzzyFileSearchSessionUpdatedData(CodexBaseModel):
    """Data for fuzzyFileSearch/sessionUpdated notification."""

    session_id: str
    query: str
    files: list[FuzzyFileSearchResult]


class FuzzyFileSearchSessionCompletedData(CodexBaseModel):
    """Data for fuzzyFileSearch/sessionCompleted notification."""

    session_id: str
