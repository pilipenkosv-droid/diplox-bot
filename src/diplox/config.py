"""Application configuration using Pydantic Settings."""

import functools
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    telegram_bot_token: str = Field(description="Telegram Bot API token")
    deepgram_api_key: str = Field(description="Deepgram API key for transcription")
    gemini_api_key: str = Field(description="Google AI Studio API key for Gemini Flash")
    anthropic_api_key: str = Field(description="Anthropic API key for Claude Haiku")
    admin_api_key: str = Field(default="", description="API key for admin endpoints")
    admin_telegram_id: int = Field(default=0, description="Admin Telegram ID for alerts")

    data_dir: Path = Field(
        default=Path("./data"),
        description="Root directory for vaults and database",
    )
    webapp_host: str = Field(default="0.0.0.0", description="FastAPI host")
    webapp_port: int = Field(default=8080, description="FastAPI port")
    bot_url: str = Field(
        default="https://t.me/diploxsbot",
        description="Bot URL for deep links",
    )
    landing_url: str = Field(
        default="https://diplox.online",
        description="Landing page URL",
    )

    @property
    def db_path(self) -> Path:
        return self.data_dir / "diplox.db"

    @property
    def vaults_dir(self) -> Path:
        return self.data_dir / "vaults"


@functools.lru_cache
def get_settings() -> Settings:
    """Get cached application settings instance."""
    return Settings()
