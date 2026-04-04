"""Transport abstractions for the Codex app-server protocol.

Provides a Protocol-based transport interface and concrete implementations:
- StdioTransport: Communicates via subprocess stdin/stdout (default)
- WebSocketTransport: Connects to a remote app-server via WebSocket
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

import anyenv

from codexed.exceptions import CodexProcessError, TransportClosedError


if TYPE_CHECKING:
    from collections.abc import Mapping

    from codexed.models import McpServerConfig


logger = logging.getLogger(__name__)


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
            self._process = await anyenv.create_process(
                *cmd,
                stdin="pipe",
                stdout="pipe",
                stderr="pipe",
                env={**os.environ, **self._env_vars},
            )
        except FileNotFoundError as exc:
            raise CodexProcessError(f"Codex binary not found: {self._command}") from exc
        except Exception as exc:
            raise CodexProcessError(f"Failed to start Codex app-server: {exc}") from exc

    async def stop(self) -> None:
        if self._process is None:
            return
        if self._process.returncode is None:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5.0)
            except TimeoutError:
                self._process.kill()
                await self._process.wait()
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
        line_bytes = await self._process.stdout.readline()
        if not line_bytes:
            return None
        line = line_bytes.decode().strip()
        if not line or line == "null":
            return await self.receive()
        return anyenv.load_json(line, return_type=dict)

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
        try:
            raw: str | bytes = await self._ws.recv()
        except Exception:  # noqa: BLE001
            return None
        if isinstance(raw, bytes):
            raw = raw.decode()
        raw = raw.strip()
        if not raw or raw == "null":
            return await self.receive()
        return anyenv.load_json(raw, return_type=dict)

    @property
    def is_connected(self) -> bool:
        return self._ws is not None
