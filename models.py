from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, timezone, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import enum

db = SQLAlchemy()


class UserRole(enum.Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    SALES = "sales"


class LeadStatus(enum.Enum):
    NEW = "NEW"
    CONTACTED = "CONTACTED"
    REPLIED = "REPLIED"
    CLOSED = "CLOSED"
    LOST = "LOST"


class LeadTemperature(enum.Enum):
    HOT = "HOT"
    WARM = "WARM"
    COLD = "COLD"


class ContactChannel(enum.Enum):
    WHATSAPP = "whatsapp"
    EMAIL = "email"
    SMS = "sms"
    PHONE = "phone"


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.Enum(UserRole), default=UserRole.SALES)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Account security
    failed_login_attempts = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime, nullable=True)
    last_login = db.Column(db.DateTime, nullable=True)
    
    # Password reset
    password_reset_token = db.Column(db.String(100), nullable=True, index=True)
    password_reset_expires = db.Column(db.DateTime, nullable=True)
    
    # Email verification
    email_verified = db.Column(db.Boolean, default=False)
    email_verification_token = db.Column(db.String(100), nullable=True)
    
    # Two-Factor Authentication
    two_factor_enabled = db.Column(db.Boolean, default=False)
    two_factor_secret = db.Column(db.String(32), nullable=True)  # Base32 encoded secret
    backup_codes = db.Column(db.Text, nullable=True)  # JSON array of backup codes
    
    # Relationships
    assigned_leads = db.relationship('Lead', backref='assigned_user', lazy='dynamic')
    contact_logs = db.relationship('ContactLog', backref='user', lazy='dynamic')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    @property
    def leads_count(self):
        return self.assigned_leads.count()
    
    @property
    def closed_leads_count(self):
        return self.assigned_leads.filter_by(status=LeadStatus.CLOSED).count()


class Lead(db.Model):
    __tablename__ = 'leads'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Multi-tenancy: Each lead belongs to an organization
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=True, index=True)  # Nullable for migration
    
    name = db.Column(db.String(200), nullable=False, index=True)
    phone = db.Column(db.String(50))
    email = db.Column(db.String(120))
    city = db.Column(db.String(100), index=True)
    address = db.Column(db.String(300))
    country = db.Column(db.String(100), default='Kosovo', index=True)
    language = db.Column(db.String(10), default='sq')
    category = db.Column(db.String(100), index=True)
    rating = db.Column(db.Float)
    maps_url = db.Column(db.String(500))
    website = db.Column(db.String(500))
    whatsapp_link = db.Column(db.String(1000))
    first_message = db.Column(db.Text)
    
    # Scoring
    lead_score = db.Column(db.Integer, default=50, index=True)
    temperature = db.Column(db.Enum(LeadTemperature), default=LeadTemperature.WARM, index=True)
    suggested_price = db.Column(db.String(50))
    
    # Status tracking
    status = db.Column(db.Enum(LeadStatus), default=LeadStatus.NEW, index=True)
    notes = db.Column(db.Text)

    # Compliance and opt-out
    gdpr_consent = db.Column(db.Boolean, default=True)
    marketing_opt_out = db.Column(db.Boolean, default=False)
    opt_out_reason = db.Column(db.String(200))
    opt_out_date = db.Column(db.DateTime)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    last_contacted = db.Column(db.DateTime)
    last_response = db.Column(db.DateTime)
    next_followup = db.Column(db.DateTime, index=True)
    
    # Assignment
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Sequence tracking
    sequence_id = db.Column(db.Integer, db.ForeignKey('sequences.id'))
    sequence_step = db.Column(db.Integer, default=0)
    
    # Relationships
    contact_logs = db.relationship('ContactLog', backref='lead', lazy='dynamic', cascade='all, delete-orphan')
    
    # Score calculation factors
    has_website = db.Column(db.Boolean, default=False)
    response_time_hours = db.Column(db.Float)
    engagement_count = db.Column(db.Integer, default=0)

    # Enhanced scoring factors
    business_size_indicator = db.Column(db.String(20))  # small, medium, large
    online_presence_score = db.Column(db.Integer, default=0)  # 0-100
    competitor_count = db.Column(db.Integer, default=0)
    market_demand_score = db.Column(db.Integer, default=50)  # 0-100
    location_advantage = db.Column(db.Float, default=1.0)  # multiplier
    industry_growth_rate = db.Column(db.Float, default=0.0)
    
    def calculate_score(self):
        """Enhanced lead scoring with ML-like factors"""
        score = 50  # Base score

        # Rating factor (0-20 points)
        if self.rating:
            score += min(int(self.rating * 4), 20)

        # Has website factor (negative for prospects who need websites)
        if self.has_website:
            score -= 10
        else:
            score += 15

        # Engagement factor (0-20 points)
        score += min(self.engagement_count * 5, 20)

        # Response time factor
        if self.response_time_hours:
            if self.response_time_hours < 1:
                score += 15
            elif self.response_time_hours < 24:
                score += 10
            elif self.response_time_hours < 72:
                score += 5

        # Business size advantage
        if self.business_size_indicator == 'small':
            score += 10  # Small businesses are easier to work with
        elif self.business_size_indicator == 'large':
            score += 5   # Large businesses have bigger budgets

        # Online presence score (lower is better for prospects)
        if self.online_presence_score < 30:
            score += 15  # Poor online presence = high need
        elif self.online_presence_score < 60:
            score += 5

        # Market demand factor
        score += int((self.market_demand_score - 50) * 0.3)  # -15 to +15

        # Location advantage multiplier
        score = int(score * self.location_advantage)

        # Industry growth factor
        growth_bonus = int(self.industry_growth_rate * 10)  # 0-20 points
        score += min(growth_bonus, 20)

        # Competitor analysis (fewer competitors = better opportunity)
        if self.competitor_count < 3:
            score += 10
        elif self.competitor_count < 10:
            score += 5

        # Decay based on days since creation without contact
        if self.status == LeadStatus.NEW and self.created_at:
            created = self.created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            days_old = (datetime.now(timezone.utc) - created).days
            score -= min(days_old * 2, 30)

        self.lead_score = max(0, min(100, score))
        self.update_temperature()
        return self.lead_score
    
    def update_temperature(self):
        """Update temperature based on score"""
        if self.lead_score >= 70:
            self.temperature = LeadTemperature.HOT
        elif self.lead_score >= 40:
            self.temperature = LeadTemperature.WARM
        else:
            self.temperature = LeadTemperature.COLD
    
    def schedule_followup(self, days=3):
        """Schedule next follow-up"""
        self.next_followup = datetime.now(timezone.utc) + timedelta(days=days)
    
    @classmethod
    def get_contactable_leads(cls, limit=500, status_filter=None, organization_id=None):
        """
        Get leads that can be contacted (not opted out, have consent, have phone)
        
        Args:
            limit: Maximum number of leads to return (default: 500)
            status_filter: List of LeadStatus values to filter by (default: [NEW])
            organization_id: Filter by organization (optional, for multi-tenancy)
        
        Returns:
            Query result with contactable leads ordered by lead_score descending
        """
        if status_filter is None:
            status_filter = [LeadStatus.NEW]
        
        query = cls.query.filter(
            cls.status.in_(status_filter),
            cls.phone.isnot(None),
            cls.phone != '',
            cls.marketing_opt_out == False,
            cls.gdpr_consent == True
        )
        
        # Multi-tenancy support
        if organization_id is not None:
            query = query.filter(cls.organization_id == organization_id)
        
        return query.order_by(cls.lead_score.desc()).limit(limit)
    
    @classmethod
    def find_duplicate(cls, phone=None, name=None, organization_id=None):
        """
        Find duplicate leads by phone number or business name
        
        Args:
            phone: Phone number to check (optional)
            name: Business name to check (optional)
            organization_id: Organization ID for multi-tenancy (optional)
        
        Returns:
            Existing Lead if duplicate found, None otherwise
        """
        if not phone and not name:
            return None
        
        query = cls.query
        
        # Multi-tenancy support
        if organization_id is not None:
            query = query.filter(cls.organization_id == organization_id)
        
        # Check by phone (most reliable)
        if phone:
            # Normalize phone: extract digits only (last 9 digits for matching)
            normalized_phone = ''.join(c for c in phone if c.isdigit())
            if normalized_phone:
                # Get last 9 digits for matching (most phone numbers end with 9 digits)
                phone_suffix = normalized_phone[-9:] if len(normalized_phone) >= 9 else normalized_phone
                
                # Get all leads and check phone numbers (simpler than complex SQL)
                candidates = query.filter(cls.phone.isnot(None)).all()
                for candidate in candidates:
                    if candidate.phone:
                        candidate_phone = ''.join(c for c in candidate.phone if c.isdigit())
                        if candidate_phone and phone_suffix in candidate_phone:
                            return candidate
        
        # Check by name (case-insensitive exact match)
        if name:
            name_lower = name.lower().strip()
            candidates = query.filter(cls.name.isnot(None)).all()
            for candidate in candidates:
                if candidate.name and candidate.name.lower().strip() == name_lower:
                    return candidate
        
        return None
    
    @classmethod
    def create_or_update(cls, data, organization_id=None):
        """
        Create a new lead or update existing if duplicate found
        
        Args:
            data: Dictionary with lead data (name, phone, email, etc.)
            organization_id: Organization ID for multi-tenancy (optional)
        
        Returns:
            Tuple of (lead, is_new) where is_new is True if created, False if updated
        """
        # Check for duplicates
        existing = cls.find_duplicate(
            phone=data.get('phone'),
            name=data.get('name'),
            organization_id=organization_id
        )
        
        if existing:
            # Update existing lead with new data (preserve important fields)
            for key, value in data.items():
                if key not in ['id', 'created_at', 'organization_id'] and value is not None:
                    if hasattr(existing, key):
                        setattr(existing, key, value)
            return existing, False
        else:
            # Create new lead
            if organization_id:
                data['organization_id'] = organization_id
            new_lead = cls(**data)
            db.session.add(new_lead)
            return new_lead, True


class ContactLog(db.Model):
    __tablename__ = 'contact_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey('leads.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    channel = db.Column(db.Enum(ContactChannel), nullable=False)
    message_template_id = db.Column(db.Integer, db.ForeignKey('message_templates.id'))
    message_content = db.Column(db.Text)
    
    # Status
    sent_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    delivered_at = db.Column(db.DateTime)
    read_at = db.Column(db.DateTime)
    responded_at = db.Column(db.DateTime)
    response_content = db.Column(db.Text)
    
    # External service IDs for tracking
    twilio_message_sid = db.Column(db.String(50), index=True)  # Twilio message SID for status tracking
    external_message_id = db.Column(db.String(100))  # Generic external message ID
    
    # For A/B testing
    ab_variant = db.Column(db.String(10))
    
    # Automation tracking
    is_automated = db.Column(db.Boolean, default=False)
    sequence_step = db.Column(db.Integer)


class MessageTemplate(db.Model):
    __tablename__ = 'message_templates'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Multi-tenancy: Each template belongs to an organization (NULL = global template)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=True, index=True)
    
    name = db.Column(db.String(100), nullable=False)
    channel = db.Column(db.Enum(ContactChannel), nullable=False)
    language = db.Column(db.String(10), default='sq')
    category = db.Column(db.String(100))  # Target category (barber, dentist, etc.)
    
    subject = db.Column(db.String(200))  # For email
    content = db.Column(db.Text, nullable=False)
    
    # A/B testing
    variant = db.Column(db.String(10), default='A')
    
    # Stats
    times_sent = db.Column(db.Integer, default=0)
    times_opened = db.Column(db.Integer, default=0)
    times_responded = db.Column(db.Integer, default=0)
    
    is_active = db.Column(db.Boolean, default=True)
    is_default = db.Column(db.Boolean, default=False)  # For default WhatsApp template
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    @property
    def open_rate(self):
        return (self.times_opened / self.times_sent * 100) if self.times_sent > 0 else 0
    
    @property
    def response_rate(self):
        return (self.times_responded / self.times_sent * 100) if self.times_sent > 0 else 0


class Sequence(db.Model):
    __tablename__ = 'sequences'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Multi-tenancy: Each sequence belongs to an organization (NULL = global sequence)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=True, index=True)
    
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    steps = db.relationship('SequenceStep', backref='sequence', lazy='dynamic', order_by='SequenceStep.step_number')
    leads = db.relationship('Lead', backref='sequence', lazy='dynamic')


class SequenceStep(db.Model):
    __tablename__ = 'sequence_steps'
    
    id = db.Column(db.Integer, primary_key=True)
    sequence_id = db.Column(db.Integer, db.ForeignKey('sequences.id'), nullable=False)
    step_number = db.Column(db.Integer, nullable=False)
    
    channel = db.Column(db.Enum(ContactChannel), nullable=False)
    template_id = db.Column(db.Integer, db.ForeignKey('message_templates.id'))
    
    delay_days = db.Column(db.Integer, default=0)  # Days after previous step
    delay_hours = db.Column(db.Integer, default=0)
    
    # Conditions
    send_if_no_response = db.Column(db.Boolean, default=True)
    
    template = db.relationship('MessageTemplate')


class Analytics(db.Model):
    __tablename__ = 'analytics'

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, index=True)

    # Daily metrics
    leads_created = db.Column(db.Integer, default=0)
    contacts_made = db.Column(db.Integer, default=0)
    responses_received = db.Column(db.Integer, default=0)
    deals_closed = db.Column(db.Integer, default=0)
    deals_lost = db.Column(db.Integer, default=0)

    # Revenue
    revenue = db.Column(db.Float, default=0)

    # By channel
    whatsapp_sent = db.Column(db.Integer, default=0)
    whatsapp_responses = db.Column(db.Integer, default=0)
    email_sent = db.Column(db.Integer, default=0)
    email_responses = db.Column(db.Integer, default=0)
    sms_sent = db.Column(db.Integer, default=0)
    sms_responses = db.Column(db.Integer, default=0)

    # Best performing
    best_hour = db.Column(db.Integer)  # 0-23
    best_day = db.Column(db.Integer)  # 0-6 (Monday-Sunday)

    # Conversion funnel metrics
    contacted_to_responded_rate = db.Column(db.Float, default=0)  # contacts -> responses
    responded_to_closed_rate = db.Column(db.Float, default=0)    # responses -> closed deals
    overall_conversion_rate = db.Column(db.Float, default=0)     # leads created -> closed deals

    # Template performance
    best_template_id = db.Column(db.Integer, db.ForeignKey('message_templates.id'))
    best_template_response_rate = db.Column(db.Float, default=0)

    # Lead quality metrics
    avg_lead_score = db.Column(db.Float, default=0)
    hot_leads_count = db.Column(db.Integer, default=0)
    warm_leads_count = db.Column(db.Integer, default=0)
    cold_leads_count = db.Column(db.Integer, default=0)

    # Compliance metrics
    opt_outs_count = db.Column(db.Integer, default=0)
    gdpr_complaints = db.Column(db.Integer, default=0)

    # A/B testing results
    ab_test_winner_variant = db.Column(db.String(10))
    ab_test_improvement_rate = db.Column(db.Float, default=0)

class SavedFilter(db.Model):
    """Saved filter combinations for quick reuse"""
    __tablename__ = 'saved_filters'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    
    # Filter parameters stored as JSON
    filters = db.Column(db.JSON, nullable=False)  # {search: '', status: 'NEW', temp: 'HOT', etc}
    
    sort_by = db.Column(db.String(20), default='score')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_used = db.Column(db.DateTime)
    usage_count = db.Column(db.Integer, default=0)
    is_favorite = db.Column(db.Boolean, default=False)
    
    def __repr__(self):
        return f'<SavedFilter {self.name}>'


class BulkJob(db.Model):
    """Track bulk operations for progress and history"""
    __tablename__ = 'bulk_jobs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Job info
    job_type = db.Column(db.String(50), nullable=False)  # 'send_message', 'change_status', 'assign', etc
    status = db.Column(db.String(20), default='pending')  # pending, running, completed, failed, cancelled
    
    # Progress tracking
    total_items = db.Column(db.Integer, default=0)
    processed_items = db.Column(db.Integer, default=0)
    successful_items = db.Column(db.Integer, default=0)
    failed_items = db.Column(db.Integer, default=0)
    skipped_items = db.Column(db.Integer, default=0)
    
    # Job details (JSON)
    parameters = db.Column(db.JSON)  # channel, template_id, lead_ids, etc
    results = db.Column(db.JSON)  # {errors: [], skipped: []}
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    
    @property
    def progress_percent(self):
        if self.total_items == 0:
            return 0
        return int((self.processed_items / self.total_items) * 100)
    
    @property
    def is_active(self):
        return self.status in ['pending', 'running']
    
    def __repr__(self):
        return f'<BulkJob {self.job_type} {self.status}>'


class AuditLog(db.Model):
    """Audit log entry for tracking important user actions"""
    __tablename__ = 'audit_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), index=True)
    
    action = db.Column(db.String(100), nullable=False, index=True)
    resource_type = db.Column(db.String(50), index=True)
    resource_id = db.Column(db.Integer)
    
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(255))
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    
    status = db.Column(db.String(20), default='success')
    error_message = db.Column(db.Text)
    details = db.Column(db.Text)  # JSON string
    
    def __repr__(self):
        return f'<AuditLog {self.action} user_id={self.user_id}>'