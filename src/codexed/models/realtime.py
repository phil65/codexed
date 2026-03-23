"""Realtime voice conversation models for the Codex app-server protocol.

EXPERIMENTAL - All realtime types are experimental and subject to change.
Realtime enables voice conversations with the Codex agent, supporting
bidirectional audio streaming, text input, and transcript updates.

See: https://github.com/openai/codex/tree/main/codex-rs/app-server-protocol
"""

from __future__ import annotations

from typing import Any, Literal

from codexed.models.base import CodexBaseModel


# ============================================================================
# Enums / Literal types
# ============================================================================

RealtimeConversationVersion = Literal["v1", "v2"]
"""Realtime conversation protocol version."""


# ============================================================================
# Audio data
# ============================================================================


class RealtimeAudioChunk(CodexBaseModel):
    """Audio chunk for realtime streaming (base64-encoded PCM data)."""

    data: str
    sample_rate: int
    num_channels: int
    samples_per_channel: int | None = None
    item_id: str | None = None


# ============================================================================
# Client request params / responses
# ============================================================================


class RealtimeStartParams(CodexBaseModel):
    """Params for thread/realtime/start request."""

    thread_id: str
    prompt: str
    session_id: str | None = None


class RealtimeStartResponse(CodexBaseModel):
    """Response for thread/realtime/start request."""


class RealtimeAppendAudioParams(CodexBaseModel):
    """Params for thread/realtime/appendAudio request."""

    thread_id: str
    audio: RealtimeAudioChunk


class RealtimeAppendAudioResponse(CodexBaseModel):
    """Response for thread/realtime/appendAudio request."""


class RealtimeAppendTextParams(CodexBaseModel):
    """Params for thread/realtime/appendText request."""

    thread_id: str
    text: str


class RealtimeAppendTextResponse(CodexBaseModel):
    """Response for thread/realtime/appendText request."""


class RealtimeStopParams(CodexBaseModel):
    """Params for thread/realtime/stop request."""

    thread_id: str


class RealtimeStopResponse(CodexBaseModel):
    """Response for thread/realtime/stop request."""


# ============================================================================
# Server notification data
# ============================================================================


class RealtimeStartedData(CodexBaseModel):
    """Data for thread/realtime/started notification."""

    thread_id: str
    session_id: str | None = None
    version: RealtimeConversationVersion


class RealtimeItemAddedData(CodexBaseModel):
    """Data for thread/realtime/itemAdded notification."""

    thread_id: str
    item: Any


class RealtimeTranscriptUpdatedData(CodexBaseModel):
    """Data for thread/realtime/transcriptUpdated notification."""

    thread_id: str
    role: str
    text: str


class RealtimeOutputAudioDeltaData(CodexBaseModel):
    """Data for thread/realtime/outputAudio/delta notification."""

    thread_id: str
    audio: RealtimeAudioChunk


class RealtimeErrorData(CodexBaseModel):
    """Data for thread/realtime/error notification."""

    thread_id: str
    message: str


class RealtimeClosedData(CodexBaseModel):
    """Data for thread/realtime/closed notification."""

    thread_id: str
    reason: str | None = None
