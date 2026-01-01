"""
Two-Factor Authentication Service
Implements TOTP-based 2FA using pyotp
"""
import pyotp
import qrcode
import io
import base64
import secrets
import json
from datetime import datetime, timezone
from flask import current_app, url_for
from models import db, User
import logging

logger = logging.getLogger(__name__)


class TwoFactorService:
    """Service for managing two-factor authentication"""
    
    @staticmethod
    def generate_secret():
        """Generate a new TOTP secret"""
        return pyotp.random_base32()
    
    @staticmethod
    def generate_qr_code(user, secret):
        """
        Generate QR code for 2FA setup
        
        Args:
            user: User object
            secret: TOTP secret (base32)
        
        Returns:
            Base64-encoded PNG image data
        """
        # Create TOTP URI
        issuer = current_app.config.get('APP_NAME', 'Lead CRM')
        totp_uri = pyotp.totp.TOTP(secret).provisioning_uri(
            name=user.email or user.username,
            issuer_name=issuer
        )
        
        # Generate QR code
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(totp_uri)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to base64
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        img_str = base64.b64encode(buffer.getvalue()).decode()
        
        return img_str
    
    @staticmethod
    def verify_token(secret, token):
        """
        Verify a TOTP token
        
        Args:
            secret: TOTP secret (base32)
            token: 6-digit token from authenticator app
        
        Returns:
            True if token is valid, False otherwise
        """
        try:
            totp = pyotp.TOTP(secret)
            return totp.verify(token, valid_window=1)  # Allow 1 time step tolerance
        except Exception as e:
            logger.exception(f"Error verifying 2FA token: {e}")
            return False
    
    @staticmethod
    def generate_backup_codes(count=10):
        """
        Generate backup codes for 2FA
        
        Args:
            count: Number of backup codes to generate
        
        Returns:
            List of backup codes (strings)
        """
        codes = []
        for _ in range(count):
            # Generate 8-digit code
            code = ''.join([str(secrets.randbelow(10)) for _ in range(8)])
            codes.append(code)
        return codes
    
    @staticmethod
    def verify_backup_code(user, code):
        """
        Verify and consume a backup code
        
        Args:
            user: User object
            code: Backup code to verify
        
        Returns:
            True if code is valid and consumed, False otherwise
        """
        if not user.backup_codes:
            return False
        
        try:
            codes = json.loads(user.backup_codes)
            if code in codes:
                # Remove used code
                codes.remove(code)
                user.backup_codes = json.dumps(codes) if codes else None
                try:
                    db.session.commit()
                except Exception:
                    db.session.rollback()
                    return False
                return True
            return False
        except (json.JSONDecodeError, Exception) as e:
            logger.exception(f"Error verifying backup code: {e}")
            return False
    
    @staticmethod
    def enable_2fa(user, secret, verification_token):
        """
        Enable 2FA for a user after verifying the token
        
        Args:
            user: User object
            secret: TOTP secret
            verification_token: Token from authenticator app to verify
        
        Returns:
            tuple: (success: bool, backup_codes: list or None, error: str or None)
        """
        # Verify the token first
        if not TwoFactorService.verify_token(secret, verification_token):
            return False, None, "Invalid verification token"
        
        # Generate backup codes
        backup_codes = TwoFactorService.generate_backup_codes()
        
        # Save to user
        user.two_factor_enabled = True
        user.two_factor_secret = secret
        user.backup_codes = json.dumps(backup_codes)
        
        try:
            db.session.commit()
            logger.info(f"2FA enabled for user {user.id}")
            return True, backup_codes, None
        except Exception as e:
            db.session.rollback()
            logger.exception(f"Error enabling 2FA: {e}")
            return False, None, str(e)
    
    @staticmethod
    def disable_2fa(user):
        """
        Disable 2FA for a user
        
        Args:
            user: User object
        
        Returns:
            tuple: (success: bool, error: str or None)
        """
        user.two_factor_enabled = False
        user.two_factor_secret = None
        user.backup_codes = None
        
        try:
            db.session.commit()
            logger.info(f"2FA disabled for user {user.id}")
            return True, None
        except Exception as e:
            db.session.rollback()
            logger.exception(f"Error disabling 2FA: {e}")
            return False, str(e)
    
    @staticmethod
    def verify_2fa(user, token):
        """
        Verify 2FA token or backup code during login
        
        Args:
            user: User object
            token: TOTP token or backup code
        
        Returns:
            True if valid, False otherwise
        """
        if not user.two_factor_enabled or not user.two_factor_secret:
            return False
        
        # Try TOTP token first
        if TwoFactorService.verify_token(user.two_factor_secret, token):
            return True
        
        # Try backup code
        if TwoFactorService.verify_backup_code(user, token):
            return True
        
        return False
