"""Main bot application."""

from telegram import Update
from telegram.ext import Application, ApplicationBuilder, CallbackContext
from telegram.error import Conflict

from config.logging_config import get_logger
from config.settings import settings
from services.monitoring_service import MonitoringService

logger = get_logger(__name__)


async def _error_handler(update: object, context: CallbackContext) -> None:
    """Handle errors. Suppress noisy Conflict logs during deployment overlap."""
    err = getattr(context, "error", None)
    if err and isinstance(err, Conflict):
        logger.warning(
            "Telegram Conflict: another instance is polling. "
            "Ensure App Platform has 1 instance. Retrying..."
        )
        return
    if err:
        logger.error("Handler error: %s", err, exc_info=err)


class BotApplication:
    """Main bot application class."""

    def __init__(self) -> None:
        """Initialize bot application."""
        self.app: Application = ApplicationBuilder().token(settings.bot_token).build()
        self.monitoring_service = MonitoringService(self)
        # Store reference to bot_application in app context
        self.app.bot_data["bot_application"] = self
        self._setup_handlers()
        self._setup_middleware()

    def _setup_handlers(self) -> None:
        """Setup command handlers."""
        from bot.handlers import start, search, filters

        # Register handlers
        self.app.add_handler(start.start_handler)
        self.app.add_handler(start.help_handler)
        self.app.add_handler(search.search_handler)
        self.app.add_handler(search.search_page_handler)
        self.app.add_handler(search.search_filter_handler)
        self.app.add_handler(search.search_manual_handler)

        # Filter handlers
        self.app.add_handler(filters.filters_handler)
        self.app.add_handler(filters.add_filter_conv_handler)
        self.app.add_handler(filters.edit_filter_conv_handler)
        self.app.add_handler(filters.filter_view_handler)
        self.app.add_handler(filters.filter_toggle_handler)
        self.app.add_handler(filters.filter_delete_confirm_handler)
        self.app.add_handler(filters.filter_delete_handler)
        self.app.add_handler(filters.filter_list_handler)

        # Monitoring handlers
        from bot.handlers import monitoring
        self.app.add_handler(monitoring.monitor_list_handler)
        self.app.add_handler(monitoring.monitor_start_handler)
        self.app.add_handler(monitoring.monitor_stop_handler)
        self.app.add_handler(monitoring.monitor_start_filter_handler)
        self.app.add_handler(monitoring.monitor_interval_handler)
        self.app.add_handler(monitoring.monitor_stop_task_handler)
        self.app.add_handler(monitoring.monitor_view_handler)
        self.app.add_handler(monitoring.monitor_run_now_handler)
        self.app.add_handler(monitoring.monitor_list_callback_handler)
        self.app.add_handler(monitoring.monitor_start_callback_handler)

        # Export handlers
        from bot.handlers import export
        self.app.add_handler(export.export_handler)
        self.app.add_handler(export.export_all_handler)
        self.app.add_handler(export.export_filter_handler)
        self.app.add_handler(export.export_filter_id_handler)
        self.app.add_handler(export.export_back_handler)

        # Stats handlers
        from bot.handlers import stats
        self.app.add_handler(stats.stats_handler)

    def _setup_middleware(self) -> None:
        """Setup middleware."""
        self.app.add_error_handler(_error_handler)

    async def post_init(self, application: Application) -> None:
        """Post initialization hook."""
        logger.info("Bot application initialized")
        # Restore monitoring tasks
        await self.monitoring_service.restore_tasks()

    async def post_shutdown(self, application: Application) -> None:
        """Post shutdown hook."""
        logger.info("Bot application shutdown")
        # Shutdown monitoring service
        await self.monitoring_service.shutdown()

    def run(self) -> None:
        """Run the bot."""
        logger.info("Starting bot application...")
        self.app.post_init = self.post_init
        self.app.post_shutdown = self.post_shutdown
        try:
            self.app.run_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True,  # Drop pending updates to avoid conflicts
            )
        except Exception as e:
            error_str = str(e).lower()
            if "conflict" in error_str or "409" in error_str:
                logger.error(
                    "Bot conflict detected: Another bot instance is running. "
                    "Please stop all other instances and restart."
                )
                logger.error(
                    "To fix this:\n"
                    "1. Stop all running bot instances\n"
                    "2. Wait a few seconds\n"
                    "3. Restart the bot"
                )
            raise
