"""Example usage of the Codex adapter."""

from __future__ import annotations

import asyncio
import sys
from typing import TYPE_CHECKING, Any

from codexed import CodexClient
from codexed.models.events import (
    ItemAgentMessageDeltaNotification,
    ItemCommandExecutionOutputDeltaNotification,
    TurnCompletedEvent,
)


if TYPE_CHECKING:
    from collections.abc import Callable


async def simple_chat() -> None:
    """Simple single-turn chat example."""
    print("=== Simple Chat Example ===\n")

    async with CodexClient() as client:
        # Start a thread
        session = await client.thread_start(cwd=".", experimental_raw_events=True)
        print(f"Started thread: {session.thread_id}\n")
        # Send a message
        message = "List the Python files in the current directory"
        print(f"> {message}\n")
        async for event in session.turn_stream(message):
            # Print agent messages
            match event:
                case ItemAgentMessageDeltaNotification(params=params):
                    print(params.delta, end="", flush=True)
                case ItemCommandExecutionOutputDeltaNotification(params=params):
                    print(f"\n[Command output]\n{params.delta}", flush=True)
                case TurnCompletedEvent():
                    print("\n\n[Turn completed]")
                    break


async def multi_turn_chat() -> None:
    """Multi-turn conversation example."""
    print("=== Multi-Turn Chat Example ===\n")

    async with CodexClient() as client:
        session = await client.thread_start(cwd=".", model="gpt-5-codex")

        messages = [
            "What is the main purpose of this codebase?",
            "Show me the entry point file",
            "What dependencies does it use?",
        ]

        for i, message in enumerate(messages, 1):
            print(f"\n--- Turn {i} ---")
            print(f"> {message}\n")

            async for event in session.turn_stream(message):
                match event:
                    case ItemAgentMessageDeltaNotification(params=params):
                        print(params.delta, end="", flush=True)
                    case TurnCompletedEvent():
                        print("\n")
                        break


async def model_override_example() -> None:
    """Example showing per-turn model override."""
    print("=== Model Override Example ===\n")

    async with CodexClient() as client:
        session = await client.thread_start(model="gpt-5-codex")

        # First turn with default model
        print("Turn 1 (default model: gpt-5-codex)")
        print("> Write a hello world function\n")

        async for event in session.turn_stream("Write a hello world function"):
            match event:
                case ItemAgentMessageDeltaNotification(params=data):
                    print(data.delta, end="", flush=True)
                case TurnCompletedEvent():
                    print("\n")
                    break

        # Second turn with different model
        print("\nTurn 2 (override to claude-opus-4, high effort)")
        print("> Now make it more elegant\n")

        async for event in session.turn_stream(
            "Now make it more elegant",
            model="claude-opus-4",
            effort="high",
        ):
            match event:
                case ItemAgentMessageDeltaNotification(params=data):
                    print(data.delta, end="", flush=True)
                case TurnCompletedEvent():
                    print("\n")
                    break


async def event_inspection_example() -> None:
    """Example showing detailed event inspection."""
    print("=== Event Inspection Example ===\n")

    async with CodexClient() as client:
        session = await client.thread_start(cwd=".", experimental_raw_events=True)

        async for event in session.turn_stream("What files are here?"):
            # Print all event types
            print(f"[{event.method}]", end=" ")
            print(event)


async def main() -> None:
    """Run all examples."""
    examples: list[tuple[str, Callable[[], Any]]] = [
        # ("Simple Chat", simple_chat),
        # ("Multi-Turn Chat", multi_turn_chat),
        # ("Model Override", model_override_example),
        ("Event Inspection", event_inspection_example),
    ]

    if len(sys.argv) > 1:
        # Run specific example by number
        try:
            idx = int(sys.argv[1]) - 1
            if 0 <= idx < len(examples):
                name, func = examples[idx]
                print(f"Running: {name}\n")
                await func()
            else:
                print(f"Invalid example number. Choose 1-{len(examples)}")
        except ValueError:
            print("Usage: python example.py [example_number]")
    else:
        # Run all examples
        print("Codex Adapter Examples")
        print("=" * 50)
        print("Running all examples...\n")

        for i, (name, func) in enumerate(examples, 1):
            print(f"\n{'=' * 50}")
            print(f"Example {i}: {name}")
            print("=" * 50)
            await func()


if __name__ == "__main__":
    asyncio.run(main())
