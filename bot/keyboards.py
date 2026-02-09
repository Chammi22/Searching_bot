"""Keyboard layouts for the bot."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton


def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Get main menu keyboard."""
    keyboard = [
        [
            KeyboardButton("🔍 Поиск вакансий"),
            KeyboardButton("📋 Мои фильтры"),
        ],
        [
            KeyboardButton("🔔 Мониторинг"),
            KeyboardButton("📊 Статистика"),
        ],
        [
            KeyboardButton("📥 Экспорт"),
            KeyboardButton("ℹ️ Помощь"),
        ],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_pagination_keyboard(page: int, total_pages: int, callback_prefix: str) -> InlineKeyboardMarkup:
    """Get pagination keyboard."""
    buttons = []
    
    if total_pages > 1:
        nav_buttons = []
        if page > 0:
            nav_buttons.append(
                InlineKeyboardButton("◀️ Назад", callback_data=f"{callback_prefix}:{page-1}")
            )
        nav_buttons.append(
            InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="noop")
        )
        if page < total_pages - 1:
            nav_buttons.append(
                InlineKeyboardButton("Вперед ▶️", callback_data=f"{callback_prefix}:{page+1}")
            )
        buttons.append(nav_buttons)
    
    return InlineKeyboardMarkup(buttons)


def get_filter_actions_keyboard(filter_id: int) -> InlineKeyboardMarkup:
    """Get filter actions keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("✏️ Редактировать", callback_data=f"edit_filter:{filter_id}"),
            InlineKeyboardButton("🗑️ Удалить", callback_data=f"delete_filter:{filter_id}"),
        ],
        [
            InlineKeyboardButton("✅ Активировать", callback_data=f"activate_filter:{filter_id}"),
            InlineKeyboardButton("❌ Деактивировать", callback_data=f"deactivate_filter:{filter_id}"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)
