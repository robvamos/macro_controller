from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from doomsday.intelligence.persistence import IntelligenceRepository, SCHEMA_VERSION
from services.semantic_campaign_service import (
    attribute_macro_to_campaign,
    create_semantic_campaign,
    list_semantic_campaigns,
    sequence_hash,
    record_campaign_run,
    suggest_campaign_attributions,
)


class SemanticCampaignServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tempdir.name) / "intelligence.db"

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_campaign_keeps_domain_and_multiple_macro_bindings(self) -> None:
        campaign_id = create_semantic_campaign(
            label="Marcia campo", campaign_kind="field_battle", objective="Preparare una marcia PvP",
            operation_tags=("battle", "march"), asset_domains=("heroes", "beasts", "weapons"),
            game_version="1.58.0", repository_path=self.db_path,
        )
        repository = IntelligenceRepository(self.db_path)
        repository.bind_campaign_macro(
            campaign_id=campaign_id, macro_id=5, operation_id="open_march", validation_status="human_reviewed", confidence=0.6,
        )
        repository.bind_campaign_macro(
            campaign_id=campaign_id, macro_id=6, operation_id="select_beast", validation_status="validated", confidence=1.0,
        )

        campaign = list_semantic_campaigns(repository_path=self.db_path)[0]
        self.assertEqual(campaign["asset_domains"], ("heroes", "beasts", "weapons"))
        self.assertEqual({item["operation_id"] for item in campaign["macro_bindings"]}, {"open_march", "select_beast"})
        connection = repository.connect()
        try:
            self.assertEqual(connection.execute("SELECT MAX(version) FROM IntelligenceSchema").fetchone()[0], SCHEMA_VERSION)
        finally:
            connection.close()

    def test_macro_attribution_preserves_sequence_evidence_without_claiming_success(self) -> None:
        campaign_id = create_semantic_campaign(
            label="Evento", campaign_kind="event_operation", objective="Aprire l'evento", repository_path=self.db_path,
        )
        events = [
            {"type": "mouse", "event": "down", "ui_node_id": "event_hub", "game_element_id": 12},
            {"type": "mouse", "event": "up", "ui_node_id": "event_hub", "game_element_id": 12},
        ]
        with patch("services.semantic_campaign_service.get_macro_metadata_by_id", return_value={"id": 9, "nome": "Apri evento"}), patch(
            "services.semantic_campaign_service.load_macro_events", return_value=events
        ):
            result = attribute_macro_to_campaign(
                campaign_id=campaign_id, macro_id=9, operation_id="open_event", repository_path=self.db_path,
            )

        self.assertTrue(result["evidence_id"])
        binding = IntelligenceRepository(self.db_path).list_campaign_macro_bindings(campaign_id=campaign_id)[0]
        self.assertEqual(binding["validation_status"], "unverified")
        self.assertEqual(binding["confidence"], 0.0)

    def test_sequence_hash_changes_only_for_semantic_sequence_changes(self) -> None:
        first = [{"type": "mouse", "event": "down", "ui_node_id": "hub", "game_element_id": 4, "x": 10}]
        moved = [{"type": "mouse", "event": "down", "ui_node_id": "hub", "game_element_id": 4, "x": 999}]
        changed = [{"type": "mouse", "event": "down", "ui_node_id": "battle", "game_element_id": 4}]
        self.assertEqual(sequence_hash(first), sequence_hash(moved))
        self.assertNotEqual(sequence_hash(first), sequence_hash(changed))

    def test_campaign_run_adds_coverage_without_validating_macro(self) -> None:
        campaign_id = create_semantic_campaign(
            label="Gestione bestie", campaign_kind="roster_management", objective="Configurare bestie",
            operation_tags=("beast_support",), asset_domains=("beasts",), repository_path=self.db_path,
        )
        IntelligenceRepository(self.db_path).bind_campaign_macro(
            campaign_id=campaign_id, macro_id=7, operation_id="open_beasts", validation_status="human_reviewed", confidence=0.6,
        )
        record_campaign_run(
            campaign_id=campaign_id, macro_id=None, operation_id="open_beasts", status="observed_success",
            pre_state={"ui.node.home.active": True}, post_state={"ui.node.beasts.active": True}, repository_path=self.db_path,
        )
        campaign = list_semantic_campaigns(repository_path=self.db_path)[0]
        self.assertEqual(campaign["coverage"], {
            "macro_bindings": 1, "validated_bindings": 0, "observed_runs": 1, "successful_runs": 1,
        })

    def test_suggestions_never_bind_macros(self) -> None:
        campaign_id = create_semantic_campaign(
            label="Bestie campo", campaign_kind="field_battle", objective="Gestire bestie per battaglia",
            operation_tags=("battle", "beast_support"), asset_domains=("beasts",), repository_path=self.db_path,
        )
        with patch("services.semantic_campaign_service.get_all_macros", return_value=[{
            "id": 19, "nome": "Battaglia bestie", "descrizione": "supporto bestie", "macro_kind": "user",
        }]):
            suggestions = suggest_campaign_attributions(repository_path=self.db_path)
        self.assertEqual(suggestions[0]["campaign_id"], campaign_id)
        self.assertEqual(IntelligenceRepository(self.db_path).list_campaign_macro_bindings(campaign_id=campaign_id), ())


if __name__ == "__main__":
    unittest.main()
