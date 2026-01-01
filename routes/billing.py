"""
Billing and Subscription Routes
Handles Stripe checkout, subscription management, and billing portal
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from models import db
from models_saas import (
    Organization, Subscription, Invoice, SubscriptionPlan, SubscriptionStatus,
    OrganizationMember, OrganizationRole, PLAN_CONFIGS
)
from services.stripe_service import StripeService
from datetime import datetime, timezone

billing_bp = Blueprint('billing', __name__, url_prefix='/billing')


def get_user_organization():
    """Get current user's organization"""
    member = OrganizationMember.query.filter_by(
        user_id=current_user.id,
        is_active=True
    ).first()
    
    if not member:
        return None
    
    return member.organization


def require_org_access():
    """Require user to have organization access"""
    org = get_user_organization()
    if not org:
        flash('You need to be part of an organization to access billing.', 'warning')
        return None
    return org


def require_billing_permission(org):
    """Require user to have billing management permission"""
    member = OrganizationMember.query.filter_by(
        organization_id=org.id,
        user_id=current_user.id,
        is_active=True
    ).first()
    
    if not member or not member.can_manage_billing:
        flash('You do not have permission to manage billing.', 'danger')
        return False
    
    return True


@billing_bp.route('/')
@login_required
def billing_dashboard():
    """Billing dashboard - view subscription, usage, invoices"""
    org = require_org_access()
    if not org:
        return redirect(url_for('main.index'))
    
    subscription = org.subscription
    if not subscription:
        flash('No subscription found. Please contact support.', 'warning')
        return redirect(url_for('main.index'))
    
    # Get invoices
    invoices = Invoice.query.filter_by(
        organization_id=org.id
    ).order_by(Invoice.issued_at.desc()).limit(10).all()
    
    # Get usage stats
    from models_saas import UsageRecord
    from datetime import datetime, timezone
    
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    leads_this_month = UsageRecord.query.filter(
        UsageRecord.organization_id == org.id,
        UsageRecord.usage_type == 'lead_created',
        UsageRecord.created_at >= month_start
    ).count()
    
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    messages_today = UsageRecord.query.filter(
        UsageRecord.organization_id == org.id,
        UsageRecord.usage_type == 'message_sent',
        UsageRecord.created_at >= today_start
    ).count()
    
    # Plan config
    plan_config = PLAN_CONFIGS.get(subscription.plan, {})
    
    return render_template(
        'billing/dashboard.html',
        organization=org,
        subscription=subscription,
        invoices=invoices,
        plan_config=plan_config,
        leads_this_month=leads_this_month,
        messages_today=messages_today,
        can_manage_billing=require_billing_permission(org) if org else False
    )


@billing_bp.route('/plans')
@login_required
def pricing():
    """Pricing page - view all plans and upgrade"""
    org = require_org_access()
    if not org:
        return redirect(url_for('main.index'))
    
    current_plan = org.subscription.plan if org.subscription else SubscriptionPlan.FREE
    
    return render_template(
        'billing/pricing.html',
        organization=org,
        current_plan=current_plan,
        plans=PLAN_CONFIGS,
        can_manage_billing=require_billing_permission(org) if org else False
    )


@billing_bp.route('/subscribe/<plan>')
@login_required
def subscribe(plan):
    """Start subscription checkout for a plan"""
    org = require_org_access()
    if not org:
        return redirect(url_for('main.index'))
    
    if not require_billing_permission(org):
        return redirect(url_for('billing.billing_dashboard'))
    
    # Validate plan
    try:
        plan_enum = SubscriptionPlan(plan)
    except ValueError:
        flash('Invalid plan selected.', 'danger')
        return redirect(url_for('billing.pricing'))
    
    # Check if already on this plan
    if org.subscription and org.subscription.plan == plan_enum:
        flash(f'You are already on the {plan_enum.value} plan.', 'info')
        return redirect(url_for('billing.billing_dashboard'))
    
    # Get billing cycle
    billing_cycle = request.args.get('cycle', 'monthly')
    if billing_cycle not in ['monthly', 'yearly']:
        billing_cycle = 'monthly'
    
    # Create checkout session
    session = StripeService.create_checkout_session(
        organization=org,
        plan=plan_enum,
        billing_cycle=billing_cycle
    )
    
    if not session:
        flash('Error creating checkout session. Please try again or contact support.', 'danger')
        return redirect(url_for('billing.pricing'))
    
    # Redirect to Stripe Checkout
    return redirect(session.url)


@billing_bp.route('/success')
@login_required
def checkout_success():
    """Handle successful checkout"""
    session_id = request.args.get('session_id')
    
    if not session_id:
        flash('No session ID provided.', 'warning')
        return redirect(url_for('billing.billing_dashboard'))
    
    # Verify session with Stripe
    if StripeService.init_stripe():
        import stripe
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            if session.payment_status == 'paid':
                flash('Payment successful! Your subscription is now active.', 'success')
            else:
                flash('Payment is being processed. You will receive an email when it completes.', 'info')
        except Exception as e:
            flash('Payment received. Processing...', 'info')
    
    return redirect(url_for('billing.billing_dashboard'))


@billing_bp.route('/cancel')
@login_required
def checkout_cancel():
    """Handle canceled checkout"""
    flash('Checkout was canceled. No charges were made.', 'info')
    return redirect(url_for('billing.pricing'))


@billing_bp.route('/portal')
@login_required
def customer_portal():
    """Access Stripe Customer Portal for subscription management"""
    org = require_org_access()
    if not org:
        return redirect(url_for('main.index'))
    
    if not require_billing_permission(org):
        return redirect(url_for('billing.billing_dashboard'))
    
    # Create portal session
    session = StripeService.create_portal_session(org)
    
    if not session:
        flash('Unable to access billing portal. Please contact support.', 'danger')
        return redirect(url_for('billing.billing_dashboard'))
    
    # Redirect to Stripe Customer Portal
    return redirect(session.url)


@billing_bp.route('/cancel-subscription', methods=['POST'])
@login_required
def cancel_subscription():
    """Cancel subscription"""
    org = require_org_access()
    if not org:
        return jsonify({'success': False, 'error': 'No organization'}), 403
    
    if not require_billing_permission(org):
        return jsonify({'success': False, 'error': 'No permission'}), 403
    
    cancel_at_period_end = request.json.get('cancel_at_period_end', True)
    
    success = StripeService.cancel_subscription(org, cancel_at_period_end)
    
    if success:
        if cancel_at_period_end:
            flash('Subscription will be canceled at the end of the billing period.', 'info')
        else:
            flash('Subscription has been canceled immediately.', 'info')
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'error': 'Failed to cancel subscription'}), 500


@billing_bp.route('/resume-subscription', methods=['POST'])
@login_required
def resume_subscription():
    """Resume a canceled subscription"""
    org = require_org_access()
    if not org:
        return jsonify({'success': False, 'error': 'No organization'}), 403
    
    if not require_billing_permission(org):
        return jsonify({'success': False, 'error': 'No permission'}), 403
    
    success = StripeService.resume_subscription(org)
    
    if success:
        flash('Subscription has been resumed.', 'success')
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'error': 'Failed to resume subscription'}), 500


@billing_bp.route('/webhook', methods=['POST'])
def webhook():
    """
    Stripe webhook endpoint
    Handles subscription events from Stripe
    """
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')
    
    if not StripeService.init_stripe():
        return jsonify({'error': 'Stripe not configured'}), 500
    
    webhook_secret = current_app.config.get('STRIPE_WEBHOOK_SECRET')
    
    if not webhook_secret:
        # In development, skip signature verification
        import json
        event = json.loads(payload)
    else:
        # In production, verify signature
        import stripe
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
        except ValueError:
            return jsonify({'error': 'Invalid payload'}), 400
        except stripe.error.SignatureVerificationError:
            return jsonify({'error': 'Invalid signature'}), 400
    
    # Handle the event
    success = StripeService.handle_webhook(event)
    
    if success:
        return jsonify({'status': 'success'}), 200
    else:
        return jsonify({'error': 'Webhook handling failed'}), 500
