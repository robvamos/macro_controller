import json
from pathlib import Path
import tempfile
import unittest

from services.task_call_map_service import (
    format_task_call_details,
    load_task_call_map,
)


class TaskCallMapServiceTests(unittest.TestCase):
    def test_loads_domains_tasks_ui_links_and_safe_call_shapes(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            (base / "network_observations").mkdir()
            (base / "learning_domain_registry.json").write_text(
                json.dumps(
                    {
                        "domains": [
                            {
                                "domain_id": "general",
                                "label": "Generale",
                                "status": "active",
                            },
                            {
                                "domain_id": "battle_reports",
                                "label": "Rapporti",
                                "status": "observed",
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            (base / "ui_semantic_graph.json").write_text(
                json.dumps(
                    {
                        "nodes": [
                            {
                                "node_id": "communications_button",
                                "label": "Comunicazioni",
                                "kind": "control",
                            },
                            {
                                "node_id": "communications_center_view",
                                "label": "Centro Comunicazioni",
                                "kind": "view",
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            observation = {
                "network_session_id": "session-a",
                "capture_policy": {"replay_allowed": False},
                "semantic_windows": [
                    {
                        "declared_semantic_label": "APRO MESSAGGI",
                        "marker_observed_at": "2026-07-23T20:00:00Z",
                        "semantic_status": "candidate_requires_repetition_and_visual_validation",
                        "shape_fingerprint": "fingerprint-a",
                        "application_message_count": 2,
                        "channel_summary": [
                            {"transport": "tcp", "server_port": 16731}
                        ],
                        "candidate_exchanges": [
                            {
                                "transport": "tcp",
                                "server_port": 16731,
                                "request_bytes": 11,
                                "response_bytes": 5923,
                                "latency_ms": 284,
                                "status": "shape_candidate_not_replayable",
                            }
                        ],
                        "candidate_server_pushes": [],
                        "application_shape": [],
                    }
                ],
            }
            (base / "network_observations" / "session-a.json").write_text(
                json.dumps(observation),
                encoding="utf-8",
            )

            model = load_task_call_map(base)

            self.assertEqual(model["observation_count"], 1)
            self.assertEqual(model["task_count"], 1)
            self.assertEqual(model["call_count"], 1)
            self.assertFalse(model["policy"]["replay_allowed"])
            task = model["tasks"][0]
            self.assertEqual(task["domain_id"], "battle_reports")
            self.assertEqual(task["operation_class"], "server-backed")
            self.assertEqual(task["maturity"], "observed")
            self.assertIn("communications_button", task["visual_node_ids"])
            self.assertFalse(task["replay_allowed"])
            self.assertEqual(task["calls"][0]["call_kind"], "exchange")

    def test_repeated_fingerprint_in_two_sessions_is_cross_session_candidate(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            observations = base / "network_observations"
            observations.mkdir()
            window = {
                "declared_semantic_label": "APRO REPORT",
                "shape_fingerprint": "same-shape",
                "application_message_count": 1,
                "candidate_exchanges": [],
                "candidate_server_pushes": [],
                "application_shape": [
                    {
                        "transport": "tcp",
                        "server_port": 16731,
                        "direction": "client_to_server",
                        "bytes": 11,
                        "count": 1,
                    }
                ],
            }
            for session_id in ("a", "b"):
                (observations / f"{session_id}.json").write_text(
                    json.dumps(
                        {
                            "network_session_id": session_id,
                            "semantic_windows": [window],
                        }
                    ),
                    encoding="utf-8",
                )

            model = load_task_call_map(base)

            self.assertTrue(
                all(
                    task["maturity"] == "cross_session_candidate"
                    for task in model["tasks"]
                )
            )

    def test_detail_text_never_presents_call_as_replayable(self):
        model = {
            "observation_count": 1,
            "task_count": 1,
            "call_count": 1,
        }
        detail = format_task_call_details(
            "call",
            {
                "label": "Scambio candidato",
                "call_kind": "exchange",
                "transport": "tcp",
                "server_port": 16731,
                "request_bytes": 11,
                "response_bytes": 5923,
                "latency_ms": 284,
                "status": "shape_candidate_not_replayable",
            },
            model,
        )
        self.assertIn("non una chiamata riproducibile", detail)


if __name__ == "__main__":
    unittest.main()
