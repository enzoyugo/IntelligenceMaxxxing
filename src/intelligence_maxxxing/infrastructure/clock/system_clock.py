"""Production/runtime clock — always wall UTC."""

from __future__ import annotations

from datetime import datetime

from intelligence_maxxxing.application.ports.clock import ClockPort
from intelligence_maxxxing.domain.common.base import utc_now


class SystemClock(ClockPort):
    def now(self) -> datetime:
        return utc_now()
