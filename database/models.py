"""Database models."""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base


class User(Base):
    """User model."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    telegram_id: Mapped[int] = mapped_column(Integer, unique=True, index=True, nullable=False)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str] = mapped_column(String(255), nullable=False)
    last_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    last_activity: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    filters: Mapped[list["Filter"]] = relationship("Filter", back_populates="user", cascade="all, delete-orphan")
    monitoring_tasks: Mapped[list["MonitoringTask"]] = relationship(
        "MonitoringTask", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, telegram_id={self.telegram_id}, username={self.username})>"


class Vacancy(Base):
    """Vacancy model."""

    __tablename__ = "vacancies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    date_posted: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    company_name: Mapped[str] = mapped_column(String(500), nullable=False)
    company_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    position: Mapped[str] = mapped_column(String(500), nullable=False)
    vacancies_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    salary: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    contact_person: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Может быть длинным (весь блок контактов)
    contact_phone: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Может содержать доп. текст
    url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<Vacancy(id={self.id}, source={self.source}, position={self.position})>"


class Filter(Base):
    """Filter model."""

    __tablename__ = "filters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    profession: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    company_name: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="filters")
    monitoring_tasks: Mapped[list["MonitoringTask"]] = relationship(
        "MonitoringTask", back_populates="filter", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Filter(id={self.id}, user_id={self.user_id}, name={self.name})>"


class MonitoringTask(Base):
    """Monitoring task model."""

    __tablename__ = "monitoring_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    filter_id: Mapped[int] = mapped_column(Integer, ForeignKey("filters.id"), nullable=False, index=True)
    interval_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    last_check: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="monitoring_tasks")
    filter: Mapped["Filter"] = relationship("Filter", back_populates="monitoring_tasks")

    def __repr__(self) -> str:
        return f"<MonitoringTask(id={self.id}, user_id={self.user_id}, filter_id={self.filter_id})>"
