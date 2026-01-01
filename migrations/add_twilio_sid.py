"""
Migration script to add twilio_message_sid column to contact_logs table
Run this if the column doesn't exist yet
"""
from models import db
from app import create_app

app = create_app()

with app.app_context():
    try:
        # Check if column exists
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns('contact_logs')]
        
        if 'twilio_message_sid' not in columns:
            db.engine.execute('ALTER TABLE contact_logs ADD COLUMN twilio_message_sid VARCHAR(50)')
            db.engine.execute('CREATE INDEX IF NOT EXISTS ix_contact_logs_twilio_message_sid ON contact_logs(twilio_message_sid)')
            print("✅ Added twilio_message_sid column and index")
        else:
            print("✅ Column twilio_message_sid already exists")
            
        if 'external_message_id' not in columns:
            db.engine.execute('ALTER TABLE contact_logs ADD COLUMN external_message_id VARCHAR(100)')
            print("✅ Added external_message_id column")
        else:
            print("✅ Column external_message_id already exists")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        # Try using SQLAlchemy DDL
        from sqlalchemy import text
        try:
            with db.engine.connect() as conn:
                conn.execute(text('ALTER TABLE contact_logs ADD COLUMN IF NOT EXISTS twilio_message_sid VARCHAR(50)'))
                conn.execute(text('CREATE INDEX IF NOT EXISTS ix_contact_logs_twilio_message_sid ON contact_logs(twilio_message_sid)'))
                conn.execute(text('ALTER TABLE contact_logs ADD COLUMN IF NOT EXISTS external_message_id VARCHAR(100)'))
                conn.commit()
            print("✅ Migration completed using SQLAlchemy")
        except Exception as e2:
            print(f"❌ Migration failed: {e2}")
            print("⚠️  You may need to run this manually in your database")
