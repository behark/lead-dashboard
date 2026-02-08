from flask import Flask, request
from flask_login import LoginManager
from flask_apscheduler import APScheduler
from flask_wtf.csrf import CSRFProtect
from flask_migrate import Migrate
from config import config
from models import db, User
# Import SaaS models to ensure they're registered
import models_saas
import os

login_manager = LoginManager()
scheduler = APScheduler()
csrf = CSRFProtect()
migrate = Migrate()

# Initialize Sentry for error tracking (optional, only if DSN is set)
try:
    import sentry_sdk
    from sentry_sdk.integrations.flask import FlaskIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
    
    sentry_dsn = os.environ.get('SENTRY_DSN')
    if sentry_dsn:
        sentry_sdk.init(
            dsn=sentry_dsn,
            integrations=[
                FlaskIntegration(),
                SqlalchemyIntegration()
            ],
            traces_sample_rate=0.1,  # 10% of transactions for performance monitoring
            environment=os.environ.get('FLASK_ENV', 'development'),
            # Only send errors in production
            before_send=lambda event, hint: event if os.environ.get('FLASK_ENV') == 'production' else None
        )
        print("✅ Sentry error tracking initialized")
    else:
        print("ℹ️  Sentry DSN not set - error tracking disabled")
except ImportError:
    print("ℹ️  Sentry SDK not installed - error tracking disabled")
except Exception as e:
    print(f"⚠️  Error initializing Sentry: {e}")


def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    # Setup logging (must be early)
    from utils.logging_config import setup_logging
    log_level = os.getenv('LOG_LEVEL', 'INFO' if not app.config.get('DEBUG', False) else 'DEBUG')
    setup_logging(app, log_level=log_level)
    
    # Add template global for safe URL building
    @app.template_global()
    def safe_url_for(endpoint, default='#', **values):
        """Safely build URL, returning default if endpoint doesn't exist"""
        try:
            from flask import url_for
            return url_for(endpoint, **values)
        except Exception:
            return default
    
    # Validate environment variables
    from utils.env_validator import validate_on_startup
    validate_on_startup(app)
    
    # Initialize Redis/job queue (optional, graceful fallback if not available)
    from utils.job_queue import init_redis
    init_redis()
    
    # Initialize request logging middleware
    from utils.request_logger import RequestLogger
    RequestLogger.init_app(app)
    
    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'info'
    
    # Initialize CSRF protection
    csrf.init_app(app)
    
    # Exempt webhook endpoints from CSRF (they use signature verification instead)
    # Note: Webhooks are exempted after blueprints are registered
    
    # Initialize database migrations
    migrate.init_app(app, db)
    
    # Initialize caching
    from utils.cache import init_cache
    init_cache(app)
    
    # Initialize rate limiting (only if enabled)
    if app.config.get('RATELIMIT_ENABLED', True):
        from flask_limiter import Limiter
        from flask_limiter.util import get_remote_address
        
        def get_user_id():
            """Get user ID for per-user rate limiting"""
            try:
                from flask_login import current_user
                if current_user.is_authenticated:
                    return f"user:{current_user.id}"
                return get_remote_address()
            except Exception:
                return get_remote_address()
        
        redis_url = app.config.get('REDIS_URL')
        if redis_url:
            # Use Redis for production
            limiter = Limiter(
                app=app,
                key_func=get_user_id,  # Per-user rate limiting
                default_limits=["200 per day", "50 per hour"],
                storage_uri=redis_url,
                headers_enabled=True
            )
        else:
            # Use in-memory for development (with warning suppression)
            import warnings
            warnings.filterwarnings('ignore', message='.*in-memory storage.*')
            limiter = Limiter(
                app=app,
                key_func=get_user_id,  # Per-user rate limiting
                default_limits=["200 per day", "50 per hour"],
                headers_enabled=True
            )
        
        # Apply stricter limits to API endpoints
        @app.before_request
        def apply_api_rate_limits():
            if request.path.startswith('/api/'):
                # API endpoints: 100 requests per hour per user
                try:
                    limiter.limit("100 per hour", key_func=get_user_id)(lambda: None)()
                except Exception as e:
                    app.logger.warning(f"Rate limiting failed: {e}")
    else:
        # Rate limiting disabled
        limiter = None
    
    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))
    
    # Register blueprints
    from routes.auth import auth_bp
    from routes.main import main_bp
    from routes.analytics import analytics_bp
    from routes.templates_routes import templates_bp
    from routes.webhooks import webhooks_bp
    from routes.bulk import bulk_bp
    from routes.api_templates import api_templates_bp
    from routes.billing import billing_bp
    from routes.usage import usage_bp
    from routes.team import team_bp
    from routes.gdpr import gdpr_bp
    from routes.landing import landing_bp
    from routes.backup import backup_bp
    from routes.demo_analytics_api import demo_analytics_bp
    from routes.business_dashboard import business_dashboard_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(templates_bp)
    app.register_blueprint(webhooks_bp)
    app.register_blueprint(bulk_bp)
    app.register_blueprint(api_templates_bp)
    app.register_blueprint(billing_bp)
    app.register_blueprint(usage_bp)
    app.register_blueprint(team_bp)
    app.register_blueprint(gdpr_bp)
    app.register_blueprint(landing_bp)
    app.register_blueprint(backup_bp)
    app.register_blueprint(demo_analytics_bp)
    app.register_blueprint(business_dashboard_bp)
    
    # Exempt webhook endpoints from CSRF (they use signature verification instead)
    csrf.exempt(webhooks_bp)
    
    # Portfolio page (public, no login required)
    @app.route('/portfolio')
    def portfolio():
        return app.send_static_file('../templates/portfolio.html')
    
    # Health check endpoint (public, no login required)
    @app.route('/health')
    def health():
        """Health check endpoint for monitoring and load balancers"""
        from sqlalchemy import text
        from datetime import datetime, timezone
        from flask import jsonify
        
        try:
            # Check database connectivity
            db.session.execute(text('SELECT 1'))
            db_status = 'connected'
        except Exception as e:
            db_status = f'error: {str(e)}'
        
        health_status = {
            'status': 'healthy' if db_status == 'connected' else 'unhealthy',
            'database': db_status,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'version': '2.1'
        }
        
        status_code = 200 if db_status == 'connected' else 503
        return jsonify(health_status), status_code
    
    # Register error handlers
    from utils.error_handlers import register_error_handlers
    register_error_handlers(app)
    
    # Create database tables
    with app.app_context():
        db.create_all()
    
    # Setup scheduled tasks (skip if already running - e.g., during migration)
    if app.config.get('SCHEDULER_API_ENABLED') and not scheduler.running:
        scheduler.init_app(app)
        
        # Setup logging for scheduled tasks
        import logging
        task_logger = logging.getLogger('scheduled_tasks')
        
        @scheduler.task('cron', id='process_sequences', hour='9,14,18')
        def process_sequences():
            """Process due sequence steps"""
            try:
                with app.app_context():
                    from services.sequence_service import SequenceService
                    result = SequenceService.process_due_sequences()
                    task_logger.info(f"Processed sequences: {result}")
            except Exception as e:
                task_logger.exception(f"Error processing sequences: {e}")
        
        @scheduler.task('cron', id='decay_temperatures', hour='2')
        def decay_temperatures():
            """Apply temperature decay to leads"""
            try:
                with app.app_context():
                    from services.scoring_service import ScoringService
                    result = ScoringService.apply_temperature_decay()
                    task_logger.info(f"Applied temperature decay: {result}")
            except Exception as e:
                task_logger.exception(f"Error applying temperature decay: {e}")
        
        @scheduler.task('cron', id='record_daily_analytics', hour='23', minute='55')
        def record_analytics():
            """Record daily analytics summary"""
            try:
                with app.app_context():
                    from services.analytics_service import AnalyticsService
                    result = AnalyticsService.record_daily_analytics()
                    task_logger.info(f"Recorded daily analytics: {result}")
            except Exception as e:
                task_logger.exception(f"Error recording daily analytics: {e}")
        
        @scheduler.task('cron', id='daily_backup', hour='2', minute='0')
        def daily_backup():
            """Create daily database backup"""
            try:
                with app.app_context():
                    from utils.backup import BackupService
                    result = BackupService.create_backup()
                    if result.get('success'):
                        task_logger.info(f"Daily backup created: {result.get('backup_path')}")
                        # Cleanup old backups (keep 30 days)
                        cleanup_result = BackupService.cleanup_old_backups(keep_days=30)
                        task_logger.info(f"Cleaned up {cleanup_result.get('deleted_count', 0)} old backups")
                    else:
                        task_logger.error(f"Backup failed: {result.get('error')}")
            except Exception as e:
                task_logger.exception(f"Error creating daily backup: {e}")
        
        scheduler.start()
        app.logger.info("Scheduled tasks initialized and started")
    
    return app


# CLI commands for database management
def register_cli(app):
    import click
    
    @app.cli.command('init-db')
    def init_db():
        """Initialize the database."""
        db.create_all()
        click.echo('Database initialized.')
    
    @app.cli.command('migrate-csv')
    @click.argument('csv_path')
    def migrate_csv(csv_path):
        """Migrate leads from CSV to database."""
        from migrate_data import migrate_from_csv
        count = migrate_from_csv(csv_path)
        click.echo(f'Migrated {count} leads.')
    
    @app.cli.command('create-admin')
    @click.argument('username')
    @click.argument('email')
    @click.argument('password')
    def create_admin(username, email, password):
        """Create an admin user."""
        from models import User, UserRole
        
        user = User(username=username, email=email, role=UserRole.ADMIN)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f'Admin user {username} created.')
    
    @app.cli.command('recalculate-scores')
    def recalculate_scores():
        """Recalculate all lead scores."""
        from services.scoring_service import ScoringService
        count = ScoringService.recalculate_all_scores()
        click.echo(f'Recalculated scores for {count} leads.')

    @app.cli.command('update-analytics')
    def update_analytics():
        """Update analytics with enhanced metrics."""
        from services.analytics_service import AnalyticsService
        AnalyticsService.update_daily_analytics()
        click.echo('Analytics updated with conversion funnel and compliance metrics.')
    
    @app.cli.command('create-default-templates')
    def create_default_templates():
        """Create default message templates."""
        from models import MessageTemplate, ContactChannel
        
        templates = [
            # Professional Initial Contact Templates
            {
                'name': 'Initial WhatsApp - Professional Introduction',
                'channel': ContactChannel.WHATSAPP,
                'language': 'sq',
                'content': '''Përshëndetje {business_name}! 👋

Jam nga Web Solutions Albania dhe e pashë biznesin tuaj në Google Maps - vlerësimi juaj {rating}⭐ tregon që ofroni shërbim të shkëlqyer!

Kam vënë re që nuk keni ende një faqe interneti. Shumë klientë potencialë ju kërkojnë online para se të ju kontaktojnë.

Ne ofrojmë:
✅ Faqe profesionale me dizajn modern
✅ Optimizim për Google (SEO)
✅ Përshtatje për celular
✅ Garanci 30-ditore

A do të donit të shihni disa shembuj të punëve tona? Jam i disponueshëm për një bisedë të shkurtër.

Me respekt,
Web Solutions Albania''',
                'variant': 'A',
                'is_default': True
            },
            {
                'name': 'Initial WhatsApp - Value Focused',
                'channel': ContactChannel.WHATSAPP,
                'language': 'sq',
                'content': '''Përshëndetje {business_name}! 🙌

E vura re biznesin tuaj në {city} dhe më pëlqeu shumë shërbimi që ofroni.

Sot, mbi 80% e klientëve kërkojnë online para se të zgjedhin një biznes. Pa një faqe interneti, mund të humbisni klientë të rinj.

Ne kemi ndihmuar mbi 50 biznese si juaji të rrisin klientët e tyre nëpërmjet faqeve profesionale.

Do të doja të ju ofroja një konsultim FALAS 15-minutësh për të diskutuar se si mund t'ju ndihmojmë.

A keni kohë këtë javë?

Me respekt,
Web Solutions Albania''',
                'variant': 'B',
                'is_default': False
            },
            # Follow-up Templates
            {
                'name': 'Follow-up Day 2 - Gentle Reminder',
                'channel': ContactChannel.WHATSAPP,
                'language': 'sq',
                'content': '''Përshëndetje përsëri {business_name}! 👋

Vetëm po ju dërgoj një mesazh të shkurtër për t'ju kujtuar ofertën tonë për faqe interneti.

Kuptoj që jeni të zënë me biznesin tuaj - por një investim i vogël në prezencën online mund të sjellë rezultate të mëdha.

A do të donit të caktojmë një telefonatë 10-minutëshe kur t'ju përshtatet?

Me respekt''',
                'variant': 'A',
                'is_default': False
            },
            {
                'name': 'Follow-up Day 5 - Case Study',
                'channel': ContactChannel.WHATSAPP,
                'language': 'sq',
                'content': '''Përshëndetje {business_name}!

Doja të ndaja një histori suksesi: Një biznes si juaji në {city} mori faqe interneti muajin e kaluar dhe tani merr 5+ klientë të rinj në javë vetëm nga kërkimet në Google.

Nëse jeni ende të interesuar, jam gati t'ju tregoj se si mund të arrini të njëjtat rezultate.

Shkruani "PO" dhe do t'ju dërgoj informacion të detajuar.

Faleminderit!''',
                'variant': 'B',
                'is_default': False
            },
            # Email Templates
            {
                'name': 'Initial Email - Professional',
                'channel': ContactChannel.EMAIL,
                'language': 'sq',
                'subject': 'Ofertë Ekskluzive për {business_name} - Faqe Interneti Profesionale',
                'content': '''Përshëndetje,

Po ju kontaktoj nga Web Solutions Albania.

E pashë biznesin tuaj {business_name} në Google Maps dhe u impresionova nga vlerësimi juaj i lartë. Kjo tregon që ofroni shërbim cilësor!

Kam vënë re që ende nuk keni një faqe interneti. Në ditët e sotme, mbi 80% e klientëve kërkojnë online para se të marrin vendim. Pa prezencë online, mund të humbisni mundësi të rëndësishme.

**Çfarë ofrojmë:**
• Faqe profesionale me dizajn modern
• Optimizim për motorët e kërkimit (SEO)
• Përshtatje për pajisje mobile
• Formular kontakti për klientë të rinj
• Hosting dhe mirëmbajtje për 1 vit
• Garanci 30-ditore kthimi të parave

**Çmimet tona fillojnë nga 299€** për paketën bazike.

A do të donit të caktojmë një telefonatë 15-minutëshe për të diskutuar nevojat tuaja? Jam i disponueshëm çdo ditë nga e hëna deri të premten.

Me respekt,
Web Solutions Albania
📞 +355 XX XXX XXXX
🌐 www.websolutions.al''',
                'variant': 'A',
                'is_default': True
            },
            # English Templates
            {
                'name': 'Initial WhatsApp - English Professional',
                'channel': ContactChannel.WHATSAPP,
                'language': 'en',
                'content': '''Hello {business_name}! 👋

I'm reaching out from Web Solutions. I came across your business on Google Maps and noticed your excellent {rating}⭐ rating!

I see that you don't have a website yet. In today's digital world, over 80% of customers search online before choosing a business.

We specialize in creating professional, mobile-friendly websites that help businesses like yours attract more customers.

**What we offer:**
✅ Modern, professional design
✅ Google optimization (SEO)
✅ Mobile-responsive layout
✅ Contact forms & booking
✅ 30-day money-back guarantee

Would you be interested in a FREE 15-minute consultation to discuss how we can help your business grow?

Best regards,
Web Solutions Team''',
                'variant': 'A',
                'is_default': False
            }
        ]
        
        for t in templates:
            if not MessageTemplate.query.filter_by(name=t['name']).first():
                template = MessageTemplate(**t)
                db.session.add(template)
        
        db.session.commit()
        click.echo('Default templates created.')


app = create_app()
register_cli(app)

if __name__ == '__main__':
    import os
    app = create_app()
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)
