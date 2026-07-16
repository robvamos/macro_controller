import json
import unittest

from doomsday.network_observation.schema import (
    MetadataRecord,
    build_http_record,
    normalize_path,
    safe_query_keys,
    summarize_observations,
)


class NetworkObservationSchemaTests(unittest.TestCase):
    def test_path_normalization_removes_likely_identifiers(self):
        self.assertEqual(
            normalize_path(
                "/api/heroes/12345/550e8400-e29b-41d4-a716-446655440000/0123456789abcdef"
            ),
            "/api/heroes/{id}/{uuid}/{hex}",
        )

    def test_query_values_are_never_retained(self):
        url = "https://game.example/hero?id=42&access_token=secret-value&locale=it"
        record = build_http_record(flow_id="flow", method="get", url=url)
        serialized = json.dumps(record.to_dict())

        self.assertEqual(record.query_keys, ("id", "locale", "{sensitive}"))
        self.assertNotIn("secret-value", serialized)
        self.assertNotIn("access_token", serialized)
        self.assertNotIn("42", serialized)

    def test_http_shape_keeps_only_route_and_size_metadata(self):
        record = build_http_record(
            flow_id="flow",
            method="post",
            url="https://api.example/roster/987?locale=it",
            status_code=200,
            request_content_type="application/json; charset=utf-8",
            response_content_type="application/json",
            request_bytes=123,
            response_bytes=456,
        )

        self.assertEqual(record.path_template, "/roster/{id}")
        self.assertEqual(record.request_content_type, "application/json")
        self.assertEqual(record.request_bytes, 123)
        self.assertFalse(hasattr(record, "headers"))
        self.assertFalse(hasattr(record, "body"))

    def test_summary_does_not_assign_semantic_game_meaning(self):
        records = [
            build_http_record(
                flow_id="one",
                method="get",
                url="https://api.example/hero/1",
                status_code=200,
            ),
            build_http_record(
                flow_id="two",
                method="get",
                url="https://api.example/hero/2",
                status_code=404,
            ),
            MetadataRecord(
                event_type="tcp_end",
                transport="tcp",
                server_host="203.0.113.5",
                server_port=16730,
                message_count=3,
            ),
        ]

        summary = summarize_observations(records)

        self.assertEqual(summary.record_count, 3)
        self.assertEqual(summary.transports, {"https": 2, "tcp": 1})
        self.assertEqual(summary.endpoints[0]["path_template"], "/hero/{id}")
        self.assertEqual(summary.endpoints[0]["status_codes"], [200, 404])
        self.assertNotIn("game_action", summary.endpoints[0])

    def test_record_rejects_invalid_port(self):
        with self.assertRaises(ValueError):
            MetadataRecord(event_type="server", transport="tcp", server_port=70000)

    def test_sensitive_parameter_names_are_collapsed(self):
        self.assertEqual(
            safe_query_keys("https://example.test/x?signature=abc&filter=all"),
            ("filter", "{sensitive}"),
        )


if __name__ == "__main__":
    unittest.main()
