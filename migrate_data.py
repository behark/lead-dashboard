"""
Migration script to import leads from CSV to SQLite database
"""
import csv
import os
from datetime import datetime, timezone
from app import create_app
from models import db, Lead, LeadStatus, LeadTemperature


def migrate_from_csv(csv_path):
    """Migrate leads from CSV file to database"""
    
    app = create_app()
    
    with app.app_context():
        # Check if already migrated
        if Lead.query.count() > 0:
            print(f"Database already has {Lead.query.count()} leads. Skipping migration.")
            return Lead.query.count()
        
        count = 0
        batch_size = 500
        batch = []
        
        with open(csv_path, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                # Parse status
                status_str = row.get('status', 'NEW').upper()
                try:
                    status = LeadStatus[status_str]
                except KeyError:
                    status = LeadStatus.NEW
                
                # Parse temperature
                temp_str = row.get('temperature', 'WARM').upper()
                try:
                    temperature = LeadTemperature[temp_str]
                except KeyError:
                    temperature = LeadTemperature.WARM
                
                # Parse dates
                created_at = None
                if row.get('created_at'):
                    try:
                        created_at = datetime.fromisoformat(row['created_at'].replace('Z', '+00:00'))
                    except (ValueError, AttributeError):
                        created_at = datetime.now(timezone.utc)
                else:
                    created_at = datetime.now(timezone.utc)
                
                last_contacted = None
                if row.get('last_contacted'):
                    try:
                        last_contacted = datetime.fromisoformat(row['last_contacted'].replace('Z', '+00:00'))
                    except (ValueError, AttributeError):
                        pass
                
                # Parse rating
                rating = None
                if row.get('rating'):
                    try:
                        rating = float(row['rating'])
                    except (ValueError, TypeError):
                        pass
                
                # Parse lead score
                lead_score = 50
                if row.get('lead_score'):
                    try:
                        lead_score = int(row['lead_score'])
                    except (ValueError, TypeError):
                        pass
                
                # Check for website
                has_website = bool(row.get('website', '').strip())
                
                lead = Lead(
                    name=row.get('name', ''),
                    phone=row.get('phone', ''),
                    email=row.get('email', ''),
                    city=row.get('city', ''),
                    address=row.get('address', ''),
                    country=row.get('country', 'Kosovo'),
                    language=row.get('language', 'sq'),
                    category=row.get('category', ''),
                    rating=rating,
                    maps_url=row.get('maps_url', ''),
                    website=row.get('website', ''),
                    whatsapp_link=row.get('whatsapp_link', ''),
                    first_message=row.get('first_message', ''),
                    lead_score=lead_score,
                    temperature=temperature,
                    suggested_price=row.get('suggested_price', ''),
                    status=status,
                    notes=row.get('notes', ''),
                    created_at=created_at,
                    last_contacted=last_contacted,
                    has_website=has_website
                )
                
                batch.append(lead)
                count += 1
                
                # Batch insert for performance
                if len(batch) >= batch_size:
                    db.session.bulk_save_objects(batch)
                    db.session.commit()
                    print(f"Migrated {count} leads...")
                    batch = []
        
        # Insert remaining
        if batch:
            db.session.bulk_save_objects(batch)
            db.session.commit()
        
        print(f"Migration complete. Total leads: {count}")
        
        # Recalculate scores
        print("Recalculating lead scores...")
        leads = Lead.query.all()
        for lead in leads:
            lead.calculate_score()
        db.session.commit()
        print("Scores recalculated.")
        
        return count


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        csv_path = os.path.join(os.path.dirname(__file__), 'leads_clean.csv')
    else:
        csv_path = sys.argv[1]
    
    if not os.path.exists(csv_path):
        print(f"Error: CSV file not found at {csv_path}")
        sys.exit(1)
    
    migrate_from_csv(csv_path)
