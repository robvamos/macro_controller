import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from doomsday.ocr.engine import OcrResult, OcrWord
from services.hero_learning_analysis_service import analyze_hero_learning_session


class _FakeEngine:
    def recognize(self, image, *, language="ita+eng", page_segmentation_mode=11):
        return OcrResult(
            text="Info abilità Eroe Battaglia Anteprima miglioramento",
            words=(OcrWord("Info", 90.0, 0, 0, 10, 10),),
            mean_confidence=90.0,
            language=language,
            page_segmentation_mode=page_segmentation_mode,
        )


class HeroLearningAnalysisServiceTests(unittest.TestCase):
    def test_analysis_labels_screen_but_not_click_transition(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir) / "session"
            base.mkdir()
            frame_path = base / "frame.png"
            Image.new("RGB", (320, 180), "green").save(frame_path)
            (base / "session.json").write_text(
                json.dumps(
                    {
                        "session_name": "Sistema - Hero inspection - 20260714_173207",
                        "declared_workflow_id": "hero-inspection-v1",
                        "status": "completed",
                    }
                ),
                encoding="utf-8",
            )
            (base / "events.jsonl").write_text(
                json.dumps({"sequence_index": 1, "game_element_id": 5}) + "\n",
                encoding="utf-8",
            )
            (base / "frames.jsonl").write_text(
                json.dumps(
                    {
                        "sequence_index": 1,
                        "event_time_ms": 100,
                        "path": str(frame_path),
                        "sha256": "abc",
                        "quality": {"valid": True},
                        "normalized_click": {"x": 0.5, "y": 0.5},
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            result = analyze_hero_learning_session(
                base,
                output_root=Path(temp_dir) / "output",
                engine=_FakeEngine(),
            )

            observation = result["payload"]["observations"][0]
            self.assertEqual(observation["screen"]["node_id"], "hero_skills_detail_view")
            self.assertEqual(observation["transition_binding_status"], "observed_unlabeled")
            self.assertFalse(observation["automation_allowed"])
            self.assertTrue(Path(result["path"]).exists())


if __name__ == "__main__":
    unittest.main()
