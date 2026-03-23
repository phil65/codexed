"""Fuzzy file search models for the Codex app-server protocol.

EXPERIMENTAL — Session-based fuzzy file search. Start a session with roots,
update with queries, and receive incremental results via notifications.
Also includes the legacy one-shot search API.
"""

from __future__ import annotations

from typing import Literal

from codexed.models.base import CodexBaseModel


# ============================================================================
# Supporting types
# ============================================================================

FuzzyFileSearchMatchType = Literal["file", "directory"]
"""Whether the match is a file or directory."""


class FuzzyFileSearchResult(CodexBaseModel):
    """A single fuzzy file search result."""

    root: str
    path: str
    match_type: FuzzyFileSearchMatchType
    file_name: str
    score: int
    indices: list[int] | None = None


# ============================================================================
# Legacy one-shot search
# ============================================================================


class FuzzyFileSearchParams(CodexBaseModel):
    """Params for the legacy fuzzyFileSearch request."""

    query: str
    roots: list[str]
    cancellation_token: str | None = None


class FuzzyFileSearchResponse(CodexBaseModel):
    """Response for the legacy fuzzyFileSearch request."""

    files: list[FuzzyFileSearchResult]


# ============================================================================
# Session-based search (EXPERIMENTAL)
# ============================================================================


class FuzzyFileSearchSessionStartParams(CodexBaseModel):
    """Params for fuzzyFileSearch/sessionStart request."""

    session_id: str
    roots: list[str]


class FuzzyFileSearchSessionStartResponse(CodexBaseModel):
    """Response for fuzzyFileSearch/sessionStart request."""


class FuzzyFileSearchSessionUpdateParams(CodexBaseModel):
    """Params for fuzzyFileSearch/sessionUpdate request."""

    session_id: str
    query: str


class FuzzyFileSearchSessionUpdateResponse(CodexBaseModel):
    """Response for fuzzyFileSearch/sessionUpdate request."""


class FuzzyFileSearchSessionStopParams(CodexBaseModel):
    """Params for fuzzyFileSearch/sessionStop request."""

    session_id: str


class FuzzyFileSearchSessionStopResponse(CodexBaseModel):
    """Response for fuzzyFileSearch/sessionStop request."""


# ============================================================================
# Server notification data
# ============================================================================


class FuzzyFileSearchSessionUpdatedData(CodexBaseModel):
    """Data for fuzzyFileSearch/sessionUpdated notification."""

    session_id: str
    query: str
    files: list[FuzzyFileSearchResult]


class FuzzyFileSearchSessionCompletedData(CodexBaseModel):
    """Data for fuzzyFileSearch/sessionCompleted notification."""

    session_id: str
