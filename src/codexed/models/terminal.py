"""Interactive terminal control models for the Codex app-server protocol.

These models support the interactive PTY/streaming mode of `command/exec`.
After starting a command with `stream_stdin=True` or `tty=True`, use
`command/exec/write` to send stdin, `command/exec/resize` to resize the PTY,
and `command/exec/terminate` to kill the process. Output arrives as
`command/exec/outputDelta` notifications.
"""

from __future__ import annotations

from typing import Literal

from codexed.models.base import CodexBaseModel


# ============================================================================
# Supporting types
# ============================================================================

CommandExecOutputStream = Literal["stdout", "stderr"]
"""Stream label for command/exec output delta notifications."""


class CommandExecTerminalSize(CodexBaseModel):
    """PTY size in character cells."""

    rows: int
    cols: int


# ============================================================================
# Client request params / responses
# ============================================================================


class CommandExecWriteParams(CodexBaseModel):
    """Params for command/exec/write request — write stdin to a running process."""

    process_id: str
    delta_base64: str | None = None
    close_stdin: bool = False


class CommandExecWriteResponse(CodexBaseModel):
    """Response for command/exec/write request."""


class CommandExecTerminateParams(CodexBaseModel):
    """Params for command/exec/terminate request — kill a running process."""

    process_id: str


class CommandExecTerminateResponse(CodexBaseModel):
    """Response for command/exec/terminate request."""


class CommandExecResizeParams(CodexBaseModel):
    """Params for command/exec/resize request — resize a PTY session."""

    process_id: str
    size: CommandExecTerminalSize


class CommandExecResizeResponse(CodexBaseModel):
    """Response for command/exec/resize request."""


# ============================================================================
# Server notification data
# ============================================================================


class CommandExecOutputDeltaData(CodexBaseModel):
    """Data for command/exec/outputDelta notification.

    Base64-encoded output chunk emitted for a streaming command/exec request.
    """

    process_id: str
    stream: CommandExecOutputStream
    delta_base64: str
    cap_reached: bool
