# AGENTS.md

## Overview

`codexed` is an async Python client for the [Codex](https://github.com/openai/codex)
`app-server` JSON-RPC protocol. It spawns `codex app-server` (or connects to a remote one over
WebSocket), exposes thread/turn operations as typed async methods and streams server
notifications as a pydantic discriminated union of events. It is a dependency of `agentpool`,
so treat the public API (`codexed/__init__.py`, `codexed.models`) as stable.

## Architecture

Layers, bottom to top:

- `src/codexed/transport.py`: `Transport` protocol plus `StdioTransport` (subprocess via
  `anyenv.create_process`, MCP servers passed as `--config` TOML strings) and `WebSocketTransport`
  (optional `websockets` extra). Newline-delimited JSON in both directions.
- `src/codexed/client/dispatch.py`: `Dispatch`, the domain-free JSON-RPC layer: read loop,
  request id / future correlation, routes notifications and server-initiated requests to callbacks.
  Errors are mapped by `exceptions.map_jsonrpc_error`.
- `src/codexed/client/client.py`: `CodexClient` (async context manager; sends `initialize` on enter).
  Global methods (`thread_start/resume/fork/list`, `model_list`, `config_*`, `command_exec`,
  `mcp_server_*`, `apps_list`, ...). `_handle_notification` validates every notification with
  `codex_event_adapter` and puts it on the queue keyed `"{thread_id}:{turn_id}"` (or
  `"realtime:{thread_id}"`); events without a running turn go to `add_event_listener` callbacks.
  `_handle_server_request` answers approval / user-input / dynamic-tool / elicitation requests via
  handlers registered with `register_handler` (types in `request_handlers.py`).
- Sub-APIs hung off the client: `client.account` (`client/account.py`, also caches the latest
  rate-limit snapshot), `client.fs`, `client.plugins`, `client.marketplace`, `client.skills`.
- `src/codexed/client/session.py`: `Session`, a per-thread handle returned by `thread_start` etc.
  `turn_stream()` is an async generator that starts a turn, yields events from its queue until
  `TurnCompletedEvent`, raises `TurnFailedError` on `ErrorMessage`, and records token usage in
  `session.usage`. `turn_stream_structured()` passes a pydantic model as output schema and parses
  `turn.final_response`. Also review, fork, revert, inject items, MCP tool calls, realtime.
- `src/codexed/client/realtime.py`: `RealtimeSession` (audio/text realtime API).

Models (`src/codexed/models/`):

- `v2_protocol.py`: ~13k lines **generated** from the Codex JSON schema by
  `scripts/generate_codex_reference_models.py`. Excluded from ruff and ty. Do not hand-edit;
  regenerate (needs the `codex` CLI and `datamodel-codegen`).
- `events.py`: hand-written event classes and the `CodexEvent` union / `codex_event_adapter`,
  discriminated on `method`. Every event's payload is in **`params`** (not `data`).
- `event_data.py`, `thread_item.py`, `misc.py`, `responses.py`, `request_params.py`: hand-written
  models that override or extend generated ones. `models/__init__.py` re-exports everything.
- `tool_config.py`: builtin tool configs (`ToolConfig` union, `tools_to_config_dict`),
  `mcp_server.py`: `StdioMcpServer` / `HttpMcpServer` (+ `to_config_toml`).
- `base.py`: `CodexBaseModel` (camelCase aliases, `populate_by_name`; `extra="forbid"` when
  pytest is imported, `"ignore"` otherwise).

## Where to look

| Task | Location |
| --- | --- |
| New app-server request method | `client/client.py` (global) or `client/session.py` (thread-scoped) |
| New notification / event type | `models/events.py` (add to `CodexEvent`), re-export in `models/__init__.py` |
| Protocol schema update | `scripts/generate_codex_reference_models.py` -> `models/v2_protocol.py` |
| Approval / server-request handling | `request_handlers.py`, `CodexClient._handle_server_request` |
| Error mapping / retryability | `exceptions.py` |
| Config merging (tools, MCP, features) | `helpers.py` (`merge_config`), `models/tool_config.py` |
| Public exports | `src/codexed/__init__.py` (`__all__`) |
| Usage examples | `examples/`, `src/codexed/README.md` |

## Commands

```bash
uv sync --all-extras                 # setup (default groups: dev, lint, docs)
uv run pytest                        # tests
uvx ruff check . && uvx ruff format --check .
uv run ty check                      # must pass with no warnings
uv run deptry src                    # dependency hygiene
uv run mknodes build                 # docs (mknodes default site, slow)
uv build
```

`duties.py` wraps these (`duty test`, `duty lint`, `duty lint_check`, `duty build`, `duty update`,
`duty version <bump>`). CI (`.github/workflows/build.yml`) runs ruff, ty and pytest on
3.13/3.14 x linux/macos/windows; 3.14 is allowed to fail.

## Conventions

- Python >= 3.13, `from __future__ import annotations`, pattern matching where it fits,
  google-style docstrings without types in `Args` (see `.github/copilot-instructions.md`).
- Ruff with a broad rule set and `preview` formatting, line length 100.
- Optional method arguments are keyword-only. Protocol params are built as pydantic `*Params` models and sent with `dispatch.send_request(method, params)`, responses
  validated with the matching `*Response` model.
- Tests in `tests/`, plain functions (no classes), `asyncio_mode = "auto"`. They never start a
  real `codex` process: they call `client.dispatch._process_message`, `client._handle_notification`
  or replace `client.dispatch.send_request` with a fake.

## Specs

| Spec | URL | Targets | Code | Update check |
|---|---|---|---|---|
| Codex app-server protocol (v2 JSON schema) | https://github.com/openai/codex/blob/main/codex-rs/app-server/README.md | codex-cli 0.169 (from commit e3b2ee2; exact patch unknown, regenerate to record it in the `v2_protocol.py` header) | `src/codexed/models/v2_protocol.py` (generated), `scripts/generate_codex_reference_models.py`, `src/codexed/client/` | `codex --version` vs. the `#   codex:` header line; https://github.com/openai/codex/releases |

## Pitfalls

- When matching events, use `Event(params=...)`. Strict `extra="forbid"` in tests means test
  payloads must match the schema exactly.
- Copier-managed project (`.copier-answers.yml`, template `copier-phil65`): `pyproject.toml`
  structure, workflows, `duties.py`, `mkdocs.yml`, `.pre-commit-config.yaml` come from the
  template. Add dependencies below the `# Only add below (Copier)` markers.
- `openai` is in the `lint` group only for the type-only import of `openai.types.responses` in
  `client/session.py`; it is not a runtime dependency.
- `websockets` is optional (`codexed[websocket]`) and imported lazily in `WebSocketTransport`.
- Pre-commit runs ruff, tombi, ty and the full test suite on every commit.
- `uv.lock` is gitignored.
