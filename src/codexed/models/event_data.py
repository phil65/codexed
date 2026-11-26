from pydantic import Field

from codexed.models.base import CodexBaseModel
from codexed.models.misc import Thread, Turn
from codexed.models.thread_item import ThreadItem


# Item lifecycle notifications


class ItemStartedData(CodexBaseModel):
    """Payload for item/started notification (V2 protocol)."""

    thread_id: str
    turn_id: str
    item: ThreadItem
    started_at_ms: int
    """Unix timestamp (in milliseconds) when this item lifecycle started."""


class ItemCompletedData(CodexBaseModel):
    """Payload for item/completed notification (V2 protocol)."""

    thread_id: str
    turn_id: str
    item: ThreadItem
    completed_at_ms: int
    """Unix timestamp (in milliseconds) when this item lifecycle completed."""
    content_token_count: int | None = Field(default=None, ge=0)
    """Token count of the item's content, if known."""


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
