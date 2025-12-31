from flask import Flask
from flask_login import LoginManager
from flask_apscheduler import APScheduler
from config import config
from models import db, User

login_manager = LoginManager()
scheduler = APScheduler()


def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'info'
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Register blueprints
    from routes.auth import auth_bp
    from routes.main import main_bp
    from routes.analytics import analytics_bp
    from routes.templates_routes import templates_bp
    from routes.webhooks import webhooks_bp
    from routes.bulk import bulk_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(templates_bp)
    app.register_blueprint(webhooks_bp)
    app.register_blueprint(bulk_bp)
    
    # Portfolio page (public, no login required)
    @app.route('/portfolio')
    def portfolio():
        return app.send_static_file('../templates/portfolio.html')
    
    # Create database tables
    with app.app_context():
        db.create_all()
    
    # Setup scheduled tasks (skip if already running - e.g., during migration)
    if app.config.get('SCHEDULER_API_ENABLED') and not scheduler.running:
        scheduler.init_app(app)
        
        @scheduler.task('cron', id='process_sequences', hour='9,14,18')
        def process_sequences():
            with app.app_context():
                from services.sequence_service import SequenceService
                SequenceService.process_due_sequences()
        
        @scheduler.task('cron', id='decay_temperatures', hour='2')
        def decay_temperatures():
            with app.app_context():
                from services.scoring_service import ScoringService
                ScoringService.apply_temperature_decay()
        
        @scheduler.task('cron', id='record_daily_analytics', hour='23', minute='55')
        def record_analytics():
            with app.app_context():
                from services.analytics_service import AnalyticsService
                AnalyticsService.record_daily_analytics()
        
        scheduler.start()
    
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
    
    @app.cli.command('create-default-templates')
    def create_default_templates():
        """Create default message templates."""
        from models import MessageTemplate, ContactChannel
        
        templates = [
            {
                'name': 'Initial WhatsApp - Albanian',
                'channel': ContactChannel.WHATSAPP,
                'language': 'sq',
                'content': '''Pershendetje 👋

Pashe *{business_name}* ne Google - vleresim te shkelqyer!

Keni uebsajt? Kam nje ide si mund te sillni me shume kliente.

2 min bisede?''',
                'variant': 'A'
            },
            {
                'name': 'Initial WhatsApp - Albanian B',
                'channel': ContactChannel.WHATSAPP,
                'language': 'sq',
                'content': '''Pershendetje {business_name}! 👋

Jam duke kerkuar biznese ne {city} dhe ju dallet.

A keni interes per nje uebsajt profesional qe sjell kliente te rinj?

Mund te flasim per 2 min?''',
                'variant': 'B'
            },
            {
                'name': 'Follow-up WhatsApp',
                'channel': ContactChannel.WHATSAPP,
                'language': 'sq',
                'content': '''Pershendetje perseri! 👋

Ju kontaktova disa dite me pare per uebsajtin.

Ende i interesuar? Kam nje oferte speciale kete jave.''',
                'variant': 'A'
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
    app.run(debug=True, port=5000)
