# Codexed

[![PyPI License](https://img.shields.io/pypi/l/codexed.svg)](https://pypi.org/project/codexed/)
[![Package status](https://img.shields.io/pypi/status/codexed.svg)](https://pypi.org/project/codexed/)
[![Monthly downloads](https://img.shields.io/pypi/dm/codexed.svg)](https://pypi.org/project/codexed/)
[![Distribution format](https://img.shields.io/pypi/format/codexed.svg)](https://pypi.org/project/codexed/)
[![Wheel availability](https://img.shields.io/pypi/wheel/codexed.svg)](https://pypi.org/project/codexed/)
[![Python version](https://img.shields.io/pypi/pyversions/codexed.svg)](https://pypi.org/project/codexed/)
[![Implementation](https://img.shields.io/pypi/implementation/codexed.svg)](https://pypi.org/project/codexed/)
[![Releases](https://img.shields.io/github/downloads/phil65/codexed/total.svg)](https://github.com/phil65/codexed/releases)
[![Github Contributors](https://img.shields.io/github/contributors/phil65/codexed)](https://github.com/phil65/codexed/graphs/contributors)
[![Github Forks](https://img.shields.io/github/forks/phil65/codexed)](https://github.com/phil65/codexed/forks)
[![Github Issues](https://img.shields.io/github/issues/phil65/codexed)](https://github.com/phil65/codexed/issues)
[![Github Issues](https://img.shields.io/github/issues-pr/phil65/codexed)](https://github.com/phil65/codexed/pulls)
[![Github Watchers](https://img.shields.io/github/watchers/phil65/codexed)](https://github.com/phil65/codexed/watchers)
[![Github Stars](https://img.shields.io/github/stars/phil65/codexed)](https://github.com/phil65/codexed/stars)
[![Github Repository size](https://img.shields.io/github/repo-size/phil65/codexed)](https://github.com/phil65/codexed)
[![Github last commit](https://img.shields.io/github/last-commit/phil65/codexed)](https://github.com/phil65/codexed/commits)
[![Github release date](https://img.shields.io/github/release-date/phil65/codexed)](https://github.com/phil65/codexed/releases)
[![Github language count](https://img.shields.io/github/languages/count/phil65/codexed)](https://github.com/phil65/codexed)
[![Github commits this month](https://img.shields.io/github/commit-activity/m/phil65/codexed)](https://github.com/phil65/codexed)
[![Package status](https://codecov.io/gh/phil65/codexed/branch/main/graph/badge.svg)](https://codecov.io/gh/phil65/codexed/)
[![PyUp](https://pyup.io/repos/github/phil65/codexed/shield.svg)](https://pyup.io/repos/github/phil65/codexed/)

[Read the documentation!](https://phil65.github.io/codexed/)

Typed, async Python client for the [Codex](https://github.com/openai/codex) `app-server`
JSON-RPC protocol. `codexed` starts `codex app-server` as a subprocess (or connects to a
remote one via WebSocket), lets you create and resume threads, run turns and stream every
server notification as a pydantic model.

## Installation

```bash
pip install codexed
# WebSocket transport for remote app-servers
pip install "codexed[websocket]"
```

The `codex` CLI must be installed and logged in for the default subprocess transport.

## Quickstart

```python
import asyncio

from codexed import CodexClient, ItemAgentMessageDeltaNotification, TurnCompletedEvent


async def main() -> None:
    async with CodexClient() as client:
        session = await client.thread_start(cwd=".")
        async for event in session.turn_stream("Summarize this repository"):
            match event:
                case ItemAgentMessageDeltaNotification(params=params):
                    print(params.delta, end="", flush=True)
                case TurnCompletedEvent():
                    print()


asyncio.run(main())
```

Events are a discriminated union (`codexed.CodexEvent`) keyed on the JSON-RPC `method`;
each event's payload lives in `.params`. `turn_stream` ends after `TurnCompletedEvent` and
raises `TurnFailedError` when the server reports an error.

### Structured output

```python
from pydantic import BaseModel


class FileList(BaseModel):
    files: list[str]
    total: int


async with CodexClient() as client:
    session = await client.thread_start(cwd=".")
    result = await session.turn_stream_structured("List the Python files", FileList)
    print(result.files)
```

### MCP servers, tools and approvals

```python
from codexed import CodexClient, HttpMcpServer, StdioMcpServer
from codexed.models.tool_config import ShellToolConfig, WebSearchToolConfig

mcp_servers = {
    "docs": HttpMcpServer(url="http://localhost:8000/mcp"),
    "fs": StdioMcpServer(command="npx", args=["-y", "@modelcontextprotocol/server-filesystem"]),
}

async with CodexClient(mcp_servers=mcp_servers) as client:
    client.set_auto_approve()  # or pass on_approval=... / on_user_input=... to CodexClient
    session = await client.thread_start(
        cwd=".",
        tools=[ShellToolConfig(), WebSearchToolConfig()],  # [] disables all builtin tools
    )
```

### Remote app-server

```python
from codexed import CodexClient, WebSocketTransport

transport = WebSocketTransport("ws://localhost:4500", auth_token="...")
async with CodexClient(transport=transport) as client:
    models = await client.model_list()
```

## Features

- Full thread lifecycle: `thread_start`, `thread_resume`, `thread_fork`, `thread_list`, plus
  per-thread `Session` operations (steer, interrupt, review, revert, compact, rename, archive,
  inject items, MCP tool calls and resource reads).
- Streaming events as typed pydantic models, token usage tracking (`session.usage`), and
  listeners for events outside a turn (`client.add_event_listener`).
- Structured output via pydantic models (`turn_stream_structured`).
- Programmatic MCP server injection (global or per thread) and builtin tool configuration.
- Server-request handlers for command/file-change/skill approvals, user input, dynamic tool
  calls and MCP elicitation.
- Sub-APIs for account and rate limits (`client.account`), file system (`client.fs`), skills,
  plugins and marketplace, config read/write, models, apps and experimental features.
- Realtime sessions (`session.realtime(...)`).
- Protocol models generated from the Codex app-server JSON schema, JSON-RPC errors mapped to
  exceptions (`CodexRequestError`, `ServerBusyError`, ..., `is_retryable_error`).

## License

MIT
