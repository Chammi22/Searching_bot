"""Filters command handler."""

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

logger = get_logger(__name__)

# Conversation states for adding filter
FILTER_NAME, FILTER_PROFESSION, FILTER_CITY, FILTER_COMPANY = range(4)


async def filters_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /filters command - show list of user's filters."""
    user = update.effective_user
    if not user:
        return

    try:
        db = next(get_db())
        user_repo = UserRepository(db)
        filter_repo = FilterRepository(db)

        # Get user from database
        db_user = user_repo.get_by_telegram_id(user.id)
        if not db_user:
            await update.message.reply_text(
                "❌ Вы не зарегистрированы. Используйте /start для регистрации."
            )
            return

        # Get user's filters
        user_filters = filter_repo.get_by_user_id(db_user.id)

        if not user_filters:
            message = (
                "📋 <b>Ваши фильтры</b>\n\n"
                "У вас пока нет сохраненных фильтров.\n\n"
                "Используйте /add_filter для создания нового фильтра."
            )
            keyboard = [
                [InlineKeyboardButton("➕ Добавить фильтр", callback_data="filter_add")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(message, parse_mode="HTML", reply_markup=reply_markup)
            return

        # Format filters list
        message = "📋 <b>Ваши фильтры:</b>\n\n"
        keyboard = []

        for i, filter_obj in enumerate(user_filters, 1):
            status = "✅" if filter_obj.is_active else "❌"
            message += (
                f"{i}. {status} <b>{filter_obj.name}</b>\n"
                f"   Профессия: {filter_obj.profession or 'не указано'}\n"
                f"   Город: {filter_obj.city or 'не указано'}\n"
                f"   Компания: {filter_obj.company_name or 'не указано'}\n\n"
            )

            # Add button for each filter
            keyboard.append(
                [
                    InlineKeyboardButton(
                        f"{status} {filter_obj.name}",
                        callback_data=f"filter_view:{filter_obj.id}",
                    )
                ]
            )

        keyboard.append([InlineKeyboardButton("➕ Добавить фильтр", callback_data="filter_add")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(message, parse_mode="HTML", reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"Error in filters_command: {e}", exc_info=True)
        await update.message.reply_text("❌ Произошла ошибка при получении фильтров.")


async def filter_view_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle filter view callback."""
    query = update.callback_query
    await query.answer()

    if not query.data or not query.data.startswith("filter_view:"):
        return

    filter_id = int(query.data.split(":")[1])
    user = update.effective_user
    if not user:
        return

    try:
        db = next(get_db())
        user_repo = UserRepository(db)
        filter_repo = FilterRepository(db)

        db_user = user_repo.get_by_telegram_id(user.id)
        if not db_user:
            await query.edit_message_text("❌ Пользователь не найден.")
            return

        filter_obj = filter_repo.get_by_id(filter_id)
        if not filter_obj or filter_obj.user_id != db_user.id:
            await query.edit_message_text("❌ Фильтр не найден.")
            return

        status = "✅ Активен" if filter_obj.is_active else "❌ Неактивен"
        message = (
            f"🔍 <b>Фильтр: {filter_obj.name}</b>\n\n"
            f"Статус: {status}\n"
            f"Профессия: {filter_obj.profession or 'не указано'}\n"
            f"Город: {filter_obj.city or 'не указано'}\n"
            f"Компания: {filter_obj.company_name or 'не указано'}\n"
            f"Создан: {filter_obj.created_at.strftime('%d.%m.%Y %H:%M')}\n"
        )

        keyboard = []
        keyboard.append(
            [InlineKeyboardButton("🔍 Использовать для поиска", callback_data=f"search_filter:{filter_id}")]
        )
        if filter_obj.is_active:
            keyboard.append(
                [InlineKeyboardButton("⏸ Деактивировать", callback_data=f"filter_toggle:{filter_id}")]
            )
        else:
            keyboard.append(
                [InlineKeyboardButton("▶ Активировать", callback_data=f"filter_toggle:{filter_id}")]
            )
        keyboard.append([InlineKeyboardButton("✏️ Редактировать", callback_data=f"filter_edit:{filter_id}")])
        keyboard.append([InlineKeyboardButton("🗑 Удалить", callback_data=f"filter_delete:{filter_id}")])
        keyboard.append([InlineKeyboardButton("🔙 Назад к списку", callback_data="filter_list")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message, parse_mode="HTML", reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"Error in filter_view_callback: {e}", exc_info=True)
        await query.edit_message_text("❌ Произошла ошибка.")


async def filter_toggle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle filter toggle (activate/deactivate) callback."""
    query = update.callback_query
    await query.answer()

    if not query.data or not query.data.startswith("filter_toggle:"):
        return

    filter_id = int(query.data.split(":")[1])
    user = update.effective_user
    if not user:
        return

    try:
        db = next(get_db())
        user_repo = UserRepository(db)
        filter_repo = FilterRepository(db)

        db_user = user_repo.get_by_telegram_id(user.id)
        if not db_user:
            await query.edit_message_text("❌ Пользователь не найден.")
            return

        filter_obj = filter_repo.get_by_id(filter_id)
        if not filter_obj or filter_obj.user_id != db_user.id:
            await query.edit_message_text("❌ Фильтр не найден.")
            return

        # Toggle filter status
        filter_repo.update(filter_id, {"is_active": not filter_obj.is_active})
        await query.answer(f"Фильтр {'активирован' if not filter_obj.is_active else 'деактивирован'}")

        # Refresh view
        await filter_view_callback(update, context)

    except Exception as e:
        logger.error(f"Error in filter_toggle_callback: {e}", exc_info=True)
        await query.answer("❌ Произошла ошибка.")


async def filter_delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle filter delete callback."""
    query = update.callback_query
    await query.answer()

    if not query.data or not query.data.startswith("filter_delete:"):
        return

    filter_id = int(query.data.split(":")[1])
    user = update.effective_user
    if not user:
        return

    try:
        db = next(get_db())
        user_repo = UserRepository(db)
        filter_repo = FilterRepository(db)

        db_user = user_repo.get_by_telegram_id(user.id)
        if not db_user:
            await query.edit_message_text("❌ Пользователь не найден.")
            return

        filter_obj = filter_repo.get_by_id(filter_id)
        if not filter_obj or filter_obj.user_id != db_user.id:
            await query.edit_message_text("❌ Фильтр не найден.")
            return

        filter_name = filter_obj.name
        filter_repo.delete(filter_id)
        await query.answer(f"Фильтр '{filter_name}' удален")

        # Show filter list
        await filter_list_callback(update, context)

    except Exception as e:
        logger.error(f"Error in filter_delete_callback: {e}", exc_info=True)
        await query.answer("❌ Произошла ошибка.")


async def filter_list_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle filter list callback."""
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
            await query.edit_message_text("❌ Пользователь не найден.")
            return

        user_filters = filter_repo.get_by_user_id(db_user.id)

        if not user_filters:
            message = (
                "📋 <b>Ваши фильтры</b>\n\n"
                "У вас пока нет сохраненных фильтров.\n\n"
                "Используйте /add_filter для создания нового фильтра."
            )
            keyboard = [
                [InlineKeyboardButton("➕ Добавить фильтр", callback_data="filter_add")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(message, parse_mode="HTML", reply_markup=reply_markup)
            return

        message = "📋 <b>Ваши фильтры:</b>\n\n"
        keyboard = []

        for filter_obj in user_filters:
            status = "✅" if filter_obj.is_active else "❌"
            message += (
                f"{status} <b>{filter_obj.name}</b>\n"
                f"Профессия: {filter_obj.profession or 'не указано'}\n"
                f"Город: {filter_obj.city or 'не указано'}\n\n"
            )

            keyboard.append(
                [
                    InlineKeyboardButton(
                        f"{status} {filter_obj.name}",
                        callback_data=f"filter_view:{filter_obj.id}",
                    )
                ]
            )

        keyboard.append([InlineKeyboardButton("➕ Добавить фильтр", callback_data="filter_add")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message, parse_mode="HTML", reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"Error in filter_list_callback: {e}", exc_info=True)
        await query.edit_message_text("❌ Произошла ошибка.")


async def add_filter_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start adding a new filter."""
    user = update.effective_user
    if not user:
        return ConversationHandler.END

    try:
        db = next(get_db())
        user_repo = UserRepository(db)

        db_user = user_repo.get_by_telegram_id(user.id)
        if not db_user:
            await update.message.reply_text(
                "❌ Вы не зарегистрированы. Используйте /start для регистрации."
            )
            return ConversationHandler.END

        await update.message.reply_text(
            "➕ <b>Создание нового фильтра</b>\n\n"
            "Введите название фильтра (например: 'Подсобные рабочие в Минске'):",
            parse_mode="HTML",
        )
        return FILTER_NAME

    except Exception as e:
        logger.error(f"Error in add_filter_start: {e}", exc_info=True)
        await update.message.reply_text("❌ Произошла ошибка.")
        return ConversationHandler.END


async def add_filter_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Get filter name."""
    filter_name = update.message.text.strip()
    if not filter_name:
        await update.message.reply_text("❌ Название не может быть пустым. Попробуйте еще раз:")
        return FILTER_NAME

    context.user_data["filter_name"] = filter_name
    await update.message.reply_text(
        f"✅ Название: <b>{filter_name}</b>\n\n"
        "Введите профессию для поиска (например: 'подсобный рабочий'):\n"
        "Или отправьте '-' чтобы пропустить:",
        parse_mode="HTML",
    )
    return FILTER_PROFESSION


async def add_filter_profession(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Get filter profession."""
    profession = update.message.text.strip()
    if profession == "-":
        profession = None
    context.user_data["filter_profession"] = profession

    await update.message.reply_text(
        f"✅ Профессия: <b>{profession or 'не указано'}</b>\n\n"
        "Введите город для поиска (например: 'Минск' или 'Могилевская область'):\n"
        "Или отправьте '-' чтобы пропустить:",
        parse_mode="HTML",
    )
    return FILTER_CITY


async def add_filter_city(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Get filter city."""
    city = update.message.text.strip()
    if city == "-":
        city = None
    context.user_data["filter_city"] = city

    await update.message.reply_text(
        f"✅ Город: <b>{city or 'не указано'}</b>\n\n"
        "Введите название компании для поиска (например: 'ООО Рога и копыта'):\n"
        "Или отправьте '-' чтобы пропустить:",
        parse_mode="HTML",
    )
    return FILTER_COMPANY


async def add_filter_company(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Get filter company and create filter."""
    company = update.message.text.strip()
    if company == "-":
        company = None
    context.user_data["filter_company"] = company

    user = update.effective_user
    if not user:
        return ConversationHandler.END

    try:
        db = next(get_db())
        user_repo = UserRepository(db)
        filter_repo = FilterRepository(db)

        db_user = user_repo.get_by_telegram_id(user.id)
        if not db_user:
            await update.message.reply_text("❌ Пользователь не найден.")
            return ConversationHandler.END

        # Create filter
        filter_data = {
            "user_id": db_user.id,
            "name": context.user_data["filter_name"],
            "profession": context.user_data.get("filter_profession"),
            "city": context.user_data.get("filter_city"),
            "company_name": context.user_data.get("filter_company"),
            "is_active": True,
        }

        new_filter = filter_repo.create(filter_data)

        message = (
            f"✅ <b>Фильтр создан!</b>\n\n"
            f"Название: {new_filter.name}\n"
            f"Профессия: {new_filter.profession or 'не указано'}\n"
            f"Город: {new_filter.city or 'не указано'}\n"
            f"Компания: {new_filter.company_name or 'не указано'}\n\n"
            "Используйте /filters для управления фильтрами."
        )

        # Clear user data
        context.user_data.pop("filter_name", None)
        context.user_data.pop("filter_profession", None)
        context.user_data.pop("filter_city", None)
        context.user_data.pop("filter_company", None)

        await update.message.reply_text(message, parse_mode="HTML")
        logger.info(f"Filter created: {new_filter.id} by user {db_user.id}")

        return ConversationHandler.END

    except Exception as e:
        logger.error(f"Error in add_filter_company: {e}", exc_info=True)
        await update.message.reply_text("❌ Произошла ошибка при создании фильтра.")
        return ConversationHandler.END


async def add_filter_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle add filter callback - redirect to command."""
    query = update.callback_query
    await query.answer()

    # Start conversation by calling the command handler
    # We'll send a message and let user use /add_filter command
    await query.message.reply_text(
        "➕ <b>Создание нового фильтра</b>\n\n"
        "Используйте команду /add_filter для создания нового фильтра.",
        parse_mode="HTML",
    )


async def cancel_filter(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel filter creation."""
    # Clear user data
    context.user_data.pop("filter_name", None)
    context.user_data.pop("filter_profession", None)
    context.user_data.pop("filter_city", None)
    context.user_data.pop("filter_company", None)

    await update.message.reply_text("❌ Создание фильтра отменено.")
    return ConversationHandler.END


# Handlers
filters_handler = CommandHandler("filters", filters_command)

# Conversation handler for adding filter
add_filter_conv_handler = ConversationHandler(
    entry_points=[
        CommandHandler("add_filter", add_filter_start),
    ],
    states={
        FILTER_NAME: [MessageHandler(tg_filters.TEXT & ~tg_filters.COMMAND, add_filter_name)],
        FILTER_PROFESSION: [
            MessageHandler(tg_filters.TEXT & ~tg_filters.COMMAND, add_filter_profession)
        ],
        FILTER_CITY: [MessageHandler(tg_filters.TEXT & ~tg_filters.COMMAND, add_filter_city)],
        FILTER_COMPANY: [MessageHandler(tg_filters.TEXT & ~tg_filters.COMMAND, add_filter_company)],
    },
    fallbacks=[CommandHandler("cancel", cancel_filter)],
)

# Callback handlers
filter_view_handler = CallbackQueryHandler(filter_view_callback, pattern="^filter_view:")
filter_toggle_handler = CallbackQueryHandler(filter_toggle_callback, pattern="^filter_toggle:")
filter_delete_handler = CallbackQueryHandler(filter_delete_callback, pattern="^filter_delete:")
filter_list_handler = CallbackQueryHandler(filter_list_callback, pattern="^filter_list$")
