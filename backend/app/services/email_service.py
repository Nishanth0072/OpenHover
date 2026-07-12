"""
Open-Brain Backend — Email Service

Sends OTP emails via SMTP, or logs them to console in mock mode.
Sender: openbrainofficial@gmail.com
"""

import asyncio
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from loguru import logger

from app.config import settings


async def send_otp_email(email: str, otp: str, purpose: str = "verification") -> None:
    """
    Send a 6-digit OTP to the given email address.

    Args:
        email: Recipient email address.
        otp: The 6-digit OTP code.
        purpose: Either "verification" (registration) or "login" (MFA).

    In mock mode (smtp_mock=True or smtp_host is empty), the OTP is printed
    to the console instead of being emailed.
    """
    if settings.smtp_mock or not settings.smtp_host:
        logger.info(
            f"[MOCK EMAIL] OTP for {email} ({purpose}): {otp}"
        )
        return

    subject = _build_subject(purpose)
    html_body = _build_html_body(otp, purpose)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from_email
    msg["To"] = email
    msg.attach(MIMEText(f"Your Open-Brain OTP code is: {otp}", "plain"))
    msg.attach(MIMEText(html_body, "html"))

    # Run blocking SMTP send in a thread to stay async-friendly
    try:
        await asyncio.to_thread(_smtp_send, email, msg)
        logger.info(f"OTP email sent to {email} ({purpose})")
    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"SMTP Authentication failed for {email}: {e}")
        raise ValueError("SMTP authentication failed. Please check your SMTP username and password (e.g. Google App Password).")
    except (smtplib.SMTPException, OSError) as e:
        logger.error(f"SMTP connection/network error sending to {email}: {e}")
        raise RuntimeError("Failed to connect to the SMTP server. Please check your SMTP host, port, and network connection.")


def _smtp_send(recipient: str, msg: MIMEMultipart) -> None:
    """Blocking SMTP send — called via asyncio.to_thread."""
    if settings.smtp_port == 465:
        # Implicit SSL connection (port 465)
        with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port) as server:
            if settings.smtp_username:
                server.login(settings.smtp_username, settings.smtp_password)
            server.sendmail(settings.smtp_from_email, recipient, msg.as_string())
    elif settings.smtp_use_tls:
        # STARTTLS upgrade (typically port 587)
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(settings.smtp_username, settings.smtp_password)
            server.sendmail(settings.smtp_from_email, recipient, msg.as_string())
    else:
        # Plain SMTP (no encryption)
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            if settings.smtp_username:
                server.login(settings.smtp_username, settings.smtp_password)
            server.sendmail(settings.smtp_from_email, recipient, msg.as_string())


def _build_subject(purpose: str) -> str:
    """Return the email subject line based on purpose."""
    if purpose == "login":
        return "Open-Brain — Your Login Verification Code"
    return "Open-Brain — Verify Your Email"


def _build_html_body(otp: str, purpose: str) -> str:
    """Return a simple HTML email body containing the OTP."""
    action = "log in" if purpose == "login" else "complete your registration"
    return f"""
    <div style="font-family: Arial, sans-serif; max-width: 480px; margin: auto; padding: 24px;">
        <h2 style="color: #2563eb;">Open-Brain</h2>
        <p>Use the code below to {action}:</p>
        <div style="font-size: 32px; font-weight: bold; letter-spacing: 8px;
                    background: #f1f5f9; border-radius: 8px; padding: 16px;
                    text-align: center; margin: 24px 0;">
            {otp}
        </div>
        <p style="color: #64748b; font-size: 13px;">
            This code expires in {settings.otp_expire_minutes} minutes.
            If you didn't request this, you can safely ignore this email.
        </p>
    </div>
    """
