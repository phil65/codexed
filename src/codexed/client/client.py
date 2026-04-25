"""Codex app-server client."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping  # noqa: TC003
import logging
from typing import TYPE_CHECKING, Any

from pydantic import TypeAdapter

from codexed.client.account import CodexAccount
from codexed.client.device import CodexDevice
from codexed.client.dispatch import Dispatch
from codexed.client.fs import CodexFS
from codexed.client.marketplace import CodexMarketPlace
from codexed.client.plugin import CodexPlugin
from codexed.client.skills import CodexSkills
from codexed.helpers import merge_config
from codexed.models import (
    AppsListParams,
    AppsListResponse,
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
    ListMcpServerStatusParams,
    ListMcpServerStatusResponse,
    McpResourceReadParams,
    McpResourceReadResponse,
    McpServerOauthLoginParams,
    McpServerOauthLoginResponse,
    MemoryResetResponse,
    ModelListParams,
    ModelListResponse,
    ThreadForkParams,
    ThreadListParams,
    ThreadListResponse,
    ThreadLoadedListParams,
    ThreadLoadedListResponse,
    ThreadResponse,
    ThreadResumeParams,
    ThreadStartParams,
    WarningNotification,
    codex_event_adapter,
)
from codexed.models.mcp_server import ResourceContents
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

    from pydantic import BaseModel

    from codexed.client.session import Session
    from codexed.models import (
        AppInfo,
        ApprovalsReviewer,
        AskForApproval,
        CodexEvent,
        CollaborationModeMask,
        ConfigEdit,
        ConfigRequirements,
        DynamicToolSpec,
        ExperimentalFeature,
        ExternalAgentConfigMigrationItem,
        McpServerConfig,
        McpServerStatusDetail,
        MergeStrategy,
        PermissionProfile,
        Personality,
        SandboxMode,
        SandboxPolicy,
        ServiceTier,
        SortDirection,
        ThreadSortKey,
        ThreadSourceKind,
        ThreadStartSource,
        ToolConfig,
        TurnEnvironmentParams,
    )
    from codexed.models.v2_protocol import ThreadListCwdFilter
    from codexed.request_handlers import (
        ApprovalHandler,
        DynamicToolCallHandler,
        HandlerMethod,
        McpElicitationHandler,
        ServerRequestHandler,
        UserInputHandler,
    )
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
        tp = transport or StdioTransport(
            command=codex_command,
            profile=profile,
            env_vars=env_vars,
            mcp_servers=mcp_servers,
        )
        self.dispatch = Dispatch(
            tp,
            on_notification=self._handle_notification,
            on_server_request=self._handle_server_request,
        )
        self._turn_queues: dict[str, asyncio.Queue[CodexEvent | None]] = {}
        self._realtime_queues: dict[str, asyncio.Queue[CodexEvent | None]] = {}
        self._event_queue: asyncio.Queue[CodexEvent | None] = asyncio.Queue()
        self._active_threads: set[str] = set()
        self._mcp_elicitation_enabled = on_mcp_elicitation is not None
        self._mcp_elicitation_for_approvals = mcp_elicitation_for_approvals
        self._server_request_handlers: dict[str, ServerRequestHandler] = {}
        self.account = CodexAccount(self)
        self.fs = CodexFS(self)
        self.device = CodexDevice(self)
        self.plugins = CodexPlugin(self)
        self.marketplace = CodexMarketPlace(self)
        self.skills = CodexSkills(self)
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
        import codexed
        from codexed.models import ClientInfo, InitializeCapabilities, InitializeParams

        await self.dispatch.start()
        version = codexed.__version__
        init_params = InitializeParams(
            client_info=ClientInfo(name="codexed", version=version),
            capabilities=InitializeCapabilities(experimental_api=True),
        )
        await self.dispatch.send_request("initialize", init_params)
        return self

    async def __aexit__(self, *_args: object) -> None:
        """Async context manager exit - stops the app-server."""
        await self.dispatch.stop()

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
        approval_policy: AskForApproval | None = None,
        approvals_reviewer: ApprovalsReviewer | None = None,
        sandbox: SandboxMode | None = None,
        config: dict[str, Any] | None = None,
        tools: list[ToolConfig] | None = None,
        code_mode: bool | None = None,
        service_name: str | None = None,
        service_tier: ServiceTier | None = None,
        personality: Personality | None = None,
        ephemeral: bool | None = None,
        dynamic_tools: list[DynamicToolSpec] | None = None,
        mcp_servers: Mapping[str, McpServerConfig] | None = None,
        experimental_raw_events: bool = False,
        persist_extended_history: bool = False,
        session_start_source: ThreadStartSource | None = None,
        environments: list[TurnEnvironmentParams] | None = None,
    ) -> Session:
        """Start a new conversation thread.

        Args:
            cwd: Working directory for the thread
            model: Model to use (e.g., "gpt-5-codex")
            model_provider: Model provider (e.g., "openai", "anthropic")
            base_instructions: Base system instructions for the thread
            developer_instructions: Developer-provided instructions
            approval_policy: Tool approval policy
            approvals_reviewer: Where approval requests are routed for review
            sandbox: Sandbox mode for file operations
            config: Additional configuration overrides
            tools: Builtin tool configurations. ``None`` uses server defaults,
                an empty list disables all tools, a populated list enables
                exactly those tools. Merged into ``config``.
            code_mode: Enable experimental code mode feature flag
            service_name: Optional service name
            service_tier: Service tier (fast/flex)
            personality: Personality preset (none, friendly, pragmatic)
            ephemeral: If true, thread is not persisted to disk
            dynamic_tools: Dynamic tool specifications
            mcp_servers: Per-thread MCP server configurations.
                Merged into ``config`` under the ``mcp_servers`` key.
            experimental_raw_events: Emit raw Responses API items (internal)
            persist_extended_history: Persist full history for resume/fork/read
            session_start_source: Source of the session start
            environments: List of environment variables to set for the thread

        Returns:
            Session wrapping the new thread
        """
        from codexed.client.session import Session

        cfg = merge_config(
            config,
            tools,
            code_mode,
            mcp_servers,
            mcp_elicitation_for_approvals=self._mcp_elicitation_for_approvals,
        )
        params = ThreadStartParams(
            cwd=cwd,
            model=model,
            model_provider=model_provider,
            base_instructions=base_instructions,
            developer_instructions=developer_instructions,
            approval_policy=approval_policy,
            approvals_reviewer=approvals_reviewer,
            sandbox=sandbox,
            config=cfg,
            service_name=service_name,
            service_tier=service_tier,
            personality=personality,
            ephemeral=ephemeral,
            dynamic_tools=dynamic_tools,
            experimental_raw_events=experimental_raw_events,
            persist_extended_history=persist_extended_history,
            session_start_source=session_start_source,
            environments=environments,
        )
        result = await self.dispatch.send_request("thread/start", params)
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
        approval_policy: AskForApproval | None = None,
        approvals_reviewer: ApprovalsReviewer | None = None,
        sandbox: SandboxMode | None = None,
        config: dict[str, Any] | None = None,
        tools: list[ToolConfig] | None = None,
        code_mode: bool | None = None,
        service_tier: ServiceTier | None = None,
        personality: Personality | None = None,
        mcp_servers: Mapping[str, McpServerConfig] | None = None,
        persist_extended_history: bool = False,
        exclude_turns: bool | None = None,
        permission_profile: PermissionProfile | None = None,
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
            approvals_reviewer: Where approval requests are routed for review
            sandbox: Sandbox mode override
            config: Additional configuration overrides
            tools: Builtin tool configurations override
            code_mode: Enable experimental code mode feature flag
            service_tier: Service tier (fast/flex)
            personality: Personality override
            mcp_servers: Per-thread MCP server configurations
            persist_extended_history: Persist full history for resume/fork/read
            exclude_turns: If true, exclude turns from the thread's history
            permission_profile: Permission profile override

        Returns:
            Session wrapping the resumed thread
        """
        from codexed.client.session import Session

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
            approvals_reviewer=approvals_reviewer,
            sandbox=sandbox,
            config=cfg,
            service_tier=service_tier,
            personality=personality,
            persist_extended_history=persist_extended_history,
            exclude_turns=exclude_turns,
            permission_profile=permission_profile,
        )
        result = await self.dispatch.send_request("thread/resume", params)
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
        approval_policy: AskForApproval | None = None,
        approvals_reviewer: ApprovalsReviewer | None = None,
        sandbox: SandboxMode | None = None,
        config: dict[str, Any] | None = None,
        tools: list[ToolConfig] | None = None,
        code_mode: bool | None = None,
        service_tier: ServiceTier | None = None,
        ephemeral: bool | None = None,
        mcp_servers: Mapping[str, McpServerConfig] | None = None,
        turn_id: str | None = None,
        persist_extended_history: bool = False,
        exclude_turns: bool | None = None,
        permission_profile: PermissionProfile | None = None,
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
            exclude_turns: When true, return only thread metadata and live fork state
                           without populating `thread.turns`. This is useful when
                           the client plans to call `thread/turns/list` immediately after forking.
            permission_profile: Permission profile for forked thread

        Returns:
            Session wrapping the new forked thread
        """
        from codexed.client.session import Session

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
            approvals_reviewer=approvals_reviewer,
            sandbox=sandbox,
            config=cfg,
            service_tier=service_tier,
            ephemeral=ephemeral,
            persist_extended_history=persist_extended_history,
            exclude_turns=exclude_turns,
            permission_profile=permission_profile,
        )
        result = await self.dispatch.send_request("thread/fork", params)
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
        cwd: ThreadListCwdFilter | None = None,
        search_term: str | None = None,
        sort_direction: SortDirection | None = None,
        use_state_db_only: bool | None = None,
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
            sort_direction: Sort direction (asc or desc)
            use_state_db_only: If true, only return threads from the state DB

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
            sort_direction=sort_direction,
            use_state_db_only=use_state_db_only,
        )
        result = await self.dispatch.send_request("thread/list", params)
        return ThreadListResponse.model_validate(result)

    async def thread_loaded_list(
        self,
        *,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> ThreadLoadedListResponse:
        """List thread IDs currently loaded in memory.

        Args:
            cursor: Opaque pagination cursor from previous response
            limit: Maximum number of thread IDs to return

        Returns:
            ThreadLoadedListResponse with data (list of thread IDs) and next_cursor
        """
        params = ThreadLoadedListParams(cursor=cursor, limit=limit)
        result = await self.dispatch.send_request("thread/loaded/list", params)
        return ThreadLoadedListResponse.model_validate(result)

    # ========================================================================
    # Model methods
    # ========================================================================

    async def model_list(
        self,
        *,
        include_hidden: bool | None = None,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> ModelListResponse:
        """List available models with reasoning effort options.

        Args:
            include_hidden: When true, include hidden models
            cursor: Opaque pagination cursor from previous response
            limit: Maximum number of models to return

        Returns:
            ModelListResponse with data (list of models) and next_cursor
        """
        params = ModelListParams(include_hidden=include_hidden, cursor=cursor, limit=limit)
        result = await self.dispatch.send_request("model/list", params)
        return ModelListResponse.model_validate(result)

    async def collaboration_mode_list(self) -> list[CollaborationModeMask]:
        """List available collaboration mode presets (experimental).

        Returns:
            List of collaboration mode presets with name, mode, model, and effort
        """
        result = await self.dispatch.send_request("collaborationMode/list")
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
        sandbox_policy: SandboxPolicy | None = None,
        output_bytes_cap: int | None = None,
        timeout_ms: int | None = None,
        permission_profile: PermissionProfile | None = None,
    ) -> CommandExecResponse:
        """Execute a command without creating a thread/turn.

        Args:
            command: Command and arguments as list (e.g., ["ls", "-la"])
            cwd: Working directory for command
            sandbox_policy: Sandbox policy override
            output_bytes_cap: Cap output based on bytes
            timeout_ms: Timeout in milliseconds
            permission_profile: Permission profile override

        Returns:
            CommandExecResponse with exit_code, stdout, stderr
        """
        params = CommandExecParams(
            command=command,
            cwd=cwd,
            output_bytes_cap=output_bytes_cap,
            sandbox_policy=sandbox_policy,
            timeout_ms=timeout_ms,
            permission_profile=permission_profile,
        )
        result = await self.dispatch.send_request("command/exec", params)
        return CommandExecResponse.model_validate(result)

    # ========================================================================
    # MCP server methods
    # ========================================================================

    async def mcp_server_refresh(self) -> None:
        """Reload MCP server configurations from disk."""
        await self.dispatch.send_request("config/mcpServer/reload")

    async def mcp_server_status_list(
        self,
        *,
        detail: McpServerStatusDetail | None = None,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> ListMcpServerStatusResponse:
        """List MCP server status with tool and resource information.

        Args:
            detail: Level of detail to include in the response
            cursor: Pagination cursor from previous call
            limit: Maximum number of servers to return

        Returns:
            Response with server status entries and optional next_cursor
        """
        params = ListMcpServerStatusParams(cursor=cursor, limit=limit, detail=detail)
        result = await self.dispatch.send_request("mcpServerStatus/list", params)
        return ListMcpServerStatusResponse.model_validate(result)

    async def mcp_server_oauth_login(
        self,
        name: str,
        *,
        scopes: list[str] | None = None,
        timeout_secs: int | None = None,
    ) -> str:
        """Start OAuth login for an MCP server.

        Args:
            name: Name of the MCP server
            scopes: Optional OAuth scopes to request
            timeout_secs: Optional timeout in seconds

        Returns:
            Authorization URL
        """
        params = McpServerOauthLoginParams(name=name, scopes=scopes, timeout_secs=timeout_secs)
        result = await self.dispatch.send_request("mcpServer/oauth/login", params)
        response = McpServerOauthLoginResponse.model_validate(result)
        return response.authorization_url

    async def read_resource(self, server: str, uri: str) -> list[ResourceContents]:
        """Read a resource from the MCP server."""
        params = McpResourceReadParams(server=server, uri=uri)
        result = await self.dispatch.send_request("mcpServer/resource/read", params)
        data = McpResourceReadResponse.model_validate(result)
        ta = TypeAdapter[ResourceContents](ResourceContents)

        def convert(old: BaseModel) -> ResourceContents:
            dct = old.model_dump()
            dct["_meta"] = dct.pop("field_meta")
            return ta.validate_python(dct)

        return [convert(i) for i in data.contents]

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
        result = await self.dispatch.send_request("config/read", params)
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
        result = await self.dispatch.send_request("config/value/write", params)
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
        result = await self.dispatch.send_request("config/batchWrite", params)
        return ConfigWriteResponse.model_validate(result)

    async def config_requirements_read(self) -> ConfigRequirements | None:
        """Read config requirements."""
        result = await self.dispatch.send_request("configRequirements/read")
        response = ConfigRequirementsReadResponse.model_validate(result)
        return response.requirements

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
        result = await self.dispatch.send_request("app/list", params)
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
        result = await self.dispatch.send_request("experimentalFeature/list", params)
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
        tags: dict[str, Any] | None = None,
        include_logs: bool = False,
        extra_log_files: list[str] | None = None,
    ) -> str:
        """Upload feedback.

        Args:
            classification: Feedback classification
            reason: Optional reason text
            thread_id: Optional thread ID to associate
            tags: Optional tags to associate with the feedback
            include_logs: Whether to include logs
            extra_log_files: Additional log files to include

        Returns:
            thread ID
        """
        params = FeedbackUploadParams(
            classification=classification,
            reason=reason,
            thread_id=thread_id,
            tags=tags,
            include_logs=include_logs,
            extra_log_files=extra_log_files,
        )
        result = await self.dispatch.send_request("feedback/upload", params)
        response = FeedbackUploadResponse.model_validate(result)
        return response.thread_id

    # ========================================================================
    # External agent config methods
    # ========================================================================

    async def external_agent_config_detect(
        self,
        *,
        include_home: bool | None = None,
        cwds: list[str] | None = None,
    ) -> list[ExternalAgentConfigMigrationItem]:
        """Detect external agent configurations.

        Args:
            include_home: Include detection under user's home directory
            cwds: Working directories for repo-scoped detection

        Returns:
            ExternalAgentConfigDetectResponse with migration items
        """
        params = ExternalAgentConfigDetectParams(include_home=include_home, cwds=cwds)
        result = await self.dispatch.send_request("externalAgentConfig/detect", params)
        response = ExternalAgentConfigDetectResponse.model_validate(result)
        return response.items

    async def external_agent_config_import(
        self,
        migration_items: list[ExternalAgentConfigMigrationItem],
    ) -> None:
        """Import external agent configurations.

        Args:
            migration_items: List of migration items to import
        """
        params = ExternalAgentConfigImportParams(migration_items=migration_items)
        await self.dispatch.send_request("externalAgentConfig/import", params)

    # ========================================================================
    # Internal: JSON-RPC dispatch callbacks
    # ========================================================================

    async def _handle_notification(self, method: str, params: dict[str, Any]) -> None:
        """Route a JSON-RPC notification to the appropriate event queue."""
        if method.startswith("codex/event/"):
            return

        event_data = {"method": method, "params": params}
        event = codex_event_adapter.validate_python(event_data)

        thread_id = params.get("threadId")

        # Route realtime events to the realtime session queue
        if method.startswith("thread/realtime/") and thread_id:
            rt_key = f"realtime:{thread_id}"
            queue = self._realtime_queues.get(rt_key)
            await (queue or self._event_queue).put(event)
            return

        turn_id = params.get("turnId")
        if not turn_id and "turn" in params:
            turn_id = params.get("turn", {}).get("id")

        if thread_id and turn_id:
            turn_key = f"{thread_id}:{turn_id}"
            queue = self._turn_queues.get(turn_key)
            await (queue or self._event_queue).put(event)
        else:
            await self._event_queue.put(event)

    async def _handle_server_request(
        self, method: str, request_id: int | str, params: dict[str, Any]
    ) -> None:
        """Handle a server-initiated JSON-RPC request."""
        type_entry = SERVER_REQUEST_TYPES.get(method)
        if type_entry is None:
            logger.warning("Unhandled server request method: %s (id=%s)", method, request_id)
            await self.dispatch.send_error(request_id, -32601, f"Method not found: {method}")
            return

        handler = self._server_request_handlers.get(method)
        if handler is None:
            logger.warning("No handler registered for request: %s (id=%s)", method, request_id)
            await self.dispatch.send_error(request_id, -32603, f"No handler for: {method}")
            return

        params_type, _ = type_entry
        try:
            if isinstance(params_type, TypeAdapter):
                parsed_params = params_type.validate_python(params)
            else:
                parsed_params = params_type.model_validate(params)
            response_model = await handler(parsed_params)
            result = response_model.model_dump(by_alias=True, exclude_none=True)
            await self.dispatch.send_response(request_id, result)
        except Exception:
            logger.exception("Error handling server request %s (id=%s)", method, request_id)
            await self.dispatch.send_error(request_id, -32603, f"Internal error handling {method}")

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

    async def reset_memory(self) -> MemoryResetResponse:
        """Reset the app-server memory."""
        response = await self.dispatch.send_request("memory/reset")
        return MemoryResetResponse.model_validate(response)

    async def warning(self, message: str) -> None:
        """Send a warning message to the app-server."""
        params = WarningNotification(message=message)
        await self.dispatch.send_request("warning", params)


if __name__ == "__main__":

    async def main() -> None:
        async with CodexClient() as client:
            session = await client.thread_start()
            async for e in session.turn_stream("Show available tools"):
                print(e)

    import asyncio

    asyncio.run(main())
