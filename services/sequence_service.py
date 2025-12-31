from datetime import datetime, timezone, timedelta
from models import db, Lead, Sequence, SequenceStep, ContactLog, LeadStatus, ContactChannel
from services.contact_service import ContactService


class SequenceService:
    """Service for managing automated outreach sequences"""
    
    @staticmethod
    def enroll_lead(lead, sequence_id):
        """Enroll a lead in a sequence"""
        sequence = Sequence.query.get(sequence_id)
        if not sequence or not sequence.is_active:
            return False
        
        lead.sequence_id = sequence_id
        lead.sequence_step = 0
        
        # Schedule first step
        first_step = sequence.steps.filter_by(step_number=1).first()
        if first_step:
            delay = timedelta(days=first_step.delay_days, hours=first_step.delay_hours)
            lead.next_followup = datetime.now(timezone.utc) + delay
        
        db.session.commit()
        return True
    
    @staticmethod
    def unenroll_lead(lead):
        """Remove a lead from their current sequence"""
        lead.sequence_id = None
        lead.sequence_step = 0
        lead.next_followup = None
        db.session.commit()
    
    @staticmethod
    def process_due_sequences():
        """Process all leads that are due for their next sequence step"""
        
        now = datetime.now(timezone.utc)
        
        # Find leads due for follow-up
        due_leads = Lead.query.filter(
            Lead.sequence_id.isnot(None),
            Lead.next_followup <= now,
            Lead.status.in_([LeadStatus.NEW, LeadStatus.CONTACTED])
        ).all()
        
        results = {'processed': 0, 'sent': 0, 'errors': []}
        
        for lead in due_leads:
            try:
                result = SequenceService.execute_next_step(lead)
                results['processed'] += 1
                if result.get('success'):
                    results['sent'] += 1
            except Exception as e:
                results['errors'].append({'lead_id': lead.id, 'error': str(e)})
        
        return results
    
    @staticmethod
    def execute_next_step(lead):
        """Execute the next step in a lead's sequence"""
        
        if not lead.sequence_id:
            return {'success': False, 'error': 'Lead not in sequence'}
        
        sequence = Sequence.query.get(lead.sequence_id)
        if not sequence or not sequence.is_active:
            return {'success': False, 'error': 'Sequence inactive'}
        
        # Check if lead has responded - stop sequence
        if lead.status == LeadStatus.REPLIED:
            SequenceService.unenroll_lead(lead)
            return {'success': False, 'error': 'Lead responded, sequence stopped'}
        
        next_step_num = lead.sequence_step + 1
        step = sequence.steps.filter_by(step_number=next_step_num).first()
        
        if not step:
            # Sequence complete
            SequenceService.unenroll_lead(lead)
            return {'success': True, 'completed': True}
        
        # Check condition
        if step.send_if_no_response and lead.last_response:
            SequenceService.unenroll_lead(lead)
            return {'success': False, 'error': 'Lead responded, sequence stopped'}
        
        # Get template and personalize message
        template = step.template
        if not template:
            return {'success': False, 'error': 'No template for step'}
        
        message = ContactService.personalize_message(template.content, lead)
        
        # Send based on channel
        result = None
        if step.channel == ContactChannel.WHATSAPP:
            result = ContactService.send_whatsapp(
                lead, message,
                template_id=template.id,
                is_automated=True
            )
        elif step.channel == ContactChannel.EMAIL:
            subject = ContactService.personalize_message(template.subject or '', lead)
            result = ContactService.send_email(
                lead, subject, message,
                template_id=template.id,
                is_automated=True
            )
        elif step.channel == ContactChannel.SMS:
            result = ContactService.send_sms(
                lead, message,
                template_id=template.id,
                is_automated=True
            )
        
        if result and result.get('success'):
            # Update lead
            lead.sequence_step = next_step_num
            
            # Schedule next step
            next_next_step = sequence.steps.filter_by(step_number=next_step_num + 1).first()
            if next_next_step:
                delay = timedelta(days=next_next_step.delay_days, hours=next_next_step.delay_hours)
                lead.next_followup = datetime.now(timezone.utc) + delay
            else:
                lead.next_followup = None
            
            db.session.commit()
        
        return result or {'success': False, 'error': 'Send failed'}
    
    @staticmethod
    def create_default_sequence():
        """Create a default multi-channel outreach sequence"""
        
        # Check if default exists
        if Sequence.query.filter_by(name='Default Outreach').first():
            return None
        
        sequence = Sequence(
            name='Default Outreach',
            description='3-step multi-channel sequence: WhatsApp -> Email -> Final WhatsApp'
        )
        db.session.add(sequence)
        db.session.flush()
        
        # Will need templates to be created first
        # This just creates the sequence structure
        
        db.session.commit()
        return sequence
