# Lead Dashboard CRM

A comprehensive lead management system with multi-channel outreach, automated sequences, and analytics.

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

## License

MIT License
