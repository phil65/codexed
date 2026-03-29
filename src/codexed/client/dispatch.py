"""Pure JSON-RPC dispatch layer — no Codex domain knowledge."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
import contextlib
import logging
from typing import TYPE_CHECKING, Any

from codexed.exceptions import CodexProcessError, TransportClosedError, map_jsonrpc_error
from codexed.models import JsonRpcRequest, JsonRpcResponse


if TYPE_CHECKING:
    from pydantic import BaseModel

    from codexed.transport import Transport

logger = logging.getLogger(__name__)

NotificationHandler = Callable[[str, dict[str, Any]], Awaitable[None]]
"""``(method, params) -> None`` — called for every JSON-RPC notification."""

ServerRequestHandler = Callable[[str, int | str, dict[str, Any]], Awaitable[None]]
"""``(method, request_id, params) -> None`` — called for every server request."""


class Dispatch:
    """Thin JSON-RPC transport wrapper.

    Owns the read loop, request/response correlation, and transport lifecycle.
    Notifications and server-initiated requests are forwarded to callbacks
    supplied by the caller.
    """

    def __init__(
        self,
        transport: Transport,
        *,
        on_notification: NotificationHandler,
        on_server_request: ServerRequestHandler,
    ) -> None:
        self._transport = transport
        self._on_notification = on_notification
        self._on_server_request = on_server_request
        self._request_id = 0
        self._pending_requests: dict[int | str, asyncio.Future[Any]] = {}
        self._reader_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Start the transport and begin the read loop."""
        if self._transport.is_connected:
            return

        await self._transport.start()
        self._reader_task = asyncio.create_task(self._read_loop())

    async def stop(self) -> None:
        """Stop the transport and clean up resources."""
        if not self._transport.is_connected:
            return

        if self._reader_task:
            self._reader_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._reader_task

        await self._transport.stop()
        for future in self._pending_requests.values():
            if not future.done():
                future.set_exception(TransportClosedError("Connection closed"))
        self._pending_requests.clear()

    async def send_request(self, method: str, params: BaseModel | None = None) -> Any:
        """Send a JSON-RPC request and wait for the response."""
        if not self._transport.is_connected:
            raise TransportClosedError("Not connected to Codex app-server")

        request_id = self._request_id
        self._request_id += 1
        future: asyncio.Future[Any] = asyncio.Future()
        self._pending_requests[request_id] = future
        params_dict = params.model_dump(by_alias=True, exclude_none=True) if params else {}
        request = JsonRpcRequest(id=request_id, method=method, params=params_dict)
        try:
            message = request.model_dump(mode="json", by_alias=True, exclude_none=True)
            await self._transport.send(message)
        except Exception as exc:
            del self._pending_requests[request_id]
            raise CodexProcessError(f"Failed to send request: {exc}") from exc

        return await future

    async def send_response(self, request_id: int | str, result: dict[str, Any]) -> None:
        """Send a JSON-RPC success response to a server request."""
        await self._transport.send({"jsonrpc": "2.0", "id": request_id, "result": result})

    async def send_error(self, request_id: int | str, code: int, message: str) -> None:
        """Send a JSON-RPC error response to a server request."""
        error = {"code": code, "message": message}
        await self._transport.send({"jsonrpc": "2.0", "id": request_id, "error": error})

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _read_loop(self) -> None:
        try:
            while True:
                message = await self._transport.receive()
                if message is None:
                    break
                try:
                    await self._process_message(message)
                except Exception:
                    logger.exception("Error processing message")
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Reader loop failed")

    async def _process_message(self, message: dict[str, Any]) -> None:
        match message:
            case {"method": _, "id": _}:
                await self._on_server_request(
                    message["method"], message["id"], message.get("params") or {}
                )
            case {"id": _}:
                self._handle_response(message)
            case {"method": _}:
                await self._on_notification(message["method"], message.get("params") or {})
            case _:
                raise TypeError(f"Unknown message shape {message}")

    def _handle_response(self, message: dict[str, Any]) -> None:
        msg_id = message["id"]
        try:
            response = JsonRpcResponse.model_validate(message)
            future = self._pending_requests.pop(response.id, None)
            if future and not future.done():
                if err := response.error:
                    future.set_exception(map_jsonrpc_error(err.code, err.message, err.data))
                else:
                    future.set_result(response.result)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to parse response: %s", exc)
            if isinstance(msg_id, int):
                future = self._pending_requests.pop(msg_id, None)
                if future and not future.done():
                    future.set_result(message.get("result"))
