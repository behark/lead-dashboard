"""
Security utilities for the Lead Dashboard application.
Provides security-related functions and decorators.
"""
import hashlib
import hmac
import secrets
import re
from functools import wraps
from flask import request, abort, current_app, session
from flask_login import current_user
import logging

logger = logging.getLogger(__name__)


# Security constants
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 30
SESSION_TIMEOUT_MINUTES = 60
PASSWORD_MIN_LENGTH = 8


def generate_secure_token(length: int = 32) -> str:
    """Generate a cryptographically secure random token"""
    return secrets.token_urlsafe(length)


def hash_token(token: str) -> str:
    """Hash a token for secure storage"""
    return hashlib.sha256(token.encode()).hexdigest()


def verify_token_hash(token: str, token_hash: str) -> bool:
    """Verify a token against its hash"""
    return hmac.compare_digest(hash_token(token), token_hash)


def sanitize_redirect_url(url: str, default: str = '/') -> str:
    """Sanitize redirect URL to prevent open redirect vulnerabilities"""
    if not url:
        return default
    
    # Only allow relative URLs or same-origin URLs
    if url.startswith('/') and not url.startswith('//'):
        return url
    
    # Check if URL is for the same origin
    from urllib.parse import urlparse
    parsed = urlparse(url)
    if parsed.netloc == '':
        return url
    
    # For absolute URLs, verify they're for the same host
    server_name = current_app.config.get('SERVER_NAME', '')
    if server_name and parsed.netloc == server_name:
        return url
    
    return default


def require_role(*roles):
    """Decorator to require specific user roles"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            
            # Check if user has any of the required roles
            user_role = getattr(current_user, 'role', None)
            if user_role is None:
                abort(403)
            
            # Handle both enum and string roles
            user_role_value = user_role.value if hasattr(user_role, 'value') else str(user_role)
            role_values = [r.value if hasattr(r, 'value') else str(r) for r in roles]
            
            if user_role_value not in role_values:
                logger.warning(f"User {current_user.id} attempted to access {f.__name__} without required role")
                abort(403)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def require_admin(f):
    """Decorator to require admin role"""
    from models import UserRole
    return require_role(UserRole.ADMIN)(f)


def require_manager_or_admin(f):
    """Decorator to require manager or admin role"""
    from models import UserRole
    return require_role(UserRole.ADMIN, UserRole.MANAGER)(f)


def rate_limit_check(key: str, max_requests: int, window_seconds: int) -> bool:
    """Simple in-memory rate limiting check (use Redis in production)"""
    from datetime import datetime, timezone
    
    # Use session-based rate limiting for simplicity
    rate_key = f'rate_limit_{key}'
    now = datetime.now(timezone.utc).timestamp()
    
    if rate_key not in session:
        session[rate_key] = {'requests': [], 'window_start': now}
    
    rate_data = session[rate_key]
    
    # Clean old requests outside window
    window_start = now - window_seconds
    rate_data['requests'] = [r for r in rate_data['requests'] if r > window_start]
    
    # Check if limit exceeded
    if len(rate_data['requests']) >= max_requests:
        return False
    
    # Add current request
    rate_data['requests'].append(now)
    session[rate_key] = rate_data
    session.modified = True
    
    return True


def verify_webhook_signature(payload: bytes, signature: str, secret: str, algorithm: str = 'sha256') -> bool:
    """Verify webhook signature for external services"""
    if not signature or not secret:
        return False
    
    try:
        expected = hmac.new(
            secret.encode(),
            payload,
            getattr(hashlib, algorithm)
        ).hexdigest()
        
        # Handle various signature formats
        if '=' in signature:
            signature = signature.split('=')[-1]
        
        return hmac.compare_digest(expected, signature)
    except Exception as e:
        logger.exception(f"Error verifying webhook signature: {e}")
        return False


def validate_password_strength(password: str) -> tuple[bool, list[str]]:
    """Validate password meets security requirements"""
    errors = []
    
    if len(password) < PASSWORD_MIN_LENGTH:
        errors.append(f"Password must be at least {PASSWORD_MIN_LENGTH} characters")
    
    if not re.search(r'[A-Z]', password):
        errors.append("Password must contain at least one uppercase letter")
    
    if not re.search(r'[a-z]', password):
        errors.append("Password must contain at least one lowercase letter")
    
    if not re.search(r'\d', password):
        errors.append("Password must contain at least one digit")
    
    # Check for common passwords
    common_passwords = ['password', '123456', 'qwerty', 'admin', 'letmein']
    if password.lower() in common_passwords:
        errors.append("Password is too common")
    
    return len(errors) == 0, errors


def check_account_lockout(user) -> tuple[bool, str]:
    """Check if user account is locked"""
    from datetime import datetime, timezone
    
    if not user:
        return False, ""
    
    if user.locked_until and user.locked_until > datetime.now(timezone.utc):
        remaining = (user.locked_until - datetime.now(timezone.utc)).total_seconds() / 60
        return True, f"Account locked. Try again in {int(remaining)} minutes."
    
    return False, ""


def record_failed_login(user):
    """Record failed login attempt and lock account if necessary"""
    from datetime import datetime, timezone, timedelta
    from models import db
    
    if not user:
        return
    
    user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
    
    if user.failed_login_attempts >= MAX_LOGIN_ATTEMPTS:
        user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
        logger.warning(f"Account {user.username} locked due to {user.failed_login_attempts} failed attempts")
    
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()


def reset_failed_login_attempts(user):
    """Reset failed login attempts after successful login"""
    from models import db
    
    if not user:
        return
    
    user.failed_login_attempts = 0
    user.locked_until = None
    
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()


class CSRFProtection:
    """CSRF protection utilities"""
    
    @staticmethod
    def generate_token() -> str:
        """Generate CSRF token"""
        if 'csrf_token' not in session:
            session['csrf_token'] = generate_secure_token()
        return session['csrf_token']
    
    @staticmethod
    def validate_token(token: str) -> bool:
        """Validate CSRF token"""
        session_token = session.get('csrf_token')
        if not session_token or not token:
            return False
        return hmac.compare_digest(session_token, token)
    
    @staticmethod
    def protect(f):
        """Decorator to require valid CSRF token for POST requests"""
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if request.method in ['POST', 'PUT', 'DELETE', 'PATCH']:
                token = request.form.get('csrf_token') or request.headers.get('X-CSRF-Token')
                if not CSRFProtection.validate_token(token):
                    logger.warning(f"CSRF validation failed for {request.path}")
                    abort(403)
            return f(*args, **kwargs)
        return decorated_function
