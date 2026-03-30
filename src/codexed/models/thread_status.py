from __future__ import annotations

from codexed.models.v2_protocol import (
    ActiveThreadStatus,
    IdleThreadStatus,
    NotLoadedThreadStatus,
    SystemErrorThreadStatus,
)


ThreadStatusValue = (
    NotLoadedThreadStatus | IdleThreadStatus | SystemErrorThreadStatus | ActiveThreadStatus
)
