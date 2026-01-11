"""
Centralized error handling utilities for the Lead Dashboard application.
Provides consistent error responses and logging across the application.
"""
from flask import jsonify, render_template, request, current_app
from functools import wraps
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
import logging

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Base application error"""
    def __init__(self, message: str, status_code: int = 400, payload: dict = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.payload = payload or {}


class NotFoundError(AppError):
    """Resource not found error"""
    def __init__(self, resource: str = "Resource"):
        super().__init__(f"{resource} not found", status_code=404)


class UnauthorizedError(AppError):
    """Unauthorized access error"""
    def __init__(self, message: str = "Unauthorized access"):
        super().__init__(message, status_code=403)


class ValidationError(AppError):
    """Validation error"""
    def __init__(self, message: str, field: str = None):
        payload = {'field': field} if field else {}
        super().__init__(message, status_code=400, payload=payload)


class RateLimitError(AppError):
    """Rate limit exceeded error"""
    def __init__(self, message: str = "Rate limit exceeded. Please try again later."):
        super().__init__(message, status_code=429)


def handle_api_error(f):
    """Decorator for API routes that provides consistent error handling"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except AppError as e:
            logger.warning(f"Application error in {f.__name__}: {e.message}")
            response = {'success': False, 'error': e.message}
            response.update(e.payload)
            return jsonify(response), e.status_code
        except IntegrityError as e:
            logger.error(f"Database integrity error in {f.__name__}: {e}")
            from models import db
            db.session.rollback()
            return jsonify({
                'success': False,
                'error': 'A database constraint was violated. This may be a duplicate entry.'
            }), 409
        except SQLAlchemyError as e:
            logger.exception(f"Database error in {f.__name__}: {e}")
            from models import db
            db.session.rollback()
            return jsonify({
                'success': False,
                'error': 'A database error occurred. Please try again.'
            }), 500
        except Exception as e:
            logger.exception(f"Unexpected error in {f.__name__}: {e}")
            return jsonify({
                'success': False,
                'error': 'An unexpected error occurred. Please try again.'
            }), 500
    return decorated_function


def handle_web_error(redirect_url: str = None):
    """Decorator for web routes that provides consistent error handling with flash messages"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except AppError as e:
                logger.warning(f"Application error in {f.__name__}: {e.message}")
                from flask import flash, redirect, url_for
                flash(e.message, 'danger')
                return redirect(redirect_url or url_for('main.index'))
            except SQLAlchemyError as e:
                logger.exception(f"Database error in {f.__name__}: {e}")
                from flask import flash, redirect, url_for
                from models import db
                db.session.rollback()
                flash('A database error occurred. Please try again.', 'danger')
                return redirect(redirect_url or url_for('main.index'))
            except Exception as e:
                logger.exception(f"Unexpected error in {f.__name__}: {e}")
                from flask import flash, redirect, url_for
                flash('An unexpected error occurred. Please try again.', 'danger')
                return redirect(redirect_url or url_for('main.index'))
        return decorated_function
    return decorator


def register_error_handlers(app):
    """Register global error handlers for the Flask application"""
    
    @app.errorhandler(400)
    def bad_request(error):
        if request.is_json or request.path.startswith('/api/'):
            return jsonify({'success': False, 'error': 'Bad request'}), 400
        return render_template('errors/400.html'), 400
    
    @app.errorhandler(401)
    def unauthorized(error):
        if request.is_json or request.path.startswith('/api/'):
            return jsonify({'success': False, 'error': 'Unauthorized'}), 401
        from flask import redirect, url_for
        return redirect(url_for('auth.login'))
    
    @app.errorhandler(403)
    def forbidden(error):
        if request.is_json or request.path.startswith('/api/'):
            return jsonify({'success': False, 'error': 'Forbidden'}), 403
        return render_template('errors/403.html'), 403
    
    @app.errorhandler(404)
    def not_found(error):
        if request.is_json or request.path.startswith('/api/'):
            return jsonify({'success': False, 'error': 'Resource not found'}), 404
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(429)
    def rate_limit_exceeded(error):
        if request.is_json or request.path.startswith('/api/'):
            return jsonify({'success': False, 'error': 'Rate limit exceeded'}), 429
        from flask import flash, redirect, url_for
        flash('Too many requests. Please wait before trying again.', 'warning')
        return redirect(url_for('main.index'))
    
    @app.errorhandler(500)
    def internal_error(error):
        logger.exception(f"Internal server error: {error}")
        from models import db
        db.session.rollback()
        if request.is_json or request.path.startswith('/api/'):
            return jsonify({'success': False, 'error': 'Internal server error'}), 500
        return render_template('errors/500.html'), 500
    
    @app.errorhandler(AppError)
    def handle_app_error(error):
        if request.is_json or request.path.startswith('/api/'):
            response = {'success': False, 'error': error.message}
            response.update(error.payload)
            return jsonify(response), error.status_code
        from flask import flash, redirect, url_for
        flash(error.message, 'danger')
        return redirect(url_for('main.index'))
