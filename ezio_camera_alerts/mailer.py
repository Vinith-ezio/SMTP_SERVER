
"""Build and send camera cleanliness alerts through the local EZIO SMTP server."""

from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import make_msgid, parseaddr
from html import escape
from pathlib import Path
import smtplib
from typing import Optional, Sequence
from urllib.parse import urlparse

from .config import MailerSettings


TEMPLATE_PATH = (
    Path(__file__).resolve().parent
    / "templates"
    / "camera_dirty_alert.html"
)


@dataclass(frozen=True)
class CameraAlert:
    camera_id: str
    camera_name: str
    location: str
    confidence: Optional[float] = None  # Accepts 0..1 or 0..100
    severity: str = "WARNING"
    details: str = (
        "The model detected a dirty or obstructed camera view."
    )
    detected_at: Optional[datetime] = None
    dashboard_url: Optional[str] = None
    snapshot_url: Optional[str] = None


def _validate_email(address: str, field: str) -> str:
    if not isinstance(address, str):
        raise ValueError(f"{field} must be a string")

    address = address.strip()
    _, parsed = parseaddr(address)

    if (
        not parsed
        or parsed != address
        or "@" not in parsed
        or any(c in address for c in "\r\n")
    ):
        raise ValueError(f"{field} must be a valid email address")

    return address


def _safe_http_url(
    value: Optional[str], field: str
) -> Optional[str]:
    if value is None:
        return None

    if not isinstance(value, str):
        raise ValueError(f"{field} must be a valid HTTP(S) URL")

    value = value.strip()
    parsed = urlparse(value)

    if (
        parsed.scheme not in ("http", "https")
        or not parsed.netloc
        or any(c in value for c in "\r\n")
    ):
        raise ValueError(
            f"{field} must be an absolute HTTP(S) URL"
        )

    return value


def _safe_text(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"{field} must be a non-empty string"
        )

    if "\r" in value or "\n" in value:
        raise ValueError(
            f"{field} must not contain line breaks"
        )

    return value.strip()


def _load_html_template() -> str:
    """Load the HTML template relative to this module."""
    if not TEMPLATE_PATH.is_file():
        raise FileNotFoundError(
            "Camera alert HTML template not found: "
            f"{TEMPLATE_PATH}"
        )

    return TEMPLATE_PATH.read_text(encoding="utf-8")


def build_camera_dirty_message(
    alert: CameraAlert,
    recipients: Sequence[str],
    sender_email: str,
) -> EmailMessage:
    """Build a multipart plain-text and HTML message without sending it."""

    camera_id = _safe_text(alert.camera_id, "camera_id")
    camera_name = _safe_text(alert.camera_name, "camera_name")
    location = _safe_text(alert.location, "location")
    severity = _safe_text(alert.severity, "severity").upper()

    if not isinstance(alert.details, str):
        raise ValueError("details must be a string")

    details = alert.details.strip() or "No additional details provided."

    if alert.confidence is not None:
        if (
            not isinstance(alert.confidence, (int, float))
            or isinstance(alert.confidence, bool)
            or not 0 <= alert.confidence <= 100
        ):
            raise ValueError(
                "confidence must be between 0 and 100"
            )

    if not recipients:
        raise ValueError("At least one recipient is required")

    recipient_list = [
        _validate_email(r, "recipient")
        for r in recipients
    ]
    sender = _validate_email(sender_email, "sender")

    dashboard_url = _safe_http_url(
        alert.dashboard_url, "dashboard_url"
    )
    snapshot_url = _safe_http_url(
        alert.snapshot_url, "snapshot_url"
    )

    detected_at = alert.detected_at or datetime.now(timezone.utc)

    if detected_at.tzinfo is None:
        detected_at = detected_at.replace(tzinfo=timezone.utc)

    timestamp = detected_at.isoformat(
        sep=" ", timespec="seconds"
    )

    confidence_text = "Not provided"

    if alert.confidence is not None:
        pct = (
            alert.confidence * 100
            if alert.confidence <= 1
            else alert.confidence
        )
        confidence_text = f"{pct:.1f}%"

    subject = (
        f"[Camera {severity}] Camera cleanliness alert: "
        f"{camera_name} ({camera_id})"
    )

    # Plain-text alternative
    plain = [
        "AUTOMATED CAMERA CLEANLINESS ALERT",
        "",
        "The vision monitoring system detected that a camera "
        "may be dirty or obstructed.",
        "",
        f"Camera ID: {camera_id}",
        f"Camera name: {camera_name}",
        f"Location: {location}",
        f"Severity: {severity}",
        f"Detected at: {timestamp}",
        f"Model confidence: {confidence_text}",
        "",
        "Detection details:",
        details,
    ]

    if dashboard_url:
        plain += ["", f"Dashboard: {dashboard_url}"]

    if snapshot_url:
        plain += [f"Snapshot: {snapshot_url}"]

    plain += [
        "",
        "Recommended action:",
        "Inspect the camera lens and protective cover. "
        "Clean if required, then verify the camera feed.",
        "",
        "This is an automated notification. Please do not reply.",
    ]

    # Build escaped table rows for the HTML template
    rows_data = [
        ("Camera ID", camera_id),
        ("Camera name", camera_name),
        ("Location", location),
        ("Severity", severity),
        ("Detected at", timestamp),
        ("Model confidence", confidence_text),
    ]

    rows = "".join(
        "<tr>"
        f"<th align='left' "
        f"style='padding:8px 14px 8px 0;color:#475569'>"
        f"{escape(key)}</th>"
        f"<td style='padding:8px 0'>{escape(value)}</td>"
        "</tr>"
        for key, value in rows_data
    )

    # Build optional links
    links = ""

    if dashboard_url:
        links += (
            "<p><a href='"
            f"{escape(dashboard_url, quote=True)}"
            "'>Open monitoring dashboard</a></p>"
        )

    if snapshot_url:
        links += (
            "<p><a href='"
            f"{escape(snapshot_url, quote=True)}"
            "'>View camera snapshot</a></p>"
        )

    # Load the external HTML file and replace its placeholders.
    # The template can be edited without changing this Python file.

    html_template = _load_html_template()

    replacements = {
        # Support the existing HTML template's placeholders
        "{{ severity }}": escape(severity),
        "{{ camera_id }}": escape(camera_id),
        "{{ camera_name }}": escape(camera_name),
        "{{ location }}": escape(location),
        "{{ detected_at }}": escape(timestamp),
        "{{ confidence }}": escape(confidence_text),
        "{{ details }}": (
            escape(details)
            .replace("\r\n", "\n")
            .replace("\n", "<br>")
        ),

        # Also support the alternative placeholder names
        "{{SEVERITY}}": escape(severity),
        "{{CAMERA_ROWS}}": rows,
        "{{DETECTION_DETAILS}}": (
            escape(details)
            .replace("\r\n", "\n")
            .replace("\n", "<br>")
        ),
        "{{LINKS}}": links,
    }

    html_body = html_template

    for placeholder, value in replacements.items():
        html_body = html_body.replace(placeholder, value)

    # Catch any unresolved template placeholders during development.
    unresolved = [
        placeholder
        for placeholder in (
            "{{ severity }}",
            "{{ camera_id }}",
            "{{ camera_name }}",
            "{{ location }}",
            "{{ detected_at }}",
            "{{ confidence }}",
            "{{ details }}",
            "{{SEVERITY}}",
            "{{CAMERA_ROWS}}",
            "{{DETECTION_DETAILS}}",
            "{{LINKS}}",
        )
        if placeholder in html_body
    ]

    if unresolved:
        raise ValueError(
            "Unresolved HTML template placeholders: "
            + ", ".join(unresolved)
        )


    message = EmailMessage()
    message["From"] = sender
    message["To"] = ", ".join(recipient_list)
    message["Subject"] = subject
    message["Message-ID"] = make_msgid(
        domain="eziosolutions.ai"
    )

    message.set_content("\n".join(plain))
    message.add_alternative(html_body, subtype="html")

    return message


def send_camera_dirty_alert(
    alert: CameraAlert,
    recipients: Sequence[str],
) -> str:
    """Submit through local SMTP and return the message's Message-ID.

    A successful return indicates SMTP submission, not guaranteed inbox
    delivery.
    """
    settings = MailerSettings.from_env()

    message = build_camera_dirty_message(
        alert,
        recipients,
        settings.sender_email,
    )

    with smtplib.SMTP(
        settings.smtp_host,
        settings.smtp_port,
        timeout=settings.timeout_seconds,
    ) as client:
        refused = client.send_message(
            message,
            from_addr=settings.sender_email,
            to_addrs=list(recipients),
        )

        if refused:
            raise smtplib.SMTPRecipientsRefused(refused)

    return str(message["Message-ID"])
