import json
import tempfile
import unittest
from pathlib import Path

from services.knowledge_graph_service import format_knowledge_graph_details, load_knowledge_graph_model


class KnowledgeGraphServiceTests(unittest.TestCase):
    def test_load_knowledge_graph_model_indexes_hierarchy_elements_edges_and_clicks(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            (base / "ui_semantic_graph.json").write_text(
                json.dumps(
                    {
                        "graph_id": "graph",
                        "name": "Graph",
                        "notes": "notes",
                        "nodes": [
                            {"node_id": "root", "label": "Root", "kind": "view", "parent_node_id": None},
                            {"node_id": "popup", "label": "Popup", "kind": "popup", "parent_node_id": "root"},
                        ],
                        "edges": [
                            {
                                "from_node_id": "popup",
                                "to_node_id": "root",
                                "trigger": "closed",
                                "action_name": "resume",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            (base / "game_elements_manifest.json").write_text(
                json.dumps(
                    {
                        "game_elements": [
                            {
                                "id": 4,
                                "name": "close",
                                "metadata_blocks": {
                                    "auto_click_element_metadata": [{"ui_node_id": "popup"}]
                                },
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            (base / "learning_sessions.json").write_text(
                json.dumps(
                    {
                        "learning_sessions": [
                            {
                                "macro_id": 9,
                                "name": "session",
                                "click_sequence": [{"ui_node_id": "popup", "game_element_id": 4}],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            (base / "pattern_suggestions.json").write_text(
                json.dumps({"pattern_suggestions": []}),
                encoding="utf-8",
            )

            model = load_knowledge_graph_model(base)

            self.assertEqual(model["children_by_parent"]["__root__"][0]["node_id"], "root")
            self.assertEqual(model["children_by_parent"]["root"][0]["node_id"], "popup")
            self.assertEqual(model["elements_by_node"]["popup"][0]["id"], 4)
            self.assertEqual(model["edges_by_source"]["popup"][0]["trigger"], "closed")
            self.assertEqual(model["clicks_by_node"]["popup"][0]["macro_id"], 9)

    def test_format_node_details_includes_link_counts(self):
        model = {
            "elements_by_node": {"node": [{"id": 1}]},
            "clicks_by_node": {"node": [{"macro_id": 2}]},
        }
        details = format_knowledge_graph_details(
            "node",
            {"node_id": "node", "label": "Node", "kind": "view", "tags": ["shared"]},
            model,
        )

        self.assertIn("Elementi collegati: 1", details)
        self.assertIn("Click learning collegati: 1", details)


if __name__ == "__main__":
    unittest.main()
