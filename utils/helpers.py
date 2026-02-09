"""Helper functions."""

from datetime import datetime
from typing import Optional


def format_date(date: Optional[datetime]) -> str:
    """Format datetime to string."""
    if not date:
        return "Не указано"
    return date.strftime("%d.%m.%Y %H:%M")


def format_vacancy_message(vacancy: dict) -> str:
    """Format vacancy data to message."""
    message = (
        f"<b>{vacancy.get('position', 'Не указано')}</b>\n\n"
        f"🏢 <b>Компания:</b> {vacancy.get('company_name', 'Не указано')}\n"
    )

    if vacancy.get('company_address'):
        message += f"📍 <b>Адрес:</b> {vacancy['company_address']}\n"

    if vacancy.get('salary'):
        message += f"💰 <b>Зарплата:</b> {vacancy['salary']}\n"

    if vacancy.get('vacancies_count'):
        message += f"👥 <b>Вакантных мест:</b> {vacancy['vacancies_count']}\n"

    if vacancy.get('date_posted'):
        message += f"📅 <b>Дата размещения:</b> {format_date(vacancy['date_posted'])}\n"

    if vacancy.get('contact_person'):
        message += f"👤 <b>Контактное лицо:</b> {vacancy['contact_person']}\n"

    if vacancy.get('contact_phone'):
        message += f"📞 <b>Телефон:</b> {vacancy['contact_phone']}\n"

    if vacancy.get('url'):
        message += f"\n🔗 <a href='{vacancy['url']}'>Подробнее на сайте</a>"

    return message


def truncate_text(text: str, max_length: int = 100) -> str:
    """Truncate text to max length."""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."
