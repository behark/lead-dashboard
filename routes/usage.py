"""
Usage Tracking Routes
Shows usage statistics, limits, and history
"""
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from models import db
from models_saas import (
    Organization, Subscription, UsageRecord, OrganizationMember,
    PLAN_CONFIGS
)
from datetime import datetime, timezone, timedelta
from collections import defaultdict

usage_bp = Blueprint('usage', __name__, url_prefix='/usage')


def get_user_organization():
    """Get current user's organization"""
    member = OrganizationMember.query.filter_by(
        user_id=current_user.id,
        is_active=True
    ).first()
    
    if not member:
        return None
    
    return member.organization


@usage_bp.route('/')
@login_required
def usage_dashboard():
    """Usage tracking dashboard"""
    org = get_user_organization()
    if not org:
        flash('You need to be part of an organization to view usage.', 'warning')
        return redirect(url_for('main.index'))
    
    subscription = org.subscription
    if not subscription:
        return redirect(url_for('main.index'))
    
    plan_config = PLAN_CONFIGS.get(subscription.plan, {})
    
    # Get current period dates
    now = datetime.now(timezone.utc)
    
    # Monthly usage (for leads)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # Daily usage (for messages)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Get usage stats
    leads_this_month = UsageRecord.query.filter(
        UsageRecord.organization_id == org.id,
        UsageRecord.usage_type == 'lead_created',
        UsageRecord.created_at >= month_start
    ).count()
    
    messages_today = UsageRecord.query.filter(
        UsageRecord.organization_id == org.id,
        UsageRecord.usage_type == 'message_sent',
        UsageRecord.created_at >= today_start
    ).count()
    
    messages_this_month = UsageRecord.query.filter(
        UsageRecord.organization_id == org.id,
        UsageRecord.usage_type == 'message_sent',
        UsageRecord.created_at >= month_start
    ).count()
    
    api_calls_this_month = UsageRecord.query.filter(
        UsageRecord.organization_id == org.id,
        UsageRecord.usage_type == 'api_call',
        UsageRecord.created_at >= month_start
    ).count()
    
    # Calculate percentages
    max_leads = plan_config.get('max_leads', 0)
    max_messages_per_day = plan_config.get('max_contacts_per_day', 0)
    
    leads_percent = (leads_this_month / max_leads * 100) if max_leads > 0 else 0
    messages_percent = (messages_today / max_messages_per_day * 100) if max_messages_per_day > 0 else 0
    
    # Get usage history (last 30 days)
    thirty_days_ago = now - timedelta(days=30)
    
    daily_usage = defaultdict(lambda: {'leads': 0, 'messages': 0, 'api_calls': 0})
    
    records = UsageRecord.query.filter(
        UsageRecord.organization_id == org.id,
        UsageRecord.created_at >= thirty_days_ago
    ).order_by(UsageRecord.created_at).all()
    
    for record in records:
        date_key = record.created_at.date().isoformat()
        if record.usage_type == 'lead_created':
            daily_usage[date_key]['leads'] += record.quantity
        elif record.usage_type == 'message_sent':
            daily_usage[date_key]['messages'] += record.quantity
        elif record.usage_type == 'api_call':
            daily_usage[date_key]['api_calls'] += record.quantity
    
    # Convert to lists for chart
    dates = sorted(daily_usage.keys())
    leads_data = [daily_usage[d]['leads'] for d in dates]
    messages_data = [daily_usage[d]['messages'] for d in dates]
    api_calls_data = [daily_usage[d]['api_calls'] for d in dates]
    
    # Get recent usage (last 10 records)
    recent_usage = UsageRecord.query.filter(
        UsageRecord.organization_id == org.id
    ).order_by(UsageRecord.created_at.desc()).limit(10).all()
    
    # Check if approaching limits
    warnings = []
    if max_leads > 0 and leads_percent >= 90:
        warnings.append({
            'type': 'danger',
            'message': f'You\'ve used {leads_this_month}/{max_leads} leads this month ({leads_percent:.0f}%). Consider upgrading!'
        })
    elif max_leads > 0 and leads_percent >= 75:
        warnings.append({
            'type': 'warning',
            'message': f'You\'ve used {leads_this_month}/{max_leads} leads this month ({leads_percent:.0f}%).'
        })
    
    if max_messages_per_day > 0 and messages_percent >= 90:
        warnings.append({
            'type': 'danger',
            'message': f'You\'ve sent {messages_today}/{max_messages_per_day} messages today ({messages_percent:.0f}%).'
        })
    elif max_messages_per_day > 0 and messages_percent >= 75:
        warnings.append({
            'type': 'warning',
            'message': f'You\'ve sent {messages_today}/{max_messages_per_day} messages today ({messages_percent:.0f}%).'
        })
    
    return render_template(
        'usage/dashboard.html',
        organization=org,
        subscription=subscription,
        plan_config=plan_config,
        leads_this_month=leads_this_month,
        messages_today=messages_today,
        messages_this_month=messages_this_month,
        api_calls_this_month=api_calls_this_month,
        max_leads=max_leads,
        max_messages_per_day=max_messages_per_day,
        leads_percent=leads_percent,
        messages_percent=messages_percent,
        dates=dates,
        leads_data=leads_data,
        messages_data=messages_data,
        api_calls_data=api_calls_data,
        recent_usage=recent_usage,
        warnings=warnings,
        month_start=month_start,
        today_start=today_start
    )


@usage_bp.route('/api/stats')
@login_required
def usage_stats_api():
    """API endpoint for usage statistics"""
    org = get_user_organization()
    if not org:
        return jsonify({'error': 'No organization'}), 403
    
    subscription = org.subscription
    if not subscription:
        return jsonify({'error': 'No subscription'}), 403
    
    plan_config = PLAN_CONFIGS.get(subscription.plan, {})
    
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    leads_this_month = UsageRecord.query.filter(
        UsageRecord.organization_id == org.id,
        UsageRecord.usage_type == 'lead_created',
        UsageRecord.created_at >= month_start
    ).count()
    
    messages_today = UsageRecord.query.filter(
        UsageRecord.organization_id == org.id,
        UsageRecord.usage_type == 'message_sent',
        UsageRecord.created_at >= today_start
    ).count()
    
    messages_this_month = UsageRecord.query.filter(
        UsageRecord.organization_id == org.id,
        UsageRecord.usage_type == 'message_sent',
        UsageRecord.created_at >= month_start
    ).count()
    
    api_calls_this_month = UsageRecord.query.filter(
        UsageRecord.organization_id == org.id,
        UsageRecord.usage_type == 'api_call',
        UsageRecord.created_at >= month_start
    ).count()
    
    max_leads = plan_config.get('max_leads', 0)
    max_messages_per_day = plan_config.get('max_contacts_per_day', 0)
    
    return jsonify({
        'leads': {
            'used': leads_this_month,
            'limit': max_leads,
            'percent': (leads_this_month / max_leads * 100) if max_leads > 0 else 0
        },
        'messages_today': {
            'used': messages_today,
            'limit': max_messages_per_day,
            'percent': (messages_today / max_messages_per_day * 100) if max_messages_per_day > 0 else 0
        },
        'messages_month': {
            'used': messages_this_month,
            'limit': -1  # Unlimited per month
        },
        'api_calls': {
            'used': api_calls_this_month,
            'limit': -1  # Based on plan
        }
    })


@usage_bp.route('/history')
@login_required
def usage_history():
    """Detailed usage history"""
    org = get_user_organization()
    if not org:
        flash('You need to be part of an organization to view usage history.', 'warning')
        return redirect(url_for('main.index'))
    
    # Get filters
    usage_type = request.args.get('type', 'all')
    days = request.args.get('days', 30, type=int)
    
    # Build query
    query = UsageRecord.query.filter(
        UsageRecord.organization_id == org.id
    )
    
    if usage_type != 'all':
        query = query.filter(UsageRecord.usage_type == usage_type)
    
    # Date filter
    date_from = datetime.now(timezone.utc) - timedelta(days=days)
    query = query.filter(UsageRecord.created_at >= date_from)
    
    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = 50
    pagination = query.order_by(UsageRecord.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    records = pagination.items
    
    # Group by type for summary
    summary = defaultdict(int)
    for record in records:
        summary[record.usage_type] += record.quantity
    
    return render_template(
        'usage/history.html',
        organization=org,
        records=records,
        pagination=pagination,
        usage_type=usage_type,
        days=days,
        summary=dict(summary)
    )
