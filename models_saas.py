"""
SaaS Multi-Tenancy Models
Organization, Subscription, Usage Tracking, Team Management
"""
from datetime import datetime, timezone, timedelta
from models import db
from enum import Enum


class SubscriptionPlan(str, Enum):
    """Subscription plan tiers"""
    FREE = 'free'
    STARTER = 'starter'
    PROFESSIONAL = 'professional'
    ENTERPRISE = 'enterprise'


class SubscriptionStatus(str, Enum):
    """Subscription status"""
    TRIAL = 'trial'
    ACTIVE = 'active'
    PAST_DUE = 'past_due'
    CANCELED = 'canceled'
    EXPIRED = 'expired'


class OrganizationRole(str, Enum):
    """User roles within an organization"""
    OWNER = 'owner'
    ADMIN = 'admin'
    MEMBER = 'member'
    VIEWER = 'viewer'


class Organization(db.Model):
    """
    Organization/Tenant model
    Each client gets their own organization with isolated data
    """
    __tablename__ = 'organizations'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False)  # For subdomain
    
    # Contact info
    email = db.Column(db.String(200))
    phone = db.Column(db.String(50))
    website = db.Column(db.String(200))
    
    # Address
    address = db.Column(db.String(500))
    city = db.Column(db.String(100))
    country = db.Column(db.String(100))
    
    # Branding (for white-label)
    logo_url = db.Column(db.String(500))
    primary_color = db.Column(db.String(7), default='#667eea')  # Hex color
    
    # Settings
    timezone = db.Column(db.String(50), default='UTC')
    language = db.Column(db.String(10), default='en')
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    subscription = db.relationship('Subscription', backref='organization', uselist=False, cascade='all, delete-orphan')
    members = db.relationship('OrganizationMember', backref='organization', lazy='dynamic', cascade='all, delete-orphan')
    leads = db.relationship('Lead', backref='organization', lazy='dynamic')
    usage_records = db.relationship('UsageRecord', backref='organization', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Organization {self.name}>'
    
    @property
    def member_count(self):
        """Get number of members"""
        return self.members.count()
    
    @property
    def lead_count(self):
        """Get number of leads"""
        return self.leads.count()
    
    @property
    def is_trial(self):
        """Check if organization is on trial"""
        return self.subscription and self.subscription.status == SubscriptionStatus.TRIAL
    
    @property
    def trial_days_left(self):
        """Get remaining trial days"""
        if not self.is_trial or not self.subscription:
            return 0
        if not self.subscription.trial_ends_at:
            return 0
        delta = self.subscription.trial_ends_at - datetime.now(timezone.utc)
        return max(0, delta.days)


class Subscription(db.Model):
    """
    Subscription model
    Tracks billing, plan, and limits for each organization
    """
    __tablename__ = 'subscriptions'
    
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False, unique=True)
    
    # Plan details
    plan = db.Column(db.Enum(SubscriptionPlan), default=SubscriptionPlan.FREE)
    status = db.Column(db.Enum(SubscriptionStatus), default=SubscriptionStatus.TRIAL)
    
    # Pricing
    price_monthly = db.Column(db.Float, default=0.0)  # In EUR
    price_yearly = db.Column(db.Float, default=0.0)
    billing_cycle = db.Column(db.String(20), default='monthly')  # monthly, yearly
    
    # Stripe integration
    stripe_customer_id = db.Column(db.String(100))
    stripe_subscription_id = db.Column(db.String(100))
    stripe_price_id = db.Column(db.String(100))
    
    # Limits
    max_leads = db.Column(db.Integer, default=50)  # Max leads per month
    max_users = db.Column(db.Integer, default=1)   # Max team members
    max_contacts_per_day = db.Column(db.Integer, default=50)  # Max messages per day
    max_templates = db.Column(db.Integer, default=5)
    max_sequences = db.Column(db.Integer, default=2)
    
    # Features
    has_api_access = db.Column(db.Boolean, default=False)
    has_white_label = db.Column(db.Boolean, default=False)
    has_priority_support = db.Column(db.Boolean, default=False)
    has_custom_integrations = db.Column(db.Boolean, default=False)
    has_advanced_analytics = db.Column(db.Boolean, default=False)
    
    # Trial
    trial_ends_at = db.Column(db.DateTime)
    
    # Billing dates
    current_period_start = db.Column(db.DateTime)
    current_period_end = db.Column(db.DateTime)
    next_billing_date = db.Column(db.DateTime)
    
    # Cancellation
    cancel_at_period_end = db.Column(db.Boolean, default=False)
    canceled_at = db.Column(db.DateTime)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    def __repr__(self):
        return f'<Subscription {self.plan.value} - {self.status.value}>'
    
    @property
    def is_active(self):
        """Check if subscription is active"""
        return self.status in [SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL]
    
    @property
    def is_paid(self):
        """Check if subscription is paid (not free)"""
        return self.plan != SubscriptionPlan.FREE
    
    @property
    def days_until_renewal(self):
        """Get days until next billing"""
        if not self.next_billing_date:
            return None
        delta = self.next_billing_date - datetime.now(timezone.utc)
        return max(0, delta.days)
    
    def can_add_lead(self):
        """Check if organization can add more leads this month"""
        # Get current month usage
        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        current_usage = UsageRecord.query.filter(
            UsageRecord.organization_id == self.organization_id,
            UsageRecord.usage_type == 'lead_created',
            UsageRecord.created_at >= month_start
        ).count()
        
        return current_usage < self.max_leads
    
    def can_add_user(self):
        """Check if organization can add more users"""
        return self.organization.member_count < self.max_users
    
    def can_send_message(self):
        """Check if organization can send more messages today"""
        # Get today's usage
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        current_usage = UsageRecord.query.filter(
            UsageRecord.organization_id == self.organization_id,
            UsageRecord.usage_type == 'message_sent',
            UsageRecord.created_at >= today_start
        ).count()
        
        return current_usage < self.max_contacts_per_day


class OrganizationMember(db.Model):
    """
    Organization membership
    Links users to organizations with roles
    """
    __tablename__ = 'organization_members'
    
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    role = db.Column(db.Enum(OrganizationRole), default=OrganizationRole.MEMBER)
    
    # Permissions
    can_manage_leads = db.Column(db.Boolean, default=True)
    can_send_messages = db.Column(db.Boolean, default=True)
    can_view_analytics = db.Column(db.Boolean, default=True)
    can_manage_templates = db.Column(db.Boolean, default=False)
    can_manage_team = db.Column(db.Boolean, default=False)
    can_manage_billing = db.Column(db.Boolean, default=False)
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    invited_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    joined_at = db.Column(db.DateTime)
    
    # Unique constraint: one user can only be in an org once
    __table_args__ = (
        db.UniqueConstraint('organization_id', 'user_id', name='unique_org_user'),
    )
    
    def __repr__(self):
        return f'<OrganizationMember org={self.organization_id} user={self.user_id} role={self.role.value}>'
    
    @property
    def is_owner(self):
        return self.role == OrganizationRole.OWNER
    
    @property
    def is_admin(self):
        return self.role in [OrganizationRole.OWNER, OrganizationRole.ADMIN]
    
    def has_permission(self, permission):
        """Check if member has specific permission"""
        # Owners have all permissions
        if self.is_owner:
            return True
        
        # Admins have most permissions
        if self.is_admin:
            return permission != 'can_manage_billing'
        
        # Check specific permission
        return getattr(self, permission, False)


class UsageRecord(db.Model):
    """
    Usage tracking for billing and limits
    Tracks leads created, messages sent, API calls, etc.
    """
    __tablename__ = 'usage_records'
    
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Usage type
    usage_type = db.Column(db.String(50), nullable=False)  # lead_created, message_sent, api_call, etc.
    
    # Resource info
    resource_id = db.Column(db.Integer)  # ID of the lead, message, etc.
    extra_data = db.Column(db.JSON)  # Additional data (renamed from metadata to avoid SQLAlchemy conflict)
    
    # Quantity (for usage-based billing)
    quantity = db.Column(db.Integer, default=1)
    
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    
    def __repr__(self):
        return f'<UsageRecord {self.usage_type} org={self.organization_id}>'
    
    @staticmethod
    def record_usage(organization_id, usage_type, user_id=None, resource_id=None, extra_data=None, quantity=1):
        """Helper method to record usage"""
        record = UsageRecord(
            organization_id=organization_id,
            user_id=user_id,
            usage_type=usage_type,
            resource_id=resource_id,
            extra_data=extra_data,
            quantity=quantity
        )
        db.session.add(record)
        db.session.commit()
        return record


class Invoice(db.Model):
    """
    Invoice tracking
    Stores billing history
    """
    __tablename__ = 'invoices'
    
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    
    # Invoice details
    invoice_number = db.Column(db.String(50), unique=True)
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(3), default='EUR')
    
    # Status
    status = db.Column(db.String(20), default='pending')  # pending, paid, failed, refunded
    
    # Stripe
    stripe_invoice_id = db.Column(db.String(100))
    stripe_payment_intent_id = db.Column(db.String(100))
    
    # Dates
    issued_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    due_at = db.Column(db.DateTime)
    paid_at = db.Column(db.DateTime)
    
    # PDF
    pdf_url = db.Column(db.String(500))
    
    # Relationships
    organization = db.relationship('Organization', backref='invoices')
    
    def __repr__(self):
        return f'<Invoice {self.invoice_number} - {self.amount} {self.currency}>'


# Plan configurations
PLAN_CONFIGS = {
    SubscriptionPlan.FREE: {
        'name': 'Free',
        'price_monthly': 0,
        'price_yearly': 0,
        'max_leads': 50,
        'max_users': 1,
        'max_contacts_per_day': 10,
        'max_templates': 3,
        'max_sequences': 1,
        'has_api_access': False,
        'has_white_label': False,
        'has_priority_support': False,
        'has_custom_integrations': False,
        'has_advanced_analytics': False,
    },
    SubscriptionPlan.STARTER: {
        'name': 'Starter',
        'price_monthly': 49,
        'price_yearly': 490,  # ~2 months free
        'max_leads': 500,
        'max_users': 3,
        'max_contacts_per_day': 100,
        'max_templates': 10,
        'max_sequences': 5,
        'has_api_access': False,
        'has_white_label': False,
        'has_priority_support': False,
        'has_custom_integrations': False,
        'has_advanced_analytics': True,
    },
    SubscriptionPlan.PROFESSIONAL: {
        'name': 'Professional',
        'price_monthly': 149,
        'price_yearly': 1490,
        'max_leads': 5000,
        'max_users': 10,
        'max_contacts_per_day': 500,
        'max_templates': 50,
        'max_sequences': 20,
        'has_api_access': True,
        'has_white_label': False,
        'has_priority_support': True,
        'has_custom_integrations': True,
        'has_advanced_analytics': True,
    },
    SubscriptionPlan.ENTERPRISE: {
        'name': 'Enterprise',
        'price_monthly': 499,
        'price_yearly': 4990,
        'max_leads': -1,  # Unlimited
        'max_users': -1,
        'max_contacts_per_day': -1,
        'max_templates': -1,
        'max_sequences': -1,
        'has_api_access': True,
        'has_white_label': True,
        'has_priority_support': True,
        'has_custom_integrations': True,
        'has_advanced_analytics': True,
    }
}


def create_organization(name, owner_user, plan=SubscriptionPlan.FREE, trial_days=14):
    """
    Helper function to create a new organization with subscription
    """
    import re
    
    # Generate slug from name
    slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
    
    # Ensure unique slug
    base_slug = slug
    counter = 1
    while Organization.query.filter_by(slug=slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1
    
    # Create organization
    org = Organization(
        name=name,
        slug=slug,
        email=owner_user.email if hasattr(owner_user, 'email') else None
    )
    db.session.add(org)
    db.session.flush()  # Get org.id
    
    # Create subscription
    config = PLAN_CONFIGS[plan]
    subscription = Subscription(
        organization_id=org.id,
        plan=plan,
        status=SubscriptionStatus.TRIAL if trial_days > 0 else SubscriptionStatus.ACTIVE,
        **{k: v for k, v in config.items() if k != 'name'}
    )
    
    if trial_days > 0:
        subscription.trial_ends_at = datetime.now(timezone.utc) + timedelta(days=trial_days)
    
    db.session.add(subscription)
    
    # Add owner as member
    member = OrganizationMember(
        organization_id=org.id,
        user_id=owner_user.id,
        role=OrganizationRole.OWNER,
        can_manage_leads=True,
        can_send_messages=True,
        can_view_analytics=True,
        can_manage_templates=True,
        can_manage_team=True,
        can_manage_billing=True,
        joined_at=datetime.now(timezone.utc)
    )
    db.session.add(member)
    
    db.session.commit()
    
    return org
