"""
Bulk operations routes - Send messages to multiple leads
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db, Lead, ContactLog, MessageTemplate, LeadStatus, LeadTemperature, ContactChannel, UserRole, BulkJob
from services.contact_service import ContactService
from services.phone_service import format_phone_international, validate_phone
from utils.job_queue import enqueue_job, get_job_status
# Import audit logger with graceful fallback
try:
    from utils.audit_logger import AuditLogger
except ImportError:
    # Create a dummy AuditLogger if import fails
    class AuditLogger:
        @staticmethod
        def log(*args, **kwargs):
            pass
        @staticmethod
        def log_bulk_action(*args, **kwargs):
            pass
from datetime import datetime, timezone
from sqlalchemy.exc import SQLAlchemyError
import time
import logging
import os

logger = logging.getLogger(__name__)

def is_retryable_error(error_message):
    """Determine if an error is retryable based on the error message"""
    if not error_message:
        return False
    
    error_lower = error_message.lower()
    
    # Retryable errors (temporary issues)
    retryable_patterns = [
        'timeout', 'network', 'connection', 'rate limit', 'too many requests',
        'service unavailable', 'temporary', 'try again', 'server error',
        'gateway timeout', 'bad gateway', '503', '502', '504', '429'
    ]
    
    # Non-retryable errors (permanent issues)
    non_retryable_patterns = [
        'invalid phone', 'not found', 'unauthorized', 'forbidden',
        'blocked', 'opt out', 'unsubscribed', 'invalid number',
        '404', '401', '403', '400'
    ]
    
    # Check for non-retryable patterns first
    for pattern in non_retryable_patterns:
        if pattern in error_lower:
            return False
    
    # Check for retryable patterns
    for pattern in retryable_patterns:
        if pattern in error_lower:
            return True
    
    # Default to retryable for unknown errors
    return True

bulk_bp = Blueprint('bulk', __name__, url_prefix='/bulk')

# Rate limiting settings - now configurable via environment
MESSAGES_PER_BATCH = int(os.environ.get('MESSAGES_PER_BATCH', '30'))
DELAY_BETWEEN_MESSAGES = int(os.environ.get('DELAY_BETWEEN_MESSAGES', '2'))  # seconds
DELAY_BETWEEN_BATCHES = int(os.environ.get('DELAY_BETWEEN_BATCHES', '20'))  # seconds
MAX_DAILY_MESSAGES = int(os.environ.get('MAX_DAILY_MESSAGES', '200'))
MAX_RETRY_ATTEMPTS = int(os.environ.get('MAX_RETRY_ATTEMPTS', '3'))


@bulk_bp.route('/send', methods=['GET', 'POST'])
@login_required
def bulk_send():
    """Bulk send page - select leads and send messages"""
    
    if request.method == 'POST':
        lead_ids = request.form.getlist('lead_ids')
        template_id = request.form.get('template_id')
        channel = request.form.get('channel', 'whatsapp')
        dry_run = request.form.get('dry_run') == 'on'
        use_background = request.form.get('use_background', 'true') == 'true'  # Default to background
        
        if not lead_ids:
            flash('No leads selected.', 'warning')
            return redirect(url_for('bulk.bulk_send'))
        
        # Convert lead_ids to integers
        try:
            lead_ids = [int(id) for id in lead_ids if id]
        except ValueError:
            flash('Invalid lead IDs.', 'danger')
            return redirect(url_for('bulk.bulk_send'))
        
        # Get leads with optimized query - eager load related data to prevent N+1 queries
        from sqlalchemy.orm import joinedload
        leads = Lead.query.options(
            joinedload(Lead.organization),
            joinedload(Lead.contact_logs)
        ).filter(Lead.id.in_(lead_ids)).all()
        
        if not leads:
            flash('No valid leads found.', 'warning')
            return redirect(url_for('bulk.bulk_send'))
        
        # Get template if specified
        template = None
        if template_id:
            template = MessageTemplate.query.get(template_id)
        
        # Check if background processing needed (if >10 leads)
        if use_background and len(leads) > 10:
            # Create BulkJob Record
            job = BulkJob(
                user_id=current_user.id,
                job_type='send_message',
                status='pending',
                total_items=len(leads),
                parameters={
                    'lead_ids': lead_ids,
                    'template_id': int(template_id) if template_id else None,
                    'channel': channel,
                    'dry_run': dry_run
                }
            )
            db.session.add(job)
            
            # Persist Job to Database
            db.session.commit()
            
            # Enqueue to Redis Queue
            from jobs.bulk_send_job import bulk_send_job
            
            # Set priority based on lead count - larger batches get higher priority
            priority = min(len(leads) // 10, 10)  # Priority 1-10 based on batch size
            
            rq_job = enqueue_job(
                bulk_send_job,
                job.id,
                lead_ids,
                int(template_id) if template_id else None,
                channel,
                current_user.id,
                dry_run,
                job_timeout='30m',  # 30 minute timeout for large batches
                priority=priority
            )
            
            if rq_job:
                # Log audit action
                AuditLogger.log_bulk_action('bulk_send_started', job.id, current_user.id,
                                          details={'lead_count': len(leads), 'channel': channel})
                
                flash(f'Bulk send job started! Processing {len(leads)} leads in the background. Job ID: {job.id}', 'success')
                return redirect(url_for('bulk.job_status', job_id=job.id))
            else:
                # Fallback to synchronous processing
                flash('Background processing not available, processing synchronously...', 'warning')
                use_background = False
        
        # Synchronous processing (fallback or small batches)
        
        # Get template (fallback to default for channel)
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
            'total': len(leads),
            'sent': 0,
            'failed': 0,
            'skipped': 0,
            'retried': 0,
            'errors': [],
            'successful_leads': [],
            'failed_leads': [],
            'retry_attempts': {}
        }
        
        # Track successful operations for rollback if needed
        successful_operations = []
        
        # Retry tracking for failed leads
        failed_leads_for_retry = {}
        
        try:
            for i, lead in enumerate(leads):
                # Enhanced rate limiting with configurable batch processing
                if i > 0 and i % MESSAGES_PER_BATCH == 0:
                    if not dry_run:
                        # Longer pause between batches to prevent API rate limits
                        batch_pause = DELAY_BETWEEN_BATCHES
                        logger.info(f"Batch completed ({i}/{len(leads)}). Pausing for {batch_pause}s...")
                        time.sleep(batch_pause)

                # Validate phone
                is_valid, error = validate_phone(lead.phone, lead.country)
                if not is_valid:
                    results['skipped'] += 1
                    results['errors'].append(f"{lead.name}: {error}")
                    continue

                # Select best performing template variant (A/B testing)
                selected_template = template
                if template:
                    # Try to find the best variant
                    base_name = template.name.split(' - ')[0]  # Remove variant suffix
                    best_variant = ContactService.select_template_variant(base_name, ContactChannel.WHATSAPP if channel == 'whatsapp' else ContactChannel.EMAIL if channel == 'email' else ContactChannel.SMS)
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
                    results['sent'] += 1
                    continue

                # Send based on channel with error handling
                result = None
                try:
                    if channel == 'whatsapp':
                        result = ContactService.send_whatsapp(
                            lead, message,
                            template_id=template_id_to_use,
                            user_id=current_user.id,
                            ab_variant=ab_variant
                        )
                    elif channel == 'email':
                        subject = selected_template.subject if selected_template and hasattr(selected_template, 'subject') and selected_template.subject else f"Hello from a business partner"
                        result = ContactService.send_email(
                            lead, subject, message,
                            template_id=template_id_to_use,
                            user_id=current_user.id,
                            ab_variant=ab_variant
                        )
                    elif channel == 'sms':
                        result = ContactService.send_sms(
                            lead, message,
                            template_id=template_id_to_use,
                            user_id=current_user.id,
                            ab_variant=ab_variant
                        )
                    
                    if result and result.get('success'):
                        results['sent'] += 1
                        results['successful_leads'].append(lead.id)
                        successful_operations.append(lead.id)
                    else:
                        results['failed'] += 1
                        results['failed_leads'].append(lead.id)
                        error = result.get('error', 'Unknown error') if result else 'Send failed'
                        results['errors'].append(f"{lead.name}: {error}")
                        # Store for retry if not dry run and error is retryable
                        if not dry_run and result and is_retryable_error(error):
                            failed_leads_for_retry[str(lead.id)] = {
                                'message': message,
                                'template_id': template_id_to_use,
                                'ab_variant': ab_variant,
                                'subject': selected_template.subject if selected_template and hasattr(selected_template, 'subject') and selected_template.subject else f"Hello from a business partner" if channel == 'email' else None
                            }
                        
                except Exception as e:
                    # Log the error but continue with other leads
                    logger.exception(f"Error sending to lead {lead.id}: {e}")
                    results['failed'] += 1
                    results['failed_leads'].append(lead.id)
                    results['errors'].append(f"{lead.name}: {str(e)}")
                    # Store for retry if not dry run
                    if not dry_run and is_retryable_error(str(e)):
                        failed_leads_for_retry[str(lead.id)] = {
                            'message': message,
                            'template_id': template_id_to_use,
                            'ab_variant': ab_variant,
                            'subject': selected_template.subject if selected_template and hasattr(selected_template, 'subject') and selected_template.subject else f"Hello from a business partner" if channel == 'email' else None
                        }
                
                # Rate limiting between messages
                if not dry_run:
                    time.sleep(DELAY_BETWEEN_MESSAGES)
            
            # Retry failed leads (if any and not dry run)
            if not dry_run and failed_leads_for_retry and MAX_RETRY_ATTEMPTS > 0:
                logger.info(f"Retrying {len(failed_leads_for_retry)} failed leads...")
                for attempt in range(1, MAX_RETRY_ATTEMPTS + 1):
                    if not failed_leads_for_retry:
                        break
                    
                    logger.info(f"Retry attempt {attempt}/{MAX_RETRY_ATTEMPTS}")
                    still_failed = {}
                    
                    for lead_id, error_info in failed_leads_for_retry.items():
                        lead = next((l for l in leads if l.id == int(lead_id)), None)
                        if not lead:
                            continue
                        
                        # Update retry tracking
                        results['retry_attempts'][lead_id] = results['retry_attempts'].get(lead_id, 0) + 1
                        
                        # Wait before retry (exponential backoff)
                        retry_delay = min(2 ** attempt, 30)  # Max 30 seconds
                        time.sleep(retry_delay)
                        
                        try:
                            # Re-attempt send with same parameters
                            if channel == 'whatsapp':
                                result = ContactService.send_whatsapp(
                                    lead, error_info['message'],
                                    template_id=error_info['template_id'],
                                    user_id=current_user.id,
                                    ab_variant=error_info['ab_variant']
                                )
                            elif channel == 'email':
                                result = ContactService.send_email(
                                    lead, error_info['subject'], error_info['message'],
                                    template_id=error_info['template_id'],
                                    user_id=current_user.id,
                                    ab_variant=error_info['ab_variant']
                                )
                            elif channel == 'sms':
                                result = ContactService.send_sms(
                                    lead, error_info['message'],
                                    template_id=error_info['template_id'],
                                    user_id=current_user.id,
                                    ab_variant=error_info['ab_variant']
                                )
                            
                            if result and result.get('success'):
                                results['sent'] += 1
                                results['retried'] += 1
                                results['successful_leads'].append(lead.id)
                                successful_operations.append(lead.id)
                                # Remove from failed list
                                results['failed'] -= 1
                                results['failed_leads'].remove(lead.id)
                                logger.info(f"Retry successful for lead {lead.name}")
                            else:
                                still_failed[lead_id] = error_info
                                logger.warning(f"Retry failed for lead {lead.name}: {result.get('error', 'Unknown error')}")
                        
                        except Exception as e:
                            logger.exception(f"Retry error for lead {lead.id}: {e}")
                            still_failed[lead_id] = error_info
                    
                    failed_leads_for_retry = still_failed
                    time.sleep(5)  # Brief pause between retry attempts
            
            # Commit all successful operations
            # Note: ContactService methods handle their own commits, but we ensure
            # database consistency here
            try:
                db.session.commit()
            except SQLAlchemyError as e:
                logger.exception("Database error during bulk send commit")
                db.session.rollback()
                # Mark all operations as failed since we can't verify state
                results['failed'] += results['sent']
                results['sent'] = 0
                results['errors'].append(f"Database error: {str(e)}")
                
        except Exception as e:
            # Critical error - rollback any uncommitted changes
            logger.exception(f"Critical error in bulk send: {e}")
            try:
                db.session.rollback()
            except Exception:
                pass
            results['errors'].append(f"Critical error: {str(e)}")
            flash(f"Bulk send encountered an error: {str(e)}", 'danger')
        
        if dry_run:
            flash(f"DRY RUN: Would send to {results['sent']} leads. Skipped: {results['skipped']}", 'info')
        else:
            retry_info = f", Retried: {results['retried']}" if results['retried'] > 0 else ""
            flash(f"Sent: {results['sent']}, Failed: {results['failed']}, Skipped: {results['skipped']}{retry_info}", 
                  'success' if results['failed'] == 0 else 'warning')
        
        return render_template('bulk/results.html', results=results)
    
    # GET - Show selection page
    # Get leads that can be contacted (not opted out, have consent)
    leads = Lead.get_contactable_leads(limit=500).all()
    
    # Get templates
    templates = MessageTemplate.query.filter_by(is_active=True).all()

    def _default_for(channel_enum: ContactChannel, preferred_language: str = 'sq'):
        t = MessageTemplate.query.filter_by(
            channel=channel_enum,
            language=preferred_language,
            is_default=True,
            is_active=True
        ).first()
        if t:
            return t
        return MessageTemplate.query.filter_by(
            channel=channel_enum,
            is_default=True,
            is_active=True
        ).first()

    default_templates = {
        'whatsapp': _default_for(ContactChannel.WHATSAPP),
        'email': _default_for(ContactChannel.EMAIL),
        'sms': _default_for(ContactChannel.SMS),
    }
    
    # Group leads by temperature
    hot_leads = [l for l in leads if l.temperature == LeadTemperature.HOT]
    warm_leads = [l for l in leads if l.temperature == LeadTemperature.WARM]
    cold_leads = [l for l in leads if l.temperature == LeadTemperature.COLD]
    
    return render_template(
        'bulk/send.html',
        leads=leads,
        hot_leads=hot_leads,
        warm_leads=warm_leads,
        cold_leads=cold_leads,
        templates=templates,
        default_template_ids={
            k: (v.id if v else None) for k, v in default_templates.items()
        }
    )


@bulk_bp.route('/preview', methods=['POST'])
@login_required
def preview_message():
    """Preview personalized message for a lead"""
    
    lead_id = request.form.get('lead_id')
    template_id = request.form.get('template_id')
    
    lead = db.session.get(Lead, lead_id)
    if not lead:
        return jsonify({'error': 'Lead not found'}), 404
    
    template = None
    if template_id:
        template = db.session.get(MessageTemplate, template_id)
    if not template:
        template = MessageTemplate.query.filter_by(
            channel=ContactChannel.WHATSAPP,
            is_default=True,
            is_active=True
        ).first()

    if template:
        message = ContactService.personalize_message(template.content, lead)
    else:
        message = lead.first_message or ''
    
    # Format phone
    formatted_phone = format_phone_international(lead.phone, lead.country)
    
    return jsonify({
        'name': lead.name,
        'phone': formatted_phone,
        'message': message,
        'category': lead.category,
        'temperature': lead.temperature.value if lead.temperature else 'WARM'
    })


@bulk_bp.route('/followup')
@login_required
def followup_queue():
    """Show leads that need follow-up"""
    
    # Get leads that were contacted but haven't replied
    from datetime import timedelta
    
    now = datetime.now(timezone.utc)
    
    # Day 1 follow-ups (contacted 24h ago)
    day1_cutoff = now - timedelta(hours=24)
    day1_leads = Lead.query.filter(
        Lead.status == LeadStatus.CONTACTED,
        Lead.last_contacted < day1_cutoff,
        Lead.last_contacted > day1_cutoff - timedelta(hours=24)
    ).all()
    
    # Day 2 follow-ups (contacted 48h ago)
    day2_cutoff = now - timedelta(hours=48)
    day2_leads = Lead.query.filter(
        Lead.status == LeadStatus.CONTACTED,
        Lead.last_contacted < day2_cutoff,
        Lead.last_contacted > day2_cutoff - timedelta(hours=24)
    ).all()
    
    # Day 3 follow-ups (contacted 72h ago)
    day3_cutoff = now - timedelta(hours=72)
    day3_leads = Lead.query.filter(
        Lead.status == LeadStatus.CONTACTED,
        Lead.last_contacted < day3_cutoff,
        Lead.last_contacted > day3_cutoff - timedelta(hours=24)
    ).all()
    
    # Day 5 final follow-ups (contacted 120h ago)
    day5_cutoff = now - timedelta(hours=120)
    day5_leads = Lead.query.filter(
        Lead.status == LeadStatus.CONTACTED,
        Lead.last_contacted < day5_cutoff,
        Lead.last_contacted > day5_cutoff - timedelta(hours=48)
    ).all()
    
    return render_template(
        'bulk/followup.html',
        day1_leads=day1_leads,
        day2_leads=day2_leads,
        day3_leads=day3_leads,
        day5_leads=day5_leads
    )


@bulk_bp.route('/smart-send')
@login_required
def smart_send():
    """Smart bulk send with progressive sending, scheduling, and smart templates"""
    
    # Get leads that can be contacted
    leads = Lead.get_contactable_leads(limit=500).all()
    
    # Group by temperature
    hot_leads = [l for l in leads if l.temperature == LeadTemperature.HOT]
    warm_leads = [l for l in leads if l.temperature == LeadTemperature.WARM]
    cold_leads = [l for l in leads if l.temperature == LeadTemperature.COLD]
    
    return render_template(
        'bulk/send_progressive.html',
        leads=leads,
        hot_leads=hot_leads,
        warm_leads=warm_leads,
        cold_leads=cold_leads
    )
