"""Database base configuration."""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from config.logging_config import get_logger
from config.settings import settings

logger = get_logger(__name__)

# Database URL (PostgreSQL для облака, SQLite локально)
database_url = settings.database_url
if database_url.startswith("postgres://"):
    database_url = "postgresql://" + database_url[9:]  # Heroku/DO дают postgres://

if "sqlite" in database_url:
    db_path = settings.get_database_path()
    logger.info(f"Database path: {db_path}")
    SCHEMA = None
else:
    logger.info("Database: PostgreSQL (persistent)")
    SCHEMA = "app"  # Своя схема — обходим "permission denied for schema public" (PostgreSQL 15+)

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

    if SCHEMA:
        # PostgreSQL 15+: своя схема — обходим "permission denied for schema public"
        with engine.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA}"'))
        for table in Base.metadata.tables.values():
            table.schema = SCHEMA

    Base.metadata.create_all(bind=engine)
