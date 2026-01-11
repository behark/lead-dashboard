from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, abort
from flask_login import login_required, current_user
from models import db, Lead, LeadStatus, LeadTemperature, ContactLog, MessageTemplate, Sequence, User, ContactChannel, SavedFilter, BulkJob
from models_saas import UsageRecord
from services.analytics_service import AnalyticsService
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
        def log_lead_action(*args, **kwargs):
            pass
from services.scoring_service import ScoringService
from services.contact_service import ContactService
from services.sequence_service import SequenceService
try:
    from sqlalchemy.orm import joinedload, selectinload
except ImportError:
    # Fallback for older SQLAlchemy versions
    joinedload = None
    selectinload = None
from datetime import datetime, timezone, timedelta
from collections import Counter
from typing import List, Dict, Any, Optional
import json

# Optional utilities - graceful fallback for serverless
try:
    from utils.logging_config import get_logger
    logger = get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

try:
    from utils.cache import cached
except ImportError:
    # Fallback: no-op decorator if caching not available
    def cached(timeout=None, key_prefix=None):
        def decorator(func):
            return func
        return decorator

main_bp = Blueprint('main', __name__)

LEADS_PER_PAGE = 50


# Cached helper functions to avoid repeated queries
@cached(timeout=300, key_prefix='categories')
def get_cached_categories() -> List[str]:
    """Get cached list of categories"""
    categories = db.session.query(Lead.category).distinct().order_by(Lead.category).all()
    return [c[0] for c in categories if c[0]]


@cached(timeout=300, key_prefix='countries')
def get_cached_countries() -> List[str]:
    """Get cached list of countries"""
    countries = db.session.query(Lead.country).distinct().order_by(Lead.country).all()
    return [c[0] for c in countries if c[0]]


@cached(timeout=600, key_prefix='users')
def get_cached_users() -> List[User]:
    """Get cached list of active users"""
    return User.query.filter_by(is_active=True).all()


@cached(timeout=300, key_prefix='templates')
def get_cached_templates() -> List[MessageTemplate]:
    """Get cached list of active templates"""
    return MessageTemplate.query.filter_by(is_active=True).all()


@cached(timeout=300, key_prefix='sequences')
def get_cached_sequences() -> List[Sequence]:
    """Get cached list of active sequences"""
    return Sequence.query.filter_by(is_active=True).all()


@main_bp.route('/')
@login_required
def index():
    # Check if user wants quick dashboard (default for personal use)
    use_quick = request.args.get('view', 'quick') == 'quick'
    
    if use_quick:
        return quick_dashboard()
    
    # Original full dashboard
    return full_dashboard()


@main_bp.route('/quick')
@login_required
def quick_dashboard():
    """Simplified quick-access dashboard optimized for personal use"""
    try:
        # Handle presets
        preset = request.args.get('preset')
        
        query = Lead.query
        
        # Apply smart presets
        if preset == 'hot':
            # Hot & Untouched: HOT temperature + NEW status
            query = query.filter(
                Lead.temperature == LeadTemperature.HOT,
                Lead.status == LeadStatus.NEW
            )
        elif preset == 'followup':
            # Follow-ups due: Has next_followup date <= today
            today = datetime.now(timezone.utc).date()
            query = query.filter(
                Lead.next_followup <= today,
                Lead.status.in_([LeadStatus.CONTACTED, LeadStatus.REPLIED])
            )
        elif preset == 'new':
            # Recently added: Last 7 days
            week_ago = datetime.now(timezone.utc) - timedelta(days=7)
            query = query.filter(Lead.created_at >= week_ago)
        
        # Pagination
        page = request.args.get('page', 1, type=int)
        pagination = query.order_by(Lead.created_at.desc()).paginate(page=page, per_page=LEADS_PER_PAGE, error_out=False)
        leads = pagination.items
        
        # Simple stats (no complex queries)
        total_leads = Lead.query.count()
        new_leads = Lead.query.filter_by(status=LeadStatus.NEW).count()
        contacted_leads = Lead.query.filter_by(status=LeadStatus.CONTACTED).count()
        replied_leads = Lead.query.filter_by(status=LeadStatus.REPLIED).count()
        closed_leads = Lead.query.filter_by(status=LeadStatus.CLOSED).count()
        
        # Hot & Untouched: HOT temperature + NEW status
        hot_new = Lead.query.filter(
            Lead.temperature == LeadTemperature.HOT,
            Lead.status == LeadStatus.NEW
        ).count()
        
        # Follow-ups due: Has next_followup date <= today
        today = datetime.now(timezone.utc).date()
        followup_due = Lead.query.filter(
            Lead.next_followup <= today,
            Lead.status.in_([LeadStatus.CONTACTED, LeadStatus.REPLIED])
        ).count()
        
        # Today's targets: Recently added (last 7 days)
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        today_targets = Lead.query.filter(Lead.created_at >= week_ago).count()
        
        # Calculate conversion rates
        response_rate = (replied_leads / contacted_leads * 100) if contacted_leads > 0 else 0
        close_rate = (closed_leads / total_leads * 100) if total_leads > 0 else 0
        
        # Recent activity: Contacts made in last 7 days
        try:
            from models import ContactLog
            contacts_made = ContactLog.query.filter(
                ContactLog.sent_at >= week_ago
            ).count()
        except Exception:
            contacts_made = 0
        
        stats = {
            'total': total_leads,
            'total_leads': total_leads,
            'new_leads': new_leads,
            'contacted_leads': contacted_leads,
            'hot_new': hot_new,
            'followup_due': followup_due,
            'today_targets': today_targets,
            'conversion': {
                'response_rate': round(response_rate, 1),
                'close_rate': round(close_rate, 1)
            },
            'recent_activity': {
                'contacts_made': contacts_made
            }
        }
        
        # Get templates without caching
        try:
            templates = MessageTemplate.query.filter_by(is_active=True).all()
        except Exception:
            templates = []
        
        return render_template(
            'quick_dashboard.html',
            leads=leads,
            pagination=pagination,
            stats=stats,
            templates=templates
        )
        
    except Exception as e:
        logger.exception(f"Error in quick_dashboard: {e}")
        flash('Error loading dashboard. Please try again.', 'danger')
        return redirect(url_for('auth.login'))


def full_dashboard():
    """Original full-featured dashboard"""
    # Get all leads for stats calculation
    all_leads_query = Lead.query
    
    # Filters
    temp_filter = request.args.get('temp')
    status_filter = request.args.get('status')
    cat_filter = request.args.get('category')
    country_filter = request.args.get('country')
    search_query = request.args.get('search', '').strip()
    assigned_filter = request.args.get('assigned')
    
    # Build query
    query = Lead.query
    
    if temp_filter:
        try:
            query = query.filter(Lead.temperature == LeadTemperature(temp_filter))
        except ValueError:
            pass
    
    if status_filter:
        try:
            query = query.filter(Lead.status == LeadStatus(status_filter))
        except ValueError:
            pass
    
    if cat_filter:
        query = query.filter(Lead.category == cat_filter)
    
    if country_filter:
        query = query.filter(Lead.country == country_filter)
    
    if search_query:
        query = query.filter(Lead.name.ilike(f'%{search_query}%'))
    
    if assigned_filter:
        if assigned_filter == 'unassigned':
            query = query.filter(Lead.assigned_to.is_(None))
        elif assigned_filter == 'mine':
            query = query.filter(Lead.assigned_to == current_user.id)
        else:
            try:
                query = query.filter(Lead.assigned_to == int(assigned_filter))
            except ValueError:
                pass
    
    # Sort
    sort_by = request.args.get('sort', 'score')
    if sort_by == 'score':
        query = query.order_by(Lead.lead_score.desc())
    elif sort_by == 'date':
        query = query.order_by(Lead.created_at.desc())
    elif sort_by == 'name':
        query = query.order_by(Lead.name)
    elif sort_by == 'followup':
        query = query.order_by(Lead.next_followup.asc().nullslast())
    
    # Optimize query: eager load relationships to avoid N+1 (if available)
    # Note: contact_logs is lazy='dynamic' so we can't use selectinload on it
    if joinedload:
        query = query.options(
            joinedload(Lead.assigned_user)
        )
    
    # Pagination
    page = request.args.get('page', 1, type=int)
    pagination = query.paginate(page=page, per_page=LEADS_PER_PAGE, error_out=False)
    leads = pagination.items
    
    # Get stats (cached)
    stats = AnalyticsService.get_dashboard_stats()
    
    # Get unique values for filters (cached)
    categories = get_cached_categories()
    countries = get_cached_countries()
    users = get_cached_users()
    
    # Leads needing attention
    attention = ScoringService.get_leads_needing_attention()
    
    return render_template(
        'index.html',
        leads=leads,
        pagination=pagination,
        stats=stats,
        categories=categories,
        countries=countries,
        users=users,
        attention=attention,
        search_query=search_query,
        current_filters={
            'temp': temp_filter,
            'status': status_filter,
            'category': cat_filter,
            'country': country_filter,
            'sort': sort_by,
            'assigned': assigned_filter,
        },
        templates=get_cached_templates()
    )


@main_bp.route('/lead/<int:lead_id>')
@login_required
def lead_detail(lead_id):
    # Eager load relationships to avoid N+1 queries (if available)
    # Note: contact_logs is lazy='dynamic' so we query it separately
    if joinedload:
        lead = db.session.get(Lead, lead_id)
        if not lead:
            abort(404)
        # Eager load relationships
        _ = lead.assigned_user  # Trigger lazy load
    else:
        lead = db.session.get(Lead, lead_id)
        if not lead:
            abort(404)
    
    # Get contact history (query separately since it's dynamic)
    contact_logs = lead.contact_logs.order_by(ContactLog.sent_at.desc()).all()
    
    # Get available templates (cached)
    templates = get_cached_templates()
    
    # Get available sequences (cached)
    sequences = get_cached_sequences()
    
    # Get users for assignment
    users = User.query.filter_by(is_active=True).all()
    
    return render_template(
        'detail.html',
        lead=lead,
        contact_logs=contact_logs,
        templates=templates,
        sequences=sequences,
        users=users
    )


@main_bp.route('/lead/<int:lead_id>/update', methods=['POST'])
@login_required
def update_lead(lead_id):
    lead = db.session.get(Lead, lead_id)
    if not lead:
        abort(404)
    
    # Update status
    new_status = request.form.get('status')
    if new_status:
        try:
            lead.status = LeadStatus(new_status)
            if new_status == 'CONTACTED' and not lead.last_contacted:
                lead.last_contacted = datetime.now(timezone.utc)
        except ValueError:
            pass
    
    # Update notes
    notes = request.form.get('notes')
    if notes is not None:
        # Validate notes length
        if len(notes) > 10000:
            flash('Notes must be 10000 characters or less.', 'danger')
            return redirect(request.referrer or url_for('main.index'))
        lead.notes = notes
    
    # Update assignment
    assigned_to = request.form.get('assigned_to')
    if assigned_to:
        if assigned_to == 'none':
            lead.assigned_to = None
        else:
            try:
                lead.assigned_to = int(assigned_to)
            except ValueError:
                pass
    
    # Update follow-up
    followup = request.form.get('next_followup')
    if followup:
        try:
            lead.next_followup = datetime.fromisoformat(followup).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    
    try:
        db.session.commit()
        
        # Log lead update
        AuditLogger.log_lead_action('lead_updated', lead_id, current_user.id, 
                                   details={'status': new_status, 'assigned_to': assigned_to})
        
        # Check if this is an AJAX request
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True})
        flash('Lead updated.', 'success')
        return redirect(request.referrer or url_for('main.index'))
    except Exception as e:
        db.session.rollback()
        logger.exception("Error updating lead")
        
        # Log failed update
        AuditLogger.log_lead_action('lead_updated', lead_id, current_user.id, 
                                   status='error', error_message=str(e))
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': 'Failed to update lead'}), 500
        flash('Error updating lead. Please try again.', 'danger')
        return redirect(request.referrer or url_for('main.index'))


@main_bp.route('/lead/<int:lead_id>/contact', methods=['POST'])
@login_required
def contact_lead(lead_id):
    lead = db.session.get(Lead, lead_id)
    if not lead:
        abort(404)
    
    channel = request.form.get('channel')
    template_id = request.form.get('template_id')
    custom_message = request.form.get('message')
    
    # Get message
    template = None
    if template_id:
        template = db.session.get(MessageTemplate, template_id)
        if not template:
            flash('Template not found.', 'danger')
            return redirect(url_for('main.lead_detail', lead_id=lead_id))
    elif not custom_message:
        # Fallback to default template for the chosen channel
        try:
            channel_enum = ContactChannel(channel)
        except ValueError:
            channel_enum = ContactChannel.WHATSAPP
        template = MessageTemplate.query.filter_by(
            channel=channel_enum,
            is_default=True,
            is_active=True
        ).first()
        if template:
            template_id = template.id

    if template:
        message = ContactService.personalize_message(template.content, lead)
        subject = ContactService.personalize_message(template.subject or '', lead) if template.subject else None
    elif custom_message:
        message = custom_message
        subject = request.form.get('subject')
        template_id = None
    else:
        flash('No message provided.', 'danger')
        return redirect(url_for('main.lead_detail', lead_id=lead_id))
    
    # Send based on channel
    result = None
    if channel == 'whatsapp':
        result = ContactService.send_whatsapp(
            lead, message,
            template_id=template_id,
            user_id=current_user.id
        )
    elif channel == 'email':
        if not subject:
            subject = f"Hello from your business partner"
        result = ContactService.send_email(
            lead, subject, message,
            template_id=template_id,
            user_id=current_user.id
        )
    elif channel == 'sms':
        result = ContactService.send_sms(
            lead, message,
            template_id=template_id,
            user_id=current_user.id
        )
    
    if result and result.get('success'):
        # Log successful contact
        AuditLogger.log_lead_action('lead_contacted', lead_id, current_user.id,
                                   details={'channel': channel, 'template_id': template_id})
        flash(f'Message sent via {channel}!', 'success')
    else:
        error = result.get('error', 'Unknown error') if result else 'Send failed'
        # Log failed contact
        AuditLogger.log_lead_action('lead_contacted', lead_id, current_user.id,
                                   status='error', error_message=error)
        flash(f'Failed to send: {error}', 'danger')
    
    return redirect(url_for('main.lead_detail', lead_id=lead_id))


@main_bp.route('/lead/<int:lead_id>/sequence', methods=['POST'])
@login_required
def enroll_sequence(lead_id):
    lead = db.session.get(Lead, lead_id)
    if not lead:
        abort(404)
    
    sequence_id = request.form.get('sequence_id')
    
    if sequence_id:
        if SequenceService.enroll_lead(lead, int(sequence_id)):
            flash('Lead enrolled in sequence.', 'success')
        else:
            flash('Failed to enroll lead.', 'danger')
    else:
        SequenceService.unenroll_lead(lead)
        flash('Lead removed from sequence.', 'info')
    
    return redirect(url_for('main.lead_detail', lead_id=lead_id))


@main_bp.route('/lead/<int:lead_id>/response', methods=['POST'])
@login_required
def record_response(lead_id):
    lead = db.session.get(Lead, lead_id)
    if not lead:
        abort(404)
    
    channel = request.form.get('channel', 'whatsapp')
    response_content = request.form.get('response_content')
    
    try:
        channel_enum = ContactChannel(channel)
    except ValueError:
        channel_enum = ContactChannel.WHATSAPP
    
    ContactService.record_response(lead, channel_enum, response_content)
    flash('Response recorded.', 'success')
    
    return redirect(url_for('main.lead_detail', lead_id=lead_id))


@main_bp.route('/bulk-action', methods=['POST'])
@login_required
def bulk_action():
    action = request.form.get('action')
    lead_ids = request.form.getlist('lead_ids')
    
    if not lead_ids:
        flash('No leads selected.', 'warning')
        return redirect(url_for('main.index'))
    
    leads = Lead.query.filter(Lead.id.in_(lead_ids)).all()
    
    if action == 'assign':
        user_id = request.form.get('assign_to')
        for lead in leads:
            lead.assigned_to = int(user_id) if user_id else None
        flash(f'{len(leads)} leads assigned.', 'success')
    
    elif action == 'status':
        new_status = request.form.get('new_status')
        try:
            status = LeadStatus(new_status)
            for lead in leads:
                lead.status = status
            flash(f'{len(leads)} leads updated.', 'success')
        except ValueError:
            flash('Invalid status.', 'danger')
    
    elif action == 'enroll_sequence':
        sequence_id = request.form.get('sequence_id')
        count = 0
        for lead in leads:
            if SequenceService.enroll_lead(lead, int(sequence_id)):
                count += 1
        flash(f'{count} leads enrolled in sequence.', 'success')
    
    elif action == 'recalculate_scores':
        for lead in leads:
            lead.calculate_score()
        flash(f'Scores recalculated for {len(leads)} leads.', 'success')
    
    elif action == 'personal_whatsapp':
        # Redirect to personal WhatsApp bulk sender page
        lead_ids_str = ','.join(str(lead.id) for lead in leads)
        return redirect(url_for('main.personal_whatsapp_bulk', lead_ids=lead_ids_str))
    
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.exception("Error in action")
        flash('Error performing action. Please try again.', 'danger')
    return redirect(url_for('main.index'))


# ===== SAVED FILTERS =====
@main_bp.route('/save-filter', methods=['POST'])
@login_required
def save_filter():
    """Save current filter selection for reuse"""
    filter_name = request.form.get('filter_name')
    filter_desc = request.form.get('filter_desc', '')
    is_favorite = request.form.get('is_favorite') == 'on'
    filters_json = request.form.get('filters')
    
    if not filter_name or not filters_json:
        return jsonify({'success': False, 'error': 'Missing filter name or data'})
    
    try:
        filters_data = json.loads(filters_json)
    except json.JSONDecodeError:
        return jsonify({'success': False, 'error': 'Invalid filter data'})
    
    saved_filter = SavedFilter(
        user_id=current_user.id,
        name=filter_name,
        description=filter_desc,
        filters=filters_data,
        is_favorite=is_favorite
    )
    
    try:
        db.session.add(saved_filter)
        db.session.commit()
        return jsonify({'success': True, 'id': saved_filter.id})
    except Exception as e:
        db.session.rollback()
        logger.exception("Error saving filter")
        return jsonify({'success': False, 'error': 'Failed to save filter'}), 500


@main_bp.route('/load-filter/<int:filter_id>')
@login_required
def load_filter(filter_id):
    """Load saved filter and redirect to dashboard with filters applied"""
    saved_filter = db.session.get(SavedFilter, filter_id)
    if not saved_filter:
        abort(404)
    
    if saved_filter.user_id != current_user.id:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('main.index'))
    
    # Update usage stats
    try:
        saved_filter.last_used = datetime.now(timezone.utc)
        saved_filter.usage_count += 1
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.exception("Error updating filter usage")
        # Continue anyway - not critical
    
    # Build redirect URL with filters
    filters = saved_filter.filters
    query_params = {k: v for k, v in filters.items() if v}
    
    return redirect(url_for('main.index', **query_params))


@main_bp.route('/delete-filter/<int:filter_id>', methods=['POST'])
@login_required
def delete_filter(filter_id):
    """Delete a saved filter"""
    saved_filter = db.session.get(SavedFilter, filter_id)
    if not saved_filter:
        abort(404)
    
    if saved_filter.user_id != current_user.id:
        return jsonify({'success': False, 'error': 'Unauthorized'})
    
    try:
        db.session.delete(saved_filter)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        logger.exception("Error deleting filter")
        return jsonify({'success': False, 'error': 'Failed to delete filter'}), 500


# ===== BULK JOB TRACKING =====
@main_bp.route('/bulk-jobs')
@login_required
def bulk_jobs_dashboard():
    """Show active and recent bulk operations"""
    # Get active jobs
    active_jobs = BulkJob.query.filter_by(
        user_id=current_user.id,
        status='running'
    ).all()
    
    # Get recent completed/failed jobs
    recent_jobs = BulkJob.query.filter_by(
        user_id=current_user.id
    ).filter(BulkJob.status.in_(['completed', 'failed', 'cancelled'])).order_by(
        BulkJob.completed_at.desc()
    ).limit(20).all()
    
    return render_template('bulk_jobs_dashboard.html', 
                         active_jobs=active_jobs,
                         recent_jobs=recent_jobs)


@main_bp.route('/bulk-job/<int:job_id>/status')
@login_required
def get_job_status(job_id):
    """Get real-time status of a bulk job with enhanced progress tracking"""
    from utils.job_queue import get_job_status as get_rq_job_status
    
    job = db.session.get(BulkJob, job_id)
    if not job:
        abort(404)
    
    # Check authorization
    if job.user_id != current_user.id and not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    # Get detailed status
    status_data = {
        'id': job.id,
        'status': job.status,
        'progress_percent': job.progress_percent,
        'total_items': job.total_items,
        'processed_items': job.processed_items,
        'successful_items': job.successful_items,
        'failed_items': job.failed_items,
        'skipped_items': job.skipped_items,
        'created_at': job.created_at.isoformat() if job.created_at else None,
        'started_at': job.started_at.isoformat() if job.started_at else None,
        'completed_at': job.completed_at.isoformat() if job.completed_at else None,
        'error_message': job.error_message,
        'estimated_completion': None
    }
    
    # Add estimated completion time for running jobs
    if job.status == 'running' and job.processed_items > 0:
        try:
            elapsed_time = (datetime.now(timezone.utc) - job.started_at).total_seconds()
            avg_time_per_item = elapsed_time / job.processed_items
            remaining_items = job.total_items - job.processed_items
            estimated_seconds = remaining_items * avg_time_per_item
            estimated_completion = datetime.now(timezone.utc) + timedelta(seconds=estimated_seconds)
            status_data['estimated_completion'] = estimated_completion.isoformat()
            status_data['estimated_time_remaining'] = f"{int(estimated_seconds // 60)}m {int(estimated_seconds % 60)}s"
        except Exception:
            pass
    
    try:
        rq_status = get_rq_job_status(job_id)
        if rq_status and rq_status.get('status') != 'not_found':
            status_data['rq_status'] = rq_status['status']
            status_data['rq_created_at'] = rq_status.get('created_at')
    except Exception:
        pass
    
    return jsonify(status_data)


@main_bp.route('/send-message', methods=['POST'])
@login_required
def send_message():
    """Send message to multiple leads (legacy endpoint)"""
    lead_ids_str = request.form.get('lead_ids', '')
    template_id = request.form.get('template_id')
    custom_message = request.form.get('custom_message', '')
    
    if not lead_ids_str:
        flash('No leads selected.', 'warning')
        return redirect(url_for('main.index'))
    
    try:
        lead_ids = [int(id) for id in lead_ids_str.split(',') if id]
    except ValueError:
        flash('Invalid lead IDs.', 'danger')
        return redirect(url_for('main.index'))
    
    leads = Lead.query.filter(Lead.id.in_(lead_ids)).all()
    
    # Get templates for message selection
    templates = get_cached_templates()
    whatsapp_templates = [t for t in templates if t.channel == ContactChannel.WHATSAPP]
    
    # Generate WhatsApp links for each lead
    whatsapp_links = []
    for lead in leads:
        if not lead.phone:
            continue
        
        # Generate or use existing WhatsApp Web link
        from services.phone_service import format_phone_international
        import urllib.parse
        
        formatted_phone = format_phone_international(lead.phone, lead.country)
        # Remove + and spaces for WhatsApp link
        clean_phone = formatted_phone.replace('+', '').replace(' ', '').replace('-', '')
        
        # Use first_message if available, otherwise generate a simple one
        message = lead.first_message or f"Hi {lead.name}! I saw your business on Google and wanted to reach out."
        encoded_message = urllib.parse.quote(message)
        
        whatsapp_link = f"https://wa.me/{clean_phone}?text={encoded_message}"
        
        whatsapp_links.append({
            'lead_id': lead.id,
            'name': lead.name,
            'phone': lead.phone,
            'link': whatsapp_link,
            'message': message
        })
    
    return render_template('bulk/personal_whatsapp.html',
                         leads_data=whatsapp_links,
                         templates=whatsapp_templates)


@main_bp.route('/personal-whatsapp-bulk')
@login_required
def personal_whatsapp_bulk():
    """Personal WhatsApp bulk sender page - accessed via bulk action redirect"""
    lead_ids_str = request.args.get('lead_ids', '')
    
    if not lead_ids_str:
        flash('No leads selected.', 'warning')
        return redirect(url_for('main.index'))
    
    try:
        lead_ids = [int(id) for id in lead_ids_str.split(',') if id]
    except ValueError:
        flash('Invalid lead IDs.', 'danger')
        return redirect(url_for('main.index'))
    
    leads = Lead.query.filter(Lead.id.in_(lead_ids)).all()
    
    if not leads:
        flash('No valid leads found.', 'warning')
        return redirect(url_for('main.index'))
    
    # Get templates for message selection
    templates = get_cached_templates()
    whatsapp_templates = [t for t in templates if t.channel == ContactChannel.WHATSAPP]
    
    # Generate WhatsApp links for each lead
    from services.phone_service import format_phone_international
    import urllib.parse
    
    whatsapp_links = []
    for lead in leads:
        if not lead.phone:
            continue
        
        # Format phone number
        formatted_phone = format_phone_international(lead.phone, lead.country)
        clean_phone = formatted_phone.replace('+', '').replace(' ', '').replace('-', '')
        
        # Use first_message if available, otherwise generate a professional one
        if lead.first_message:
            message = lead.first_message
        else:
            # Use default professional template
            message = f"Përshëndetje {lead.name}! 👋\n\nJam nga Web Solutions Albania dhe e pashë biznesin tuaj në Google Maps.\n\nKam vënë re që nuk keni ende një faqe interneti. A do të donit të diskutojmë se si mund t'ju ndihmojmë?\n\nMe respekt"
        
        encoded_message = urllib.parse.quote(message)
        whatsapp_link = f"https://wa.me/{clean_phone}?text={encoded_message}"
        
        whatsapp_links.append({
            'lead_id': lead.id,
            'name': lead.name,
            'phone': lead.phone,
            'link': whatsapp_link,
            'message': message
        })
    
    if not whatsapp_links:
        flash('No leads with valid phone numbers found.', 'warning')
        return redirect(url_for('main.index'))
    
    return render_template('bulk/personal_whatsapp.html',
                         leads_data=whatsapp_links,
                         templates=whatsapp_templates)


@main_bp.route('/bulk-job/<int:job_id>/cancel', methods=['POST'])
@login_required
def cancel_job(job_id):
    """Cancel a running bulk job"""
    job = db.session.get(BulkJob, job_id)
    if not job:
        abort(404)
    
    if job.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    if job.is_active:
        try:
            job.status = 'cancelled'
            job.completed_at = datetime.now(timezone.utc)
            db.session.commit()
            return jsonify({'success': True, 'message': 'Job cancelled'})
        except Exception as e:
            db.session.rollback()
            logger.exception("Error cancelling job")
            return jsonify({'success': False, 'error': 'Failed to cancel job'}), 500
    
    return jsonify({'success': False, 'message': 'Job is not active'})


# ===== KANBAN BOARD API =====
@main_bp.route('/kanban')
@login_required
def kanban_board():
    """Kanban board view for drag-and-drop status management"""
    return render_template('kanban_board.html')


@main_bp.route('/api/leads')
@login_required
def get_leads_api():
    """Get leads as JSON for Kanban board"""
    try:
        leads = Lead.query.filter_by(assigned_to=current_user.id).all()
        
        return jsonify([{
            'id': l.id,
            'name': l.name,
            'phone': l.phone,
            'status': l.status.value,
            'temperature': l.temperature.value,
            'lead_score': l.lead_score,
            'category': l.category,
            'city': l.city
        } for l in leads])
    except Exception as e:
        logger.exception("Error fetching leads API")
        return jsonify({'error': 'Failed to fetch leads', 'message': str(e)}), 500


@main_bp.route('/api/lead/<int:lead_id>/status', methods=['POST'])
@login_required
def update_lead_status(lead_id):
    """Update lead status via API"""
    try:
        lead = db.session.get(Lead, lead_id)
        if not lead:
            return jsonify({'success': False, 'error': 'Lead not found'}), 404
        
        if lead.assigned_to != current_user.id and current_user.role != 'admin':
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        new_status = data.get('status')
        if not new_status:
            return jsonify({'success': False, 'error': 'Status is required'}), 400
        
        lead.status = LeadStatus(new_status)
        db.session.commit()
        return jsonify({'success': True})
    except ValueError as e:
        return jsonify({'success': False, 'error': f'Invalid status: {str(e)}'}), 400
    except Exception as e:
        db.session.rollback()
        logger.exception("Error updating lead status")
        return jsonify({'success': False, 'error': 'Failed to update status'}), 500


@main_bp.route('/api/hot-leads')
@login_required
def get_hot_leads():
    """Get new hot leads for notifications"""
    try:
        since_timestamp = request.args.get('since', type=int)
        
        if not since_timestamp:
            # Default to last hour
            since_timestamp = int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp() * 1000)
        
        # Convert milliseconds to datetime
        try:
            since_date = datetime.fromtimestamp(since_timestamp / 1000, tz=timezone.utc)
        except (ValueError, OSError) as e:
            return jsonify({'error': 'Invalid timestamp format', 'message': str(e)}), 400
        
        # Query hot leads created since timestamp
        hot_leads = Lead.query.filter(
            Lead.temperature == LeadTemperature.HOT,
            Lead.status == LeadStatus.NEW,
            Lead.created_at >= since_date
        ).order_by(Lead.created_at.desc()).limit(10).all()
        
        return jsonify({
            'leads': [{
                'id': lead.id,
                'name': lead.name,
                'category': lead.category,
                'city': lead.city,
                'country': lead.country,
                'lead_score': lead.lead_score,
                'phone': lead.phone,
                'created_at': lead.created_at.isoformat()
            } for lead in hot_leads]
        })
    except Exception as e:
        logger.exception("Error fetching hot leads")
        return jsonify({'error': 'Failed to fetch hot leads', 'message': str(e)}), 500


@main_bp.route('/api/lead/<int:lead_id>')
@login_required
def get_lead_api(lead_id):
    """Get single lead data as JSON for inline editing"""
    try:
        lead = db.session.get(Lead, lead_id)
        if not lead:
            return jsonify({'error': 'Lead not found'}), 404
        
        return jsonify({
            'id': lead.id,
            'name': lead.name,
            'phone': lead.phone,
            'email': lead.email,
            'city': lead.city,
            'country': lead.country,
            'category': lead.category,
            'status': lead.status.value,
            'temperature': lead.temperature.value,
            'lead_score': lead.lead_score,
            'notes': lead.notes,
            'next_followup': lead.next_followup.isoformat() if lead.next_followup else None,
            'whatsapp_link': lead.whatsapp_link,
            'rating': lead.rating
        })
    except Exception as e:
        logger.exception("Error fetching lead API")
        return jsonify({'error': 'Failed to fetch lead', 'message': str(e)}), 500


@main_bp.route('/api/templates')
@login_required
def get_templates_api():
    """Get all active templates as JSON"""
    try:
        templates = MessageTemplate.query.filter_by(is_active=True).all()
        
        return jsonify([{
            'id': t.id,
            'name': t.name,
            'content': t.content,
            'channel': t.channel.value,
            'category': t.category,
            'language': t.language,
            'is_default': t.is_default,
            'response_rate': t.response_rate,
            'usage_count': t.times_sent
        } for t in templates])
    except Exception as e:
        logger.exception("Error fetching templates API")
        return jsonify({'error': 'Failed to fetch templates', 'message': str(e)}), 500


@main_bp.route('/api/send-message', methods=['POST'])
@login_required
def send_message_api():
    """Send a message to a lead via API"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        lead_id = data.get('lead_id')
        template_id = data.get('template_id')
        custom_message = data.get('custom_message')
        channel = data.get('channel', 'whatsapp')
        
        if not lead_id:
            return jsonify({'success': False, 'error': 'lead_id is required'}), 400
        
        lead = db.session.get(Lead, lead_id)
        if not lead:
            return jsonify({'success': False, 'error': 'Lead not found'}), 404
        
        # Get message
        template = None
        if template_id:
            template = db.session.get(MessageTemplate, template_id)
            if template:
                message = ContactService.personalize_message(template.content, lead)
            else:
                message = custom_message or lead.first_message
        else:
            message = custom_message or lead.first_message
        
        if not message:
            return jsonify({'success': False, 'error': 'No message provided'}), 400
        
        # Validate channel
        if channel not in ['whatsapp', 'email', 'sms']:
            return jsonify({'success': False, 'error': 'Invalid channel. Must be whatsapp, email, or sms'}), 400
        
        # Send based on channel
        result = None
        try:
            if channel == 'whatsapp':
                result = ContactService.send_whatsapp(
                    lead, message,
                    template_id=template_id,
                    user_id=current_user.id
                )
            elif channel == 'email':
                subject = template.subject if template_id and template else "Hello"
                result = ContactService.send_email(
                    lead, subject, message,
                    template_id=template_id,
                    user_id=current_user.id
                )
            elif channel == 'sms':
                result = ContactService.send_sms(
                    lead, message,
                    template_id=template_id,
                    user_id=current_user.id
                )
        except Exception as e:
            logger.exception(f"Error sending {channel} message to lead {lead_id}")
            return jsonify({'success': False, 'error': f'Failed to send message: {str(e)}'}), 500
        
        if result and result.get('success'):
            return jsonify({'success': True, 'message': 'Message sent successfully'})
        else:
            error = result.get('error', 'Unknown error') if result else 'Send failed'
            return jsonify({'success': False, 'error': error}), 400
            
    except Exception as e:
        logger.exception("Error in send_message_api")
        return jsonify({'success': False, 'error': 'Internal server error', 'message': str(e)}), 500


@main_bp.route('/api/mark-whatsapp-sent', methods=['POST'])
@login_required
def mark_whatsapp_sent():
    """Record that a WhatsApp message was sent via personal WhatsApp"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        lead_id = data.get('lead_id')
        if not lead_id:
            return jsonify({'success': False, 'error': 'lead_id is required'}), 400
        
        lead = db.session.get(Lead, lead_id)
        if not lead:
            return jsonify({'success': False, 'error': 'Lead not found'}), 404
        
        # Create contact log for the personal WhatsApp send
        log = ContactLog(
            lead_id=lead.id,
            user_id=current_user.id,
            channel=ContactChannel.WHATSAPP,
            message_content='[Sent via Personal WhatsApp]',
            status='sent',
            is_automated=False
        )
        
        # Update lead status
        lead.last_contacted = datetime.now(timezone.utc)
        if lead.status == LeadStatus.NEW:
            lead.status = LeadStatus.CONTACTED
        
        db.session.add(log)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Contact recorded'})
        
    except Exception as e:
        db.session.rollback()
        logger.exception("Error marking WhatsApp sent")
        return jsonify({'success': False, 'error': str(e)}), 500


@main_bp.route('/test-buttons')
@login_required
def test_buttons():
    """Button testing page"""
    return render_template('test_buttons.html')


