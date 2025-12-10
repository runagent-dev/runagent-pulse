"""Centralized application settings loaded from environment."""
from typing import List, Optional
import logging

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    api_key: str = Field("", env="PULSE_API_KEY")
    db_path: str = Field("/app/data/pulse.db", env="PULSE_DB_PATH")
    timezone: str = Field("UTC", env="PULSE_TIMEZONE")
    debug: bool = Field(False, env="PULSE_DEBUG")
    webhook_default_timeout: int = Field(30, env="PULSE_WEBHOOK_TIMEOUT")
    webhook_default_retries: int = Field(3, env="PULSE_WEBHOOK_RETRIES")
    webhook_worker_interval: int = Field(10, env="PULSE_WEBHOOK_INTERVAL")
    host: str = Field("0.0.0.0", env="PULSE_HOST")
    port: int = Field(8000, env="PULSE_PORT")
    cors_allow_origins: List[str] = Field(default_factory=lambda: ["*"], env="PULSE_CORS_ORIGINS")
    enable_serverless_integration: bool = Field(True, env="ENABLE_SERVERLESS_INTEGRATION")
    runagent_serverless_api_key: Optional[str] = Field(None, env="RUNAGENT_SERVERLESS_API_KEY")
    local_agent_path: Optional[str] = Field(None, env="LOCAL_AGENT_PATH")
    default_executor: str = Field("auto", env="DEFAULT_EXECUTOR")  # "auto", "serverless", or "local"

    @property
    def log_level(self) -> int:
        return logging.DEBUG if self.debug else logging.INFO


def get_settings() -> Settings:
    """Factory to load settings from environment."""
    return Settings()  # type: ignore[arg-type]


