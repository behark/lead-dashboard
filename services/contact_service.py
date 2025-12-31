import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone
from flask import current_app
from models import db, Lead, ContactLog, MessageTemplate, ContactChannel, LeadStatus
import re


class ContactService:
    """Unified service for contacting leads across multiple channels"""
    
    @staticmethod
    def personalize_message(template_content, lead):
        """Replace placeholders in message template with lead data"""
        replacements = {
            '{name}': lead.name or '',
            '{business_name}': lead.name or '',
            '{city}': lead.city or '',
            '{rating}': str(lead.rating) if lead.rating else '',
            '{category}': lead.category or '',
        }
        
        message = template_content
        for placeholder, value in replacements.items():
            message = message.replace(placeholder, value)
        
        return message
    
    @staticmethod
    def send_whatsapp(lead, message, template_id=None, user_id=None, is_automated=False, ab_variant=None):
        """Send WhatsApp message via Meta Business API"""
        
        if not current_app.config.get('WHATSAPP_ACCESS_TOKEN'):
            return {'success': False, 'error': 'WhatsApp API not configured'}
        
        phone = lead.phone
        if not phone:
            return {'success': False, 'error': 'No phone number'}
        
        # Clean phone number
        phone = re.sub(r'[^\d+]', '', phone)
        if not phone.startswith('+'):
            phone = '+383' + phone.lstrip('0')
        
        api_url = f"{current_app.config['WHATSAPP_API_URL']}/{current_app.config['WHATSAPP_PHONE_ID']}/messages"
        
        headers = {
            'Authorization': f"Bearer {current_app.config['WHATSAPP_ACCESS_TOKEN']}",
            'Content-Type': 'application/json'
        }
        
        payload = {
            'messaging_product': 'whatsapp',
            'to': phone.replace('+', ''),
            'type': 'text',
            'text': {'body': message}
        }
        
        try:
            response = requests.post(api_url, headers=headers, json=payload, timeout=30)
            success = response.status_code == 200
            
            # Log the contact
            log = ContactLog(
                lead_id=lead.id,
                user_id=user_id,
                channel=ContactChannel.WHATSAPP,
                message_template_id=template_id,
                message_content=message,
                is_automated=is_automated,
                ab_variant=ab_variant
            )
            
            if success:
                log.delivered_at = datetime.now(timezone.utc)
                lead.last_contacted = datetime.now(timezone.utc)
                if lead.status == LeadStatus.NEW:
                    lead.status = LeadStatus.CONTACTED
                
                # Update template stats
                if template_id:
                    template = MessageTemplate.query.get(template_id)
                    if template:
                        template.times_sent += 1
            
            db.session.add(log)
            db.session.commit()
            
            return {
                'success': success,
                'message_id': response.json().get('messages', [{}])[0].get('id') if success else None,
                'error': response.json().get('error', {}).get('message') if not success else None
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def send_email(lead, subject, message, template_id=None, user_id=None, is_automated=False, ab_variant=None):
        """Send email via SMTP"""
        
        if not current_app.config.get('MAIL_USERNAME'):
            return {'success': False, 'error': 'Email not configured'}
        
        if not lead.email:
            return {'success': False, 'error': 'No email address'}
        
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = current_app.config['MAIL_DEFAULT_SENDER']
            msg['To'] = lead.email
            
            # Plain text
            text_part = MIMEText(message, 'plain', 'utf-8')
            msg.attach(text_part)
            
            # HTML version
            html_message = message.replace('\n', '<br>')
            html_part = MIMEText(f"<html><body>{html_message}</body></html>", 'html', 'utf-8')
            msg.attach(html_part)
            
            with smtplib.SMTP(current_app.config['MAIL_SERVER'], current_app.config['MAIL_PORT']) as server:
                if current_app.config['MAIL_USE_TLS']:
                    server.starttls()
                server.login(current_app.config['MAIL_USERNAME'], current_app.config['MAIL_PASSWORD'])
                server.sendmail(msg['From'], [lead.email], msg.as_string())
            
            # Log the contact
            log = ContactLog(
                lead_id=lead.id,
                user_id=user_id,
                channel=ContactChannel.EMAIL,
                message_template_id=template_id,
                message_content=message,
                delivered_at=datetime.now(timezone.utc),
                is_automated=is_automated,
                ab_variant=ab_variant
            )
            
            lead.last_contacted = datetime.now(timezone.utc)
            if lead.status == LeadStatus.NEW:
                lead.status = LeadStatus.CONTACTED
            
            if template_id:
                template = MessageTemplate.query.get(template_id)
                if template:
                    template.times_sent += 1
            
            db.session.add(log)
            db.session.commit()
            
            return {'success': True}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def send_sms(lead, message, template_id=None, user_id=None, is_automated=False, ab_variant=None):
        """Send SMS via Twilio"""
        
        if not current_app.config.get('TWILIO_ACCOUNT_SID'):
            return {'success': False, 'error': 'SMS not configured'}
        
        phone = lead.phone
        if not phone:
            return {'success': False, 'error': 'No phone number'}
        
        # Clean phone number
        phone = re.sub(r'[^\d+]', '', phone)
        if not phone.startswith('+'):
            phone = '+383' + phone.lstrip('0')
        
        try:
            from twilio.rest import Client
            
            client = Client(
                current_app.config['TWILIO_ACCOUNT_SID'],
                current_app.config['TWILIO_AUTH_TOKEN']
            )
            
            tw_message = client.messages.create(
                body=message,
                from_=current_app.config['TWILIO_PHONE_NUMBER'],
                to=phone
            )
            
            # Log the contact
            log = ContactLog(
                lead_id=lead.id,
                user_id=user_id,
                channel=ContactChannel.SMS,
                message_template_id=template_id,
                message_content=message,
                delivered_at=datetime.now(timezone.utc),
                is_automated=is_automated,
                ab_variant=ab_variant
            )
            
            lead.last_contacted = datetime.now(timezone.utc)
            if lead.status == LeadStatus.NEW:
                lead.status = LeadStatus.CONTACTED
            
            if template_id:
                template = MessageTemplate.query.get(template_id)
                if template:
                    template.times_sent += 1
            
            db.session.add(log)
            db.session.commit()
            
            return {'success': True, 'message_sid': tw_message.sid}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def record_response(lead, channel, response_content=None):
        """Record a response from a lead"""
        
        # Find the last contact log for this lead and channel
        log = ContactLog.query.filter_by(
            lead_id=lead.id,
            channel=channel
        ).order_by(ContactLog.sent_at.desc()).first()
        
        if log:
            log.responded_at = datetime.now(timezone.utc)
            log.response_content = response_content
            
            # Update template stats
            if log.message_template_id:
                template = MessageTemplate.query.get(log.message_template_id)
                if template:
                    template.times_responded += 1
        
        # Update lead
        lead.last_response = datetime.now(timezone.utc)
        lead.status = LeadStatus.REPLIED
        lead.engagement_count = (lead.engagement_count or 0) + 1
        
        # Calculate response time
        if lead.last_contacted:
            diff = datetime.now(timezone.utc) - lead.last_contacted
            lead.response_time_hours = diff.total_seconds() / 3600
        
        lead.calculate_score()
        db.session.commit()
        
        return True
