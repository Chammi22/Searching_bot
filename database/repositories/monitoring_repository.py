"""Monitoring task repository."""

from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import MonitoringTask


class MonitoringRepository:
    """Repository for MonitoringTask model."""

    def __init__(self, db: Session) -> None:
        """Initialize repository with database session."""
        self.db = db

    def get_by_id(self, task_id: int) -> Optional[MonitoringTask]:
        """Get monitoring task by ID."""
        return self.db.get(MonitoringTask, task_id)

    def get_by_user_id(self, user_id: int) -> list[MonitoringTask]:
        """Get all monitoring tasks for a user."""
        stmt = (
            select(MonitoringTask)
            .where(MonitoringTask.user_id == user_id)
            .order_by(MonitoringTask.created_at.desc())
        )
        return list(self.db.scalars(stmt).all())

    def get_active_tasks(self) -> list[MonitoringTask]:
        """Get all active monitoring tasks."""
        stmt = select(MonitoringTask).where(MonitoringTask.is_active == True)
        return list(self.db.scalars(stmt).all())

    def get_active_by_user_id(self, user_id: int) -> list[MonitoringTask]:
        """Get active monitoring tasks for a user."""
        stmt = select(MonitoringTask).where(
            MonitoringTask.user_id == user_id, MonitoringTask.is_active == True
        )
        return list(self.db.scalars(stmt).all())

    def create(self, task_data: dict) -> MonitoringTask:
        """Create new monitoring task."""
        task = MonitoringTask(**task_data)
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def update_last_check(self, task_id: int) -> None:
        """Update last check timestamp."""
        task = self.db.get(MonitoringTask, task_id)
        if task:
            task.last_check = datetime.utcnow()
            self.db.commit()

    def update(self, task_id: int, task_data: dict) -> Optional[MonitoringTask]:
        """Update monitoring task."""
        task = self.db.get(MonitoringTask, task_id)
        if task:
            for key, value in task_data.items():
                setattr(task, key, value)
            self.db.commit()
            self.db.refresh(task)
        return task

    def delete(self, task_id: int) -> bool:
        """Delete monitoring task."""
        task = self.db.get(MonitoringTask, task_id)
        if task:
            self.db.delete(task)
            self.db.commit()
            return True
        return False
