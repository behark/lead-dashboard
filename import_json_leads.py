"""
Import leads from leads_data.json to SQLite database
"""
import json
import os
from datetime import datetime, timezone
from app import create_app
from models import db, Lead, LeadStatus, LeadTemperature, User, UserRole

def import_leads():
    app = create_app()
    with app.app_context():
        # Create tables if they don't exist
        db.create_all()
        
        # Check if already has leads
        if Lead.query.count() > 0:
            print(f"Database already has {Lead.query.count()} leads.")
            # return
        
        # Create admin user if not exists
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', email='admin@example.com', role=UserRole.ADMIN)
            admin.set_password('admin123')
            db.session.add(admin)
            print("Created admin user (admin/admin123)")

        json_path = 'leads_data.json'
        if not os.path.exists(json_path):
            print(f"Error: {json_path} not found")
            return

        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            print(f"Loading {len(data)} leads from {json_path}")
            
            count = 0
            for item in data:
                # Parse Enums
                status_val = item.get('status', 'NEW')
                if isinstance(status_val, str):
                    status = getattr(LeadStatus, status_val.upper(), LeadStatus.NEW)
                else:
                    status = LeadStatus.NEW
                    
                temp_val = item.get('temperature', 'WARM')
                if isinstance(temp_val, str):
                    temperature = getattr(LeadTemperature, temp_val.upper(), LeadTemperature.WARM)
                else:
                    temperature = LeadTemperature.WARM
                
                # Parse Dates
                created_at = None
                if item.get('created_at'):
                    try:
                        created_at = datetime.fromisoformat(item['created_at'].replace('Z', '+00:00'))
                    except (ValueError, TypeError):
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
                    has_website=bool(item.get('website', '').strip())
                )
                db.session.add(lead)
                count += 1
                if count % 100 == 0:
                    db.session.commit()
                    print(f"Imported {count} leads...")
            
            db.session.commit()
            print(f"✅ Successfully imported {count} leads!")

if __name__ == '__main__':
    import_leads()
