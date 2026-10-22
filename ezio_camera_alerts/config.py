"""Environment-based settings for the camera alert mailer."""
import os
from dataclasses import dataclass

@dataclass(frozen=True)
class MailerSettings:
    smtp_host: str = "127.0.0.1"
    smtp_port: int = 1025
    sender_email: str = "info@eziosolutions.ai"
    timeout_seconds: float = 15.0

    @classmethod
    def from_env(cls):
        return cls(
            smtp_host=os.getenv("EZIO_SMTP_HOST", "127.0.0.1"),
            smtp_port=int(os.getenv("EZIO_SMTP_PORT", "1025")),
            sender_email=os.getenv("EZIO_ALERT_SENDER", "info@eziosolutions.ai"),
            timeout_seconds=float(os.getenv("EZIO_SMTP_TIMEOUT_SECONDS", "15")),
        )
