"""
Background job for bulk sending messages
"""
from flask import current_app
from models import db, Lead, MessageTemplate, ContactChannel, BulkJob
from services.contact_service import ContactService
from services.phone_service import validate_phone
from datetime import datetime, timezone
from sqlalchemy.exc import SQLAlchemyError
import time
import logging

logger = logging.getLogger(__name__)


def bulk_send_job(job_id, lead_ids, template_id, channel, user_id, dry_run=False):
    """
    Background job for bulk sending messages
    
    Args:
        job_id: BulkJob ID for tracking
        lead_ids: List of lead IDs to send to
        template_id: Template ID to use
        channel: Channel ('whatsapp', 'email', 'sms')
        user_id: User ID performing the action
        dry_run: If True, don't actually send
    
    Returns:
        dict with results
    """
    from app import create_app
    
    # Create app context for database access
    app = create_app()
    with app.app_context():
        job = db.session.get(BulkJob, job_id)
        if not job:
            logger.error(f"BulkJob {job_id} not found")
            return {'success': False, 'error': 'Job not found'}
        
        try:
            job.status = 'running'
            job.started_at = datetime.now(timezone.utc)
            db.session.commit()
            
            # Get leads
            leads = Lead.query.filter(Lead.id.in_(lead_ids)).all()
            job.total_items = len(leads)
            db.session.commit()
            
            # Get template
            template = None
            if template_id:
                template = db.session.get(MessageTemplate, template_id)
            else:
                try:
                    channel_enum = ContactChannel(channel)
                except ValueError:
                    channel_enum = ContactChannel.WHATSAPP
                template = MessageTemplate.query.filter_by(
                    channel=channel_enum,
                    is_default=True,
                    is_active=True
                ).first()
            
            results = {
                'sent': 0,
                'failed': 0,
                'skipped': 0,
                'errors': [],
                'successful_leads': [],
                'failed_leads': []
            }
            
            # Rate limiting settings
            MESSAGES_PER_BATCH = 30
            DELAY_BETWEEN_MESSAGES = 2  # seconds
            
            for i, lead in enumerate(leads):
                # Check if job was cancelled
                job = db.session.get(BulkJob, job_id)
                if job.status == 'cancelled':
                    logger.info(f"Job {job_id} was cancelled")
                    break
                
                # Rate limiting
                if i > 0 and i % MESSAGES_PER_BATCH == 0:
                    if not dry_run:
                        time.sleep(DELAY_BETWEEN_MESSAGES * 10)  # Pause between batches
                
                # Validate phone
                is_valid, error = validate_phone(lead.phone, lead.country)
                if not is_valid:
                    results['skipped'] += 1
                    results['errors'].append(f"{lead.name}: {error}")
                    job.skipped_items += 1
                    job.processed_items += 1
                    db.session.commit()
                    continue
                
                # Select template variant
                selected_template = template
                if template:
                    base_name = template.name.split(' - ')[0]
                    best_variant = ContactService.select_template_variant(
                        base_name,
                        ContactChannel.WHATSAPP if channel == 'whatsapp' 
                        else ContactChannel.EMAIL if channel == 'email' 
                        else ContactChannel.SMS
                    )
                    if best_variant:
                        selected_template = best_variant
                    
                    selected_template = ContactService.get_personalized_template(selected_template, lead)
                
                # Get message
                if selected_template:
                    message = selected_template.content
                    template_id_to_use = selected_template.id
                    ab_variant = selected_template.variant
                else:
                    message = lead.first_message or f"Hi! I saw {lead.name} on Google and wanted to reach out."
                    template_id_to_use = template_id
                    ab_variant = None
                
                if dry_run:
                    results['sent'] += 1
                    job.successful_items += 1
                    job.processed_items += 1
                    db.session.commit()
                    continue
                
                # Send message
                result = None
                try:
                    if channel == 'whatsapp':
                        result = ContactService.send_whatsapp(
                            lead, message,
                            template_id=template_id_to_use,
                            user_id=user_id,
                            ab_variant=ab_variant
                        )
                    elif channel == 'email':
                        subject = selected_template.subject if selected_template and hasattr(selected_template, 'subject') and selected_template.subject else f"Hello from a business partner"
                        result = ContactService.send_email(
                            lead, subject, message,
                            template_id=template_id_to_use,
                            user_id=user_id,
                            ab_variant=ab_variant
                        )
                    elif channel == 'sms':
                        result = ContactService.send_sms(
                            lead, message,
                            template_id=template_id_to_use,
                            user_id=user_id,
                            ab_variant=ab_variant
                        )
                    
                    if result and result.get('success'):
                        results['sent'] += 1
                        results['successful_leads'].append(lead.id)
                        job.successful_items += 1
                    else:
                        results['failed'] += 1
                        results['failed_leads'].append(lead.id)
                        error = result.get('error', 'Unknown error') if result else 'Send failed'
                        results['errors'].append(f"{lead.name}: {error}")
                        job.failed_items += 1
                    
                    job.processed_items += 1
                    db.session.commit()
                    
                except Exception as e:
                    logger.exception(f"Error sending to lead {lead.id}: {e}")
                    results['failed'] += 1
                    results['failed_leads'].append(lead.id)
                    results['errors'].append(f"{lead.name}: {str(e)}")
                    job.failed_items += 1
                    job.processed_items += 1
                    db.session.commit()
                
                # Rate limiting between messages
                if not dry_run and i < len(leads) - 1:
                    time.sleep(DELAY_BETWEEN_MESSAGES)
            
            # Update job status
            job.status = 'completed'
            job.completed_at = datetime.now(timezone.utc)
            job.results = results
            db.session.commit()
            
            logger.info(f"Bulk send job {job_id} completed: {results['sent']} sent, {results['failed']} failed")
            
            return {
                'success': True,
                'results': results
            }
            
        except Exception as e:
            logger.exception(f"Error in bulk send job {job_id}: {e}")
            job.status = 'failed'
            job.completed_at = datetime.now(timezone.utc)
            job.error_message = str(e)
            db.session.commit()
            
            return {
                'success': False,
                'error': str(e)
            }
