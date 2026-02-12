# Подключение PostgreSQL на DigitalOcean

## Шаг 1: Добавить базу данных в App Platform

1. Откройте [cloud.digitalocean.com/apps](https://cloud.digitalocean.com/apps)
2. Выберите своё приложение (бот)
3. Нажмите **Add Component** → **Create Database**
4. Выберите:
   - **Database Engine:** PostgreSQL
   - **Plan:** Basic ($15/мес) или Dev Database (бесплатно, без бэкапов)
5. Нажмите **Create and Attach**

## Шаг 2: Проверить подключение

DigitalOcean автоматически добавит переменную `DATABASE_URL` в ваше приложение при связывании.

1. В настройках приложения откройте **Settings** → **App** → **Environment Variables**
2. Должна появиться переменная `DATABASE_URL` (её подставляет Database компонент)

## Шаг 3: Задеплоить изменения

В `requirements.txt` уже добавлен `psycopg2-binary` — драйвер для PostgreSQL.

Закоммитьте и запушьте изменения — приложение пересоберётся и подключится к PostgreSQL.

## Временный обход: USE_SQLITE=1

Пока PostgreSQL не настроен — добавьте в **App** → **Environment Variables**:
- **Key:** `USE_SQLITE`
- **Value:** `1`

Приложение будет использовать SQLite и запустится. Данные будут теряться при каждом деплое. Когда настроите PostgreSQL и выполните GRANT — удалите `USE_SQLITE`.

---

## Шаг 4: Выдать права (PostgreSQL 15+)

При ошибке `permission denied for schema public` нужно один раз выполнить GRANT.

### Dev Database (нет отдельного кластера в Databases)

Подключение только от приложения. Используйте **консоль приложения**:

1. App → вкладка **Console** → выберите компонент (ваш сервис)
2. В открывшемся shell выполните:
   ```bash
   cd /workspace
   python scripts/grant_schema_from_app.py
   ```
3. Удалите `USE_SQLITE=1` из переменных окружения и перезапустите приложение.

### Managed Database (есть в Databases)

1. Databases → кластер → **Connection Details**
2. Добавьте свой IP в **Trusted Sources**
3. Подключитесь через psql и выполните:
   ```sql
   GRANT USAGE ON SCHEMA public TO your_user;
   GRANT CREATE ON SCHEMA public TO your_user;
   ```
4. Перезапустите приложение.

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
