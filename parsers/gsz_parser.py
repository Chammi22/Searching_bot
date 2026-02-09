"""Parser for gsz.gov.by website."""

import asyncio
import random
from datetime import datetime
from typing import Awaitable, Callable, Optional
from urllib.parse import quote, urljoin

import aiohttp
from bs4 import BeautifulSoup

from config.logging_config import get_logger
from config.settings import settings
from parsers.base_parser import BaseParser
from parsers.rate_limiter import RateLimiter, RequestThrottler, UserAgentRotator
from schemas.vacancy import VacancySchema
from utils.exceptions import ParserError

logger = get_logger(__name__)


class GszParser(BaseParser):
    """Parser for gsz.gov.by website."""

    def __init__(self) -> None:
        """Initialize GSZ parser."""
        super().__init__(
            source_name="gsz.gov.by",
            base_url="https://gsz.gov.by",
        )
        self.session: Optional[aiohttp.ClientSession] = None
        self.user_agent_rotator = UserAgentRotator()
        self.rate_limiter = RateLimiter(
            min_delay=settings.parser_delay_between_requests,
            max_delay=settings.parser_delay_between_requests * 1.5,
            jitter=True,
        )
        self.request_throttler = RequestThrottler(
            requests_per_minute=20,  # Conservative limit
            requests_per_hour=500,  # Conservative limit
        )
        self._update_headers()

    def _update_headers(self) -> None:
        """Update headers with rotated User-Agent."""
        self.headers = {
            "User-Agent": self.user_agent_rotator.get_random(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Cache-Control": "max-age=0",
        }

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            # Create connector with SSL verification disabled (for development)
            # In production, should use proper SSL certificates
            connector = aiohttp.TCPConnector(
                ssl=False,
                limit=settings.parser_max_concurrent_requests,  # Limit concurrent connections
            )
            # Update headers with new User-Agent
            self._update_headers()
            self.session = aiohttp.ClientSession(
                headers=self.headers,
                timeout=timeout,
                connector=connector,
            )
        return self.session

    async def close(self) -> None:
        """Close aiohttp session."""
        if self.session and not self.session.closed:
            await self.session.close()

    async def _fetch_page(self, url: str, retries: int = 3) -> Optional[str]:
        """
        Fetch page content with retry mechanism and rate limiting.

        Args:
            url: URL to fetch
            retries: Number of retry attempts

        Returns:
            HTML content or None if failed
        """
        # Check throttler before making request
        if not await self.request_throttler.can_make_request():
            # Wait a bit if we're rate limited
            await asyncio.sleep(5)
        
        # Wait for rate limiter
        await self.rate_limiter.wait()
        
        session = await self._get_session()
        for attempt in range(retries):
            try:
                # Rotate User-Agent every few requests
                if attempt == 0 and random.random() < 0.3:  # 30% chance to rotate
                    self._update_headers()
                    # Update session headers
                    session.headers.update(self.headers)
                
                async with session.get(url) as response:
                    # Record successful request
                    await self.request_throttler.record_request()
                    
                    if response.status == 200:
                        return await response.text()
                    elif response.status == 404:
                        self.logger.warning(f"Page not found: {url}")
                        return None
                    elif response.status == 429:  # Too Many Requests
                        # Rate limited - wait longer
                        wait_time = int(response.headers.get("Retry-After", 60))
                        self.logger.warning(
                            f"Rate limited (429) for {url}, waiting {wait_time}s, "
                            f"attempt {attempt + 1}/{retries}"
                        )
                        if attempt < retries - 1:
                            await asyncio.sleep(wait_time)
                        continue
                    elif response.status == 503:
                        # Service Unavailable - server is overloaded
                        self.logger.warning(
                            f"Service unavailable (503) for {url}, attempt {attempt + 1}/{retries}"
                        )
                        # For 503, use longer backoff
                        if attempt < retries - 1:
                            wait_time = 5 * (attempt + 1) + random.uniform(0, 3)  # Add jitter
                            await asyncio.sleep(wait_time)
                        continue
                    elif response.status == 403:  # Forbidden - might be IP ban
                        self.logger.error(
                            f"Forbidden (403) for {url} - possible IP ban, "
                            f"attempt {attempt + 1}/{retries}"
                        )
                        if attempt < retries - 1:
                            # Wait longer for 403
                            await asyncio.sleep(30 * (attempt + 1))
                        continue
                    else:
                        self.logger.warning(
                            f"Unexpected status {response.status} for {url}, "
                            f"attempt {attempt + 1}/{retries}"
                        )
            except asyncio.TimeoutError:
                self.logger.warning(f"Timeout fetching {url}, attempt {attempt + 1}/{retries}")
            except Exception as e:
                self.logger.error(f"Error fetching {url}: {e}, attempt {attempt + 1}/{retries}")

            if attempt < retries - 1:
                # Exponential backoff with jitter
                backoff_time = (2 ** attempt) + random.uniform(0, 1)
                await asyncio.sleep(backoff_time)

        return None

    def build_search_url(
        self,
        profession: Optional[str] = None,
        city: Optional[str] = None,
        company_name: Optional[str] = None,
        page: int = 1,
    ) -> str:
        """
        Build search URL for gsz.gov.by.

        Args:
            profession: Profession/specialty
            city: City or region
            company_name: Company name
            page: Page number

        Returns:
            Complete search URL
        """
        # Base URL for vacancy search
        base_search_url = f"{self.base_url}/registration/vacancy-search/"

        params = []
        if profession:
            params.append(f"profession={quote(profession)}")
        if city:
            # Note: city filtering might need to be done via business_entity parameter
            # For now, we'll include it in params
            params.append(f"city={quote(city)}")
        if company_name:
            params.append(f"business_entity={quote(company_name)}")
        
        # Filter for foreign citizens (as per requirements)
        params.append("for_foreigner=on")
        
        # Pagination
        params.append(f"paginate_by=20")
        if page > 1:
            params.append(f"page={page}")

        if params:
            return f"{base_search_url}?{'&'.join(params)}"
        return base_search_url

    async def get_total_vacancies_count(
        self,
        profession: Optional[str] = None,
        city: Optional[str] = None,
        company_name: Optional[str] = None,
    ) -> Optional[int]:
        """
        Get total number of vacancies from search results page.
        
        Looks for text like "Количество заявленных вакансий: 4442"

        Args:
            profession: Profession/specialty
            city: City or region
            company_name: Company name

        Returns:
            Total number of vacancies or None if not found
        """
        url = self.build_search_url(profession, city, company_name, page=1)
        html = await self._fetch_page(url)
        if not html:
            return None

        try:
            import re
            soup = BeautifulSoup(html, "html.parser")
            
            # Look for text containing "Количество заявленных вакансий" or similar
            # Patterns to search for:
            patterns = [
                r"Количество заявленных вакансий:\s*(\d+)",
                r"Количество вакансий:\s*(\d+)",
                r"Найдено вакансий:\s*(\d+)",
                r"Всего вакансий:\s*(\d+)",
                r"вакансий[:\s]+(\d+)",
            ]
            
            # Search in all text content
            page_text = soup.get_text()
            
            for pattern in patterns:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match:
                    count = int(match.group(1))
                    self.logger.info(f"Found total vacancies count: {count}")
                    return count
            
            # Also try to find in specific elements
            # Look for elements containing "Количество" and "вакансий"
            for elem in soup.find_all(string=re.compile(r"Количество.*вакансий", re.IGNORECASE)):
                text = str(elem)
                for pattern in patterns:
                    match = re.search(pattern, text, re.IGNORECASE)
                    if match:
                        count = int(match.group(1))
                        self.logger.info(f"Found total vacancies count in element: {count}")
                        return count
            
            self.logger.warning("Could not find total vacancies count on page")
            return None
            
        except Exception as e:
            self.logger.error(f"Error parsing total vacancies count: {e}", exc_info=True)
            return None

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
            Total number of pages (default: 1, but will try to parse more)
        """
        url = self.build_search_url(profession, city, company_name, page=1)
        html = await self._fetch_page(url)
        if not html:
            return 1

        try:
            soup = BeautifulSoup(html, "html.parser")
            
            # Try multiple pagination selectors
            pagination_selectors = [
                ("div", {"class": "pagination"}),
                ("nav", {"class": "pagination"}),
                ("ul", {"class": "pagination"}),
                ("div", {"class": "pager"}),
                ("nav", {"class": "pager"}),
                ("ul", {"class": "pager"}),
                ("div", {"class": "page-numbers"}),
            ]
            
            pagination = None
            for tag, attrs in pagination_selectors:
                pagination = soup.find(tag, attrs)
                if pagination:
                    break
            
            if pagination:
                page_links = pagination.find_all("a")
                max_page = 1
                for link in page_links:
                    try:
                        # Check text content
                        page_text = link.text.strip()
                        if page_text.isdigit():
                            page_num = int(page_text)
                            max_page = max(max_page, page_num)
                        
                        # Also check href for page numbers
                        href = link.get("href", "")
                        if href:
                            # Look for page= parameter
                            import re
                            match = re.search(r'[?&]page=(\d+)', href)
                            if match:
                                page_num = int(match.group(1))
                                max_page = max(max_page, page_num)
                    except (ValueError, AttributeError):
                        continue
                
                if max_page > 1:
                    self.logger.info(f"Found pagination: {max_page} pages")
                    return max_page
            
            # If no pagination found, check if there are job blocks
            # If there are many job blocks (20 per page), likely there are more pages
            job_blocks = soup.find_all("div", class_="job-block")
            if job_blocks:
                # If we have exactly 20 job blocks, there might be more pages
                # Return a reasonable default (10 pages) to try parsing
                if len(job_blocks) >= 20:
                    self.logger.info(
                        f"Found {len(job_blocks)} job blocks on first page, "
                        "assuming there might be more pages"
                    )
                    # Return a reasonable number to try (will stop when no more results)
                    return 10  # Try up to 10 pages, will stop earlier if no results
                return 1
        except Exception as e:
            self.logger.error(f"Error parsing pagination: {e}", exc_info=True)

        return 1

    async def parse_vacancy_detail(self, vacancy_url: str) -> Optional[dict]:
        """
        Parse detailed information about a specific vacancy.

        Args:
            vacancy_url: URL of the vacancy page

        Returns:
            Dictionary with detailed vacancy information or None if failed
        """
        html = await self._fetch_page(vacancy_url)
        if not html:
            return None

        try:
            soup = BeautifulSoup(html, "html.parser")
            detail_data = {"url": vacancy_url}

            # Find contact section
            contact_section = soup.find(id="contact-info-anchor")
            if contact_section:
                # Find parent container
                parent = contact_section.parent
                while parent and parent.name not in ["section", "div"]:
                    parent = parent.parent

                if parent:
                    # Extract contact phone
                    # Look for text "Контактный телефон организации" and get next sibling
                    phone_label = parent.find(string=lambda x: x and "Контактный телефон" in x)
                    if phone_label:
                        phone_parent = phone_label.find_parent(["div", "p"])
                        if phone_parent:
                            # Find next div with phone number
                            phone_elem = phone_parent.find_next_sibling("div")
                            if phone_elem:
                                phone_text = phone_elem.get_text(strip=True)
                                detail_data["contact_phone"] = self.extract_phone(phone_text) or self.normalize_text(phone_text)
                            else:
                                # Try to find in same row
                                row = phone_parent.find_parent("div", class_="row")
                                if row:
                                    phone_col = row.find("div", class_=lambda x: x and "col" in str(x))
                                    if phone_col:
                                        phone_text = phone_col.get_text(strip=True)
                                        detail_data["contact_phone"] = self.extract_phone(phone_text) or self.normalize_text(phone_text)

                    # Extract contact person (ФИО)
                    fio_label = parent.find(string=lambda x: x and ("ФИО" in x or "Контактное лицо" in x))
                    if fio_label:
                        fio_parent = fio_label.find_parent(["div", "p"])
                        if fio_parent:
                            # Find next div with FIO
                            fio_elem = fio_parent.find_next_sibling("div")
                            if fio_elem:
                                detail_data["contact_person"] = self.normalize_text(fio_elem.get_text(strip=True))
                            else:
                                # Try to find in same row
                                row = fio_parent.find_parent("div", class_="row")
                                if row:
                                    fio_col = row.find("div", class_=lambda x: x and "col" in str(x))
                                    if fio_col:
                                        detail_data["contact_person"] = self.normalize_text(fio_col.get_text(strip=True))

            return detail_data

        except Exception as e:
            self.logger.error(f"Error parsing vacancy detail {vacancy_url}: {e}", exc_info=True)
            return None

    async def _parse_vacancy_item(self, item: BeautifulSoup) -> Optional[dict]:
        """
        Parse a single vacancy item from listing page.

        Args:
            item: BeautifulSoup element containing vacancy data (div.job-block)

        Returns:
            Dictionary with vacancy data or None if parsing failed
        """
        try:
            import re
            from datetime import timedelta

            # Extract position (profession) from h4.job-title > a
            title_elem = item.find("h4", class_="job-title")
            if title_elem:
                title_link = title_elem.find("a")
                position = self.normalize_text(title_link.text if title_link else title_elem.text)
                # Extract URL
                url = None
                if title_link:
                    href = title_link.get("href")
                    if href:
                        url = urljoin(self.base_url, href)
            else:
                position = None
                url = None

            # Extract external ID from URL
            external_id = "unknown"
            if url:
                match = re.search(r"/vacancy/(\d+)/", url)
                if match:
                    external_id = match.group(1)

            # Extract company name from ul.job-info > li.org > a
            company_name = None
            org_elem = item.find("li", class_="org")
            if org_elem:
                org_link = org_elem.find("a")
                company_name = self.normalize_text(org_link.text if org_link else org_elem.text)

            # Extract salary from ul.job-info > li > span.salary
            salary = None
            salary_elem = item.find("span", class_="salary")
            if salary_elem:
                salary = self.normalize_text(salary_elem.text)

            # Extract address from ul.job-info > li > span.address
            address = None
            address_elem = item.find("span", class_="address")
            if address_elem:
                address = self.normalize_text(address_elem.text)

            # Extract vacancies count (Ставка: X)
            vacancies_count = None
            job_info = item.find("ul", class_="job-info")
            if job_info:
                # Look for text containing "Ставка:"
                for elem in job_info.find_all(["li", "span"]):
                    text = elem.get_text(strip=True)
                    if "Ставка:" in text:
                        match = re.search(r"Ставка:\s*(\d+)", text)
                        if match:
                            vacancies_count = int(match.group(1))
                        break

            # Extract date (Обновлено X часов/дней назад)
            date_posted = None
            # Look for text with "Обновлено"
            update_text_elem = item.find(string=re.compile(r"Обновлено"))
            if update_text_elem:
                parent = update_text_elem.parent
                update_text = parent.get_text(strip=True) if parent else str(update_text_elem)
                # Try to parse relative time (X часов назад, X дней назад)
                # For now, we'll set date_posted to None and handle it later
                # In production, you might want to parse relative dates properly
                match = re.search(r"(\d+)\s+(час|день|дня|дней)", update_text)
                if match:
                    # Approximate: subtract hours/days from current time
                    # This is approximate - for exact date, need to parse detail page
                    pass

            # Contact info is usually on detail page, not in listing
            contact_person = None
            contact_phone = None

            if not position or not company_name:
                self.logger.warning("Missing required fields (position or company_name)")
                return None

            vacancy_data = {
                "external_id": external_id,
                "source": self.source_name,
                "date_posted": date_posted,
                "company_name": company_name,
                "company_address": address,
                "position": position,
                "vacancies_count": vacancies_count,
                "salary": salary,
                "contact_person": contact_person,
                "contact_phone": contact_phone,
                "url": url,
            }

            # Validate with Pydantic schema
            try:
                validated = VacancySchema(**vacancy_data)
                return validated.model_dump()
            except Exception as e:
                self.logger.error(f"Validation error for vacancy: {e}, data: {vacancy_data}")
                return None

        except Exception as e:
            self.logger.error(f"Error parsing vacancy item: {e}", exc_info=True)
            return None

    async def parse_vacancies(
        self,
        profession: Optional[str] = None,
        city: Optional[str] = None,
        company_name: Optional[str] = None,
        limit: Optional[int] = None,
        fetch_details: bool = False,
        filter_by_city: bool = True,
        progress_callback: Optional[Callable[[int, int, int], Awaitable[None]]] = None,
        parse_all_pages: bool = False,
    ) -> list[dict]:
        """
        Parse vacancies from gsz.gov.by.

        Args:
            profession: Profession/specialty to search for
            city: City or region to search in
            company_name: Company name to search for
            limit: Maximum number of vacancies to return
            fetch_details: Whether to fetch detailed contact info from detail pages.
                          Default False to avoid overwhelming the server.
            filter_by_city: Whether to filter results by city
            progress_callback: Optional callback function(current_page, total_pages, found_count)
                              called after parsing each page for progress updates
            parse_all_pages: If True, parse all pages until no more results (for monitoring).
                            If False, limit to reasonable number of pages (for search).

        Returns:
            List of vacancy dictionaries
        """
        self.logger.info(
            f"Starting to parse vacancies: profession={profession}, city={city}, company={company_name}, "
            f"fetch_details={fetch_details}, filter_by_city={filter_by_city}"
        )
        
        if city and filter_by_city:
            self.logger.info(f"City filtering enabled: will filter results by '{city}'")

        vacancies = []
        detail_fetch_errors = 0
        max_detail_errors = 5  # Stop fetching details after 5 consecutive errors
        
        try:
            # Get total pages
            total_pages = await self.get_total_pages(profession, city, company_name)
            self.logger.info(f"Found {total_pages} page(s)")
            
            # Call progress callback for initial state
            if progress_callback:
                await progress_callback(0, total_pages, 0)

            # Parse each page
            # For monitoring (parse_all_pages=True): parse all pages until no more results
            # For search (parse_all_pages=False): limit to reasonable number of pages
            if parse_all_pages:
                # For monitoring: parse all pages, stop only when no more results
                max_pages_to_try = 1000  # Very high limit, will stop earlier on empty pages
                self.logger.info("Parsing all pages (monitoring mode)")
            else:
                # For search: reasonable limit based on total_pages or default
                max_pages_to_try = max(total_pages, 10) if total_pages > 0 else 10
                self.logger.info(f"Parsing up to {max_pages_to_try} pages (search mode)")
            
            consecutive_empty_pages = 0
            
            for page in range(1, max_pages_to_try + 1):
                if limit and len(vacancies) >= limit:
                    break

                url = self.build_search_url(profession, city, company_name, page)
                self.logger.debug(f"Fetching page {page}: {url}")

                html = await self._fetch_page(url)
                if not html:
                    self.logger.warning(f"Failed to fetch page {page}")
                    consecutive_empty_pages += 1
                    # Stop if 2 consecutive pages fail
                    if consecutive_empty_pages >= 2:
                        self.logger.info(f"Stopping after {consecutive_empty_pages} consecutive failed pages")
                        break
                    continue

                soup = BeautifulSoup(html, "html.parser")

                # Find vacancy items - actual structure: div.job-block
                vacancy_items = soup.find_all("div", class_="job-block")
                
                # Also try alternative selectors if job-block not found
                if len(vacancy_items) == 0:
                    # Try alternative selectors
                    alt_items = soup.find_all("div", class_="vacancy-item")
                    if not alt_items:
                        alt_items = soup.find_all("div", class_="vacancy")
                    if not alt_items:
                        alt_items = soup.find_all("article", class_="vacancy")
                    if not alt_items:
                        alt_items = soup.find_all("div", {"data-vacancy": True})
                    if alt_items:
                        vacancy_items = alt_items
                        self.logger.info(f"Found {len(vacancy_items)} items using alternative selectors")

                self.logger.info(f"Page {page}: Found {len(vacancy_items)} vacancy items")

                # If no items found, increment empty pages counter
                if len(vacancy_items) == 0:
                    consecutive_empty_pages += 1
                    # Stop if 2 consecutive pages have no results
                    if consecutive_empty_pages >= 2:
                        self.logger.info(f"Stopping after {consecutive_empty_pages} consecutive empty pages")
                        break
                else:
                    consecutive_empty_pages = 0  # Reset counter on successful page

                page_vacancies_count = 0
                for item in vacancy_items:
                    if limit and len(vacancies) >= limit:
                        break

                    vacancy = await self._parse_vacancy_item(item)
                    if vacancy:
                        # Filter by city if specified and filter_by_city is True
                        if city and filter_by_city:
                            # Check if city matches in company address
                            address = vacancy.get("company_address", "").lower()
                            city_lower = city.lower()
                            
                            # Check if city name appears in address
                            # Handle variations: "Минск", "г. Минск", "Минская область", etc.
                            city_variations = [
                                city_lower,
                                f"г. {city_lower}",
                                f"г {city_lower}",
                                f"{city_lower}ая",
                                f"{city_lower}ская",
                            ]
                            
                            # Also check common city name variations
                            city_mapping = {
                                "минск": ["минск", "г. минск", "г минск", "минская"],
                                "могилев": ["могилев", "г. могилев", "могилевская"],
                                "гомель": ["гомель", "г. гомель", "гомельская"],
                                "брест": ["брест", "г. брест", "брестская"],
                                "гродно": ["гродно", "г. гродно", "гродненская"],
                                "витебск": ["витебск", "г. витебск", "витебская"],
                            }
                            
                            if city_lower in city_mapping:
                                city_variations.extend(city_mapping[city_lower])
                            
                            # Check if any variation matches
                            # Use word boundaries to avoid partial matches
                            matches = False
                            for variation in city_variations:
                                # Check if variation appears in address (as whole word or part of word)
                                if variation in address:
                                    matches = True
                                    break
                            
                            if not matches:
                                # Skip this vacancy - doesn't match city filter
                                self.logger.debug(f"Skipping vacancy - city '{city}' not found in address '{address}'")
                                continue
                        
                        # Filter by company name if specified
                        if company_name:
                            company = vacancy.get("company_name", "").lower()
                            if company_name.lower() not in company:
                                self.logger.debug(f"Skipping vacancy - company '{company_name}' not found in '{company}'")
                                continue
                        
                        # Try to get contact info from detail page if enabled and URL is available
                        if fetch_details and vacancy.get("url") and detail_fetch_errors < max_detail_errors:
                            # Wait for rate limiter before detail request
                            await self.rate_limiter.wait()
                            # Additional delay for detail pages (they're more expensive)
                            await asyncio.sleep(1.0 + random.uniform(0, 0.5))  # 1-1.5s delay
                            
                            detail_data = await self.parse_vacancy_detail(vacancy["url"])
                            if detail_data:
                                if detail_data.get("contact_phone"):
                                    vacancy["contact_phone"] = detail_data["contact_phone"]
                                if detail_data.get("contact_person"):
                                    vacancy["contact_person"] = detail_data["contact_person"]
                                # Reset error counter on success
                                detail_fetch_errors = 0
                            else:
                                # Increment error counter if detail fetch failed
                                detail_fetch_errors += 1
                                if detail_fetch_errors >= max_detail_errors:
                                    self.logger.warning(
                                        f"Too many detail fetch errors ({detail_fetch_errors}), "
                                        "skipping detail fetching for remaining vacancies"
                                    )
                        
                        vacancies.append(vacancy)
                        page_vacancies_count += 1

                # Call progress callback after parsing page
                if progress_callback:
                    await progress_callback(page, max_pages_to_try, len(vacancies))

                # Delay between pages (longer than between individual requests)
                if page < max_pages_to_try:
                    delay = settings.parser_delay_between_pages
                    # Add random jitter (±30%)
                    jitter = delay * 0.3 * (random.random() * 2 - 1)
                    await asyncio.sleep(delay + jitter)

            self.logger.info(f"Successfully parsed {len(vacancies)} vacancies")
            return vacancies

        except Exception as e:
            self.logger.error(f"Error parsing vacancies: {e}", exc_info=True)
            raise ParserError(f"Failed to parse vacancies: {e}") from e

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
