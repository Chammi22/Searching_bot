"""User repository."""

from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import User


class UserRepository:
    """Repository for User model."""

    def __init__(self, db: Session) -> None:
        """Initialize repository with database session."""
        self.db = db

    def get_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID."""
        return self.db.get(User, user_id)

    def get_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """Get user by Telegram ID."""
        stmt = select(User).where(User.telegram_id == telegram_id)
        return self.db.scalar(stmt)

    def create(
        self,
        telegram_id: int,
        username: Optional[str],
        first_name: str,
        last_name: Optional[str] = None,
        is_admin: bool = False,
    ) -> User:
        """Create new user."""
        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            is_admin=is_admin,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def update_activity(self, user_id: int) -> None:
        """Update user's last activity timestamp."""
        user = self.db.get(User, user_id)
        if user:
            user.last_activity = datetime.utcnow()
            self.db.commit()

    def get_all_active(self) -> list[User]:
        """Get all active users."""
        stmt = select(User).where(User.is_active == True)
        return list(self.db.scalars(stmt).all())

    def get_all_admins(self) -> list[User]:
        """Get all admin users."""
        stmt = select(User).where(User.is_admin == True)
        return list(self.db.scalars(stmt).all())
