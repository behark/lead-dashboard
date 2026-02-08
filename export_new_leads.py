#!/usr/bin/env python3
"""
Export new leads from database to JSON for website generation
"""
from models import db, Lead
from app import create_app
import json

def export_leads_to_json():
    app = create_app()
    with app.app_context():
        # Get all leads, especially those without websites
        leads = Lead.query.filter(
            (Lead.has_website == 0) | (Lead.has_website.is_(None))
        ).limit(50).all()
        
        leads_data = []
        for lead in leads:
            lead_dict = {
                "name": lead.name,
                "phone": lead.phone,
                "email": lead.email or "",
                "city": lead.city,
                "address": lead.address or "",
                "country": lead.country or "Kosovo",
                "language": lead.language or "sq",
                "category": lead.category or "business",
                "rating": float(lead.rating) if lead.rating else 4.5,
                "maps_url": lead.maps_url or "",
                "website": lead.website or "",
                "whatsapp_link": lead.whatsapp_link or "",
                "first_message": lead.first_message or "",
                "lead_score": lead.lead_score or 70,
                "temperature": lead.temperature.value if lead.temperature else "WARM",
                "suggested_price": lead.suggested_price or "300 - 500",
                "status": lead.status.value if lead.status else "NEW",
                "notes": lead.notes or "",
                "created_at": str(lead.created_at) if lead.created_at else "",
                "last_contacted": str(lead.last_contacted) if lead.last_contacted else "",
                "last_response": str(lead.last_response) if lead.last_response else "",
                "next_followup": str(lead.next_followup) if lead.next_followup else "",
                "sequence_step": lead.sequence_step or 0,
                "has_website": lead.has_website or 0,
                "response_time_hours": lead.response_time_hours,
                "engagement_count": lead.engagement_count or 0
            }
            leads_data.append(lead_dict)
        
        # Save to selected_leads.json
        with open('selected_leads.json', 'w', encoding='utf-8') as f:
            json.dump(leads_data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Exported {len(leads_data)} leads to selected_leads.json")
        
        # Show sample of leads
        print(f"\n📋 Sample leads:")
        for i, lead in enumerate(leads_data[:5], 1):
            print(f"{i}. {lead['name']} - {lead['category']} - {lead['city']} - Rating: {lead['rating']}⭐")
        
        return leads_data

if __name__ == '__main__':
    export_leads_to_json()
