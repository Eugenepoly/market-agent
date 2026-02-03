"""Email service for sending market reports."""

import smtplib
import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

import markdown

from config import get_config


def send_market_report(report_content: str, subject: Optional[str] = None, test_mode: bool = False) -> bool:
    """Send market report via email.

    Args:
        report_content: The markdown report content.
        subject: Optional custom subject line.
        test_mode: If True, only send to the first recipient.

    Returns:
        True if sent successfully, False otherwise.
    """
    config = get_config()

    if not config.email_enabled:
        return False

    recipients = config.get_email_recipients_list()
    if not all([recipients, config.email_sender, config.email_password]):
        print("Email configuration incomplete, skipping email send")
        return False

    # Test mode: only send to first recipient
    if test_mode:
        recipients = recipients[:1]

    # Build email
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject or f"每日交易者逻辑更新 [{datetime.date.today()}]"
    msg["From"] = config.email_sender
    msg["To"] = ", ".join(recipients)

    # Plain text fallback
    msg.attach(MIMEText(report_content, "plain", "utf-8"))

    # HTML version (render Markdown)
    html_content = markdown.markdown(
        report_content,
        extensions=["tables", "fenced_code"]
    )
    html_body = f"""
    <html>
    <head>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; padding: 20px; max-width: 800px; }}
            h1 {{ color: #1a1a1a; border-bottom: 2px solid #007AFF; padding-bottom: 10px; }}
            h2 {{ color: #333; margin-top: 24px; }}
            ul, ol {{ padding-left: 20px; }}
            li {{ margin: 8px 0; }}
            strong {{ color: #007AFF; }}
            code {{ background: #f4f4f4; padding: 2px 6px; border-radius: 4px; }}
        </style>
    </head>
    <body>
        {html_content}
    </body>
    </html>
    """
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    # Send via Gmail SMTP
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(config.email_sender, config.email_password)
            server.sendmail(config.email_sender, recipients, msg.as_string())
        print(f"✉️ Email sent to {', '.join(recipients)}")
        return True
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        return False
