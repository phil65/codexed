"""Transport and dispatch lifecycle against a scripted app-server process."""

import asyncio
import os
from pathlib import Path
import sys
from typing import Any

import pytest

from codexed import CodexClient, Session
from codexed.client.dispatch import Dispatch
from codexed.exceptions import CodexProcessError, TransportClosedError
from codexed.models import ThreadResponse
from codexed.transport import StdioTransport


pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="POSIX shebang script")

FAKE_SERVER = Path(__file__).with_name("fake_app_server.py")


@pytest.fixture
def fake_codex(tmp_path: Path) -> str:
    """An executable that runs the fake server (the transport appends ``app-server``)."""
    script = tmp_path / "codex"
    script.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{FAKE_SERVER}" "$@"\n')
    script.chmod(0o755)
    return str(script)


def client_for(command: str, scenario: str, **env: str) -> CodexClient:
    return CodexClient(codex_command=command, env_vars={"FAKE_SCENARIO": scenario, **env})


def session_for(client: CodexClient) -> Session:
    response = ThreadResponse.model_construct(thread=type("T", (), {"id": "thread-1"})())
    return Session(client, response)


async def test_server_exit_fails_pending_request(fake_codex: str) -> None:
    async with client_for(fake_codex, "") as client:
        with pytest.raises(TransportClosedError, match=r"(?s)exit code 3.*panic: something broke"):
            await asyncio.wait_for(client.dispatch.send_request("die"), 5)
        # Later requests fail at once instead of writing to a dead pipe.
        with pytest.raises(TransportClosedError):
            await asyncio.wait_for(client.dispatch.send_request("model/list"), 5)


async def test_server_exit_ends_turn_stream_with_error(fake_codex: str) -> None:
    async with client_for(fake_codex, "") as client:
        session = session_for(client)

        async def fake_start(method: str, params: Any = None) -> Any:
            return await real_send("turn/start-then-die", params)

        real_send = client.dispatch.send_request
        client.dispatch.send_request = fake_start  # type: ignore[method-assign]

        async def consume() -> None:
            async for _ in session.turn_stream("hi"):
                pass

        with pytest.raises(TransportClosedError):
            await asyncio.wait_for(consume(), 5)


async def test_garbage_on_stdout_is_skipped(fake_codex: str) -> None:
    async def run() -> Any:
        async with client_for(fake_codex, "garbage") as client:
            return await client.dispatch.send_request("ping")

    assert await asyncio.wait_for(run(), 10) == {"echo": "ping"}


async def test_stderr_flood_does_not_block_the_server(fake_codex: str) -> None:
    async def run() -> Any:
        async with client_for(fake_codex, "stderr_flood") as client:
            return await client.dispatch.send_request("ping")

    assert await asyncio.wait_for(run(), 30) == {"echo": "ping"}


async def test_turn_events_right_after_the_response_reach_the_stream(fake_codex: str) -> None:
    listener_events: list[str] = []
    async with client_for(fake_codex, "") as client:
        client.add_event_listener(lambda e: listener_events.append(e.method))
        session = session_for(client)

        async def consume() -> list[str]:
            return [event.method async for event in session.turn_stream("hi")]

        methods = await asyncio.wait_for(consume(), 5)
    assert methods == ["turn/started", "turn/completed"]
    assert listener_events == []


async def test_server_request_handler_may_call_the_client(fake_codex: str) -> None:
    """A handler awaiting a client request must not block the read loop (deadlock)."""
    transport = StdioTransport(fake_codex, env_vars={"FAKE_SCENARIO": "server_request"})
    done = asyncio.Event()
    answers: list[Any] = []

    async def on_notification(method: str, params: dict[str, Any]) -> None:
        pass

    async def on_server_request(method: str, request_id: int | str, params: Any) -> None:
        answers.append(await dispatch.send_request("config/read"))
        await dispatch.send_response(request_id, {})
        done.set()

    dispatch = Dispatch(
        transport, on_notification=on_notification, on_server_request=on_server_request
    )
    await dispatch.start()
    try:
        await asyncio.wait_for(dispatch.send_request("initialize"), 5)
        await asyncio.wait_for(done.wait(), 5)
    finally:
        await dispatch.stop()
    assert answers == [{"echo": "config/read"}]


async def test_cancelled_request_is_forgotten(fake_codex: str) -> None:
    async with client_for(fake_codex, "") as client:
        task = asyncio.create_task(client.dispatch.send_request("never-answered-yet"))
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert client.dispatch._pending_requests == {}


@pytest.mark.skipif(not hasattr(os, "killpg"), reason="process groups")
async def test_stop_kills_the_server_children(fake_codex: str, tmp_path: Path) -> None:
    pid_file = tmp_path / "child.pid"
    async with client_for(fake_codex, "child", CHILD_PID_FILE=str(pid_file)) as client:
        await client.dispatch.send_request("ping")
    child = int(pid_file.read_text())
    for _ in range(50):
        try:
            os.kill(child, 0)
        except ProcessLookupError:
            break
        await asyncio.sleep(0.1)
    else:
        os.kill(child, 9)
        pytest.fail("child of the app-server survived stop()")


async def _interrupts(client: CodexClient) -> list[dict[str, Any]]:
    result = await asyncio.wait_for(client.dispatch.send_request("fake/interrupts"), 5)
    return result["interrupts"]


async def test_cancelled_turn_stream_interrupts_the_turn(fake_codex: str) -> None:
    async with client_for(fake_codex, "slow_turn") as client:
        session = session_for(client)
        started = asyncio.Event()

        async def consume() -> None:
            async for event in session.turn_stream("hi"):
                if event.method == "turn/started":
                    started.set()

        task = asyncio.create_task(consume())
        await asyncio.wait_for(started.wait(), 5)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert await _interrupts(client) == [{"threadId": "thread-1", "turnId": "turn-1"}]


async def test_abandoned_turn_stream_interrupts_the_turn(fake_codex: str) -> None:
    async with client_for(fake_codex, "slow_turn") as client:
        session = session_for(client)
        stream = session.turn_stream("hi")
        async for event in stream:
            assert event.method == "turn/started"
            break
        await stream.aclose()
        assert await _interrupts(client) == [{"threadId": "thread-1", "turnId": "turn-1"}]


async def test_completed_turn_is_not_interrupted(fake_codex: str) -> None:
    async with client_for(fake_codex, "") as client:
        session = session_for(client)
        async for _ in session.turn_stream("hi"):
            pass
        assert await _interrupts(client) == []


async def test_cancelled_during_leftover_delivery_forgets_and_interrupts_the_turn(
    fake_codex: str,
) -> None:
    async with client_for(fake_codex, "leftover_turn") as client:
        session = session_for(client)
        in_listener = asyncio.Event()

        async def slow_listener(event: Any) -> None:
            in_listener.set()
            await asyncio.Event().wait()

        client._event_listeners.append(slow_listener)

        async def consume() -> None:
            async for _ in session.turn_stream("hi"):
                pass

        task = asyncio.create_task(consume())
        await asyncio.wait_for(in_listener.wait(), 5)
        client._event_listeners.remove(slow_listener)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert client._turn_queues == {}
        assert await _interrupts(client) == [{"threadId": "thread-1", "turnId": "turn-1"}]


async def test_send_failing_after_close_is_a_process_error(fake_codex: str) -> None:
    async with client_for(fake_codex, "") as client:
        dispatch = client.dispatch

        async def send(message: dict[str, Any]) -> None:
            dispatch._close(TransportClosedError("gone"))
            raise BrokenPipeError

        dispatch._transport.send = send  # type: ignore[method-assign]
        with pytest.raises(CodexProcessError, match="Failed to send"):
            await dispatch.send_request("ping")
        assert dispatch._pending_requests == {}


async def test_request_cancelled_while_sending_is_forgotten(fake_codex: str) -> None:
    async with client_for(fake_codex, "") as client:
        dispatch = client.dispatch
        sending = asyncio.Event()

        async def send(message: dict[str, Any]) -> None:
            sending.set()
            await asyncio.Event().wait()

        dispatch._transport.send = send  # type: ignore[method-assign]
        task = asyncio.create_task(dispatch.send_request("ping"))
        await asyncio.wait_for(sending.wait(), 5)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert dispatch._pending_requests == {}


async def test_closed_error_wins_over_not_connected(
    fake_codex: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    async with client_for(fake_codex, "") as client:
        with pytest.raises(TransportClosedError):
            await asyncio.wait_for(client.dispatch.send_request("die"), 5)
        monkeypatch.setattr(StdioTransport, "is_connected", property(lambda _self: False))
        with pytest.raises(TransportClosedError, match="exit code 3"):
            await client.dispatch.send_request("model/list")


async def test_stderr_line_over_the_limit_does_not_stop_draining(fake_codex: str) -> None:
    async with client_for(fake_codex, "stderr_long_line") as client:
        transport = client.dispatch._transport
        assert isinstance(transport, StdioTransport)
        for _ in range(100):
            if "after" in transport._stderr_tail:
                break
            await asyncio.sleep(0.05)
        assert "after" in transport._stderr_tail
        assert await asyncio.wait_for(client.dispatch.send_request("ping"), 5)
