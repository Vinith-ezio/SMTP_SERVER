
"""Send a sample camera-dirty alert through the local SMTP server."""

import logging
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env", override=True)

# Allow imports from the project root.
sys.path.insert(0, str(PROJECT_ROOT))

from ezio_camera_alerts import CameraAlert, CameraAlertMonitor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("camera-monitor")


def get_recipients() -> list[str]:
    """Read alert recipients from the current .env configuration."""
    recipients = [
        item.strip()
        for item in os.getenv("EZIO_ALERT_RECIPIENTS", "").split(",")
        if item.strip()
    ]

    if not recipients:
        raise SystemExit(
            "No recipients configured. Set EZIO_ALERT_RECIPIENTS "
            "in the project .env file."
        )

    return recipients


def main() -> None:
    # Read the current configuration.
    recipients = get_recipients()

    cooldown_seconds = float(
        os.getenv("EZIO_ALERT_COOLDOWN_SECONDS", "900")
    )

    # Create the monitor using the configured cooldown.
    monitor = CameraAlertMonitor(
        cooldown_seconds=cooldown_seconds
    )

    # Display the configuration being used.
    # Do not print SMTP passwords or other secrets.
    logger.info("Loaded alert recipients: %s", recipients)
    logger.info("Alert cooldown: %s seconds", cooldown_seconds)

    # Example camera alert.
    alert = CameraAlert(
        camera_id="CAM-014",
        camera_name="Packaging Line Camera 2",
        location="Factory A / Packaging Line 2",
        confidence=0.97,
        severity="WARNING",
        details=(
            "Image clarity dropped below the configured threshold."
        ),
    )

    # Demonstration only. Production inference code should pass
    # the actual camera status and alert details.
    result = monitor.process(
        alert.camera_id,
        is_dirty=True,
        recipients=recipients,
        alert=alert,
    )

    logger.info(
        "Camera alert result=%s (cooldown=%ss)",
        result,
        monitor.cooldown_seconds,
    )


if __name__ == "__main__":
    main()
