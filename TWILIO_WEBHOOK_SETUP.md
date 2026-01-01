# 📡 Twilio Webhook Setup Guide

## ✅ What's Been Implemented

1. **Twilio Status Webhook Handler** (`/webhooks/twilio/status`)
   - Tracks message delivery status (delivered, read, failed)
   - Updates `delivered_at` and `read_at` timestamps
   - Stores Twilio message SID for tracking

2. **Database Updates**
   - Added `twilio_message_sid` column to `contact_logs` table
   - Added `external_message_id` column for future use
   - Indexed for fast lookups

3. **Contact Service Updates**
   - Stores Twilio message SID when sending messages
   - Removed premature `delivered_at` setting (now waits for webhook)

## 🔧 Setup Instructions

### Step 1: Run Database Migration

The new columns need to be added to your database. In serverless (Vercel), this happens automatically on first use, but for local development:

```bash
python migrations/add_twilio_sid.py
```

### Step 2: Configure Twilio Webhook URL

1. **Go to Twilio Console:**
   - https://www.twilio.com/console

2. **Navigate to Messaging → Settings → WhatsApp Sandbox** (or your WhatsApp number)

3. **Set Status Callback URL:**
   ```
   https://leaddashboard.vercel.app/webhooks/twilio/status
   ```

4. **For Production WhatsApp Number:**
   - Go to Phone Numbers → Manage → Active Numbers
   - Click on your WhatsApp-enabled number
   - Under "Messaging Configuration", set:
     - **Status Callback URL:** `https://leaddashboard.vercel.app/webhooks/twilio/status`
     - **Status Callback Method:** POST

### Step 3: Verify Environment Variables (Already Done ✅)

Your Vercel environment variables are configured:
- ✅ `TWILIO_ACCOUNT_SID`
- ✅ `TWILIO_AUTH_TOKEN`
- ✅ `TWILIO_WHATSAPP_NUMBER`

### Step 4: Test the Webhook

1. Send a test message via bulk send
2. Check Vercel logs:
   ```bash
   vercel logs leaddashboard.vercel.app
   ```
3. Look for: `"Twilio status webhook: SID=..., Status=..."`

## 📊 How It Works

### Message Flow:

```
1. User sends message via bulk send
   ↓
2. ContactService.send_whatsapp() called
   ↓
3. Twilio API receives message
   ↓
4. Twilio returns message SID
   ↓
5. ContactLog created with twilio_message_sid stored
   ↓
6. Twilio sends status updates to webhook:
   - "sent" → Message accepted by Twilio
   - "delivered" → Message delivered to recipient
   - "read" → Recipient read the message
   ↓
7. Webhook updates ContactLog:
   - delivered_at (when status = "delivered")
   - read_at (when status = "read")
```

### Status Values:

- **queued** - Message is queued for delivery
- **sending** - Message is being sent
- **sent** - Message sent to Twilio (not yet delivered)
- **delivered** - Message delivered to recipient's device ✅
- **undelivered** - Message failed to deliver
- **failed** - Message failed to send
- **received** - Message received (for incoming)
- **read** - Message was read by recipient ✅

## 🔍 Checking Delivery Status

### In the Dashboard:

1. Go to a lead's detail page
2. Check "Contact History" tab
3. Look for:
   - ✅ **Delivered** timestamp (when message reached device)
   - 👁️ **Read** timestamp (when recipient opened message)

### Via API:

```python
# Get contact log with delivery status
log = ContactLog.query.filter_by(twilio_message_sid='SM...').first()
if log.delivered_at:
    print(f"Delivered at: {log.delivered_at}")
if log.read_at:
    print(f"Read at: {log.read_at}")
```

## 🛡️ Security (Optional)

To verify webhook authenticity, uncomment the signature validation in `routes/webhooks.py`:

```python
from twilio.request_validator import RequestValidator

validator = RequestValidator(current_app.config.get('TWILIO_AUTH_TOKEN'))
if not validator.validate(request.url, request.form, request.headers.get('X-Twilio-Signature', '')):
    return jsonify({'error': 'Invalid signature'}), 403
```

## 🐛 Troubleshooting

### Webhook Not Receiving Updates:

1. **Check Twilio Console:**
   - Go to Monitor → Logs → Messaging
   - Look for webhook delivery attempts
   - Check for errors (404, 500, etc.)

2. **Check Vercel Logs:**
   ```bash
   vercel logs leaddashboard.vercel.app | grep twilio
   ```

3. **Verify URL:**
   - Make sure webhook URL is publicly accessible
   - Test with: `curl https://leaddashboard.vercel.app/webhooks/twilio/status`

### Messages Show as "Sent" but Not "Delivered":

- **Wait a few seconds** - Delivery status comes via webhook (not instant)
- **Check Twilio logs** - See if webhook was called
- **Verify webhook URL** - Must be set correctly in Twilio console
- **Check recipient number** - Must be valid and WhatsApp-enabled

### Database Migration Issues:

If columns don't exist, run:
```bash
python migrations/add_twilio_sid.py
```

Or manually in SQLite:
```sql
ALTER TABLE contact_logs ADD COLUMN twilio_message_sid VARCHAR(50);
CREATE INDEX ix_contact_logs_twilio_message_sid ON contact_logs(twilio_message_sid);
ALTER TABLE contact_logs ADD COLUMN external_message_id VARCHAR(100);
```

## 📝 Current Status

✅ **Implemented:**
- Webhook handler for status updates
- Database columns for tracking
- Message SID storage

⏳ **Next Steps:**
1. Configure webhook URL in Twilio console
2. Test with a real message
3. Verify delivery status updates appear

## 🔗 Resources

- [Twilio Status Callbacks](https://www.twilio.com/docs/messaging/guides/webhook-request-objects#status-callback)
- [Twilio WhatsApp API](https://www.twilio.com/docs/whatsapp)
- [Webhook Security](https://www.twilio.com/docs/usage/webhooks/webhooks-security)
