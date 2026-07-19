"""Environment-driven settings. Secrets never live in code."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class EngineSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    engine_env: str = Field(default="development", alias="ENGINE_ENV")
    engine_host: str = Field(default="127.0.0.1", alias="ENGINE_HOST")
    engine_port: int = Field(default=8100, alias="ENGINE_PORT")
    engine_version: str = Field(default="0.1.0", alias="ENGINE_VERSION")
    constitution_version: str = Field(default="1.1", alias="CONSTITUTION_VERSION")
    database_url: str = Field(
        default="postgresql+psycopg://intelligence:intelligence@127.0.0.1:5432/intelligence_maxxxing",
        alias="DATABASE_URL",
    )
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")


@lru_cache(maxsize=1)
def get_settings() -> EngineSettings:
    return EngineSettings()
