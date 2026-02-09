"""Base parser class for all parsers."""

from abc import ABC, abstractmethod
from typing import Optional

from config.logging_config import get_logger

logger = get_logger(__name__)


class BaseParser(ABC):
    """Base abstract class for all parsers."""

    def __init__(self, source_name: str, base_url: str) -> None:
        """
        Initialize base parser.

        Args:
            source_name: Name of the source (e.g., 'gsz.gov.by')
            base_url: Base URL of the source website
        """
        self.source_name = source_name
        self.base_url = base_url
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")

    @abstractmethod
    async def parse_vacancies(
        self,
        profession: Optional[str] = None,
        city: Optional[str] = None,
        company_name: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> list[dict]:
        """
        Parse vacancies from the source.

        Args:
            profession: Profession/specialty to search for
            city: City or region to search in
            company_name: Company name to search for
            limit: Maximum number of vacancies to return

        Returns:
            List of vacancy dictionaries
        """
        pass

    @abstractmethod
    async def parse_vacancy_detail(self, vacancy_url: str) -> Optional[dict]:
        """
        Parse detailed information about a specific vacancy.

        Args:
            vacancy_url: URL of the vacancy page

        Returns:
            Dictionary with detailed vacancy information or None if failed
        """
        pass

    @abstractmethod
    def build_search_url(
        self,
        profession: Optional[str] = None,
        city: Optional[str] = None,
        company_name: Optional[str] = None,
        page: int = 1,
    ) -> str:
        """
        Build search URL with parameters.

        Args:
            profession: Profession/specialty
            city: City or region
            company_name: Company name
            page: Page number for pagination

        Returns:
            Complete URL for search
        """
        pass

    @abstractmethod
    async def get_total_pages(
        self,
        profession: Optional[str] = None,
        city: Optional[str] = None,
        company_name: Optional[str] = None,
    ) -> int:
        """
        Get total number of pages for search results.

        Args:
            profession: Profession/specialty
            city: City or region
            company_name: Company name

        Returns:
            Total number of pages
        """
        pass

    def normalize_text(self, text: Optional[str]) -> Optional[str]:
        """
        Normalize text: strip whitespace, remove extra spaces.

        Args:
            text: Text to normalize

        Returns:
            Normalized text or None
        """
        if not text:
            return None
        return " ".join(text.strip().split())

    def extract_phone(self, text: Optional[str]) -> Optional[str]:
        """
        Extract phone number from text.

        Args:
            text: Text that may contain phone number

        Returns:
            Extracted phone number or None
        """
        if not text:
            return None
        # Basic phone extraction - can be improved with regex
        import re

        # Match Belarus phone numbers: +375 XX XXX-XX-XX or similar formats
        phone_pattern = r"(\+375\s?\d{2}\s?\d{3}[-.\s]?\d{2}[-.\s]?\d{2})"
        match = re.search(phone_pattern, text)
        if match:
            return match.group(1)
        return None
