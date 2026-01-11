"""
Input validation utilities for the Lead Dashboard application.
Provides consistent validation across routes and services.
"""
import re
from typing import Optional, Tuple, List, Any
from functools import wraps
from flask import request, jsonify, flash, redirect, url_for


# Validation patterns
EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
PHONE_PATTERN = re.compile(r'^[\d\s\-\+\(\)]{7,20}$')
USERNAME_PATTERN = re.compile(r'^[a-zA-Z0-9_]{3,80}$')
SAFE_STRING_PATTERN = re.compile(r'^[a-zA-Z0-9\s\-_.,!?@#$%&*()\'\"]+$')


class ValidationError(Exception):
    """Custom exception for validation errors"""
    def __init__(self, message: str, field: str = None):
        self.message = message
        self.field = field
        super().__init__(self.message)


def validate_email(email: str) -> Tuple[bool, Optional[str]]:
    """Validate email format"""
    if not email:
        return False, "Email is required"
    if len(email) > 254:
        return False, "Email must be 254 characters or less"
    if not EMAIL_PATTERN.match(email):
        return False, "Invalid email format"
    return True, None


def validate_phone(phone: str) -> Tuple[bool, Optional[str]]:
    """Validate phone number format"""
    if not phone:
        return True, None  # Phone is optional
    if len(phone) > 50:
        return False, "Phone number must be 50 characters or less"
    # Remove common formatting characters for validation
    cleaned = re.sub(r'[\s\-\(\)]', '', phone)
    if not cleaned.replace('+', '').isdigit():
        return False, "Phone number contains invalid characters"
    if len(cleaned) < 7 or len(cleaned) > 20:
        return False, "Phone number must be between 7 and 20 digits"
    return True, None


def validate_username(username: str) -> Tuple[bool, Optional[str]]:
    """Validate username format"""
    if not username:
        return False, "Username is required"
    if len(username) < 3:
        return False, "Username must be at least 3 characters"
    if len(username) > 80:
        return False, "Username must be 80 characters or less"
    if not USERNAME_PATTERN.match(username):
        return False, "Username can only contain letters, numbers, and underscores"
    return True, None


def validate_password(password: str, min_length: int = 8) -> Tuple[bool, Optional[str]]:
    """Validate password strength"""
    if not password:
        return False, "Password is required"
    if len(password) < min_length:
        return False, f"Password must be at least {min_length} characters"
    if len(password) > 128:
        return False, "Password must be 128 characters or less"
    
    # Check for at least one uppercase, lowercase, and digit
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    
    if not (has_upper and has_lower and has_digit):
        return False, "Password must contain at least one uppercase letter, one lowercase letter, and one digit"
    
    return True, None


def validate_string_length(value: str, field_name: str, max_length: int, min_length: int = 0, required: bool = False) -> Tuple[bool, Optional[str]]:
    """Validate string length"""
    if not value:
        if required:
            return False, f"{field_name} is required"
        return True, None
    
    if len(value) < min_length:
        return False, f"{field_name} must be at least {min_length} characters"
    if len(value) > max_length:
        return False, f"{field_name} must be {max_length} characters or less"
    
    return True, None


def validate_integer(value: Any, field_name: str, min_val: int = None, max_val: int = None) -> Tuple[bool, Optional[str], Optional[int]]:
    """Validate and convert integer value"""
    if value is None or value == '':
        return True, None, None
    
    try:
        int_val = int(value)
    except (ValueError, TypeError):
        return False, f"{field_name} must be a valid integer", None
    
    if min_val is not None and int_val < min_val:
        return False, f"{field_name} must be at least {min_val}", None
    if max_val is not None and int_val > max_val:
        return False, f"{field_name} must be at most {max_val}", None
    
    return True, None, int_val


def validate_enum(value: str, enum_class, field_name: str) -> Tuple[bool, Optional[str], Any]:
    """Validate enum value"""
    if not value:
        return True, None, None
    
    try:
        enum_val = enum_class(value)
        return True, None, enum_val
    except (ValueError, KeyError):
        valid_values = [e.value for e in enum_class]
        return False, f"Invalid {field_name}. Must be one of: {', '.join(valid_values)}", None


def sanitize_string(value: str, max_length: int = 1000) -> str:
    """Sanitize string input by stripping and truncating"""
    if not value:
        return ''
    return str(value).strip()[:max_length]


def sanitize_html(value: str) -> str:
    """Remove potentially dangerous HTML/script content"""
    if not value:
        return ''
    
    # Remove script tags and their content
    value = re.sub(r'<script[^>]*>.*?</script>', '', value, flags=re.IGNORECASE | re.DOTALL)
    # Remove on* event handlers
    value = re.sub(r'\s+on\w+\s*=\s*["\'][^"\']*["\']', '', value, flags=re.IGNORECASE)
    # Remove javascript: URLs
    value = re.sub(r'javascript:', '', value, flags=re.IGNORECASE)
    
    return value


def validate_lead_data(data: dict) -> Tuple[bool, List[str]]:
    """Validate lead creation/update data"""
    errors = []
    
    # Name validation
    name = data.get('name', '')
    if not name:
        errors.append("Business name is required")
    elif len(name) > 200:
        errors.append("Business name must be 200 characters or less")
    
    # Phone validation
    phone = data.get('phone', '')
    if phone:
        valid, error = validate_phone(phone)
        if not valid:
            errors.append(error)
    
    # Email validation
    email = data.get('email', '')
    if email:
        valid, error = validate_email(email)
        if not valid:
            errors.append(error)
    
    # Notes validation
    notes = data.get('notes', '')
    if notes and len(notes) > 10000:
        errors.append("Notes must be 10000 characters or less")
    
    # City validation
    city = data.get('city', '')
    if city and len(city) > 100:
        errors.append("City must be 100 characters or less")
    
    # Country validation
    country = data.get('country', '')
    if country and len(country) > 100:
        errors.append("Country must be 100 characters or less")
    
    # Category validation
    category = data.get('category', '')
    if category and len(category) > 100:
        errors.append("Category must be 100 characters or less")
    
    return len(errors) == 0, errors


def require_json(f):
    """Decorator to require JSON content type for API endpoints"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not request.is_json:
            return jsonify({'success': False, 'error': 'Content-Type must be application/json'}), 400
        return f(*args, **kwargs)
    return decorated_function


def validate_request_json(*required_fields):
    """Decorator to validate required fields in JSON request"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            data = request.get_json()
            if not data:
                return jsonify({'success': False, 'error': 'No JSON data provided'}), 400
            
            missing = [field for field in required_fields if field not in data or data[field] is None]
            if missing:
                return jsonify({
                    'success': False, 
                    'error': f'Missing required fields: {", ".join(missing)}'
                }), 400
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator
