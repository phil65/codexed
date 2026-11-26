"""StdioTransport's Windows branch, with the platform faked."""

import signal

import pytest

from codexed import transport as transport_module
from codexed.transport import StdioTransport


class ExitedProcess:
    """Like asyncio's Process after exit: terminate() and kill() raise."""

    returncode = 0
    pid = 12345

    def terminate(self) -> None:
        raise ProcessLookupError

    def kill(self) -> None:
        raise ProcessLookupError


@pytest.mark.parametrize("sig", [signal.SIGTERM, getattr(signal, "SIGKILL", signal.SIGTERM)])
def test_signalling_an_exited_server_on_windows_is_a_no_op(
    monkeypatch: pytest.MonkeyPatch, sig: int
) -> None:
    monkeypatch.setattr(transport_module.sys, "platform", "win32")
    StdioTransport("codex")._signal_group(ExitedProcess(), sig)  # type: ignore[arg-type]
