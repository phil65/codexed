"""Codex session — runtime handle for an active thread."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Mapping  # noqa: TC003
import logging
from typing import TYPE_CHECKING, Any, assert_never

from pydantic import BaseModel, TypeAdapter

from codexed.exceptions import CodexRequestError, TurnFailedError
from codexed.helpers import kebab_to_camel
from codexed.models import (
    ReviewStartParams,
    ReviewStartResponse,
    ThreadArchiveParams,
    ThreadCompactStartParams,
    ThreadReadParams,
    ThreadReadResponse,
    ThreadRollbackParams,
    ThreadRollbackResponse,
    ThreadSetNameParams,
    ThreadShellCommandParams,
    ThreadTokenUsageUpdatedData,
    ThreadTokenUsageUpdatedEvent,
    ThreadUnarchiveParams,
    ThreadUnarchiveResponse,
    ThreadUnsubscribeParams,
    ThreadUnsubscribeResponse,
    TurnCompletedData,
    TurnCompletedEvent,
    TurnErrorData,
    TurnErrorEvent,
    TurnInterruptParams,
    TurnStartParams,
    TurnStartResponse,
    TurnSteerParams,
    TurnSteerResponse,
    UserInputText,
)


if TYPE_CHECKING:
    from codexed.client import CodexClient
    from codexed.models import (
        ApprovalPolicy,
        ApprovalsReviewer,
        CodexEvent,
        CollaborationMode,
        McpServerConfig,
        Personality,
        ReasoningEffort,
        ReasoningSummary,
        ReviewDelivery,
        ReviewTarget,
        SandboxMode,
        ServiceTier,
        ThreadResponse,
        ThreadTokenUsage,
        ToolConfig,
        Turn,
        UserInput,
    )

logger = logging.getLogger(__name__)


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
        user_input: str | list[UserInput],
        *,
        model: str | None = None,
        effort: ReasoningEffort | None = None,
        approval_policy: ApprovalPolicy | None = None,
        approvals_reviewer: ApprovalsReviewer | None = None,
        cwd: str | None = None,
        sandbox_policy: SandboxMode | dict[str, Any] | None = None,
        output_schema: dict[str, Any] | type[Any] | None = None,
        personality: Personality | None = None,
        service_tier: ServiceTier | None = None,
        summary: ReasoningSummary | None = None,
        collaboration_mode: CollaborationMode | None = None,
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

        Yields:
            CodexEvent: Streaming events from the turn
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
                sandbox_dict: dict[str, Any] | None = None
            case str():
                sandbox_dict = {"type": kebab_to_camel(sandbox_policy)}
            case dict():
                sandbox_dict = sandbox_policy
            case _:
                assert_never(sandbox_policy)
        params = TurnStartParams(
            thread_id=self.thread_id,
            input=[UserInputText(text=user_input)] if isinstance(user_input, str) else user_input,
            model=model,
            effort=effort,
            approval_policy=approval_policy,
            approvals_reviewer=approvals_reviewer,
            cwd=cwd,
            sandbox_policy=sandbox_dict,
            service_tier=service_tier,
            output_schema=schema_dict,
            personality=personality,
            summary=summary,
            collaboration_mode=collaboration_mode,
        )
        turn_result = await self._client.dispatch.send_request("turn/start", params)
        response = TurnStartResponse.model_validate(turn_result)
        turn_id = response.turn.id
        turn_queue: asyncio.Queue[CodexEvent | None] = asyncio.Queue()
        turn_key = f"{self.thread_id}:{turn_id}"
        self._client._turn_queues[turn_key] = turn_queue
        try:
            while True:
                event = await turn_queue.get()
                match event:
                    case None:
                        break
                    case TurnCompletedEvent():
                        yield event
                        break
                    case TurnErrorEvent(data=TurnErrorData(error=error)):
                        yield event
                        raise TurnFailedError(error, turn_id=turn_id)
                    case _:
                        match event:
                            case ThreadTokenUsageUpdatedEvent(
                                data=ThreadTokenUsageUpdatedData(token_usage=usage)
                            ):
                                self.usage = usage
                        yield event
        finally:
            if turn_key in self._client._turn_queues:
                del self._client._turn_queues[turn_key]

    async def turn_steer(
        self,
        user_input: str | list[UserInput],
        *,
        expected_turn_id: str,
    ) -> TurnSteerResponse:
        """Steer a running turn with additional input.

        Args:
            user_input: Additional user input
            expected_turn_id: The expected active turn ID (precondition)

        Returns:
            TurnSteerResponse with the turn ID
        """
        params = TurnSteerParams(
            thread_id=self.thread_id,
            input=[UserInputText(text=user_input)] if isinstance(user_input, str) else user_input,
            expected_turn_id=expected_turn_id,
        )
        result = await self._client.dispatch.send_request("turn/steer", params)
        return TurnSteerResponse.model_validate(result)

    async def turn_interrupt(self, turn_id: str) -> None:
        """Interrupt a running turn."""
        params = TurnInterruptParams(thread_id=self.thread_id, turn_id=turn_id)
        await self._client.dispatch.send_request("turn/interrupt", params)

    async def turn_stream_structured[ResultType: BaseModel](
        self,
        user_input: str | list[UserInput],
        result_type: type[ResultType],
        *,
        model: str | None = None,
        effort: ReasoningEffort | None = None,
        approval_policy: ApprovalPolicy | None = None,
        approvals_reviewer: ApprovalsReviewer | None = None,
        cwd: str | None = None,
        sandbox_policy: SandboxMode | dict[str, Any] | None = None,
        personality: Personality | None = None,
        service_tier: ServiceTier | None = None,
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
                case TurnCompletedEvent(data=TurnCompletedData(turn=t)):
                    turn = t
                case TurnErrorEvent(data=TurnErrorData(error=error)):
                    raise TurnFailedError(error, turn_id="unknown")

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

    async def rollback(self, turns: int) -> ThreadRollbackResponse:
        """Rollback the last N turns from this thread.

        Args:
            turns: Number of turns to rollback

        Returns:
            Updated thread object with turns populated
        """
        params = ThreadRollbackParams(thread_id=self.thread_id, turns=turns)
        result = await self._client.dispatch.send_request("thread/rollback", params)
        return ThreadRollbackResponse.model_validate(result)

    async def rollback_to_turn(self, turn_id: str) -> ThreadRollbackResponse:
        """Rollback to a specific turn, keeping that turn and removing all after it.

        Args:
            turn_id: The turn ID to roll back to (this turn will be kept)

        Returns:
            Updated thread object with turns populated

        Raises:
            ValueError: If the turn_id is not found in the thread
        """
        thread_response = await self.read(include_turns=True)
        turns = thread_response.thread.turns
        turn_index = next((i for i, turn in enumerate(turns) if turn.id == turn_id), None)
        if turn_index is None:
            raise ValueError(f"Turn {turn_id!r} not found in thread {self.thread_id!r}")
        num_turns_to_drop = len(turns) - turn_index - 1
        if num_turns_to_drop < 1:
            msg = f"Turn {turn_id!r} is already the last turn in thread {self.thread_id!r}"
            raise ValueError(msg)
        return await self.rollback(num_turns_to_drop)

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
        delivery: ReviewDelivery | None = None,
    ) -> ReviewStartResponse:
        """Start a code review.

        Args:
            target: Review target (uncommittedChanges, baseBranch, commit, or custom)
            delivery: Where to run the review (inline or detached)

        Returns:
            ReviewStartResponse with turn and review thread ID
        """
        params = ReviewStartParams(thread_id=self.thread_id, target=target, delivery=delivery)
        result = await self._client.dispatch.send_request("review/start", params)
        return ReviewStartResponse.model_validate(result)

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
        approval_policy: ApprovalPolicy | None = None,
        approvals_reviewer: ApprovalsReviewer | None = None,
        sandbox: SandboxMode | None = None,
        config: dict[str, Any] | None = None,
        tools: list[ToolConfig] | None = None,
        code_mode: bool | None = None,
        service_tier: ServiceTier | None = None,
        personality: Personality | None = None,
        ephemeral: bool | None = None,
        mcp_servers: Mapping[str, McpServerConfig] | None = None,
        turn_id: str | None = None,
        persist_extended_history: bool = False,
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
            service_tier: Service tier (fast/flex)
            personality: Personality for forked thread
            ephemeral: If true, forked thread is not persisted
            mcp_servers: Per-thread MCP server configurations
            turn_id: If provided, rollback the forked thread to this turn
            persist_extended_history: Persist full history for resume/fork/read

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
            personality=personality,
            ephemeral=ephemeral,
            mcp_servers=mcp_servers,
            turn_id=turn_id,
            persist_extended_history=persist_extended_history,
        )

    def __repr__(self) -> str:
        return f"Session(thread_id={self.thread_id!r})"
