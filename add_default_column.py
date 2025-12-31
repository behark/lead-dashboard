from models import db
from app import create_app

app = create_app()

with app.app_context():
    try:
        # Add is_default column to MessageTemplate table
        db.execute('ALTER TABLE message_templates ADD COLUMN is_default BOOLEAN DEFAULT 0')
        db.session.commit()
        print('✅ is_default column added successfully!')
    except Exception as e:
        print(f'Error adding column: {e}')
        print('Column might already exist, continuing...')