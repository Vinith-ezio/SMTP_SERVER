import unittest
from ezio_camera_alerts.mailer import CameraAlert, build_camera_dirty_message


class CameraMailerTests(unittest.TestCase):
    def setUp(self):
        self.alert = CameraAlert(
            camera_id="CAM-014",
            camera_name="Packaging Line Camera 2",
            location="Factory A",
            confidence=0.97,
            details="Lens clarity dropped.",
        )

    def test_builds_plain_html_and_message_id(self):
        message = build_camera_dirty_message(
            self.alert, ["maintenance@example.com"], "info@eziosolutions.ai"
        )
        self.assertIn("Camera cleanliness alert", message["Subject"])
        self.assertEqual(message["From"], "info@eziosolutions.ai")
        self.assertTrue(message["Message-ID"])
        self.assertTrue(message.is_multipart())
        self.assertIn("CAM-014", message.get_body(preferencelist=("plain",)).get_content())
        self.assertIn("CAM-014", message.get_body(preferencelist=("html",)).get_content())

    def test_rejects_empty_recipients(self):
        with self.assertRaises(ValueError):
            build_camera_dirty_message(self.alert, [], "info@eziosolutions.ai")

    def test_rejects_line_break_in_camera_name(self):
        bad = CameraAlert("CAM-1", "Camera\r\nBcc:bad@example.com", "Factory A")
        with self.assertRaises(ValueError):
            build_camera_dirty_message(bad, ["maintenance@example.com"], "info@eziosolutions.ai")

    def test_rejects_invalid_url_scheme(self):
        bad = CameraAlert("CAM-1", "Camera 1", "Factory A", dashboard_url="javascript:alert(1)")
        with self.assertRaises(ValueError):
            build_camera_dirty_message(bad, ["maintenance@example.com"], "info@eziosolutions.ai")


if __name__ == "__main__":
    unittest.main()
