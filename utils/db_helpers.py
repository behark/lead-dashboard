"""
Database helper utilities for optimized queries and common operations.
Provides efficient database access patterns and query optimization.
"""
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy import func, and_, or_, text
from sqlalchemy.orm import joinedload, selectinload
from datetime import datetime, timezone, timedelta
import logging

logger = logging.getLogger(__name__)


class QueryOptimizer:
    """Helper class for optimized database queries"""
    
    @staticmethod
    def paginate_query(query, page: int, per_page: int, max_per_page: int = 100):
        """Safely paginate a query with bounds checking"""
        page = max(1, page)
        per_page = min(max(1, per_page), max_per_page)
        return query.paginate(page=page, per_page=per_page, error_out=False)
    
    @staticmethod
    def bulk_update(model, ids: List[int], updates: Dict[str, Any], commit: bool = True):
        """Efficiently bulk update records"""
        from models import db
        
        if not ids:
            return 0
        
        try:
            count = model.query.filter(model.id.in_(ids)).update(
                updates,
                synchronize_session='fetch'
            )
            if commit:
                db.session.commit()
            return count
        except Exception as e:
            db.session.rollback()
            logger.exception(f"Error in bulk update: {e}")
            raise
    
    @staticmethod
    def bulk_insert(model, records: List[Dict], commit: bool = True):
        """Efficiently bulk insert records"""
        from models import db
        
        if not records:
            return 0
        
        try:
            objects = [model(**record) for record in records]
            db.session.bulk_save_objects(objects)
            if commit:
                db.session.commit()
            return len(objects)
        except Exception as e:
            db.session.rollback()
            logger.exception(f"Error in bulk insert: {e}")
            raise
    
    @staticmethod
    def get_or_create(model, defaults: Dict = None, **kwargs):
        """Get existing record or create new one atomically"""
        from models import db
        
        instance = model.query.filter_by(**kwargs).first()
        if instance:
            return instance, False
        
        try:
            params = {**kwargs, **(defaults or {})}
            instance = model(**params)
            db.session.add(instance)
            db.session.commit()
            return instance, True
        except Exception:
            db.session.rollback()
            # Race condition - try to get again
            instance = model.query.filter_by(**kwargs).first()
            if instance:
                return instance, False
            raise


class LeadQueryHelper:
    """Optimized query helpers for Lead model"""
    
    @staticmethod
    def get_leads_with_relations(lead_ids: List[int]):
        """Get leads with eagerly loaded relationships"""
        from models import Lead
        
        return Lead.query.options(
            joinedload(Lead.assigned_user),
            joinedload(Lead.sequence)
        ).filter(Lead.id.in_(lead_ids)).all()
    
    @staticmethod
    def get_dashboard_stats_optimized() -> Dict[str, Any]:
        """Get dashboard statistics with optimized single query"""
        from models import Lead, LeadStatus, LeadTemperature, ContactLog, db
        
        # Use subqueries for efficiency
        stats = db.session.query(
            func.count(Lead.id).label('total'),
            func.sum(func.cast(Lead.status == LeadStatus.NEW, db.Integer)).label('new'),
            func.sum(func.cast(Lead.status == LeadStatus.CONTACTED, db.Integer)).label('contacted'),
            func.sum(func.cast(Lead.status == LeadStatus.REPLIED, db.Integer)).label('replied'),
            func.sum(func.cast(Lead.status == LeadStatus.CLOSED, db.Integer)).label('closed'),
            func.sum(func.cast(Lead.status == LeadStatus.LOST, db.Integer)).label('lost'),
            func.sum(func.cast(Lead.temperature == LeadTemperature.HOT, db.Integer)).label('hot'),
            func.sum(func.cast(Lead.temperature == LeadTemperature.WARM, db.Integer)).label('warm'),
            func.sum(func.cast(Lead.temperature == LeadTemperature.COLD, db.Integer)).label('cold'),
            func.avg(Lead.lead_score).label('avg_score')
        ).first()
        
        return {
            'total': stats.total or 0,
            'by_status': {
                'new': stats.new or 0,
                'contacted': stats.contacted or 0,
                'replied': stats.replied or 0,
                'closed': stats.closed or 0,
                'lost': stats.lost or 0
            },
            'by_temperature': {
                'hot': stats.hot or 0,
                'warm': stats.warm or 0,
                'cold': stats.cold or 0
            },
            'avg_score': round(stats.avg_score or 0, 1)
        }
    
    @staticmethod
    def get_leads_needing_followup(days_overdue: int = 0) -> List:
        """Get leads that need follow-up"""
        from models import Lead, LeadStatus
        
        cutoff_date = datetime.now(timezone.utc).date() - timedelta(days=days_overdue)
        
        return Lead.query.filter(
            Lead.next_followup <= cutoff_date,
            Lead.status.in_([LeadStatus.CONTACTED, LeadStatus.REPLIED]),
            Lead.marketing_opt_out == False
        ).order_by(Lead.next_followup.asc()).all()
    
    @staticmethod
    def search_leads(
        search_term: str = None,
        status: str = None,
        temperature: str = None,
        category: str = None,
        country: str = None,
        assigned_to: int = None,
        page: int = 1,
        per_page: int = 50,
        sort_by: str = 'score'
    ) -> Tuple[List, Any]:
        """Search leads with multiple filters"""
        from models import Lead, LeadStatus, LeadTemperature
        
        query = Lead.query.options(joinedload(Lead.assigned_user))
        
        # Apply filters
        if search_term:
            search_pattern = f'%{search_term}%'
            query = query.filter(
                or_(
                    Lead.name.ilike(search_pattern),
                    Lead.email.ilike(search_pattern),
                    Lead.phone.ilike(search_pattern),
                    Lead.city.ilike(search_pattern)
                )
            )
        
        if status:
            try:
                query = query.filter(Lead.status == LeadStatus(status))
            except ValueError:
                pass
        
        if temperature:
            try:
                query = query.filter(Lead.temperature == LeadTemperature(temperature))
            except ValueError:
                pass
        
        if category:
            query = query.filter(Lead.category == category)
        
        if country:
            query = query.filter(Lead.country == country)
        
        if assigned_to is not None:
            if assigned_to == -1:  # Unassigned
                query = query.filter(Lead.assigned_to.is_(None))
            else:
                query = query.filter(Lead.assigned_to == assigned_to)
        
        # Apply sorting
        sort_options = {
            'score': Lead.lead_score.desc(),
            'date': Lead.created_at.desc(),
            'name': Lead.name.asc(),
            'followup': Lead.next_followup.asc().nullslast()
        }
        query = query.order_by(sort_options.get(sort_by, Lead.lead_score.desc()))
        
        # Paginate
        pagination = QueryOptimizer.paginate_query(query, page, per_page)
        
        return pagination.items, pagination


class AnalyticsQueryHelper:
    """Optimized query helpers for analytics"""
    
    @staticmethod
    def get_conversion_metrics(days: int = 30) -> Dict[str, Any]:
        """Get conversion metrics for the specified period"""
        from models import Lead, LeadStatus, ContactLog, db
        
        start_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        # Lead conversion stats
        lead_stats = db.session.query(
            func.count(Lead.id).label('total'),
            func.sum(func.cast(Lead.status == LeadStatus.CLOSED, db.Integer)).label('closed'),
            func.sum(func.cast(Lead.status == LeadStatus.CONTACTED, db.Integer)).label('contacted')
        ).filter(Lead.created_at >= start_date).first()
        
        # Contact response stats
        contact_stats = db.session.query(
            func.count(ContactLog.id).label('total_contacts'),
            func.count(ContactLog.responded_at).label('responses')
        ).filter(ContactLog.sent_at >= start_date).first()
        
        total = lead_stats.total or 0
        closed = lead_stats.closed or 0
        contacted = lead_stats.contacted or 0
        total_contacts = contact_stats.total_contacts or 0
        responses = contact_stats.responses or 0
        
        return {
            'conversion_rate': round((closed / total * 100) if total > 0 else 0, 1),
            'contact_rate': round((contacted / total * 100) if total > 0 else 0, 1),
            'response_rate': round((responses / total_contacts * 100) if total_contacts > 0 else 0, 1),
            'total_leads': total,
            'closed_leads': closed,
            'total_contacts': total_contacts,
            'responses': responses
        }
    
    @staticmethod
    def get_activity_by_hour(days: int = 7) -> Dict[int, int]:
        """Get contact activity grouped by hour of day"""
        from models import ContactLog, db
        
        start_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        results = db.session.query(
            func.extract('hour', ContactLog.sent_at).label('hour'),
            func.count(ContactLog.id).label('count')
        ).filter(
            ContactLog.sent_at >= start_date
        ).group_by('hour').all()
        
        return {int(r.hour): r.count for r in results}
