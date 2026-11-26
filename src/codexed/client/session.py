"""Codex session — runtime handle for an active thread."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Mapping, Sequence  # noqa: TC003
import logging
from typing import TYPE_CHECKING, Any, assert_never

from mcp.types import CallToolResult
from pydantic import BaseModel, TypeAdapter

from codexed.client.realtime import RealtimeSession
from codexed.exceptions import CodexRequestError, TransportClosedError, TurnFailedError
from codexed.helpers import kebab_to_camel
from codexed.models import (
    DangerFullAccessSandboxPolicy,
    ErrorMessage,
    ErrorNotification,
    ExternalSandboxSandboxPolicy,
    McpResourceReadParams,
    McpResourceReadResponse,
    McpServerToolCallParams,
    McpServerToolCallResponse,
    ReadOnlySandboxPolicy,
    ReviewStartParams,
    ReviewStartResponse,
    SandboxPolicy,
    TextUserInput,
    ThreadArchiveParams,
    ThreadCompactStartParams,
    ThreadInjectItemsParams,
    ThreadMemoryModeSetParams,
    ThreadReadParams,
    ThreadReadResponse,
    ThreadRevertParams,
    ThreadRevertResponse,
    ThreadSetNameParams,
    ThreadShellCommandParams,
    ThreadTokenUsageUpdatedEvent,
    ThreadTokenUsageUpdatedNotification,
    ThreadTurnsListParams,
    ThreadTurnsListResponse,
    ThreadUnarchiveParams,
    ThreadUnarchiveResponse,
    ThreadUnsubscribeParams,
    ThreadUnsubscribeResponse,
    TurnCompletedData,
    TurnCompletedEvent,
    TurnInterruptParams,
    TurnStartParams,
    TurnStartResponse,
    TurnSteerParams,
    TurnSteerResponse,
    WarningNotification,
    WorkspaceWriteSandboxPolicy,
)
from codexed.models.mcp_server import ResourceContents
from codexed.models.v2_protocol import (
    GuardianWarningNotification,
    ThreadApproveGuardianDeniedActionParams,
)


if TYPE_CHECKING:
    from openai.types.responses import ResponseItem

    from codexed.client import CodexClient
    from codexed.models import (
        ApprovalsReviewer,
        AskForApproval,
        CodexEvent,
        CollaborationMode,
        McpServerConfig,
        Personality,
        RealtimeOutputModality,
        ReasoningEffort,
        ReasoningSummary,
        ReviewDelivery,
        ReviewTarget,
        SandboxMode,
        SortDirection,
        ThreadMemoryMode,
        ThreadResponse,
        ThreadTokenUsage,
        ToolConfig,
        Turn,
        TurnEnvironmentParams,
        UserInput,
    )

logger = logging.getLogger(__name__)

ABANDONED_TURN_INTERRUPT_TIMEOUT = 5.0
"""Seconds a cancelled or abandoned turn stream waits for its ``turn/interrupt``."""


class Session:
    """Runtime handle for an active Codex thread.

    Wraps a :class:`CodexClient` and a ``thread_id`` so that every
    thread-scoped operation can be called without passing the ID again.

    Returned by :meth:`CodexClient.thread_start`,
    :meth:`CodexClient.thread_resume`, and :meth:`CodexClient.thread_fork`.

    Example::

        session = await client.thread_start(cwd="/my/project")
        async for event in session.turn_stream("Explain this repo"):
            ...
        await session.set_name("exploration")
    """

    def __init__(self, client: CodexClient, response: ThreadResponse) -> None:
        self._client = client
        self.response = response
        self.usage: ThreadTokenUsage | None = None

    @property
    def thread_id(self) -> str:
        """The underlying thread ID."""
        return self.response.thread.id

    # -- Turn operations -----------------------------------------------------

    async def turn_stream(
        self,
        user_input: str | Sequence[UserInput],
        *,
        model: str | None = None,
        effort: ReasoningEffort | None = None,
        approval_policy: AskForApproval | None = None,
        approvals_reviewer: ApprovalsReviewer | None = None,
        cwd: str | None = None,
        sandbox_policy: SandboxMode | SandboxPolicy | None = None,
        output_schema: dict[str, Any] | type[Any] | None = None,
        personality: Personality | None = None,
        service_tier: str | None = None,
        summary: ReasoningSummary | None = None,
        collaboration_mode: CollaborationMode | None = None,
        responsesapi_client_metadata: dict[str, Any] | None = None,
        environments: list[TurnEnvironmentParams] | None = None,
        permissions: str | None = None,
    ) -> AsyncIterator[CodexEvent]:
        """Start a turn and stream events.

        Args:
            user_input: User input as string or list of input items (text/image)
            model: Optional model override for this turn
            effort: Optional reasoning effort override
            approval_policy: Optional approval policy
            approvals_reviewer: Where approval requests are routed for review
            cwd: Optional working directory override for this and subsequent turns
            sandbox_policy: Optional sandbox mode or policy dict
            output_schema: Optional JSON Schema dict or Pydantic type to constrain output
            personality: Optional personality override
            service_tier: Optional service tier (fast/flex)
            summary: Optional reasoning summary mode
            collaboration_mode: Optional collaboration mode preset (experimental)
            responsesapi_client_metadata: Optional turn-scoped Responses API client metadata.
            environments: Optional list of environment variables to set for this turn.
            permissions: Named permissions profile ID (cannot be combined with sandbox)

        Yields:
            CodexEvent: Streaming events from the turn

        Cancelling the consumer, or closing the stream before ``turn/completed``,
        interrupts the turn (``turn/interrupt``).
        """
        # Handle output_schema - convert type to JSON Schema if needed
        match output_schema:
            case None:
                schema_dict: dict[str, Any] | None = None
            case dict():
                schema_dict = output_schema
            case type():
                schema_dict = TypeAdapter(output_schema).json_schema()
            case _ as unreachable:
                assert_never(unreachable)
        # Handle sandbox_policy - convert string to dict if needed
        match sandbox_policy:
            case None:
                policy: SandboxPolicy | None = None
            case str():
                dct = {"type": kebab_to_camel(sandbox_policy)}
                policy = TypeAdapter[SandboxPolicy](SandboxPolicy).validate_python(dct)
            case (
                DangerFullAccessSandboxPolicy()
                | ReadOnlySandboxPolicy()
                | ExternalSandboxSandboxPolicy()
                | WorkspaceWriteSandboxPolicy()
            ):
                policy = sandbox_policy
            case _:
                assert_never(sandbox_policy)
        in_: list[UserInput] = (
            [TextUserInput(text=user_input)] if isinstance(user_input, str) else list(user_input)
        )
        params = TurnStartParams(
            thread_id=self.thread_id,
            input=in_,
            model=model,
            effort=effort,
            approval_policy=approval_policy,
            approvals_reviewer=approvals_reviewer,
            cwd=cwd,
            sandbox_policy=policy,
            service_tier=service_tier,
            output_schema=schema_dict,
            personality=personality,
            summary=summary,
            collaboration_mode=collaboration_mode,
            responsesapi_client_metadata=responsesapi_client_metadata,
            environments=environments,
            permissions=permissions,
        )
        turn_queue: asyncio.Queue[CodexEvent | None] = asyncio.Queue()
        turn_key: str | None = None
        self._client._begin_turn_start()
        try:
            turn_result = await self._client.dispatch.send_request("turn/start", params)
            response = TurnStartResponse.model_validate(turn_result)
            turn_id = response.turn.id
            turn_key = f"{self.thread_id}:{turn_id}"
        finally:
            await self._client._end_turn_start(turn_key, turn_queue)
        finished = False  # The turn ended (or the connection did): nothing to interrupt
        try:
            while True:
                event = await turn_queue.get()
                match event:
                    case None:
                        finished = True
                        raise self._connection_closed()
                    case TurnCompletedEvent():
                        finished = True
                        yield event
                        break
                    case ErrorMessage(params=ErrorNotification(error=error)):
                        finished = True
                        yield event
                        raise TurnFailedError(error.message, turn_id=turn_id)
                    case ThreadTokenUsageUpdatedEvent(
                        params=ThreadTokenUsageUpdatedNotification(token_usage=usage)
                    ):
                        self.usage = usage
                        yield event
                    case _:
                        yield event
        finally:
            self._client._turn_queues.pop(turn_key, None)
            if not finished:  # Cancelled, or the caller stopped iterating
                await self._interrupt_abandoned_turn(self.thread_id, turn_id)

    async def turn_steer(
        self,
        user_input: str | Sequence[UserInput],
        *,
        expected_turn_id: str,
        responsesapi_client_metadata: dict[str, Any] | None = None,
    ) -> TurnSteerResponse:
        """Steer a running turn with additional input.

        Args:
            user_input: Additional user input
            expected_turn_id: The expected active turn ID (precondition)
            responsesapi_client_metadata: Optional turn-scoped Responses API client metadata.

        Returns:
            TurnSteerResponse with the turn ID
        """
        params = TurnSteerParams(
            thread_id=self.thread_id,
            input=[TextUserInput(text=user_input)]  # pyright: ignore[reportCallIssue, reportArgumentType]
            if isinstance(user_input, str)
            else list(user_input),
            expected_turn_id=expected_turn_id,
            responsesapi_client_metadata=responsesapi_client_metadata,
        )
        result = await self._client.dispatch.send_request("turn/steer", params)
        return TurnSteerResponse.model_validate(result)

    async def turn_interrupt(self, turn_id: str) -> None:
        """Interrupt a running turn."""
        params = TurnInterruptParams(thread_id=self.thread_id, turn_id=turn_id)
        await self._client.dispatch.send_request("turn/interrupt", params)

    async def _interrupt_abandoned_turn(self, thread_id: str, turn_id: str) -> None:
        """Stop a turn whose stream was cancelled or closed early (best effort, bounded)."""
        params = TurnInterruptParams(thread_id=thread_id, turn_id=turn_id)
        try:
            async with asyncio.timeout(ABANDONED_TURN_INTERRUPT_TIMEOUT):
                await self._client.dispatch.send_request("turn/interrupt", params)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Interrupting abandoned turn %s failed: %s", turn_id, exc)

    async def turn_stream_structured[ResultType: BaseModel](
        self,
        user_input: str | list[UserInput],
        result_type: type[ResultType],
        *,
        model: str | None = None,
        effort: ReasoningEffort | None = None,
        approval_policy: AskForApproval | None = None,
        approvals_reviewer: ApprovalsReviewer | None = None,
        cwd: str | None = None,
        sandbox_policy: SandboxMode | SandboxPolicy | None = None,
        personality: Personality | None = None,
        service_tier: str | None = None,
        summary: ReasoningSummary | None = None,
        collaboration_mode: CollaborationMode | None = None,
    ) -> ResultType:
        """Start a turn with structured output and return the parsed result.

        Args:
            user_input: User input as string or list of items
            result_type: Pydantic model class for the expected result
            model: Optional model override for this turn
            effort: Optional reasoning effort override
            approval_policy: Optional approval policy
            approvals_reviewer: Where approval requests are routed for review
            cwd: Optional working directory override
            sandbox_policy: Optional sandbox mode or policy dict
            personality: Optional personality override
            service_tier: Optional service tier (fast/flex)
            summary: Optional reasoning summary mode
            collaboration_mode: Optional collaboration mode preset (experimental)

        Returns:
            Parsed Pydantic model instance of type result_type
        """
        turn: Turn | None = None
        async for event in self.turn_stream(
            user_input,
            model=model,
            effort=effort,
            approval_policy=approval_policy,
            approvals_reviewer=approvals_reviewer,
            cwd=cwd,
            sandbox_policy=sandbox_policy,
            output_schema=result_type,
            personality=personality,
            service_tier=service_tier,
            summary=summary,
            collaboration_mode=collaboration_mode,
        ):
            match event:
                case TurnCompletedEvent(params=TurnCompletedData(turn=t)):
                    turn = t
                case ErrorMessage(params=ErrorNotification(error=error)):
                    raise TurnFailedError(error.message, turn_id="unknown")

        if turn is None:
            raise CodexRequestError(code=-1, message="Turn completed without a TurnCompletedEvent")
        response_text = turn.final_response
        if response_text is None:
            raise CodexRequestError(code=-1, message="Turn completed without a final response")
        return result_type.model_validate_json(response_text)

    # -- Thread operations ---------------------------------------------------

    async def read(self, *, include_turns: bool = False) -> ThreadReadResponse:
        """Read thread data."""
        params = ThreadReadParams(thread_id=self.thread_id, include_turns=include_turns)
        result = await self._client.dispatch.send_request("thread/read", params)
        return ThreadReadResponse.model_validate(result)

    async def unsubscribe(self) -> ThreadUnsubscribeResponse:
        """Stop listening to this thread's events."""
        params = ThreadUnsubscribeParams(thread_id=self.thread_id)
        result = await self._client.dispatch.send_request("thread/unsubscribe", params)
        return ThreadUnsubscribeResponse.model_validate(result)

    async def archive(self) -> None:
        """Archive this thread."""
        params = ThreadArchiveParams(thread_id=self.thread_id)
        await self._client.dispatch.send_request("thread/archive", params)
        self._client._active_threads.discard(self.thread_id)

    async def unarchive(self) -> ThreadUnarchiveResponse:
        """Unarchive this thread."""
        params = ThreadUnarchiveParams(thread_id=self.thread_id)
        result = await self._client.dispatch.send_request("thread/unarchive", params)
        return ThreadUnarchiveResponse.model_validate(result)

    async def set_name(self, name: str) -> None:
        """Set a user-facing name for this thread."""
        params = ThreadSetNameParams(thread_id=self.thread_id, name=name)
        await self._client.dispatch.send_request("thread/name/set", params)

    async def compact_start(self) -> None:
        """Trigger context compaction for this thread."""
        params = ThreadCompactStartParams(thread_id=self.thread_id)
        await self._client.dispatch.send_request("thread/compact/start", params)

    def realtime(
        self,
        output_modality: RealtimeOutputModality,
        prompt: str | None = None,
        *,
        realtime_session_id: str | None = None,
    ) -> RealtimeSession:
        """Open a realtime voice session on this thread.

        Returns an async context manager that sends ``thread/realtime/start``
        on enter and ``thread/realtime/stop`` on exit.  Iterate over the
        returned object to receive realtime events.

        Example::

            async with session.realtime(prompt="You are helpful") as rt:
                await rt.send_text("hello")
                async for event in rt:
                    ...
        """
        return RealtimeSession(
            self._client,
            self.thread_id,
            output_modality=output_modality,
            prompt=prompt,
            realtime_session_id=realtime_session_id,
        )

    async def list_turns(
        self,
        cursor: str | None = None,
        limit: int | None = None,
        sort_direction: SortDirection | None = None,
    ) -> ThreadTurnsListResponse:
        """List all turns in this thread."""
        params = ThreadTurnsListParams(
            cursor=cursor,
            limit=limit,
            sort_direction=sort_direction,
            thread_id=self.thread_id,
        )
        result = await self._client.dispatch.send_request("thread/turns/list", params)
        return ThreadTurnsListResponse.model_validate(result)

    async def revert(self, before_turn_id: str) -> ThreadRevertResponse:
        """Replace the thread's persisted history with the turns before `before_turn_id`.

        The given turn and all later turns are dropped. Only conversation history
        changes; local file changes are not reverted.

        Args:
            before_turn_id: First turn to drop (it and every later turn are removed)

        Returns:
            Updated thread metadata and cursors for re-hydrating the retained history
        """
        params = ThreadRevertParams(thread_id=self.thread_id, before_turn_id=before_turn_id)
        result = await self._client.dispatch.send_request("thread/revert", params)
        return ThreadRevertResponse.model_validate(result)

    async def shell_command(self, command: str) -> None:
        """Run a user-initiated shell command against this thread.

        Executes the command unsandboxed, as if the user typed ``!command``
        in the Codex CLI.

        Args:
            command: Shell command to execute.
        """
        params = ThreadShellCommandParams(thread_id=self.thread_id, command=command)
        await self._client.dispatch.send_request("thread/shellCommand", params)

    # -- Review --------------------------------------------------------------

    async def review_start(
        self,
        target: ReviewTarget,
        *,
        delivery: ReviewDelivery = "inline",
    ) -> ReviewStartResponse:
        """Start a code review.

        Inline delivery runs the review on the same thread, so review items
        appear in the existing thread history.  Detached delivery creates a new
        thread for the review, keeping the original thread's history clean.

        Args:
            target: Review target (uncommittedChanges, baseBranch, commit, or custom)
            delivery: Where to run the review (inline or detached)

        Returns:
            ReviewStartResponse with turn and review thread ID
        """
        params = ReviewStartParams(thread_id=self.thread_id, target=target, delivery=delivery)
        result = await self._client.dispatch.send_request("review/start", params)
        return ReviewStartResponse.model_validate(result)

    async def review_stream(
        self,
        target: ReviewTarget,
        *,
        delivery: ReviewDelivery = "inline",
    ) -> AsyncIterator[CodexEvent]:
        """Start a code review and stream events.

        Inline delivery runs the review on the same thread, so review items
        appear in the existing thread history.  Detached delivery creates a new
        thread for the review, keeping the original thread's history clean.

        Args:
            target: Review target (uncommittedChanges, baseBranch, commit, or custom)
            delivery: Where to run the review (inline or detached)

        Yields:
            CodexEvent: Streaming events from the review turn

        Cancelling the consumer, or closing the stream before the turn completes,
        interrupts the review turn.
        """
        params = ReviewStartParams(thread_id=self.thread_id, target=target, delivery=delivery)
        turn_queue: asyncio.Queue[CodexEvent | None] = asyncio.Queue()
        turn_key: str | None = None
        self._client._begin_turn_start()
        try:
            result = await self._client.dispatch.send_request("review/start", params)
            response = ReviewStartResponse.model_validate(result)
            turn_id = response.turn.id
            review_thread_id = response.review_thread_id
            turn_key = f"{review_thread_id}:{turn_id}"
        finally:
            await self._client._end_turn_start(turn_key, turn_queue)
        finished = False  # The turn ended (or the connection did): nothing to interrupt
        try:
            while True:
                event = await turn_queue.get()
                match event:
                    case None:
                        finished = True
                        raise self._connection_closed()
                    case TurnCompletedEvent():
                        finished = True
                        yield event
                        break
                    case ErrorMessage(params=ErrorNotification(error=error)):
                        finished = True
                        yield event
                        raise TurnFailedError(error.message, turn_id=turn_id)
                    case _:
                        yield event
        finally:
            self._client._turn_queues.pop(turn_key, None)
            if not finished:  # Cancelled, or the caller stopped iterating
                await self._interrupt_abandoned_turn(review_thread_id, turn_id)

    # -- Fork ----------------------------------------------------------------

    async def fork(
        self,
        *,
        path: str | None = None,
        cwd: str | None = None,
        model: str | None = None,
        model_provider: str | None = None,
        base_instructions: str | None = None,
        developer_instructions: str | None = None,
        approval_policy: AskForApproval | None = None,
        approvals_reviewer: ApprovalsReviewer | None = None,
        sandbox: SandboxMode | None = None,
        config: dict[str, Any] | None = None,
        tools: list[ToolConfig] | None = None,
        code_mode: bool | None = None,
        service_tier: str | None = None,
        ephemeral: bool | None = None,
        mcp_servers: Mapping[str, McpServerConfig] | None = None,
        last_turn_id: str | None = None,
        before_turn_id: str | None = None,
        exclude_turns: bool | None = None,
        permissions: str | None = None,
    ) -> Session:
        """Fork this thread into a new thread with copied history.

        Args:
            path: Path to thread storage
            cwd: Working directory for the forked thread
            model: Model override for forked thread
            model_provider: Model provider override
            base_instructions: Base system instructions for forked thread
            developer_instructions: Developer instructions for forked thread
            approval_policy: Tool approval policy for forked thread
            approvals_reviewer: Where approval requests are routed for review
            sandbox: Sandbox mode for forked thread
            config: Additional configuration overrides
            tools: Builtin tool configurations for forked thread
            code_mode: Enable experimental code mode feature flag
            service_tier: Service tier
            ephemeral: If true, forked thread is not persisted
            mcp_servers: Per-thread MCP server configurations
            last_turn_id: Fork through this turn (inclusive), omitting later turns
            before_turn_id: Fork before this turn, excluding it and all later turns
            exclude_turns: When true, return only thread metadata and live fork state
                            without populating `thread.turns`. This is useful when
                            the client plans to call `thread/turns/list` immediately after forking.
            permissions: Named permissions profile ID (cannot be combined with sandbox)

        Returns:
            Session wrapping the new forked thread
        """
        return await self._client.thread_fork(
            self.thread_id,
            path=path,
            cwd=cwd,
            model=model,
            model_provider=model_provider,
            base_instructions=base_instructions,
            developer_instructions=developer_instructions,
            approval_policy=approval_policy,
            approvals_reviewer=approvals_reviewer,
            sandbox=sandbox,
            config=config,
            tools=tools,
            code_mode=code_mode,
            service_tier=service_tier,
            ephemeral=ephemeral,
            mcp_servers=mcp_servers,
            last_turn_id=last_turn_id,
            before_turn_id=before_turn_id,
            exclude_turns=exclude_turns,
            permissions=permissions,
        )

    async def read_resource(self, server: str, uri: str) -> list[ResourceContents]:
        """Read a resource from the MCP server."""
        params = McpResourceReadParams(server=server, thread_id=self.thread_id, uri=uri)
        result = await self._client.dispatch.send_request("mcpServer/resource/read", params)
        data = McpResourceReadResponse.model_validate(result)
        ta = TypeAdapter[ResourceContents](ResourceContents)

        def convert(old: BaseModel) -> ResourceContents:
            dct = old.model_dump()
            dct["_meta"] = dct.pop("field_meta")
            return ta.validate_python(dct)

        return [convert(i) for i in data.contents]

    async def tool_call(
        self,
        server: str,
        tool: str,
        arguments: Any | None = None,
        meta: dict[str, Any] | None = None,
    ) -> CallToolResult:
        """Call a tool on the MCP server."""
        params = McpServerToolCallParams(
            server=server,
            thread_id=self.thread_id,
            tool=tool,
            arguments=arguments,
            field_meta=meta,
        )
        result = await self._client.dispatch.send_request("mcpServer/tool/call", params)
        data = McpServerToolCallResponse.model_validate(result)
        return CallToolResult(
            structured_content=data.structured_content,
            is_error=bool(data.is_error),
            content=data.content,
            meta=data.field_meta,
        )

    def _connection_closed(self) -> TransportClosedError:
        """The error for a stream whose connection ended before the turn completed."""
        reason = self._client.dispatch.closed_error or "connection closed"
        return TransportClosedError(f"Codex app-server connection ended mid-turn: {reason}")

    def __repr__(self) -> str:
        return f"Session(thread_id={self.thread_id!r})"

    async def inject_items(self, items: list[ResponseItem]) -> None:
        """Inject raw responses-API Items into the thread's model-visible history."""
        params = ThreadInjectItemsParams(items=items, thread_id=self.thread_id)
        await self._client.dispatch.send_request("thread/inject_items", params)

    async def set_memory_mode(self, mode: ThreadMemoryMode) -> None:
        """Set the thread's memory mode."""
        params = ThreadMemoryModeSetParams(mode=mode, thread_id=self.thread_id)
        await self._client.dispatch.send_request("thread/memoryMode/set", params)

    async def warning(self, message: str) -> None:
        """Send a thread-related warning message to the app-server."""
        params = WarningNotification(message=message, thread_id=self.thread_id)
        await self._client.dispatch.send_request("warning", params)

    async def guardian_warning(self, message: str) -> None:
        """Send a thread-related guardian warning message to the app-server."""
        params = GuardianWarningNotification(message=message, thread_id=self.thread_id)
        await self._client.dispatch.send_request("warning", params)

    async def approve_guardian_denied_action(self, event: Any) -> None:
        """Send a request to the server to approve a guardian denied action."""
        params = ThreadApproveGuardianDeniedActionParams(event=event, thread_id=self.thread_id)
        await self._client.dispatch.send_request("thread/approveGuardianDeniedAction", params)
