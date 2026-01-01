"""
Migration: Add Multi-Tenancy Support
Adds organizations, subscriptions, and organization members tables
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from models import db
from models_saas import (
    Organization, Subscription, OrganizationMember, UsageRecord, Invoice,
    SubscriptionPlan, SubscriptionStatus, OrganizationRole,
    create_organization
)
from models import User, Lead, MessageTemplate, Sequence
from datetime import datetime, timezone

def migrate():
    """Run the migration"""
    app = create_app()
    
    with app.app_context():
        print("🚀 Starting Multi-Tenancy Migration...")
        
        # Step 1: Create new tables
        print("\n📊 Creating new tables...")
        try:
            db.create_all()
            print("✅ Tables created successfully")
        except Exception as e:
            print(f"⚠️  Some tables may already exist: {e}")
        
        # Step 2: Check if we need to migrate existing data
        existing_users = User.query.count()
        existing_orgs = Organization.query.count()
        
        if existing_users > 0 and existing_orgs == 0:
            print(f"\n🔄 Found {existing_users} existing users. Creating organizations...")
            
            # For each existing user, create a personal organization
            users = User.query.all()
            for user in users:
                # Check if user already has an organization
                existing_member = OrganizationMember.query.filter_by(user_id=user.id).first()
                if existing_member:
                    print(f"   ⏭️  User {user.username} already has an organization")
                    continue
                
                # Create organization for this user
                org_name = f"{user.username}'s Organization"
                print(f"   📦 Creating organization: {org_name}")
                
                org = create_organization(
                    name=org_name,
                    owner_user=user,
                    plan=SubscriptionPlan.FREE,
                    trial_days=14
                )
                
                print(f"   ✅ Created organization: {org.name} (ID: {org.id})")
                
                # Migrate user's leads to this organization
                user_leads = Lead.query.filter_by(assigned_to=user.id).all()
                if user_leads:
                    print(f"   🔗 Migrating {len(user_leads)} leads...")
                    for lead in user_leads:
                        lead.organization_id = org.id
                    db.session.commit()
                    print(f"   ✅ Migrated {len(user_leads)} leads")
        
        elif existing_orgs > 0:
            print(f"\n✅ Found {existing_orgs} existing organizations. Skipping migration.")
        
        else:
            print("\n📝 No existing users found. Creating default organization...")
            
            # Create a default admin user and organization
            admin = User.query.filter_by(username='admin').first()
            if not admin:
                admin = User(
                    username='admin',
                    email='admin@example.com',
                    role='admin'
                )
                admin.set_password('admin123')  # Change this!
                db.session.add(admin)
                db.session.commit()
                print("   ✅ Created admin user (username: admin, password: admin123)")
            
            # Create organization
            org = create_organization(
                name="Default Organization",
                owner_user=admin,
                plan=SubscriptionPlan.PROFESSIONAL,
                trial_days=30
            )
            print(f"   ✅ Created default organization: {org.name}")
        
        # Step 3: Update all orphaned leads (leads without organization_id)
        orphaned_leads = Lead.query.filter_by(organization_id=None).all()
        if orphaned_leads:
            print(f"\n🔍 Found {len(orphaned_leads)} orphaned leads...")
            
            # Assign to first organization
            first_org = Organization.query.first()
            if first_org:
                print(f"   📦 Assigning to organization: {first_org.name}")
                for lead in orphaned_leads:
                    lead.organization_id = first_org.id
                db.session.commit()
                print(f"   ✅ Assigned {len(orphaned_leads)} leads")
        
        # Step 4: Update templates and sequences
        orphaned_templates = MessageTemplate.query.filter_by(organization_id=None).all()
        if orphaned_templates:
            print(f"\n📝 Found {len(orphaned_templates)} global templates (keeping as global)")
        
        orphaned_sequences = Sequence.query.filter_by(organization_id=None).all()
        if orphaned_sequences:
            print(f"\n🔄 Found {len(orphaned_sequences)} global sequences (keeping as global)")
        
        # Step 5: Summary
        print("\n" + "="*60)
        print("✅ MIGRATION COMPLETE!")
        print("="*60)
        print(f"\n📊 Summary:")
        print(f"   Organizations: {Organization.query.count()}")
        print(f"   Subscriptions: {Subscription.query.count()}")
        print(f"   Organization Members: {OrganizationMember.query.count()}")
        print(f"   Leads with Organizations: {Lead.query.filter(Lead.organization_id.isnot(None)).count()}")
        print(f"   Total Leads: {Lead.query.count()}")
        
        # Show organizations
        print(f"\n🏢 Organizations:")
        for org in Organization.query.all():
            members = org.members.count()
            leads = org.leads.count()
            plan = org.subscription.plan.value if org.subscription else 'none'
            print(f"   • {org.name} ({org.slug})")
            print(f"     Plan: {plan} | Members: {members} | Leads: {leads}")
        
        print("\n🎉 Ready to use multi-tenancy!")
        print("\n⚠️  IMPORTANT: If you created an admin user, change the password!")
        print("   Default credentials: admin / admin123")
        print("\n")

if __name__ == '__main__':
    migrate()
