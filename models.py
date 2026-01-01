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