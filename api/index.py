import sys
import os

# Add parent directory to path for imports
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

from flask import Flask
from flask_login import LoginManager
from config import config
from models import db, User, Lead, LeadStatus, LeadTemperature, MessageTemplate, ContactChannel

login_manager = LoginManager()

def create_app():
    app = Flask(__name__, 
                template_folder=os.path.join(parent_dir, 'templates'),
                static_folder=os.path.join(parent_dir, 'static'))
    
    app.config.from_object(config['production'])
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'  # In-memory for serverless
    app.config['SCHEDULER_API_ENABLED'] = False
    app.config['DEBUG'] = False
    
    # Disable features that don't work well in serverless
    app.config['CACHE_TYPE'] = 'null'  # Disable caching in serverless
    
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'info'
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Try to setup logging (gracefully fail if utils not available)
    # In serverless, only use console logging (no file handlers)
    try:
        from utils.logging_config import setup_logging
        setup_logging(app, log_level='INFO')
    except (ImportError, OSError, PermissionError) as e:
        # Fallback: basic logging if utils not available or file system is read-only
        import logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[logging.StreamHandler(sys.stdout)]  # Only console, no file
        )
        app.logger = logging.getLogger(__name__)
    
    # Skip cache and rate limiter in serverless (not needed)
    # These features require persistent storage which serverless doesn't provide
    
    # Register blueprints
    from routes.auth import auth_bp
    from routes.main import main_bp
    from routes.analytics import analytics_bp
    from routes.templates_routes import templates_bp
    from routes.bulk import bulk_bp
    from routes.api_templates import api_templates_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(templates_bp)
    app.register_blueprint(bulk_bp)
    app.register_blueprint(api_templates_bp)
    
    @app.route('/portfolio')
    def portfolio():
        from flask import render_template
        return render_template('portfolio.html')
    
    # Create tables and seed demo data
    with app.app_context():
        db.create_all()
        seed_demo_data()
    
    return app


def seed_demo_data():
    """Seed demo data for Vercel deployment"""
    from models import UserRole
    from datetime import datetime, timezone
    import json
    
    # Check if already seeded
    if User.query.first():
        return
    
    # Create demo user
    demo_user = User(
        username='demo',
        email='demo@example.com',
        role=UserRole.ADMIN
    )
    demo_user.set_password('demo123')
    db.session.add(demo_user)
    
    # Try to load leads from export file
    json_path = os.path.join(parent_dir, 'leads_data.json')
    leads_to_insert = []
    
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                print(f"Loading {len(data)} leads from {json_path}")
                
                for item in data:
                    # Parse Enums
                    status = getattr(LeadStatus, item.get('status', 'NEW'), LeadStatus.NEW)
                    temperature = getattr(LeadTemperature, item.get('temperature', 'WARM'), LeadTemperature.WARM)
                    
                    # Parse Dates
                    created_at = None
                    if item.get('created_at'):
                        try:
                            # Handle string format from export
                            created_at = datetime.fromisoformat(item['created_at'])
                        except ValueError:
                            created_at = datetime.now(timezone.utc)
                    else:
                        created_at = datetime.now(timezone.utc)
                    
                    # Create Lead object
                    lead = Lead(
                        name=item.get('name', ''),
                        phone=item.get('phone', ''),
                        email=item.get('email', ''),
                        city=item.get('city', ''),
                        address=item.get('address', ''),
                        country=item.get('country', 'Kosovo'),
                        language=item.get('language', 'sq'),
                        category=item.get('category', ''),
                        rating=item.get('rating'),
                        maps_url=item.get('maps_url', ''),
                        website=item.get('website', ''),
                        whatsapp_link=item.get('whatsapp_link', ''),
                        first_message=item.get('first_message', ''),
                        lead_score=item.get('lead_score', 50),
                        temperature=temperature,
                        suggested_price=item.get('suggested_price', ''),
                        status=status,
                        notes=item.get('notes', ''),
                        created_at=created_at,
                        has_website=bool(item.get('has_website', False))
                    )
                    leads_to_insert.append(lead)
        except Exception as e:
            print(f"Error loading leads.json: {e}")
    
    # Fallback to demo leads if no file or error
    if not leads_to_insert:
        print("Using fallback demo leads")
        demo_leads_data = [
            {'name': 'Lux Barbershop', 'phone': '044 406 405', 'city': 'Pristina', 'category': 'barber', 'rating': 4.9, 'lead_score': 90, 'temperature': LeadTemperature.HOT},
            {'name': 'Culture Barbershop', 'phone': '044 384 499', 'city': 'Pristina', 'category': 'barber', 'rating': 5.0, 'lead_score': 95, 'temperature': LeadTemperature.HOT},
            {'name': 'Smile Dental', 'phone': '044 123 456', 'city': 'Pristina', 'category': 'dentist', 'rating': 4.8, 'lead_score': 85, 'temperature': LeadTemperature.HOT},
            {'name': 'Pizza Roma', 'phone': '049 111 222', 'city': 'Pristina', 'category': 'restaurant', 'rating': 4.5, 'lead_score': 70, 'temperature': LeadTemperature.WARM},
            {'name': 'Bella Salon', 'phone': '045 333 444', 'city': 'Pristina', 'category': 'salon', 'rating': 4.7, 'lead_score': 75, 'temperature': LeadTemperature.WARM},
            {'name': 'Auto Fix', 'phone': '048 555 666', 'city': 'Pristina', 'category': 'car repair', 'rating': 4.3, 'lead_score': 60, 'temperature': LeadTemperature.WARM},
            {'name': 'Fitness Pro Gym', 'phone': '043 777 888', 'city': 'Pristina', 'category': 'gym', 'rating': 4.6, 'lead_score': 65, 'temperature': LeadTemperature.WARM},
            {'name': 'Legal Partners', 'phone': '044 999 000', 'city': 'Pristina', 'category': 'lawyer', 'rating': 4.4, 'lead_score': 55, 'temperature': LeadTemperature.COLD},
        ]
        
        for lead_data in demo_leads_data:
            lead = Lead(
                name=lead_data['name'],
                phone=lead_data['phone'],
                city=lead_data['city'],
                country='Kosovo',
                category=lead_data['category'],
                rating=lead_data['rating'],
                lead_score=lead_data['lead_score'],
                temperature=lead_data['temperature'],
                status=LeadStatus.NEW,
                created_at=datetime.now(timezone.utc)
            )
            leads_to_insert.append(lead)
            
    # Batch insert
    for lead in leads_to_insert:
        db.session.add(lead)
    
    # Create demo templates
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
        }
    ]
    
    for t in templates:
        template = MessageTemplate(**t)
        db.session.add(template)
    
    db.session.commit()


# Create the Flask app
app = create_app()

# Export for Vercel serverless function
# Vercel expects either 'app' or 'application' to be the WSGI application
application = app  # Alias for compatibility
