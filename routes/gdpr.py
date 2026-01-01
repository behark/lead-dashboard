"""
GDPR Compliance Routes
Data export, deletion, consent management
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file, make_response, abort
from sqlalchemy.exc import SQLAlchemyError
import logging

logger = logging.getLogger(__name__)
from flask_login import login_required, current_user
from models import db, Lead, ContactLog, User
from models_saas import Organization, OrganizationMember
from datetime import datetime, timezone
import json
import csv
import io
from zipfile import ZipFile

gdpr_bp = Blueprint('gdpr', __name__, url_prefix='/gdpr')


def get_user_organization():
    """Get current user's organization"""
    member = OrganizationMember.query.filter_by(
        user_id=current_user.id,
        is_active=True
    ).first()
    
    if not member:
        return None, None
    
    return member.organization, member


@gdpr_bp.route('/')
@login_required
def gdpr_dashboard():
    """GDPR compliance dashboard"""
    org, member = get_user_organization()
    if not org:
        flash('You need to be part of an organization.', 'warning')
        return redirect(url_for('main.index'))
    
    # Get consent statistics
    total_leads = Lead.query.filter_by(organization_id=org.id).count()
    consented_leads = Lead.query.filter_by(
        organization_id=org.id,
        gdpr_consent=True
    ).count()
    opted_out = Lead.query.filter_by(
        organization_id=org.id,
        marketing_opt_out=True
    ).count()
    
    return render_template(
        'gdpr/dashboard.html',
        organization=org,
        total_leads=total_leads,
        consented_leads=consented_leads,
        opted_out=opted_out,
        consent_rate=(consented_leads / total_leads * 100) if total_leads > 0 else 0
    )


@gdpr_bp.route('/export')
@login_required
def export_data():
    """Export all organization data (GDPR right to data portability)"""
    org, member = get_user_organization()
    if not org:
        flash('You need to be part of an organization.', 'warning')
        return redirect(url_for('main.index'))
    
    # Only owners and admins can export
    if not member.can_manage_team:
        flash('You do not have permission to export data.', 'danger')
        return redirect(url_for('gdpr.gdpr_dashboard'))
    
    # Create in-memory zip file
    zip_buffer = io.BytesIO()
    
    with ZipFile(zip_buffer, 'w') as zip_file:
        # Export leads
        leads = Lead.query.filter_by(organization_id=org.id).all()
        leads_data = []
        for lead in leads:
            leads_data.append({
                'id': lead.id,
                'name': lead.name,
                'phone': lead.phone,
                'email': lead.email,
                'address': lead.address,
                'city': lead.city,
                'country': lead.country,
                'category': lead.category,
                'status': lead.status.value if lead.status else None,
                'temperature': lead.temperature.value if lead.temperature else None,
                'lead_score': lead.lead_score,
                'rating': lead.rating,
                'notes': lead.notes,
                'gdpr_consent': lead.gdpr_consent,
                'marketing_opt_out': lead.marketing_opt_out,
                'created_at': lead.created_at.isoformat() if lead.created_at else None,
                'last_contacted': lead.last_contacted.isoformat() if lead.last_contacted else None
            })
        
        leads_json = json.dumps(leads_data, indent=2)
        zip_file.writestr('leads.json', leads_json)
        
        # Export leads as CSV
        csv_buffer = io.StringIO()
        if leads_data:
            writer = csv.DictWriter(csv_buffer, fieldnames=leads_data[0].keys())
            writer.writeheader()
            writer.writerows(leads_data)
            zip_file.writestr('leads.csv', csv_buffer.getvalue())
        
        # Export contact logs
        contact_logs = ContactLog.query.join(Lead).filter(
            Lead.organization_id == org.id
        ).all()
        
        logs_data = []
        for log in contact_logs:
            logs_data.append({
                'id': log.id,
                'lead_id': log.lead_id,
                'channel': log.channel.value if log.channel else None,
                'message_content': log.message_content,
                'sent_at': log.sent_at.isoformat() if log.sent_at else None,
                'delivered_at': log.delivered_at.isoformat() if log.delivered_at else None,
                'is_automated': log.is_automated
            })
        
        logs_json = json.dumps(logs_data, indent=2)
        zip_file.writestr('contact_logs.json', logs_json)
        
        # Export organization info
        org_data = {
            'organization_id': org.id,
            'organization_name': org.name,
            'organization_slug': org.slug,
            'export_date': datetime.now(timezone.utc).isoformat(),
            'exported_by': current_user.username,
            'total_leads': len(leads_data),
            'total_contact_logs': len(logs_data)
        }
        
        org_json = json.dumps(org_data, indent=2)
        zip_file.writestr('organization_info.json', org_json)
    
    zip_buffer.seek(0)
    
    # Create response
    response = make_response(zip_buffer.getvalue())
    response.headers['Content-Type'] = 'application/zip'
    response.headers['Content-Disposition'] = f'attachment; filename=gdpr_export_{org.slug}_{datetime.now(timezone.utc).strftime("%Y%m%d")}.zip'
    
    return response


@gdpr_bp.route('/delete-lead/<int:lead_id>', methods=['POST'])
@login_required
def delete_lead_data(lead_id):
    """Delete lead data (GDPR right to be forgotten)"""
    org, member = get_user_organization()
    if not org:
        return jsonify({'success': False, 'error': 'No organization'}), 403
    
    lead = db.session.get(Lead, lead_id)
    if not lead:
        abort(404)
    
    # Verify lead belongs to organization
    if lead.organization_id != org.id:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    # Delete contact logs
    ContactLog.query.filter_by(lead_id=lead_id).delete()
    
    # Delete lead
    try:
        db.session.delete(lead)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Lead data deleted successfully'})
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.exception("Error deleting lead data")
        return jsonify({'success': False, 'error': 'Failed to delete lead data'}), 500


@gdpr_bp.route('/bulk-delete', methods=['POST'])
@login_required
def bulk_delete_data():
    """Bulk delete leads (GDPR right to be forgotten)"""
    org, member = get_user_organization()
    if not org:
        return jsonify({'success': False, 'error': 'No organization'}), 403
    
    # Only owners can bulk delete
    if member.role.value != 'owner':
        return jsonify({'success': False, 'error': 'Only owners can perform bulk deletion'}), 403
    
    lead_ids = request.json.get('lead_ids', [])
    
    if not lead_ids:
        return jsonify({'success': False, 'error': 'No leads selected'}), 400
    
    # Verify all leads belong to organization
    leads = Lead.query.filter(
        Lead.id.in_(lead_ids),
        Lead.organization_id == org.id
    ).all()
    
    if len(leads) != len(lead_ids):
        return jsonify({'success': False, 'error': 'Some leads not found or unauthorized'}), 400
    
    # Delete contact logs
    ContactLog.query.filter(ContactLog.lead_id.in_(lead_ids)).delete(synchronize_session=False)
    
    # Delete leads
    try:
        for lead in leads:
            db.session.delete(lead)
        
        db.session.commit()
        return jsonify({
            'success': True,
            'message': f'{len(leads)} leads deleted successfully',
            'deleted_count': len(leads)
        })
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.exception("Error bulk deleting leads")
        return jsonify({'success': False, 'error': 'Failed to delete leads'}), 500


@gdpr_bp.route('/consent/<int:lead_id>', methods=['POST'])
@login_required
def update_consent(lead_id):
    """Update GDPR consent status"""
    org, member = get_user_organization()
    if not org:
        return jsonify({'success': False, 'error': 'No organization'}), 403
    
    lead = db.session.get(Lead, lead_id)
    if not lead:
        abort(404)
    
    # Verify lead belongs to organization
    if lead.organization_id != org.id:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    consent = request.json.get('consent', False)
    lead.gdpr_consent = consent
    
    if not consent:
        # If consent withdrawn, also opt out of marketing
        lead.marketing_opt_out = True
        lead.opt_out_date = datetime.now(timezone.utc)
    
    try:
        db.session.commit()
        return jsonify({'success': True, 'message': 'Consent updated successfully'})
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.exception("Error updating consent")
        return jsonify({'success': False, 'error': 'Failed to update consent'}), 500


@gdpr_bp.route('/consent-banner')
def consent_banner():
    """Cookie consent banner component"""
    return render_template('gdpr/consent_banner.html')


@gdpr_bp.route('/privacy-policy')
def privacy_policy():
    """Privacy policy page"""
    return render_template('gdpr/privacy_policy.html')


@gdpr_bp.route('/terms-of-service')
def terms_of_service():
    """Terms of service page"""
    return render_template('gdpr/terms_of_service.html')


@gdpr_bp.route('/cookie-policy')
def cookie_policy():
    """Cookie policy page"""
    return render_template('gdpr/cookie_policy.html')
