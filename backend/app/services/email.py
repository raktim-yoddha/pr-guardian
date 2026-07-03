"""Email service for sending OTP verification emails."""
from __future__ import annotations

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import random
import string
from datetime import datetime, timedelta

from app.core.config import settings

# Simple in-memory OTP store (in production, use Redis)
_otp_store: dict[str, tuple[str, datetime]] = {}


def generate_otp(length: int = 6) -> str:
    """Generate a random OTP code."""
    return "".join(random.choices(string.digits, k=length))


def store_otp(email: str, otp: str, expires_minutes: int = 10) -> None:
    """Store OTP with expiration time."""
    expires_at = datetime.now() + timedelta(minutes=expires_minutes)
    _otp_store[email] = (otp, expires_at)


def verify_otp(email: str, otp: str) -> bool:
    """Verify OTP code."""
    if email not in _otp_store:
        return False
    
    stored_otp, expires_at = _otp_store[email]
    
    if datetime.now() > expires_at:
        del _otp_store[email]
        return False
    
    if stored_otp != otp:
        return False
    
    # OTP verified, remove it
    del _otp_store[email]
    return True


async def send_otp_email(email: str, otp: str) -> bool:
    """Send OTP verification email."""
    if not all([settings.SMTP_HOST, settings.SMTP_USER, settings.SMTP_PASSWORD, settings.SMTP_FROM_EMAIL]):
        # For development, just log the OTP
        print(f"OTP for {email}: {otp}")
        return True
    
    try:
        msg = MIMEMultipart()
        msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
        msg["To"] = email
        msg["Subject"] = "Your PR Guardian Verification Code"
        
        body = f"""
Your verification code is: {otp}

This code will expire in 10 minutes.

If you didn't request this code, please ignore this email.
"""
        
        msg.attach(MIMEText(body, "plain"))
        
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)
        
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False
