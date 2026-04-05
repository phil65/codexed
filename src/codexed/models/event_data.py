from __future__ import annotations

from codexed.models.base import CodexBaseModel
from codexed.models.misc import Thread, Turn
from codexed.models.thread_item import ThreadItem


# Item lifecycle notifications


class ItemStartedData(CodexBaseModel):
    """Payload for item/started notification (V2 protocol)."""

    thread_id: str
    turn_id: str
    item: ThreadItem


class ItemCompletedData(CodexBaseModel):
    """Payload for item/completed notification (V2 protocol)."""

    thread_id: str
    turn_id: str
    item: ThreadItem


class ThreadStartedData(CodexBaseModel):
    """Payload for thread/started notification (V2 protocol)."""

    thread: Thread

    @property
    def thread_id(self) -> str:
        """Thread ID derived from the thread object."""
        return self.thread.id


# Turn lifecycle notifications


class TurnStartedData(CodexBaseModel):
    """Payload for turn/started notification (V2 protocol)."""

    thread_id: str
    turn: Turn


class TurnCompletedData(CodexBaseModel):
    """Payload for turn/completed notification (V2 protocol)."""

    thread_id: str
    turn: Turn
