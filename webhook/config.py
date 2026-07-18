from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent.parent / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="forbid",
    )

    WEBHOOK_URL: str
    WATCH_FOLDER_ID: str
    GCP_PROJECT_ID: str = ""

    TRELLO_API_KEY: str
    TRELLO_API_SECRET: str
    TRELLO_BOARD_ID: str


settings = Settings()
