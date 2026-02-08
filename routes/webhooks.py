from flask import Blueprint, request, jsonify, current_app
from models import db, Lead, ContactLog, ContactChannel
from services.contact_service import ContactService
import hmac
import hashlib
import logging

logger = logging.getLogger(__name__)
webhooks_bp = Blueprint('webhooks', __name__, url_prefix='/webhooks')


def normalize_phone(phone):
    """Normalize phone number to digits only, with country code"""
    if not phone:
        return None
    # Remove all non-digit characters
    digits = ''.join(c for c in phone if c.isdigit())
    # Ensure Kosovo country code
    if digits.startswith('383'):
        return digits
    elif digits.startswith('0') and len(digits) >= 9:
        return '383' + digits[1:]
    elif len(digits) == 9:
        return '383' + digits
    return digits


def find_lead_by_phone(phone):
    """Find lead by phone number with proper matching"""
    if not phone:
        return None

    normalized = normalize_phone(phone)
    if not normalized:
        return None

    # Try exact match first (most reliable)
    leads = Lead.query.filter(Lead.phone.isnot(None)).all()

    for lead in leads:
        lead_normalized = normalize_phone(lead.phone)
        if lead_normalized and lead_normalized == normalized:
            return lead

    # Fallback: match if one contains the other (for partial matches)
    # But require at least 9 matching digits
    if len(normalized) >= 9:
        suffix = normalized[-9:]
        for lead in leads:
            lead_normalized = normalize_phone(lead.phone)
            if lead_normalized and suffix in lead_normalized:
                return lead

    return None


@webhooks_bp.route('/whatsapp', methods=['GET', 'POST'])
def whatsapp_webhook():
    """Handle WhatsApp Business API webhooks"""
    
    if request.method == 'GET':
        # Webhook verification
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        
        if mode == 'subscribe' and token == current_app.config.get('WHATSAPP_WEBHOOK_TOKEN'):
            return challenge, 200
        return 'Forbidden', 403
    
    # Handle incoming message
    try:
        data = request.get_json()
        
        if data.get('object') == 'whatsapp_business_account':
            for entry in data.get('entry', []):
                for change in entry.get('changes', []):
                    value = change.get('value', {})
                    
                    # Handle messages
                    for message in value.get('messages', []):
                        phone = message.get('from')
                        text = message.get('text', {}).get('body', '')
                        
                        # Find lead by phone (using secure matching)
                        lead = find_lead_by_phone(phone)
                        
                        if lead:
                            ContactService.record_response(
                                lead,
                                ContactChannel.WHATSAPP,
                                text
                            )
                    
                    # Handle status updates
                    for status in value.get('statuses', []):
                        message_status = status.get('status')
                        recipient = status.get('recipient_id')
                        
                        # Find lead (using secure matching)
                        lead = find_lead_by_phone(recipient)
                        
                        if lead:
                            log = ContactLog.query.filter_by(
                                lead_id=lead.id,
                                channel=ContactChannel.WHATSAPP
                            ).order_by(ContactLog.sent_at.desc()).first()
                            
                            if log:
                                from datetime import datetime, timezone
                                if message_status == 'delivered':
                                    log.delivered_at = datetime.now(timezone.utc)
                                elif message_status == 'read':
                                    log.read_at = datetime.now(timezone.utc)
                                    # Update template open stats
                                    if log.message_template_id:
                                        from models import MessageTemplate
                                        template = db.session.get(MessageTemplate, log.message_template_id)
                                        if template:
                                            template.times_opened += 1
                                
                                db.session.commit()
        
        return jsonify({'status': 'ok'}), 200
    
    except Exception as e:
        current_app.logger.error(f"WhatsApp webhook error: {e}")
        return jsonify({'error': str(e)}), 500


@webhooks_bp.route('/email/mailgun', methods=['POST'])
def mailgun_webhook():
    """Handle Mailgun email webhooks (replies, opens, etc.)"""
    
    try:
        # Verify signature (if using signed webhooks)
        # token = request.form.get('token')
        # timestamp = request.form.get('timestamp')
        # signature = request.form.get('signature')
        
        event = request.form.get('event')
        recipient = request.form.get('recipient')
        
        if event in ['opened', 'clicked', 'delivered', 'complained', 'unsubscribed']:
            lead = Lead.query.filter_by(email=recipient).first()
            
            if lead:
                log = ContactLog.query.filter_by(
                    lead_id=lead.id,
                    channel=ContactChannel.EMAIL
                ).order_by(ContactLog.sent_at.desc()).first()
                
                if log:
                    from datetime import datetime, timezone
                    if event == 'delivered':
                        log.delivered_at = datetime.now(timezone.utc)
                    elif event == 'opened':
                        log.read_at = datetime.now(timezone.utc)
                        if log.message_template_id:
                            from models import MessageTemplate
                            template = db.session.get(MessageTemplate, log.message_template_id)
                            if template:
                                template.times_opened += 1
                    
                    db.session.commit()
        
        return jsonify({'status': 'ok'}), 200
    
    except Exception as e:
        current_app.logger.error(f"Mailgun webhook error: {e}")
        return jsonify({'error': str(e)}), 500


@webhooks_bp.route('/sms/twilio', methods=['POST'])
def twilio_webhook():
    """Handle Twilio SMS webhooks (replies)"""
    
    try:
        from_number = request.form.get('From', '')
        body = request.form.get('Body', '')
        
        # Clean phone number
        phone = from_number.replace('+', '').replace(' ', '')

        # Find lead (using secure matching)
        lead = find_lead_by_phone(phone)
        
        if lead:
            ContactService.record_response(
                lead,
                ContactChannel.SMS,
                body
            )
        
        # Twilio expects TwiML response
        return '<?xml version="1.0" encoding="UTF-8"?><Response></Response>', 200, {
            'Content-Type': 'text/xml'
        }
    
    except Exception as e:
        current_app.logger.error(f"Twilio webhook error: {e}")
        return '<?xml version="1.0" encoding="UTF-8"?><Response></Response>', 200, {
            'Content-Type': 'text/xml'
        }


@webhooks_bp.route('/twilio/status', methods=['POST'])
def twilio_status_webhook():
    """
    Enhanced webhook for Twilio message status updates with comprehensive delivery tracking
    """
    try:
        from datetime import datetime, timezone
        from twilio.request_validator import RequestValidator
        from sqlalchemy.exc import SQLAlchemyError
        
        # Get status information
        message_sid = request.form.get('MessageSid', '')
        message_status = request.form.get('MessageStatus', '')
        to_number = request.form.get('To', '')
        from_number = request.form.get('From', '')
        error_code = request.form.get('ErrorCode', '')
        error_message = request.form.get('ErrorMessage', '')
        
        current_app.logger.info(f"Twilio status webhook: SID={message_sid}, Status={message_status}, ErrorCode={error_code}")

        # Verify webhook signature for security (if auth token is configured)
        twilio_auth_token = current_app.config.get('TWILIO_AUTH_TOKEN')
        if twilio_auth_token:
            validator = RequestValidator(twilio_auth_token)
            signature = request.headers.get('X-Twilio-Signature', '')
            if not validator.validate(request.url, request.form, signature):
                current_app.logger.warning("Invalid Twilio webhook signature - possible spoofing attempt")
                return jsonify({'error': 'Invalid signature'}), 403

        if not message_sid:
            return jsonify({'error': 'Missing MessageSid'}), 400
        
        # Find the contact log by Twilio message SID
        log = ContactLog.query.filter_by(twilio_message_sid=message_sid).first()
        
        if not log:
            current_app.logger.warning(f"No contact log found for Twilio SID: {message_sid}")
            return jsonify({'status': 'ok', 'message': 'Log not found'}), 200
        
        # Update status based on Twilio status
        now = datetime.now(timezone.utc)
        status_updated = False
        
        # Twilio status values: queued, sending, sent, delivered, undelivered, failed, received, read
        if message_status == 'delivered':
            if not log.delivered_at:  # Only set if not already set
                log.delivered_at = now
                status_updated = True
                current_app.logger.info(f"Message {message_sid} delivered to lead {log.lead_id}")
                
                # Update lead status if this is the first delivered message
                lead = db.session.get(Lead, log.lead_id)
                if lead and lead.status == 'CONTACTED':
                    lead.status = 'DELIVERED'
                    
        elif message_status == 'read':
            if not log.read_at:  # Only set if not already set
                log.read_at = now
                status_updated = True
                
                # Update template stats for open tracking
                if log.message_template_id:
                    template = db.session.get(MessageTemplate, log.message_template_id)
                    if template:
                        template.times_opened += 1
                        
                current_app.logger.info(f"Message {message_sid} read by lead {log.lead_id}")
                
        elif message_status in ['failed', 'undelivered']:
            # Log detailed failure information
            failure_info = {
                'status': message_status,
                'error_code': error_code,
                'error_message': error_message,
                'timestamp': now.isoformat()
            }
            
            # Store failure info in log metadata (if you add a metadata JSON field)
            log.status = message_status
            status_updated = True
            
            current_app.logger.warning(f"Message {message_sid} {message_status}: {error_message} (Code: {error_code})")
            
            # Could trigger retry logic here for specific error codes
            
        elif message_status in ['queued', 'sending', 'sent']:
            # Update intermediate status
            log.status = message_status
            status_updated = True
            current_app.logger.debug(f"Message {message_sid} status updated to {message_status}")
        
        # Commit status updates
        if status_updated:
            try:
                db.session.commit()
                current_app.logger.info(f"Updated message {message_sid} status to {message_status}")
            except SQLAlchemyError as e:
                current_app.logger.error(f"Database error updating message status: {e}")
                db.session.rollback()
        
        return jsonify({'status': 'ok', 'message': f'Status updated to {message_status}'}), 200
        
    except Exception as e:
        current_app.logger.exception(f"Error processing Twilio webhook: {e}")
        return jsonify({'error': 'Internal server error'}), 500
