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

При ошибке `permission denied for schema public` нужно один раз выполнить SQL:

1. **DigitalOcean App Platform:**  
   App → Settings → Database → **Connection** → откройте консоль или подключитесь через psql.

2. **Heroku:** в терминале: `heroku pg:psql -a имя-вашего-приложения`

3. Узнайте имя пользователя из `DATABASE_URL` (в строке `postgresql://USER:password@host/...`).

4. Выполните (замените `YOUR_DB_USER` на имя пользователя, например `doadmin` или `u123abc`):
   ```sql
   GRANT USAGE ON SCHEMA public TO YOUR_DB_USER;
   GRANT CREATE ON SCHEMA public TO YOUR_DB_USER;
   ```

5. Перезапустите приложение.

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
