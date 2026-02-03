"""Email service for sending market reports."""

import smtplib
import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from config import get_config


def send_market_report(report_content: str, subject: Optional[str] = None) -> bool:
    """Send market report via email.

    Args:
        report_content: The markdown report content.
        subject: Optional custom subject line.

    Returns:
        True if sent successfully, False otherwise.
    """
    config = get_config()

    if not config.email_enabled:
        return False

    if not all([config.email_recipient, config.email_sender, config.email_password]):
        print("Email configuration incomplete, skipping email send")
        return False

    # Build email
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject or f"Market Update - {datetime.date.today()}"
    msg["From"] = config.email_sender
    msg["To"] = config.email_recipient

    # Plain text version (markdown)
    msg.attach(MIMEText(report_content, "plain", "utf-8"))

    # Send via Gmail SMTP
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(config.email_sender, config.email_password)
            server.sendmail(config.email_sender, config.email_recipient, msg.as_string())
        print(f"✉️ Email sent to {config.email_recipient}")
        return True
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        return False
