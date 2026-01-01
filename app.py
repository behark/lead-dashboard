from flask import Flask
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
                per_method=True,
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
                per_method=True,
                headers_enabled=True
            )
        
        # Apply stricter limits to API endpoints
        @app.before_request
        def apply_api_rate_limits():
            if request.path.startswith('/api/'):
                # API endpoints: 100 requests per hour per user
                try:
                    limiter.limit("100 per hour", key_func=get_user_id)(lambda: None)()
                except Exception:
                    pass  # Ignore if limiter not available
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
            {
                'name': 'Initial WhatsApp - Urgency Focus',
                'channel': ContactChannel.WHATSAPP,
                'language': 'sq',
                'content': '''Pershendetje {business_name}! 👋

Shoh që nuk keni uebsajt dhe humbisni klientë çdo ditë.

Kam një ofertë speciale sot: uebsajt profesional për vetëm 299€ (zakonisht 499€).

Interesuar për një takim 10-minutësh? Mund të fillojmë nesër!

Shiko shembujt këtu: [link]''',
                'variant': 'A'
            },
            {
                'name': 'Initial WhatsApp - Social Proof',
                'channel': ContactChannel.WHATSAPP,
                'language': 'sq',
                'content': '''Pershendetje {business_name}! 🙌

3 biznese si juaji javën e kaluar morën uebsajt dhe thanë: "Pse nuk e bëra më herët?"

Klientët ju gjejnë në Google, ju kontaktojnë 24/7, dhe ju merrni më shumë thirrje.

Çmimi: 299€ për paketën bazike.

Doni të shihni se si duket për biznesin tuaj?''',
                'variant': 'B'
            },
            {
                'name': 'Follow-up Day 1 - Value Reminder',
                'channel': ContactChannel.WHATSAPP,
                'language': 'sq',
                'content': '''Përshëndetje {business_name}! 👋

Vetëm po ju kujtoj për uebsajtin - klientët tuaj po kërkojnë në Google por nuk ju gjejnë.

Oferta ime: uebsajt i gatshëm brenda 5 ditëve, me optimizim për Google.

A keni 5 minuta për të folur sot?

[Link për shembuj]''',
                'variant': 'A'
            },
            {
                'name': 'Follow-up Day 3 - Scarcity',
                'channel': ContactChannel.WHATSAPP,
                'language': 'sq',
                'content': '''Përshëndetje {business_name}!

Oferta ime speciale mbaron sot - uebsajt për 299€ (nga 499€).

Kam vetëm 2 vende të lira këtë javë për projekte të reja.

Interesuar? Mund të fillojmë menjëherë me logon dhe fotot tuaja.

Shkruani "PO" nëse doni të vazhdojmë! ✅''',
                'variant': 'B'
            },
            {
                'name': 'Initial Email - Albanian',
                'channel': ContactChannel.EMAIL,
                'language': 'sq',
                'subject': 'Oferte per {business_name}',
                'content': '''Pershendetje,

Pashe biznesin tuaj {business_name} ne Google Maps dhe me pelqeu shume!

Kam vene re qe nuk keni uebsajt. Deshironi te diskutojme se si nje uebsajt profesional mund te sillni me shume kliente?

Ofrojme:
- Dizajn modern dhe profesional
- Optimizim per Google (SEO)
- Forma kontakti per kliente te rinj
- Garanci 30 ditesh

A mund te caktojme nje telefonat te shkurter?

Me respekt''',
                'variant': 'A'
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
