"""Export command handler."""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, ContextTypes, CallbackQueryHandler

from config.logging_config import get_logger
from database.session import get_db
from database.repositories.user_repository import UserRepository
from database.repositories.filter_repository import FilterRepository
from services.export_service import ExportService

logger = get_logger(__name__)


async def export_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /export command - export vacancies to Excel."""
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

        # Show export options
        message = (
            "📊 <b>Экспорт вакансий в Excel</b>\n\n"
            "Выберите вариант экспорта:"
        )
        keyboard = [
            [InlineKeyboardButton("📋 Все вакансии", callback_data="export_all")],
        ]

        if user_filters:
            keyboard.append([InlineKeyboardButton("📌 По фильтру", callback_data="export_filter")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(message, parse_mode="HTML", reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"Error in export_command: {e}", exc_info=True)
        await update.message.reply_text("❌ Произошла ошибка.")


async def export_all_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle export all vacancies callback."""
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    if not user:
        return

    try:
        db = next(get_db())
        user_repo = UserRepository(db)

        db_user = user_repo.get_by_telegram_id(user.id)
        if not db_user:
            await query.edit_message_text("❌ Пользователь не найден.")
            return

        await query.edit_message_text("⏳ Генерирую Excel файл...")

        # Export vacancies
        export_service = ExportService()
        excel_file = export_service.export_vacancies_to_excel(user_id=db_user.id)

        # Send file
        filename = f"vacancies_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        await query.message.reply_document(
            document=excel_file,
            filename=filename,
            caption="📊 <b>Экспорт вакансий</b>\n\nФайл Excel с данными о вакансиях.",
            parse_mode="HTML",
        )

        await query.edit_message_text("✅ Файл успешно создан и отправлен!")

    except ValueError as e:
        await query.edit_message_text(f"❌ {str(e)}")
    except Exception as e:
        logger.error(f"Error in export_all_callback: {e}", exc_info=True)
        await query.edit_message_text("❌ Произошла ошибка при экспорте.")


async def export_filter_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle export by filter callback - show filter selection."""
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

        # Get user's active filters
        user_filters = filter_repo.get_active_by_user_id(db_user.id)

        if not user_filters:
            await query.edit_message_text(
                "❌ У вас нет активных фильтров.\n\n"
                "Создайте фильтр через /add_filter перед экспортом."
            )
            return

        # Show filters to choose from
        message = (
            "📊 <b>Экспорт по фильтру</b>\n\n"
            "Выберите фильтр для экспорта вакансий:\n\n"
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
                        callback_data=f"export_filter_id:{filter_obj.id}",
                    )
                ]
            )

        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="export_back")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message, parse_mode="HTML", reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"Error in export_filter_callback: {e}", exc_info=True)
        await query.edit_message_text("❌ Произошла ошибка.")


async def export_filter_id_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle export by specific filter callback."""
    query = update.callback_query
    await query.answer()

    if not query.data or not query.data.startswith("export_filter_id:"):
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

        await query.edit_message_text(f"⏳ Генерирую Excel файл по фильтру <b>\"{filter_obj.name}\"</b>...", parse_mode="HTML")

        # Export vacancies
        export_service = ExportService()
        excel_file = export_service.export_vacancies_to_excel(
            user_id=db_user.id, filter_id=filter_id
        )

        # Send file
        filename = f"vacancies_{filter_obj.name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        await query.message.reply_document(
            document=excel_file,
            filename=filename,
            caption=f"📊 <b>Экспорт вакансий</b>\n\nФильтр: {filter_obj.name}\n\nФайл Excel с данными о вакансиях.",
            parse_mode="HTML",
        )

        await query.edit_message_text("✅ Файл успешно создан и отправлен!")

    except ValueError as e:
        await query.edit_message_text(f"❌ {str(e)}")
    except Exception as e:
        logger.error(f"Error in export_filter_id_callback: {e}", exc_info=True)
        await query.edit_message_text("❌ Произошла ошибка при экспорте.")


async def export_back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle back to export menu callback."""
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

        # Get user's active filters
        user_filters = filter_repo.get_active_by_user_id(db_user.id)

        # Show export options
        message = (
            "📊 <b>Экспорт вакансий в Excel</b>\n\n"
            "Выберите вариант экспорта:"
        )
        keyboard = [
            [InlineKeyboardButton("📋 Все вакансии", callback_data="export_all")],
        ]

        if user_filters:
            keyboard.append([InlineKeyboardButton("📌 По фильтру", callback_data="export_filter")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message, parse_mode="HTML", reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"Error in export_back_callback: {e}", exc_info=True)
        await query.edit_message_text("❌ Произошла ошибка.")


# Handlers
export_handler = CommandHandler("export", export_command)
export_all_handler = CallbackQueryHandler(export_all_callback, pattern="^export_all$")
export_filter_handler = CallbackQueryHandler(export_filter_callback, pattern="^export_filter$")
export_filter_id_handler = CallbackQueryHandler(
    export_filter_id_callback, pattern="^export_filter_id:"
)
export_back_handler = CallbackQueryHandler(export_back_callback, pattern="^export_back$")