"""Rate limits from account/rateLimits/updated, and events outside turns."""

from typing import Any

from codexed import CodexClient
from codexed.models import AccountRateLimitsUpdatedMessage


SNAPSHOT = {
    "limitId": "codex",
    "planType": "pro",
    "primary": {"usedPercent": 42, "windowDurationMins": 300, "resetsAt": 1795170000},
    "secondary": {"usedPercent": 7, "windowDurationMins": 10080, "resetsAt": 1795700000},
}


async def test_rate_limit_updates_are_recorded_and_passed_to_listeners() -> None:
    client = CodexClient()
    received: list[Any] = []
    client.add_event_listener(received.append)
    await client._handle_notification("account/rateLimits/updated", {"rateLimits": SNAPSHOT})
    snapshot = client.account.rate_limits
    assert snapshot is not None
    assert snapshot.primary is not None
    assert (snapshot.primary.used_percent, snapshot.plan_type) == (42, "pro")
    (event,) = received
    assert isinstance(event, AccountRateLimitsUpdatedMessage)
    client.remove_event_listener(received.append)
    await client._handle_notification("account/rateLimits/updated", {"rateLimits": SNAPSHOT})
    assert len(received) == 1


async def test_async_listener_and_failing_listener() -> None:
    client = CodexClient()
    received: list[Any] = []

    def broken(_event: Any) -> None:
        raise RuntimeError("boom")

    async def collect(event: Any) -> None:
        received.append(event)

    client.add_event_listener(broken)
    client.add_event_listener(collect)
    await client._handle_notification("account/rateLimits/updated", {"rateLimits": SNAPSHOT})
    assert len(received) == 1  # A failing listener does not stop the others
