"""
Team Collaboration Routes
Invite members, manage roles, and permissions
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, abort
from sqlalchemy.exc import SQLAlchemyError
import logging

logger = logging.getLogger(__name__)
from flask_login import login_required, current_user
from models import db, User
from models_saas import (
    Organization, OrganizationMember, OrganizationRole, Subscription,
    OrganizationMember
)
from datetime import datetime, timezone
import secrets
import string

team_bp = Blueprint('team', __name__, url_prefix='/team')


def get_user_organization():
    """Get current user's organization"""
    member = OrganizationMember.query.filter_by(
        user_id=current_user.id,
        is_active=True
    ).first()
    
    if not member:
        return None, None
    
    return member.organization, member


def require_org_access():
    """Require user to have organization access"""
    org, member = get_user_organization()
    if not org:
        flash('You need to be part of an organization to access team features.', 'warning')
        return None, None
    return org, member


def require_team_permission(org, member):
    """Require user to have team management permission"""
    if not member or not member.can_manage_team:
        flash('You do not have permission to manage team members.', 'danger')
        return False
    return True


@team_bp.route('/')
@login_required
def team_dashboard():
    """Team dashboard - view all members"""
    org, member = require_org_access()
    if not org:
        return redirect(url_for('main.index'))
    
    # Get all active members
    members = OrganizationMember.query.filter_by(
        organization_id=org.id,
        is_active=True
    ).all()
    
    # Get subscription to check user limit
    subscription = org.subscription
    max_users = subscription.max_users if subscription else 1
    
    # Check if can add more users
    can_add_member = subscription.can_add_user() if subscription else False
    
    return render_template(
        'team/dashboard.html',
        organization=org,
        members=members,
        current_member=member,
        max_users=max_users,
        can_add_member=can_add_member,
        can_manage_team=member.can_manage_team if member else False
    )


@team_bp.route('/invite', methods=['GET', 'POST'])
@login_required
def invite_member():
    """Invite a new team member"""
    org, member = require_org_access()
    if not org:
        return redirect(url_for('team.team_dashboard'))
    
    if not require_team_permission(org, member):
        return redirect(url_for('team.team_dashboard'))
    
    # Check subscription limits
    subscription = org.subscription
    if not subscription or not subscription.can_add_user():
        flash(f'You have reached your user limit ({subscription.max_users} users). Please upgrade your plan to add more members.', 'warning')
        return redirect(url_for('team.team_dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        username = request.form.get('username', '').strip()
        role_str = request.form.get('role', 'member')
        
        # Try username first, then email
        user = None
        if username:
            user = User.query.filter_by(username=username).first()
        elif email:
            user = User.query.filter_by(email=email).first()
        
        if not user:
            flash(f'User not found. Please check the email/username or ask them to register first.', 'warning')
            return render_template('team/invite.html', organization=org, email=email or username)
        
        # Validate role
        try:
            role = OrganizationRole(role_str)
        except ValueError:
            role = OrganizationRole.MEMBER
        
        # Check if user is already a member
        existing_member = OrganizationMember.query.filter_by(
            organization_id=org.id,
            user_id=user.id
        ).first()
        
        if existing_member:
            if existing_member.is_active:
                flash('This user is already a member of your organization.', 'warning')
            else:
                # Reactivate member
                existing_member.is_active = True
                existing_member.role = role
                existing_member.joined_at = datetime.now(timezone.utc)
                try:
                    db.session.commit()
                    flash('Member reactivated successfully.', 'success')
                except SQLAlchemyError as e:
                    db.session.rollback()
                    logger.exception("Error reactivating member")
                    flash('Error reactivating member. Please try again.', 'danger')
            return redirect(url_for('team.team_dashboard'))
        
        # User exists - add directly
        new_member = OrganizationMember(
            organization_id=org.id,
            user_id=user.id,
            role=role,
            can_manage_leads=True,
            can_send_messages=True,
            can_view_analytics=True,
            can_manage_templates=role in [OrganizationRole.OWNER, OrganizationRole.ADMIN],
            can_manage_team=role in [OrganizationRole.OWNER, OrganizationRole.ADMIN],
            can_manage_billing=role == OrganizationRole.OWNER,
            joined_at=datetime.now(timezone.utc)
        )
        try:
            db.session.add(new_member)
            db.session.commit()
            flash(f'{user.username} has been added to your team!', 'success')
            return redirect(url_for('team.team_dashboard'))
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.exception("Error adding team member")
            flash('Error adding team member. Please try again.', 'danger')
            return redirect(url_for('team.team_dashboard'))
    
    return render_template('team/invite.html', organization=org)


@team_bp.route('/member/<int:member_id>/update', methods=['POST'])
@login_required
def update_member(member_id):
    """Update member role and permissions"""
    org, member = require_org_access()
    if not org:
        return jsonify({'success': False, 'error': 'No organization'}), 403
    
    if not require_team_permission(org, member):
        return jsonify({'success': False, 'error': 'No permission'}), 403
    
    target_member = db.session.get(OrganizationMember, member_id)
    if not target_member:
        abort(404)
    
    # Can't modify yourself if you're the only owner
    if target_member.id == member.id and member.role == OrganizationRole.OWNER:
        owner_count = OrganizationMember.query.filter_by(
            organization_id=org.id,
            role=OrganizationRole.OWNER,
            is_active=True
        ).count()
        if owner_count == 1:
            return jsonify({'success': False, 'error': 'Cannot change your own role. You are the only owner.'}), 400
    
    # Can't modify owners unless you're an owner
    if target_member.role == OrganizationRole.OWNER and member.role != OrganizationRole.OWNER:
        return jsonify({'success': False, 'error': 'Only owners can modify other owners.'}), 403
    
    # Update role
    new_role_str = request.json.get('role')
    if new_role_str:
        try:
            new_role = OrganizationRole(new_role_str)
            target_member.role = new_role
            
            # Update permissions based on role
            if new_role == OrganizationRole.OWNER:
                target_member.can_manage_leads = True
                target_member.can_send_messages = True
                target_member.can_view_analytics = True
                target_member.can_manage_templates = True
                target_member.can_manage_team = True
                target_member.can_manage_billing = True
            elif new_role == OrganizationRole.ADMIN:
                target_member.can_manage_leads = True
                target_member.can_send_messages = True
                target_member.can_view_analytics = True
                target_member.can_manage_templates = True
                target_member.can_manage_team = True
                target_member.can_manage_billing = False
            elif new_role == OrganizationRole.MEMBER:
                target_member.can_manage_leads = True
                target_member.can_send_messages = True
                target_member.can_view_analytics = True
                target_member.can_manage_templates = False
                target_member.can_manage_team = False
                target_member.can_manage_billing = False
            else:  # VIEWER
                target_member.can_manage_leads = False
                target_member.can_send_messages = False
                target_member.can_view_analytics = True
                target_member.can_manage_templates = False
                target_member.can_manage_team = False
                target_member.can_manage_billing = False
        except ValueError:
            pass
    
    # Update individual permissions if provided
    permissions = request.json.get('permissions', {})
    if 'can_manage_leads' in permissions:
        target_member.can_manage_leads = permissions['can_manage_leads']
    if 'can_send_messages' in permissions:
        target_member.can_send_messages = permissions['can_send_messages']
    if 'can_view_analytics' in permissions:
        target_member.can_view_analytics = permissions['can_view_analytics']
    if 'can_manage_templates' in permissions:
        target_member.can_manage_templates = permissions['can_manage_templates']
    if 'can_manage_team' in permissions:
        target_member.can_manage_team = permissions['can_manage_team']
    if 'can_manage_billing' in permissions:
        # Only owners can have billing permission
        if member.role == OrganizationRole.OWNER:
            target_member.can_manage_billing = permissions['can_manage_billing']
    
    try:
        db.session.commit()
        return jsonify({'success': True, 'message': 'Member updated successfully'})
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.exception("Error updating member")
        return jsonify({'success': False, 'error': 'Failed to update member'}), 500


@team_bp.route('/member/<int:member_id>/remove', methods=['POST'])
@login_required
def remove_member(member_id):
    """Remove a team member"""
    org, member = require_org_access()
    if not org:
        return jsonify({'success': False, 'error': 'No organization'}), 403
    
    if not require_team_permission(org, member):
        return jsonify({'success': False, 'error': 'No permission'}), 403
    
    target_member = db.session.get(OrganizationMember, member_id)
    if not target_member:
        abort(404)
    
    # Can't remove yourself
    if target_member.id == member.id:
        return jsonify({'success': False, 'error': 'Cannot remove yourself. Leave the organization instead.'}), 400
    
    # Can't remove the only owner
    if target_member.role == OrganizationRole.OWNER:
        owner_count = OrganizationMember.query.filter_by(
            organization_id=org.id,
            role=OrganizationRole.OWNER,
            is_active=True
        ).count()
        if owner_count == 1:
            return jsonify({'success': False, 'error': 'Cannot remove the only owner. Transfer ownership first.'}), 400
    
    # Deactivate instead of delete (soft delete)
    try:
        target_member.is_active = False
        db.session.commit()
        return jsonify({'success': True, 'message': 'Member removed successfully'})
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.exception("Error removing member")
        return jsonify({'success': False, 'error': 'Failed to remove member'}), 500


@team_bp.route('/member/<int:member_id>/transfer-ownership', methods=['POST'])
@login_required
def transfer_ownership(member_id):
    """Transfer organization ownership"""
    org, member = require_org_access()
    if not org:
        return jsonify({'success': False, 'error': 'No organization'}), 403
    
    # Only current owner can transfer
    if member.role != OrganizationRole.OWNER:
        return jsonify({'success': False, 'error': 'Only the owner can transfer ownership'}), 403
    
    new_owner = db.session.get(OrganizationMember, member_id)
    if not new_owner:
        abort(404)
    
    if not new_owner.is_active or new_owner.organization_id != org.id:
        return jsonify({'success': False, 'error': 'Invalid member'}), 400
    
    # Transfer ownership
    member.role = OrganizationRole.ADMIN
    member.can_manage_billing = False
    
    new_owner.role = OrganizationRole.OWNER
    new_owner.can_manage_team = True
    new_owner.can_manage_billing = True
    new_owner.can_manage_templates = True
    
    try:
        db.session.commit()
        return jsonify({'success': True, 'message': 'Ownership transferred successfully'})


@team_bp.route('/leave', methods=['POST'])
@login_required
def leave_organization():
    """Leave the organization"""
    org, member = require_org_access()
    if not org:
        return jsonify({'success': False, 'error': 'No organization'}), 403
    
    # Can't leave if you're the only owner
    if member.role == OrganizationRole.OWNER:
        owner_count = OrganizationMember.query.filter_by(
            organization_id=org.id,
            role=OrganizationRole.OWNER,
            is_active=True
        ).count()
        if owner_count == 1:
            return jsonify({'success': False, 'error': 'Cannot leave. You are the only owner. Transfer ownership or delete the organization first.'}), 400
    
    # Deactivate membership
    try:
        member.is_active = False
        db.session.commit()
        return jsonify({'success': True, 'message': 'Left organization successfully'})
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.exception("Error leaving organization")
        return jsonify({'success': False, 'error': 'Failed to leave organization'}), 500
    
    flash('You have left the organization.', 'info')
    return jsonify({'success': True, 'redirect': url_for('main.index')})


@team_bp.route('/activity')
@login_required
def team_activity():
    """View team activity log"""
    org, member = require_org_access()
    if not org:
        return redirect(url_for('main.index'))
    
    # Get recent activity from usage records
    from models_saas import UsageRecord
    from datetime import timedelta
    
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    
    # Get activity for all team members
    member_ids = [m.user_id for m in org.members.filter_by(is_active=True).all() if m.user_id]
    
    activity = UsageRecord.query.filter(
        UsageRecord.organization_id == org.id,
        UsageRecord.created_at >= thirty_days_ago
    )
    
    if member_ids:
        activity = activity.filter(UsageRecord.user_id.in_(member_ids))
    
    activity = activity.order_by(UsageRecord.created_at.desc()).limit(100).all()
    
    # Group by user
    from collections import defaultdict
    user_activity = defaultdict(list)
    for record in activity:
        if record.user_id:
            user_activity[record.user_id].append(record)
    
    return render_template(
        'team/activity.html',
        organization=org,
        activity=activity,
        user_activity=dict(user_activity),
        members={m.user_id: m for m in org.members.filter_by(is_active=True).all()}
    )
