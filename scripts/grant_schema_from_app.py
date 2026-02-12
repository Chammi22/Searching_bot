#!/usr/bin/env python3
"""
Выполнить GRANT для PostgreSQL через консоль приложения.
Запускать в App Platform Console (подключение идёт от приложения = trusted source).

В консоли: python scripts/grant_schema_from_app.py
"""
import os
import sys
from urllib.parse import urlparse

# Добавляем корень проекта в path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL не задан")
        sys.exit(1)
    if "postgres" not in url:
        print("DATABASE_URL не PostgreSQL, пропускаем")
        sys.exit(0)

    url = url.replace("postgres://", "postgresql://", 1)

    # Извлекаем имя пользователя из URL
    db_user = urlparse(url).username or "db"

    from sqlalchemy import create_engine, text

    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            conn.execute(text(f"GRANT USAGE ON SCHEMA public TO {db_user}"))
            conn.execute(text(f"GRANT CREATE ON SCHEMA public TO {db_user}"))
            conn.commit()
        print(f"GRANT выполнен для пользователя {db_user}")
    except Exception as e:
        print(f"Ошибка: {e}")
        print("Возможно, у пользователя нет прав. Попробуйте другого пользователя.")
        sys.exit(1)

if __name__ == "__main__":
    main()
