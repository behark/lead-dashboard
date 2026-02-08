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
import os

logger = logging.getLogger(__name__)


def bulk_send_job(job_id, lead_ids, template_id, channel, user_id, dry_run=False):
    """
    Background job for bulk sending messages with multi-layered processing
    
    Args:
        job_id: BulkJob record ID
        lead_ids: List of lead IDs to process
        template_id: Template ID to use (optional)
        channel: Channel to send through
        user_id: User ID who initiated the job
        dry_run: If True, don't actually send messages
    """
    from app import create_app
    
    # Create app context for database access
    app = create_app()
    
    with app.app_context():
        try:
            # Fetch Job Record [2a]
            job = db.session.get(BulkJob, job_id)
            if not job:
                logger.error(f"Bulk job {job_id} not found")
                return
            
            # Mark Job as Running [2b]
            job.status = 'running'
            job.started_at = datetime.now(timezone.utc)
            db.session.commit()
            
            # Load Leads with Eager Loading [2c]
            from sqlalchemy.orm import joinedload
            leads = Lead.query.options(
                joinedload(Lead.organization),
                joinedload(Lead.contact_logs)
            ).filter(Lead.id.in_(lead_ids)).all()
            
            if not leads:
                job.status = 'completed'
                job.completed_at = datetime.now(timezone.utc)
                job.error_message = "No valid leads found"
                db.session.commit()
                return
            
            # Get template if specified
            template = None
            if template_id:
                template = MessageTemplate.query.get(template_id)
            
            # Configure rate limiting
            MESSAGES_PER_BATCH = int(os.environ.get('MESSAGES_PER_BATCH', '30'))
            DELAY_BETWEEN_MESSAGES = int(os.environ.get('DELAY_BETWEEN_MESSAGES', '2'))  # seconds
            DELAY_BETWEEN_BATCHES = int(os.environ.get('DELAY_BETWEEN_BATCHES', '20'))  # seconds
            MAX_RETRY_ATTEMPTS = int(os.environ.get('MAX_RETRY_ATTEMPTS', '3'))
            
            # Initialize counters
            successful_count = 0
            failed_count = 0
            skipped_count = 0
            retry_attempts = {}
            
            # Main processing loop
            for i, lead in enumerate(leads):
                # Check if job was cancelled
                if job.status == 'cancelled':
                    logger.info(f"Job {job_id} was cancelled, stopping processing")
                    return
                
                # Check Batch Boundary [2d]
                if i > 0 and i % MESSAGES_PER_BATCH == 0:
                    if not dry_run:
                        # Batch Rate Limiting Pause [2e]
                        batch_pause = DELAY_BETWEEN_BATCHES
                        logger.info(f"Batch completed ({i}/{len(leads)}). Pausing for {batch_pause}s...")
                        time.sleep(batch_pause)
                
                # Validate phone number
                is_valid, error = validate_phone(lead.phone, lead.country)
                if not is_valid:
                    skipped_count += 1
                    job.skipped_items += 1
                    logger.warning(f"Skipped lead {lead.name}: {error}")
                    db.session.commit()
                    continue
                
                # Select template variant
                selected_template = template
                if template:
                    # Try to find the best variant
                    base_name = template.name.split(' - ')[0]  # Remove variant suffix
                    best_variant = ContactService.select_template_variant(base_name, ContactChannel.WHATSAPP if channel == 'whatsapp' or channel == ContactChannel.WHATSAPP else ContactChannel.EMAIL if channel == 'email' or channel == ContactChannel.EMAIL else ContactChannel.SMS)
                    if best_variant:
                        selected_template = best_variant
                    
                    # Apply AI personalization
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
                    successful_count += 1
                    job.processed_items += 1
                    job.successful_items += 1
                    db.session.commit()
                    continue
                
                # Invoke Message Send [2f]
                try:
                    if channel == 'whatsapp' or channel == ContactChannel.WHATSAPP:
                        result = ContactService.send_whatsapp(
                            lead, message,
                            template_id=template_id_to_use,
                            user_id=user_id,
                            ab_variant=ab_variant
                        )
                    elif channel == 'email' or channel == ContactChannel.EMAIL:
                        result = ContactService.send_email(
                            lead, selected_template.subject if selected_template and hasattr(selected_template, 'subject') else "Hello from a business partner",
                            message,
                            template_id=template_id_to_use,
                            user_id=user_id,
                            ab_variant=ab_variant
                        )
                    elif channel == 'sms' or channel == ContactChannel.SMS:
                        result = ContactService.send_sms(
                            lead, message,
                            template_id=template_id_to_use,
                            user_id=user_id,
                            ab_variant=ab_variant
                        )
                    
                    if result and result.get('success'):
                        successful_count += 1
                        job.successful_items += 1
                        logger.info(f"Successfully sent to lead {lead.name}")
                    else:
                        failed_count += 1
                        job.failed_items += 1
                        error_msg = result.get('error', 'Unknown error') if result else 'Send failed'
                        logger.warning(f"Failed to send to lead {lead.name}: {error_msg}")
                        
                except Exception as e:
                    failed_count += 1
                    job.failed_items += 1
                    logger.exception(f"Error sending to lead {lead.id}: {e}")
                
                # Update job progress counters [2g]
                job.processed_items += 1
                
                # Commit Progress Update [2h]
                db.session.commit()
                
                # Inter-Message Rate Limiting [2i]
                if not dry_run:
                    time.sleep(DELAY_BETWEEN_MESSAGES)
            
            # Mark job as completed
            job.status = 'completed'
            job.completed_at = datetime.now(timezone.utc)
            job.processed_items = len(leads)
            job.successful_items = successful_count
            job.failed_items = failed_count
            job.skipped_items = skipped_count
            
            # Store results
            job.parameters.update({
                'retry_attempts': retry_attempts,
                'completed_at': job.completed_at.isoformat()
            })
            
            db.session.commit()
            
            logger.info(f"Bulk job {job_id} completed: {successful_count} sent, {failed_count} failed, {skipped_count} skipped")
            
        except Exception as e:
            logger.exception(f"Error in bulk job {job_id}: {e}")
            job.status = 'failed'
            job.error_message = str(e)
            job.completed_at = datetime.now(timezone.utc)
            db.session.commit()
            
            return {
                'success': False,
                'error': str(e)
            }
