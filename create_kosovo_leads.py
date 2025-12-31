"""
Create realistic sample leads based on Kosovo business data
"""
from models import db, Lead, LeadStatus, LeadTemperature
from app import create_app
import random

def create_realistic_leads():
    app = create_app()
    with app.app_context():
        # Kosovo business data - realistic sample
        kosovo_businesses = [
            # Dental offices
            {'name': 'Stomatologjia Dent-Art', 'city': 'Prishtina', 'category': 'dentist', 'rating': 4.7},
            {'name': 'Dental Center Genti', 'city': 'Prizren', 'category': 'dentist', 'rating': 4.3},
            {'name': 'Smile Studio', 'city': 'Gjakova', 'category': 'dentist', 'rating': 4.5},
            {'name': 'Oral Health Clinic', 'city': 'Peja', 'category': 'dentist', 'rating': 4.1},
            {'name': 'Family Dental Care', 'city': 'Mitrovica', 'category': 'dentist', 'rating': 4.6},
            {'name': 'Dentist Plus', 'city': 'Ferizaj', 'category': 'dentist', 'rating': 4.4},
            {'name': 'Dentistry Modern', 'city': 'Suva Reka', 'category': 'dentist', 'rating': 4.8},
            {'name': 'Euro Dental', 'city': 'Vushtrri', 'category': 'dentist', 'rating': 4.2},
            
            # Salons
            {'name': 'Salon Lira', 'city': 'Prishtina', 'category': 'salon', 'rating': 4.9},
            {'name': 'Beauty Studio', 'city': 'Prishtina', 'category': 'salon', 'rating': 4.5},
            {'name': 'Hair Design', 'city': 'Prizren', 'category': 'salon', 'rating': 4.3},
            {'name': 'Fashion Cuts', 'city': 'Gjakova', 'category': 'salon', 'rating': 4.6},
            {'name': 'Style Master', 'city': 'Peja', 'category': 'salon', 'rating': 4.7},
            {'name': 'Glamour Salon', 'city': 'Mitrovica', 'category': 'salon', 'rating': 4.4},
            {'name': 'Elite Cuts', 'city': 'Ferizaj', 'category': 'salon', 'rating': 4.8},
            {'name': 'Trendy Styles', 'city': 'Suva Reka', 'category': 'salon', 'rating': 4.5},
            {'name': 'Hair Pro', 'city': 'Vushtrri', 'category': 'salon', 'rating': 4.6},
            
            # Restaurants
            {'name': 'Restaurant Artisan', 'city': 'Prishtina', 'category': 'restaurant', 'rating': 4.4},
            {'name': 'Taverna Tradicionale', 'city': 'Prishtina', 'category': 'restaurant', 'rating': 4.2},
            {'name': 'Pizza House', 'city': 'Prizren', 'category': 'restaurant', 'rating': 4.5},
            {'name': 'Balkan Bites', 'city': 'Gjakova', 'category': 'restaurant', 'rating': 4.3},
            {'name': 'Grill Master', 'city': 'Peja', 'category': 'restaurant', 'rating': 4.6},
            {'name': 'Food Paradise', 'city': 'Mitrovica', 'category': 'restaurant', 'rating': 4.1},
            {'name': 'Kuzhina moderne', 'city': 'Ferizaj', 'category': 'restaurant', 'rating': 4.4},
            {'name': 'Restorant Pika', 'city': 'Suva Reka', 'category': 'restaurant', 'rating': 4.7},
            {'name': 'Traditional Food', 'city': 'Vushtrri', 'category': 'restaurant', 'rating': 4.5},
            
            # Barbers
            {'name': 'Barber Shop King', 'city': 'Prishtina', 'category': 'barber', 'rating': 4.8},
            {'name': "Gents Salon", 'city': 'Prishtina', 'category': 'barber', 'rating': 4.6},
            {'name': 'Modern Cuts', 'city': 'Prizren', 'category': 'barber', 'rating': 4.5},
            {'name': 'Classic Barber', 'city': 'Gjakova', 'category': 'barber', 'rating': 4.7},
            {'name': 'Style Zone', 'city': 'Peja', 'category': 'barber', 'rating': 4.4},
            {'name': 'Premium Cuts', 'city': 'Mitrovica', 'category': 'barber', 'rating': 4.9},
            {'name': "Men's Grooming", 'city': 'Ferizaj', 'category': 'barber', 'rating': 4.3},
            {'name': 'Urban Style', 'city': 'Suva Reka', 'category': 'barber', 'rating': 4.6},
            {'name': 'Elite Barber', 'city': 'Vushtrri', 'category': 'barber', 'rating': 4.8},
            
            # More businesses
            {'name': 'Legal Office Advocate', 'city': 'Prishtina', 'category': 'lawyer', 'rating': 4.9},
            {'name': 'Auto Service Pro', 'city': 'Prishtina', 'category': 'auto_service', 'rating': 4.5},
            {'name': 'Gym Power Fitness', 'city': 'Prishtina', 'category': 'gym', 'rating': 4.7},
            {'name': 'Cafe Corner', 'city': 'Prishtina', 'category': 'cafe', 'rating': 4.3},
            {'name': 'Hotel Central', 'city': 'Prishtina', 'category': 'hotel', 'rating': 4.6},
        ]
        
        leads = []
        for i, business in enumerate(kosovo_businesses):
            # Random phone patterns
            phone_patterns = [
                f"+383 44 {random.randint(100, 999)} {random.randint(100, 999)}",
                f"+383 49 {random.randint(100, 999)} {random.randint(100, 999)}",
                f"+383 {random.choice([44, 45, 46, 47, 48, 49])} {random.randint(100000, 999999)}"
            ]
            
            # Some have websites, some don't (realistic)
            has_website = random.choice([True, False, True, False])
            
            # Mix of statuses
            status_choices = [LeadStatus.NEW] * 7 + [LeadStatus.CONTACTED] * 2 + [LeadStatus.REPLIED] * 1
            temp_choices = [LeadTemperature.HOT] * 3 + [LeadTemperature.WARM] * 4 + [LeadTemperature.COLD] * 3
            
            lead = Lead(
                name=business['name'],
                phone=random.choice(phone_patterns),
                email=f"{business['name'].lower().replace(' ', '').replace('-', '')}@example.com",
                city=business['city'],
                country='Kosovo',
                category=business['category'],
                rating=business['rating'],
                address=f"Rruga e {random.choice(['Ismail Qemali', 'Shtjefën Gërqov', 'Nëna Mother Teresa'])} {random.randint(10, 200)}",
                website=f"http://{business['name'].lower().replace(' ', '').replace('-', '')}.com" if has_website else '',
                status=random.choice(status_choices),
                temperature=random.choice(temp_choices),
                lead_score=int(business['rating'] * 20)  # Simple scoring
            )
            leads.append(lead)
        
        # Add all leads
        for lead in leads:
            db.session.add(lead)
        
        db.session.commit()
        print(f"✅ Created {len(leads)} realistic Kosovo business leads!")
        
        # Stats
        total_leads = Lead.query.count()
        by_category = db.session.query(Lead.category, db.func.count(Lead.id)).group_by(Lead.category).all()
        by_status = db.session.query(Lead.status, db.func.count(Lead.id)).group_by(Lead.status).all()
        
        print(f"\n📊 Database Statistics:")
        print(f"Total leads: {total_leads}")
        print(f"By category: {dict(by_category)}")
        print(f"By status: {dict(by_status)}")

if __name__ == '__main__':
    create_realistic_leads()