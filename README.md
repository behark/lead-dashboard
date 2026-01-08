# Lead Dashboard - Enterprise CRM System

A comprehensive lead management and CRM system with advanced features for sales teams.

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Redis (optional, for background jobs)
- PostgreSQL (optional, SQLite works for development)

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/behark/lead-dashboard.git
   cd lead-dashboard
   ```

2. **Run the launcher script:**
   ```bash
   ./launch.sh
   ```

   The launcher script will:
   - Create a virtual environment (if needed)
   - Install all dependencies
   - Set up database migrations
   - Start the Flask application
   - Start background job worker (if Redis is available)

3. **Access the dashboard:**
   - Open your browser to: http://localhost:5000
   - Health check: http://localhost:5000/health

### Manual Setup

If you prefer manual setup:

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
cd lead_dashboard
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your configuration

# Initialize database
flask db init
flask db migrate -m "Initial migration"
flask db upgrade

# Run the application
flask run
```

## ✨ Features

### 🔒 Security
- **CSRF Protection** - All forms protected
- **Two-Factor Authentication (2FA)** - TOTP-based with backup codes
- **Account Lockout** - Automatic lockout after failed login attempts
- **Password Reset** - Secure email-based password recovery
- **Email Verification** - Verify user email addresses
- **Audit Logging** - Complete action tracking for compliance

### 📊 Management
- **Lead Management** - Comprehensive lead tracking and scoring
- **Bulk Operations** - Send messages to multiple leads
- **Background Jobs** - Non-blocking bulk operations with progress tracking
- **Template Management** - Message templates with A/B testing
- **Sequence Automation** - Automated follow-up sequences
- **Analytics Dashboard** - Real-time analytics and insights

### 🔧 Production Features
- **Health Check Endpoint** - `/health` for monitoring
- **Error Tracking** - Sentry integration for production errors
- **Database Migrations** - Flask-Migrate for schema management
- **Automated Backups** - Daily database backups
- **Rate Limiting** - Per-user API rate limiting
- **Request Logging** - Comprehensive request tracking

### 💳 SaaS Features
- **Multi-tenancy** - Organization-based isolation
- **Stripe Integration** - Payment processing
- **Usage Tracking** - Track API and feature usage
- **Team Collaboration** - Team management and permissions
- **GDPR Compliance** - Data protection and privacy features

## 📁 Project Structure

```
lead-dashboard/
├── lead_dashboard/          # Main application
│   ├── app.py              # Flask application
│   ├── models.py           # Database models
│   ├── routes/             # Route handlers
│   ├── services/           # Business logic
│   ├── utils/              # Utilities
│   ├── jobs/               # Background jobs
│   ├── templates/          # Jinja2 templates
│   └── static/             # Static files
├── lead_finder.py          # Lead finder script
├── launch.sh               # Launcher script
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

## 🔧 Configuration

### Environment Variables

Create a `.env` file in the project root:

```bash
# Flask
FLASK_ENV=development
SECRET_KEY=your-secret-key-here
DEBUG=True

# Database
DATABASE_URL=sqlite:///lead_dashboard/leads.db
# Or for PostgreSQL:
# DATABASE_URL=postgresql://user:pass@localhost/dbname

# Redis (optional)
REDIS_URL=redis://localhost:6379/0

# Sentry (optional)
SENTRY_DSN=your-sentry-dsn

# Email (optional)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
```

See `.env.example` for all available options.

## 🛠️ Development

### Running Tests
```bash
cd lead_dashboard
pytest
```

### Database Migrations
```bash
# Create migration
flask db migrate -m "Description"

# Apply migration
flask db upgrade

# Rollback migration
flask db downgrade
```

### Background Jobs

Start the RQ worker:
```bash
cd lead_dashboard
rq worker default
```

## 📚 Documentation

- [API Documentation](API_DOCUMENTATION.md)
- [Setup Guide](STRIPE_SETUP_GUIDE.md)
- [Cloud Deployment](CLOUD_DEPLOYMENT_GUIDE.md)

## 🔐 Security Notes

- **Never commit `.env` file** - It contains sensitive information
- **Use strong SECRET_KEY** in production
- **Enable 2FA** for admin accounts
- **Use HTTPS** in production
- **Regular backups** are automated but verify they work

## 📝 License

[Your License Here]

## 🤝 Contributing

[Contributing Guidelines]

## 📧 Support

[Support Information]

---

**Built with ❤️ using Flask, SQLAlchemy, and modern web technologies**
