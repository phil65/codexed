"""Session turn streaming reacts to completion, error and token-usage events."""

from __future__ import annotations

import asyncio
from typing import Any

from pydantic import BaseModel
import pytest

from codexed import CodexClient, Session, TurnFailedError
from codexed.models import ThreadResponse


THREAD_ID = "thread-1"
TURN_ID = "turn-1"
USAGE = {"totalTokens": 3, "inputTokens": 2, "cachedInputTokens": 0}
USAGE |= {"outputTokens": 1, "reasoningOutputTokens": 0}


class Answer(BaseModel):
    value: int


def make_session(notifications: list[tuple[str, dict[str, Any]]]) -> Session:
    client = CodexClient()
    tasks: list[asyncio.Task[None]] = []

    async def send_request(method: str, _params: Any) -> dict[str, Any]:
        assert method == "turn/start"

        async def emit() -> None:
            for name, params in notifications:
                await client._handle_notification(name, params)

        tasks.append(asyncio.get_running_loop().create_task(emit()))
        return {"turn": {"id": TURN_ID, "items": [], "status": "inProgress"}}

    client.dispatch.send_request = send_request  # type: ignore[method-assign]
    response = ThreadResponse.model_construct(thread=type("T", (), {"id": THREAD_ID})())
    return Session(client, response)


def completed(text: str) -> tuple[str, dict[str, Any]]:
    item = {"type": "agentMessage", "id": "m1", "text": text, "phase": "final_answer"}
    turn = {"id": TURN_ID, "items": [item], "status": "completed"}
    return "turn/completed", {"threadId": THREAD_ID, "turn": turn}


async def test_turn_stream_structured_parses_final_answer() -> None:
    session = make_session([completed('{"value": 42}')])
    result = await asyncio.wait_for(session.turn_stream_structured("q", Answer), 5)
    assert result.value == 42  # noqa: PLR2004


async def consume(session: Session) -> None:
    async def run() -> None:
        async for _ in session.turn_stream("q"):
            pass

    await asyncio.wait_for(run(), 5)


async def test_turn_stream_raises_on_error_event() -> None:
    error = {"message": "boom"}
    params = {"threadId": THREAD_ID, "turnId": TURN_ID, "error": error, "willRetry": False}
    session = make_session([("error", params)])
    with pytest.raises(TurnFailedError, match="boom"):
        await consume(session)


async def test_turn_stream_records_token_usage() -> None:
    usage = {"total": USAGE, "last": USAGE, "modelContextWindow": 1000}
    params = {"threadId": THREAD_ID, "turnId": TURN_ID, "tokenUsage": usage}
    session = make_session([("thread/tokenUsage/updated", params), completed("done")])
    await consume(session)
    assert session.usage is not None
    assert session.usage.total.total_tokens == 3  # noqa: PLR2004
