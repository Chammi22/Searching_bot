"""Filter repository."""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import Filter


class FilterRepository:
    """Repository for Filter model."""

    def __init__(self, db: Session) -> None:
        """Initialize repository with database session."""
        self.db = db

    def get_by_id(self, filter_id: int) -> Optional[Filter]:
        """Get filter by ID."""
        return self.db.get(Filter, filter_id)

    def get_by_user_id(self, user_id: int) -> list[Filter]:
        """Get all filters for a user."""
        stmt = select(Filter).where(Filter.user_id == user_id).order_by(Filter.created_at.desc())
        return list(self.db.scalars(stmt).all())

    def get_active_by_user_id(self, user_id: int) -> list[Filter]:
        """Get active filters for a user."""
        stmt = (
            select(Filter)
            .where(Filter.user_id == user_id, Filter.is_active == True)
            .order_by(Filter.created_at.desc())
        )
        return list(self.db.scalars(stmt).all())

    def create(self, filter_data: dict) -> Filter:
        """Create new filter."""
        filter_obj = Filter(**filter_data)
        self.db.add(filter_obj)
        self.db.commit()
        self.db.refresh(filter_obj)
        return filter_obj

    def update(self, filter_id: int, filter_data: dict) -> Optional[Filter]:
        """Update filter."""
        filter_obj = self.db.get(Filter, filter_id)
        if filter_obj:
            for key, value in filter_data.items():
                setattr(filter_obj, key, value)
            self.db.commit()
            self.db.refresh(filter_obj)
        return filter_obj

    def delete(self, filter_id: int) -> bool:
        """Delete filter."""
        filter_obj = self.db.get(Filter, filter_id)
        if filter_obj:
            self.db.delete(filter_obj)
            self.db.commit()
            return True
        return False
