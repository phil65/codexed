"""Codex app-server client."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Mapping  # noqa: TC003
import contextlib
import logging
from typing import TYPE_CHECKING, Any, assert_never

from pydantic import BaseModel, TypeAdapter

from codexed.client.fs import CodexFS
from codexed.exceptions import (
    CodexProcessError,
    CodexRequestError,
    TransportClosedError,
    TurnFailedError,
    map_jsonrpc_error,
)
from codexed.helpers import kebab_to_camel, merge_config
from codexed.models import (
    AppsListParams,
    AppsListResponse,
    CancelLoginAccountParams,
    CancelLoginAccountResponse,
    CollaborationModeListResponse,
    CommandExecParams,
    CommandExecResponse,
    ConfigBatchWriteParams,
    ConfigReadParams,
    ConfigReadResponse,
    ConfigRequirementsReadResponse,
    ConfigValueWriteParams,
    ConfigWriteResponse,
    ExperimentalFeatureListParams,
    ExperimentalFeatureListResponse,
    ExternalAgentConfigDetectParams,
    ExternalAgentConfigDetectResponse,
    ExternalAgentConfigImportParams,
    FeedbackUploadParams,
    FeedbackUploadResponse,
    GetAccountParams,
    GetAccountRateLimitsResponse,
    GetAccountResponse,
    InitializeParams,
    JsonRpcRequest,
    JsonRpcResponse,
    ListMcpServerStatusParams,
    ListMcpServerStatusResponse,
    LoginAccountParams,
    LoginAccountResponse,
    McpServerOauthLoginParams,
    McpServerOauthLoginResponse,
    ModelListParams,
    ModelListResponse,
    ReviewStartParams,
    ReviewStartResponse,
    SkillsConfigWriteParams,
    SkillsListParams,
    SkillsListResponse,
    SkillsRemoteExportParams,
    SkillsRemoteExportResponse,
    SkillsRemoteListParams,
    SkillsRemoteListResponse,
    ThreadArchiveParams,
    ThreadCompactStartParams,
    ThreadForkParams,
    ThreadListParams,
    ThreadListResponse,
    ThreadLoadedListResponse,
    ThreadReadParams,
    ThreadReadResponse,
    ThreadResponse,
    ThreadResumeParams,
    ThreadRollbackParams,
    ThreadRollbackResponse,
    ThreadSetNameParams,
    ThreadShellCommandParams,
    ThreadStartParams,
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
    codex_event_adapter,
)
from codexed.request_handlers import (
    SERVER_REQUEST_COMMAND_APPROVAL,
    SERVER_REQUEST_DYNAMIC_TOOL_CALL,
    SERVER_REQUEST_FILE_CHANGE_APPROVAL,
    SERVER_REQUEST_MCP_ELICITATION,
    SERVER_REQUEST_SKILL_APPROVAL,
    SERVER_REQUEST_TYPES,
    SERVER_REQUEST_USER_INPUT,
    create_auto_approve_dict,
)
from codexed.transport import StdioTransport


if TYPE_CHECKING:
    from typing import Self

    from codexed.models import (
        AppInfo,
        ApprovalPolicy,
        CodexEvent,
        CollaborationMode,
        CollaborationModeMask,
        ConfigEdit,
        ExperimentalFeature,
        ExternalAgentConfigMigrationItem,
        McpServerConfig,
        MergeStrategy,
        ModelData,
        Personality,
        ReasoningEffort,
        ReasoningSummary,
        RemoteSkillSummary,
        ReviewDelivery,
        ReviewTarget,
        SandboxMode,
        SkillData,
        ThreadSortKey,
        ThreadSourceKind,
        ToolConfig,
        Turn,
        UserInput,
    )
    from codexed.models.request_params import HazelnutScope, LoginType, ProductSurface
    from codexed.request_handlers import (
        ApprovalHandler,
        DynamicToolCallHandler,
        HandlerMethod,
        McpElicitationHandler,
        ServerRequestHandler,
        UserInputHandler,
    )
    from codexed.session import Session
    from codexed.transport import Transport

logger = logging.getLogger(__name__)


class CodexClient:
    """Client for the Codex app-server JSON-RPC protocol.

    Manages the subprocess lifecycle and provides async methods for:
    - Thread management (conversations)
    - Turn management (message exchanges)
    - Event streaming via notifications
    """

    def __init__(
        self,
        codex_command: str = "codex",
        profile: str | None = None,
        env_vars: dict[str, str] | None = None,
        mcp_servers: Mapping[str, McpServerConfig] | None = None,
        on_approval: ApprovalHandler | None = None,
        on_user_input: UserInputHandler | None = None,
        on_dynamic_tool_call: DynamicToolCallHandler | None = None,
        on_mcp_elicitation: McpElicitationHandler | None = None,
        mcp_elicitation_for_approvals: bool = False,
        transport: Transport | None = None,
    ) -> None:
        """Initialize the Codex app-server client.

        Args:
            codex_command: Path to the codex binary (default: "codex")
            profile: Optional Codex profile to use
            env_vars: Optional environment variables to set for the Codex process.
            mcp_servers: Optional MCP servers to inject programmatically.
                Keys are server names, values are server configurations.
            on_approval: Handler for all approval requests
                (command execution, file change, and skill approval).
            on_user_input: Handler for tool user input requests.
            on_dynamic_tool_call: Handler for dynamic tool call requests.
            on_mcp_elicitation: Handler for MCP elicitation requests.
            mcp_elicitation_for_approvals: If True, enables the Codex
                ``tool_call_mcp_elicitation`` feature flag which routes MCP tool
                approval prompts through ``mcpServer/elicitation/request`` instead
                of ``item/tool/requestUserInput``.  Requires *on_mcp_elicitation*
                to handle approvals (the schema is empty; context is in ``_meta``).
                Default is False because the default elicitation handler auto-declines,
                which would break MCP tool approvals.
            transport: Pre-configured transport instance. If provided,
                ``codex_command``, ``profile``, ``env_vars``, and ``mcp_servers``
                are ignored (they are only used to build the default
                ``StdioTransport``).  Pass a ``WebSocketTransport`` here to
                connect to a remote app-server.
        """
        if transport is not None:
            self._transport = transport
        else:
            self._transport = StdioTransport(
                command=codex_command,
                profile=profile,
                env_vars=env_vars,
                mcp_servers=mcp_servers,
            )
        self._request_id = 0
        self._pending_requests: dict[int, asyncio.Future[Any]] = {}
        self._event_queue: asyncio.Queue[CodexEvent | None] = asyncio.Queue()
        self._turn_queues: dict[str, asyncio.Queue[CodexEvent | None]] = {}
        self._reader_task: asyncio.Task[None] | None = None
        self._active_threads: set[str] = set()
        self._mcp_elicitation_enabled = on_mcp_elicitation is not None
        self._mcp_elicitation_for_approvals = mcp_elicitation_for_approvals
        self._server_request_handlers: dict[str, ServerRequestHandler] = {}
        self.fs = CodexFS(self)
        if on_approval:
            self.register_handler(SERVER_REQUEST_COMMAND_APPROVAL, on_approval)  # type: ignore[arg-type]
            self.register_handler(SERVER_REQUEST_FILE_CHANGE_APPROVAL, on_approval)  # type: ignore[arg-type]
            self.register_handler(SERVER_REQUEST_SKILL_APPROVAL, on_approval)  # type: ignore[arg-type]
        if on_user_input:
            self.register_handler(SERVER_REQUEST_USER_INPUT, on_user_input)  # type: ignore[arg-type]
        if on_dynamic_tool_call:
            self.register_handler(SERVER_REQUEST_DYNAMIC_TOOL_CALL, on_dynamic_tool_call)  # type: ignore[arg-type]
        if on_mcp_elicitation:
            self.register_handler(SERVER_REQUEST_MCP_ELICITATION, on_mcp_elicitation)  # type: ignore[arg-type]

    async def __aenter__(self) -> Self:
        """Async context manager entry - starts the app-server."""
        await self.start()
        return self

    async def __aexit__(self, *_args: object) -> None:
        """Async context manager exit - stops the app-server."""
        await self.stop()

    async def start(self) -> None:
        """Start the transport and initialize the JSON-RPC connection.

        Raises:
            CodexProcessError: If failed to start the transport
        """
        import codexed

        if self._transport.is_connected:
            return

        await self._transport.start()
        # Start reader task
        self._reader_task = asyncio.create_task(self._read_loop())
        # Initialize connection
        version = codexed.__version__
        init_params = InitializeParams.create(name="codexed", version=version)
        await self._send_request("initialize", init_params)

    async def stop(self) -> None:
        """Stop the transport and clean up resources."""
        if not self._transport.is_connected:
            return

        # Cancel reader task
        if self._reader_task:
            self._reader_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._reader_task

        await self._transport.stop()
        # Reject pending requests
        for future in self._pending_requests.values():
            if not future.done():
                future.set_exception(TransportClosedError("Connection closed"))
        self._pending_requests.clear()

    # ========================================================================
    # Thread lifecycle methods
    # ========================================================================

    async def thread_start(
        self,
        *,
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
        service_name: str | None = None,
        personality: Personality | None = None,
        ephemeral: bool | None = None,
        mcp_servers: Mapping[str, McpServerConfig] | None = None,
    ) -> Session:
        """Start a new conversation thread.

        Args:
            cwd: Working directory for the thread
            model: Model to use (e.g., "gpt-5-codex")
            model_provider: Model provider (e.g., "openai", "anthropic")
            base_instructions: Base system instructions for the thread
            developer_instructions: Developer-provided instructions
            approval_policy: Tool approval policy
            sandbox: Sandbox mode for file operations
            config: Additional configuration overrides
            tools: Builtin tool configurations. ``None`` uses server defaults,
                an empty list disables all tools, a populated list enables
                exactly those tools. Merged into ``config``.
            code_mode: Enable experimental code mode feature flag
            service_name: Optional service name
            personality: Personality preset (none, friendly, pragmatic)
            ephemeral: If true, thread is not persisted to disk
            mcp_servers: Per-thread MCP server configurations.
                Merged into ``config`` under the ``mcp_servers`` key.

        Returns:
            Session wrapping the new thread
        """
        from codexed.session import Session

        params = ThreadStartParams(
            cwd=cwd,
            model=model,
            model_provider=model_provider,
            base_instructions=base_instructions,
            developer_instructions=developer_instructions,
            approval_policy=approval_policy,
            sandbox=sandbox,
            config=merge_config(
                config,
                tools,
                code_mode,
                mcp_servers,
                mcp_elicitation_for_approvals=self._mcp_elicitation_for_approvals,
            ),
            service_name=service_name,
            personality=personality,
            ephemeral=ephemeral,
        )
        result = await self._send_request("thread/start", params)
        response = ThreadResponse.model_validate(result)
        self._active_threads.add(response.thread.id)
        return Session(self, response)

    async def thread_resume(
        self,
        thread_id: str,
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
        mcp_servers: Mapping[str, McpServerConfig] | None = None,
    ) -> Session:
        """Resume an existing thread by ID.

        Args:
            thread_id: ID of the thread to resume
            path: Path to thread storage
            cwd: Working directory override
            model: Model override
            model_provider: Model provider override
            base_instructions: Base system instructions override
            developer_instructions: Developer instructions override
            approval_policy: Tool approval policy override
            sandbox: Sandbox mode override
            config: Additional configuration overrides
            tools: Builtin tool configurations override
            code_mode: Enable experimental code mode feature flag
            personality: Personality override
            mcp_servers: Per-thread MCP server configurations

        Returns:
            Session wrapping the resumed thread
        """
        from codexed.session import Session

        cfg = merge_config(
            config,
            tools,
            code_mode,
            mcp_servers,
            mcp_elicitation_for_approvals=self._mcp_elicitation_for_approvals,
        )
        params = ThreadResumeParams(
            thread_id=thread_id,
            path=path,
            cwd=cwd,
            model=model,
            model_provider=model_provider,
            base_instructions=base_instructions,
            developer_instructions=developer_instructions,
            approval_policy=approval_policy,
            sandbox=sandbox,
            config=cfg,
            personality=personality,
        )
        result = await self._send_request("thread/resume", params)
        response = ThreadResponse.model_validate(result)
        self._active_threads.add(response.thread.id)
        return Session(self, response)

    async def thread_fork(
        self,
        thread_id: str,
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
        mcp_servers: Mapping[str, McpServerConfig] | None = None,
        turn_id: str | None = None,
    ) -> Session:
        """Fork an existing thread into a new thread with copied history.

        Args:
            thread_id: ID of the thread to fork
            path: Path to thread storage
            cwd: Working directory for the forked thread
            model: Model override for forked thread
            model_provider: Model provider override
            base_instructions: Base system instructions for forked thread
            developer_instructions: Developer instructions for forked thread
            approval_policy: Tool approval policy for forked thread
            sandbox: Sandbox mode for forked thread
            config: Additional configuration overrides
            tools: Builtin tool configurations for forked thread
            code_mode: Enable experimental code mode feature flag
            personality: Personality for forked thread
            mcp_servers: Per-thread MCP server configurations
            turn_id: If provided, rollback the forked thread to this turn

        Returns:
            Session wrapping the new forked thread
        """
        from codexed.session import Session

        cfg = merge_config(
            config,
            tools,
            code_mode,
            mcp_servers,
            mcp_elicitation_for_approvals=self._mcp_elicitation_for_approvals,
        )
        params = ThreadForkParams(
            thread_id=thread_id,
            path=path,
            cwd=cwd,
            model=model,
            model_provider=model_provider,
            base_instructions=base_instructions,
            developer_instructions=developer_instructions,
            approval_policy=approval_policy,
            sandbox=sandbox,
            config=cfg,
            personality=personality,
        )
        result = await self._send_request("thread/fork", params)
        response = ThreadResponse.model_validate(result)
        self._active_threads.add(response.thread.id)
        session = Session(self, response)
        if turn_id is not None:
            await session.rollback_to_turn(turn_id)
        return session

    async def thread_list(
        self,
        *,
        cursor: str | None = None,
        limit: int | None = None,
        sort_key: ThreadSortKey | None = None,
        model_providers: list[str] | None = None,
        source_kinds: list[ThreadSourceKind] | None = None,
        archived: bool | None = None,
        cwd: str | None = None,
        search_term: str | None = None,
    ) -> ThreadListResponse:
        """List stored threads with pagination.

        Args:
            cursor: Opaque pagination cursor from previous response
            limit: Maximum number of threads to return
            sort_key: Sort key (created_at or updated_at)
            model_providers: Filter by model providers
            source_kinds: Filter by source kinds
            archived: If true, only return archived threads
            cwd: Filter by working directory
            search_term: Substring filter for thread title

        Returns:
            ThreadListResponse with data (list of threads) and next_cursor
        """
        params = ThreadListParams(
            cursor=cursor,
            limit=limit,
            sort_key=sort_key,
            model_providers=model_providers,
            source_kinds=source_kinds,
            archived=archived,
            cwd=cwd,
            search_term=search_term,
        )
        result = await self._send_request("thread/list", params)
        return ThreadListResponse.model_validate(result)

    async def thread_read(
        self, thread_id: str, *, include_turns: bool = False
    ) -> ThreadReadResponse:
        """Read a thread's data."""
        params = ThreadReadParams(thread_id=thread_id, include_turns=include_turns)
        result = await self._send_request("thread/read", params)
        return ThreadReadResponse.model_validate(result)

    async def thread_loaded_list(self) -> list[str]:
        """List thread IDs currently loaded in memory."""
        result = await self._send_request("thread/loaded/list")
        response = ThreadLoadedListResponse.model_validate(result)
        return response.data

    async def thread_unsubscribe(self, thread_id: str) -> ThreadUnsubscribeResponse:
        """Stop listening to a thread's events.

        Args:
            thread_id: The thread ID to unsubscribe from

        Returns:
            ThreadUnsubscribeResponse with status (notLoaded/notSubscribed/unsubscribed)
        """
        params = ThreadUnsubscribeParams(thread_id=thread_id)
        result = await self._send_request("thread/unsubscribe", params)
        return ThreadUnsubscribeResponse.model_validate(result)

    async def thread_archive(self, thread_id: str) -> None:
        """Archive a thread (move to archived directory)."""
        params = ThreadArchiveParams(thread_id=thread_id)
        await self._send_request("thread/archive", params)
        self._active_threads.discard(thread_id)

    async def thread_unarchive(self, thread_id: str) -> ThreadUnarchiveResponse:
        """Unarchive a previously archived thread. Returns unarchived thread data."""
        params = ThreadUnarchiveParams(thread_id=thread_id)
        result = await self._send_request("thread/unarchive", params)
        return ThreadUnarchiveResponse.model_validate(result)

    async def thread_set_name(self, thread_id: str, name: str) -> None:
        """Set a user-facing name for a thread."""
        params = ThreadSetNameParams(thread_id=thread_id, name=name)
        await self._send_request("thread/name/set", params)

    async def thread_compact_start(self, thread_id: str) -> None:
        """Trigger context compaction for a thread."""
        params = ThreadCompactStartParams(thread_id=thread_id)
        await self._send_request("thread/compact/start", params)

    async def thread_rollback(self, thread_id: str, turns: int) -> ThreadRollbackResponse:
        """Rollback the last N turns from a thread.

        Args:
            thread_id: The thread ID
            turns: Number of turns to rollback

        Returns:
            Updated thread object with turns populated
        """
        params = ThreadRollbackParams(thread_id=thread_id, turns=turns)
        result = await self._send_request("thread/rollback", params)
        return ThreadRollbackResponse.model_validate(result)

    async def thread_rollback_to_turn(self, thread_id: str, turn_id: str) -> ThreadRollbackResponse:
        """Rollback a thread to a specific turn, keeping that turn and removing all after it.

        This is a convenience method that reads the thread to find the turn index,
        then calls thread_rollback with the computed number of turns to drop.

        Args:
            thread_id: The thread ID
            turn_id: The turn ID to roll back to (this turn will be kept)

        Returns:
            Updated thread object with turns populated

        Raises:
            ValueError: If the turn_id is not found in the thread
        """
        thread_response = await self.thread_read(thread_id, include_turns=True)
        turns = thread_response.thread.turns
        turn_index = next((i for i, turn in enumerate(turns) if turn.id == turn_id), None)
        if turn_index is None:
            raise ValueError(f"Turn {turn_id!r} not found in thread {thread_id!r}")
        num_turns_to_drop = len(turns) - turn_index - 1
        if num_turns_to_drop < 1:
            raise ValueError(f"Turn {turn_id!r} is already the last turn in thread {thread_id!r}")
        return await self.thread_rollback(thread_id, num_turns_to_drop)

    async def thread_shell_command(self, thread_id: str, command: str) -> None:
        """Run a user-initiated shell command against a thread.

        Executes the command unsandboxed, as if the user typed `!command`
        in the Codex CLI.

        Args:
            thread_id: The thread ID.
            command: Shell command to execute.
        """
        params = ThreadShellCommandParams(thread_id=thread_id, command=command)
        await self._send_request("thread/shellCommand", params)

    # ========================================================================
    # Turn methods
    # ========================================================================

    async def turn_stream(
        self,
        thread_id: str,
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
        """Start a turn and stream events.

        Args:
            thread_id: The thread ID to send the turn to
            user_input: User input as string or list of input items (text/image)
            model: Optional model override for this turn
            effort: Optional reasoning effort override
            approval_policy: Optional approval policy
            cwd: Optional working directory override for this and subsequent turns
            sandbox_policy: Optional sandbox mode or policy dict
            output_schema: Optional JSON Schema dict or Pydantic type to constrain output
            personality: Optional personality override
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
            case type():  # It's a type - use TypeAdapter to extract schema
                schema_dict = TypeAdapter(output_schema).json_schema()
            case _ as unreachable:
                assert_never(unreachable)
        # Handle sandbox_policy - convert string to dict if needed
        # Turn-level API uses camelCase (workspaceWrite), thread-level uses kebab-case
        match sandbox_policy:
            case None:
                sandbox_dict: dict[str, Any] | None = None
            case str():
                # Convert kebab-case to camelCase for turn API
                sandbox_dict = {"type": kebab_to_camel(sandbox_policy)}
            case dict():
                sandbox_dict = sandbox_policy
            case _:
                assert_never(sandbox_policy)
        params = TurnStartParams(
            thread_id=thread_id,
            input=[UserInputText(text=user_input)] if isinstance(user_input, str) else user_input,
            model=model,
            effort=effort,
            approval_policy=approval_policy,
            cwd=cwd,
            sandbox_policy=sandbox_dict,
            output_schema=schema_dict,
            personality=personality,
            summary=summary,
            collaboration_mode=collaboration_mode,
        )
        # Start turn (non-blocking request)
        turn_result = await self._send_request("turn/start", params)
        response = TurnStartResponse.model_validate(turn_result)
        turn_id = response.turn.id
        # Create per-turn event queue for proper routing
        turn_queue: asyncio.Queue[CodexEvent | None] = asyncio.Queue()
        turn_key = f"{thread_id}:{turn_id}"
        self._turn_queues[turn_key] = turn_queue
        try:  # Stream events until turn completes
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
                        yield event
        finally:  # Cleanup turn queue
            if turn_key in self._turn_queues:
                del self._turn_queues[turn_key]

    async def turn_steer(
        self,
        thread_id: str,
        user_input: str | list[UserInput],
        *,
        expected_turn_id: str,
    ) -> TurnSteerResponse:
        """Steer a running turn with additional input.

        Args:
            thread_id: The thread ID
            user_input: Additional user input
            expected_turn_id: The expected active turn ID (precondition)

        Returns:
            TurnSteerResponse with the turn ID
        """
        params = TurnSteerParams(
            thread_id=thread_id,
            input=[UserInputText(text=user_input)] if isinstance(user_input, str) else user_input,
            expected_turn_id=expected_turn_id,
        )
        result = await self._send_request("turn/steer", params)
        return TurnSteerResponse.model_validate(result)

    async def turn_interrupt(self, thread_id: str, turn_id: str) -> None:
        """Interrupt a running turn."""
        params = TurnInterruptParams(thread_id=thread_id, turn_id=turn_id)
        await self._send_request("turn/interrupt", params)

    async def turn_stream_structured[ResultType: BaseModel](
        self,
        thread_id: str,
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
        """Start a turn with structured output and return the parsed result.

        This is a convenience method that combines turn_stream with automatic
        schema generation and result parsing. Similar to PydanticAI's approach.

        Note: This method only accepts Pydantic types (not raw dict schemas).
        For dict schemas, use turn_stream() with output_schema and parse manually.

        Args:
            thread_id: The thread ID to send the turn to
            user_input: User input as string or list of items
            result_type: Pydantic model class for the expected result (not a dict!)
            model: Optional model override for this turn
            effort: Optional reasoning effort override
            approval_policy: Optional approval policy
            cwd: Optional working directory override for this and subsequent turns
            sandbox_policy: Optional sandbox mode or policy dict
            personality: Optional personality override
            summary: Optional reasoning summary mode
            collaboration_mode: Optional collaboration mode preset (experimental)

        Returns:
            Parsed Pydantic model instance of type result_type

        Raises:
            ValidationError: If the agent's response doesn't match the schema
            CodexRequestError: If the turn fails
        """
        turn: Turn | None = None
        async for event in self.turn_stream(
            thread_id,
            user_input,
            model=model,
            effort=effort,
            approval_policy=approval_policy,
            cwd=cwd,
            sandbox_policy=sandbox_policy,
            output_schema=result_type,  # Auto-generate schema from type
            personality=personality,
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

    # ========================================================================
    # Review methods
    # ========================================================================

    async def review_start(
        self,
        thread_id: str,
        target: ReviewTarget,
        *,
        delivery: ReviewDelivery | None = None,
    ) -> ReviewStartResponse:
        """Start a code review.

        Args:
            thread_id: The thread ID to start the review on
            target: Review target (uncommittedChanges, baseBranch, commit, or custom)
            delivery: Where to run the review (inline or detached)

        Returns:
            ReviewStartResponse with turn and review thread ID
        """
        params = ReviewStartParams(thread_id=thread_id, target=target, delivery=delivery)
        result = await self._send_request("review/start", params)
        return ReviewStartResponse.model_validate(result)

    # ========================================================================
    # Skills methods
    # ========================================================================

    async def skills_list(
        self,
        *,
        cwds: list[str] | None = None,
        force_reload: bool | None = None,
    ) -> list[SkillData]:
        """List available skills.

        Args:
            cwds: Optional working directories to scope skills
            force_reload: Force reload of skills cache

        Returns:
            List of skills with metadata
        """
        params = SkillsListParams(cwds=cwds, force_reload=force_reload)
        result = await self._send_request("skills/list", params)
        response = SkillsListResponse.model_validate(result)
        # Return skills from first container (usually only one)
        if response.data:
            return response.data[0].skills
        return []

    async def skills_config_write(self, path: str, *, enabled: bool) -> None:
        """Write skills configuration.

        Args:
            path: Path to the skill
            enabled: Whether the skill is enabled
        """
        params = SkillsConfigWriteParams(path=path, enabled=enabled)
        await self._send_request("skills/config/write", params)

    async def skills_remote_list(
        self,
        *,
        hazelnut_scope: HazelnutScope = "example",
        product_surface: ProductSurface = "codex",
        enabled: bool = False,
    ) -> list[RemoteSkillSummary]:
        """List remote skills.

        Args:
            hazelnut_scope: Scope filter (example/workspace-shared/all-shared/personal)
            product_surface: Product surface filter (chatgpt/codex/api/atlas)
            enabled: Whether to filter by enabled status

        Returns:
            List of remote skill summaries
        """
        params = SkillsRemoteListParams(
            hazelnut_scope=hazelnut_scope,
            product_surface=product_surface,
            enabled=enabled,
        )
        result = await self._send_request("skills/remote/list", params)
        response = SkillsRemoteListResponse.model_validate(result)
        return response.data

    async def skills_remote_export(self, hazelnut_id: str) -> SkillsRemoteExportResponse:
        """Export a skill to remote storage.

        Args:
            hazelnut_id: ID of the remote skill to export

        Returns:
            SkillsRemoteExportResponse with id and local path
        """
        params = SkillsRemoteExportParams(hazelnut_id=hazelnut_id)
        result = await self._send_request("skills/remote/export", params)
        return SkillsRemoteExportResponse.model_validate(result)

    # ========================================================================
    # Model methods
    # ========================================================================

    async def model_list(self, *, include_hidden: bool | None = None) -> list[ModelData]:
        """List available models with reasoning effort options.

        Args:
            include_hidden: When true, include hidden models

        Returns:
            List of available models
        """
        params = ModelListParams(include_hidden=include_hidden)
        result = await self._send_request("model/list", params)
        response = ModelListResponse.model_validate(result)
        return response.data

    async def collaboration_mode_list(self) -> list[CollaborationModeMask]:
        """List available collaboration mode presets (experimental).

        Returns:
            List of collaboration mode presets with name, mode, model, and effort
        """
        result = await self._send_request("collaborationMode/list")
        response = CollaborationModeListResponse.model_validate(result)
        return response.data

    # ========================================================================
    # Command execution
    # ========================================================================

    async def command_exec(
        self,
        command: list[str],
        *,
        cwd: str | None = None,
        sandbox_policy: dict[str, Any] | None = None,
        timeout_ms: int | None = None,
    ) -> CommandExecResponse:
        """Execute a command without creating a thread/turn.

        Args:
            command: Command and arguments as list (e.g., ["ls", "-la"])
            cwd: Working directory for command
            sandbox_policy: Sandbox policy override
            timeout_ms: Timeout in milliseconds

        Returns:
            CommandExecResponse with exit_code, stdout, stderr
        """
        params = CommandExecParams(
            command=command,
            cwd=cwd,
            sandbox_policy=sandbox_policy,
            timeout_ms=timeout_ms,
        )
        result = await self._send_request("command/exec", params)
        return CommandExecResponse.model_validate(result)

    # ========================================================================
    # MCP server methods
    # ========================================================================

    async def mcp_server_refresh(self) -> None:
        """Reload MCP server configurations from disk.

        Triggers all threads to rebuild their MCP connections on the next turn
        using the latest config file.
        """
        await self._send_request("config/mcpServer/reload")

    async def mcp_server_status_list(
        self,
        *,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> ListMcpServerStatusResponse:
        """List MCP server status with tool and resource information.

        Args:
            cursor: Pagination cursor from previous call
            limit: Maximum number of servers to return

        Returns:
            Response with server status entries and optional next_cursor
        """
        params = ListMcpServerStatusParams(cursor=cursor, limit=limit)
        result = await self._send_request("mcpServerStatus/list", params)
        return ListMcpServerStatusResponse.model_validate(result)

    async def mcp_server_oauth_login(
        self,
        name: str,
        *,
        scopes: list[str] | None = None,
        timeout_secs: int | None = None,
    ) -> McpServerOauthLoginResponse:
        """Start OAuth login for an MCP server.

        Args:
            name: Name of the MCP server
            scopes: Optional OAuth scopes to request
            timeout_secs: Optional timeout in seconds

        Returns:
            Response with authorization URL
        """
        params = McpServerOauthLoginParams(name=name, scopes=scopes, timeout_secs=timeout_secs)
        result = await self._send_request("mcpServer/oauth/login", params)
        return McpServerOauthLoginResponse.model_validate(result)

    # ========================================================================
    # Account methods
    # ========================================================================

    async def account_read(self, *, refresh_token: bool = False) -> GetAccountResponse:
        """Read account information.

        Args:
            refresh_token: When true, trigger a proactive token refresh

        Returns:
            GetAccountResponse with account info
        """
        params = GetAccountParams(refresh_token=refresh_token)
        result = await self._send_request("account/read", params)
        return GetAccountResponse.model_validate(result)

    async def account_login_start(
        self,
        login_type: LoginType,
        *,
        api_key: str | None = None,
        access_token: str | None = None,
        chatgpt_account_id: str | None = None,
    ) -> LoginAccountResponse:
        """Start account login.

        Args:
            login_type: Login type (apiKey, chatgpt, chatgptAuthTokens)
            api_key: API key (for apiKey type)
            access_token: Access token (for chatgptAuthTokens type)
            chatgpt_account_id: ChatGPT account ID (for chatgptAuthTokens type)

        Returns:
            LoginAccountResponse with login details
        """
        params = LoginAccountParams(
            type=login_type,
            api_key=api_key,
            access_token=access_token,
            chatgpt_account_id=chatgpt_account_id,
        )
        result = await self._send_request("account/login/start", params)
        return LoginAccountResponse.model_validate(result)

    async def account_login_cancel(self, login_id: str) -> CancelLoginAccountResponse:
        """Cancel an in-progress account login."""
        params = CancelLoginAccountParams(login_id=login_id)
        result = await self._send_request("account/login/cancel", params)
        return CancelLoginAccountResponse.model_validate(result)

    async def account_logout(self) -> None:
        """Logout from the current account."""
        await self._send_request("account/logout")

    async def account_rate_limits_read(self) -> GetAccountRateLimitsResponse:
        """Read account rate limits."""
        result = await self._send_request("account/rateLimits/read")
        return GetAccountRateLimitsResponse.model_validate(result)

    # ========================================================================
    # Config methods
    # ========================================================================

    async def config_read(
        self,
        *,
        include_layers: bool = False,
        cwd: str | None = None,
    ) -> ConfigReadResponse:
        """Read configuration.

        Args:
            include_layers: Whether to include config layer details
            cwd: Optional working directory for project config resolution

        Returns:
            ConfigReadResponse with config data
        """
        params = ConfigReadParams(include_layers=include_layers, cwd=cwd)
        result = await self._send_request("config/read", params)
        return ConfigReadResponse.model_validate(result)

    async def config_value_write(
        self,
        key_path: str,
        value: Any,
        merge_strategy: MergeStrategy,
        *,
        file_path: str | None = None,
        expected_version: str | None = None,
    ) -> ConfigWriteResponse:
        """Write a config value.

        Args:
            key_path: Dotted key path (e.g., "model")
            value: Value to write
            merge_strategy: How to merge (replace or merge)
            file_path: Optional config file path
            expected_version: Optional expected version for optimistic locking

        Returns:
            ConfigWriteResponse with status
        """
        params = ConfigValueWriteParams(
            key_path=key_path,
            value=value,
            merge_strategy=merge_strategy,
            file_path=file_path,
            expected_version=expected_version,
        )
        result = await self._send_request("config/value/write", params)
        return ConfigWriteResponse.model_validate(result)

    async def config_batch_write(
        self,
        edits: list[ConfigEdit],
        *,
        file_path: str | None = None,
        expected_version: str | None = None,
    ) -> ConfigWriteResponse:
        """Batch write config values.

        Args:
            edits: List of ConfigEdit objects
            file_path: Optional config file path
            expected_version: Optional expected version for optimistic locking

        Returns:
            ConfigWriteResponse with status
        """
        params = ConfigBatchWriteParams(
            edits=edits,
            file_path=file_path,
            expected_version=expected_version,
        )
        result = await self._send_request("config/batchWrite", params)
        return ConfigWriteResponse.model_validate(result)

    async def config_requirements_read(self) -> ConfigRequirementsReadResponse:
        """Read config requirements."""
        result = await self._send_request("configRequirements/read")
        return ConfigRequirementsReadResponse.model_validate(result)

    # ========================================================================
    # Apps methods
    # ========================================================================

    async def apps_list(
        self,
        *,
        cursor: str | None = None,
        limit: int | None = None,
        thread_id: str | None = None,
        force_refetch: bool | None = None,
    ) -> list[AppInfo]:
        """List available apps/connectors.

        Args:
            cursor: Pagination cursor
            limit: Maximum number of apps to return
            thread_id: Optional thread ID for feature gating
            force_refetch: Bypass caches and fetch latest

        Returns:
            List of AppInfo objects
        """
        params = AppsListParams(
            cursor=cursor,
            limit=limit,
            thread_id=thread_id,
            force_refetch=force_refetch,
        )
        result = await self._send_request("app/list", params)
        response = AppsListResponse.model_validate(result)
        return response.data

    # ========================================================================
    # Experimental feature methods
    # ========================================================================

    async def experimental_feature_list(
        self,
        *,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> list[ExperimentalFeature]:
        """List experimental features.

        Args:
            cursor: Pagination cursor
            limit: Maximum number of features to return

        Returns:
            List of ExperimentalFeature objects
        """
        params = ExperimentalFeatureListParams(cursor=cursor, limit=limit)
        result = await self._send_request("experimentalFeature/list", params)
        response = ExperimentalFeatureListResponse.model_validate(result)
        return response.data

    # ========================================================================
    # Feedback methods
    # ========================================================================

    async def feedback_upload(
        self,
        classification: str,
        *,
        reason: str | None = None,
        thread_id: str | None = None,
        include_logs: bool = False,
        extra_log_files: list[str] | None = None,
    ) -> FeedbackUploadResponse:
        """Upload feedback.

        Args:
            classification: Feedback classification
            reason: Optional reason text
            thread_id: Optional thread ID to associate
            include_logs: Whether to include logs
            extra_log_files: Additional log files to include

        Returns:
            FeedbackUploadResponse with thread ID
        """
        params = FeedbackUploadParams(
            classification=classification,
            reason=reason,
            thread_id=thread_id,
            include_logs=include_logs,
            extra_log_files=extra_log_files,
        )
        result = await self._send_request("feedback/upload", params)
        return FeedbackUploadResponse.model_validate(result)

    # ========================================================================
    # External agent config methods
    # ========================================================================

    async def external_agent_config_detect(
        self,
        *,
        include_home: bool | None = None,
        cwds: list[str] | None = None,
    ) -> ExternalAgentConfigDetectResponse:
        """Detect external agent configurations.

        Args:
            include_home: Include detection under user's home directory
            cwds: Working directories for repo-scoped detection

        Returns:
            ExternalAgentConfigDetectResponse with migration items
        """
        params = ExternalAgentConfigDetectParams(include_home=include_home, cwds=cwds)
        result = await self._send_request("externalAgentConfig/detect", params)
        return ExternalAgentConfigDetectResponse.model_validate(result)

    async def external_agent_config_import(
        self,
        migration_items: list[ExternalAgentConfigMigrationItem],
    ) -> None:
        """Import external agent configurations.

        Args:
            migration_items: List of migration items to import
        """
        params = ExternalAgentConfigImportParams(migration_items=migration_items)
        await self._send_request("externalAgentConfig/import", params)

    # ========================================================================
    # Internal transport methods
    # ========================================================================

    async def _send_request(self, method: str, params: BaseModel | None = None) -> Any:
        """Send a JSON-RPC request and wait for response.

        Args:
            method: JSON-RPC method name
            params: Pydantic model with request parameters (will be serialized)

        Returns:
            Response result (not yet validated - caller should validate)
        """
        if not self._transport.is_connected:
            raise TransportClosedError("Not connected to Codex app-server")

        request_id = self._request_id
        self._request_id += 1
        future: asyncio.Future[Any] = asyncio.Future()
        self._pending_requests[request_id] = future
        # Serialize params to dict if provided
        params_dict = params.model_dump(by_alias=True, exclude_none=True) if params else {}
        request = JsonRpcRequest(id=request_id, method=method, params=params_dict)
        try:
            message = request.model_dump(mode="json", by_alias=True, exclude_none=True)
            await self._transport.send(message)
        except Exception as exc:
            del self._pending_requests[request_id]
            raise CodexProcessError(f"Failed to send request: {exc}") from exc

        return await future

    async def _read_loop(self) -> None:
        """Read messages from the transport."""
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
        finally:
            await self._event_queue.put(None)

    async def _process_message(self, message: dict[str, Any]) -> None:
        """Process a message from the app-server.

        Messages are one of:
        - Server request: has both "method" and "id" -> needs a response
        - Response to our request: has "id" but no "method" -> resolves pending future
        - Notification: has "method" but no "id" -> routed as event

        Args:
            message: Raw JSON-RPC message
        """
        match message:
            case {"method": _, "id": _}:  # Server request - the server is asking us to do something
                await self._handle_server_request(message)
            case {"id": _}:  # Response to one of our requests
                self._handle_response(message)
            case {"method": _}:  # Notification - one-way event
                await self._handle_notification(message)
            case _:
                raise TypeError(f"Unknown message shape {message}")

    def _handle_response(self, message: dict[str, Any]) -> None:
        """Handle a JSON-RPC response to one of our pending requests."""
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

    async def _handle_notification(self, message: dict[str, Any]) -> None:
        """Handle a JSON-RPC notification (one-way event)."""
        method = message["method"]
        params = message.get("params") or {}

        if method.startswith("codex/event/"):
            return

        event_data = {"event_type": method, "data": params or {}}
        event = codex_event_adapter.validate_python(event_data)
        # Route event to appropriate turn queue
        thread_id = params.get("threadId")
        turn_id = params.get("turnId")
        # Also check nested turn object (some events have it there)
        if not turn_id and "turn" in params:
            turn_data = params.get("turn", {})
            turn_id = turn_data.get("id")

        if thread_id and turn_id:
            # Turn-specific event - route to turn queue
            turn_key = f"{thread_id}:{turn_id}"
            if turn_key in self._turn_queues:
                await self._turn_queues[turn_key].put(event)
            else:
                # Turn queue not found (might be old event) - put in global queue
                await self._event_queue.put(event)
        else:
            # Global event (account, MCP, etc.) - put in global queue
            await self._event_queue.put(event)

    async def _handle_server_request(self, message: dict[str, Any]) -> None:
        """Handle a JSON-RPC request from the server that expects a response."""
        method: str = message["method"]
        request_id = message["id"]
        params = message.get("params") or {}

        type_entry = SERVER_REQUEST_TYPES.get(method)
        if type_entry is None:
            logger.warning("Unhandled server request method: %s (id=%s)", method, request_id)
            await self._send_server_request_error(request_id, -32601, f"Method not found: {method}")
            return

        params_type, _ = type_entry
        handler = self._server_request_handlers.get(method)
        if handler is None:
            logger.warning("No handler registered for request: %s (id=%s)", method, request_id)
            await self._send_server_request_error(request_id, -32603, f"No handler for: {method}")
            return

        try:
            if isinstance(params_type, TypeAdapter):
                parsed_params = params_type.validate_python(params)
            else:
                parsed_params = params_type.model_validate(params)
            response_model = await handler(parsed_params)
            await self._send_server_request_response(request_id, response_model)
        except Exception:
            logger.exception("Error handling server request %s (id=%s)", method, request_id)
            await self._send_server_request_error(
                request_id, -32603, f"Internal error handling {method}"
            )

    async def _send_server_request_response(self, request_id: int | str, result: BaseModel) -> None:
        """Send a JSON-RPC response to a server request."""
        dct = result.model_dump(by_alias=True, exclude_none=True)
        response = {"jsonrpc": "2.0", "id": request_id, "result": dct}
        await self._write_message(response)

    async def _send_server_request_error(
        self, request_id: int | str, code: int, message: str
    ) -> None:
        """Send a JSON-RPC error response to a server request."""
        error = {"code": code, "message": message}
        response = {"jsonrpc": "2.0", "id": request_id, "error": error}
        await self._write_message(response)

    async def _write_message(self, message: dict[str, Any]) -> None:
        """Write a JSON message via the transport."""
        await self._transport.send(message)

    # ========================================================================
    # Server request handler registration
    # ========================================================================

    def register_handler(self, method: HandlerMethod, handler: ServerRequestHandler) -> None:
        """Register a handler for a server request method.

        The handler receives the parsed params model and must return
        the appropriate response model.

        Args:
            method: Server request method name (use SERVER_REQUEST_* constants)
            handler: Async callback that processes the request and returns a response
        """
        if method not in SERVER_REQUEST_TYPES:
            msg = (
                f"Unknown server request method: {method}. "
                f"Valid methods: {list(SERVER_REQUEST_TYPES)}"
            )
            raise ValueError(msg)
        self._server_request_handlers[method] = handler

    def set_auto_approve(self) -> None:
        """Register default handlers that auto-approve all server requests.

        Convenience method for non-interactive use cases where all approvals
        should be automatically granted and tool calls return empty results.
        """
        self._server_request_handlers = create_auto_approve_dict()


if __name__ == "__main__":

    async def main() -> None:
        async with CodexClient() as client:
            session = await client.thread_start()
            async for e in session.turn_stream("Show available tools"):
                print(e)

    asyncio.run(main())
