import smtplib
import imaplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from langchain.tools import tool

from ..config.settings import get_settings
from ..core.logger import setup_logging


def connect_smtp():
    """Connect to SMTP server using env settings."""
    settings = get_settings()
    server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_ssl_port, timeout=30)
    server.login(settings.email_address, settings.email_password)
    return server


def connect_imap():
    """Connect to IMAP server using env settings."""
    settings = get_settings()
    mail = imaplib.IMAP4_SSL(settings.imap_host)
    mail.login(settings.email_address, settings.email_password)
    return mail


@tool
def send_email(content: str, to_email: str) -> str:
    """Send an email using credentials from .env. Return 'ok' or 'error: ...'."""
    settings = get_settings()
    logger = setup_logging(settings.log_level)

    if not settings.email_address or not settings.email_password:
        return "error: missing EMAIL_ADDRESS or EMAIL_PASSWORD in env"

    try:
        smtp_server = connect_smtp()

        msg = MIMEMultipart()
        msg["From"] = settings.email_address
        msg["To"] = to_email
        msg["Subject"] = "自动邮件"

        email_content = f"自动生成的邮件：\n\n{content}"
        msg.attach(MIMEText(email_content, "plain"))

        smtp_server.sendmail(settings.email_address, to_email, msg.as_string())
        smtp_server.quit()
        logger.info(f"邮件已发送到 {to_email}")
        return "ok"
    except Exception as e:
        logger.error(f"发送邮件失败: {e}")
        return f"error: {e}"