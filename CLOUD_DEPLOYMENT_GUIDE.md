# ☁️ Cloud Deployment Guide - Railway.app

**Platform:** Railway.app (Recommended)  
**Alternative:** Render.com, Heroku, DigitalOcean  
**Estimated Time:** 30-60 minutes  
**Cost:** €5-20/month (depending on usage)

---

## 🎯 **WHY RAILWAY.APP?**

✅ **Easiest deployment** - Just connect GitHub  
✅ **Automatic HTTPS** - SSL certificates included  
✅ **PostgreSQL included** - No separate database setup  
✅ **Redis included** - For caching and rate limiting  
✅ **Environment variables** - Easy configuration  
✅ **Free tier available** - €5 credit/month  
✅ **Simple pricing** - Pay for what you use  

---

## 📋 **PRE-DEPLOYMENT CHECKLIST**

### **Before You Start:**
- [ ] Code pushed to GitHub
- [ ] Stripe account created (for payments)
- [ ] Domain name ready (optional)
- [ ] Email service ready (for notifications)

---

## 🚀 **STEP-BY-STEP DEPLOYMENT**

### **Step 1: Create Railway Account** (2 minutes)

1. **Go to:** https://railway.app
2. **Sign up** with GitHub (recommended)
3. **Verify** your email

### **Step 2: Create New Project** (1 minute)

1. **Click:** "New Project"
2. **Select:** "Deploy from GitHub repo"
3. **Choose:** Your repository
4. **Select:** The `lead_dashboard` directory

### **Step 3: Add PostgreSQL Database** (2 minutes)

1. **Click:** "+ New" → "Database" → "PostgreSQL"
2. **Wait** for database to provision
3. **Copy** the connection string (DATABASE_URL)

### **Step 4: Add Redis** (2 minutes)

1. **Click:** "+ New" → "Database" → "Redis"
2. **Wait** for Redis to provision
3. **Copy** the connection string (REDIS_URL)

### **Step 5: Configure Environment Variables** (5 minutes)

**Go to:** Variables tab

**Add these variables:**

```bash
# Flask Configuration
FLASK_ENV=production
SECRET_KEY=your-secret-key-here-generate-with-openssl-rand-hex-32
DEBUG=False

# Database (Auto-set by Railway, but verify)
DATABASE_URL=${{Postgres.DATABASE_URL}}

# Redis (Auto-set by Railway, but verify)
REDIS_URL=${{Redis.REDIS_URL}}

# Stripe (From your Stripe dashboard)
STRIPE_SECRET_KEY=sk_live_...
STRIPE_PUBLISHABLE_KEY=pk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_ID_STARTER_MONTHLY=price_...
STRIPE_PRICE_ID_STARTER_YEARLY=price_...
STRIPE_PRICE_ID_PROFESSIONAL_MONTHLY=price_...
STRIPE_PRICE_ID_PROFESSIONAL_YEARLY=price_...
STRIPE_PRICE_ID_ENTERPRISE_MONTHLY=price_...
STRIPE_PRICE_ID_ENTERPRISE_YEARLY=price_...

# Base URL (Your Railway domain)
BASE_URL=https://your-app-name.up.railway.app

# Twilio (If using WhatsApp/SMS)
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886

# Google Places API (For lead generation)
GOOGLE_PLACES_API_KEY=...

# Telegram (For notifications)
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...

# Email (For SMTP)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password

# Optional
LOG_LEVEL=INFO
RATELIMIT_ENABLED=True
SCHEDULER_API_ENABLED=True
```

**Generate SECRET_KEY:**
```bash
openssl rand -hex 32
```

### **Step 6: Configure Build Settings** (2 minutes)

**Go to:** Settings → Build

**Build Command:**
```bash
pip install -r requirements.txt
```

**Start Command:**
```bash
gunicorn app:app --bind 0.0.0.0:$PORT --workers 2
```

**Or if using waitress (Windows-compatible):**
```bash
waitress-serve --host=0.0.0.0 --port=$PORT app:app
```

### **Step 7: Add Gunicorn to Requirements** (1 minute)

**Add to `requirements.txt`:**
```
gunicorn==21.2.0
```

**Or waitress:**
```
waitress==2.1.2
```

### **Step 8: Update App for Production** (5 minutes)

**Create `Procfile` (optional, Railway auto-detects):**
```
web: gunicorn app:app --bind 0.0.0.0:$PORT --workers 2
```

**Update `app.py` to handle PORT:**
```python
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
```

### **Step 9: Deploy!** (5 minutes)

1. **Railway will automatically:**
   - Detect your Python app
   - Install dependencies
   - Run migrations
   - Start your app

2. **Check logs** for any errors

3. **Visit** your app URL (provided by Railway)

### **Step 10: Run Database Migrations** (2 minutes)

**Option A: Via Railway CLI**
```bash
railway run python migrations/add_multi_tenancy.py
```

**Option B: Via Railway Dashboard**
1. Go to your service
2. Click "Shell"
3. Run: `python migrations/add_multi_tenancy.py`

### **Step 11: Create Admin User** (2 minutes)

**Via Railway Shell:**
```bash
railway run python
```

```python
from app import create_app
from models import db, User
app = create_app()
with app.app_context():
    admin = User(
        username='admin',
        email='admin@yourdomain.com',
        role='admin'
    )
    admin.set_password('your-secure-password')
    db.session.add(admin)
    db.session.commit()
    print('Admin user created!')
```

### **Step 12: Configure Custom Domain** (5 minutes, Optional)

1. **Go to:** Settings → Domains
2. **Click:** "Custom Domain"
3. **Enter:** your domain name
4. **Add DNS records** (Railway will show you)
5. **Wait** for SSL certificate (automatic)

---

## 🔧 **PRODUCTION CONFIGURATION**

### **Update `config.py`:**

```python
class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
    
    # Database
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')
    
    # Redis
    REDIS_URL = os.getenv('REDIS_URL')
    
    # Security
    SECRET_KEY = os.getenv('SECRET_KEY')
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Stripe
    STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY')
    STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_PUBLISHABLE_KEY')
    STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')
    
    # Base URL
    BASE_URL = os.getenv('BASE_URL', 'https://your-app.up.railway.app')
    
    # Rate Limiting
    RATELIMIT_ENABLED = True
    
    # Scheduler
    SCHEDULER_API_ENABLED = True
```

### **Update `app.py`:**

```python
def create_app(config_name=None):
    # Auto-detect environment
    if config_name is None:
        if os.getenv('FLASK_ENV') == 'production':
            config_name = 'production'
        else:
            config_name = 'default'
    
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    # ... rest of your code
```

---

## 📊 **MONITORING & LOGS**

### **View Logs:**
1. **Go to:** Railway Dashboard
2. **Click:** Your service
3. **View:** Real-time logs

### **Set Up Monitoring:**
- **Railway Metrics:** Built-in (CPU, Memory, Network)
- **Error Tracking:** Add Sentry (optional)
- **Uptime Monitoring:** UptimeRobot (free)

---

## 🔒 **SECURITY CHECKLIST**

- [ ] SECRET_KEY is set and strong
- [ ] DEBUG=False in production
- [ ] HTTPS enabled (automatic)
- [ ] Database credentials secure
- [ ] API keys in environment variables
- [ ] Rate limiting enabled
- [ ] CORS configured (if needed)
- [ ] Session security enabled

---

## 🐛 **TROUBLESHOOTING**

### **Issue: App won't start**
- ✅ Check logs in Railway dashboard
- ✅ Verify all environment variables
- ✅ Check requirements.txt is complete
- ✅ Verify PORT is set (Railway auto-sets)

### **Issue: Database connection fails**
- ✅ Check DATABASE_URL is set
- ✅ Verify database is provisioned
- ✅ Check database migrations ran

### **Issue: Static files not loading**
- ✅ Check STATIC_URL in config
- ✅ Verify static folder structure
- ✅ Check BASE_URL is correct

### **Issue: Stripe webhooks not working**
- ✅ Update webhook URL in Stripe dashboard
- ✅ Use Railway domain or custom domain
- ✅ Verify STRIPE_WEBHOOK_SECRET matches

---

## 💰 **COST ESTIMATE**

### **Railway.app Pricing:**

**Free Tier:**
- €5 credit/month
- Good for testing

**Hobby Plan:**
- €5-10/month
- 512MB RAM
- Good for small apps

**Pro Plan:**
- €20+/month
- 1GB+ RAM
- Better performance

**Your Estimated Cost:**
- **Development:** €0-5/month (free tier)
- **Small Business:** €10-20/month
- **Growing Business:** €20-50/month

---

## 🎯 **POST-DEPLOYMENT**

### **Immediate:**
1. ✅ Test all features
2. ✅ Verify Stripe webhooks
3. ✅ Test email sending
4. ✅ Check database migrations
5. ✅ Verify SSL certificate

### **This Week:**
1. ✅ Set up monitoring
2. ✅ Configure backups
3. ✅ Set up error tracking
4. ✅ Test payment flow
5. ✅ Load test

### **This Month:**
1. ✅ Optimize performance
2. ✅ Set up CDN (if needed)
3. ✅ Configure auto-scaling
4. ✅ Set up staging environment

---

## 📚 **ALTERNATIVE PLATFORMS**

### **Render.com:**
- Similar to Railway
- Free tier available
- Easy deployment

### **Heroku:**
- More expensive
- Easy deployment
- Good documentation

### **DigitalOcean App Platform:**
- More control
- Good pricing
- More setup required

### **AWS/DigitalOcean Droplet:**
- Full control
- Cheapest option
- More technical setup

---

## ✅ **DEPLOYMENT CHECKLIST**

- [ ] Railway account created
- [ ] Project created
- [ ] PostgreSQL added
- [ ] Redis added
- [ ] Environment variables set
- [ ] Build command configured
- [ ] App deployed successfully
- [ ] Database migrations run
- [ ] Admin user created
- [ ] Custom domain configured (optional)
- [ ] SSL certificate active
- [ ] All features tested
- [ ] Monitoring set up
- [ ] Backups configured

---

## 🎉 **YOU'RE LIVE!**

**Your app is now:**
- ✅ Accessible worldwide
- ✅ HTTPS secured
- ✅ Auto-scaling
- ✅ Monitored
- ✅ Production-ready

**Next Steps:**
1. Share your app URL
2. Start onboarding customers
3. Monitor usage and performance
4. Scale as needed

---

**Questions?** Check Railway docs: https://docs.railway.app
