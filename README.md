# Lead Dashboard CRM

A comprehensive, production-ready lead management system with multi-channel outreach, automated sequences, analytics, and enterprise-grade features.

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-2.0+-green.svg)](https://flask.palletsprojects.com)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## Features

### Core Features
- **SQLite Database**: Fast, indexed database replacing CSV files
- **User Authentication**: Multi-user support with roles (Admin, Manager, Sales)
- **Lead Management**: Full CRUD with filtering, sorting, and bulk actions

### Contact Automation
- **WhatsApp Business API**: Send messages directly via Meta's API
- **Email Integration**: SMTP-based email sending
- **SMS via Twilio**: SMS fallback for non-responsive leads
- **Webhook Receivers**: Automatic response detection

### Automation
- **Outreach Sequences**: Multi-step automated campaigns (e.g., WhatsApp → Email → Final follow-up)
- **Dynamic Lead Scoring**: Scores based on rating, engagement, response time
- **Temperature Decay**: Leads automatically cool down if not contacted
- **Scheduled Follow-ups**: Automatic reminders and sequence processing

### Analytics
- **Conversion Funnels**: Track leads through each stage
- **Channel Performance**: Compare WhatsApp vs Email vs SMS
- **A/B Testing**: Test message variants and see winners
- **Best Contact Times**: Analyze optimal days/hours for outreach
- **Team Performance**: Track individual sales rep metrics

## Quick Start

### 1. Setup Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Environment
```bash
cp .env.example .env
# Edit .env with your API keys
```

### 4. Migrate Data from CSV
```bash
python migrate_data.py leads_clean.csv
```

### 5. Create Default Templates
```bash
flask create-default-templates
```

### 6. Run the Application
```bash
flask run
# or: python app.py
```

### 7. Create Admin Account
Visit http://localhost:5000 and register (first user becomes admin)

## Configuration

### WhatsApp Business API
1. Create a Meta Business account
2. Set up WhatsApp Business API
3. Get Phone Number ID and Access Token
4. Configure webhook URL: `https://your-domain.com/webhooks/whatsapp`

### Email (Gmail)
1. Enable 2FA on Gmail
2. Create an App Password
3. Use that as MAIL_PASSWORD

### Twilio SMS
1. Create Twilio account
2. Get Account SID, Auth Token, and Phone Number

## CLI Commands

```bash
# Initialize database
flask init-db

# Migrate from CSV
flask migrate-csv leads_clean.csv

# Create admin user
flask create-admin username email password

# Recalculate all lead scores
flask recalculate-scores

# Create default message templates
flask create-default-templates
```

## API Webhooks

### WhatsApp
- **Verify**: `GET /webhooks/whatsapp?hub.mode=subscribe&hub.verify_token=TOKEN`
- **Messages**: `POST /webhooks/whatsapp`

### Email (Mailgun)
- **Events**: `POST /webhooks/email/mailgun`

### SMS (Twilio)
- **Replies**: `POST /webhooks/sms/twilio`

## Project Structure

```
lead_dashboard/
├── app.py              # Main Flask application
├── config.py           # Configuration settings
├── models.py           # Database models
├── migrate_data.py     # CSV to SQLite migration
├── routes/
│   ├── auth.py         # Authentication routes
│   ├── main.py         # Lead management routes
│   ├── analytics.py    # Analytics dashboard
│   ├── templates_routes.py  # Message templates & sequences
│   └── webhooks.py     # Webhook receivers
├── services/
│   ├── contact_service.py   # WhatsApp/Email/SMS sending
│   ├── sequence_service.py  # Automation sequences
│   ├── analytics_service.py # Analytics calculations
│   └── scoring_service.py   # Lead scoring logic
├── templates/
│   ├── base.html       # Base layout
│   ├── index.html      # Lead list
│   ├── detail.html     # Lead detail
│   ├── auth/           # Login/register pages
│   ├── analytics/      # Analytics dashboard
│   └── templates/      # Template management
└── static/             # CSS/JS files
```

## Lead Scoring

Leads are scored 0-100 based on:
- **Rating**: Higher Google rating = higher score
- **Website**: No website = +15 points (potential client)
- **Engagement**: Each interaction adds points
- **Response Time**: Faster responses = higher score
- **Decay**: Score decreases if lead goes cold

Temperature is automatically assigned:
- **HOT**: Score 70-100
- **WARM**: Score 40-69
- **COLD**: Score 0-39

## Sequences

Create automated outreach campaigns:

1. **Step 1** (Day 0): WhatsApp initial message
2. **Step 2** (Day 3): If no response, send email
3. **Step 3** (Day 7): Final WhatsApp follow-up

Sequences stop automatically when a lead responds.

## Security Features

- **Input Validation**: Comprehensive validation for all user inputs
- **CSRF Protection**: Cross-site request forgery prevention
- **Rate Limiting**: Per-user and per-IP rate limiting
- **Account Lockout**: Automatic lockout after failed login attempts
- **Password Requirements**: Strong password policy enforcement
- **Audit Logging**: Track all user actions for compliance
- **Webhook Signature Verification**: Secure webhook handling

## Utility Modules

The application includes several utility modules for common operations:

- `utils/validators.py` - Input validation utilities
- `utils/error_handlers.py` - Centralized error handling
- `utils/security.py` - Security utilities and decorators
- `utils/db_helpers.py` - Database query optimization
- `utils/helpers.py` - General helper functions
- `utils/cache.py` - Caching utilities
- `utils/audit_logger.py` - Audit logging

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `SECRET_KEY` | Flask secret key | Yes (production) |
| `DATABASE_URL` | Database connection string | No (defaults to SQLite) |
| `TWILIO_ACCOUNT_SID` | Twilio Account SID | For SMS/WhatsApp |
| `TWILIO_AUTH_TOKEN` | Twilio Auth Token | For SMS/WhatsApp |
| `TWILIO_PHONE_NUMBER` | Twilio Phone Number | For SMS |
| `TWILIO_WHATSAPP_NUMBER` | WhatsApp Business Number | For WhatsApp |
| `MAIL_SERVER` | SMTP Server | For Email |
| `MAIL_USERNAME` | SMTP Username | For Email |
| `MAIL_PASSWORD` | SMTP Password | For Email |
| `REDIS_URL` | Redis connection URL | For caching/queues |
| `SENTRY_DSN` | Sentry error tracking | Optional |

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

MIT License
