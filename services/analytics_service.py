from datetime import datetime, timezone, timedelta, date
from sqlalchemy import func, case
from sqlalchemy.orm import joinedload
from models import db, Lead, ContactLog, Analytics, LeadStatus, LeadTemperature, ContactChannel
from collections import defaultdict
from typing import Dict, List, Any, Optional
from utils.cache import cached
from utils.logging_config import get_logger

logger = get_logger(__name__)


class AnalyticsService:
    """Service for generating analytics and reports"""
    
    @staticmethod
    @cached(timeout=60, key_prefix='dashboard_stats')  # Cache for 1 minute
    def get_dashboard_stats() -> Dict[str, Any]:
        """Get overview statistics for the dashboard (cached)"""
        
        total = Lead.query.count()
        
        stats = {
            'total': total,
            'by_status': {},
            'by_temperature': {},
            'by_category': {},
            'by_country': {},
            'conversion': {},
            'recent_activity': {}
        }
        
        # By status
        status_counts = db.session.query(
            Lead.status, func.count(Lead.id)
        ).group_by(Lead.status).all()
        
        for status, count in status_counts:
            stats['by_status'][status.value if status else 'NEW'] = count
        
        # By temperature
        temp_counts = db.session.query(
            Lead.temperature, func.count(Lead.id)
        ).group_by(Lead.temperature).all()
        
        for temp, count in temp_counts:
            stats['by_temperature'][temp.value if temp else 'WARM'] = count
        
        # By category (top 10)
        cat_counts = db.session.query(
            Lead.category, func.count(Lead.id)
        ).group_by(Lead.category).order_by(func.count(Lead.id).desc()).limit(10).all()
        
        stats['by_category'] = {cat or 'Unknown': count for cat, count in cat_counts}
        
        # By country (top 10)
        country_counts = db.session.query(
            Lead.country, func.count(Lead.id)
        ).group_by(Lead.country).order_by(func.count(Lead.id).desc()).limit(10).all()
        
        stats['by_country'] = {country or 'Unknown': count for country, count in country_counts}
        
        # Conversion rates
        contacted = stats['by_status'].get('CONTACTED', 0)
        replied = stats['by_status'].get('REPLIED', 0)
        closed = stats['by_status'].get('CLOSED', 0)
        
        stats['conversion']['response_rate'] = round((replied / contacted * 100), 1) if contacted > 0 else 0
        stats['conversion']['close_rate'] = round((closed / replied * 100), 1) if replied > 0 else 0
        stats['conversion']['overall_rate'] = round((closed / total * 100), 1) if total > 0 else 0
        
        # Recent activity (last 7 days) - optimize with single query
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        
        # Use single query with aggregation instead of multiple queries
        recent_stats = db.session.query(
            func.count(Lead.id).filter(Lead.created_at >= week_ago).label('new_leads'),
            func.count(ContactLog.id).filter(ContactLog.sent_at >= week_ago).label('contacts'),
            func.count(ContactLog.id).filter(ContactLog.responded_at >= week_ago).label('responses')
        ).first()
        
        stats['recent_activity']['new_leads'] = recent_stats.new_leads or 0
        stats['recent_activity']['contacts_made'] = recent_stats.contacts or 0
        stats['recent_activity']['responses'] = recent_stats.responses or 0
        
        return stats
    
    @staticmethod
    def get_conversion_funnel():
        """Get conversion funnel data"""
        
        total = Lead.query.count()
        contacted = Lead.query.filter(Lead.status.in_([
            LeadStatus.CONTACTED, LeadStatus.REPLIED, LeadStatus.CLOSED, LeadStatus.LOST
        ])).count()
        replied = Lead.query.filter(Lead.status.in_([
            LeadStatus.REPLIED, LeadStatus.CLOSED
        ])).count()
        closed = Lead.query.filter_by(status=LeadStatus.CLOSED).count()
        
        funnel = [
            {'stage': 'Total Leads', 'count': total, 'percentage': 100},
            {'stage': 'Contacted', 'count': contacted, 'percentage': round(contacted/total*100, 1) if total else 0},
            {'stage': 'Replied', 'count': replied, 'percentage': round(replied/total*100, 1) if total else 0},
            {'stage': 'Closed', 'count': closed, 'percentage': round(closed/total*100, 1) if total else 0},
        ]
        
        return funnel
    
    @staticmethod
    def get_channel_performance():
        """Get performance metrics by contact channel"""
        
        channels = {}
        
        for channel in ContactChannel:
            sent = ContactLog.query.filter_by(channel=channel).count()
            delivered = ContactLog.query.filter(
                ContactLog.channel == channel,
                ContactLog.delivered_at.isnot(None)
            ).count()
            responded = ContactLog.query.filter(
                ContactLog.channel == channel,
                ContactLog.responded_at.isnot(None)
            ).count()
            
            channels[channel.value] = {
                'sent': sent,
                'delivered': delivered,
                'delivery_rate': round(delivered/sent*100, 1) if sent else 0,
                'responded': responded,
                'response_rate': round(responded/sent*100, 1) if sent else 0
            }
        
        return channels
    
    @staticmethod
    def get_best_contact_times():
        """Analyze best times to contact based on response data"""
        
        # Get responses with timestamps
        responses = db.session.query(
            func.extract('dow', ContactLog.sent_at).label('day_of_week'),
            func.extract('hour', ContactLog.sent_at).label('hour'),
            func.count(ContactLog.id).label('sent'),
            func.sum(case((ContactLog.responded_at.isnot(None), 1), else_=0)).label('responded')
        ).group_by('day_of_week', 'hour').all()
        
        by_hour = defaultdict(lambda: {'sent': 0, 'responded': 0})
        by_day = defaultdict(lambda: {'sent': 0, 'responded': 0})
        
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        
        for row in responses:
            hour = int(row.hour) if row.hour else 0
            day = int(row.day_of_week) if row.day_of_week else 0
            
            by_hour[hour]['sent'] += row.sent
            by_hour[hour]['responded'] += row.responded or 0
            
            by_day[day]['sent'] += row.sent
            by_day[day]['responded'] += row.responded or 0
        
        # Calculate response rates
        hour_rates = []
        for hour in range(24):
            data = by_hour[hour]
            rate = round(data['responded']/data['sent']*100, 1) if data['sent'] > 0 else 0
            hour_rates.append({'hour': f"{hour:02d}:00", 'rate': rate, 'sent': data['sent']})
        
        day_rates = []
        for i, day in enumerate(days):
            data = by_day[i]
            rate = round(data['responded']/data['sent']*100, 1) if data['sent'] > 0 else 0
            day_rates.append({'day': day, 'rate': rate, 'sent': data['sent']})
        
        # Find best times
        best_hour = max(hour_rates, key=lambda x: x['rate']) if hour_rates else None
        best_day = max(day_rates, key=lambda x: x['rate']) if day_rates else None
        
        return {
            'by_hour': hour_rates,
            'by_day': day_rates,
            'best_hour': best_hour,
            'best_day': best_day
        }
    
    @staticmethod
    def get_ab_test_results():
        """Get A/B test results for message templates"""
        
        from models import MessageTemplate
        
        templates = MessageTemplate.query.filter(
            MessageTemplate.times_sent > 0
        ).all()
        
        # Group by category and variant
        results = defaultdict(list)
        
        for template in templates:
            key = f"{template.category or 'general'}_{template.channel.value}"
            results[key].append({
                'id': template.id,
                'name': template.name,
                'variant': template.variant,
                'sent': template.times_sent,
                'opened': template.times_opened,
                'responded': template.times_responded,
                'open_rate': template.open_rate,
                'response_rate': template.response_rate
            })
        
        # Determine winners
        analysis = {}
        for key, variants in results.items():
            if len(variants) > 1:
                winner = max(variants, key=lambda x: x['response_rate'])
                analysis[key] = {
                    'variants': variants,
                    'winner': winner['variant'],
                    'winner_rate': winner['response_rate']
                }
        
        return analysis
    
    @staticmethod
    def get_user_performance(user_id=None):
        """Get performance metrics by user/sales rep"""
        
        from models import User
        
        query = db.session.query(
            User.id,
            User.username,
            func.count(Lead.id).label('total_leads'),
            func.sum(case((Lead.status == LeadStatus.CONTACTED, 1), else_=0)).label('contacted'),
            func.sum(case((Lead.status == LeadStatus.REPLIED, 1), else_=0)).label('replied'),
            func.sum(case((Lead.status == LeadStatus.CLOSED, 1), else_=0)).label('closed'),
        ).outerjoin(Lead, User.id == Lead.assigned_to).group_by(User.id, User.username)
        
        if user_id:
            query = query.filter(User.id == user_id)
        
        results = []
        for row in query.all():
            results.append({
                'user_id': row.id,
                'username': row.username,
                'total_leads': row.total_leads or 0,
                'contacted': row.contacted or 0,
                'replied': row.replied or 0,
                'closed': row.closed or 0,
                'close_rate': round((row.closed or 0) / (row.total_leads or 1) * 100, 1)
            })
        
        return results
    
    @staticmethod
    def record_daily_analytics():
        """Record daily analytics snapshot"""

        today = date.today()

        # Check if already recorded
        existing = Analytics.query.filter_by(date=today).first()
        if existing:
            analytics = existing
        else:
            analytics = Analytics(date=today)

        # Get today's data
        today_start = datetime.combine(today, datetime.min.time()).replace(tzinfo=timezone.utc)
        today_end = today_start + timedelta(days=1)

        analytics.leads_created = Lead.query.filter(
            Lead.created_at >= today_start,
            Lead.created_at < today_end
        ).count()

        analytics.contacts_made = ContactLog.query.filter(
            ContactLog.sent_at >= today_start,
            ContactLog.sent_at < today_end
        ).count()

        analytics.responses_received = ContactLog.query.filter(
            ContactLog.responded_at >= today_start,
            ContactLog.responded_at < today_end
        ).count()

        # By channel
        for channel in ContactChannel:
            sent = ContactLog.query.filter(
                ContactLog.channel == channel,
                ContactLog.sent_at >= today_start,
                ContactLog.sent_at < today_end
            ).count()

            responded = ContactLog.query.filter(
                ContactLog.channel == channel,
                ContactLog.responded_at >= today_start,
                ContactLog.responded_at < today_end
            ).count()

            if channel == ContactChannel.WHATSAPP:
                analytics.whatsapp_sent = sent
                analytics.whatsapp_responses = responded
            elif channel == ContactChannel.EMAIL:
                analytics.email_sent = sent
                analytics.email_responses = responded
            elif channel == ContactChannel.SMS:
                analytics.sms_sent = sent
                analytics.sms_responses = responded

        # Enhanced metrics
        AnalyticsService.update_enhanced_metrics(analytics)

        db.session.add(analytics)
        db.session.commit()

        return analytics

    @staticmethod
    def update_enhanced_metrics(analytics):
        """Update enhanced analytics metrics for the given analytics record"""

        # Calculate conversion rates
        total_contacts = analytics.contacts_made
        total_responses = analytics.responses_received
        total_closed = analytics.deals_closed

        analytics.contacted_to_responded_rate = (total_responses / total_contacts * 100) if total_contacts > 0 else 0
        analytics.responded_to_closed_rate = (total_closed / total_responses * 100) if total_responses > 0 else 0

        # Overall conversion rate (leads created to closed deals)
        leads_created_today = analytics.leads_created
        analytics.overall_conversion_rate = (total_closed / leads_created_today * 100) if leads_created_today > 0 else 0

        # Best performing template
        from models import MessageTemplate
        best_template = MessageTemplate.query.filter(
            MessageTemplate.times_sent > 0
        ).order_by(MessageTemplate.response_rate.desc()).first()

        if best_template:
            analytics.best_template_id = best_template.id
            analytics.best_template_response_rate = best_template.response_rate

        # Lead quality metrics
        today_start = datetime.combine(analytics.date, datetime.min.time()).replace(tzinfo=timezone.utc)
        today_end = today_start + timedelta(days=1)

        leads_today = Lead.query.filter(
            Lead.created_at >= today_start,
            Lead.created_at < today_end
        ).all()

        if leads_today:
            analytics.avg_lead_score = sum(lead.lead_score for lead in leads_today) / len(leads_today)
            analytics.hot_leads_count = sum(1 for lead in leads_today if lead.temperature == LeadTemperature.HOT)
            analytics.warm_leads_count = sum(1 for lead in leads_today if lead.temperature == LeadTemperature.WARM)
            analytics.cold_leads_count = sum(1 for lead in leads_today if lead.temperature == LeadTemperature.COLD)

        # Compliance metrics
        analytics.opt_outs_count = Lead.query.filter(
            Lead.opt_out_date >= today_start,
            Lead.opt_out_date < today_end
        ).count()

        # A/B testing results
        ab_results = AnalyticsService.get_ab_test_results()
        if ab_results:
            # Find the best performing variant overall
            best_variant = None
            best_rate = 0
            improvement = 0

            for category, result in ab_results.items():
                winner_rate = result['winner_rate']
                if winner_rate > best_rate:
                    best_rate = winner_rate
                    best_variant = result['winner']
                    # Calculate improvement over average
                    avg_rate = sum(v['response_rate'] for v in result['variants']) / len(result['variants'])
                    improvement = ((winner_rate - avg_rate) / avg_rate * 100) if avg_rate > 0 else 0

            analytics.ab_test_winner_variant = best_variant
            analytics.ab_test_improvement_rate = improvement

    @staticmethod
    def update_daily_analytics():
        """Update analytics for today with enhanced metrics"""
        today = date.today()
        analytics = AnalyticsService.record_daily_analytics()

        # Also update the last 30 days to ensure historical data has enhanced metrics
        for days_back in range(1, 31):
            past_date = today - timedelta(days=days_back)
            past_analytics = Analytics.query.filter_by(date=past_date).first()
            if past_analytics:
                AnalyticsService.update_enhanced_metrics(past_analytics)

        db.session.commit()
    
    @staticmethod
    def get_trend_data(days=30):
        """Get trend data for the last N days"""
        
        start_date = date.today() - timedelta(days=days)
        
        analytics = Analytics.query.filter(
            Analytics.date >= start_date
        ).order_by(Analytics.date).all()
        
        return [{
            'date': a.date.isoformat(),
            'leads_created': a.leads_created,
            'contacts_made': a.contacts_made,
            'responses': a.responses_received,
            'deals_closed': a.deals_closed
        } for a in analytics]
