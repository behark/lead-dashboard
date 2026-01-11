"""
General helper utilities for the Lead Dashboard application.
Common functions used across the application.
"""
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Union
import re
import json
import logging

logger = logging.getLogger(__name__)


def format_datetime(dt: datetime, fmt: str = '%Y-%m-%d %H:%M') -> str:
    """Format datetime for display"""
    if not dt:
        return ''
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime(fmt)


def format_datetime_relative(dt: datetime) -> str:
    """Format datetime as relative time (e.g., '2 hours ago')"""
    if not dt:
        return ''
    
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    now = datetime.now(timezone.utc)
    diff = now - dt
    
    seconds = diff.total_seconds()
    
    if seconds < 60:
        return 'just now'
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f'{minutes} minute{"s" if minutes != 1 else ""} ago'
    elif seconds < 86400:
        hours = int(seconds / 3600)
        return f'{hours} hour{"s" if hours != 1 else ""} ago'
    elif seconds < 604800:
        days = int(seconds / 86400)
        return f'{days} day{"s" if days != 1 else ""} ago'
    else:
        return dt.strftime('%b %d, %Y')


def format_number(num: Union[int, float], decimals: int = 0) -> str:
    """Format number with thousands separator"""
    if num is None:
        return '0'
    if decimals > 0:
        return f'{num:,.{decimals}f}'
    return f'{int(num):,}'


def format_percentage(value: float, decimals: int = 1) -> str:
    """Format value as percentage"""
    if value is None:
        return '0%'
    return f'{value:.{decimals}f}%'


def format_currency(amount: float, currency: str = 'EUR', decimals: int = 2) -> str:
    """Format amount as currency"""
    if amount is None:
        amount = 0
    
    symbols = {
        'EUR': '€',
        'USD': '$',
        'GBP': '£',
        'ALL': 'L'
    }
    symbol = symbols.get(currency, currency)
    return f'{symbol}{amount:,.{decimals}f}'


def truncate_string(text: str, max_length: int, suffix: str = '...') -> str:
    """Truncate string to max length with suffix"""
    if not text:
        return ''
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def slugify(text: str) -> str:
    """Convert text to URL-safe slug"""
    if not text:
        return ''
    # Convert to lowercase
    text = text.lower()
    # Replace spaces with hyphens
    text = re.sub(r'\s+', '-', text)
    # Remove non-alphanumeric characters except hyphens
    text = re.sub(r'[^a-z0-9-]', '', text)
    # Remove multiple consecutive hyphens
    text = re.sub(r'-+', '-', text)
    # Remove leading/trailing hyphens
    text = text.strip('-')
    return text


def parse_bool(value: Any) -> bool:
    """Parse various boolean representations"""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ('true', '1', 'yes', 'on')
    return bool(value)


def safe_json_loads(json_str: str, default: Any = None) -> Any:
    """Safely parse JSON string"""
    if not json_str:
        return default
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return default


def safe_json_dumps(obj: Any, default: str = '{}') -> str:
    """Safely serialize object to JSON"""
    try:
        return json.dumps(obj, default=str)
    except (TypeError, ValueError):
        return default


def get_client_ip(request) -> str:
    """Get client IP address from request, handling proxies"""
    # Check for forwarded headers (reverse proxy)
    forwarded = request.headers.get('X-Forwarded-For')
    if forwarded:
        return forwarded.split(',')[0].strip()
    
    real_ip = request.headers.get('X-Real-IP')
    if real_ip:
        return real_ip
    
    return request.remote_addr or 'unknown'


def mask_sensitive_data(data: str, visible_chars: int = 4) -> str:
    """Mask sensitive data, showing only last few characters"""
    if not data:
        return ''
    if len(data) <= visible_chars:
        return '*' * len(data)
    return '*' * (len(data) - visible_chars) + data[-visible_chars:]


def mask_email(email: str) -> str:
    """Mask email address for privacy"""
    if not email or '@' not in email:
        return email
    
    local, domain = email.split('@', 1)
    if len(local) <= 2:
        masked_local = '*' * len(local)
    else:
        masked_local = local[0] + '*' * (len(local) - 2) + local[-1]
    
    return f'{masked_local}@{domain}'


def mask_phone(phone: str) -> str:
    """Mask phone number for privacy"""
    if not phone:
        return ''
    
    digits = re.sub(r'\D', '', phone)
    if len(digits) <= 4:
        return '*' * len(digits)
    
    return '*' * (len(digits) - 4) + digits[-4:]


def calculate_percentage_change(old_value: float, new_value: float) -> float:
    """Calculate percentage change between two values"""
    if old_value == 0:
        return 100.0 if new_value > 0 else 0.0
    return ((new_value - old_value) / abs(old_value)) * 100


def chunk_list(lst: List, chunk_size: int) -> List[List]:
    """Split list into chunks of specified size"""
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


def deep_merge(base: Dict, override: Dict) -> Dict:
    """Deep merge two dictionaries"""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def get_enum_choices(enum_class) -> List[tuple]:
    """Get choices list from enum for forms"""
    return [(e.value, e.name.replace('_', ' ').title()) for e in enum_class]


def retry_on_exception(max_retries: int = 3, delay: float = 1.0, exceptions: tuple = (Exception,)):
    """Decorator to retry function on exception"""
    import time
    from functools import wraps
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        time.sleep(delay * (attempt + 1))
                        logger.warning(f"Retry {attempt + 1}/{max_retries} for {func.__name__}: {e}")
            raise last_exception
        return wrapper
    return decorator


class Timer:
    """Context manager for timing code blocks"""
    
    def __init__(self, name: str = 'Operation'):
        self.name = name
        self.start_time = None
        self.end_time = None
    
    def __enter__(self):
        self.start_time = datetime.now(timezone.utc)
        return self
    
    def __exit__(self, *args):
        self.end_time = datetime.now(timezone.utc)
        duration = (self.end_time - self.start_time).total_seconds()
        logger.debug(f"{self.name} completed in {duration:.3f}s")
    
    @property
    def elapsed(self) -> float:
        if self.start_time is None:
            return 0
        end = self.end_time or datetime.now(timezone.utc)
        return (end - self.start_time).total_seconds()
