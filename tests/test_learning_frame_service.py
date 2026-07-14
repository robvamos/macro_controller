import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from doomsday.vision.desktop_capture import assess_frame_quality
from services.learning_frame_service import capture_learning_frame


class LearningFrameServiceTests(unittest.TestCase):
    def test_quality_rejects_black_and_large_black_holes(self):
        black = Image.new("RGB", (200, 100), "black")
        partial = Image.new("RGB", (200, 100), "black")
        for x in range(120, 200):
            for y in range(100):
                partial.putpixel((x, y), (80, 120, 60))

        self.assertFalse(assess_frame_quality(black).valid)
        self.assertFalse(assess_frame_quality(partial).valid)

    def test_capture_writes_png_and_jsonl_lineage(self):
        image = Image.new("RGB", (320, 180), (80, 120, 60))
        for x in range(100, 200):
            for y in range(50, 100):
                image.putpixel((x, y), (220, 200, 80))
        with tempfile.TemporaryDirectory() as tempdir, patch(
            "services.learning_frame_service.capture_screen_region", return_value=image
        ):
            result = capture_learning_frame(
                session_name="Hero path test",
                sequence_index=1,
                window_rect=(10, 20, 330, 200),
                event_time_ms=1234,
                view_node_id="hero_section",
                semantic_node_id="hero_selector",
                normalized_x=0.9,
                normalized_y=0.8,
                phase="click_time",
                root=tempdir,
            )

            self.assertTrue(Path(result["path"]).exists())
            self.assertTrue(result["quality"]["valid"])
            self.assertEqual(result["phase"], "click_time")
            lines = list(Path(tempdir).rglob("frames.jsonl"))[0].read_text(encoding="utf-8").splitlines()
            self.assertEqual(json.loads(lines[0])["semantic_node_id"], "hero_selector")


if __name__ == "__main__":
    unittest.main()
