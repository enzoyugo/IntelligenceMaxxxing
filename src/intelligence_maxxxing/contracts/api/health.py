"""Public contract for GET /api/v1/health."""

from pydantic import BaseModel, ConfigDict


class HealthData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    service: str
    engine_version: str
    constitution_version: str
