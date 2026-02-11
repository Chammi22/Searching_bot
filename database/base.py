"""Database base configuration."""

from sqlalchemy import create_engine
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
    # Import models to ensure they are registered with Base
    from database.models import User, Vacancy, Filter, MonitoringTask  # noqa: F401
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
