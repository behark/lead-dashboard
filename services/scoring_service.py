from datetime import datetime, timezone, timedelta
from models import db, Lead, LeadStatus, LeadTemperature


class ScoringService:
    """Service for managing lead scoring and temperature decay"""
    
    @staticmethod
    def recalculate_all_scores():
        """Recalculate scores for all leads"""
        leads = Lead.query.all()
        
        for lead in leads:
            lead.calculate_score()
        
        db.session.commit()
        return len(leads)
    
    @staticmethod
    def apply_temperature_decay():
        """Apply temperature decay to leads that haven't been contacted"""
        
        now = datetime.now(timezone.utc)
        
        # Decay rules:
        # - NEW leads: decay after 7 days
        # - CONTACTED leads: decay after 14 days without response
        
        decayed_count = 0
        
        # NEW leads older than 7 days
        cutoff_new = now - timedelta(days=7)
        new_leads = Lead.query.filter(
            Lead.status == LeadStatus.NEW,
            Lead.created_at < cutoff_new,
            Lead.temperature != LeadTemperature.COLD
        ).all()
        
        for lead in new_leads:
            days_old = (now - lead.created_at).days
            
            if days_old > 21:  # 3 weeks
                lead.temperature = LeadTemperature.COLD
                lead.lead_score = max(lead.lead_score - 30, 10)
            elif days_old > 14:  # 2 weeks
                if lead.temperature == LeadTemperature.HOT:
                    lead.temperature = LeadTemperature.WARM
                    lead.lead_score = max(lead.lead_score - 20, 30)
            elif days_old > 7:  # 1 week
                lead.lead_score = max(lead.lead_score - 10, 40)
            
            decayed_count += 1
        
        # CONTACTED leads without response after 14 days
        cutoff_contacted = now - timedelta(days=14)
        contacted_leads = Lead.query.filter(
            Lead.status == LeadStatus.CONTACTED,
            Lead.last_contacted < cutoff_contacted,
            Lead.last_response.is_(None),
            Lead.temperature != LeadTemperature.COLD
        ).all()
        
        for lead in contacted_leads:
            days_since_contact = (now - lead.last_contacted).days
            
            if days_since_contact > 30:
                lead.temperature = LeadTemperature.COLD
                lead.lead_score = max(lead.lead_score - 25, 10)
            elif days_since_contact > 21:
                if lead.temperature == LeadTemperature.HOT:
                    lead.temperature = LeadTemperature.WARM
                lead.lead_score = max(lead.lead_score - 15, 25)
            elif days_since_contact > 14:
                lead.lead_score = max(lead.lead_score - 10, 35)
            
            decayed_count += 1
        
        db.session.commit()
        return decayed_count
    
    @staticmethod
    def boost_score(lead, reason, points=10):
        """Boost a lead's score for positive engagement"""
        
        lead.lead_score = min(lead.lead_score + points, 100)
        lead.update_temperature()
        
        # Track in notes
        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')
        boost_note = f"[{timestamp}] Score +{points}: {reason}"
        
        if lead.notes:
            lead.notes = f"{lead.notes}\n{boost_note}"
        else:
            lead.notes = boost_note
        
        db.session.commit()
        return lead.lead_score
    
    @staticmethod
    def penalize_score(lead, reason, points=10):
        """Reduce a lead's score for negative signals"""
        
        lead.lead_score = max(lead.lead_score - points, 0)
        lead.update_temperature()
        
        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')
        penalty_note = f"[{timestamp}] Score -{points}: {reason}"
        
        if lead.notes:
            lead.notes = f"{lead.notes}\n{penalty_note}"
        else:
            lead.notes = penalty_note
        
        db.session.commit()
        return lead.lead_score
    
    @staticmethod
    def get_score_distribution():
        """Get distribution of lead scores"""
        
        from sqlalchemy import func
        
        ranges = [
            (0, 20, 'Very Cold'),
            (21, 40, 'Cold'),
            (41, 60, 'Warm'),
            (61, 80, 'Hot'),
            (81, 100, 'Very Hot')
        ]
        
        distribution = []
        
        for low, high, label in ranges:
            count = Lead.query.filter(
                Lead.lead_score >= low,
                Lead.lead_score <= high
            ).count()
            
            distribution.append({
                'range': f"{low}-{high}",
                'label': label,
                'count': count
            })
        
        return distribution
    
    @staticmethod
    def get_leads_needing_attention():
        """Get leads that need attention (high score but not contacted recently)"""
        
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        
        # Hot leads not contacted in a week
        hot_neglected = Lead.query.filter(
            Lead.temperature == LeadTemperature.HOT,
            Lead.status.in_([LeadStatus.NEW, LeadStatus.CONTACTED]),
            db.or_(
                Lead.last_contacted.is_(None),
                Lead.last_contacted < week_ago
            )
        ).order_by(Lead.lead_score.desc()).limit(20).all()
        
        # Leads with scheduled follow-up that's overdue
        overdue = Lead.query.filter(
            Lead.next_followup < datetime.now(timezone.utc),
            Lead.status.in_([LeadStatus.NEW, LeadStatus.CONTACTED])
        ).order_by(Lead.next_followup).limit(20).all()
        
        return {
            'hot_neglected': hot_neglected,
            'overdue_followup': overdue
        }
