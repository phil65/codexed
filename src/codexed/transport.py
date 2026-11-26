"""Transport abstractions for the Codex app-server protocol.

Provides a Protocol-based transport interface and concrete implementations:
- StdioTransport: Communicates via subprocess stdin/stdout (default)
- WebSocketTransport: Connects to a remote app-server via WebSocket
"""

import asyncio
from collections import deque
import contextlib
import logging
import os
import signal
import sys
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

import anyenv

from codexed.exceptions import CodexProcessError, TransportClosedError


if TYPE_CHECKING:
    from collections.abc import Mapping

    from codexed.models import McpServerConfig


logger = logging.getLogger(__name__)


STDOUT_LINE_LIMIT = 10 * 1024 * 1024
"""Longest JSON line read from the server's stdout."""
STDERR_TAIL_LINES = 50
"""Last stderr lines kept for the error when the server exits."""


def _parse_line(line: str) -> dict[str, Any] | None:
    """Parse one JSON-RPC message; None for blank or invalid lines (logged and skipped)."""
    line = line.strip()
    if not line or line == "null":
        return None
    try:
        message = anyenv.load_json(line)
    except Exception:  # noqa: BLE001
        logger.warning("Skipping non-JSON line from the app-server: %.200s", line)
        return None
    if not isinstance(message, dict):
        logger.warning("Skipping non-object JSON from the app-server: %.200s", line)
        return None
    return message


@runtime_checkable
class Transport(Protocol):
    """Abstract transport for bidirectional JSON message exchange."""

    async def start(self) -> None:
        """Open the transport connection."""
        ...

    async def stop(self) -> None:
        """Close the transport connection and release resources."""
        ...

    async def send(self, message: dict[str, Any]) -> None:
        """Send a JSON message over the transport."""
        ...

    async def receive(self) -> dict[str, Any] | None:
        """Receive the next JSON message, or None if the transport is closed."""
        ...

    @property
    def is_connected(self) -> bool:
        """Whether the transport is currently connected."""
        ...


class StdioTransport:
    """Transport that communicates with a Codex app-server subprocess via stdin/stdout."""

    def __init__(
        self,
        command: str,
        profile: str | None = None,
        env_vars: dict[str, str] | None = None,
        mcp_servers: Mapping[str, McpServerConfig] | None = None,
    ) -> None:
        self._command = command
        self._profile = profile
        self._mcp_servers = dict(mcp_servers) if mcp_servers else {}
        self._env_vars = env_vars or {}
        self._process: asyncio.subprocess.Process | None = None
        self._writer_lock = asyncio.Lock()
        self._stderr_task: asyncio.Task[None] | None = None
        self._stderr_tail: deque[str] = deque(maxlen=STDERR_TAIL_LINES)

    async def start(self) -> None:
        if self._process is not None:
            return

        cmd = [self._command, "app-server"]
        if self._profile:
            cmd.extend(["--profile", self._profile])
        for server_name, server_config in self._mcp_servers.items():
            config_str = server_config.to_config_toml(server_name)
            cmd.extend(["--config", config_str])

        logger.info("Starting Codex app-server: %s", " ".join(cmd))
        try:
            self._process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                limit=STDOUT_LINE_LIMIT,
                env={**os.environ, **self._env_vars},
                # Own process group: stop() also ends wrapper children and MCP servers.
                start_new_session=sys.platform != "win32",
            )
        except FileNotFoundError as exc:
            raise CodexProcessError(f"Codex binary not found: {self._command}") from exc
        except Exception as exc:
            raise CodexProcessError(f"Failed to start Codex app-server: {exc}") from exc
        self._stderr_tail.clear()
        self._stderr_task = asyncio.create_task(self._drain_stderr(self._process))

    async def _drain_stderr(self, process: asyncio.subprocess.Process) -> None:
        """Read stderr continuously: an unread pipe fills up and blocks the server."""
        assert process.stderr is not None
        while line_bytes := await process.stderr.readline():
            line = line_bytes.decode(errors="replace").rstrip()
            self._stderr_tail.append(line)
            logger.debug("codex stderr: %s", line)

    async def close_reason(self) -> str:
        """Describe why the server's stdout closed: exit code and the last stderr lines."""
        process = self._process
        if process is None:
            return "transport stopped"
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(process.wait(), timeout=2.0)
        if self._stderr_task is not None:
            with contextlib.suppress(TimeoutError, Exception):
                await asyncio.wait_for(asyncio.shield(self._stderr_task), timeout=0.5)
        code = process.returncode
        reason = "still running" if code is None else f"exit code {code}"
        if self._stderr_tail:
            reason += "; stderr:\n" + "\n".join(self._stderr_tail)
        return reason

    def _signal_group(self, process: asyncio.subprocess.Process, sig: int) -> None:
        if sys.platform == "win32":
            if sig == signal.SIGTERM:
                process.terminate()
            else:
                process.kill()
            return
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(process.pid, sig)

    async def stop(self) -> None:
        process = self._process
        if process is None:
            return
        # Closing stdin is the graceful shutdown for a stdio server.
        if process.stdin is not None and not process.stdin.is_closing():
            process.stdin.close()
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(process.wait(), timeout=2.0)
        # Also when the server exited: its children (MCP servers, tools) may still run.
        self._signal_group(process, signal.SIGTERM)
        try:
            await asyncio.wait_for(process.wait(), timeout=5.0)
        except TimeoutError:
            self._signal_group(process, getattr(signal, "SIGKILL", signal.SIGTERM))
            await process.wait()
        if self._stderr_task is not None:
            self._stderr_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._stderr_task
            self._stderr_task = None
        self._process = None

    async def send(self, message: dict[str, Any]) -> None:
        if self._process is None or self._process.stdin is None:
            raise TransportClosedError("Not connected to Codex app-server")
        async with self._writer_lock:
            line = anyenv.dump_json(message) + "\n"
            self._process.stdin.write(line.encode())
            await self._process.stdin.drain()

    async def receive(self) -> dict[str, Any] | None:
        if self._process is None or self._process.stdout is None:
            return None
        while True:
            line_bytes = await self._process.stdout.readline()
            if not line_bytes:
                return None
            # A stray warning line or byte must not end the connection: skip it.
            if (message := _parse_line(line_bytes.decode(errors="replace"))) is not None:
                return message

    @property
    def is_connected(self) -> bool:
        return self._process is not None


class WebSocketTransport:
    """Transport that connects to a remote Codex app-server via WebSocket.

    Requires the ``websockets`` package (``pip install codexed[websocket]``).
    """

    def __init__(
        self,
        url: str,
        *,
        auth_token: str | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self._url = url
        self._auth_token = auth_token
        self._extra_headers = extra_headers or {}
        self._ws: Any = None
        self._writer_lock = asyncio.Lock()

    async def start(self) -> None:
        import websockets

        if self._ws is not None:
            return
        headers = dict(self._extra_headers)
        if self._auth_token:
            headers["Authorization"] = f"Bearer {self._auth_token}"

        self._ws = await websockets.connect(self._url, additional_headers=headers)

    async def stop(self) -> None:
        if self._ws is None:
            return
        with contextlib.suppress(Exception):
            await self._ws.close()
        self._ws = None

    async def send(self, message: dict[str, Any]) -> None:
        if self._ws is None:
            raise TransportClosedError("WebSocket not connected")
        async with self._writer_lock:
            await self._ws.send(anyenv.dump_json(message))

    async def receive(self) -> dict[str, Any] | None:
        if self._ws is None:
            return None
        while True:
            try:
                raw: str | bytes = await self._ws.recv()
            except Exception as exc:  # noqa: BLE001
                logger.debug("WebSocket closed: %s", exc)
                return None
            if isinstance(raw, bytes):
                raw = raw.decode(errors="replace")
            if (message := _parse_line(raw)) is not None:
                return message

    @property
    def is_connected(self) -> bool:
        return self._ws is not None
