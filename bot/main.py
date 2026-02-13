"""Main entry point for the bot."""

import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.logging_config import setup_logging, get_logger
from config.settings import settings
from database.base import init_db
from bot.application import BotApplication
from bot.health_server import start_health_server

logger = get_logger(__name__)


def main() -> None:
    """Main function."""
    # Setup logging
    setup_logging(settings.log_level)
    logger.info("Starting Telegram bot...")

    # Start health check server FIRST — App Platform проверяет порт до завершения init_db
    port = int(os.getenv("PORT", os.getenv("HEALTH_CHECK_PORT", "8080")))
    start_health_server(port)
    logger.info(f"Health check server started on port {port}")

    # Initialize database (может занять время — health уже отвечает)
    logger.info("Initializing database...")
    try:
        init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Error initializing database: {e}", exc_info=True)
        raise

    # Create and run bot
    try:
        bot_app = BotApplication()
        bot_app.run()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error("Bot error", exc_info=e)
        # Check if it's a network error
        error_str = str(e).lower()
        if "network" in error_str or "connect" in error_str or "nodename" in error_str:
            logger.error(
                "Network error: Cannot connect to Telegram API. "
                "Please check your internet connection and try again."
            )
        raise


if __name__ == "__main__":
    main()
