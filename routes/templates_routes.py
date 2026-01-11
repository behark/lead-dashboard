from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, abort
from sqlalchemy.exc import SQLAlchemyError
import logging

logger = logging.getLogger(__name__)
from flask_login import login_required, current_user
from models import db, MessageTemplate, Sequence, SequenceStep, ContactChannel, UserRole
# Import audit logger with graceful fallback
try:
    from utils.audit_logger import AuditLogger
except ImportError:
    # Create a dummy AuditLogger if import fails
    class AuditLogger:
        @staticmethod
        def log(*args, **kwargs):
            pass
        @staticmethod
        def log_template_action(*args, **kwargs):
            pass

templates_bp = Blueprint('templates', __name__, url_prefix='/templates')


@templates_bp.route('/')
@login_required
def list_templates():
    templates = MessageTemplate.query.order_by(MessageTemplate.created_at.desc()).all()
    return render_template('templates/list.html', templates=templates)


@templates_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_template():
    if request.method == 'POST':
        name = request.form.get('name')
        channel = request.form.get('channel')
        language = request.form.get('language', 'sq')
        category = request.form.get('category')
        subject = request.form.get('subject')
        content = request.form.get('content')
        variant = request.form.get('variant', 'A')
        
        # Input validation
        if not name or not name.strip():
            flash('Name is required.', 'danger')
            return render_template('templates/create.html')
        if len(name) > 200:
            flash('Name must be 200 characters or less.', 'danger')
            return render_template('templates/create.html')
        if not channel:
            flash('Channel is required.', 'danger')
            return render_template('templates/create.html')
        if not content or not content.strip():
            flash('Content is required.', 'danger')
            return render_template('templates/create.html')
        if len(content) > 5000:
            flash('Content must be 5000 characters or less.', 'danger')
            return render_template('templates/create.html')
        
        try:
            template = MessageTemplate(
                name=name,
                channel=ContactChannel(channel),
                language=language,
                category=category,
                subject=subject,
                content=content,
                variant=variant
            )
            db.session.add(template)
            db.session.commit()
            
            # Log template creation
            AuditLogger.log_template_action('template_created', template.id, current_user.id,
                                          details={'name': template.name, 'channel': template.channel.value})
            
            flash('Template created.', 'success')
            return redirect(url_for('templates.list_templates'))
        except ValueError as e:
            flash(f'Error: {e}', 'danger')
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.exception("Error creating template")
            flash('Error creating template. Please try again.', 'danger')
    
    return render_template('templates/create.html')


@templates_bp.route('/<int:template_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_template(template_id):
    template = db.session.get(MessageTemplate, template_id)
    if not template:
        abort(404)
    
    if request.method == 'POST':
        # Input validation
        name = request.form.get('name', template.name)
        content = request.form.get('content', template.content)
        
        if name and len(name) > 200:
            flash('Name must be 200 characters or less.', 'danger')
            return render_template('templates/edit.html', template=template)
        if content and len(content) > 5000:
            flash('Content must be 5000 characters or less.', 'danger')
            return render_template('templates/edit.html', template=template)
        
        template.name = name
        template.language = request.form.get('language', template.language)
        template.category = request.form.get('category', template.category)
        template.subject = request.form.get('subject')
        template.content = content
        template.variant = request.form.get('variant', template.variant)
        template.is_active = request.form.get('is_active') == 'on'
        
        try:
            db.session.commit()
            
            # Log template update
            AuditLogger.log_template_action('template_updated', template_id, current_user.id)
            
            flash('Template updated.', 'success')
            return redirect(url_for('templates.list_templates'))
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.exception("Error updating template")
            flash('Error updating template. Please try again.', 'danger')
            return render_template('templates/edit.html', template=template)
    
    return render_template('templates/edit.html', template=template)


@templates_bp.route('/<int:template_id>/delete', methods=['POST'])
@login_required
def delete_template(template_id):
    if current_user.role != UserRole.ADMIN:
        flash('Only admins can delete templates.', 'danger')
        return redirect(url_for('templates.list_templates'))
    
    template = db.session.get(MessageTemplate, template_id)
    if not template:
        abort(404)
    
    try:
        template_id = template.id  # Store before deletion
        db.session.delete(template)
        db.session.commit()
        
        # Log template deletion
        AuditLogger.log_template_action('template_deleted', template_id, current_user.id)
        
        flash('Template deleted.', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.exception("Error deleting template")
        flash('Error deleting template. Please try again.', 'danger')
    return redirect(url_for('templates.list_templates'))


@templates_bp.route('/<int:template_id>/duplicate', methods=['POST'])
@login_required
def duplicate_template(template_id):
    template = db.session.get(MessageTemplate, template_id)
    if not template:
        abort(404)
    
    # Create A/B variant
    new_variant = 'B' if template.variant == 'A' else 'A'
    
    new_template = MessageTemplate(
        name=f"{template.name} (Variant {new_variant})",
        channel=template.channel,
        language=template.language,
        category=template.category,
        subject=template.subject,
        content=template.content,
        variant=new_variant
    )
    try:
        db.session.add(new_template)
        db.session.commit()
        flash(f'Template duplicated as Variant {new_variant}.', 'success')
        return redirect(url_for('templates.edit_template', template_id=new_template.id))
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.exception("Error duplicating template")
        flash('Error duplicating template. Please try again.', 'danger')
        return redirect(url_for('templates.list_templates'))


# Sequences
@templates_bp.route('/sequences')
@login_required
def list_sequences():
    sequences = Sequence.query.order_by(Sequence.created_at.desc()).all()
    return render_template('templates/sequences.html', sequences=sequences)


@templates_bp.route('/sequences/create', methods=['GET', 'POST'])
@login_required
def create_sequence():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        
        if not name:
            flash('Name is required.', 'danger')
            return render_template('templates/create_sequence.html')
        
        try:
            sequence = Sequence(name=name, description=description)
            db.session.add(sequence)
            db.session.commit()
            flash('Sequence created. Now add steps.', 'success')
            return redirect(url_for('templates.edit_sequence', sequence_id=sequence.id))
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.exception("Error creating sequence")
            flash('Error creating sequence. Please try again.', 'danger')
    
    return render_template('templates/create_sequence.html')


@templates_bp.route('/sequences/<int:sequence_id>', methods=['GET', 'POST'])
@login_required
def edit_sequence(sequence_id):
    sequence = db.session.get(Sequence, sequence_id)
    if not sequence:
        abort(404)
    templates = MessageTemplate.query.filter_by(is_active=True).all()
    
    if request.method == 'POST':
        sequence.name = request.form.get('name', sequence.name)
        sequence.description = request.form.get('description', sequence.description)
        sequence.is_active = request.form.get('is_active') == 'on'
        
        try:
            db.session.commit()
            flash('Sequence updated.', 'success')
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.exception("Error updating sequence")
            flash('Error updating sequence. Please try again.', 'danger')
    
    steps = sequence.steps.order_by(SequenceStep.step_number).all()
    
    return render_template(
        'templates/edit_sequence.html',
        sequence=sequence,
        steps=steps,
        templates=templates
    )


@templates_bp.route('/sequences/<int:sequence_id>/add-step', methods=['POST'])
@login_required
def add_sequence_step(sequence_id):
    sequence = db.session.get(Sequence, sequence_id)
    if not sequence:
        abort(404)
    
    # Get next step number
    max_step = db.session.query(db.func.max(SequenceStep.step_number)).filter_by(
        sequence_id=sequence_id
    ).scalar() or 0
    
    channel = request.form.get('channel')
    template_id = request.form.get('template_id')
    delay_days = request.form.get('delay_days', 0, type=int)
    delay_hours = request.form.get('delay_hours', 0, type=int)
    
    try:
        step = SequenceStep(
            sequence_id=sequence_id,
            step_number=max_step + 1,
            channel=ContactChannel(channel),
            template_id=int(template_id) if template_id else None,
            delay_days=delay_days,
            delay_hours=delay_hours
        )
        db.session.add(step)
        db.session.commit()
        flash('Step added.', 'success')
    except (ValueError, TypeError) as e:
        flash(f'Error: {e}', 'danger')
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.exception("Error adding sequence step")
        flash('Error adding step. Please try again.', 'danger')
    
    return redirect(url_for('templates.edit_sequence', sequence_id=sequence_id))


@templates_bp.route('/sequences/<int:sequence_id>/step/<int:step_id>/delete', methods=['POST'])
@login_required
def delete_sequence_step(sequence_id, step_id):
    step = db.session.get(SequenceStep, step_id)
    if not step:
        abort(404)
    
    if step.sequence_id != sequence_id:
        flash('Step not found in this sequence.', 'danger')
        return redirect(url_for('templates.edit_sequence', sequence_id=sequence_id))
    
    db.session.delete(step)
    
    # Renumber remaining steps
    remaining_steps = SequenceStep.query.filter_by(sequence_id=sequence_id).order_by(
        SequenceStep.step_number
    ).all()
    
    for i, s in enumerate(remaining_steps, 1):
        s.step_number = i
    
    try:
        db.session.commit()
        flash('Step deleted.', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.exception("Error deleting sequence step")
        flash('Error deleting step. Please try again.', 'danger')
    
    return redirect(url_for('templates.edit_sequence', sequence_id=sequence_id))


@templates_bp.route('/<int:template_id>/set_default', methods=['POST'])
@login_required
def set_default_template(template_id):
    template = db.session.get(MessageTemplate, template_id)
    if not template:
        abort(404)
    
    # Set default per (channel, language)
    MessageTemplate.query.filter_by(
        channel=template.channel,
        language=template.language
    ).update({'is_default': False})
    
    # Set this template as default
    template.is_default = True
    
    try:
        db.session.commit()
        flash(f'{template.name} set as default for {template.channel.value.upper()} ({template.language}).', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.exception("Error setting default template")
        flash('Error setting default template. Please try again.', 'danger')
    return redirect(url_for('templates.list_templates'))


@templates_bp.route('/sequences/<int:sequence_id>/delete', methods=['POST'])
@login_required
def delete_sequence(sequence_id):
    if current_user.role != UserRole.ADMIN:
        flash('Only admins can delete sequences.', 'danger')
        return redirect(url_for('templates.list_sequences'))
    
    sequence = db.session.get(Sequence, sequence_id)
    if not sequence:
        abort(404)
    
    # Remove sequence from leads
    from models import Lead
    try:
        Lead.query.filter_by(sequence_id=sequence_id).update({'sequence_id': None, 'sequence_step': 0})
        
        # Delete steps
        SequenceStep.query.filter_by(sequence_id=sequence_id).delete()
        
        db.session.delete(sequence)
        db.session.commit()
        flash('Sequence deleted.', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.exception("Error deleting sequence")
        flash('Error deleting sequence. Please try again.', 'danger')
    return redirect(url_for('templates.list_sequences'))
