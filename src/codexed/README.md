# Codex Adapter

Python adapter for the [Codex](https://github.com/openai/codex) app-server JSON-RPC protocol.

## Quick Start

```python
import asyncio
from codexed import CodexClient
from codexed.models import ItemAgentMessageDeltaNotification, TurnCompletedEvent

async def main():
    async with CodexClient() as client:
        session = await client.thread_start(cwd="/path/to/project")
        
        async for event in session.turn_stream("Help me refactor this code"):
            match event:
                case ItemAgentMessageDeltaNotification(data=data):
                    print(data.delta, end="", flush=True)
                case TurnCompletedEvent():
                    break

asyncio.run(main())
```

## Structured Responses

```python
from pydantic import BaseModel

class FileList(BaseModel):
    files: list[str]
    total: int

async with CodexClient() as client:
    session = await client.thread_start(cwd=".")
    result = await session.turn_stream_structured(
        "List Python files",
        FileList,
    )
    print(result.files)  # Typed result
```

## Events

Events are a discriminated union. Use pattern matching or helper functions:

```python
from codexed.models import (
    ItemAgentMessageDeltaNotification,
    ItemCommandExecutionOutputDeltaNotification,
    TurnCompletedEvent,
)

async for event in session.turn_stream(message):
    match event:
        case ItemAgentMessageDeltaNotification(data=data) | ItemCommandExecutionOutputDeltaNotification(data=data):
            print(data.delta, end="")
        case TurnCompletedEvent():
            break

```

## See Also

- [Codex app-server docs](https://github.com/openai/codex/blob/main/codex-rs/app-server/README.md)
