"""Vacancy repository."""

from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import Vacancy


class VacancyRepository:
    """Repository for Vacancy model."""

    def __init__(self, db: Session) -> None:
        """Initialize repository with database session."""
        self.db = db

    def get_by_external_id_and_source(self, external_id: str, source: str) -> Optional[Vacancy]:
        """Get vacancy by external ID and source."""
        stmt = select(Vacancy).where(
            Vacancy.external_id == external_id, Vacancy.source == source
        )
        return self.db.scalar(stmt)

    def create(self, vacancy_data: dict) -> Vacancy:
        """Create new vacancy."""
        vacancy = Vacancy(**vacancy_data)
        self.db.add(vacancy)
        self.db.commit()
        self.db.refresh(vacancy)
        return vacancy

    def search(
        self,
        profession: Optional[str] = None,
        city: Optional[str] = None,
        company_name: Optional[str] = None,
        limit: int = 100,
    ) -> list[Vacancy]:
        """Search vacancies by criteria."""
        stmt = select(Vacancy)

        if profession:
            stmt = stmt.where(Vacancy.position.ilike(f"%{profession}%"))

        if city:
            stmt = stmt.where(Vacancy.company_address.ilike(f"%{city}%"))

        if company_name:
            stmt = stmt.where(Vacancy.company_name.ilike(f"%{company_name}%"))

        stmt = stmt.order_by(Vacancy.date_posted.desc()).limit(limit)
        return list(self.db.scalars(stmt).all())

    def get_recent(self, days: int = 7, limit: int = 100) -> list[Vacancy]:
        """Get recent vacancies."""
        cutoff_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        cutoff_date = cutoff_date.replace(day=cutoff_date.day - days)

        stmt = (
            select(Vacancy)
            .where(Vacancy.created_at >= cutoff_date)
            .order_by(Vacancy.created_at.desc())
            .limit(limit)
        )
        return list(self.db.scalars(stmt).all())
