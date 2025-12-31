#!/usr/bin/env python3
"""
Initialize database with updated schema
"""
from models import db, MessageTemplate, ContactChannel
from app import create_app

def init_db():
    app = create_app()
    with app.app_context():
        print("Creating all tables with updated schema...")
        db.create_all()
        print("✅ Database initialized successfully!")
        
        # Set a default template
        print("Setting up default template...")
        default_template = MessageTemplate(
            name="Default WhatsApp Template",
            channel="whatsapp",
            content="Pershendetje 👋\n\nPashe {business_name} ne Google - {rating}⭐, po beni shkelqyeshem!",
            is_default=True
        )
        db.session.add(default_template)
        db.session.commit()
        print("✅ Default template created!")

if __name__ == '__main__':
    init_db()