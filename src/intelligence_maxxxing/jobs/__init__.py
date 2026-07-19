"""Async jobs (Engine Service Contract §4.2).

Stage 0 status: CONTRACT_ONLY. The interface exists so the queue technology
stays behind an internal boundary; no worker or queue is implemented yet.
"""

from abc import ABC, abstractmethod
from enum import StrEnum


class JobState(StrEnum):
    SUBMITTED = "SUBMITTED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class JobQueuePort(ABC):
    """Future durable job queue. Submissions must be idempotent."""

    @abstractmethod
    def submit(self, job_type: str, payload: dict[str, object], idempotency_key: str) -> str:
        """Return a job_id. Same idempotency key must not create a second job."""

    @abstractmethod
    def get_state(self, job_id: str) -> JobState: ...

    @abstractmethod
    def cancel(self, job_id: str) -> None: ...
