"""Monitoring service for tracking new vacancies."""

import asyncio
from datetime import datetime
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from config.logging_config import get_logger
from database.session import get_db
from database.repositories.monitoring_repository import MonitoringRepository
from database.repositories.filter_repository import FilterRepository
from database.repositories.vacancy_repository import VacancyRepository
from database.repositories.user_repository import UserRepository
from parsers.gsz_parser import GszParser
from utils.helpers import format_vacancy_message

logger = get_logger(__name__)


class MonitoringService:
    """Service for managing monitoring tasks."""

    def __init__(self, bot_application) -> None:
        """Initialize monitoring service."""
        self.bot_application = bot_application
        self.scheduler = AsyncIOScheduler(
            timezone="UTC",
            job_defaults={
                "coalesce": True,  # Combine multiple pending executions into one
                "max_instances": 1,  # Only one instance of a job can run at a time
                "misfire_grace_time": 300,  # 5 minutes grace time
            },
        )
        self.scheduler.start()
        self._task_jobs: dict[int, str] = {}  # task_id -> job_id mapping
        logger.info("MonitoringService initialized, scheduler started")

    async def start_monitoring_task(self, task_id: int) -> bool:
        """
        Start monitoring for a specific task.

        Args:
            task_id: ID of the monitoring task

        Returns:
            True if task started successfully, False otherwise
        """
        try:
            db = next(get_db())
            monitoring_repo = MonitoringRepository(db)
            task = monitoring_repo.get_by_id(task_id)

            if not task:
                logger.error(f"Monitoring task {task_id} not found")
                return False

            if not task.is_active:
                logger.warning(f"Monitoring task {task_id} is not active")
                return False

            # Check if job already exists
            if task_id in self._task_jobs:
                logger.warning(f"Monitoring task {task_id} is already running")
                return False

            # Create job ID
            job_id = f"monitor_task_{task_id}"

            # Add job to scheduler
            # Note: IntervalTrigger starts after the interval, so we'll run first check immediately
            self.scheduler.add_job(
                self._check_new_vacancies,
                trigger=IntervalTrigger(hours=task.interval_hours),
                id=job_id,
                args=[task_id],
                replace_existing=True,
                misfire_grace_time=300,  # 5 minutes grace time for missed runs
            )

            self._task_jobs[task_id] = job_id
            logger.info(f"Started monitoring task {task_id} with interval {task.interval_hours} hours")
            
            # Run first check immediately (don't wait for interval)
            asyncio.create_task(self._check_new_vacancies(task_id))
            logger.info(f"Running initial check for task {task_id} immediately")
            
            return True

        except Exception as e:
            logger.error(f"Error starting monitoring task {task_id}: {e}", exc_info=True)
            return False

    async def stop_monitoring_task(self, task_id: int) -> bool:
        """
        Stop monitoring for a specific task.

        Args:
            task_id: ID of the monitoring task

        Returns:
            True if task stopped successfully, False otherwise
        """
        try:
            if task_id not in self._task_jobs:
                logger.warning(f"Monitoring task {task_id} is not running")
                return False

            job_id = self._task_jobs[task_id]
            self.scheduler.remove_job(job_id)
            del self._task_jobs[task_id]

            logger.info(f"Stopped monitoring task {task_id}")
            return True

        except Exception as e:
            logger.error(f"Error stopping monitoring task {task_id}: {e}", exc_info=True)
            return False

    async def _check_new_vacancies(self, task_id: int) -> None:
        """
        Check for new vacancies for a monitoring task.

        Args:
            task_id: ID of the monitoring task
        """
        try:
            db = next(get_db())
            monitoring_repo = MonitoringRepository(db)
            filter_repo = FilterRepository(db)
            vacancy_repo = VacancyRepository(db)
            user_repo = UserRepository(db)

            task = monitoring_repo.get_by_id(task_id)
            if not task or not task.is_active:
                logger.warning(f"Monitoring task {task_id} is not active, stopping")
                await self.stop_monitoring_task(task_id)
                return

            filter_obj = filter_repo.get_by_id(task.filter_id)
            if not filter_obj or not filter_obj.is_active:
                logger.warning(f"Filter {task.filter_id} is not active, stopping task {task_id}")
                await self.stop_monitoring_task(task_id)
                return

            user = user_repo.get_by_id(task.user_id)
            if not user:
                logger.warning(f"User {task.user_id} not found, stopping task {task_id}")
                await self.stop_monitoring_task(task_id)
                return

            logger.info(
                f"Checking new vacancies for task {task_id} "
                f"(filter: {filter_obj.name}, user: {user.telegram_id})"
            )

            # Parse vacancies using filter parameters
            # For monitoring, parse ALL pages to catch all new vacancies
            async with GszParser() as parser:
                vacancies = await parser.parse_vacancies(
                    profession=filter_obj.profession,
                    city=filter_obj.city,
                    company_name=filter_obj.company_name,
                    limit=None,  # No limit for monitoring - parse all vacancies
                    fetch_details=False,
                    filter_by_city=True,
                    parse_all_pages=True,  # Parse all pages for monitoring
                )

            # Find new vacancies that are not yet in database
            # For monitoring, we consider a vacancy "new" if it doesn't exist in database
            # (by external_id + source), regardless of date_posted
            # This ensures we catch all vacancies that appeared since monitoring started
            
            new_vacancies = []
            skipped_existing = 0
            
            for vacancy_data in vacancies:
                # Check if vacancy already exists in database
                existing = vacancy_repo.get_by_external_id_and_source(
                    vacancy_data["external_id"], vacancy_data["source"]
                )
                
                if existing:
                    # Vacancy already in database - skip (already processed)
                    skipped_existing += 1
                    continue
                
                # This is a new vacancy (not in database yet)
                # Save it to database
                saved_vacancy = vacancy_repo.create(vacancy_data)
                new_vacancies.append(saved_vacancy)
                logger.info(
                    f"Found new vacancy: {vacancy_data.get('position')} "
                    f"at {vacancy_data.get('company_name')} "
                    f"(external_id: {vacancy_data.get('external_id')})"
                )
            
            logger.info(
                f"Task {task_id} check complete: "
                f"{len(new_vacancies)} new vacancies found, {skipped_existing} already in database"
            )

            # Update last check time
            monitoring_repo.update_last_check(task_id)

            # Send notifications for new vacancies
            if new_vacancies:
                logger.info(f"Found {len(new_vacancies)} new vacancies for task {task_id}")
                await self._send_notifications(task.user_id, new_vacancies, filter_obj.name)
            else:
                logger.info(f"No new vacancies found for task {task_id}")

        except Exception as e:
            logger.error(f"Error checking new vacancies for task {task_id}: {e}", exc_info=True)

    async def _send_notifications(
        self, user_id: int, vacancies: list, filter_name: str
    ) -> None:
        """
        Send notifications about new vacancies to user.

        Args:
            user_id: User ID
            vacancies: List of new vacancies
            filter_name: Name of the filter that found these vacancies
        """
        try:
            db = next(get_db())
            user_repo = UserRepository(db)
            user = user_repo.get_by_id(user_id)

            if not user:
                logger.error(f"User {user_id} not found")
                return

            app = self.bot_application.app

            # Send notifications for each new vacancy
            # Send first few vacancies with details, then summary if there are more
            max_detailed = 5  # Show details for first 5 vacancies
            
            for i, vacancy in enumerate(vacancies[:max_detailed]):
                vacancy_dict = {
                    "position": vacancy.position,
                    "company_name": vacancy.company_name,
                    "company_address": vacancy.company_address,
                    "salary": vacancy.salary,
                    "vacancies_count": vacancy.vacancies_count,
                    "date_posted": vacancy.date_posted,
                    "contact_person": vacancy.contact_person,
                    "contact_phone": vacancy.contact_phone,
                    "url": vacancy.url,
                }
                
                if len(vacancies) == 1:
                    message = (
                        f"🔔 <b>Новая вакансия по фильтру \"{filter_name}\"</b>\n\n"
                        + format_vacancy_message(vacancy_dict)
                    )
                else:
                    message = (
                        f"🔔 <b>Новая вакансия {i+1}/{len(vacancies)} по фильтру \"{filter_name}\"</b>\n\n"
                        + format_vacancy_message(vacancy_dict)
                    )
                
                await app.bot.send_message(
                    chat_id=user.telegram_id,
                    text=message,
                    parse_mode="HTML",
                )
            
            # If there are more vacancies, send summary
            if len(vacancies) > max_detailed:
                remaining = len(vacancies) - max_detailed
                summary_message = (
                    f"🔔 <b>И еще {remaining} новых вакансий по фильтру \"{filter_name}\"</b>\n\n"
                    f"Всего найдено: {len(vacancies)} новых вакансий\n"
                    "Используйте /search для просмотра всех вакансий."
                )
                await app.bot.send_message(
                    chat_id=user.telegram_id,
                    text=summary_message,
                    parse_mode="HTML",
                )

            logger.info(f"Sent notification to user {user_id} about {len(vacancies)} new vacancies")

        except Exception as e:
            logger.error(f"Error sending notification to user {user_id}: {e}", exc_info=True)

    async def restore_tasks(self) -> None:
        """Restore all active monitoring tasks from database."""
        try:
            db = next(get_db())
            monitoring_repo = MonitoringRepository(db)
            active_tasks = monitoring_repo.get_active_tasks()

            logger.info(f"Restoring {len(active_tasks)} active monitoring tasks")

            for task in active_tasks:
                await self.start_monitoring_task(task.id)

            logger.info(f"Successfully restored {len(active_tasks)} monitoring tasks")

        except Exception as e:
            logger.error(f"Error restoring monitoring tasks: {e}", exc_info=True)

    async def shutdown(self) -> None:
        """Shutdown the monitoring service."""
        logger.info("Shutting down monitoring service...")
        self.scheduler.shutdown(wait=True)
        logger.info("Monitoring service shut down")
