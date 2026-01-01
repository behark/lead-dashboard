"""
Database Backup Management Routes
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file, current_app
from flask_login import login_required, current_user
from models import db, UserRole
from utils.backup import BackupService
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

backup_bp = Blueprint('backup', __name__, url_prefix='/backup')


@backup_bp.route('/')
@login_required
def backup_dashboard():
    """Backup management dashboard"""
    # Only admins can access backups
    if current_user.role != UserRole.ADMIN:
        flash('Access denied. Admin only.', 'danger')
        return redirect(url_for('main.index'))
    
    with current_app.app_context():
        backups = BackupService.list_backups()
    
    return render_template('backup/dashboard.html', backups=backups)


@backup_bp.route('/create', methods=['POST'])
@login_required
def create_backup():
    """Manually create a backup"""
    if current_user.role != UserRole.ADMIN:
        return jsonify({'success': False, 'error': 'Access denied'}), 403
    
    try:
        with current_app.app_context():
            result = BackupService.create_backup()
            if result.get('success'):
                size_mb = result.get('size', 0) / 1024 / 1024
                return jsonify({
                    'success': True,
                    'message': f'Backup created successfully ({size_mb:.2f} MB)',
                    'backup_path': result.get('backup_path')
                })
            else:
                return jsonify({'success': False, 'error': result.get('error')}), 500
    except Exception as e:
        logger.exception("Error creating backup")
        return jsonify({'success': False, 'error': str(e)}), 500


@backup_bp.route('/cleanup', methods=['POST'])
@login_required
def cleanup_backups():
    """Clean up old backups"""
    if current_user.role != UserRole.ADMIN:
        return jsonify({'success': False, 'error': 'Access denied'}), 403
    
    try:
        keep_days = int(request.form.get('keep_days', 30))
        with current_app.app_context():
            result = BackupService.cleanup_old_backups(keep_days=keep_days)
        
        freed_mb = result.get('freed_space', 0) / 1024 / 1024
        return jsonify({
            'success': True,
            'message': f'Cleaned up {result.get("deleted_count", 0)} backups, freed {freed_mb:.2f} MB'
        })
    except Exception as e:
        logger.exception("Error cleaning up backups")
        return jsonify({'success': False, 'error': str(e)}), 500
