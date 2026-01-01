#!/bin/bash

# Lead Dashboard Launcher Script
# This script launches the Lead Dashboard application

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}   Lead Dashboard Launcher${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Check if virtual environment exists
if [ ! -d "venv" ] && [ ! -d "env" ]; then
    echo -e "${YELLOW}⚠️  Virtual environment not found. Creating one...${NC}"
    python3 -m venv venv
    echo -e "${GREEN}✅ Virtual environment created${NC}"
fi

# Activate virtual environment
if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d "env" ]; then
    source env/bin/activate
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠️  .env file not found. Creating template...${NC}"
    cat > .env << EOF
# Flask Configuration
FLASK_ENV=development
SECRET_KEY=your-secret-key-change-this-in-production
DEBUG=True

# Database
DATABASE_URL=sqlite:///lead_dashboard/leads.db

# Redis (optional, for background jobs and rate limiting)
# REDIS_URL=redis://localhost:6379/0

# Sentry (optional, for error tracking)
# SENTRY_DSN=your-sentry-dsn-here

# Email Configuration (optional)
# MAIL_SERVER=smtp.gmail.com
# MAIL_PORT=587
# MAIL_USE_TLS=true
# MAIL_USERNAME=your-email@gmail.com
# MAIL_PASSWORD=your-app-password
# MAIL_DEFAULT_SENDER=your-email@gmail.com

# WhatsApp API (optional)
# WHATSAPP_API_URL=https://graph.facebook.com/v18.0
# WHATSAPP_PHONE_ID=your-phone-id
# WHATSAPP_ACCESS_TOKEN=your-access-token
# WHATSAPP_WEBHOOK_TOKEN=your-webhook-token

# Twilio (optional)
# TWILIO_ACCOUNT_SID=your-account-sid
# TWILIO_AUTH_TOKEN=your-auth-token
# TWILIO_PHONE_NUMBER=your-phone-number

# Google Maps API (for lead_finder.py)
# GOOGLE_MAPS_API_KEY=your-api-key
# TELEGRAM_BOT_TOKEN=your-bot-token
# TELEGRAM_CHAT_ID=your-chat-id
EOF
    echo -e "${GREEN}✅ .env template created. Please edit it with your configuration.${NC}"
    echo ""
fi

# Install/update dependencies
echo -e "${YELLOW}📦 Checking dependencies...${NC}"
cd lead_dashboard
pip install -q --upgrade pip
pip install -q -r requirements.txt
cd ..

# Check if Redis is available (optional)
REDIS_AVAILABLE=false
if command -v redis-cli &> /dev/null; then
    if redis-cli ping &> /dev/null; then
        REDIS_AVAILABLE=true
        echo -e "${GREEN}✅ Redis is available${NC}"
    else
        echo -e "${YELLOW}⚠️  Redis is installed but not running${NC}"
    fi
else
    echo -e "${YELLOW}ℹ️  Redis not found (optional - for background jobs)${NC}"
fi

# Check if database needs migration
echo -e "${YELLOW}🗄️  Checking database...${NC}"
cd lead_dashboard
if [ -f "migrations" ] || [ -d "migrations" ]; then
    echo -e "${GREEN}✅ Migrations directory exists${NC}"
else
    echo -e "${YELLOW}⚠️  Initializing database migrations...${NC}"
    flask db init 2>/dev/null || echo "Migrations may already be initialized"
fi

# Run migrations
echo -e "${YELLOW}🔄 Running database migrations...${NC}"
flask db upgrade 2>/dev/null || echo "Database may already be up to date"
cd ..

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}   Starting Lead Dashboard${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Function to cleanup on exit
cleanup() {
    echo ""
    echo -e "${YELLOW}🛑 Shutting down...${NC}"
    kill $FLASK_PID 2>/dev/null || true
    kill $RQ_PID 2>/dev/null || true
    exit 0
}

trap cleanup SIGINT SIGTERM

# Start RQ worker in background if Redis is available
if [ "$REDIS_AVAILABLE" = true ]; then
    echo -e "${GREEN}🚀 Starting background job worker...${NC}"
    cd lead_dashboard
    rq worker default > /tmp/rq-worker.log 2>&1 &
    RQ_PID=$!
    cd ..
    echo -e "${GREEN}✅ Background worker started (PID: $RQ_PID)${NC}"
    echo ""
fi

# Start Flask application
echo -e "${GREEN}🚀 Starting Flask application...${NC}"
echo -e "${YELLOW}   Access the dashboard at: http://localhost:5000${NC}"
echo -e "${YELLOW}   Press Ctrl+C to stop${NC}"
echo ""

cd lead_dashboard
export FLASK_APP=app.py
export FLASK_ENV=${FLASK_ENV:-development}

# Use gunicorn in production, flask run in development
if [ "${FLASK_ENV}" = "production" ]; then
    gunicorn -w 4 -b 0.0.0.0:5000 app:app &
    FLASK_PID=$!
else
    flask run --host=0.0.0.0 --port=5000 &
    FLASK_PID=$!
fi

cd ..

# Wait for Flask to start
sleep 2

# Check if Flask is running
if ps -p $FLASK_PID > /dev/null; then
    echo -e "${GREEN}✅ Flask application started (PID: $FLASK_PID)${NC}"
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}   Lead Dashboard is running!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo -e "🌐 ${GREEN}Dashboard:${NC} http://localhost:5000"
    echo -e "❤️  ${GREEN}Health Check:${NC} http://localhost:5000/health"
    echo ""
    echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}"
    echo ""
    
    # Wait for processes
    wait $FLASK_PID
else
    echo -e "${RED}❌ Failed to start Flask application${NC}"
    exit 1
fi
