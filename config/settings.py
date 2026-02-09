"""Application settings using Pydantic."""

from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Telegram Bot
    bot_token: str = Field(..., alias="BOT_TOKEN")

    # Database
    database_url: str = Field(default="sqlite:///./vacancies.db", alias="DATABASE_URL")

    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Admin IDs (comma-separated string)
    admin_ids: str = Field(default="", alias="ADMIN_IDS")

    # Monitoring
    default_monitoring_interval_hours: int = Field(
        default=3, alias="DEFAULT_MONITORING_INTERVAL_HOURS"
    )

    # Parser rate limiting (to avoid IP bans)
    parser_delay_between_requests: float = Field(
        default=2.0, alias="PARSER_DELAY_BETWEEN_REQUESTS"
    )  # Seconds between requests
    parser_delay_between_pages: float = Field(
        default=3.0, alias="PARSER_DELAY_BETWEEN_PAGES"
    )  # Seconds between page requests
    parser_max_concurrent_requests: int = Field(
        default=1, alias="PARSER_MAX_CONCURRENT_REQUESTS"
    )  # Max concurrent requests (1 = sequential)

    @property
    def admin_ids_list(self) -> List[int]:
        """Parse admin IDs from comma-separated string."""
        if not self.admin_ids:
            return []
        return [int(admin_id.strip()) for admin_id in self.admin_ids.split(",") if admin_id.strip()]


# Global settings instance
settings = Settings()
