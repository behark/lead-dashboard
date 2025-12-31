"""
Bulk operations routes - Send messages to multiple leads
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db, Lead, ContactLog, MessageTemplate, LeadStatus, LeadTemperature, ContactChannel, UserRole
from services.contact_service import ContactService
from services.phone_service import format_phone_international, validate_phone
from datetime import datetime, timezone
import time

bulk_bp = Blueprint('bulk', __name__, url_prefix='/bulk')

# Rate limiting settings
MESSAGES_PER_BATCH = 30
DELAY_BETWEEN_MESSAGES = 2  # seconds
MAX_DAILY_MESSAGES = 200


@bulk_bp.route('/send', methods=['GET', 'POST'])
@login_required
def bulk_send():
    """Bulk send page - select leads and send messages"""
    
    if request.method == 'POST':
        lead_ids = request.form.getlist('lead_ids')
        template_id = request.form.get('template_id')
        channel = request.form.get('channel', 'whatsapp')
        dry_run = request.form.get('dry_run') == 'on'
        
        if not lead_ids:
            flash('No leads selected.', 'warning')
            return redirect(url_for('bulk.bulk_send'))
        
        # Get leads
        leads = Lead.query.filter(Lead.id.in_(lead_ids)).all()
        
        # Get template
        template = None
        if template_id:
            template = MessageTemplate.query.get(template_id)
        
        results = {
            'total': len(leads),
            'sent': 0,
            'failed': 0,
            'skipped': 0,
            'errors': []
        }
        
        for i, lead in enumerate(leads):
            # Rate limiting
            if i > 0 and i % MESSAGES_PER_BATCH == 0:
                if not dry_run:
                    time.sleep(DELAY_BETWEEN_MESSAGES * 10)  # Longer pause between batches
            
            # Validate phone
            is_valid, error = validate_phone(lead.phone, lead.country)
            if not is_valid:
                results['skipped'] += 1
                results['errors'].append(f"{lead.name}: {error}")
                continue
            
            # Get message
            if template:
                message = ContactService.personalize_message(template.content, lead)
            else:
                message = lead.first_message or f"Hi! I saw {lead.name} on Google and wanted to reach out."
            
            if dry_run:
                results['sent'] += 1
                continue
            
            # Send based on channel
            result = None
            if channel == 'whatsapp':
                result = ContactService.send_whatsapp(
                    lead, message,
                    template_id=template_id,
                    user_id=current_user.id
                )
            elif channel == 'email':
                subject = template.subject if template and template.subject else f"Hello from a business partner"
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
                results['sent'] += 1
            else:
                results['failed'] += 1
                error = result.get('error', 'Unknown error') if result else 'Send failed'
                results['errors'].append(f"{lead.name}: {error}")
            
            # Rate limiting between messages
            if not dry_run:
                time.sleep(DELAY_BETWEEN_MESSAGES)
        
        if dry_run:
            flash(f"DRY RUN: Would send to {results['sent']} leads. Skipped: {results['skipped']}", 'info')
        else:
            flash(f"Sent: {results['sent']}, Failed: {results['failed']}, Skipped: {results['skipped']}", 
                  'success' if results['failed'] == 0 else 'warning')
        
        return render_template('bulk/results.html', results=results)
    
    # GET - Show selection page
    # Get leads that can be contacted
    leads = Lead.query.filter(
        Lead.status.in_([LeadStatus.NEW]),
        Lead.phone.isnot(None),
        Lead.phone != ''
    ).order_by(Lead.lead_score.desc()).limit(500).all()
    
    # Get templates
    templates = MessageTemplate.query.filter_by(is_active=True).all()
    
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
        templates=templates
    )


@bulk_bp.route('/preview', methods=['POST'])
@login_required
def preview_message():
    """Preview personalized message for a lead"""
    
    lead_id = request.form.get('lead_id')
    template_id = request.form.get('template_id')
    
    lead = Lead.query.get(lead_id)
    if not lead:
        return jsonify({'error': 'Lead not found'}), 404
    
    if template_id:
        template = MessageTemplate.query.get(template_id)
        if template:
            message = ContactService.personalize_message(template.content, lead)
        else:
            message = lead.first_message or ''
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
