import json
import tempfile
import unittest
from pathlib import Path

from services.annotated_network_analysis_service import analyze_annotated_network_session


class AnnotatedNetworkAnalysisServiceTests(unittest.TestCase):
    def test_separates_heartbeat_and_builds_semantic_exchange_candidate(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "session.json").write_text(
                json.dumps(
                    {
                        "capture_level": "metadata-only",
                        "tls_passthrough": True,
                        "payloads_persisted": False,
                    }
                ),
                encoding="utf-8",
            )
            records = [
                _message("client_to_server", 4, "2026-07-23T20:00:00.000+00:00"),
                _message("server_to_client", 4, "2026-07-23T20:00:00.100+00:00"),
                _message("client_to_server", 4, "2026-07-23T20:00:01.000+00:00"),
                _message("server_to_client", 4, "2026-07-23T20:00:01.100+00:00"),
                _message("client_to_server", 4, "2026-07-23T20:00:02.000+00:00"),
                _message("server_to_client", 4, "2026-07-23T20:00:02.100+00:00"),
                _message("client_to_server", 11, "2026-07-23T20:00:03.000+00:00"),
                _message("server_to_client", 5923, "2026-07-23T20:00:03.284+00:00"),
            ]
            (root / "events.jsonl").write_text(
                "\n".join(json.dumps(record) for record in records) + "\n",
                encoding="utf-8",
            )
            (root / "annotations.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps({"label": "OPEN REPORT", "event_count": 6}),
                        json.dumps({"label": "REPORT OPEN", "event_count": 8}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            result = analyze_annotated_network_session(root)
            window = result["semantic_windows"][0]

            self.assertEqual(window["application_message_count"], 2)
            self.assertEqual(window["candidate_exchanges"][0]["request_bytes"], 11)
            self.assertEqual(window["candidate_exchanges"][0]["response_bytes"], 5923)
            self.assertEqual(window["candidate_exchanges"][0]["latency_ms"], 284)
            self.assertFalse(result["capture_policy"]["replay_allowed"])
            self.assertEqual(len(result["recurring_background_shapes"]), 2)


def _message(direction, size, observed_at):
    return {
        "event_type": "tcp_message",
        "transport": "tcp",
        "server_port": 16731,
        "observed_at": observed_at,
        "request_bytes": size if direction == "client_to_server" else 0,
        "response_bytes": size if direction == "server_to_client" else 0,
        "metadata": {"direction": direction},
    }


if __name__ == "__main__":
    unittest.main()
