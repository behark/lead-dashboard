# Project Overview: Lead Dashboard CRM

## 1. Project Introduction

**Project Path:** `/home/behar/Desktop/lead-dashboard`

This document provides a comprehensive overview of the **Lead Dashboard CRM**, a powerful and feature-rich application designed for managing sales leads and automating outreach. Originally built as an enterprise-grade, multi-user CRM, it has recently been optimized for high-performance personal use, combining robust backend features with a fast, intuitive, and mobile-friendly user interface.

The application serves as a central hub for tracking potential clients (leads), initiating contact through various channels like WhatsApp, Email, and SMS, and analyzing the effectiveness of outreach campaigns. It includes advanced features such as automated multi-step sequences, dynamic lead scoring, and detailed analytics, making it a complete solution for sales and marketing professionals.

## 2. Core Functionality and Use Cases

The primary function of this project is to streamline the entire lead management lifecycle:

- **Lead Generation & Import**: While the application includes scripts to generate leads (e.g., from Google Maps data), it's primarily designed to manage existing lead lists. Leads can be imported from various sources, including CSV files and JSON.
- **Lead Organization**: Leads are stored in a structured database (SQLite by default) and can be filtered, sorted, and searched based on numerous criteria like temperature (Hot, Warm, Cold), status (New, Contacted, Replied, Closed), location, category, and assigned user.
- **Automated & Manual Outreach**: Users can send messages to leads one-by-one or in bulk. The system supports manual messaging as well as fully automated outreach "sequences" that can send a series of messages across different channels over several days.
- **Performance Tracking**: The application provides analytics to measure key metrics such as response rates, conversion rates, and channel performance, helping users optimize their sales strategy.
- **Personal Productivity**: Recent enhancements have introduced a "Quick Dashboard" tailored for single-user productivity, featuring keyboard shortcuts, mobile swipe gestures, and performance optimizations for a "mouse-free" workflow.

## 3. Key Features

The application is packed with features catering to both enterprise and personal use:

### Lead Management
- **Centralized Database**: All leads are stored in an indexed SQLite database for fast access, replacing inefficient flat files like CSVs.
- **Full CRUD Operations**: Create, Read, Update, and Delete leads.
- **Advanced Filtering and Sorting**: Filter leads by temperature, status, category, country, assigned user, or a text-based search. Sort by score, creation date, name, or follow-up date.
- **Bulk Actions**: Assign leads to users, change their status, or enroll them in outreach sequences in bulk.
- **Kanban Board**: A visual, drag-and-drop interface to manage leads by status.

### Contact and Automation
- **Multi-Channel Outreach**:
    - **WhatsApp**: Integrated with the WhatsApp Business API and also supports a "Personal WhatsApp" mode that generates `wa.me` links for sending messages manually.
    - **Email**: Sends emails via SMTP, compatible with services like Gmail.
    - **SMS**: Integrates with Twilio for sending SMS messages.
- **Message Templates**: Create, manage, and A/B test message templates with dynamic placeholders (e.g., `{business_name}`).
- **Outreach Sequences**: Design multi-step, multi-channel automated outreach campaigns. For example: send a WhatsApp message on Day 1, an email on Day 3 if no reply is received, and a final follow-up on Day 7. Sequences automatically stop when a lead responds.
- **Dynamic Lead Scoring**: Leads are automatically scored from 0-100 based on criteria like their Google rating, website presence, engagement with outreach, and response time. This helps prioritize high-potential leads.
- **Lead Temperature and Decay**: Leads are categorized as HOT, WARM, or COLD based on their score. A "temperature decay" system automatically cools down leads that haven't been contacted recently, ensuring focus remains on active prospects.
- **Scheduled Follow-ups**: Manually set or automatically schedule follow-up dates for each lead.

### Analytics and Reporting
- **Analytics Dashboard**: A dedicated dashboard to visualize sales performance.
- **Conversion Funnels**: Track how many leads move from "New" to "Contacted" to "Replied" and finally "Closed".
- **Channel Performance**: Compare the effectiveness of WhatsApp, Email, and SMS channels.
- **A/B Testing**: Analyze the performance of different message template variants to identify which ones get the best response rates.
- **Team Performance**: (In the multi-user version) Track metrics for individual sales representatives.

### Enterprise and SaaS Features
- **Multi-User Authentication**: Support for multiple users with distinct roles (Admin, Manager, Sales).
- **Multi-Tenancy**: The codebase includes models (`models_saas.py`) and routes for multi-tenancy, organization management, and billing, suggesting it can be run as a Software-as-a-Service (SaaS) platform.
- **Billing Integration**: Includes routes and configuration for Stripe integration, allowing for subscription-based access to different pricing tiers.
- **GDPR and Compliance**: Contains routes and templates for GDPR-related pages like cookie policy, privacy policy, and terms of service.
- **Audit Logging**: A system for logging all significant user actions for security and compliance purposes.

### Personal Use Optimizations (Quick Dashboard)
- **High-Performance UI**: A new default dashboard (`quick_dashboard.html`) that is optimized for speed, featuring lazy loading and response caching.
- **Keyboard Shortcuts**: A comprehensive set of keyboard shortcuts allows for a nearly "mouse-free" workflow, including selecting leads, sending messages, and changing status.
- **Mobile Swipe Gestures**: On mobile devices, swipe right on a lead to open WhatsApp and swipe left to skip to the next lead.
- **Inline Editing**: Double-click a lead to open a modal for quick edits without leaving the page.
- **Browser Notifications**: Get desktop notifications for newly added HOT leads.

## 4. Technology Stack

- **Backend**: Python 3 with the **Flask** web framework.
- **Database**: **SQLAlchemy** ORM with a **SQLite** database by default. The configuration allows for other database backends like PostgreSQL. **Flask-Migrate** (using Alembic) is used for database schema migrations.
- **Frontend**: Standard **HTML5**, **CSS3**, and **JavaScript**. Templates are rendered using Flask's default **Jinja2** engine.
- **Authentication**: **Flask-Login** for session-based user authentication.
- **Scheduling**: **Flask-APScheduler** for running background tasks like processing sequences and decaying lead scores.
- **Security**: **Flask-WTF** for CSRF protection, **Flask-Limiter** for rate limiting, and webhook signature verification for secure communication.
- **Caching**: **Flask-Caching** with support for in-memory or Redis-based caching to improve performance.
- **Deployment**: The project includes `Procfile` (for Heroku) and `vercel.json` (for Vercel), indicating it's designed for easy deployment to these platforms.

## 5. Project Structure

The project follows a modular structure that separates concerns, making it maintainable and scalable.

```
/home/behar/Desktop/lead-dashboard/
├── app.py                      # Main Flask application factory and entry point.
├── config.py                   # Configuration settings for different environments (Dev, Prod).
├── models.py                   # Core SQLAlchemy database models (Lead, User, etc.).
├── models_saas.py              # Database models for SaaS features (Organization, Subscription).
├── requirements.txt            # Python package dependencies.
├── api/                        # Vercel serverless function entry point.
├── routes/                     # Flask Blueprints, defining the application's URLs.
│   ├── main.py                 # Core lead management routes.
│   ├── auth.py                 # User authentication (login, registration).
│   ├── analytics.py            # Analytics dashboard routes.
│   ├── webhooks.py             # Webhook handlers for WhatsApp, Twilio, etc.
│   └── ...                     # Other blueprints for billing, team, GDPR, etc.
├── services/                   # Business logic is abstracted into service classes.
│   ├── contact_service.py      # Logic for sending messages (WhatsApp, Email, SMS).
│   ├── scoring_service.py      # Logic for lead scoring and temperature.
│   ├── sequence_service.py     # Logic for managing automated outreach sequences.
│   └── ...
├── templates/                  # Jinja2 HTML templates for the user interface.
│   ├── index.html              # The original, full-featured dashboard.
│   ├── quick_dashboard.html    # The new, optimized personal dashboard.
│   ├── detail.html             # Lead detail page.
│   └── ...
├── static/                     # Static assets.
│   └── js/                     # JavaScript files, including new ones for personal use features.
├── utils/                      # Reusable utility modules.
│   ├── cache.py                # Caching setup.
│   ├── logging_config.py       # Application-wide logging configuration.
│   ├── env_validator.py        # Environment variable validation.
│   └── ...
├── migrations/                 # Alembic database migration scripts.
├── *.py                        # Various standalone utility scripts for one-off tasks.
└── ...
```

## 6. Installation and Setup

1.  **Create a Virtual Environment**:
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```
2.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
3.  **Configure Environment**:
    Copy `.env.example` to `.env` and fill in the necessary API keys and secrets for services like WhatsApp, Twilio, and SMTP.
    ```bash
    cp .env.example .env
    ```
4.  **Initialize the Database**:
    This will create the `leads.db` SQLite file and all the necessary tables.
    ```bash
    flask init-db
    ```
5.  **Create Default Templates**:
    This populates the database with pre-written message templates.
    ```bash
    flask create-default-templates
    ```
6.  **Run the Application**:
    ```bash
    flask run
    ```
7.  **Create an Admin Account**:
    Navigate to `http://127.0.0.1:5000` in your browser and register. The first user to register automatically becomes an admin.

## 7. Configuration

The application is configured through environment variables, defined in the `.env` file. Key variables include:

- `SECRET_KEY`: A secret key for signing session cookies.
- `DATABASE_URL`: The connection string for the database. Defaults to SQLite.
- `WHATSAPP_*`: Credentials for the WhatsApp Business API.
- `MAIL_*`: Credentials for the SMTP email server.
- `TWILIO_*`: Credentials for the Twilio SMS service.
- `REDIS_URL`: URL for a Redis instance, used for caching and job queues in production.
- `STRIPE_*`: API keys for Stripe billing (for the SaaS version).

## 8. Standalone Scripts

The project root contains numerous Python scripts for administrative and data management tasks:

- `init_db.py`: Initializes the database.
- `migrate_data.py`: Migrates data from a legacy CSV file to the database.
- `create_sample_leads.py`: Generates sample lead data for testing.
- `add_column.py`, `add_default_column.py`, `migrate_schema.py`: Various scripts for manual schema migrations.
- `export_new_leads.py`: Exports leads to a file.
- `generate_websites.py`: A script that appears to generate websites for leads, possibly interacting with an AI service.
- `test_api.py`, `test_gooseai.py`, `test_format.py`: Scripts for testing various components and APIs.

This comprehensive set of scripts provides powerful tools for managing the application and its data from the command line.
