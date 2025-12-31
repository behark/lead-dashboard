from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db, MessageTemplate, Sequence, SequenceStep, ContactChannel, UserRole

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
        
        if not name or not channel or not content:
            flash('Name, channel, and content are required.', 'danger')
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
            
            flash('Template created.', 'success')
            return redirect(url_for('templates.list_templates'))
        except ValueError as e:
            flash(f'Error: {e}', 'danger')
    
    return render_template('templates/create.html')


@templates_bp.route('/<int:template_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_template(template_id):
    template = MessageTemplate.query.get_or_404(template_id)
    
    if request.method == 'POST':
        template.name = request.form.get('name', template.name)
        template.language = request.form.get('language', template.language)
        template.category = request.form.get('category', template.category)
        template.subject = request.form.get('subject')
        template.content = request.form.get('content', template.content)
        template.variant = request.form.get('variant', template.variant)
        template.is_active = request.form.get('is_active') == 'on'
        
        db.session.commit()
        flash('Template updated.', 'success')
        return redirect(url_for('templates.list_templates'))
    
    return render_template('templates/edit.html', template=template)


@templates_bp.route('/<int:template_id>/delete', methods=['POST'])
@login_required
def delete_template(template_id):
    if current_user.role != UserRole.ADMIN:
        flash('Only admins can delete templates.', 'danger')
        return redirect(url_for('templates.list_templates'))
    
    template = MessageTemplate.query.get_or_404(template_id)
    db.session.delete(template)
    db.session.commit()
    
    flash('Template deleted.', 'success')
    return redirect(url_for('templates.list_templates'))


@templates_bp.route('/<int:template_id>/duplicate', methods=['POST'])
@login_required
def duplicate_template(template_id):
    template = MessageTemplate.query.get_or_404(template_id)
    
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
    db.session.add(new_template)
    db.session.commit()
    
    flash(f'Template duplicated as Variant {new_variant}.', 'success')
    return redirect(url_for('templates.edit_template', template_id=new_template.id))


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
        
        sequence = Sequence(name=name, description=description)
        db.session.add(sequence)
        db.session.commit()
        
        flash('Sequence created. Now add steps.', 'success')
        return redirect(url_for('templates.edit_sequence', sequence_id=sequence.id))
    
    return render_template('templates/create_sequence.html')


@templates_bp.route('/sequences/<int:sequence_id>', methods=['GET', 'POST'])
@login_required
def edit_sequence(sequence_id):
    sequence = Sequence.query.get_or_404(sequence_id)
    templates = MessageTemplate.query.filter_by(is_active=True).all()
    
    if request.method == 'POST':
        sequence.name = request.form.get('name', sequence.name)
        sequence.description = request.form.get('description', sequence.description)
        sequence.is_active = request.form.get('is_active') == 'on'
        
        db.session.commit()
        flash('Sequence updated.', 'success')
    
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
    sequence = Sequence.query.get_or_404(sequence_id)
    
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
    
    return redirect(url_for('templates.edit_sequence', sequence_id=sequence_id))


@templates_bp.route('/sequences/<int:sequence_id>/step/<int:step_id>/delete', methods=['POST'])
@login_required
def delete_sequence_step(sequence_id, step_id):
    step = SequenceStep.query.get_or_404(step_id)
    
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
    
    db.session.commit()
    flash('Step deleted.', 'success')
    
    return redirect(url_for('templates.edit_sequence', sequence_id=sequence_id))


@templates_bp.route('/<int:template_id>/set_default', methods=['POST'])
@login_required
def set_default_template(template_id):
    template = MessageTemplate.query.get_or_404(template_id)
    
    # Set default per (channel, language)
    MessageTemplate.query.filter_by(
        channel=template.channel,
        language=template.language
    ).update({'is_default': False})
    
    # Set this template as default
    template.is_default = True
    
    db.session.commit()
    
    flash(f'{template.name} set as default for {template.channel.value.upper()} ({template.language}).', 'success')
    return redirect(url_for('templates.list_templates'))


@templates_bp.route('/sequences/<int:sequence_id>/delete', methods=['POST'])
@login_required
def delete_sequence(sequence_id):
    if current_user.role != UserRole.ADMIN:
        flash('Only admins can delete sequences.', 'danger')
        return redirect(url_for('templates.list_sequences'))
    
    sequence = Sequence.query.get_or_404(sequence_id)
    
    # Remove sequence from leads
    from models import Lead
    Lead.query.filter_by(sequence_id=sequence_id).update({'sequence_id': None, 'sequence_step': 0})
    
    # Delete steps
    SequenceStep.query.filter_by(sequence_id=sequence_id).delete()
    
    db.session.delete(sequence)
    db.session.commit()
    
    flash('Sequence deleted.', 'success')
    return redirect(url_for('templates.list_sequences'))
