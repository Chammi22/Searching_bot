"""Search command handler."""

from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, ContextTypes, CallbackQueryHandler

from config.logging_config import get_logger
from database.session import get_db
from database.repositories.vacancy_repository import VacancyRepository
from database.repositories.user_repository import UserRepository
from database.repositories.filter_repository import FilterRepository
from parsers.gsz_parser import GszParser
from utils.helpers import format_vacancy_message

logger = get_logger(__name__)

# Store search results in context for pagination
SEARCH_RESULTS_KEY = "search_results"
CURRENT_PAGE_KEY = "current_page"


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /search command."""
    user = update.effective_user
    if not user:
        return

    # Parse command arguments
    args = context.args
    profession = None
    city = None
    company_name = None

    if args:
        # Parse arguments: /search профессия [город]
        # Simple approach: if 2+ arguments, last is city, rest is profession
        args_list = list(args)
        
        # Common city/region keywords in Russian/Belarusian
        city_keywords = ["в", "город", "г.", "область", "обл.", "район", "р-н"]
        
        # Check if there's a keyword separator (e.g., "в", "город")
        keyword_index = None
        for i, arg in enumerate(args_list):
            if arg.lower() in city_keywords:
                keyword_index = i
                break
        
        if keyword_index is not None:
            # Format: /search профессия в город
            profession = " ".join(args_list[:keyword_index])
            if keyword_index + 1 < len(args_list):
                city = " ".join(args_list[keyword_index + 1:])
        elif len(args_list) >= 2:
            # Format: /search профессия город
            # Last argument is city, rest is profession
            # This works for: "подсобный рабочий Минск" -> profession="подсобный рабочий", city="Минск"
            profession = " ".join(args_list[:-1])
            city = args_list[-1]
        else:
            # Single argument - profession only
            profession = args_list[0]
    else:
        # No arguments - show filters or ask for search parameters
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

            if user_filters:
                # Show filters to choose from
                message = (
                    "🔍 <b>Поиск вакансий</b>\n\n"
                    "Выберите фильтр для поиска или используйте команду с параметрами:\n"
                    "<code>/search подсобный рабочий</code>\n\n"
                    "<b>Ваши активные фильтры:</b>"
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
                                callback_data=f"search_filter:{filter_obj.id}",
                            )
                        ]
                    )
                keyboard.append(
                    [
                        InlineKeyboardButton(
                            "✏️ Ввести параметры вручную",
                            callback_data="search_manual",
                        )
                    ]
                )
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text(message, parse_mode="HTML", reply_markup=reply_markup)
            else:
                # No filters - ask for manual input
                await update.message.reply_text(
                    "🔍 <b>Поиск вакансий</b>\n\n"
                    "Используйте команду так:\n"
                    "<code>/search подсобный рабочий</code> - поиск по профессии\n"
                    "<code>/search подсобный рабочий Минск</code> - поиск по профессии и городу\n"
                    "<code>/search плотник в Могилев</code> - поиск с предлогом \"в\"\n\n"
                    "💡 <b>Совет:</b> Создайте фильтр через /add_filter для быстрого доступа к часто используемым поискам.",
                    parse_mode="HTML",
                )
            return
        except Exception as e:
            logger.error(f"Error in search_command: {e}", exc_info=True)
            await update.message.reply_text(
                "🔍 <b>Поиск вакансий</b>\n\n"
                "Используйте команду так:\n"
                "<code>/search подсобный рабочий</code> - поиск по профессии\n"
                "<code>/search подсобный рабочий Минск</code> - поиск по профессии и городу",
                parse_mode="HTML",
            )
            return

    # Show loading message
    loading_msg = await update.message.reply_text("⏳ Ищу вакансии...")

    try:
        # Parse vacancies using parser
        async with GszParser() as parser:
            vacancies = await parser.parse_vacancies(
                profession=profession,
                city=city,
                company_name=company_name,
                limit=200,  # Increased limit for better results
            )

        if not vacancies:
            await loading_msg.edit_text(
                f"❌ Вакансии по запросу <b>\"{profession}\"</b> не найдены.\n\n"
                "Попробуйте изменить параметры поиска.",
                parse_mode="HTML",
            )
            return

        # Save vacancies to database
        db = next(get_db())
        vacancy_repo = VacancyRepository(db)
        saved_count = 0

        for vacancy_data in vacancies:
            # Check if vacancy already exists
            existing = vacancy_repo.get_by_external_id_and_source(
                vacancy_data["external_id"], vacancy_data["source"]
            )
            if not existing:
                vacancy_repo.create(vacancy_data)
                saved_count += 1

        # Store results in context for pagination
        context.user_data[SEARCH_RESULTS_KEY] = vacancies
        context.user_data[CURRENT_PAGE_KEY] = 0

        # Show first result
        await show_search_results(update, context, page=0, message=loading_msg)

    except Exception as e:
        logger.error(f"Error searching vacancies: {e}", exc_info=True)
        await loading_msg.edit_text(
            "❌ Произошла ошибка при поиске вакансий.\n"
            "Попробуйте позже или измените параметры поиска."
        )


async def show_search_results(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    page: int = 0,
    message=None,
) -> None:
    """Show search results with pagination."""
    vacancies = context.user_data.get(SEARCH_RESULTS_KEY, [])
    if not vacancies:
        return

    total_pages = len(vacancies)
    if page >= total_pages:
        page = total_pages - 1
    if page < 0:
        page = 0

    vacancy = vacancies[page]
    context.user_data[CURRENT_PAGE_KEY] = page

    # Format message
    message_text = (
        f"📋 <b>Результат {page + 1} из {total_pages}</b>\n\n"
        + format_vacancy_message(vacancy)
    )

    # Create pagination keyboard
    keyboard = []
    nav_buttons = []

    if page > 0:
        nav_buttons.append(
            InlineKeyboardButton("◀️ Назад", callback_data=f"search_page:{page-1}")
        )

    nav_buttons.append(
        InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="noop")
    )

    if page < total_pages - 1:
        nav_buttons.append(
            InlineKeyboardButton("Вперед ▶️", callback_data=f"search_page:{page+1}")
        )

    if nav_buttons:
        keyboard.append(nav_buttons)

    # Add action buttons
    action_buttons = []
    if vacancy.get("url"):
        action_buttons.append(
            InlineKeyboardButton("🔗 Открыть вакансию", url=vacancy["url"])
        )
    keyboard.append(action_buttons)

    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None

    if message:
        await message.edit_text(message_text, parse_mode="HTML", reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text(
            message_text, parse_mode="HTML", reply_markup=reply_markup
        )


async def search_page_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle pagination callback for search results."""
    query = update.callback_query
    await query.answer()

    # Extract page number from callback data
    callback_data = query.data
    if callback_data == "noop":
        return
    
    if callback_data.startswith("search_page:"):
        page = int(callback_data.split(":")[1])
        await show_search_results(update, context, page=page)


async def search_filter_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle search using filter callback."""
    query = update.callback_query
    await query.answer()

    if not query.data or not query.data.startswith("search_filter:"):
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

        # Use filter parameters for search
        profession = filter_obj.profession
        city = filter_obj.city
        company_name = filter_obj.company_name

        # Show loading message
        await query.edit_message_text(
            f"⏳ Ищу вакансии по фильтру <b>\"{filter_obj.name}\"</b>...",
            parse_mode="HTML",
        )

        # Parse vacancies using parser
        async with GszParser() as parser:
            vacancies = await parser.parse_vacancies(
                profession=profession,
                city=city,
                company_name=company_name,
                limit=200,  # Increased limit for better results
            )

        if not vacancies:
            await query.edit_message_text(
                f"❌ Вакансии по фильтру <b>\"{filter_obj.name}\"</b> не найдены.\n\n"
                "Попробуйте изменить параметры фильтра или использовать другой фильтр.",
                parse_mode="HTML",
            )
            return

        # Save vacancies to database
        vacancy_repo = VacancyRepository(db)
        saved_count = 0

        for vacancy_data in vacancies:
            existing = vacancy_repo.get_by_external_id_and_source(
                vacancy_data["external_id"], vacancy_data["source"]
            )
            if not existing:
                vacancy_repo.create(vacancy_data)
                saved_count += 1

        # Store results in context for pagination
        context.user_data[SEARCH_RESULTS_KEY] = vacancies
        context.user_data[CURRENT_PAGE_KEY] = 0

        # Show first result
        await show_search_results(update, context, page=0, message=query.message)

    except Exception as e:
        logger.error(f"Error in search_filter_callback: {e}", exc_info=True)
        await query.edit_message_text(
            "❌ Произошла ошибка при поиске вакансий.\n"
            "Попробуйте позже или используйте другой фильтр."
        )


async def search_manual_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle manual search input callback."""
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "🔍 <b>Поиск вакансий</b>\n\n"
        "Используйте команду так:\n"
        "<code>/search подсобный рабочий</code> - поиск по профессии\n"
        "<code>/search подсобный рабочий Минск</code> - поиск по профессии и городу\n\n"
        "Или создайте фильтр через /add_filter для быстрого доступа.",
        parse_mode="HTML",
    )


# Handlers
search_handler = CommandHandler("search", search_command)
search_page_handler = CallbackQueryHandler(search_page_callback, pattern="^search_page:")
search_filter_handler = CallbackQueryHandler(search_filter_callback, pattern="^search_filter:")
search_manual_handler = CallbackQueryHandler(search_manual_callback, pattern="^search_manual$")