"""Monitoring command handler."""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters as tg_filters,
)

from config.logging_config import get_logger
from database.session import get_db
from database.repositories.user_repository import UserRepository
from database.repositories.filter_repository import FilterRepository
from database.repositories.monitoring_repository import MonitoringRepository

logger = get_logger(__name__)

# Conversation states for setting interval
MONITOR_INTERVAL = range(1)


async def monitor_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /monitor_list command - show active monitoring tasks."""
    user = update.effective_user
    if not user:
        return

    try:
        db = next(get_db())
        user_repo = UserRepository(db)
        monitoring_repo = MonitoringRepository(db)
        filter_repo = FilterRepository(db)

        db_user = user_repo.get_by_telegram_id(user.id)
        if not db_user:
            await update.message.reply_text(
                "❌ Вы не зарегистрированы. Используйте /start для регистрации."
            )
            return

        # Get user's monitoring tasks
        tasks = monitoring_repo.get_by_user_id(db_user.id)

        if not tasks:
            message = (
                "📊 <b>Мои задачи мониторинга</b>\n\n"
                "У вас пока нет задач мониторинга.\n\n"
                "Используйте /monitor_start для создания новой задачи."
            )
            keyboard = [
                [InlineKeyboardButton("➕ Создать задачу", callback_data="monitor_start")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(message, parse_mode="HTML", reply_markup=reply_markup)
            return

        # Format tasks list
        message = "📊 <b>Мои задачи мониторинга:</b>\n\n"
        keyboard = []

        for i, task in enumerate(tasks, 1):
            filter_obj = filter_repo.get_by_id(task.filter_id)
            status = "✅" if task.is_active else "❌"
            last_check = (
                task.last_check.strftime("%d.%m.%Y %H:%M") if task.last_check else "Никогда"
            )
            message += (
                f"{i}. {status} <b>{filter_obj.name if filter_obj else 'Неизвестный фильтр'}</b>\n"
                f"   Интервал: {task.interval_hours} ч.\n"
                f"   Последняя проверка: {last_check}\n\n"
            )

            keyboard.append(
                [
                    InlineKeyboardButton(
                        f"{status} {filter_obj.name if filter_obj else 'Неизвестный'}"
                        + f" ({task.interval_hours}ч)",
                        callback_data=f"monitor_view:{task.id}",
                    )
                ]
            )

        keyboard.append([InlineKeyboardButton("➕ Создать задачу", callback_data="monitor_start")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(message, parse_mode="HTML", reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"Error in monitor_list_command: {e}", exc_info=True)
        await update.message.reply_text("❌ Произошла ошибка при получении задач мониторинга.")


async def monitor_start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /monitor_start command - start monitoring with filter selection."""
    user = update.effective_user
    if not user:
        return

    try:
        db = next(get_db())
        user_repo = UserRepository(db)
        filter_repo = FilterRepository(db)

        db_user = user_repo.get_by_telegram_id(user.id)
        if not db_user:
            await update.message.reply_text(
                "❌ Вы не зарегистрированы. Используйте /start для регистрации."
            )
            return

        # Get user's active filters
        user_filters = filter_repo.get_active_by_user_id(db_user.id)

        if not user_filters:
            await update.message.reply_text(
                "❌ У вас нет активных фильтров.\n\n"
                "Создайте фильтр через /add_filter перед запуском мониторинга."
            )
            return

        # Show filters to choose from
        message = (
            "🔔 <b>Запуск мониторинга</b>\n\n"
            "Выберите фильтр для мониторинга новых вакансий:\n\n"
        )
        keyboard = []

        for filter_obj in user_filters:
            filter_desc = filter_obj.name
            if filter_obj.profession:
                filter_desc += f" ({filter_obj.profession}"
                if filter_obj.city:
                    filter_desc += f", {filter_obj.city}"
                filter_desc += ")"
            keyboard.append(
                [
                    InlineKeyboardButton(
                        f"🔍 {filter_obj.name}",
                        callback_data=f"monitor_start_filter:{filter_obj.id}",
                    )
                ]
            )

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(message, parse_mode="HTML", reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"Error in monitor_start_command: {e}", exc_info=True)
        await update.message.reply_text("❌ Произошла ошибка.")


async def monitor_start_filter_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle filter selection for monitoring start - show interval selection."""
    query = update.callback_query
    await query.answer()

    if not query.data or not query.data.startswith("monitor_start_filter:"):
        return

    filter_id = int(query.data.split(":")[1])
    user = update.effective_user
    if not user:
        return

    try:
        db = next(get_db())
        user_repo = UserRepository(db)
        filter_repo = FilterRepository(db)
        monitoring_repo = MonitoringRepository(db)

        db_user = user_repo.get_by_telegram_id(user.id)
        if not db_user:
            await query.edit_message_text("❌ Пользователь не найден.")
            return

        filter_obj = filter_repo.get_by_id(filter_id)
        if not filter_obj or filter_obj.user_id != db_user.id:
            await query.edit_message_text("❌ Фильтр не найден.")
            return

        # Check if monitoring task already exists for this filter
        existing_tasks = monitoring_repo.get_active_by_user_id(db_user.id)
        for task in existing_tasks:
            if task.filter_id == filter_id and task.is_active:
                await query.edit_message_text(
                    f"⚠️ Мониторинг по фильтру <b>\"{filter_obj.name}\"</b> уже запущен.\n\n"
                    "Используйте /monitor_list для просмотра активных задач.",
                    parse_mode="HTML",
                )
                return

        # Store filter_id in context for interval selection
        context.user_data["monitor_filter_id"] = filter_id

        # Show interval selection
        message = (
            f"🔔 <b>Запуск мониторинга</b>\n\n"
            f"Фильтр: <b>{filter_obj.name}</b>\n\n"
            "Выберите интервал проверки новых вакансий:"
        )

        keyboard = [
            [InlineKeyboardButton("⏰ 1 час", callback_data=f"monitor_interval:{filter_id}:1")],
            [InlineKeyboardButton("⏰ 3 часа", callback_data=f"monitor_interval:{filter_id}:3")],
            [InlineKeyboardButton("⏰ 6 часов", callback_data=f"monitor_interval:{filter_id}:6")],
            [InlineKeyboardButton("⏰ 12 часов", callback_data=f"monitor_interval:{filter_id}:12")],
            [InlineKeyboardButton("⏰ 24 часа", callback_data=f"monitor_interval:{filter_id}:24")],
            [InlineKeyboardButton("🔙 Назад к фильтрам", callback_data="monitor_start")],
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message, parse_mode="HTML", reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"Error in monitor_start_filter_callback: {e}", exc_info=True)
        await query.edit_message_text("❌ Произошла ошибка.")


async def monitor_interval_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle interval selection and create monitoring task."""
    query = update.callback_query
    await query.answer()

    if not query.data or not query.data.startswith("monitor_interval:"):
        return

    # Parse callback data: monitor_interval:filter_id:interval_hours
    parts = query.data.split(":")
    if len(parts) != 3:
        await query.edit_message_text("❌ Неверный формат данных.")
        return

    filter_id = int(parts[1])
    interval_hours = int(parts[2])
    user = update.effective_user
    if not user:
        return

    try:
        db = next(get_db())
        user_repo = UserRepository(db)
        filter_repo = FilterRepository(db)
        monitoring_repo = MonitoringRepository(db)

        db_user = user_repo.get_by_telegram_id(user.id)
        if not db_user:
            await query.edit_message_text("❌ Пользователь не найден.")
            return

        filter_obj = filter_repo.get_by_id(filter_id)
        if not filter_obj or filter_obj.user_id != db_user.id:
            await query.edit_message_text("❌ Фильтр не найден.")
            return

        # Create monitoring task with selected interval
        task_data = {
            "user_id": db_user.id,
            "filter_id": filter_id,
            "interval_hours": interval_hours,
            "is_active": True,
        }

        new_task = monitoring_repo.create(task_data)

        # Start monitoring task
        bot_application = context.application.bot_data.get("bot_application")
        if bot_application:
            monitoring_service = bot_application.monitoring_service
            await monitoring_service.start_monitoring_task(new_task.id)

        # Clear context
        context.user_data.pop("monitor_filter_id", None)

        message = (
            f"✅ <b>Мониторинг запущен!</b>\n\n"
            f"Фильтр: {filter_obj.name}\n"
            f"Интервал проверки: {interval_hours} {'час' if interval_hours == 1 else 'часов'}\n\n"
            "Бот будет автоматически проверять новые вакансии и отправлять уведомления.\n"
            "Используйте /monitor_list для управления задачами."
        )

        await query.edit_message_text(message, parse_mode="HTML")
        logger.info(f"Started monitoring task {new_task.id} for user {db_user.id} with interval {interval_hours} hours")

    except Exception as e:
        logger.error(f"Error in monitor_interval_callback: {e}", exc_info=True)
        await query.edit_message_text("❌ Произошла ошибка при запуске мониторинга.")


async def monitor_stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /monitor_stop command - stop monitoring task."""
    user = update.effective_user
    if not user:
        return

    try:
        db = next(get_db())
        user_repo = UserRepository(db)
        monitoring_repo = MonitoringRepository(db)
        filter_repo = FilterRepository(db)

        db_user = user_repo.get_by_telegram_id(user.id)
        if not db_user:
            await update.message.reply_text(
                "❌ Вы не зарегистрированы. Используйте /start для регистрации."
            )
            return

        # Get user's active monitoring tasks
        active_tasks = monitoring_repo.get_active_by_user_id(db_user.id)

        if not active_tasks:
            await update.message.reply_text(
                "❌ У вас нет активных задач мониторинга.\n\n"
                "Используйте /monitor_start для создания новой задачи."
            )
            return

        # Show tasks to stop
        message = "⏸ <b>Остановка мониторинга</b>\n\nВыберите задачу для остановки:\n\n"
        keyboard = []

        for task in active_tasks:
            filter_obj = filter_repo.get_by_id(task.filter_id)
            keyboard.append(
                [
                    InlineKeyboardButton(
                        f"⏸ {filter_obj.name if filter_obj else 'Неизвестный'} ({task.interval_hours}ч)",
                        callback_data=f"monitor_stop_task:{task.id}",
                    )
                ]
            )

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(message, parse_mode="HTML", reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"Error in monitor_stop_command: {e}", exc_info=True)
        await update.message.reply_text("❌ Произошла ошибка.")


async def monitor_stop_task_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle task stop callback."""
    query = update.callback_query
    await query.answer()

    if not query.data or not query.data.startswith("monitor_stop_task:"):
        return

    task_id = int(query.data.split(":")[1])
    user = update.effective_user
    if not user:
        return

    try:
        db = next(get_db())
        user_repo = UserRepository(db)
        monitoring_repo = MonitoringRepository(db)
        filter_repo = FilterRepository(db)

        db_user = user_repo.get_by_telegram_id(user.id)
        if not db_user:
            await query.edit_message_text("❌ Пользователь не найден.")
            return

        task = monitoring_repo.get_by_id(task_id)
        if not task or task.user_id != db_user.id:
            await query.edit_message_text("❌ Задача не найдена.")
            return

        filter_obj = filter_repo.get_by_id(task.filter_id)

        # Stop monitoring task
        bot_application = context.application.bot_data.get("bot_application")
        if bot_application:
            monitoring_service = bot_application.monitoring_service
            await monitoring_service.stop_monitoring_task(task_id)

        # Deactivate task in database
        monitoring_repo.update(task_id, {"is_active": False})

        message = (
            f"⏸ <b>Мониторинг остановлен</b>\n\n"
            f"Фильтр: {filter_obj.name if filter_obj else 'Неизвестный'}\n\n"
            "Задача деактивирована. Используйте /monitor_start для запуска нового мониторинга."
        )

        await query.edit_message_text(message, parse_mode="HTML")
        logger.info(f"Stopped monitoring task {task_id} for user {db_user.id}")

    except Exception as e:
        logger.error(f"Error in monitor_stop_task_callback: {e}", exc_info=True)
        await query.edit_message_text("❌ Произошла ошибка при остановке мониторинга.")


async def monitor_view_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle monitor view callback."""
    query = update.callback_query
    await query.answer()

    if not query.data or not query.data.startswith("monitor_view:"):
        return

    task_id = int(query.data.split(":")[1])
    user = update.effective_user
    if not user:
        return

    try:
        db = next(get_db())
        user_repo = UserRepository(db)
        monitoring_repo = MonitoringRepository(db)
        filter_repo = FilterRepository(db)

        db_user = user_repo.get_by_telegram_id(user.id)
        if not db_user:
            await query.edit_message_text("❌ Пользователь не найден.")
            return

        task = monitoring_repo.get_by_id(task_id)
        if not task or task.user_id != db_user.id:
            await query.edit_message_text("❌ Задача не найдена.")
            return

        filter_obj = filter_repo.get_by_id(task.filter_id)
        status = "✅ Активна" if task.is_active else "❌ Неактивна"
        last_check = (
            task.last_check.strftime("%d.%m.%Y %H:%M") if task.last_check else "Никогда"
        )

        message = (
            f"📊 <b>Задача мониторинга</b>\n\n"
            f"Фильтр: {filter_obj.name if filter_obj else 'Неизвестный'}\n"
            f"Статус: {status}\n"
            f"Интервал проверки: {task.interval_hours} часов\n"
            f"Последняя проверка: {last_check}\n"
            f"Создана: {task.created_at.strftime('%d.%m.%Y %H:%M')}\n"
        )

        keyboard = []
        if task.is_active:
            keyboard.append(
                [InlineKeyboardButton("🔄 Запустить проверку сейчас", callback_data=f"monitor_run_now:{task_id}")]
            )
            keyboard.append(
                [InlineKeyboardButton("⏸ Остановить", callback_data=f"monitor_stop_task:{task_id}")]
            )
        keyboard.append([InlineKeyboardButton("🔙 Назад к списку", callback_data="monitor_list")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message, parse_mode="HTML", reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"Error in monitor_view_callback: {e}", exc_info=True)
        await query.edit_message_text("❌ Произошла ошибка.")


async def monitor_list_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle monitor list callback."""
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    if not user:
        return

    try:
        db = next(get_db())
        user_repo = UserRepository(db)
        monitoring_repo = MonitoringRepository(db)
        filter_repo = FilterRepository(db)

        db_user = user_repo.get_by_telegram_id(user.id)
        if not db_user:
            await query.edit_message_text("❌ Пользователь не найден.")
            return

        tasks = monitoring_repo.get_by_user_id(db_user.id)

        if not tasks:
            message = (
                "📊 <b>Мои задачи мониторинга</b>\n\n"
                "У вас пока нет задач мониторинга.\n\n"
                "Используйте /monitor_start для создания новой задачи."
            )
            keyboard = [
                [InlineKeyboardButton("➕ Создать задачу", callback_data="monitor_start")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(message, parse_mode="HTML", reply_markup=reply_markup)
            return

        message = "📊 <b>Мои задачи мониторинга:</b>\n\n"
        keyboard = []

        for task in tasks:
            filter_obj = filter_repo.get_by_id(task.filter_id)
            status = "✅" if task.is_active else "❌"
            last_check = (
                task.last_check.strftime("%d.%m.%Y %H:%M") if task.last_check else "Никогда"
            )
            message += (
                f"{status} <b>{filter_obj.name if filter_obj else 'Неизвестный'}</b>\n"
                f"Интервал: {task.interval_hours} ч. | Последняя проверка: {last_check}\n\n"
            )

            keyboard.append(
                [
                    InlineKeyboardButton(
                        f"{status} {filter_obj.name if filter_obj else 'Неизвестный'}"
                        + f" ({task.interval_hours}ч)",
                        callback_data=f"monitor_view:{task.id}",
                    )
                ]
            )

        keyboard.append([InlineKeyboardButton("➕ Создать задачу", callback_data="monitor_start")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message, parse_mode="HTML", reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"Error in monitor_list_callback: {e}", exc_info=True)
        await query.edit_message_text("❌ Произошла ошибка.")


async def monitor_run_now_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle run monitoring task now callback."""
    query = update.callback_query
    await query.answer()

    if not query.data or not query.data.startswith("monitor_run_now:"):
        return

    task_id = int(query.data.split(":")[1])
    user = update.effective_user
    if not user:
        return

    try:
        db = next(get_db())
        user_repo = UserRepository(db)
        monitoring_repo = MonitoringRepository(db)
        filter_repo = FilterRepository(db)

        db_user = user_repo.get_by_telegram_id(user.id)
        if not db_user:
            await query.edit_message_text("❌ Пользователь не найден.")
            return

        task = monitoring_repo.get_by_id(task_id)
        if not task or task.user_id != db_user.id:
            await query.edit_message_text("❌ Задача не найдена.")
            return

        filter_obj = filter_repo.get_by_id(task.filter_id)

        await query.edit_message_text(
            f"⏳ Запускаю проверку для задачи <b>\"{filter_obj.name if filter_obj else 'Неизвестный'}\"</b>...",
            parse_mode="HTML",
        )

        # Run check immediately
        bot_application = context.application.bot_data.get("bot_application")
        if bot_application:
            monitoring_service = bot_application.monitoring_service
            # Run check in background
            import asyncio
            asyncio.create_task(monitoring_service._check_new_vacancies(task_id))

        await query.edit_message_text(
            f"✅ Проверка запущена для задачи <b>\"{filter_obj.name if filter_obj else 'Неизвестный'}\"</b>.\n\n"
            "Результаты будут отправлены вам, если будут найдены новые вакансии.",
            parse_mode="HTML",
        )

    except Exception as e:
        logger.error(f"Error in monitor_run_now_callback: {e}", exc_info=True)
        await query.edit_message_text("❌ Произошла ошибка при запуске проверки.")


# Handlers
monitor_list_handler = CommandHandler("monitor_list", monitor_list_command)
monitor_start_handler = CommandHandler("monitor_start", monitor_start_command)
monitor_stop_handler = CommandHandler("monitor_stop", monitor_stop_command)

# Callback handlers
monitor_start_filter_handler = CallbackQueryHandler(
    monitor_start_filter_callback, pattern="^monitor_start_filter:"
)
monitor_interval_handler = CallbackQueryHandler(
    monitor_interval_callback, pattern="^monitor_interval:"
)
monitor_stop_task_handler = CallbackQueryHandler(
    monitor_stop_task_callback, pattern="^monitor_stop_task:"
)
monitor_view_handler = CallbackQueryHandler(monitor_view_callback, pattern="^monitor_view:")
monitor_run_now_handler = CallbackQueryHandler(monitor_run_now_callback, pattern="^monitor_run_now:")
monitor_list_callback_handler = CallbackQueryHandler(monitor_list_callback, pattern="^monitor_list$")


async def monitor_start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle monitor start callback."""
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    if not user:
        return

    try:
        db = next(get_db())
        user_repo = UserRepository(db)
        filter_repo = FilterRepository(db)

        db_user = user_repo.get_by_telegram_id(user.id)
        if not db_user:
            await query.edit_message_text(
                "❌ Вы не зарегистрированы. Используйте /start для регистрации."
            )
            return

        # Get user's active filters
        user_filters = filter_repo.get_active_by_user_id(db_user.id)

        if not user_filters:
            await query.edit_message_text(
                "❌ У вас нет активных фильтров.\n\n"
                "Создайте фильтр через /add_filter перед запуском мониторинга."
            )
            return

        # Show filters to choose from
        message = (
            "🔔 <b>Запуск мониторинга</b>\n\n"
            "Выберите фильтр для мониторинга новых вакансий:\n\n"
        )
        keyboard = []

        for filter_obj in user_filters:
            filter_desc = filter_obj.name
            if filter_obj.profession:
                filter_desc += f" ({filter_obj.profession}"
                if filter_obj.city:
                    filter_desc += f", {filter_obj.city}"
                filter_desc += ")"
            keyboard.append(
                [
                    InlineKeyboardButton(
                        f"🔍 {filter_obj.name}",
                        callback_data=f"monitor_start_filter:{filter_obj.id}",
                    )
                ]
            )

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message, parse_mode="HTML", reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"Error in monitor_start_callback: {e}", exc_info=True)
        await query.edit_message_text("❌ Произошла ошибка.")


monitor_start_callback_handler = CallbackQueryHandler(
    monitor_start_callback, pattern="^monitor_start$"
)
