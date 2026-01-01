"""
Migration Step 1: Add organization_id column to existing tables
This must run before the full multi-tenancy migration
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from models import db

def migrate():
    """Add organization_id columns to existing tables"""
    app = create_app()
    
    with app.app_context():
        print("🔧 Adding organization_id columns to existing tables...")
        
        # Get database connection
        connection = db.engine.connect()
        
        try:
            # Add organization_id to leads table
            print("\n📊 Adding organization_id to leads table...")
            try:
                connection.execute(db.text("""
                    ALTER TABLE leads 
                    ADD COLUMN organization_id INTEGER
                """))
                connection.commit()
                print("   ✅ Added organization_id to leads")
            except Exception as e:
                if "duplicate column name" in str(e).lower():
                    print("   ⏭️  Column already exists")
                else:
                    print(f"   ⚠️  Error: {e}")
            
            # Add organization_id to message_templates table
            print("\n📝 Adding organization_id to message_templates table...")
            try:
                connection.execute(db.text("""
                    ALTER TABLE message_templates 
                    ADD COLUMN organization_id INTEGER
                """))
                connection.commit()
                print("   ✅ Added organization_id to message_templates")
            except Exception as e:
                if "duplicate column name" in str(e).lower():
                    print("   ⏭️  Column already exists")
                else:
                    print(f"   ⚠️  Error: {e}")
            
            # Add organization_id to sequences table
            print("\n🔄 Adding organization_id to sequences table...")
            try:
                connection.execute(db.text("""
                    ALTER TABLE sequences 
                    ADD COLUMN organization_id INTEGER
                """))
                connection.commit()
                print("   ✅ Added organization_id to sequences")
            except Exception as e:
                if "duplicate column name" in str(e).lower():
                    print("   ⏭️  Column already exists")
                else:
                    print(f"   ⚠️  Error: {e}")
            
            print("\n✅ Column migration complete!")
            print("\n📝 Next step: Run add_multi_tenancy.py to create organizations")
            
        finally:
            connection.close()

if __name__ == '__main__':
    migrate()
