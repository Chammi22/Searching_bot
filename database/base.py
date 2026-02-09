"""Database base configuration."""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from config.settings import settings

# Create engine
engine = create_engine(
    settings.database_url,
    echo=False,  # Set to True for SQL query logging
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
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
