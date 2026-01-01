"""
Landing Page Routes
Public marketing pages
"""
from flask import Blueprint, render_template, request, redirect, url_for
from models_saas import PLAN_CONFIGS, SubscriptionPlan

landing_bp = Blueprint('landing', __name__)


@landing_bp.route('/')
def index():
    """Public landing page"""
    return render_template('landing/index.html', plans=PLAN_CONFIGS)


@landing_bp.route('/features')
def features():
    """Features page"""
    return render_template('landing/features.html')


@landing_bp.route('/pricing')
def pricing():
    """Public pricing page"""
    return render_template('landing/pricing.html', plans=PLAN_CONFIGS)


@landing_bp.route('/about')
def about():
    """About page"""
    return render_template('landing/about.html')


@landing_bp.route('/contact')
def contact():
    """Contact page"""
    return render_template('landing/contact.html')
