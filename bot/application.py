"""Main bot application."""

from telegram import Update
from telegram.ext import Application, ApplicationBuilder

from config.logging_config import get_logger
from config.settings import settings
from services.monitoring_service import MonitoringService

logger = get_logger(__name__)


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
        self.app.add_handler(filters.filter_view_handler)
        self.app.add_handler(filters.filter_toggle_handler)
        self.app.add_handler(filters.filter_delete_handler)
        self.app.add_handler(filters.filter_list_handler)
        # Add filter callback handler (must be before conversation handler)
        from telegram.ext import CallbackQueryHandler
        self.app.add_handler(CallbackQueryHandler(filters.add_filter_callback, pattern="^filter_add$"))

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
        # Middleware will be added here
        pass

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
        self.app.run_polling(allowed_updates=Update.ALL_TYPES)
