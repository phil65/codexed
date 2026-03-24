"""Codex app-server client."""

from __future__ import annotations

from collections.abc import AsyncIterator  # noqa: TC003
import logging
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from codexed.models import ThreadTokenUsageUpdatedData, ThreadTokenUsageUpdatedEvent


if TYPE_CHECKING:
    from codexed.client import CodexClient
    from codexed.models import (
        ApprovalPolicy,
        CodexEvent,
        CollaborationMode,
        Personality,
        ReasoningEffort,
        ReasoningSummary,
        ReviewDelivery,
        ReviewStartResponse,
        ReviewTarget,
        SandboxMode,
        ThreadReadResponse,
        ThreadResponse,
        ThreadRollbackResponse,
        ThreadTokenUsage,
        ThreadUnarchiveResponse,
        ThreadUnsubscribeResponse,
        ToolConfig,
        TurnSteerResponse,
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
        cwd: str | None = None,
        sandbox_policy: SandboxMode | dict[str, Any] | None = None,
        output_schema: dict[str, Any] | type[Any] | None = None,
        personality: Personality | None = None,
        summary: ReasoningSummary | None = None,
        collaboration_mode: CollaborationMode | None = None,
    ) -> AsyncIterator[CodexEvent]:
        """Start a turn and stream events.  See :meth:`CodexClient.turn_stream`."""
        async for event in self._client.turn_stream(
            self.thread_id,
            user_input,
            model=model,
            effort=effort,
            approval_policy=approval_policy,
            cwd=cwd,
            sandbox_policy=sandbox_policy,
            output_schema=output_schema,
            personality=personality,
            summary=summary,
            collaboration_mode=collaboration_mode,
        ):
            match event:
                case ThreadTokenUsageUpdatedEvent(
                    data=ThreadTokenUsageUpdatedData(token_usage=usage)
                ):
                    self.usage = usage
            yield event

    async def turn_steer(
        self,
        user_input: str | list[UserInput],
        *,
        expected_turn_id: str,
    ) -> TurnSteerResponse:
        """Steer a running turn.  See :meth:`CodexClient.turn_steer`."""
        return await self._client.turn_steer(
            self.thread_id,
            user_input,
            expected_turn_id=expected_turn_id,
        )

    async def turn_interrupt(self, turn_id: str) -> None:
        """Interrupt a running turn.  See :meth:`CodexClient.turn_interrupt`."""
        await self._client.turn_interrupt(self.thread_id, turn_id)

    async def turn_stream_structured[ResultType: BaseModel](
        self,
        user_input: str | list[UserInput],
        result_type: type[ResultType],
        *,
        model: str | None = None,
        effort: ReasoningEffort | None = None,
        approval_policy: ApprovalPolicy | None = None,
        cwd: str | None = None,
        sandbox_policy: SandboxMode | dict[str, Any] | None = None,
        personality: Personality | None = None,
        summary: ReasoningSummary | None = None,
        collaboration_mode: CollaborationMode | None = None,
    ) -> ResultType:
        """Structured-output turn.  See :meth:`CodexClient.turn_stream_structured`."""
        return await self._client.turn_stream_structured(
            self.thread_id,
            user_input,
            result_type,
            model=model,
            effort=effort,
            approval_policy=approval_policy,
            cwd=cwd,
            sandbox_policy=sandbox_policy,
            personality=personality,
            summary=summary,
            collaboration_mode=collaboration_mode,
        )

    # -- Thread operations ---------------------------------------------------

    async def read(self, *, include_turns: bool = False) -> ThreadReadResponse:
        """Read thread data.  See :meth:`CodexClient.thread_read`."""
        return await self._client.thread_read(self.thread_id, include_turns=include_turns)

    async def unsubscribe(self) -> ThreadUnsubscribeResponse:
        """Unsubscribe from thread events.  See :meth:`CodexClient.thread_unsubscribe`."""
        return await self._client.thread_unsubscribe(self.thread_id)

    async def archive(self) -> None:
        """Archive this thread.  See :meth:`CodexClient.thread_archive`."""
        await self._client.thread_archive(self.thread_id)

    async def unarchive(self) -> ThreadUnarchiveResponse:
        """Unarchive this thread.  See :meth:`CodexClient.thread_unarchive`."""
        return await self._client.thread_unarchive(self.thread_id)

    async def set_name(self, name: str) -> None:
        """Set thread name.  See :meth:`CodexClient.thread_set_name`."""
        await self._client.thread_set_name(self.thread_id, name)

    async def compact_start(self) -> None:
        """Trigger context compaction.  See :meth:`CodexClient.thread_compact_start`."""
        await self._client.thread_compact_start(self.thread_id)

    async def rollback(self, turns: int) -> ThreadRollbackResponse:
        """Rollback last N turns.  See :meth:`CodexClient.thread_rollback`."""
        return await self._client.thread_rollback(self.thread_id, turns)

    async def rollback_to_turn(self, turn_id: str) -> ThreadRollbackResponse:
        """Rollback to a specific turn.  See :meth:`CodexClient.thread_rollback_to_turn`."""
        return await self._client.thread_rollback_to_turn(self.thread_id, turn_id)

    # -- Review --------------------------------------------------------------

    async def review_start(
        self,
        target: ReviewTarget,
        *,
        delivery: ReviewDelivery | None = None,
    ) -> ReviewStartResponse:
        """Start a code review.  See :meth:`CodexClient.review_start`."""
        return await self._client.review_start(self.thread_id, target, delivery=delivery)

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
        sandbox: SandboxMode | None = None,
        config: dict[str, Any] | None = None,
        tools: list[ToolConfig] | None = None,
        code_mode: bool | None = None,
        personality: Personality | None = None,
        turn_id: str | None = None,
    ) -> Session:
        """Fork this thread.  See :meth:`CodexClient.thread_fork`."""
        return await self._client.thread_fork(
            self.thread_id,
            path=path,
            cwd=cwd,
            model=model,
            model_provider=model_provider,
            base_instructions=base_instructions,
            developer_instructions=developer_instructions,
            approval_policy=approval_policy,
            sandbox=sandbox,
            config=config,
            tools=tools,
            code_mode=code_mode,
            personality=personality,
            turn_id=turn_id,
        )

    def __repr__(self) -> str:
        return f"Session(thread_id={self.thread_id!r})"
