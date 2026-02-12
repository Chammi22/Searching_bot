#!/usr/bin/env python3
"""
Диагностика подключения к БД. Запускать в App Console: python scripts/check_db.py
"""
import os
from urllib.parse import urlparse

url = os.environ.get("DATABASE_URL")
if not url:
    print("DATABASE_URL не задан")
    exit(1)

url = url.replace("postgres://", "postgresql://", 1)
parsed = urlparse(url)
user = parsed.username or "?"
host = parsed.hostname or "?"
db = parsed.path.strip("/") if parsed.path else "?"

print(f"Пользователь: {user}")
print(f"Хост: {host}")
print(f"База: {db}")

try:
    from sqlalchemy import create_engine, text
    engine = create_engine(url)
    with engine.connect() as conn:
        row = conn.execute(text("SELECT version()")).fetchone()
        print(f"PostgreSQL: {row[0][:80]}...")
        # Права на public
        row2 = conn.execute(text("""
            SELECT has_schema_privilege(current_user, 'public', 'CREATE')
        """)).fetchone()
        print(f"CREATE в public: {row2[0]}")
except Exception as e:
    print(f"Ошибка: {e}")
