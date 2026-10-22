"""EZIO camera alert package."""
from .mailer import CameraAlert, build_camera_dirty_message, send_camera_dirty_alert
from .monitor import CameraAlertMonitor, send_camera_recovery_alert

__all__ = [
    "CameraAlert",
    "CameraAlertMonitor",
    "build_camera_dirty_message",
    "send_camera_dirty_alert",
    "send_camera_recovery_alert",
]
