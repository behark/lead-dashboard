from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user
from models import db, UserRole
from services.analytics_service import AnalyticsService

analytics_bp = Blueprint('analytics', __name__, url_prefix='/analytics')


@analytics_bp.route('/')
@login_required
def dashboard():
    stats = AnalyticsService.get_dashboard_stats()
    funnel = AnalyticsService.get_conversion_funnel()
    channel_perf = AnalyticsService.get_channel_performance()
    best_times = AnalyticsService.get_best_contact_times()
    ab_results = AnalyticsService.get_ab_test_results()
    user_perf = AnalyticsService.get_user_performance()
    trends = AnalyticsService.get_trend_data(30)
    
    return render_template(
        'analytics/dashboard.html',
        stats=stats,
        funnel=funnel,
        channel_perf=channel_perf,
        best_times=best_times,
        ab_results=ab_results,
        user_perf=user_perf,
        trends=trends
    )


@analytics_bp.route('/api/stats')
@login_required
def api_stats():
    return jsonify(AnalyticsService.get_dashboard_stats())


@analytics_bp.route('/api/funnel')
@login_required
def api_funnel():
    return jsonify(AnalyticsService.get_conversion_funnel())


@analytics_bp.route('/api/channels')
@login_required
def api_channels():
    return jsonify(AnalyticsService.get_channel_performance())


@analytics_bp.route('/api/best-times')
@login_required
def api_best_times():
    return jsonify(AnalyticsService.get_best_contact_times())


@analytics_bp.route('/api/trends')
@login_required
def api_trends():
    days = request.args.get('days', 30, type=int)
    return jsonify(AnalyticsService.get_trend_data(days))


@analytics_bp.route('/api/ab-tests')
@login_required
def api_ab_tests():
    return jsonify(AnalyticsService.get_ab_test_results())


@analytics_bp.route('/api/user-performance')
@login_required
def api_user_performance():
    user_id = request.args.get('user_id', type=int)
    
    # Non-admins can only see their own performance
    if current_user.role != UserRole.ADMIN and user_id != current_user.id:
        user_id = current_user.id
    
    return jsonify(AnalyticsService.get_user_performance(user_id))
