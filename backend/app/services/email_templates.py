"""
Pure email-content builders for Auth. Deliberately NOT in infrastructure/
— these have no I/O, no SMTP dependency, just string templating, so they
belong with the use-case logic that calls them (services/auth_service.py),
keeping infrastructure/notifications/ limited to the actual send adapter.
"""


def build_verification_email(frontend_base_url: str, token: str) -> tuple[str, str, str]:
    link = f"{frontend_base_url}/verify-email?token={token}"
    subject = "Verify your KeyMood AI account"
    text = f"Welcome to KeyMood AI. Verify your email by visiting: {link}\nThis link expires in 24 hours."
    html = f'<p>Welcome to KeyMood AI.</p><p><a href="{link}">Verify your email</a> (expires in 24 hours).</p>'
    return subject, text, html


def build_password_reset_email(frontend_base_url: str, token: str) -> tuple[str, str, str]:
    link = f"{frontend_base_url}/reset-password?token={token}"
    subject = "Reset your KeyMood AI password"
    text = (
        f"Reset your password by visiting: {link}\n"
        "This link expires in 30 minutes. If you did not request this, ignore this email."
    )
    html = (
        f'<p><a href="{link}">Reset your password</a> (expires in 30 minutes).</p>'
        "<p>If you did not request this, ignore this email.</p>"
    )
    return subject, text, html
