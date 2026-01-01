# 💳 Stripe Payment Integration - Setup Guide

**Status:** ✅ Code Complete - Needs Stripe Account Configuration  
**Time to Setup:** 15-30 minutes

---

## 🎉 **WHAT WAS IMPLEMENTED**

### **✅ Complete Stripe Integration:**
1. ✅ Stripe Service (`services/stripe_service.py`)
   - Customer creation
   - Checkout sessions
   - Customer portal
   - Webhook handling
   - Subscription management

2. ✅ Billing Routes (`routes/billing.py`)
   - Billing dashboard
   - Pricing page
   - Checkout flow
   - Webhook endpoint
   - Subscription management

3. ✅ Billing Templates
   - Dashboard with usage stats
   - Pricing page with all plans
   - Invoice history

---

## 📋 **SETUP STEPS**

### **Step 1: Create Stripe Account** (5 minutes)

1. **Go to:** https://stripe.com
2. **Sign up** for a free account
3. **Complete** business verification
4. **Get your API keys:**
   - Go to: Developers → API keys
   - Copy your **Publishable key** (starts with `pk_`)
   - Copy your **Secret key** (starts with `sk_`)

### **Step 2: Create Products & Prices** (10 minutes)

1. **Go to:** Products → Add Product

2. **Create 4 Products:**

   **A. STARTER Plan (Monthly)**
   ```
   Name: Starter Plan (Monthly)
   Description: 500 leads/month, 3 users
   Pricing: €49.00 EUR, Recurring monthly
   ```
   - Copy the **Price ID** (starts with `price_`)

   **B. STARTER Plan (Yearly)**
   ```
   Name: Starter Plan (Yearly)
   Description: 500 leads/month, 3 users
   Pricing: €490.00 EUR, Recurring yearly
   ```
   - Copy the **Price ID**

   **C. PROFESSIONAL Plan (Monthly)**
   ```
   Name: Professional Plan (Monthly)
   Description: 5,000 leads/month, 10 users
   Pricing: €149.00 EUR, Recurring monthly
   ```
   - Copy the **Price ID**

   **D. PROFESSIONAL Plan (Yearly)**
   ```
   Name: Professional Plan (Yearly)
   Description: 5,000 leads/month, 10 users
   Pricing: €1,490.00 EUR, Recurring yearly
   ```
   - Copy the **Price ID**

   **E. ENTERPRISE Plan (Monthly)**
   ```
   Name: Enterprise Plan (Monthly)
   Description: Unlimited everything
   Pricing: €499.00 EUR, Recurring monthly
   ```
   - Copy the **Price ID**

   **F. ENTERPRISE Plan (Yearly)**
   ```
   Name: Enterprise Plan (Yearly)
   Description: Unlimited everything
   Pricing: €4,990.00 EUR, Recurring yearly
   ```
   - Copy the **Price ID**

### **Step 3: Configure Webhook** (5 minutes)

1. **Go to:** Developers → Webhooks
2. **Click:** "Add endpoint"
3. **Endpoint URL:** `https://yourdomain.com/billing/webhook`
   - For local testing: Use Stripe CLI (see below)
4. **Events to listen for:**
   - `checkout.session.completed`
   - `customer.subscription.created`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.paid`
   - `invoice.payment_failed`
5. **Copy the webhook signing secret** (starts with `whsec_`)

### **Step 4: Add to Environment Variables** (2 minutes)

Add these to your `.env` file:

```bash
# Stripe Configuration
STRIPE_SECRET_KEY=sk_test_...  # Your secret key
STRIPE_PUBLISHABLE_KEY=pk_test_...  # Your publishable key (for frontend)
STRIPE_WEBHOOK_SECRET=whsec_...  # Webhook signing secret

# Stripe Price IDs (from Step 2)
STRIPE_PRICE_ID_STARTER_MONTHLY=price_...
STRIPE_PRICE_ID_STARTER_YEARLY=price_...
STRIPE_PRICE_ID_PROFESSIONAL_MONTHLY=price_...
STRIPE_PRICE_ID_PROFESSIONAL_YEARLY=price_...
STRIPE_PRICE_ID_ENTERPRISE_MONTHLY=price_...
STRIPE_PRICE_ID_ENTERPRISE_YEARLY=price_...

# Base URL (for redirects)
BASE_URL=http://localhost:5000  # Change to your domain in production
```

### **Step 5: Update Config** (2 minutes)

Add to `config.py`:

```python
# Stripe Configuration
STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY')
STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_PUBLISHABLE_KEY')
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')

# Stripe Price IDs
STRIPE_PRICE_ID_STARTER_MONTHLY = os.getenv('STRIPE_PRICE_ID_STARTER_MONTHLY')
STRIPE_PRICE_ID_STARTER_YEARLY = os.getenv('STRIPE_PRICE_ID_STARTER_YEARLY')
STRIPE_PRICE_ID_PROFESSIONAL_MONTHLY = os.getenv('STRIPE_PRICE_ID_PROFESSIONAL_MONTHLY')
STRIPE_PRICE_ID_PROFESSIONAL_YEARLY = os.getenv('STRIPE_PRICE_ID_PROFESSIONAL_YEARLY')
STRIPE_PRICE_ID_ENTERPRISE_MONTHLY = os.getenv('STRIPE_PRICE_ID_ENTERPRISE_MONTHLY')
STRIPE_PRICE_ID_ENTERPRISE_YEARLY = os.getenv('STRIPE_PRICE_ID_ENTERPRISE_YEARLY')

# Base URL
BASE_URL = os.getenv('BASE_URL', 'http://localhost:5000')
```

---

## 🧪 **TESTING (Local Development)**

### **Option 1: Stripe CLI** (Recommended)

1. **Install Stripe CLI:**
   ```bash
   # macOS
   brew install stripe/stripe-cli/stripe
   
   # Linux
   wget https://github.com/stripe/stripe-cli/releases/download/v1.15.0/stripe_1.15.0_linux_x86_64.tar.gz
   tar -xvf stripe_1.15.0_linux_x86_64.tar.gz
   sudo mv stripe /usr/local/bin/
   ```

2. **Login:**
   ```bash
   stripe login
   ```

3. **Forward webhooks to local server:**
   ```bash
   stripe listen --forward-to localhost:5000/billing/webhook
   ```
   
   This will give you a webhook secret starting with `whsec_` - use this in your `.env`

4. **Test payments:**
   - Use test card: `4242 4242 4242 4242`
   - Any future expiry date
   - Any CVC
   - Any ZIP

### **Option 2: ngrok** (Alternative)

1. **Install ngrok:**
   ```bash
   # Download from https://ngrok.com
   ```

2. **Start tunnel:**
   ```bash
   ngrok http 5000
   ```

3. **Use the HTTPS URL** in Stripe webhook configuration:
   ```
   https://xxxx.ngrok.io/billing/webhook
   ```

---

## ✅ **VERIFICATION CHECKLIST**

- [ ] Stripe account created
- [ ] API keys obtained (secret + publishable)
- [ ] 6 products created (3 plans × 2 billing cycles)
- [ ] 6 price IDs copied
- [ ] Webhook endpoint configured
- [ ] Webhook secret copied
- [ ] Environment variables set
- [ ] Config file updated
- [ ] Server restarted
- [ ] Test checkout works
- [ ] Test webhook received

---

## 🚀 **USAGE**

### **For Users:**

1. **View Plans:**
   ```
   Visit: /billing/plans
   ```

2. **Subscribe:**
   ```
   Click "Subscribe Now" on any plan
   → Redirected to Stripe Checkout
   → Enter payment details
   → Redirected back to dashboard
   ```

3. **Manage Subscription:**
   ```
   Visit: /billing
   → Click "Manage Subscription"
   → Redirected to Stripe Customer Portal
   → Can update payment method, cancel, etc.
   ```

### **For Developers:**

**Check subscription status:**
```python
from models_saas import Organization
org = Organization.query.first()
print(f"Plan: {org.subscription.plan.value}")
print(f"Status: {org.subscription.status.value}")
print(f"Stripe Customer: {org.subscription.stripe_customer_id}")
```

**Create checkout:**
```python
from services.stripe_service import StripeService
from models_saas import SubscriptionPlan

session = StripeService.create_checkout_session(
    organization=org,
    plan=SubscriptionPlan.PROFESSIONAL,
    billing_cycle='monthly'
)
print(f"Checkout URL: {session.url}")
```

---

## 🐛 **TROUBLESHOOTING**

### **Issue: "Stripe not configured"**
- ✅ Check `STRIPE_SECRET_KEY` is set in `.env`
- ✅ Restart server after adding env vars

### **Issue: "Price ID not found"**
- ✅ Check all 6 price IDs are set in `.env`
- ✅ Verify price IDs match your Stripe dashboard

### **Issue: Webhooks not working**
- ✅ Check webhook secret is correct
- ✅ Verify webhook endpoint URL is accessible
- ✅ Check Stripe dashboard for webhook delivery logs
- ✅ Use Stripe CLI for local testing

### **Issue: Checkout redirects to error**
- ✅ Check `BASE_URL` is set correctly
- ✅ Verify success/cancel URLs are accessible
- ✅ Check Stripe logs in dashboard

---

## 📊 **TEST CARDS**

**Success:**
- `4242 4242 4242 4242` - Visa
- `5555 5555 5555 4444` - Mastercard

**Decline:**
- `4000 0000 0000 0002` - Card declined
- `4000 0000 0000 9995` - Insufficient funds

**3D Secure:**
- `4000 0025 0000 3155` - Requires authentication

---

## 🎉 **YOU'RE READY!**

Once configured, you can:
- ✅ Accept payments
- ✅ Manage subscriptions
- ✅ Handle upgrades/downgrades
- ✅ Generate invoices
- ✅ Process refunds (via Stripe dashboard)

**Next Steps:**
1. Complete Stripe setup (15-30 min)
2. Test with test cards
3. Go live with real payments!

---

**Questions?** Check Stripe docs: https://stripe.com/docs
