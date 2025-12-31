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
    app.run(debug=True, port=5000)
