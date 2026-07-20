"""Test-only governed clock. Forbidden outside ENGINE_ENV=test."""

from __future__ import annotations

import os
from datetime import datetime, timedelta

from intelligence_maxxxing.application.ports.clock import ClockPort
from intelligence_maxxxing.domain.common.base import utc_now


class ControlledTestClock(ClockPort):
    """Mutable clock for Stage 3.1 canaries and unit tests.

    Not part of the public SDK. Must not be constructed when ENGINE_ENV is
    production/staging/development unless explicitly set to ``test``.
    """

    def __init__(self, start: datetime | None = None) -> None:
        env = (os.environ.get("ENGINE_ENV") or "").strip().lower()
        if env != "test":
            raise RuntimeError(
                "ControlledTestClock is only available when ENGINE_ENV=test; "
                f"got ENGINE_ENV={env!r}"
            )
        self._now = start or utc_now()

    def now(self) -> datetime:
        return self._now

    def advance(self, *, days: int = 0, hours: int = 0, minutes: int = 0, seconds: int = 0) -> datetime:
        self._now = self._now + timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)
        return self._now

    def set(self, value: datetime) -> None:
        self._now = value
