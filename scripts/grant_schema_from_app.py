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
    print(f"Пользователь из DATABASE_URL: {db_user}")

    from sqlalchemy import create_engine, text

    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            conn.execute(text(f"GRANT ALL ON SCHEMA public TO {db_user}"))
            conn.commit()
        print(f"GRANT ALL выполнен для пользователя {db_user}")
        # Проверка: создаём тестовую таблицу
        with engine.connect() as conn:
            conn.execute(text("CREATE TABLE IF NOT EXISTS _perm_test (id int)"))
            conn.execute(text("DROP TABLE IF EXISTS _perm_test"))
            conn.commit()
        print("Проверка OK: CREATE TABLE работает")
    except Exception as e:
        print(f"Ошибка: {e}")
        print("Требуется суперпользователь (postgres/doadmin). Проверьте Connection String в DO.")
        sys.exit(1)

if __name__ == "__main__":
    main()
