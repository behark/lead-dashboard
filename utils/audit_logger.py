"""
Audit Logging Utility
Tracks important user actions for compliance and security
"""
from flask import request, current_app, has_request_context
from models import db, AuditLog
from datetime import datetime, timezone
import json
import logging

logger = logging.getLogger(__name__)


class AuditLogger:
    """Service for creating audit log entries"""
    
    @staticmethod
    def log(action, resource_type=None, resource_id=None, user_id=None, 
            status='success', error_message=None, details=None, organization_id=None):
        """
        Create an audit log entry
        
        Args:
            action: Action name (e.g., 'login', 'lead_created', 'template_deleted')
            resource_type: Type of resource affected (e.g., 'lead', 'template', 'user')
            resource_id: ID of resource affected
            user_id: ID of user performing action (None for anonymous)
            status: 'success', 'failure', or 'error'
            error_message: Error message if status is 'failure' or 'error'
            details: Additional context (dict will be JSON-encoded)
            organization_id: Organization ID if applicable
        """
        try:
            # Get request context if available
            ip_address = None
            user_agent = None
            
            if has_request_context():
                ip_address = request.remote_addr
                user_agent = request.headers.get('User-Agent', '')[:255]  # Limit length
            
            # Convert details dict to JSON string
            details_json = None
            if details:
                if isinstance(details, dict):
                    details_json = json.dumps(details)
                else:
                    details_json = str(details)
            
            # Create audit log entry
            audit_log = AuditLog(
                user_id=user_id,
                organization_id=organization_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                ip_address=ip_address,
                user_agent=user_agent,
                timestamp=datetime.now(timezone.utc),
                status=status,
                error_message=error_message,
                details=details_json
            )
            
            db.session.add(audit_log)
            db.session.commit()
            
            logger.debug(f"Audit log created: {action} by user {user_id}")
            
        except Exception as e:
            # Don't fail the main operation if audit logging fails
            logger.exception(f"Error creating audit log: {e}")
            try:
                db.session.rollback()
            except Exception:
                pass
    
    @staticmethod
    def log_login(user_id, success=True, error_message=None):
        """Log user login attempt"""
        AuditLogger.log(
            action='login',
            resource_type='user',
            resource_id=user_id,
            user_id=user_id,
            status='success' if success else 'failure',
            error_message=error_message
        )
    
    @staticmethod
    def log_logout(user_id):
        """Log user logout"""
        AuditLogger.log(
            action='logout',
            resource_type='user',
            resource_id=user_id,
            user_id=user_id
        )
    
    @staticmethod
    def log_lead_action(action, lead_id, user_id, details=None, status='success', error_message=None):
        """Log lead-related actions"""
        AuditLogger.log(
            action=action,  # 'lead_created', 'lead_updated', 'lead_deleted', 'lead_contacted'
            resource_type='lead',
            resource_id=lead_id,
            user_id=user_id,
            status=status,
            error_message=error_message,
            details=details
        )
    
    @staticmethod
    def log_template_action(action, template_id, user_id, details=None, status='success', error_message=None):
        """Log template-related actions"""
        AuditLogger.log(
            action=action,  # 'template_created', 'template_updated', 'template_deleted'
            resource_type='template',
            resource_id=template_id,
            user_id=user_id,
            status=status,
            error_message=error_message,
            details=details
        )
    
    @staticmethod
    def log_user_action(action, target_user_id, user_id, details=None, status='success', error_message=None):
        """Log user management actions"""
        AuditLogger.log(
            action=action,  # 'user_created', 'user_updated', 'user_deleted', 'user_disabled'
            resource_type='user',
            resource_id=target_user_id,
            user_id=user_id,
            status=status,
            error_message=error_message,
            details=details
        )
    
    @staticmethod
    def log_bulk_action(action, job_id, user_id, details=None, status='success', error_message=None):
        """Log bulk operation actions"""
        AuditLogger.log(
            action=action,  # 'bulk_send_started', 'bulk_send_completed', 'bulk_send_failed'
            resource_type='bulk_job',
            resource_id=job_id,
            user_id=user_id,
            status=status,
            error_message=error_message,
            details=details
        )
    
    @staticmethod
    def log_security_event(action, user_id=None, details=None, status='success', error_message=None):
        """Log security-related events"""
        AuditLogger.log(
            action=action,  # 'password_reset_requested', 'password_changed', 'account_locked', 'csrf_attempt'
            resource_type='security',
            user_id=user_id,
            status=status,
            error_message=error_message,
            details=details
        )
