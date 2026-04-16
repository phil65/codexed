"""Realtime voice session — async context manager for thread-scoped realtime."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Self

from codexed.models import (
    ThreadRealtimeAppendAudioParams,
    ThreadRealtimeAppendAudioResponse,
    ThreadRealtimeAppendTextParams,
    ThreadRealtimeAppendTextResponse,
    ThreadRealtimeAudioChunk,
    ThreadRealtimeClosedMessage,
    ThreadRealtimeListVoicesParams,
    ThreadRealtimeListVoicesResponse,
    ThreadRealtimeStartedMessage,
    ThreadRealtimeStartParams,
    ThreadRealtimeStartResponse,
    ThreadRealtimeStopParams,
    ThreadRealtimeStopResponse,
)


if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from types import TracebackType

    from codexed.client import CodexClient
    from codexed.models import (
        CodexEvent,
        RealtimeOutputModality,
        RealtimeVoice,
        RealtimeVoicesList,
        ThreadRealtimeStartTransport,
    )

logger = logging.getLogger(__name__)


class RealtimeSession:
    """Async context manager for a thread-scoped realtime voice session."""

    def __init__(
        self,
        client: CodexClient,
        thread_id: str,
        prompt: str | None = None,
        *,
        session_id: str | None = None,
        output_modality: RealtimeOutputModality | None = None,
        transport: ThreadRealtimeStartTransport | None = None,
        voice: RealtimeVoice | None = None,
    ) -> None:
        self._client = client
        self._thread_id = thread_id
        self._prompt = prompt
        self._session_id = session_id
        self._queue: asyncio.Queue[CodexEvent | None] = asyncio.Queue()
        self._closed = False
        self._queue_key = f"realtime:{thread_id}"
        self._output_modality = output_modality
        self._transport = transport
        self._voice = voice

    @property
    def thread_id(self) -> str:
        return self._thread_id

    @property
    def session_id(self) -> str | None:
        return self._session_id

    async def __aenter__(self) -> Self:
        # Register our queue for realtime events
        self._client._realtime_queues[self._queue_key] = self._queue

        # Send start request
        params = ThreadRealtimeStartParams(
            thread_id=self._thread_id,
            prompt=self._prompt,
            session_id=self._session_id,
        )
        result = await self._client.dispatch.send_request("thread/realtime/start", params)
        ThreadRealtimeStartResponse.model_validate(result)

        # Wait for the started notification
        event = await self._queue.get()
        if isinstance(event, ThreadRealtimeStartedMessage):
            self._session_id = event.params.session_id
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        try:
            if not self._closed:
                params = ThreadRealtimeStopParams(thread_id=self._thread_id)
                result = await self._client.dispatch.send_request("thread/realtime/stop", params)
                ThreadRealtimeStopResponse.model_validate(result)
                # Drain until we get the closed notification
                while True:
                    event = await self._queue.get()
                    if event is None or isinstance(event, ThreadRealtimeClosedMessage):
                        break
        except Exception:  # noqa: BLE001
            logger.debug("Error during realtime cleanup", exc_info=True)
        finally:
            self._client._realtime_queues.pop(self._queue_key, None)

    def __aiter__(self) -> AsyncIterator[CodexEvent]:
        return self

    async def __anext__(self) -> CodexEvent:
        if self._closed:
            raise StopAsyncIteration
        event = await self._queue.get()
        if event is None or isinstance(event, ThreadRealtimeClosedMessage):
            self._closed = True
            if isinstance(event, ThreadRealtimeClosedMessage):
                return event
            raise StopAsyncIteration
        return event

    async def send_text(self, text: str) -> None:
        """Send text input to the realtime session."""
        params = ThreadRealtimeAppendTextParams(thread_id=self._thread_id, text=text)
        result = await self._client.dispatch.send_request("thread/realtime/appendText", params)
        ThreadRealtimeAppendTextResponse.model_validate(result)

    async def list_voices(self) -> RealtimeVoicesList:
        """List available voices for the realtime session."""
        params = ThreadRealtimeListVoicesParams()
        result = await self._client.dispatch.send_request("thread/realtime/listVoices", params)
        data = ThreadRealtimeListVoicesResponse.model_validate(result)
        return data.voices

    async def send_audio(
        self,
        data: str,
        *,
        sample_rate: int = 24_000,
        num_channels: int = 1,
        samples_per_channel: int | None = None,
        item_id: str | None = None,
    ) -> None:
        """Send an audio chunk to the realtime session.

        Args:
            data: Base64-encoded audio data.
            sample_rate: Audio sample rate in Hz.
            num_channels: Number of audio channels.
            samples_per_channel: Number of samples per channel.
            item_id: Optional item ID for the audio chunk.
        """
        params = ThreadRealtimeAppendAudioParams(
            thread_id=self._thread_id,
            audio=ThreadRealtimeAudioChunk(
                data=data,
                sample_rate=sample_rate,
                num_channels=num_channels,
                samples_per_channel=samples_per_channel,
                item_id=item_id,
            ),
        )
        result = await self._client.dispatch.send_request("thread/realtime/appendAudio", params)
        ThreadRealtimeAppendAudioResponse.model_validate(result)

    def __repr__(self) -> str:
        state = "closed" if self._closed else "active"
        return (
            f"RealtimeSession(thread_id={self._thread_id!r}, "
            f"session_id={self._session_id!r}, {state})"
        )
