"""Governed clock port for epistemic temporal rules."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime


class ClockPort(ABC):
    """Authoritative clock for Engine use cases. Never trust client wall time alone."""

    @abstractmethod
    def now(self) -> datetime:
        """Return timezone-aware UTC datetime."""
