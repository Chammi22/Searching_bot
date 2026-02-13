"""Database base configuration."""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from config.logging_config import get_logger
from config.settings import settings

logger = get_logger(__name__)

# USE_SQLITE=1 — временно использовать SQLite (данные теряются при деплое, но приложение запускается)
if settings.use_sqlite:
    database_url = "sqlite:///./vacancies.db"
    settings.get_database_path()  # создать директорию если нужно
    logger.info("Database: SQLite (USE_SQLITE=1)")
else:
    database_url = settings.database_url
    if database_url.startswith("postgres://"):
        database_url = "postgresql://" + database_url[9:]
    if "sqlite" in database_url:
        logger.info(f"Database path: {settings.get_database_path()}")
    else:
        logger.info("Database: PostgreSQL (persistent)")

engine = create_engine(
    database_url,
    echo=False,
    connect_args={"check_same_thread": False} if "sqlite" in database_url else {},
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base class for all models."""

    pass


def init_db() -> None:
    """Initialize database - create all tables."""
    from database.models import User, Vacancy, Filter, MonitoringTask  # noqa: F401

    Base.metadata.create_all(bind=engine)

    # Миграция: расширить contact_person и contact_phone для PostgreSQL (были varchar)
    if "postgresql" in database_url:
        try:
            with engine.connect() as conn:
                conn.execute(text(
                    "ALTER TABLE vacancies ALTER COLUMN contact_person TYPE TEXT"
                ))
                conn.execute(text(
                    "ALTER TABLE vacancies ALTER COLUMN contact_phone TYPE TEXT"
                ))
                conn.commit()
            logger.info("Migration: contact_person, contact_phone -> TEXT")
        except Exception as e:
            # Игнорируем если уже TEXT или таблица новая
            logger.debug("Migration skip (already applied or new): %s", e)
