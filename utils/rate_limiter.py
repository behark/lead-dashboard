"""
Rate limiting utilities for external API calls
"""
import time
from typing import Dict, Optional
from collections import defaultdict
from threading import Lock
from utils.logging_config import get_logger

logger = get_logger(__name__)


class RateLimiter:
    """
    Simple rate limiter for external API calls
    Thread-safe implementation
    """
    
    def __init__(self, max_calls: int, period: float):
        """
        Initialize rate limiter
        
        Args:
            max_calls: Maximum number of calls allowed
            period: Time period in seconds
        """
        self.max_calls = max_calls
        self.period = period
        self.calls: Dict[str, list] = defaultdict(list)
        self.lock = Lock()
    
    def wait_if_needed(self, key: str = 'default') -> None:
        """
        Wait if rate limit would be exceeded
        
        Args:
            key: Identifier for different rate limit buckets
        """
        with self.lock:
            now = time.time()
            calls = self.calls[key]
            
            # Remove old calls outside the period
            calls[:] = [call_time for call_time in calls if now - call_time < self.period]
            
            # If at limit, wait until oldest call expires
            if len(calls) >= self.max_calls:
                oldest_call = min(calls)
                wait_time = self.period - (now - oldest_call) + 0.1  # Small buffer
                if wait_time > 0:
                    logger.debug(f"Rate limit reached for {key}, waiting {wait_time:.2f}s")
                    time.sleep(wait_time)
                    # Clean up again after waiting
                    now = time.time()
                    calls[:] = [call_time for call_time in calls if now - call_time < self.period]
            
            # Record this call
            calls.append(time.time())
    
    def can_proceed(self, key: str = 'default') -> bool:
        """
        Check if a call can proceed without waiting
        
        Args:
            key: Identifier for different rate limit buckets
        
        Returns:
            True if call can proceed, False if would exceed limit
        """
        with self.lock:
            now = time.time()
            calls = self.calls[key]
            
            # Remove old calls
            calls[:] = [call_time for call_time in calls if now - call_time < self.period]
            
            return len(calls) < self.max_calls


# Google Places API rate limiter
# Free tier: 100 requests per 100 seconds
# Paid tier: 1000 requests per 100 seconds
GOOGLE_PLACES_LIMITER = RateLimiter(max_calls=90, period=100.0)  # Conservative limit

# Telegram API rate limiter
# 30 messages per second
TELEGRAM_LIMITER = RateLimiter(max_calls=25, period=1.0)  # Conservative limit
