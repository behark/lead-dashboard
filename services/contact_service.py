import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone
from flask import current_app
from models import db, Lead, ContactLog, MessageTemplate, ContactChannel, LeadStatus
from sqlalchemy.exc import SQLAlchemyError
from requests.exceptions import RequestException
import re
import random
import logging
import time
from functools import lru_cache

logger = logging.getLogger(__name__)


class ContactService:
    """Unified service for contacting leads across multiple channels"""
    
    @staticmethod
    def personalize_message(template_content, lead):
        """Replace placeholders in message template with lead data"""
        replacements = {
            '{name}': lead.name or '',
            '{business_name}': lead.name or '',
            '{city}': lead.city or '',
            '{country}': lead.country or '',
            '{rating}': str(lead.rating) if lead.rating else '',
            '{category}': lead.category or '',
            '{phone}': lead.phone or '',
            '{email}': lead.email or '',
            '{score}': str(lead.lead_score) if lead.lead_score else '',
            '{temperature}': lead.temperature.value if lead.temperature else '',
        }
        
        message = template_content
        for placeholder, value in replacements.items():
            message = message.replace(placeholder, value)
        
        return message
    
    @staticmethod
    def send_whatsapp(lead, message, template_id=None, user_id=None, is_automated=False, ab_variant=None):
        """Send WhatsApp message via Twilio with enhanced delivery tracking"""
        
        if not current_app.config.get('TWILIO_ACCOUNT_SID'):
            return {'success': False, 'error': 'Twilio API not configured'}
        
        phone = lead.phone
        if not phone:
            return {'success': False, 'error': 'No phone number'}
        
        # Format phone for international use
        from services.phone_service import format_phone_international
        formatted_phone = format_phone_international(phone, lead.country)
        
        try:
            from twilio.rest import Client
            
            client = Client(
                current_app.config['TWILIO_ACCOUNT_SID'],
                current_app.config['TWILIO_AUTH_TOKEN']
            )
            
            # Send message using Twilio WhatsApp
            # Note: Business-initiated messages might require a template (content_sid)
            # but for sandbox and session-based, 'body' works fine.
            tw_message = client.messages.create(
                body=message,
                from_=f"whatsapp:{current_app.config.get('TWILIO_WHATSAPP_NUMBER', '+14155238886')}",
                to=f"whatsapp:{formatted_phone}"
            )
            
            success = tw_message.sid is not None
            
            # Log the contact with enhanced tracking
            log = ContactLog(
                lead_id=lead.id,
                user_id=user_id,
                channel=ContactChannel.WHATSAPP,
                message_template_id=template_id,
                message_content=message,
                is_automated=is_automated,
                ab_variant=ab_variant,
                twilio_message_sid=tw_message.sid if success else None,  # Store SID for status tracking
                status='sent' if success else 'failed'  # Initial status for tracking
            )
            
            if success:
                # Don't set delivered_at here - wait for webhook confirmation
                # Only update lead status and template stats
                lead.last_contacted = datetime.now(timezone.utc)
                if lead.status == LeadStatus.NEW:
                    lead.status = LeadStatus.CONTACTED
                
                # Update template stats
                if template_id:
                    template = db.session.get(MessageTemplate, template_id)
                    if template:
                        template.times_sent += 1
            
            db.session.add(log)
            
            # Record usage
            if success:
                from models_saas import UsageRecord
                UsageRecord.record_usage(
                    organization_id=lead.organization_id,
                    usage_type='message_sent',
                    user_id=user_id,
                    resource_id=log.id,
                    quantity=1
                )
            
            db.session.commit()
            
            logger.info(f"WhatsApp message sent to {lead.name} (SID: {tw_message.sid})")
            
            return {
                'success': success,
                'message_sid': tw_message.sid,
                'status': 'sent' if success else 'failed',
                'error': None if success else "Failed to get message SID"
            }
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.exception("Database error sending WhatsApp")
            return {'success': False, 'error': 'Database error: ' + str(e)}
        except RequestException as e:
            logger.exception("API error sending WhatsApp")
            return {'success': False, 'error': 'API error: ' + str(e)}
        except Exception as e:
            logger.exception("Unexpected error sending WhatsApp")
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
            
            # Log the contact with enhanced tracking
            log = ContactLog(
                lead_id=lead.id,
                user_id=user_id,
                channel=ContactChannel.EMAIL,
                message_template_id=template_id,
                message_content=message,
                delivered_at=datetime.now(timezone.utc),  # Email delivery is immediate
                is_automated=is_automated,
                ab_variant=ab_variant
            )
            
            lead.last_contacted = datetime.now(timezone.utc)
            if lead.status == LeadStatus.NEW:
                lead.status = LeadStatus.CONTACTED
            
            if template_id:
                template = db.session.get(MessageTemplate, template_id)
                if template:
                    template.times_sent += 1
            
            db.session.add(log)
            
            # Record usage
            from models_saas import UsageRecord
            UsageRecord.record_usage(
                organization_id=lead.organization_id,
                usage_type='message_sent',
                user_id=user_id,
                resource_id=log.id,
                quantity=1
            )
            
            db.session.commit()
            
            return {'success': True}
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.exception("Database error sending email")
            return {'success': False, 'error': 'Database error: ' + str(e)}
        except (smtplib.SMTPException, OSError) as e:
            logger.exception("SMTP error sending email")
            return {'success': False, 'error': 'Email error: ' + str(e)}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def send_sms(lead, message, template_id=None, user_id=None, is_automated=False, ab_variant=None):
        """Send SMS via Twilio with enhanced delivery tracking"""
        
        if not current_app.config.get('TWILIO_ACCOUNT_SID'):
            return {'success': False, 'error': 'SMS not configured'}
        
        phone = lead.phone
        if not phone:
            return {'success': False, 'error': 'No phone number'}
        
        # Format phone for international use
        from services.phone_service import format_phone_international
        formatted_phone = format_phone_international(phone, lead.country)
        
        try:
            from twilio.rest import Client
            
            client = Client(
                current_app.config['TWILIO_ACCOUNT_SID'],
                current_app.config['TWILIO_AUTH_TOKEN']
            )
            
            # Send SMS message
            tw_message = client.messages.create(
                body=message,
                from_=current_app.config.get('TWILIO_PHONE_NUMBER', '+15017122661'),
                to=formatted_phone
            )
            
            success = tw_message.sid is not None
            
            # Log the contact with enhanced tracking
            log = ContactLog(
                lead_id=lead.id,
                user_id=user_id,
                channel=ContactChannel.SMS,
                message_template_id=template_id,
                message_content=message,
                twilio_message_sid=tw_message.sid if success else None,  # Store SID for status tracking
                status='sent' if success else 'failed',  # Initial status for tracking
                is_automated=is_automated,
                ab_variant=ab_variant
            )
            
            if success:
                # Update lead information
                lead.last_contacted = datetime.now(timezone.utc)
                if lead.status == LeadStatus.NEW:
                    lead.status = LeadStatus.CONTACTED
                
                # Update template statistics
                if template_id:
                    template = db.session.get(MessageTemplate, template_id)
                    if template:
                        template.times_sent += 1
            
            db.session.add(log)
            
            # Record usage
            if success:
                from models_saas import UsageRecord
                UsageRecord.record_usage(
                    organization_id=lead.organization_id,
                    usage_type='message_sent',
                    user_id=user_id,
                    resource_id=log.id,
                    quantity=1
                )
            
            db.session.commit()
            
            logger.info(f"SMS message sent to {lead.name} (SID: {tw_message.sid})")
            
            return {
                'success': success,
                'message_sid': tw_message.sid,
                'status': 'sent' if success else 'failed',
                'error': None if success else "Failed to get message SID"
            }
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.exception("Database error sending SMS")
            return {'success': False, 'error': 'Database error: ' + str(e)}
        except RequestException as e:
            logger.exception("API error sending SMS")
            return {'success': False, 'error': 'API error: ' + str(e)}
        except Exception as e:
            logger.exception("Unexpected error sending SMS")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def select_template_variant_cached(base_template_name, channel, cache_timestamp=None):
        """Cached version of template variant selection with performance tracking"""
        return ContactService.select_template_variant(base_template_name, channel)
    
    @staticmethod
    def select_template_variant(base_template_name, channel):
        """Select the best performing variant of a template using A/B testing"""
        start_time = time.time()
        
        # Get all variants of this template
        variants = MessageTemplate.query.filter(
            MessageTemplate.name.like(f"{base_template_name}%"),
            MessageTemplate.channel == channel,
            MessageTemplate.is_active == True
        ).all()

        if not variants:
            logger.debug(f"No variants found for template '{base_template_name}' on {channel}")
            return None

        # If only one variant, return it
        if len(variants) == 1:
            logger.debug(f"Single variant found for '{base_template_name}': {variants[0].name}")
            return variants[0]

        # Calculate performance score for each variant
        variant_scores = []
        for variant in variants:
            if variant.times_sent > 0:
                # Score based on response rate with minimum sample size
                response_rate = variant.response_rate
                sample_size = variant.times_sent

                # Bayesian estimate with beta distribution (add pseudocounts)
                alpha = 1 + variant.times_responded  # successes + pseudocount
                beta = 1 + (variant.times_sent - variant.times_responded)  # failures + pseudocount

                # Expected response rate
                expected_rate = alpha / (alpha + beta)

                # Adjust for sample size (prefer variants with more data)
                confidence_adjustment = min(sample_size / 50, 1)  # Full confidence at 50 samples

                score = expected_rate * confidence_adjustment
                
                # Log performance data
                logger.debug(f"Variant '{variant.name}': {response_rate:.2%} response rate, "
                           f"{sample_size} sends, score: {score:.3f}")
            else:
                score = 0.5  # Default for new variants
                logger.debug(f"New variant '{variant.name}': default score {score}")

            variant_scores.append((variant, score))

        # Sort by score descending and return best
        variant_scores.sort(key=lambda x: x[1], reverse=True)
        best_variant = variant_scores[0][0]
        
        # Performance tracking
        selection_time = time.time() - start_time
        logger.info(f"Template variant selection for '{base_template_name}' completed in {selection_time:.3f}s. "
                   f"Selected '{best_variant.name}' with score {variant_scores[0][1]:.3f}")
        
        return best_variant

    @staticmethod
    def get_personalized_template(template, lead, timeout_seconds=10):
        """Get personalized template using AI with timeout and fallback handling"""
        from services.ai_service import ai_service
        import concurrent.futures
        import threading
        
        # Try AI personalization first with timeout
        ai_message = None
        ai_error = None
        
        try:
            # Use ThreadPoolExecutor for timeout handling
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(
                    ai_service.generate_message_variation,
                    template.content,
                    {
                        'name': lead.name,
                        'city': lead.city,
                        'rating': lead.rating,
                        'category': lead.category
                    }
                )
                
                try:
                    ai_message = future.result(timeout=timeout_seconds)
                    logger.info(f"AI personalization completed for lead {lead.name}")
                except concurrent.futures.TimeoutError:
                    logger.warning(f"AI personalization timed out for lead {lead.name} after {timeout_seconds}s")
                    ai_error = "AI service timeout"
                    future.cancel()
                
        except Exception as e:
            logger.exception(f"AI personalization failed for lead {lead.name}: {e}")
            ai_error = str(e)
        
        # Create personalized template
        if ai_message and len(ai_message.strip()) > 10:
            # AI succeeded - create personalized template
            personalized_template = MessageTemplate(
                name=template.name,
                channel=template.channel,
                language=template.language,
                content=ai_message,
                variant=template.variant
            )
            logger.info(f"Using AI-generated message for lead {lead.name}")
            return personalized_template
        else:
            # AI failed - use basic personalization fallback
            logger.info(f"Using fallback personalization for lead {lead.name} (AI error: {ai_error})")
            personalized_content = ContactService.personalize_message(template.content, lead)
            template.content = personalized_content
            return template

    @staticmethod
    def detect_opt_out(response_content):
        """Detect opt-out keywords in response"""
        if not response_content:
            return False, None

        content_lower = response_content.lower().strip()

        # Common opt-out keywords in Albanian and English
        opt_out_keywords = [
            'stop', 'unsubscribe', 'opt out', 'no more', 'remove me',
            'ndalo', 'çregjistrohu', 'mos me shkruaj', 'hiqni mua',
            'mos me kontaktoni', 'fshi mua', 'jo më', 'mjaft'
        ]

        for keyword in opt_out_keywords:
            if keyword in content_lower:
                return True, keyword

        return False, None

    @staticmethod
    def process_opt_out(lead, reason=None):
        """Process opt-out for a lead"""
        lead.marketing_opt_out = True
        lead.opt_out_reason = reason
        lead.opt_out_date = datetime.now(timezone.utc)
        lead.status = LeadStatus.LOST
        lead.notes = (lead.notes or '') + f'\n[OPT-OUT {lead.opt_out_date.strftime("%Y-%m-%d")}] {reason or "User requested opt-out"}'

        try:
            db.session.commit()
            return True
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.exception("Error recording opt-out")
            return False

    @staticmethod
    def record_response(lead, channel, response_content=None):
        """Record a response from a lead"""

        # Check for opt-out first
        is_opt_out, opt_out_keyword = ContactService.detect_opt_out(response_content)
        if is_opt_out:
            ContactService.process_opt_out(lead, f"Detected opt-out keyword: '{opt_out_keyword}'")
            return True

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
                template = db.session.get(MessageTemplate, log.message_template_id)
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
        try:
            db.session.commit()
            return True
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.exception("Error recording response")
            return False

    @staticmethod
    def can_contact_lead(lead, channel):
        """Check if we can legally contact this lead"""
        if not lead:
            return False

        # Check GDPR consent
        if not lead.gdpr_consent:
            return False

        # Check marketing opt-out
        if lead.marketing_opt_out:
            return False

        # Check if lead has valid contact info for the channel
        if channel == 'whatsapp' or channel == 'sms':
            return bool(lead.phone)
        elif channel == 'email':
            return bool(lead.email)

        return False
