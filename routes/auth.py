from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, session, jsonify
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime, timezone, timedelta
import logging
import secrets
import hashlib

logger = logging.getLogger(__name__)
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User, UserRole
from services.user_email_service import UserEmailService
from services.two_factor_service import TwoFactorService
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
        def log_login(*args, **kwargs):
            pass
        @staticmethod
        def log_logout(*args, **kwargs):
            pass
        @staticmethod
        def log_security_event(*args, **kwargs):
            pass

auth_bp = Blueprint('auth', __name__)

# Rate limiting for login - 5 attempts per minute, 20 per hour
def get_login_rate_limit_key():
    """Get rate limit key based on IP address"""
    return request.remote_addr or 'unknown'


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember', False)
        
        # Input validation
        if not username:
            flash('Username is required.', 'danger')
            return render_template('auth/login.html')
        if not password:
            flash('Password is required.', 'danger')
            return render_template('auth/login.html')
        if len(username) > 80:
            flash('Username must be 80 characters or less.', 'danger')
            return render_template('auth/login.html')
        
        user = User.query.filter_by(username=username).first()
        
        # Check if account is locked
        if user and user.locked_until and user.locked_until > datetime.now(timezone.utc):
            remaining_time = (user.locked_until - datetime.now(timezone.utc)).total_seconds() / 60
            flash(f'Account locked due to too many failed login attempts. Try again in {int(remaining_time)} minutes.', 'danger')
            return render_template('auth/login.html')
        
        # Check if lockout period has expired
        if user and user.locked_until and user.locked_until <= datetime.now(timezone.utc):
            user.locked_until = None
            user.failed_login_attempts = 0
            db.session.commit()
        
        if user and user.check_password(password):
            if not user.is_active:
                flash('Your account is disabled.', 'danger')
                return render_template('auth/login.html')
            
            # Successful login - reset failed attempts and update last login
            user.failed_login_attempts = 0
            user.locked_until = None
            user.last_login = datetime.now(timezone.utc)
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
            
            # Check if 2FA is enabled
            if user.two_factor_enabled:
                # Store user ID in session for 2FA verification with 5-minute timeout
                session['2fa_user_id'] = user.id
                session['2fa_remember'] = remember
                session['2fa_next'] = request.args.get('next')
                session['2fa_expires'] = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
                return redirect(url_for('auth.verify_2fa'))
            
            login_user(user, remember=remember)
            
            # Log successful login
            AuditLogger.log_login(user.id, success=True)
            
            next_page = request.args.get('next')
            return redirect(next_page or url_for('main.index'))
        
        # Failed login - increment attempts
        if user:
            user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
            
            # Lock account after 5 failed attempts for 30 minutes
            if user.failed_login_attempts >= 5:
                from datetime import timedelta
                user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=30)
                try:
                    db.session.commit()
                except Exception:
                    db.session.rollback()
                
                # Log failed login and account lockout
                AuditLogger.log_login(user.id, success=False, error_message='Too many failed attempts')
                AuditLogger.log_security_event('account_locked', user_id=user.id, 
                                             details={'reason': 'too_many_failed_attempts'})
                
                flash('Too many failed login attempts. Account locked for 30 minutes.', 'danger')
            else:
                try:
                    db.session.commit()
                except Exception:
                    db.session.rollback()
                
                # Log failed login attempt
                AuditLogger.log_login(user.id, success=False, error_message='Invalid password')
                
                remaining_attempts = 5 - user.failed_login_attempts
                if remaining_attempts <= 2:
                    flash(f'Invalid username or password. {remaining_attempts} attempt(s) remaining before account lockout.', 'warning')
                else:
                    flash('Invalid username or password.', 'danger')
        else:
            # Log failed login (user not found)
            AuditLogger.log_login(None, success=False, error_message='User not found')
            flash('Invalid username or password.', 'danger')
    
    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    user_id = current_user.id
    logout_user()
    
    # Log logout
    AuditLogger.log_logout(user_id)
    
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    # Only allow registration if no users exist (first user becomes admin)
    # Or if current user is admin
    user_count = User.query.count()
    
    if user_count > 0 and (not current_user.is_authenticated or current_user.role != UserRole.ADMIN):
        flash('Registration is disabled. Contact an administrator.', 'warning')
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        # Input validation
        if not username:
            flash('Username is required.', 'danger')
            return render_template('auth/register.html')
        if len(username) > 80:
            flash('Username must be 80 characters or less.', 'danger')
            return render_template('auth/register.html')
        if not email or '@' not in email:
            flash('Valid email is required.', 'danger')
            return render_template('auth/register.html')
        if len(email) > 120:
            flash('Email must be 120 characters or less.', 'danger')
            return render_template('auth/register.html')
        if not password:
            flash('Password is required.', 'danger')
            return render_template('auth/register.html')
        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'danger')
            return render_template('auth/register.html')
        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('auth/register.html')
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists.', 'danger')
            return render_template('auth/register.html')
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return render_template('auth/register.html')
        
        # First user becomes admin
        role = UserRole.ADMIN if user_count == 0 else UserRole.SALES
        
        # Generate email verification token
        verification_token = secrets.token_urlsafe(32)
        
        user = User(username=username, email=email, role=role, email_verification_token=verification_token)
        user.set_password(password)
        
        try:
            db.session.add(user)
            db.session.commit()
            
            # Send verification email (if email is configured)
            email_result = UserEmailService.send_verification_email(user, verification_token)
            if not email_result.get('success'):
                logger.warning(f"Could not send verification email: {email_result.get('error')}")
                flash('Registration successful, but verification email could not be sent. Please contact an administrator.', 'warning')
            else:
                flash('Registration successful! Please check your email to verify your account.', 'success')
            
            return redirect(url_for('auth.login'))
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.exception("Error registering user")
            flash('Error during registration. Please try again.', 'danger')
    
    return render_template('auth/register.html', first_user=(user_count == 0))


@auth_bp.route('/users')
@login_required
def users():
    if current_user.role != UserRole.ADMIN:
        flash('Access denied.', 'danger')
        return redirect(url_for('main.index'))
    
    users = User.query.all()
    return render_template('auth/users.html', users=users)


@auth_bp.route('/users/<int:user_id>/toggle', methods=['POST'])
@login_required
def toggle_user(user_id):
    if current_user.role != UserRole.ADMIN:
        flash('Access denied.', 'danger')
        return redirect(url_for('main.index'))
    
    user = db.session.get(User, user_id)
    if not user:
        abort(404)
    if user.id == current_user.id:
        flash('Cannot disable your own account.', 'warning')
    else:
        try:
            user.is_active = not user.is_active
            db.session.commit()
            flash(f"User {'enabled' if user.is_active else 'disabled'}.", 'success')
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.exception("Error toggling user status")
            flash('Error updating user status. Please try again.', 'danger')
    
    return redirect(url_for('auth.users'))


@auth_bp.route('/users/<int:user_id>/role', methods=['POST'])
@login_required
def change_role(user_id):
    if current_user.role != UserRole.ADMIN:
        flash('Access denied.', 'danger')
        return redirect(url_for('main.index'))
    
    user = db.session.get(User, user_id)
    if not user:
        abort(404)
    new_role = request.form.get('role')
    
    try:
        user.role = UserRole(new_role)
        db.session.commit()
        flash('Role updated.', 'success')
    except ValueError:
        flash('Invalid role.', 'danger')
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.exception("Error updating user role")
        flash('Error updating role. Please try again.', 'danger')
    
    return redirect(url_for('auth.users'))


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Request password reset"""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        
        if not email:
            flash('Email is required.', 'danger')
            return render_template('auth/forgot_password.html')
        
        user = User.query.filter_by(email=email).first()
        
        # Always show success message (security: don't reveal if email exists)
        if user:
            # Generate reset token (store plain token, hash for comparison)
            reset_token = secrets.token_urlsafe(32)
            # Store hashed token in database for security
            token_hash = hashlib.sha256(reset_token.encode()).hexdigest()
            user.password_reset_token = token_hash
            user.password_reset_expires = datetime.now(timezone.utc) + timedelta(hours=1)
            
            try:
                db.session.commit()
                
                # Log password reset request
                AuditLogger.log_security_event('password_reset_requested', user_id=user.id)
                
                # Send reset email with plain token (will be hashed when received)
                email_result = UserEmailService.send_password_reset_email(user, reset_token)
                if not email_result.get('success'):
                    logger.warning(f"Could not send password reset email: {email_result.get('error')}")
                    flash('Error sending reset email. Please contact an administrator.', 'danger')
                else:
                    flash('If that email exists, a password reset link has been sent.', 'info')
            except SQLAlchemyError as e:
                db.session.rollback()
                logger.exception("Error generating password reset token")
                flash('Error processing request. Please try again.', 'danger')
        else:
            # Still show success (security best practice)
            flash('If that email exists, a password reset link has been sent.', 'info')
        
        return redirect(url_for('auth.login'))
    
    return render_template('auth/forgot_password.html')


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Reset password with token"""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    # Hash the token to compare
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    
    user = User.query.filter_by(password_reset_token=token_hash).first()
    
    if not user:
        flash('Invalid or expired reset token.', 'danger')
        return redirect(url_for('auth.login'))
    
    if not user.password_reset_expires or user.password_reset_expires < datetime.now(timezone.utc):
        flash('Reset token has expired. Please request a new one.', 'danger')
        user.password_reset_token = None
        user.password_reset_expires = None
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
        return redirect(url_for('auth.forgot_password'))
    
    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        if not password:
            flash('Password is required.', 'danger')
            return render_template('auth/reset_password.html', token=token)
        
        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'danger')
            return render_template('auth/reset_password.html', token=token)
        
        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('auth/reset_password.html', token=token)
        
        # Reset password
        user.set_password(password)
        user.password_reset_token = None
        user.password_reset_expires = None
        user.failed_login_attempts = 0  # Reset failed attempts
        user.locked_until = None
        
        try:
            db.session.commit()
            
            # Log password reset
            AuditLogger.log_security_event('password_reset_completed', user_id=user.id)
            
            flash('Password reset successful! Please login with your new password.', 'success')
            return redirect(url_for('auth.login'))
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.exception("Error resetting password")
            flash('Error resetting password. Please try again.', 'danger')
    
    return render_template('auth/reset_password.html', token=token)


@auth_bp.route('/verify-email/<token>')
def verify_email(token):
    """Verify email address with token"""
    user = User.query.filter_by(email_verification_token=token).first()
    
    if not user:
        flash('Invalid verification token.', 'danger')
        return redirect(url_for('auth.login'))
    
    if user.email_verified:
        flash('Email already verified.', 'info')
        return redirect(url_for('main.index') if current_user.is_authenticated else url_for('auth.login'))
    
    user.email_verified = True
    user.email_verification_token = None
    
    try:
        db.session.commit()
        flash('Email verified successfully!', 'success')
        if not current_user.is_authenticated:
            flash('Please login to continue.', 'info')
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.exception("Error verifying email")
        flash('Error verifying email. Please try again.', 'danger')
    
    return redirect(url_for('auth.login') if not current_user.is_authenticated else url_for('main.index'))


@auth_bp.route('/verify-2fa', methods=['GET', 'POST'])
def verify_2fa():
    """Verify 2FA token during login"""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    user_id = session.get('2fa_user_id')
    if not user_id:
        flash('Please login first.', 'info')
        return redirect(url_for('auth.login'))

    # Check if 2FA session has expired (5 minutes)
    expires_str = session.get('2fa_expires')
    if expires_str:
        try:
            expires = datetime.fromisoformat(expires_str)
            if datetime.now(timezone.utc) > expires:
                # Clear expired 2FA session
                session.pop('2fa_user_id', None)
                session.pop('2fa_remember', None)
                session.pop('2fa_next', None)
                session.pop('2fa_expires', None)
                flash('2FA session expired. Please login again.', 'warning')
                return redirect(url_for('auth.login'))
        except (ValueError, TypeError):
            pass  # If parsing fails, continue with verification
    
    user = db.session.get(User, user_id)
    if not user or not user.two_factor_enabled:
        session.pop('2fa_user_id', None)
        flash('2FA not enabled for this account.', 'warning')
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        token = request.form.get('token', '').strip()
        
        if not token:
            flash('Please enter your 2FA code.', 'danger')
            return render_template('auth/verify_2fa.html')
        
        # Verify 2FA token
        if TwoFactorService.verify_2fa(user, token):
            # Clear 2FA session
            remember = session.pop('2fa_remember', False)
            next_page = session.pop('2fa_next', None)
            session.pop('2fa_user_id', None)
            
            login_user(user, remember=remember)
            
            # Log successful login with 2FA
            AuditLogger.log_login(user.id, success=True, details={'2fa_used': True})
            
            return redirect(next_page or url_for('main.index'))
        else:
            # Log failed 2FA attempt
            AuditLogger.log_security_event('2fa_verification_failed', user_id=user.id)
            flash('Invalid 2FA code. Please try again.', 'danger')
    
    return render_template('auth/verify_2fa.html')


@auth_bp.route('/settings/2fa', methods=['GET', 'POST'])
@login_required
def two_factor_settings():
    """Manage 2FA settings"""
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'enable':
            # Generate secret and QR code
            secret = TwoFactorService.generate_secret()
            qr_code = TwoFactorService.generate_qr_code(current_user, secret)
            
            # Store secret in session temporarily
            session['2fa_setup_secret'] = secret
            
            return render_template('auth/setup_2fa.html', secret=secret, qr_code=qr_code)
        
        elif action == 'verify_enable':
            # Verify token and enable 2FA
            secret = session.get('2fa_setup_secret')
            token = request.form.get('token', '').strip()
            
            if not secret:
                flash('2FA setup session expired. Please try again.', 'danger')
                return redirect(url_for('auth.two_factor_settings'))
            
            if not token:
                flash('Please enter the verification code.', 'danger')
                secret = session.get('2fa_setup_secret')
                qr_code = TwoFactorService.generate_qr_code(current_user, secret)
                return render_template('auth/setup_2fa.html', secret=secret, qr_code=qr_code)
            
            success, backup_codes, error = TwoFactorService.enable_2fa(current_user, secret, token)
            
            if success:
                session.pop('2fa_setup_secret', None)
                AuditLogger.log_security_event('2fa_enabled', user_id=current_user.id)
                return render_template('auth/2fa_backup_codes.html', backup_codes=backup_codes)
            else:
                flash(f'Error: {error}', 'danger')
                secret = session.get('2fa_setup_secret')
                qr_code = TwoFactorService.generate_qr_code(current_user, secret)
                return render_template('auth/setup_2fa.html', secret=secret, qr_code=qr_code)
        
        elif action == 'disable':
            password = request.form.get('password', '')
            
            # Verify password
            if not current_user.check_password(password):
                flash('Invalid password.', 'danger')
                return redirect(url_for('auth.two_factor_settings'))
            
            success, error = TwoFactorService.disable_2fa(current_user)
            
            if success:
                AuditLogger.log_security_event('2fa_disabled', user_id=current_user.id)
                flash('2FA has been disabled.', 'success')
            else:
                flash(f'Error disabling 2FA: {error}', 'danger')
    
    return render_template('auth/2fa_settings.html', user=current_user)


@auth_bp.route('/resend-verification')
@login_required
def resend_verification():
    """Resend email verification"""
    if current_user.email_verified:
        flash('Email already verified.', 'info')
        return redirect(url_for('main.index'))
    
    # Generate new verification token
    verification_token = secrets.token_urlsafe(32)
    current_user.email_verification_token = verification_token
    
    try:
        db.session.commit()
        
        email_result = UserEmailService.send_verification_email(current_user, verification_token)
        if email_result.get('success'):
            flash('Verification email sent! Please check your inbox.', 'success')
        else:
            flash('Error sending verification email. Please contact an administrator.', 'danger')
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.exception("Error resending verification email")
        flash('Error sending verification email. Please try again.', 'danger')
    
    return redirect(url_for('main.index'))
