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

    DRIVE_WEBHOOK_URL: str
    TOPIC_BLUEPRINT_PUSH_URL: str
    TRELLO_WEBHOOK_URL: str
    WATCH_FOLDER_ID: str
    GCP_PROJECT_ID: str = ""

    ENVIRONMENT: str

    WATCH_FOLDER_LOCAL: str = "/tmp/blueprints"

    TRELLO_API_TOKEN: str
    TRELLO_API_KEY: str
    TRELLO_API_SECRET: str = ""
    TRELLO_BOARD_ID: str


settings = Settings()
