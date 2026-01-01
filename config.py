import os
from datetime import timedelta

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    # SECRET_KEY validation - fail fast in production if not set
    _secret_key = os.environ.get('SECRET_KEY')
    if not _secret_key:
        if os.environ.get('FLASK_ENV') == 'production':
            raise ValueError("SECRET_KEY must be set in production environment")
        # Generate random key for development
        import secrets
        _secret_key = secrets.token_hex(32)
        import warnings
        warnings.warn("Using auto-generated SECRET_KEY for development. Set SECRET_KEY in production!")
    
    SECRET_KEY = _secret_key
    
    # Database
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'leads.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Session
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    
    # Pagination
    LEADS_PER_PAGE = 50
    
    # WhatsApp Business API (Meta)
    WHATSAPP_API_URL = os.environ.get('WHATSAPP_API_URL', 'https://graph.facebook.com/v18.0')
    WHATSAPP_PHONE_ID = os.environ.get('WHATSAPP_PHONE_ID', '')
    WHATSAPP_ACCESS_TOKEN = os.environ.get('WHATSAPP_ACCESS_TOKEN', '')
    WHATSAPP_WEBHOOK_TOKEN = os.environ.get('WHATSAPP_WEBHOOK_TOKEN', '')
    
    # Email (SMTP)
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', '')
    
    # SMS (Twilio)
    TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID', '')
    TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN', '')
    TWILIO_PHONE_NUMBER = os.environ.get('TWILIO_PHONE_NUMBER', '')
    TWILIO_WHATSAPP_NUMBER = os.environ.get('TWILIO_WHATSAPP_NUMBER', '+14155238886')
    
    # Scheduler
    SCHEDULER_API_ENABLED = True
    SCHEDULER_TIMEZONE = 'Europe/Tirane'
    
    # Lead scoring
    SCORE_DECAY_DAYS = 7  # Start decaying score after 7 days
    FOLLOWUP_DEFAULT_DAYS = 3


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
    
    # Security
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Stripe
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY')
    STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY')
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')
    STRIPE_PRICE_ID_STARTER_MONTHLY = os.environ.get('STRIPE_PRICE_ID_STARTER_MONTHLY')
    STRIPE_PRICE_ID_STARTER_YEARLY = os.environ.get('STRIPE_PRICE_ID_STARTER_YEARLY')
    STRIPE_PRICE_ID_PROFESSIONAL_MONTHLY = os.environ.get('STRIPE_PRICE_ID_PROFESSIONAL_MONTHLY')
    STRIPE_PRICE_ID_PROFESSIONAL_YEARLY = os.environ.get('STRIPE_PRICE_ID_PROFESSIONAL_YEARLY')
    STRIPE_PRICE_ID_ENTERPRISE_MONTHLY = os.environ.get('STRIPE_PRICE_ID_ENTERPRISE_MONTHLY')
    STRIPE_PRICE_ID_ENTERPRISE_YEARLY = os.environ.get('STRIPE_PRICE_ID_ENTERPRISE_YEARLY')
    
    # Base URL
    BASE_URL = os.environ.get('BASE_URL', 'http://localhost:5000')
    
    # Redis
    REDIS_URL = os.environ.get('REDIS_URL')
    
    # Rate Limiting
    RATELIMIT_ENABLED = os.environ.get('RATELIMIT_ENABLED', 'True') == 'True'


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
