"""Stats command handler."""

from datetime import datetime, timedelta

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from config.logging_config import get_logger
from database.session import get_db
from database.repositories.user_repository import UserRepository
from database.repositories.vacancy_repository import VacancyRepository
from database.repositories.filter_repository import FilterRepository
from database.repositories.monitoring_repository import MonitoringRepository
from utils.helpers import format_date

logger = get_logger(__name__)


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /stats command."""
    user = update.effective_user
    if not user:
        return

    try:
        db = next(get_db())
        user_repo = UserRepository(db)
        vacancy_repo = VacancyRepository(db)
        filter_repo = FilterRepository(db)
        monitoring_repo = MonitoringRepository(db)

        # Get user
        db_user = user_repo.get_by_telegram_id(user.id)
        if not db_user:
            await update.message.reply_text(
                "❌ Вы не зарегистрированы в системе. Используйте /start для регистрации."
            )
            return

        # Update activity
        user_repo.update_activity(db_user.id)

        # Get statistics
        # Total vacancies in database
        from sqlalchemy import select, func
        from database.models import Vacancy
        total_vacancies_stmt = select(func.count(Vacancy.id))
        total_vacancies = db.scalar(total_vacancies_stmt) or 0

        # Recent vacancies (last 7 days)
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        recent_vacancies_stmt = select(func.count(Vacancy.id)).where(
            Vacancy.created_at >= seven_days_ago
        )
        recent_vacancies = db.scalar(recent_vacancies_stmt) or 0

        # User's filters
        all_filters = filter_repo.get_by_user_id(db_user.id)
        active_filters = filter_repo.get_active_by_user_id(db_user.id)

        # User's monitoring tasks
        all_tasks = monitoring_repo.get_by_user_id(db_user.id)
        active_tasks = monitoring_repo.get_active_by_user_id(db_user.id)

        # Format statistics message
        stats_message = (
            "📊 <b>Ваша статистика:</b>\n\n"
            
            "👤 <b>Профиль:</b>\n"
            f"   • Дата регистрации: {format_date(db_user.created_at)}\n"
            f"   • Последняя активность: {format_date(db_user.last_activity)}\n"
            f"   • Статус: {'✅ Активен' if db_user.is_active else '❌ Неактивен'}\n"
            f"   • Права: {'👑 Администратор' if db_user.is_admin else '👤 Пользователь'}\n\n"
            
            "📋 <b>База вакансий:</b>\n"
            f"   • Всего вакансий: {total_vacancies}\n"
            f"   • За последние 7 дней: {recent_vacancies}\n\n"
            
            "🔍 <b>Фильтры поиска:</b>\n"
            f"   • Всего фильтров: {len(all_filters)}\n"
            f"   • Активных фильтров: {len(active_filters)}\n\n"
            
            "🔔 <b>Задачи мониторинга:</b>\n"
            f"   • Всего задач: {len(all_tasks)}\n"
            f"   • Активных задач: {len(active_tasks)}\n"
        )

        # Add details about active monitoring tasks
        if active_tasks:
            stats_message += "\n📌 <b>Активные задачи мониторинга:</b>\n"
            for task in active_tasks[:5]:  # Show up to 5 tasks
                filter_obj = filter_repo.get_by_id(task.filter_id)
                filter_name = filter_obj.name if filter_obj else f"Фильтр #{task.filter_id}"
                last_check = format_date(task.last_check) if task.last_check else "Никогда"
                stats_message += (
                    f"   • {filter_name}\n"
                    f"     Интервал: {task.interval_hours} ч | Последняя проверка: {last_check}\n"
                )
            if len(active_tasks) > 5:
                stats_message += f"   ... и ещё {len(active_tasks) - 5} задач\n"

        # Add details about active filters
        if active_filters:
            stats_message += "\n📝 <b>Активные фильтры:</b>\n"
            for filter_obj in active_filters[:5]:  # Show up to 5 filters
                filter_desc = []
                if filter_obj.profession:
                    filter_desc.append(f"Профессия: {filter_obj.profession}")
                if filter_obj.city:
                    filter_desc.append(f"Город: {filter_obj.city}")
                if filter_obj.company_name:
                    filter_desc.append(f"Компания: {filter_obj.company_name}")
                desc = " | ".join(filter_desc) if filter_desc else "Без параметров"
                stats_message += f"   • {filter_obj.name}: {desc}\n"
            if len(active_filters) > 5:
                stats_message += f"   ... и ещё {len(active_filters) - 5} фильтров\n"

        await update.message.reply_text(stats_message, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Error getting statistics: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ Произошла ошибка при получении статистики. Попробуйте позже."
        )


# Handler
stats_handler = CommandHandler("stats", stats_command)
