import unittest
from io import BytesIO

from PIL import Image

from doomsday.runtime.bluestacks_capture import (
    AdbSessionStatus,
    BlueStacksAdbCaptureProvider,
    resolve_unique_adb_endpoint,
)


def _png_bytes(color=(20, 40, 60)):
    buffer = BytesIO()
    image = Image.new("RGB", (100, 60), color=color)
    for x in range(30, 70):
        for y in range(20, 40):
            image.putpixel((x, y), (180, 160, 80))
    image.save(buffer, format="PNG")
    return buffer.getvalue()


class _FakeSession:
    def __init__(self, status, payload=None):
        self._status = status
        self.payload = payload or _png_bytes()
        self.commands = []

    def status(self):
        return self._status

    def exec_out(self, argv, *, timeout, max_bytes):
        self.commands.append((tuple(argv), timeout, max_bytes))
        return self.payload


class BlueStacksCaptureTests(unittest.TestCase):
    def _provider(self, session):
        return BlueStacksAdbCaptureProvider(
            session,
            expected_instance="Pie64_2",
            expected_endpoint="127.0.0.1:5575",
            expected_serial="emulator-5575",
        )

    def test_constructor_and_health_never_execute_adb_command(self):
        session = _FakeSession(
            AdbSessionStatus(True, "Pie64_2", "127.0.0.1:5575", "emulator-5575", True)
        )
        provider = self._provider(session)

        health = provider.health()

        self.assertTrue(health.available)
        self.assertEqual(session.commands, [])

    def test_capture_allows_only_screencap_on_verified_existing_session(self):
        session = _FakeSession(
            AdbSessionStatus(True, "Pie64_2", "127.0.0.1:5575", "emulator-5575", True)
        )

        frame = self._provider(session).capture_frame()

        self.assertEqual(frame.size, (100, 60))
        self.assertEqual(session.commands[0][0], ("screencap", "-p"))

    def test_mismatched_identity_fails_closed_without_exec(self):
        session = _FakeSession(
            AdbSessionStatus(True, "Nougat64", "127.0.0.1:5555", "other", True)
        )

        with self.assertRaises(RuntimeError):
            self._provider(session).capture_frame()

        self.assertEqual(session.commands, [])

    def test_corrupt_png_is_rejected_without_retry(self):
        session = _FakeSession(
            AdbSessionStatus(True, "Pie64_2", "127.0.0.1:5575", "emulator-5575", True),
            payload=b"not-a-png",
        )

        with self.assertRaises(ValueError):
            self._provider(session).capture_frame()

        self.assertEqual(len(session.commands), 1)

    def test_static_port_collision_is_rejected(self):
        record = {
            "instances": [
                {"name": "Nougat64", "adb_port": 5555},
                {"name": "Pie64", "adb_port": 5555},
            ]
        }

        with self.assertRaises(ValueError):
            resolve_unique_adb_endpoint(record, "Nougat64")


if __name__ == "__main__":
    unittest.main()
