from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db, Lead, LeadStatus, LeadTemperature, ContactLog, MessageTemplate, Sequence, User, ContactChannel, SavedFilter, BulkJob
from services.analytics_service import AnalyticsService
from services.scoring_service import ScoringService
from services.contact_service import ContactService
from services.sequence_service import SequenceService
try:
    from sqlalchemy.orm import joinedload, selectinload
except ImportError:
    # Fallback for older SQLAlchemy versions
    joinedload = None
    selectinload = None
from datetime import datetime, timezone
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
        }
    )


@main_bp.route('/lead/<int:lead_id>')
@login_required
def lead_detail(lead_id):
    # Eager load relationships to avoid N+1 queries (if available)
    # Note: contact_logs is lazy='dynamic' so we query it separately
    if joinedload:
        lead = Lead.query.options(
            joinedload(Lead.assigned_user)
        ).get_or_404(lead_id)
    else:
        lead = Lead.query.get_or_404(lead_id)
    
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
    lead = Lead.query.get_or_404(lead_id)
    
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
    
    db.session.commit()
    
    # Check if this is an AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True})
    
    flash('Lead updated.', 'success')
    return redirect(request.referrer or url_for('main.index'))


@main_bp.route('/lead/<int:lead_id>/contact', methods=['POST'])
@login_required
def contact_lead(lead_id):
    lead = Lead.query.get_or_404(lead_id)
    
    channel = request.form.get('channel')
    template_id = request.form.get('template_id')
    custom_message = request.form.get('message')
    
    # Get message
    template = None
    if template_id:
        template = MessageTemplate.query.get(template_id)
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
        flash(f'Message sent via {channel}!', 'success')
    else:
        error = result.get('error', 'Unknown error') if result else 'Send failed'
        flash(f'Failed to send: {error}', 'danger')
    
    return redirect(url_for('main.lead_detail', lead_id=lead_id))


@main_bp.route('/lead/<int:lead_id>/sequence', methods=['POST'])
@login_required
def enroll_sequence(lead_id):
    lead = Lead.query.get_or_404(lead_id)
    
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
    lead = Lead.query.get_or_404(lead_id)
    
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
    
    db.session.commit()
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
    
    db.session.add(saved_filter)
    db.session.commit()
    
    return jsonify({'success': True, 'id': saved_filter.id})


@main_bp.route('/load-filter/<int:filter_id>')
@login_required
def load_filter(filter_id):
    """Load saved filter and redirect to dashboard with filters applied"""
    saved_filter = SavedFilter.query.get_or_404(filter_id)
    
    if saved_filter.user_id != current_user.id:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('main.index'))
    
    # Update usage stats
    saved_filter.last_used = datetime.now(timezone.utc)
    saved_filter.usage_count += 1
    db.session.commit()
    
    # Build redirect URL with filters
    filters = saved_filter.filters
    query_params = {k: v for k, v in filters.items() if v}
    
    return redirect(url_for('main.index', **query_params))


@main_bp.route('/delete-filter/<int:filter_id>', methods=['POST'])
@login_required
def delete_filter(filter_id):
    """Delete a saved filter"""
    saved_filter = SavedFilter.query.get_or_404(filter_id)
    
    if saved_filter.user_id != current_user.id:
        return jsonify({'success': False, 'error': 'Unauthorized'})
    
    db.session.delete(saved_filter)
    db.session.commit()
    
    return jsonify({'success': True})


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
    """Get real-time status of a bulk job"""
    job = BulkJob.query.get_or_404(job_id)
    
    if job.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    return jsonify({
        'id': job.id,
        'status': job.status,
        'processed': job.processed_items,
        'total': job.total_items,
        'successful': job.successful_items,
        'failed': job.failed_items,
        'skipped': job.skipped_items,
        'progress_percent': job.progress_percent,
        'results': job.results or {}
    })


@main_bp.route('/bulk-job/<int:job_id>/cancel', methods=['POST'])
@login_required
def cancel_job(job_id):
    """Cancel a running bulk job"""
    job = BulkJob.query.get_or_404(job_id)
    
    if job.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    if job.is_active:
        job.status = 'cancelled'
        job.completed_at = datetime.now(timezone.utc)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Job cancelled'})
    
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


@main_bp.route('/api/lead/<int:lead_id>/status', methods=['POST'])
@login_required
def update_lead_status(lead_id):
    """Update lead status via API"""
    lead = Lead.query.get_or_404(lead_id)
    
    if lead.assigned_to != current_user.id and current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    new_status = data.get('status')
    
    try:
        lead.status = LeadStatus(new_status)
        db.session.commit()
        return jsonify({'success': True})
    except ValueError:
        return jsonify({'success': False, 'error': 'Invalid status'})


