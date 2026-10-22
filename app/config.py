"""Configuration for the local SMTP development server and optional relay."""
from dataclasses import dataclass
import os


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().casefold()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean value")


@dataclass(frozen=True)
class Settings:
    host: str = "127.0.0.1"
    port: int = 1025
    spool_dir: str = "mail_spool"
    max_command_line_bytes: int = 8192
    max_data_line_bytes: int = 998
    max_message_bytes: int = 1_000_000
    client_timeout_seconds: float = 60.0
    relay_enabled: bool = False
    relay_host: str = "smtp.hostinger.com"
    relay_port: int = 465
    relay_username: str = ""
    relay_password: str = ""
    relay_security: str = "ssl"
    relay_timeout_seconds: float = 20.0

    @classmethod
    def from_env(cls) -> "Settings":
        """Load configuration; credentials are read only from environment variables."""
        enabled = _env_bool("SMTP_RELAY_ENABLED", False)
        settings = cls(
            host=os.getenv("SMTP_HOST", "127.0.0.1"),
            port=int(os.getenv("SMTP_PORT", "1025")),
            spool_dir=os.getenv("SMTP_SPOOL_DIR", "mail_spool"),
            max_command_line_bytes=int(os.getenv("SMTP_MAX_COMMAND_LINE_BYTES", "8192")),
            max_data_line_bytes=int(os.getenv("SMTP_MAX_DATA_LINE_BYTES", "998")),
            max_message_bytes=int(os.getenv("SMTP_MAX_MESSAGE_BYTES", "1000000")),
            client_timeout_seconds=float(os.getenv("SMTP_CLIENT_TIMEOUT_SECONDS", "60")),
            relay_enabled=enabled,
            relay_host=os.getenv("SMTP_RELAY_HOST", "smtp.hostinger.com"),
            relay_port=int(os.getenv("SMTP_RELAY_PORT", "465")),
            relay_username=os.getenv("SMTP_RELAY_USERNAME", "").strip(),
            relay_password=os.getenv("SMTP_RELAY_PASSWORD", ""),
            relay_security=os.getenv("SMTP_RELAY_SECURITY", "ssl").strip().casefold(),
            relay_timeout_seconds=float(os.getenv("SMTP_RELAY_TIMEOUT_SECONDS", "20")),
        )
        if settings.relay_enabled:
            if not settings.relay_username or not settings.relay_password:
                raise ValueError(
                    "SMTP_RELAY_ENABLED requires SMTP_RELAY_USERNAME and SMTP_RELAY_PASSWORD"
                )
            if settings.relay_security not in {"ssl", "starttls"}:
                raise ValueError("SMTP_RELAY_SECURITY must be 'ssl' or 'starttls'")
            if not 1 <= settings.relay_port <= 65535:
                raise ValueError("SMTP_RELAY_PORT must be between 1 and 65535")
            if settings.relay_timeout_seconds <= 0:
                raise ValueError("SMTP_RELAY_TIMEOUT_SECONDS must be positive")
        return settings
