import json
import sqlite3
import tempfile
import unittest
from io import BytesIO
from pathlib import Path

from PIL import Image

from services.learning_session_recovery_service import (
    load_recovered_learning_sessions,
    recover_learning_session,
)


SESSION = "Sistema - Hero inspection - Locale TEST\\User - 20260714_170238"


def _png_bytes(color: str) -> bytes:
    output = BytesIO()
    Image.new("RGB", (12, 10), color).save(output, format="PNG")
    return output.getvalue()


def _metadata_block(sequence_index, element_id, previous_element_id, *, source="macro_recording_click_capture"):
    auto = {
        "source": source,
        "graph_id": "graph",
        "macro_name": SESSION,
        "event_time_ms": sequence_index * 100,
        "button": "left",
        "click_position": {"x": sequence_index * 10, "y": sequence_index * 20},
        "normalized_position": {"x": sequence_index / 10, "y": sequence_index / 20},
        "sequence_index": sequence_index,
        "previous_element_id": previous_element_id,
    }
    note = {
        "session_name": SESSION,
        "sequence_index": sequence_index,
        "previous_element_id": previous_element_id,
        "view_node_id": "unknown",
        "semantic_node_id": "unknown",
        "screen_zone": "top_left",
    }
    return (
        "AUTO_CLICK_ELEMENT_METADATA:" + json.dumps(auto) + "\n"
        "GENERAL_CLICK_SEMANTIC_NOTE:" + json.dumps(note)
    )


class LearningSessionRecoveryServiceTests(unittest.TestCase):
    def test_recovers_reused_element_events_without_mutating_database(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            db_path = root / "macro.db"
            connection = sqlite3.connect(db_path)
            connection.execute(
                "CREATE TABLE GameElements (id INTEGER PRIMARY KEY, nome TEXT, descrizione TEXT, "
                "immagine BLOB, formato_immagine TEXT)"
            )
            connection.execute(
                "INSERT INTO GameElements VALUES (1, ?, ?, ?, 'PNG')",
                ("first", _metadata_block(1, 1, None), _png_bytes("red")),
            )
            repeated_description = (
                _metadata_block(2, 63, 1, source="macro_recording_semantic_click_action")
                + "\n"
                + _metadata_block(3, 63, 63, source="macro_recording_semantic_click_action")
            )
            connection.execute(
                "INSERT INTO GameElements VALUES (63, ?, ?, ?, 'PNG')",
                ("shared", repeated_description, _png_bytes("blue")),
            )
            connection.commit()
            connection.close()
            before = db_path.read_bytes()

            result = recover_learning_session(
                SESSION,
                db_path=db_path,
                output_root=root / "recovered",
                declared_workflow_id="hero-inspection-v1",
            )

            self.assertEqual(result["click_count"], 3)
            self.assertEqual(db_path.read_bytes(), before)
            payload = result["payload"]
            self.assertEqual([item["game_element_id"] for item in payload["click_sequence"]], [1, 63, 63])
            self.assertEqual(
                payload["click_sequence"][1]["evidence"]["semantic_gap"],
                "shared_spatial_placeholder",
            )
            self.assertFalse(payload["click_sequence"][0]["automation_allowed"])
            self.assertEqual(len(load_recovered_learning_sessions(root / "recovered")), 1)

    def test_rejects_non_contiguous_sequence(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            db_path = root / "macro.db"
            connection = sqlite3.connect(db_path)
            connection.execute(
                "CREATE TABLE GameElements (id INTEGER PRIMARY KEY, nome TEXT, descrizione TEXT, "
                "immagine BLOB, formato_immagine TEXT)"
            )
            connection.execute(
                "INSERT INTO GameElements VALUES (2, ?, ?, ?, 'PNG')",
                ("second", _metadata_block(2, 2, None), _png_bytes("red")),
            )
            connection.commit()
            connection.close()

            with self.assertRaisesRegex(ValueError, "not contiguous"):
                recover_learning_session(SESSION, db_path=db_path, output_root=root / "recovered")


if __name__ == "__main__":
    unittest.main()
