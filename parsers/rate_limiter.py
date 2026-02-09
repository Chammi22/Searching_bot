"""Rate limiter for parser requests to avoid IP bans."""

import asyncio
import random
from datetime import datetime, timedelta
from typing import Optional

from config.logging_config import get_logger

logger = get_logger(__name__)


class RateLimiter:
    """Rate limiter to control request frequency."""

    def __init__(
        self,
        min_delay: float = 2.0,
        max_delay: float = 5.0,
        jitter: bool = True,
    ) -> None:
        """
        Initialize rate limiter.

        Args:
            min_delay: Minimum delay between requests in seconds
            max_delay: Maximum delay between requests in seconds
            jitter: Add random jitter to delays to make them less predictable
        """
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.jitter = jitter
        self.last_request_time: Optional[datetime] = None
        self._lock = asyncio.Lock()

    async def wait(self) -> None:
        """Wait before making next request."""
        async with self._lock:
            if self.last_request_time is not None:
                elapsed = (datetime.now() - self.last_request_time).total_seconds()
                
                # Calculate delay
                delay = self.min_delay
                if self.max_delay > self.min_delay:
                    delay = random.uniform(self.min_delay, self.max_delay)
                
                # Add jitter (±20% random variation)
                if self.jitter:
                    jitter_amount = delay * 0.2 * (random.random() * 2 - 1)  # -20% to +20%
                    delay += jitter_amount
                
                # Wait if needed
                if elapsed < delay:
                    wait_time = delay - elapsed
                    logger.debug(f"Rate limiter: waiting {wait_time:.2f}s before next request")
                    await asyncio.sleep(wait_time)
            
            self.last_request_time = datetime.now()


class UserAgentRotator:
    """Rotate User-Agent strings to appear more like different browsers."""

    USER_AGENTS = [
        # Chrome on Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        # Chrome on macOS
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        # Firefox on Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        # Firefox on macOS
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
        # Safari on macOS
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
        # Edge on Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    ]

    def __init__(self) -> None:
        """Initialize User-Agent rotator."""
        self.current_index = 0

    def get(self) -> str:
        """Get next User-Agent string."""
        ua = self.USER_AGENTS[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.USER_AGENTS)
        return ua

    def get_random(self) -> str:
        """Get random User-Agent string."""
        return random.choice(self.USER_AGENTS)


class RequestThrottler:
    """Throttle requests to avoid overwhelming the server."""

    def __init__(
        self,
        requests_per_minute: int = 20,
        requests_per_hour: int = 500,
    ) -> None:
        """
        Initialize request throttler.

        Args:
            requests_per_minute: Max requests per minute
            requests_per_hour: Max requests per hour
        """
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.request_times: list[datetime] = []
        self._lock = asyncio.Lock()

    async def can_make_request(self) -> bool:
        """Check if we can make a request without exceeding limits."""
        async with self._lock:
            now = datetime.now()
            
            # Remove old requests (older than 1 hour)
            self.request_times = [
                req_time
                for req_time in self.request_times
                if (now - req_time).total_seconds() < 3600
            ]
            
            # Check hourly limit
            if len(self.request_times) >= self.requests_per_hour:
                logger.warning(
                    f"Hourly request limit reached ({self.requests_per_hour}). "
                    "Waiting before next request."
                )
                return False
            
            # Check per-minute limit
            recent_requests = [
                req_time
                for req_time in self.request_times
                if (now - req_time).total_seconds() < 60
            ]
            
            if len(recent_requests) >= self.requests_per_minute:
                logger.debug(
                    f"Per-minute limit reached ({self.requests_per_minute}). "
                    "Waiting before next request."
                )
                return False
            
            return True

    async def record_request(self) -> None:
        """Record that a request was made."""
        async with self._lock:
            self.request_times.append(datetime.now())
