"""
Environment variable validation
"""
import os
from typing import List, Dict, Optional, Any
from flask import current_app


class EnvVarError(Exception):
    """Raised when a required environment variable is missing"""
    pass


class EnvValidator:
    """Validates environment variables on application startup"""
    
    @staticmethod
    def validate_required(vars_dict: Dict[str, Optional[str]]) -> Dict[str, str]:
        """
        Validate that required environment variables are set
        
        Args:
            vars_dict: Dictionary mapping env var names to their descriptions
        
        Returns:
            Dictionary of validated environment variables
        
        Raises:
            EnvVarError: If any required variable is missing
        """
        missing = []
        validated = {}
        
        for var_name, description in vars_dict.items():
            value = os.getenv(var_name)
            if not value:
                missing.append(f"{var_name} ({description})")
            else:
                validated[var_name] = value
        
        if missing:
            error_msg = "Missing required environment variables:\n" + "\n".join(f"  - {m}" for m in missing)
            raise EnvVarError(error_msg)
        
        return validated
    
    @staticmethod
    def validate_optional(vars_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate optional environment variables with defaults
        
        Args:
            vars_dict: Dictionary mapping env var names to default values
        
        Returns:
            Dictionary of environment variables with defaults applied
        """
        validated = {}
        
        for var_name, default in vars_dict.items():
            value = os.getenv(var_name, default)
            validated[var_name] = value
        
        return validated
    
    @staticmethod
    def validate_config(config_class) -> List[str]:
        """
        Validate Flask app configuration
        
        Args:
            config_class: Configuration class to validate
        
        Returns:
            List of warnings (missing optional configs)
        """
        warnings = []
        
        # Check for critical configs
        if not hasattr(config_class, 'SECRET_KEY') or not config_class.SECRET_KEY:
            warnings.append("SECRET_KEY is not set - using default (not secure for production)")
        
        if hasattr(config_class, 'DEBUG') and config_class.DEBUG and os.getenv('FLASK_ENV') == 'production':
            warnings.append("DEBUG is True in production environment - security risk!")
        
        # Check database
        db_uri = getattr(config_class, 'SQLALCHEMY_DATABASE_URI', '')
        if 'sqlite' in db_uri.lower() and os.getenv('FLASK_ENV') == 'production':
            warnings.append("SQLite database in production - consider PostgreSQL for scale")
        
        return warnings


def validate_on_startup(app) -> None:
    """
    Validate environment variables when app starts
    
    Args:
        app: Flask application instance
    """
    from utils.logging_config import get_logger
    
    logger = get_logger(__name__)
    
    # Required variables (empty dict means none required for now)
    # Add variables here as needed
    required_vars = {}
    
    # Optional variables with defaults
    optional_vars = {
        'SECRET_KEY': None,
        'DATABASE_URL': None,
        'FLASK_ENV': 'development',
    }
    
    try:
        # Validate required
        if required_vars:
            EnvValidator.validate_required(required_vars)
            logger.info("All required environment variables are set")
        
        # Validate optional
        EnvValidator.validate_optional(optional_vars)
        
        # Validate config
        warnings = EnvValidator.validate_config(app.config)
        for warning in warnings:
            logger.warning(warning)
        
        logger.info("Environment validation complete")
        
    except EnvVarError as e:
        logger.error(str(e))
        raise
    except Exception as e:
        logger.error(f"Error validating environment: {e}")
        # Don't raise in development, but log it
        if not app.config.get('DEBUG', False):
            raise
