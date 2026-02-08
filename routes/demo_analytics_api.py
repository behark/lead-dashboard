"""
Demo Analytics API Endpoints
Receives tracking data from demo websites
"""

from flask import Blueprint, request, jsonify
from models import db, Lead
from services.analytics_service import AnalyticsService
from datetime import datetime, timezone
import json
import os

demo_analytics_bp = Blueprint('demo_analytics', __name__, url_prefix='/api/demo-analytics')

@demo_analytics_bp.route('/track', methods=['POST'])
def track_demo_event():
    """
    Track demo website events (views, interactions, etc.)
    Public endpoint - no auth required (but can add API key validation)
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        event_type = data.get('event_type')  # 'page_view', 'interaction', 'page_exit'
        business_name = data.get('business_name')
        
        if not business_name:
            return jsonify({'error': 'business_name required'}), 400
        
        # Find lead by business name
        lead = Lead.query.filter(
            db.func.lower(Lead.name) == business_name.lower()
        ).first()
        
        if not lead:
            # Try to find by normalized name (remove special chars)
            normalized_name = business_name.lower().replace('-', ' ').replace('_', ' ')
            lead = Lead.query.filter(
                db.func.lower(Lead.name).like(f'%{normalized_name}%')
            ).first()
        
        # Update lead engagement
        if lead:
            if event_type == 'page_view':
                # First view - high engagement
                if lead.engagement_count == 0:
                    lead.engagement_count = 1
                    lead.lead_score = min(lead.lead_score + 10, 100)
                    lead.update_temperature()
                
                # Update last response time
                lead.last_response = datetime.now(timezone.utc)
            
            elif event_type == 'interaction':
                interaction_type = data.get('interaction_type')
                
                # High-value interactions boost score more
                if interaction_type in ['whatsapp_click', 'phone_click', 'form_submit']:
                    lead.engagement_count += 1
                    lead.lead_score = min(lead.lead_score + 15, 100)
                    lead.update_temperature()
                    
                    # If they clicked WhatsApp/phone, they're very interested
                    if interaction_type in ['whatsapp_click', 'phone_click']:
                        lead.status = LeadStatus.REPLIED  # They're engaging!
            
            elif event_type == 'page_exit':
                time_on_page = data.get('time_on_page', 0)
                # Longer time = more engagement
                if time_on_page > 60:  # More than 1 minute
                    lead.engagement_count += 1
                    lead.lead_score = min(lead.lead_score + 5, 100)
                    lead.update_temperature()
            
            db.session.commit()
        
        # Store analytics data (for reporting)
        analytics_file = '/home/behar/Desktop/website-generator/demo_analytics.json'
        try:
            if os.path.exists(analytics_file):
                with open(analytics_file, 'r', encoding='utf-8') as f:
                    analytics = json.load(f)
            else:
                analytics = {}
            
            if business_name not in analytics:
                analytics[business_name] = {
                    'total_views': 0,
                    'unique_visitors': [],
                    'views': [],
                    'interactions': []
                }
            
            # Add event
            event_record = {
                'event_type': event_type,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'data': data
            }
            
            if event_type == 'page_view':
                analytics[business_name]['total_views'] += 1
                analytics[business_name]['views'].append(event_record)
                
                # Track unique visitor (by IP or user agent)
                ip = data.get('ip_address') or request.remote_addr
                if ip not in analytics[business_name]['unique_visitors']:
                    analytics[business_name]['unique_visitors'].append(ip)
            
            elif event_type == 'interaction':
                analytics[business_name]['interactions'].append(event_record)
            
            # Save analytics
            with open(analytics_file, 'w', encoding='utf-8') as f:
                json.dump(analytics, f, indent=2, ensure_ascii=False)
        
        except Exception as e:
            # Analytics file error shouldn't break the API
            print(f"Warning: Could not save analytics: {e}")
        
        return jsonify({
            'success': True,
            'lead_found': lead is not None,
            'lead_id': lead.id if lead else None
        }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@demo_analytics_bp.route('/stats/<business_name>', methods=['GET'])
def get_demo_stats(business_name):
    """Get statistics for a specific demo"""
    try:
        from demo_analytics import get_demo_stats
        stats = get_demo_stats(business_name)
        return jsonify(stats), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@demo_analytics_bp.route('/update-engagement', methods=['POST'])
def update_lead_engagement():
    """Update lead engagement score (called from demo_analytics.py)"""
    try:
        data = request.get_json()
        business_name = data.get('business_name')
        engagement_boost = data.get('engagement_boost', 1)
        
        if not business_name:
            return jsonify({'error': 'business_name required'}), 400
        
        # Find lead
        lead = Lead.query.filter(
            db.func.lower(Lead.name) == business_name.lower()
        ).first()
        
        if lead:
            lead.engagement_count += 1
            lead.lead_score = min(lead.lead_score + engagement_boost, 100)
            lead.update_temperature()
            db.session.commit()
            
            return jsonify({
                'success': True,
                'lead_id': lead.id,
                'new_score': lead.lead_score,
                'temperature': lead.temperature.value
            }), 200
        else:
            return jsonify({'error': 'Lead not found'}), 404
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500
