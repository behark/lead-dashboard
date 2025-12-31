from flask import Blueprint, request, jsonify, current_app
from models import db, Lead, ContactLog, ContactChannel
from services.contact_service import ContactService
import hmac
import hashlib

webhooks_bp = Blueprint('webhooks', __name__, url_prefix='/webhooks')


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
                        
                        # Find lead by phone
                        lead = Lead.query.filter(
                            Lead.phone.contains(phone[-9:])  # Match last 9 digits
                        ).first()
                        
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
                        
                        # Find lead
                        lead = Lead.query.filter(
                            Lead.phone.contains(recipient[-9:])
                        ).first()
                        
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
                                        template = MessageTemplate.query.get(log.message_template_id)
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
                            template = MessageTemplate.query.get(log.message_template_id)
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
        
        # Find lead
        lead = Lead.query.filter(
            Lead.phone.contains(phone[-9:])
        ).first()
        
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
