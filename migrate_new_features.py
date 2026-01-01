#!/usr/bin/env python3
"""
Migration script for new dashboard features
Adds SavedFilter and BulkJob tables
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app import create_app
from models import db

def migrate():
    """Run database migration"""
    app = create_app()
    
    with app.app_context():
        print("🔄 Running migrations...")
        
        try:
            # Create tables
            db.create_all()
            print("✅ Database tables created/updated successfully")
            
            # Check if tables exist
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            
            if 'saved_filters' in tables:
                print("✅ SavedFilter table created")
            if 'bulk_jobs' in tables:
                print("✅ BulkJob table created")
            
            print("\n✨ Migration completed successfully!")
            
        except Exception as e:
            print(f"❌ Migration failed: {e}")
            return False
    
    return True

if __name__ == '__main__':
    success = migrate()
    sys.exit(0 if success else 1)
