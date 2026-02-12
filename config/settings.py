"""Application settings using Pydantic."""

import os
from pathlib import Path
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
    # Локально: sqlite:///./vacancies.db
    # Временно: USE_SQLITE=1 — использовать SQLite даже если есть DATABASE_URL (для деплоя пока не настроен PostgreSQL)
    database_url: str = Field(
        default="sqlite:///./vacancies.db",
        alias="DATABASE_URL"
    )
    use_sqlite: bool = Field(default=False, alias="USE_SQLITE")  # Установите 1 чтобы принудительно использовать SQLite
    
    def get_database_path(self) -> str:
        """Get database file path, ensuring directory exists."""
        # Parse database URL
        if self.database_url.startswith("sqlite:///"):
            db_path = self.database_url.replace("sqlite:///", "")
        else:
            db_path = "./vacancies.db"
        
        # Ensure directory exists
        db_dir = Path(db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)
        
        return db_path

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
