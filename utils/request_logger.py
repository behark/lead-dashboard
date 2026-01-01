"""
Request Logging Middleware
Logs all HTTP requests with details for monitoring and debugging
"""
from flask import request, g, current_app
from datetime import datetime, timezone
import logging
import time
import json

logger = logging.getLogger(__name__)


class RequestLogger:
    """Middleware for logging HTTP requests"""
    
    @staticmethod
    def init_app(app):
        """Initialize request logging for the app"""
        
        @app.before_request
        def before_request():
            """Log request start"""
            g.start_time = time.time()
            g.request_id = f"{datetime.now(timezone.utc).timestamp()}-{id(request)}"
            
            # Skip logging for static files and health checks
            if request.path.startswith('/static/') or request.path == '/health':
                return
            
            # Log request details
            log_data = {
                'request_id': g.request_id,
                'method': request.method,
                'path': request.path,
                'remote_addr': request.remote_addr,
                'user_agent': request.headers.get('User-Agent', '')[:200],  # Limit length
                'referrer': request.referrer,
                'timestamp': datetime.now(timezone.utc).isoformat(),
            }
            
            # Add user info if authenticated
            try:
                from flask_login import current_user
                if current_user.is_authenticated:
                    log_data['user_id'] = current_user.id
                    log_data['username'] = current_user.username
            except Exception:
                pass
            
            # Add query parameters (limit sensitive data)
            if request.args:
                safe_params = {}
                for key, value in request.args.items():
                    # Don't log sensitive parameters
                    if key.lower() not in ['password', 'token', 'secret', 'key', 'api_key']:
                        safe_params[key] = str(value)[:100]  # Limit length
                if safe_params:
                    log_data['query_params'] = safe_params
            
            logger.info(f"Request started: {request.method} {request.path}", extra=log_data)
        
        @app.after_request
        def after_request(response):
            """Log request completion"""
            # Skip logging for static files and health checks
            if request.path.startswith('/static/') or request.path == '/health':
                return response
            
            # Calculate duration
            duration = None
            if hasattr(g, 'start_time'):
                duration = (time.time() - g.start_time) * 1000  # Convert to milliseconds
            
            # Log response details
            log_data = {
                'request_id': getattr(g, 'request_id', 'unknown'),
                'method': request.method,
                'path': request.path,
                'status_code': response.status_code,
                'duration_ms': round(duration, 2) if duration else None,
                'timestamp': datetime.now(timezone.utc).isoformat(),
            }
            
            # Add user info if authenticated
            try:
                from flask_login import current_user
                if current_user.is_authenticated:
                    log_data['user_id'] = current_user.id
                    log_data['username'] = current_user.username
            except Exception:
                pass
            
            # Log slow requests as warnings
            if duration and duration > 1000:  # > 1 second
                logger.warning(f"Slow request: {request.method} {request.path} took {duration:.0f}ms", extra=log_data)
            elif response.status_code >= 400:
                # Log errors
                logger.warning(f"Request error: {request.method} {request.path} returned {response.status_code}", extra=log_data)
            else:
                logger.info(f"Request completed: {request.method} {request.path} {response.status_code}", extra=log_data)
            
            # Add request ID to response headers (for tracing)
            response.headers['X-Request-ID'] = getattr(g, 'request_id', 'unknown')
            
            return response
        
        @app.errorhandler(Exception)
        def handle_exception(e):
            """Log unhandled exceptions"""
            log_data = {
                'request_id': getattr(g, 'request_id', 'unknown'),
                'method': request.method,
                'path': request.path,
                'error': str(e),
                'error_type': type(e).__name__,
                'timestamp': datetime.now(timezone.utc).isoformat(),
            }
            
            # Add user info if authenticated
            try:
                from flask_login import current_user
                if current_user.is_authenticated:
                    log_data['user_id'] = current_user.id
                    log_data['username'] = current_user.username
            except Exception:
                pass
            
            logger.exception(f"Unhandled exception: {request.method} {request.path}", extra=log_data)
            
            # Re-raise to let Flask handle it
            raise
