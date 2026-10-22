import unittest
from ezio_camera_alerts import CameraAlert, CameraAlertMonitor


class FakeClock:
    def __init__(self):
        self.value = 100.0

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


class CameraAlertMonitorTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.dirty_calls = []
        self.recovery_calls = []
        self.monitor = CameraAlertMonitor(
            cooldown_seconds=60,
            dirty_sender=lambda alert, recipients: self.dirty_calls.append((alert.camera_id, list(recipients))),
            recovery_sender=lambda camera_id, alert, recipients: self.recovery_calls.append((camera_id, list(recipients))),
            clock=self.clock,
        )
        self.alert = CameraAlert("CAM-1", "Line Camera", "Factory A")
        self.recipients = ["maintenance@example.com"]

    def test_first_dirty_sends_alert(self):
        result = self.monitor.process("CAM-1", True, self.recipients, self.alert)
        self.assertEqual(result, "alert_sent")
        self.assertEqual(len(self.dirty_calls), 1)

    def test_repeated_dirty_suppressed_until_cooldown_then_reminder(self):
        self.assertEqual(self.monitor.process("CAM-1", True, self.recipients, self.alert), "alert_sent")
        self.assertEqual(self.monitor.process("CAM-1", True, self.recipients, self.alert), "suppressed")
        self.clock.advance(60)
        self.assertEqual(self.monitor.process("CAM-1", True, self.recipients, self.alert), "reminder_sent")
        self.assertEqual(len(self.dirty_calls), 2)

    def test_clean_transition_sends_recovery_once(self):
        self.monitor.process("CAM-1", True, self.recipients, self.alert)
        self.assertEqual(self.monitor.process("CAM-1", False, self.recipients, self.alert), "recovery_sent")
        self.assertEqual(self.monitor.process("CAM-1", False, self.recipients, self.alert), "no_change")
        self.assertEqual(len(self.recovery_calls), 1)

    def test_rejects_mismatched_camera_id(self):
        with self.assertRaises(ValueError):
            self.monitor.process("CAM-2", True, self.recipients, self.alert)


if __name__ == "__main__":
    unittest.main()
