import json
import tempfile
import unittest
from pathlib import Path

from services.learning_network_correlation_service import (
    append_learning_network_marker,
    build_network_correlation_window,
    capture_network_cursor,
    discover_active_network_observation,
    start_or_attach_learning_network_observation,
    summarize_learning_network_correlations,
)


class LearningNetworkCorrelationServiceTests(unittest.TestCase):
    def test_discovers_compatible_active_observer(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            session = root / "20260723_220000"
            session.mkdir(parents=True)
            (root / "active.pid").write_text("456", encoding="ascii")
            events = session / "events.jsonl"
            events.write_text('{"event_type":"session_start"}\n', encoding="utf-8")
            (session / "session.json").write_text(
                json.dumps({"target_pid": 123, "events_path": str(events)}),
                encoding="utf-8",
            )

            binding = discover_active_network_observation(
                target_pid=123,
                root=root,
                pid_exists=lambda pid: pid == 456,
            )

            self.assertIsNotNone(binding)
            self.assertEqual(binding["network_session_id"], "20260723_220000")
            self.assertEqual(binding["proxy_pid"], 456)

    def test_cursor_window_and_marker_share_event_indices(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            events = root / "events.jsonl"
            annotations = root / "annotations.jsonl"
            events.write_text('{"n":1}\n{"n":2}\n', encoding="utf-8")
            binding = {
                "status": "active",
                "network_session_id": "session",
                "events_path": str(events),
                "annotations_path": str(annotations),
            }

            before = capture_network_cursor(binding)
            append_learning_network_marker(
                binding=binding,
                learning_session_name="learning",
                sequence_index=3,
                event_time_ms=1500,
                ui_node_id="research_center",
                network_cursor=before,
            )
            with events.open("a", encoding="utf-8") as handle:
                handle.write('{"n":3}\n')
                handle.write('{"n":4}\n')
            after = capture_network_cursor(binding)
            window = build_network_correlation_window(
                binding=binding,
                before=before,
                after=after,
            )

            self.assertEqual(window["event_index_start"], 3)
            self.assertEqual(window["event_index_end"], 4)
            self.assertEqual(window["event_count"], 2)
            marker = json.loads(annotations.read_text(encoding="utf-8"))
            self.assertEqual(marker["sequence_index"], 3)
            self.assertEqual(marker["event_count_before"], 2)
            self.assertNotIn("payload", marker)

    def test_disabled_observation_is_explicitly_partial(self):
        binding = start_or_attach_learning_network_observation(
            target_pid=123,
            duration_seconds=60,
            enabled=False,
        )

        self.assertEqual(binding["status"], "unavailable")
        self.assertEqual(binding["reason"], "disabled_by_operator")

    def test_summary_builds_stable_per_click_application_shape(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            network_events = root / "network.jsonl"
            network_events.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "event_type": "tcp_message",
                                "transport": "tcp",
                                "server_port": 16731,
                                "observed_at": "2026-07-23T20:00:00.000+00:00",
                                "request_bytes": 11,
                                "response_bytes": 0,
                                "metadata": {"direction": "client_to_server"},
                            }
                        ),
                        json.dumps(
                            {
                                "event_type": "tcp_message",
                                "transport": "tcp",
                                "server_port": 16731,
                                "observed_at": "2026-07-23T20:00:00.284+00:00",
                                "request_bytes": 0,
                                "response_bytes": 5923,
                                "metadata": {"direction": "server_to_client"},
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (root / "session.json").write_text(
                json.dumps(
                    {
                        "session_name": "Research learning",
                        "scenario": "general",
                        "network_observation": {
                            "network_session_id": "network-session",
                            "events_path": str(network_events),
                        },
                    }
                ),
                encoding="utf-8",
            )
            (root / "events.jsonl").write_text(
                json.dumps(
                    {
                        "sequence_index": 1,
                        "time": 1000,
                        "ui_node_id": "research_center",
                        "network_correlation": {
                            "available": True,
                            "event_index_start": 1,
                            "event_index_end": 2,
                        },
                        "learning_frames": [],
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            summary = summarize_learning_network_correlations(root)
            correlation = summary["correlations"][0]

            self.assertEqual(correlation["application_message_count"], 2)
            self.assertEqual(correlation["first_response_latency_ms"], 284)
            self.assertEqual(correlation["application_shape"][0]["bytes"], 11)
            self.assertEqual(correlation["application_shape"][1]["bytes"], 5923)
            self.assertEqual(len(correlation["shape_fingerprint"]), 16)


if __name__ == "__main__":
    unittest.main()
