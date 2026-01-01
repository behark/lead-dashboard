"""
Usage Tracking Utilities
Helper functions to record usage automatically
"""
from models_saas import UsageRecord, OrganizationMember
from models import db
from flask_login import current_user


def record_lead_created(lead):
    """Record when a lead is created"""
    if not lead.organization_id:
        return
    
    # Get user's organization if lead doesn't have one
    if not lead.organization_id and current_user.is_authenticated:
        member = OrganizationMember.query.filter_by(
            user_id=current_user.id,
            is_active=True
        ).first()
        if member:
            lead.organization_id = member.organization_id
            db.session.commit()
    
    if lead.organization_id:
        UsageRecord.record_usage(
            organization_id=lead.organization_id,
            usage_type='lead_created',
            user_id=current_user.id if current_user.is_authenticated else None,
            resource_id=lead.id,
            quantity=1
        )


def record_message_sent(lead, user_id=None):
    """Record when a message is sent"""
    if not lead.organization_id:
        return
    
    UsageRecord.record_usage(
        organization_id=lead.organization_id,
        usage_type='message_sent',
        user_id=user_id,
        resource_id=lead.id,
        quantity=1
    )


def record_api_call(organization_id, user_id=None, endpoint=None):
    """Record API call usage"""
    UsageRecord.record_usage(
        organization_id=organization_id,
        usage_type='api_call',
        user_id=user_id,
        extra_data={'endpoint': endpoint} if endpoint else None,
        quantity=1
    )


def check_usage_limits(organization_id, usage_type):
    """
    Check if organization can perform an action based on usage limits
    
    Returns:
        (can_proceed, message) tuple
    """
    from models_saas import Organization
    
    org = db.session.get(Organization, organization_id)
    if not org or not org.subscription:
        return True, None
    
    sub = org.subscription
    
    if usage_type == 'lead_created':
        if not sub.can_add_lead():
            return False, f"You've reached your limit of {sub.max_leads} leads this month. Please upgrade your plan."
    
    elif usage_type == 'message_sent':
        if not sub.can_send_message():
            return False, f"You've reached your daily limit of {sub.max_contacts_per_day} messages. Please upgrade your plan."
    
    return True, None
