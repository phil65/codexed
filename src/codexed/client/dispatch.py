"""Pure JSON-RPC dispatch layer — no Codex domain knowledge."""

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

CloseHandler = Callable[[Exception], None]
"""``(error) -> None`` — called once when the read loop ends (server exit, EOF, stop)."""


class Dispatch:
    """Thin JSON-RPC transport wrapper.

    Owns the read loop, request/response correlation, and transport lifecycle.
    Notifications and server-initiated requests are forwarded to callbacks
    supplied by the caller. Notifications are handled in order, inside the read loop;
    each server request runs in its own task, so a slow approval or a handler that
    calls back into the client doesn't stall the loop.

    When the read loop ends (server exit, EOF, transport error), every pending and later
    request fails with a :class:`TransportClosedError` naming the reason.
    """

    def __init__(
        self,
        transport: Transport,
        *,
        on_notification: NotificationHandler,
        on_server_request: ServerRequestHandler,
        on_close: CloseHandler | None = None,
    ) -> None:
        self._transport = transport
        self._on_notification = on_notification
        self._on_server_request = on_server_request
        self._on_close = on_close
        self._request_id = 0
        self._pending_requests: dict[int | str, asyncio.Future[Any]] = {}
        self._reader_task: asyncio.Task[None] | None = None
        self._request_tasks: set[asyncio.Task[None]] = set()
        self._closed_error: TransportClosedError | None = None

    @property
    def closed_error(self) -> TransportClosedError | None:
        """Why the connection ended, once the read loop has stopped (else None)."""
        return self._closed_error

    async def start(self) -> None:
        """Start the transport and begin the read loop."""
        if self._transport.is_connected:
            return

        await self._transport.start()
        self._closed_error = None
        self._reader_task = asyncio.create_task(self._read_loop())

    async def stop(self) -> None:
        """Stop the transport and clean up resources."""
        if not self._transport.is_connected:
            return

        if self._reader_task:
            self._reader_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._reader_task
        for task in list(self._request_tasks):
            task.cancel()
        if self._request_tasks:
            await asyncio.gather(*self._request_tasks, return_exceptions=True)

        await self._transport.stop()
        self._close(TransportClosedError("Connection closed"))

    async def send_request(self, method: str, params: BaseModel | None = None) -> Any:
        """Send a JSON-RPC request and wait for the response."""
        if not self._transport.is_connected:
            raise TransportClosedError("Not connected to Codex app-server")
        if self._closed_error is not None:
            raise TransportClosedError(str(self._closed_error))

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

        try:
            return await future
        finally:  # also when cancelled: no response may ever come
            self._pending_requests.pop(request_id, None)

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
        reason = "app-server closed the connection"
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
            self._close(TransportClosedError("Connection closed"))
            raise
        except Exception as exc:
            logger.exception("Reader loop failed")
            reason = f"reading from the app-server failed: {exc}"
        describe = getattr(self._transport, "close_reason", None)
        if describe is not None:
            with contextlib.suppress(Exception):
                reason = f"{reason} ({await describe()})"
        logger.warning("Codex app-server connection ended: %s", reason)
        self._close(TransportClosedError(reason))

    def _close(self, error: TransportClosedError) -> None:
        """Fail pending requests and tell the owner (once per connection)."""
        if self._closed_error is not None:
            return
        self._closed_error = error
        pending = list(self._pending_requests.values())
        self._pending_requests.clear()
        for future in pending:
            if not future.done():
                future.set_exception(TransportClosedError(str(error)))
        if self._on_close is not None:
            try:
                self._on_close(error)
            except Exception:
                logger.exception("Close handler failed")

    async def _process_message(self, message: dict[str, Any]) -> None:
        match message:
            case {"method": _, "id": _}:
                coro = self._on_server_request(
                    message["method"], message["id"], message.get("params") or {}
                )
                task = asyncio.create_task(self._run_server_request(coro, message["method"]))
                self._request_tasks.add(task)
                task.add_done_callback(self._request_tasks.discard)
            case {"id": _}:
                self._handle_response(message)
            case {"method": _}:
                await self._on_notification(message["method"], message.get("params") or {})
            case _:
                raise TypeError(f"Unknown message shape {message}")

    async def _run_server_request(self, coro: Awaitable[None], method: str) -> None:
        try:
            await coro
        except Exception:
            logger.exception("Error handling server request %s", method)

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
