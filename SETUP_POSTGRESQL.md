# Подключение PostgreSQL на DigitalOcean

## Важно: Dev Database не подходит

**Dev Database** — ограниченная бесплатная БД. Она **не может**:
- создавать схемы,
- выдавать права на схему `public`,
- управлять ролями.

Из‑за PostgreSQL 15 приложение не может создавать таблицы в `public`. **Нужен Managed Database** (Basic $15/мес или выше).

---

## Шаг 1: Создать Managed Database

1. [Databases](https://cloud.digitalocean.com/databases) → **Create Database Cluster**
2. Выберите PostgreSQL, план **Basic** ($15/мес), регион (как у приложения)
3. Создайте кластер
4. В кластере: **Connection Details** → скопируйте **Connection string**
5. В **Trusted Sources** → **Add** → выберите ваше приложение (чтобы оно могло подключаться)

## Шаг 2: Подключить к приложению

1. [Apps](https://cloud.digitalocean.com/apps) → ваше приложение → **Settings**
2. **App-Level Environment Variables** → Edit
3. Удалите старую `DATABASE_URL` от Dev Database (если есть)
4. Добавьте `DATABASE_URL` = connection string из Managed Database
5. Удалите `USE_SQLITE=1` (если был)

## Шаг 3: Выдать права (PostgreSQL 15+)

1. В **Trusted Sources** Managed Database добавьте свой IP (если хотите подключиться с Mac)
2. Подключитесь через psql:
   ```bash
   psql "postgresql://doadmin:PASSWORD@host:25060/defaultdb?sslmode=require"
   ```
3. Выполните (замените `doadmin` на вашего пользователя из connection string):
   ```sql
   GRANT ALL ON SCHEMA public TO doadmin;
   ```
4. Сохраните и перезапустите приложение.

## Шаг 4: Задеплоить

В `requirements.txt` уже есть `psycopg2-binary`. Закоммитьте и запушьте — приложение подключится к Managed Database.

---

## Временный обход: USE_SQLITE=1

Пока Managed Database не настроен — добавьте в **App** → **Environment Variables**:
- **Key:** `USE_SQLITE`
- **Value:** `1`

Приложение будет использовать SQLite и запустится. Данные будут теряться при каждом деплое.

## Шаг 5: Проверка

После деплоя в логах должно появиться:
```
Database: PostgreSQL (persistent)
```

---

## Альтернатива: создать Managed Database отдельно

Если хотите создать базу вне App Platform:

1. [Databases](https://cloud.digitalocean.com/databases) → **Create Database Cluster**
2. Выберите PostgreSQL, план, регион
3. Создайте кластер
4. В кластере: **Connection Details** → скопируйте **Connection string**
5. В приложении добавьте переменную окружения:
   - **Key:** `DATABASE_URL`
   - **Value:** вставьте connection string (типа `postgresql://doadmin:xxx@host:25060/defaultdb?sslmode=require`)
6. В **Trusted Sources** добавьте ваш App, чтобы приложение могло подключаться
