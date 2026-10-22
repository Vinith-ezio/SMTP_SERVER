"""Per-process camera alert deduplication and recovery notifications.

This controller is intentionally separate from the SMTP transport. It keeps a
small in-memory state per camera; state resets when the process restarts.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import make_msgid
import smtplib
import time
from typing import Callable, Dict, Optional, Sequence

from .config import MailerSettings
from .mailer import CameraAlert, send_camera_dirty_alert


@dataclass
class _CameraState:
    is_dirty: bool
    last_alert_monotonic: float
    last_detected_at: datetime


class CameraAlertMonitor:
    """Send one alert on clean->dirty, suppress repeats during cooldown, and notify recovery.

    Args:
        cooldown_seconds: Minimum interval between reminders while a camera remains dirty.
            Set to 0 to send a reminder on every dirty observation (not recommended).
        dirty_sender: Injectable sender for tests; defaults to send_camera_dirty_alert.
        recovery_sender: Injectable recovery sender for tests.
        clock: Injectable monotonic clock for deterministic tests.

    `process()` returns one of: ``alert_sent``, ``reminder_sent``, ``suppressed``,
    ``recovery_sent``, or ``no_change``. A state entry is created on the first
    observation, whether clean or dirty.
    """

    def __init__(
        self,
        cooldown_seconds: float = 900,
        dirty_sender: Optional[Callable] = None,
        recovery_sender: Optional[Callable] = None,
        clock: Callable[[], float] = time.monotonic,
    ):
        if cooldown_seconds < 0:
            raise ValueError("cooldown_seconds must be >= 0")
        self.cooldown_seconds = float(cooldown_seconds)
        self._dirty_sender = dirty_sender or send_camera_dirty_alert
        self._recovery_sender = recovery_sender or send_camera_recovery_alert
        self._clock = clock
        self._states: Dict[str, _CameraState] = {}

    def process(
        self,
        camera_id: str,
        is_dirty: bool,
        recipients: Sequence[str],
        alert: Optional[CameraAlert] = None,
    ) -> str:
        camera_id = camera_id.strip() if isinstance(camera_id, str) else ""
        if not camera_id:
            raise ValueError("camera_id must be a non-empty string")
        if not isinstance(is_dirty, bool):
            raise ValueError("is_dirty must be a bool")
        if not recipients:
            raise ValueError("At least one recipient is required")

        now = self._clock()
        current = datetime.now(timezone.utc)
        previous = self._states.get(camera_id)

        if is_dirty:
            if alert is None:
                raise ValueError("alert is required when is_dirty=True")
            if alert.camera_id != camera_id:
                raise ValueError("alert.camera_id must match camera_id")
            if previous is None or not previous.is_dirty:
                # Only update state after sending succeeds, so failures can be retried.
                self._dirty_sender(alert, recipients)
                self._states[camera_id] = _CameraState(True, now, current)
                return "alert_sent"

            if now - previous.last_alert_monotonic < self.cooldown_seconds:
                return "suppressed"
            self._dirty_sender(alert, recipients)
            self._states[camera_id] = _CameraState(True, now, current)
            return "reminder_sent"

        if previous is None:
            self._states[camera_id] = _CameraState(False, now, current)
            return "no_change"
        if not previous.is_dirty:
            return "no_change"

        self._recovery_sender(camera_id, alert, recipients)
        self._states[camera_id] = _CameraState(False, now, current)
        return "recovery_sent"


def send_camera_recovery_alert(
    camera_id: str, alert: Optional[CameraAlert], recipients: Sequence[str]
) -> str:
    """Send a recovery email when a previously dirty camera becomes clean."""
    if not recipients:
        raise ValueError("At least one recipient is required")
    settings = MailerSettings.from_env()
    camera_name = alert.camera_name if alert else camera_id
    location = alert.location if alert else "Not provided"
    message = EmailMessage()
    message["From"] = settings.sender_email
    message["To"] = ", ".join(recipients)
    message["Subject"] = f"[Camera RECOVERED] Camera view restored: {camera_name} ({camera_id})"
    message["Message-ID"] = make_msgid(domain="eziosolutions.ai")
    body = (
        "AUTOMATED CAMERA RECOVERY NOTICE\n\n"
        "The camera monitoring system reports that the camera view is no longer dirty or obstructed.\n\n"
        f"Camera ID: {camera_id}\nCamera name: {camera_name}\nLocation: {location}\n"
        f"Recovered at: {datetime.now(timezone.utc).isoformat(sep=' ', timespec='seconds')}\n\n"
        "Please verify that the live camera feed is clear."
    )
    message.set_content(body)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=settings.timeout_seconds) as client:
        refused = client.send_message(message, from_addr=settings.sender_email, to_addrs=list(recipients))
        if refused:
            raise smtplib.SMTPRecipientsRefused(refused)
    return str(message["Message-ID"])
