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
        
        # Get template (fallback to default for channel)
        template = None
        if template_id:
            template = MessageTemplate.query.get(template_id)
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

            # Send based on channel
            result = None
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
    # Get leads that can be contacted (not opted out, have consent)
    leads = Lead.query.filter(
        Lead.status.in_([LeadStatus.NEW]),
        Lead.phone.isnot(None),
        Lead.phone != '',
        Lead.marketing_opt_out == False,
        Lead.gdpr_consent == True
    ).order_by(Lead.lead_score.desc()).limit(500).all()
    
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
    
    lead = Lead.query.get(lead_id)
    if not lead:
        return jsonify({'error': 'Lead not found'}), 404
    
    template = None
    if template_id:
        template = MessageTemplate.query.get(template_id)
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
    leads = Lead.query.filter(
        Lead.status.in_([LeadStatus.NEW]),
        Lead.phone.isnot(None),
        Lead.phone != '',
        Lead.marketing_opt_out == False,
        Lead.gdpr_consent == True
    ).order_by(Lead.lead_score.desc()).limit(500).all()
    
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
