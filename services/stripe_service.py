"""
Stripe Payment Service
Handles subscriptions, payments, webhooks, and billing
"""
import stripe
from flask import current_app
from models import db
from models_saas import (
    Organization, Subscription, Invoice, SubscriptionPlan, SubscriptionStatus,
    PLAN_CONFIGS
)
from datetime import datetime, timezone, timedelta
import logging

logger = logging.getLogger(__name__)


class StripeService:
    """Service for handling Stripe payments and subscriptions"""
    
    @staticmethod
    def init_stripe():
        """Initialize Stripe with API key"""
        api_key = current_app.config.get('STRIPE_SECRET_KEY')
        if not api_key:
            logger.warning("STRIPE_SECRET_KEY not configured")
            return False
        
        stripe.api_key = api_key
        return True
    
    @staticmethod
    def create_customer(organization, user_email):
        """
        Create a Stripe customer for an organization
        
        Args:
            organization: Organization instance
            user_email: Email of the organization owner
            
        Returns:
            Stripe customer object or None
        """
        if not StripeService.init_stripe():
            return None
        
        try:
            customer = stripe.Customer.create(
                email=user_email,
                name=organization.name,
                metadata={
                    'organization_id': organization.id,
                    'organization_slug': organization.slug
                }
            )
            
            # Save customer ID to subscription
            if organization.subscription:
                organization.subscription.stripe_customer_id = customer.id
                db.session.commit()
            
            logger.info(f"Created Stripe customer {customer.id} for organization {organization.id}")
            return customer
            
        except Exception as e:
            logger.error(f"Error creating Stripe customer: {e}")
            return None
    
    @staticmethod
    def get_or_create_customer(organization, user_email):
        """Get existing customer or create new one"""
        if organization.subscription and organization.subscription.stripe_customer_id:
            try:
                if StripeService.init_stripe():
                    customer = stripe.Customer.retrieve(
                        organization.subscription.stripe_customer_id
                    )
                    return customer
            except stripe.error.StripeError as e:
                logger.warning(f"Could not retrieve customer: {e}")
        
        # Create new customer
        return StripeService.create_customer(organization, user_email)
    
    @staticmethod
    def create_checkout_session(organization, plan, billing_cycle='monthly', success_url=None, cancel_url=None):
        """
        Create Stripe Checkout session for subscription
        
        Args:
            organization: Organization instance
            plan: SubscriptionPlan enum
            billing_cycle: 'monthly' or 'yearly'
            success_url: URL to redirect after success
            cancel_url: URL to redirect after cancel
            
        Returns:
            Checkout session object or None
        """
        if not StripeService.init_stripe():
            return None
        
        # Get price ID from config
        price_id = current_app.config.get(f'STRIPE_PRICE_ID_{plan.value.upper()}_{billing_cycle.upper()}')
        
        if not price_id:
            logger.error(f"Stripe price ID not configured for {plan.value} {billing_cycle}")
            return None
        
        # Get or create customer
        owner = organization.members.filter_by(role='owner').first()
        user_email = owner.user.email if owner and owner.user else None
        
        customer = StripeService.get_or_create_customer(organization, user_email)
        if not customer:
            return None
        
        try:
            session = stripe.checkout.Session.create(
                customer=customer.id,
                payment_method_types=['card'],
                line_items=[{
                    'price': price_id,
                    'quantity': 1,
                }],
                mode='subscription',
                success_url=success_url or f"{current_app.config.get('BASE_URL', 'http://localhost:5000')}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=cancel_url or f"{current_app.config.get('BASE_URL', 'http://localhost:5000')}/billing/cancel",
                metadata={
                    'organization_id': organization.id,
                    'plan': plan.value,
                    'billing_cycle': billing_cycle
                },
                subscription_data={
                    'metadata': {
                        'organization_id': organization.id,
                        'plan': plan.value
                    }
                },
                allow_promotion_codes=True,
            )
            
            logger.info(f"Created checkout session {session.id} for organization {organization.id}")
            return session
            
        except Exception as e:
            logger.error(f"Error creating checkout session: {e}")
            return None
    
    @staticmethod
    def create_portal_session(organization):
        """
        Create Stripe Customer Portal session for subscription management
        
        Args:
            organization: Organization instance
            
        Returns:
            Portal session object or None
        """
        if not StripeService.init_stripe():
            return None
        
        if not organization.subscription or not organization.subscription.stripe_customer_id:
            logger.error("Organization has no Stripe customer")
            return None
        
        try:
            session = stripe.billing_portal.Session.create(
                customer=organization.subscription.stripe_customer_id,
                return_url=f"{current_app.config.get('BASE_URL', 'http://localhost:5000')}/billing",
            )
            
            logger.info(f"Created portal session for organization {organization.id}")
            return session
            
        except Exception as e:
            logger.error(f"Error creating portal session: {e}")
            return None
    
    @staticmethod
    def handle_webhook(event):
        """
        Handle Stripe webhook events
        
        Args:
            event: Stripe event object
            
        Returns:
            True if handled successfully
        """
        if not StripeService.init_stripe():
            return False
        
        event_type = event['type']
        data = event['data']['object']
        
        logger.info(f"Handling Stripe webhook: {event_type}")
        
        try:
            if event_type == 'checkout.session.completed':
                # Customer completed checkout
                organization_id = data['metadata'].get('organization_id')
                if organization_id:
                    StripeService._activate_subscription(organization_id, data)
            
            elif event_type == 'customer.subscription.created':
                # New subscription created
                organization_id = data['metadata'].get('organization_id')
                if organization_id:
                    StripeService._update_subscription_from_stripe(organization_id, data)
            
            elif event_type == 'customer.subscription.updated':
                # Subscription updated (plan change, etc.)
                organization_id = data['metadata'].get('organization_id')
                if organization_id:
                    StripeService._update_subscription_from_stripe(organization_id, data)
            
            elif event_type == 'customer.subscription.deleted':
                # Subscription canceled
                organization_id = data['metadata'].get('organization_id')
                if organization_id:
                    StripeService._cancel_subscription(organization_id)
            
            elif event_type == 'invoice.paid':
                # Invoice paid
                StripeService._handle_invoice_paid(data)
            
            elif event_type == 'invoice.payment_failed':
                # Payment failed
                StripeService._handle_payment_failed(data)
            
            return True
            
        except Exception as e:
            logger.error(f"Error handling webhook {event_type}: {e}")
            return False
    
    @staticmethod
    def _activate_subscription(organization_id, checkout_session):
        """Activate subscription after successful checkout"""
        organization = db.session.get(Organization, organization_id)
        if not organization:
            logger.error(f"Organization {organization_id} not found")
            return
        
        subscription_id = checkout_session.get('subscription')
        if not subscription_id:
            logger.error("No subscription ID in checkout session")
            return
        
        # Get subscription from Stripe
        try:
            stripe_sub = stripe.Subscription.retrieve(subscription_id)
            
            # Update our subscription
            if not organization.subscription:
                logger.warning(f"Organization {organization_id} has no subscription")
                return
            
            sub = organization.subscription
            sub.stripe_subscription_id = subscription_id
            sub.status = SubscriptionStatus.ACTIVE
            sub.current_period_start = datetime.fromtimestamp(
                stripe_sub.current_period_start, tz=timezone.utc
            )
            sub.current_period_end = datetime.fromtimestamp(
                stripe_sub.current_period_end, tz=timezone.utc
            )
            sub.next_billing_date = sub.current_period_end
            sub.trial_ends_at = None  # Trial is over
            
            # Determine plan from price
            price_id = stripe_sub['items']['data'][0]['price']['id']
            plan = StripeService._get_plan_from_price_id(price_id)
            if plan:
                sub.plan = plan
                # Update limits from plan config
                config = PLAN_CONFIGS[plan]
                sub.max_leads = config['max_leads']
                sub.max_users = config['max_users']
                sub.max_contacts_per_day = config['max_contacts_per_day']
                sub.max_templates = config['max_templates']
                sub.max_sequences = config['max_sequences']
                sub.has_api_access = config['has_api_access']
                sub.has_white_label = config['has_white_label']
                sub.has_priority_support = config['has_priority_support']
                sub.has_custom_integrations = config['has_custom_integrations']
                sub.has_advanced_analytics = config['has_advanced_analytics']
            
            db.session.commit()
            logger.info(f"Activated subscription for organization {organization_id}")
            
        except Exception as e:
            logger.error(f"Error activating subscription: {e}")
    
    @staticmethod
    def _update_subscription_from_stripe(organization_id, stripe_subscription):
        """Update subscription from Stripe data"""
        organization = db.session.get(Organization, organization_id)
        if not organization or not organization.subscription:
            return
        
        sub = organization.subscription
        sub.stripe_subscription_id = stripe_subscription['id']
        
        # Update status
        if stripe_subscription['status'] == 'active':
            sub.status = SubscriptionStatus.ACTIVE
        elif stripe_subscription['status'] == 'past_due':
            sub.status = SubscriptionStatus.PAST_DUE
        elif stripe_subscription['status'] == 'canceled':
            sub.status = SubscriptionStatus.CANCELED
        
        # Update dates
        if stripe_subscription.get('current_period_start'):
            sub.current_period_start = datetime.fromtimestamp(
                stripe_subscription['current_period_start'], tz=timezone.utc
            )
        if stripe_subscription.get('current_period_end'):
            sub.current_period_end = datetime.fromtimestamp(
                stripe_subscription['current_period_end'], tz=timezone.utc
            )
            sub.next_billing_date = sub.current_period_end
        
        # Update plan if changed
        if stripe_subscription.get('items', {}).get('data'):
            price_id = stripe_subscription['items']['data'][0]['price']['id']
            plan = StripeService._get_plan_from_price_id(price_id)
            if plan and plan != sub.plan:
                sub.plan = plan
                # Update limits
                config = PLAN_CONFIGS[plan]
                sub.max_leads = config['max_leads']
                sub.max_users = config['max_users']
                sub.max_contacts_per_day = config['max_contacts_per_day']
                sub.max_templates = config['max_templates']
                sub.max_sequences = config['max_sequences']
                sub.has_api_access = config['has_api_access']
                sub.has_white_label = config['has_white_label']
                sub.has_priority_support = config['has_priority_support']
                sub.has_custom_integrations = config['has_custom_integrations']
                sub.has_advanced_analytics = config['has_advanced_analytics']
        
        db.session.commit()
        logger.info(f"Updated subscription for organization {organization_id}")
    
    @staticmethod
    def _cancel_subscription(organization_id):
        """Handle subscription cancellation"""
        organization = db.session.get(Organization, organization_id)
        if not organization or not organization.subscription:
            return
        
        sub = organization.subscription
        sub.status = SubscriptionStatus.CANCELED
        sub.canceled_at = datetime.now(timezone.utc)
        
        # Downgrade to FREE plan
        sub.plan = SubscriptionPlan.FREE
        config = PLAN_CONFIGS[SubscriptionPlan.FREE]
        sub.max_leads = config['max_leads']
        sub.max_users = config['max_users']
        sub.max_contacts_per_day = config['max_contacts_per_day']
        sub.max_templates = config['max_templates']
        sub.max_sequences = config['max_sequences']
        sub.has_api_access = False
        sub.has_white_label = False
        sub.has_priority_support = False
        sub.has_custom_integrations = False
        sub.has_advanced_analytics = False
        
        db.session.commit()
        logger.info(f"Canceled subscription for organization {organization_id}")
    
    @staticmethod
    def _handle_invoice_paid(invoice_data):
        """Handle successful invoice payment"""
        customer_id = invoice_data.get('customer')
        if not customer_id:
            return
        
        # Find organization by customer ID
        subscription = Subscription.query.filter_by(stripe_customer_id=customer_id).first()
        if not subscription:
            return
        
        # Create invoice record
        invoice = Invoice(
            organization_id=subscription.organization_id,
            invoice_number=invoice_data.get('number'),
            amount=invoice_data.get('amount_paid', 0) / 100,  # Convert from cents
            currency=invoice_data.get('currency', 'eur').upper(),
            status='paid',
            stripe_invoice_id=invoice_data.get('id'),
            issued_at=datetime.fromtimestamp(invoice_data.get('created', 0), tz=timezone.utc),
            paid_at=datetime.now(timezone.utc),
            pdf_url=invoice_data.get('invoice_pdf')
        )
        
        db.session.add(invoice)
        db.session.commit()
        logger.info(f"Recorded paid invoice for organization {subscription.organization_id}")
    
    @staticmethod
    def _handle_payment_failed(invoice_data):
        """Handle failed payment"""
        customer_id = invoice_data.get('customer')
        if not customer_id:
            return
        
        subscription = Subscription.query.filter_by(stripe_customer_id=customer_id).first()
        if not subscription:
            return
        
        subscription.status = SubscriptionStatus.PAST_DUE
        db.session.commit()
        logger.warning(f"Payment failed for organization {subscription.organization_id}")
    
    @staticmethod
    def _get_plan_from_price_id(price_id):
        """Get SubscriptionPlan from Stripe price ID"""
        # This should match your Stripe price IDs
        price_mapping = {
            current_app.config.get('STRIPE_PRICE_ID_STARTER_MONTHLY'): SubscriptionPlan.STARTER,
            current_app.config.get('STRIPE_PRICE_ID_STARTER_YEARLY'): SubscriptionPlan.STARTER,
            current_app.config.get('STRIPE_PRICE_ID_PROFESSIONAL_MONTHLY'): SubscriptionPlan.PROFESSIONAL,
            current_app.config.get('STRIPE_PRICE_ID_PROFESSIONAL_YEARLY'): SubscriptionPlan.PROFESSIONAL,
            current_app.config.get('STRIPE_PRICE_ID_ENTERPRISE_MONTHLY'): SubscriptionPlan.ENTERPRISE,
            current_app.config.get('STRIPE_PRICE_ID_ENTERPRISE_YEARLY'): SubscriptionPlan.ENTERPRISE,
        }
        
        return price_mapping.get(price_id)
    
    @staticmethod
    def cancel_subscription(organization, cancel_at_period_end=True):
        """
        Cancel a subscription
        
        Args:
            organization: Organization instance
            cancel_at_period_end: If True, cancel at end of period; if False, cancel immediately
        """
        if not StripeService.init_stripe():
            return False
        
        if not organization.subscription or not organization.subscription.stripe_subscription_id:
            logger.error("No Stripe subscription to cancel")
            return False
        
        try:
            if cancel_at_period_end:
                # Cancel at end of period
                stripe.Subscription.modify(
                    organization.subscription.stripe_subscription_id,
                    cancel_at_period_end=True
                )
                organization.subscription.cancel_at_period_end = True
            else:
                # Cancel immediately
                stripe.Subscription.delete(
                    organization.subscription.stripe_subscription_id
                )
                StripeService._cancel_subscription(organization.id)
            
            db.session.commit()
            logger.info(f"Canceled subscription for organization {organization.id}")
            return True
            
        except Exception as e:
            logger.error(f"Error canceling subscription: {e}")
            return False
    
    @staticmethod
    def resume_subscription(organization):
        """Resume a canceled subscription"""
        if not StripeService.init_stripe():
            return False
        
        if not organization.subscription or not organization.subscription.stripe_subscription_id:
            return False
        
        try:
            stripe.Subscription.modify(
                organization.subscription.stripe_subscription_id,
                cancel_at_period_end=False
            )
            
            organization.subscription.cancel_at_period_end = False
            organization.subscription.status = SubscriptionStatus.ACTIVE
            db.session.commit()
            
            logger.info(f"Resumed subscription for organization {organization.id}")
            return True
            
        except Exception as e:
            logger.error(f"Error resuming subscription: {e}")
            return False
