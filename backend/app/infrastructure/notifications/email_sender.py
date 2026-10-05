"""
Email sending adapter — lives under infrastructure/notifications/ per
ARCHITECTURE.md §3 ("push/email/SMS abstraction"). Auth is the first
consumer (verification + password-reset emails); Notifications module
will extend this package later, not replace it (approved decision #7).

Implements app.domain.auth.ports.EmailSender (structurally — Protocols
don't require inheritance).
"""
import logging
import smtplib
from email.message import EmailMessage

logger = logging.getLogger("keymood.notifications")


class SmtpEmailSender:
    """Real SMTP implementation. Works against any standard SMTP server —
    a local dev mailhog/mailpit instance today, a transactional email
    provider's SMTP endpoint in production. No provider-specific SDK
    lock-in at this layer."""

    def __init__(self, host: str, port: int, username: str, password: str, use_tls: bool, from_address: str):
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._use_tls = use_tls
        self._from_address = from_address

    def send(self, to: str, subject: str, body_text: str, body_html: str | None = None) -> None:
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = self._from_address
        message["To"] = to
        message.set_content(body_text)
        if body_html:
            message.add_alternative(body_html, subtype="html")

        with smtplib.SMTP(self._host, self._port, timeout=10) as smtp:
            if self._use_tls:
                smtp.starttls()
            if self._username:
                smtp.login(self._username, self._password)
            smtp.send_message(message)

        logger.info("email_sent", extra={"to": to, "subject": subject})
