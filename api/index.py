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
    from routes.bulk import bulk_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(templates_bp)
    app.register_blueprint(bulk_bp)
    
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
            'name': 'Initial WhatsApp - Albanian',
            'channel': ContactChannel.WHATSAPP,
            'language': 'sq',
            'content': 'Pershendetje 👋\n\nPashe {business_name} ne Google - shkelqyeshem!\n\nKeni uebsajt? Kam nje ide si mund te sillni me shume kliente.\n\n2 min bisede?',
            'variant': 'A'
        },
        {
            'name': 'Follow-up Day 1',
            'channel': ContactChannel.WHATSAPP,
            'language': 'sq', 
            'content': 'Pershendetje 👋\n\nPo ndjek mesazhin tim per {business_name}.\n\nPa presion - thjesht doja te shoh nese jeni te interesuar?\n\nGjithe te mirat!',
            'variant': 'A'
        }
    ]
    
    for t in templates:
        template = MessageTemplate(**t)
        db.session.add(template)
    
    db.session.commit()


app = create_app()
