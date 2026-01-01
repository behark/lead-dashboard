"""
Caching utilities using Flask-Caching
"""
from typing import Optional, Callable, Any
from functools import wraps
from flask import current_app
from flask_caching import Cache
import hashlib
import json


# Cache instance (will be initialized in app.py)
cache: Optional[Cache] = None


def init_cache(app) -> Cache:
    """
    Initialize cache for the Flask app
    
    Args:
        app: Flask application instance
    
    Returns:
        Cache instance
    """
    global cache
    
    cache_config = {
        'CACHE_TYPE': 'simple',  # Simple in-memory cache
        'CACHE_DEFAULT_TIMEOUT': 300,  # 5 minutes default
    }
    
    # Use Redis if available
    if app.config.get('REDIS_URL'):
        cache_config.update({
            'CACHE_TYPE': 'redis',
            'CACHE_REDIS_URL': app.config['REDIS_URL'],
        })
    
    cache = Cache(app, config=cache_config)
    return cache


def cache_key(*args, **kwargs) -> str:
    """
    Generate a cache key from arguments
    
    Args:
        *args: Positional arguments
        **kwargs: Keyword arguments
    
    Returns:
        Cache key string
    """
    key_data = {
        'args': args,
        'kwargs': sorted(kwargs.items())
    }
    key_str = json.dumps(key_data, sort_keys=True, default=str)
    return hashlib.md5(key_str.encode()).hexdigest()


def cached(timeout: int = 300, key_prefix: str = None):
    """
    Decorator to cache function results
    
    Args:
        timeout: Cache timeout in seconds
        key_prefix: Optional prefix for cache key
    
    Usage:
        @cached(timeout=600)
        def expensive_function(arg1, arg2):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            if cache is None:
                return func(*args, **kwargs)
            
            # Generate cache key
            if key_prefix:
                key = f"{key_prefix}:{cache_key(*args, **kwargs)}"
            else:
                key = f"{func.__module__}.{func.__name__}:{cache_key(*args, **kwargs)}"
            
            # Try to get from cache
            result = cache.get(key)
            if result is not None:
                return result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cache.set(key, result, timeout=timeout)
            return result
        
        return wrapper
    return decorator


def clear_cache_pattern(pattern: str) -> int:
    """
    Clear cache entries matching a pattern
    
    Args:
        pattern: Pattern to match (e.g., 'analytics:*')
    
    Returns:
        Number of keys cleared
    """
    if cache is None:
        return 0
    
    # Simple cache doesn't support pattern matching
    # For Redis, we'd use cache.cache._read_clients[0].keys(pattern)
    # For now, just clear all
    cache.clear()
    return 0
