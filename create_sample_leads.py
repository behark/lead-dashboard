"""
Create sample leads for testing
"""
from models import db, Lead, LeadStatus, LeadTemperature
from app import create_app
import random

def create_sample_leads():
    app = create_app()
    with app.app_context():
        sample_leads = [
            {
                'name': 'Dentist Prishtina',
                'phone': '+383 44 123 456',
                'email': 'dentist@example.com',
                'city': 'Prishtina',
                'country': 'Kosovo',
                'category': 'dentist',
                'rating': 4.8,
                'address': 'Rruga "Ismail Qemali"',
                'website': 'http://dentist-prishtina.com',
                'status': LeadStatus.NEW,
                'temperature': LeadTemperature.HOT
            },
            {
                'name': 'Salon Bella',
                'phone': '+383 44 234 567',
                'email': 'salon@example.com',
                'city': 'Prizren',
                'country': 'Kosovo',
                'category': 'salon',
                'rating': 4.5,
                'address': 'Sheshi i Nolte',
                'website': '',
                'status': LeadStatus.NEW,
                'temperature': LeadTemperature.WARM
            },
            {
                'name': 'Restaurant Terra',
                'phone': '+383 44 345 678',
                'email': 'restaurant@example.com',
                'city': 'Peja',
                'country': 'Kosovo',
                'category': 'restaurant',
                'rating': 4.2,
                'address': 'Qendra e Qytetit',
                'website': 'http://restaurant-terra.com',
                'status': LeadStatus.NEW,
                'temperature': LeadTemperature.WARM
            },
            {
                'name': 'Barber Shop Alpha',
                'phone': '+383 44 456 789',
                'city': 'Gjakova',
                'country': 'Kosovo',
                'category': 'barber',
                'rating': 4.7,
                'address': 'Rruga e Perparimit',
                'website': 'http://barber-alpha.com',
                'status': LeadStatus.NEW,
                'temperature': LeadTemperature.HOT
            },
            {
                'name': 'Law Firm Legalis',
                'phone': '+383 44 567 890',
                'city': 'Mitrovica',
                'country': 'Kosovo',
                'category': 'lawyer',
                'rating': 4.9,
                'address': 'Rruga "Skenderbeu"',
                'website': 'http://legalis-ks.com',
                'status': LeadStatus.NEW,
                'temperature': LeadTemperature.HOT
            }
        ]
        
        for lead_data in sample_leads:
            lead = Lead(**lead_data)
            db.session.add(lead)
        
        db.session.commit()
        print(f"✅ Created {len(sample_leads)} sample leads!")
        
        # Show some stats
        total_leads = Lead.query.count()
        print(f"📊 Total leads in database: {total_leads}")

if __name__ == '__main__':
    create_sample_leads()