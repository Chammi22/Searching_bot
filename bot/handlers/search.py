"""Search command handler."""

import asyncio
import time
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
SEARCH_PARAMS_KEY = "search_params"  # Store search parameters for lazy loading
VACANCIES_PER_PAGE = 20  # Show 20 vacancies per page


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
            # Last argument might be city, but check if it's a known city name
            # Common Belarusian cities
            known_cities = [
                "минск", "могилев", "гомель", "брест", "гродно", "витебск",
                "бобруйск", "барановичи", "пинск", "орша", "мозырь", "солигорск",
                "новополоцк", "лида", "молодечно", "полоцк", "слоним", "кобрин",
                "волковыск", "калинковичи", "светлогорск", "речица", "жлобин",
                "слуцк", "лепель", "климовичи", "рогачев", "чаусы", "чашники"
            ]
            
            last_arg_lower = args_list[-1].lower()
            # Check if last argument is a known city
            if last_arg_lower in known_cities or any(city in last_arg_lower for city in known_cities):
                # Last argument is a city
                profession = " ".join(args_list[:-1])
                city = args_list[-1]
            else:
                # Last argument is part of profession (e.g., "подсобный рабочий")
                profession = " ".join(args_list)
                city = None
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

    # Progress tracking
    last_progress_update = 0

    async def update_progress(current_page: int, total_pages: int, found_count: int) -> None:
        """Update progress message."""
        nonlocal last_progress_update
        
        # Update progress more frequently for better UX
        # Always update on first page (page 0) to show initial progress immediately
        current_time = time.time()
        time_since_last = current_time - last_progress_update
        
        # Update immediately on first page, then every 1 second minimum
        if current_page == 0:
            # First page - update immediately
            pass
        elif time_since_last < 1.0:
            # Too soon since last update
            return
        
        last_progress_update = current_time
        
        # Calculate progress percentage
        if total_pages > 0:
            progress_pct = min(int((current_page / total_pages) * 100), 100)
        else:
            progress_pct = 0
        
        # Create progress bar with more visual elements
        bar_length = 12
        filled = int(bar_length * progress_pct / 100)
        bar = "█" * filled + "░" * (bar_length - filled)
        
        # Add spinner animation based on page number
        spinner = ["⏳", "🔍", "📋", "🔎"][current_page % 4]
        
        progress_text = (
            f"{spinner} <b>Ищу вакансии...</b>\n\n"
            f"📄 Обработано страниц: {current_page}/{total_pages if total_pages > 0 else '?'}\n"
            f"📊 Найдено вакансий: {found_count}\n"
            f"📈 Прогресс: [{bar}] {progress_pct}%\n\n"
            f"<i>Пожалуйста, подождите...</i>"
        )
        
        try:
            await loading_msg.edit_text(progress_text, parse_mode="HTML")
        except Exception as e:
            error_str = str(e).lower()
            if "not modified" not in error_str:
                logger.debug(f"Could not update progress message: {e}")

    try:
        # First, get exact total count of vacancies from the page
        async with GszParser() as parser:
            total_vacancies = await parser.get_total_vacancies_count(profession, city, company_name)
            
            # If exact count not found, estimate from pages
            if total_vacancies is None:
                total_pages = await parser.get_total_pages(profession, city, company_name)
                total_vacancies = total_pages * 20  # ~20 vacancies per page
                logger.info(f"Estimated total vacancies: {total_vacancies} (from {total_pages} pages)")
            else:
                logger.info(f"Found exact total vacancies count: {total_vacancies}")
            
            # Parse first batch of vacancies (first page to show immediately)
            vacancies = await parser.parse_vacancies(
                profession=profession,
                city=city,
                company_name=company_name,
                limit=VACANCIES_PER_PAGE,  # Parse first 20 for immediate display
                progress_callback=update_progress,
            )

        if not vacancies:
            await loading_msg.edit_text(
                f"❌ Вакансии по запросу <b>\"{profession}\"</b> не найдены.\n\n"
                "Попробуйте изменить параметры поиска.",
                parse_mode="HTML",
            )
            return

        # Save search parameters for lazy loading more pages
        context.user_data[SEARCH_PARAMS_KEY] = {
            "profession": profession,
            "city": city,
            "company_name": company_name,
        }
        
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
        context.user_data["total_vacancies"] = total_vacancies  # Exact or estimated count
        context.user_data["parsed_pages"] = 1  # Track how many pages we've parsed

        # Show final message briefly before showing results
        final_text = (
            f"✅ <b>Найдено: {total_vacancies} вакансий</b>\n"
            f"📋 Загружено: {len(vacancies)} вакансий\n"
            "💾 Сохраняю в базу данных..."
        )
        await loading_msg.edit_text(final_text, parse_mode="HTML")
        await asyncio.sleep(0.8)  # Show final message for 0.8 seconds

        # Show first batch of 20 vacancies
        await show_search_results_batch(update, context, batch=0, message=loading_msg)

    except Exception as e:
        logger.error(f"Error searching vacancies: {e}", exc_info=True)
        await loading_msg.edit_text(
            "❌ Произошла ошибка при поиске вакансий.\n"
            "Попробуйте позже или измените параметры поиска."
        )


async def show_search_results_batch(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    batch: int = 0,
    message=None,
) -> None:
    """Show search results in batches of 20 vacancies."""
    vacancies = context.user_data.get(SEARCH_RESULTS_KEY, [])
    if not vacancies:
        return

    total_vacancies = context.user_data.get("total_vacancies", len(vacancies))
    parsed_pages = context.user_data.get("parsed_pages", 1)
    
    # Calculate batch range
    start_idx = batch * VACANCIES_PER_PAGE
    end_idx = min(start_idx + VACANCIES_PER_PAGE, len(vacancies))
    batch_vacancies = vacancies[start_idx:end_idx]
    
    if not batch_vacancies:
        # Need to load more vacancies
        await load_more_vacancies(update, context, batch, message)
        return

    # Format message with batch info
    total_batches = (len(vacancies) + VACANCIES_PER_PAGE - 1) // VACANCIES_PER_PAGE
    message_text = (
        f"📊 <b>Найдено: {total_vacancies} вакансий</b>\n"
        f"📋 Показано: {start_idx + 1}-{end_idx} из {total_vacancies}\n"
        f"📄 Загружено: {len(vacancies)} из {total_vacancies}\n\n"
    )
    
    # Show up to 20 vacancies in compact format
    for i, vacancy in enumerate(batch_vacancies[:20], start=start_idx + 1):
        position = vacancy.get("position", "Не указано")
        company = vacancy.get("company_name", "Не указано")
        address = vacancy.get("company_address", "")
        salary = vacancy.get("salary", "")
        
        message_text += f"<b>{i}. {position}</b>\n"
        message_text += f"🏢 {company}\n"
        if address:
            message_text += f"📍 {address}\n"
        if salary:
            message_text += f"💰 {salary}\n"
        message_text += "\n"

    # Create pagination keyboard
    keyboard = []
    nav_buttons = []

    if batch > 0:
        nav_buttons.append(
            InlineKeyboardButton("◀️ Предыдущие 20", callback_data=f"search_batch:{batch-1}")
        )

    nav_buttons.append(
        InlineKeyboardButton(f"Страница {batch + 1}", callback_data="noop")
    )

    # Check if we have more vacancies or can load more
    has_more = end_idx < len(vacancies) or len(vacancies) < total_vacancies
    if has_more:
        nav_buttons.append(
            InlineKeyboardButton("Следующие 20 ▶️", callback_data=f"search_batch:{batch+1}")
        )

    if nav_buttons:
        keyboard.append(nav_buttons)
    
    # Add button to load all remaining vacancies
    if len(vacancies) < total_vacancies:
        remaining = total_vacancies - len(vacancies)
        keyboard.append([
            InlineKeyboardButton(
                f"📥 Загрузить все ({remaining} осталось)",
                callback_data="search_load_all"
            )
        ])

    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None

    try:
        if message:
            await message.edit_text(message_text, parse_mode="HTML", reply_markup=reply_markup)
        else:
            query = update.callback_query
            if query:
                await query.edit_message_text(
                    message_text, parse_mode="HTML", reply_markup=reply_markup
                )
    except Exception as e:
        # Handle "Message is not modified" error gracefully
        error_str = str(e).lower()
        if "not modified" in error_str or "message is not modified" in error_str:
            logger.debug("Message not modified - content is the same, ignoring")
            # Just answer the callback query
            if update.callback_query:
                await update.callback_query.answer()
        else:
            logger.error(f"Error updating message: {e}", exc_info=True)
            raise


async def load_more_vacancies(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    batch: int,
    message=None,
) -> None:
    """Load more vacancies for the current search."""
    query = update.callback_query
    if query:
        await query.answer()
    
    search_params = context.user_data.get(SEARCH_PARAMS_KEY)
    if not search_params:
        if query:
            await query.edit_message_text(
                "❌ Параметры поиска не найдены. Начните новый поиск."
            )
        return

    # Show loading message
    loading_text = "⏳ Загружаю следующие вакансии..."
    try:
        if message:
            await message.edit_text(loading_text)
        elif query:
            await query.edit_message_text(loading_text)
    except Exception as e:
        logger.debug(f"Could not update loading message: {e}")

    try:
        parsed_pages = context.user_data.get("parsed_pages", 1)
        current_vacancies = context.user_data.get(SEARCH_RESULTS_KEY, [])
        
        # Parse next page (page = parsed_pages + 1)
        next_page = parsed_pages + 1
        
        # Build URL for next page manually to parse only that page
        async with GszParser() as parser:
            # Parse only the next page
            url = parser.build_search_url(
                profession=search_params["profession"],
                city=search_params["city"],
                company_name=search_params["company_name"],
                page=next_page,
            )
            
            html = await parser._fetch_page(url)
            if not html:
                if query:
                    await query.edit_message_text(
                        "✅ Все доступные вакансии загружены."
                    )
                return
            
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
            vacancy_items = soup.find_all("div", class_="job-block")
            
            if len(vacancy_items) == 0:
                if query:
                    await query.edit_message_text(
                        "✅ Все доступные вакансии загружены."
                    )
                return
            
            # Parse vacancies from this page
            next_page_vacancies = []
            for item in vacancy_items:
                vacancy = await parser._parse_vacancy_item(item)
                if vacancy:
                    # Apply city filter if needed
                    if search_params.get("city") and search_params["city"]:
                        address = vacancy.get("company_address", "").lower()
                        city_lower = search_params["city"].lower()
                        # Skip if city filter doesn't match (but only if city is a real city)
                        if len(city_lower) >= 4 and city_lower not in address:
                            # Check city variations
                            city_variations = [
                                city_lower,
                                f"г. {city_lower}",
                                f"г {city_lower}",
                            ]
                            matches = any(var in address for var in city_variations)
                            if not matches:
                                continue
                    
                    next_page_vacancies.append(vacancy)
        
        if not next_page_vacancies:
            if query:
                await query.edit_message_text(
                    "✅ Все доступные вакансии загружены."
                )
            return
        
        # Save to database
        db = next(get_db())
        vacancy_repo = VacancyRepository(db)
        
        for vacancy_data in next_page_vacancies:
            existing = vacancy_repo.get_by_external_id_and_source(
                vacancy_data["external_id"], vacancy_data["source"]
            )
            if not existing:
                vacancy_repo.create(vacancy_data)
        
        # Add to existing vacancies
        current_vacancies.extend(next_page_vacancies)
        context.user_data[SEARCH_RESULTS_KEY] = current_vacancies
        context.user_data["parsed_pages"] = parsed_pages + 1
        
        # Show the batch
        await show_search_results_batch(update, context, batch=batch)
        
    except Exception as e:
        logger.error(f"Error loading more vacancies: {e}", exc_info=True)
        if query:
            try:
                await query.edit_message_text(
                    "❌ Ошибка при загрузке вакансий. Попробуйте позже."
                )
            except Exception:
                pass


async def load_all_vacancies(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Load all remaining vacancies."""
    search_params = context.user_data.get(SEARCH_PARAMS_KEY)
    if not search_params:
        await update.callback_query.edit_message_text(
            "❌ Параметры поиска не найдены."
        )
        return

    await update.callback_query.edit_message_text(
        "⏳ Загружаю все оставшиеся вакансии...\n"
        "Это может занять некоторое время."
    )

    try:
        current_vacancies = context.user_data.get(SEARCH_RESULTS_KEY, [])
        parsed_pages = context.user_data.get("parsed_pages", 1)
        
        # Progress callback
        async def update_progress(current_page: int, total_pages: int, found_count: int) -> None:
            try:
                await update.callback_query.edit_message_text(
                    f"⏳ Загружаю все вакансии...\n"
                    f"📄 Страница: {current_page}\n"
                    f"📊 Найдено: {found_count} вакансий"
                )
            except:
                pass
        
        # Parse all remaining pages
        async with GszParser() as parser:
            all_vacancies = await parser.parse_vacancies(
                profession=search_params["profession"],
                city=search_params["city"],
                company_name=search_params["company_name"],
                limit=None,  # No limit - get all
                progress_callback=update_progress,
            )
        
        # Save to database
        db = next(get_db())
        vacancy_repo = VacancyRepository(db)
        
        for vacancy_data in all_vacancies:
            existing = vacancy_repo.get_by_external_id_and_source(
                vacancy_data["external_id"], vacancy_data["source"]
            )
            if not existing:
                vacancy_repo.create(vacancy_data)
        
        # Update context
        context.user_data[SEARCH_RESULTS_KEY] = all_vacancies
        # Keep original total count if it exists, otherwise use parsed count
        original_total = context.user_data.get("total_vacancies")
        if original_total:
            context.user_data["total_vacancies"] = max(original_total, len(all_vacancies))
        else:
            context.user_data["total_vacancies"] = len(all_vacancies)
        context.user_data["parsed_pages"] = 999  # Mark as fully parsed
        
        # Show first batch
        await show_search_results_batch(update, context, batch=0)
        
    except Exception as e:
        logger.error(f"Error loading all vacancies: {e}", exc_info=True)
        await update.callback_query.edit_message_text(
            "❌ Ошибка при загрузке всех вакансий. Попробуйте позже."
        )


async def search_batch_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle batch pagination callback for search results."""
    query = update.callback_query
    await query.answer()

    # Extract batch number from callback data
    callback_data = query.data
    if callback_data == "noop":
        return
    
    if callback_data.startswith("search_batch:"):
        batch = int(callback_data.split(":")[1])
        await show_search_results_batch(update, context, batch=batch)
    elif callback_data == "search_load_all":
        await load_all_vacancies(update, context)


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
        loading_msg = await query.edit_message_text(
            f"⏳ Ищу вакансии по фильтру <b>\"{filter_obj.name}\"</b>...",
            parse_mode="HTML",
        )

        # Progress tracking
        last_progress_update = 0

        async def update_progress(current_page: int, total_pages: int, found_count: int) -> None:
            """Update progress message."""
            nonlocal last_progress_update
            
            # Update progress every page or every 3 seconds
            import time
            current_time = time.time()
            if current_time - last_progress_update < 3 and current_page > 0:
                return  # Skip if updated recently
            
            last_progress_update = current_time
            
            # Calculate progress percentage
            if total_pages > 0:
                progress_pct = min(int((current_page / total_pages) * 100), 100)
            else:
                progress_pct = 0
            
            # Create progress bar
            bar_length = 10
            filled = int(bar_length * progress_pct / 100)
            bar = "█" * filled + "░" * (bar_length - filled)
            
            progress_text = (
                f"⏳ <b>Ищу вакансии по фильтру \"{filter_obj.name}\"...</b>\n\n"
                f"📄 Страница: {current_page}/{total_pages if total_pages > 0 else '?'}\n"
                f"📊 Найдено: {found_count} вакансий\n"
                f"📈 Прогресс: [{bar}] {progress_pct}%"
            )
            
            try:
                await loading_msg.edit_text(progress_text, parse_mode="HTML")
            except Exception as e:
                logger.debug(f"Could not update progress message: {e}")

        # First, get exact total count of vacancies from the page
        async with GszParser() as parser:
            total_vacancies = await parser.get_total_vacancies_count(profession, city, company_name)
            
            # If exact count not found, estimate from pages
            if total_vacancies is None:
                total_pages = await parser.get_total_pages(profession, city, company_name)
                total_vacancies = total_pages * 20  # ~20 vacancies per page
                logger.info(f"Estimated total vacancies: {total_vacancies} (from {total_pages} pages)")
            else:
                logger.info(f"Found exact total vacancies count: {total_vacancies}")
            
            # Parse first batch of vacancies (first page to show immediately)
            vacancies = await parser.parse_vacancies(
                profession=profession,
                city=city,
                company_name=company_name,
                limit=VACANCIES_PER_PAGE,  # Parse first 20 for immediate display
                progress_callback=update_progress,
            )

        if not vacancies:
            await loading_msg.edit_text(
                f"❌ Вакансии по фильтру <b>\"{filter_obj.name}\"</b> не найдены.\n\n"
                "Попробуйте изменить параметры фильтра или использовать другой фильтр.",
                parse_mode="HTML",
            )
            return

        # Save search parameters for lazy loading more pages
        context.user_data[SEARCH_PARAMS_KEY] = {
            "profession": profession,
            "city": city,
            "company_name": company_name,
        }

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
        context.user_data["total_vacancies"] = total_vacancies  # Exact or estimated count
        context.user_data["parsed_pages"] = 1

        # Show first batch of 20 vacancies
        await show_search_results_batch(update, context, batch=0, message=loading_msg)

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
search_page_handler = CallbackQueryHandler(search_batch_callback, pattern="^search_batch:|^search_load_all$")
search_filter_handler = CallbackQueryHandler(search_filter_callback, pattern="^search_filter:")
search_manual_handler = CallbackQueryHandler(search_manual_callback, pattern="^search_manual$")