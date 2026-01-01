"""
User Email Service
Sends emails to application users (not leads) for password reset, verification, etc.
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone
from flask import current_app, url_for
import logging

logger = logging.getLogger(__name__)


class UserEmailService:
    """Service for sending emails to application users"""
    
    @staticmethod
    def send_email(to_email, subject, html_body, text_body=None):
        """
        Send email to a user
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            html_body: HTML email body
            text_body: Plain text email body (optional)
        
        Returns:
            dict with 'success' and optional 'error'
        """
        if not current_app.config.get('MAIL_USERNAME'):
            logger.warning("Email not configured - cannot send email")
            return {'success': False, 'error': 'Email not configured'}
        
        if not to_email:
            return {'success': False, 'error': 'No email address'}
        
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = current_app.config['MAIL_DEFAULT_SENDER']
            msg['To'] = to_email
            
            # Plain text version
            if text_body:
                text_part = MIMEText(text_body, 'plain', 'utf-8')
                msg.attach(text_part)
            else:
                # Auto-generate from HTML
                import re
                text_body = re.sub(r'<[^>]+>', '', html_body)
                text_part = MIMEText(text_body, 'plain', 'utf-8')
                msg.attach(text_part)
            
            # HTML version
            html_part = MIMEText(html_body, 'html', 'utf-8')
            msg.attach(html_part)
            
            with smtplib.SMTP(current_app.config['MAIL_SERVER'], current_app.config['MAIL_PORT']) as server:
                if current_app.config['MAIL_USE_TLS']:
                    server.starttls()
                server.login(current_app.config['MAIL_USERNAME'], current_app.config['MAIL_PASSWORD'])
                server.sendmail(msg['From'], [to_email], msg.as_string())
            
            logger.info(f"Email sent to {to_email}: {subject}")
            return {'success': True}
            
        except (smtplib.SMTPException, OSError) as e:
            logger.exception(f"SMTP error sending email to {to_email}")
            return {'success': False, 'error': f'Email error: {str(e)}'}
        except Exception as e:
            logger.exception(f"Unexpected error sending email to {to_email}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def send_password_reset_email(user, reset_token):
        """Send password reset email to user"""
        reset_url = url_for('auth.reset_password', token=reset_token, _external=True)
        
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #1a1a2e;">Password Reset Request</h2>
                <p>Hello {user.username},</p>
                <p>You requested to reset your password. Click the button below to reset it:</p>
                <p style="text-align: center; margin: 30px 0;">
                    <a href="{reset_url}" style="background-color: #007bff; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; display: inline-block;">Reset Password</a>
                </p>
                <p>Or copy and paste this link into your browser:</p>
                <p style="word-break: break-all; color: #666;">{reset_url}</p>
                <p><strong>This link will expire in 1 hour.</strong></p>
                <p>If you didn't request this, please ignore this email.</p>
                <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
                <p style="color: #666; font-size: 12px;">This is an automated message. Please do not reply.</p>
            </div>
        </body>
        </html>
        """
        
        text_body = f"""
        Password Reset Request
        
        Hello {user.username},
        
        You requested to reset your password. Visit this link to reset it:
        {reset_url}
        
        This link will expire in 1 hour.
        
        If you didn't request this, please ignore this email.
        """
        
        return UserEmailService.send_email(
            user.email,
            'Password Reset Request - Lead CRM',
            html_body,
            text_body
        )
    
    @staticmethod
    def send_verification_email(user, verification_token):
        """Send email verification email to user"""
        verify_url = url_for('auth.verify_email', token=verification_token, _external=True)
        
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #1a1a2e;">Verify Your Email</h2>
                <p>Hello {user.username},</p>
                <p>Thank you for registering! Please verify your email address by clicking the button below:</p>
                <p style="text-align: center; margin: 30px 0;">
                    <a href="{verify_url}" style="background-color: #28a745; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; display: inline-block;">Verify Email</a>
                </p>
                <p>Or copy and paste this link into your browser:</p>
                <p style="word-break: break-all; color: #666;">{verify_url}</p>
                <p><strong>This link will expire in 24 hours.</strong></p>
                <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
                <p style="color: #666; font-size: 12px;">This is an automated message. Please do not reply.</p>
            </div>
        </body>
        </html>
        """
        
        text_body = f"""
        Verify Your Email
        
        Hello {user.username},
        
        Thank you for registering! Please verify your email address by visiting this link:
        {verify_url}
        
        This link will expire in 24 hours.
        """
        
        return UserEmailService.send_email(
            user.email,
            'Verify Your Email - Lead CRM',
            html_body,
            text_body
        )
