import json
import tempfile
import unittest
from pathlib import Path

from doomsday.intelligence.evidence import ProviderContribution
from doomsday.intelligence.models import GamePlan
from doomsday.intelligence.persistence import IntelligenceRepository, SCHEMA_VERSION


def build_plan():
    return GamePlan(
        plan_id="plan-1",
        query="completa campagna",
        mode_id="campaign",
        ruleset_id="campaign-v2",
        objective_id="finish-campaign",
        created_at="2026-07-14T12:00:00+00:00",
        steps=(),
        initial_facts={"ui.campaign.open": False},
        projected_facts={"objective.complete": True},
        success_facts={"objective.complete": True},
    )


def contribution(*, provider_id, field_name="skill_damage", value=100, observed_at="2026-07-14T12:00:00+00:00"):
    return ProviderContribution(
        provider_id=provider_id,
        provider_type="test",
        subject_id="hero.elena",
        field_name=field_name,
        field_value=value,
        confidence=0.8,
        trust_score=0.7,
        observed_at=observed_at,
        source_ref=f"test:{provider_id}",
        game_version="2.1.0",
        normalization_notes=("normalized",),
        metadata={"fixture": True},
    )


class IntelligenceRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.db_path = Path(self.temp_dir.name) / "nested" / "intelligence.db"
        self.repository = IntelligenceRepository(self.db_path)

    def test_setup_and_contribution_round_trip_with_subject_field_filter(self):
        self.repository.setup()
        first_id = self.repository.record_contribution(
            contribution(provider_id="official", value=100, observed_at="2026-07-14T12:00:00+00:00")
        )
        second_id = self.repository.record_contribution(
            contribution(provider_id="ocr", value=110, observed_at="2026-07-15T12:00:00+00:00")
        )
        self.repository.record_contribution(
            contribution(provider_id="other-field", field_name="attack", value=900)
        )

        rows = self.repository.list_contributions(
            subject_id="hero.elena",
            field_name="skill_damage",
        )

        self.assertEqual([row["contribution_id"] for row in rows], [second_id, first_id])
        self.assertEqual([row["provider_id"] for row in rows], ["ocr", "official"])
        self.assertEqual(rows[0]["field_value"], 110)
        self.assertEqual(rows[0]["normalization_notes"], ["normalized"])
        self.assertEqual(rows[0]["metadata"], {"fixture": True})

        conn = self.repository.connect()
        try:
            version = conn.execute("SELECT version FROM IntelligenceSchema").fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(version, SCHEMA_VERSION)

    def test_episode_storage_and_action_performance_are_accumulated(self):
        plan = build_plan()
        success_episode_id = self.repository.record_episode(
            plan,
            status="completed",
            executed_action_ids=("open-campaign", "open-campaign", "start-battle"),
            durations_sec={"open-campaign": 2.0, "start-battle": 8.0},
            outcome={"reward": 50, "objective.complete": True},
            evidence_refs=("claim-1", "claim-2"),
            user_feedback="ok",
            completed_at="2026-07-14T12:05:00+00:00",
        )
        failure_episode_id = self.repository.record_episode(
            plan,
            status="failed",
            executed_action_ids=("open-campaign",),
            durations_sec={"open-campaign": 4.0},
            outcome={"error": "popup"},
            evidence_refs=("claim-3",),
            completed_at="2026-07-14T12:10:00+00:00",
        )

        open_performance = self.repository.get_action_performance("open-campaign")
        battle_performance = self.repository.get_action_performance("start-battle")

        self.assertEqual(open_performance["attempts"], 2)
        self.assertEqual(open_performance["successes"], 1)
        self.assertEqual(open_performance["failures"], 1)
        self.assertEqual(open_performance["total_duration_sec"], 6.0)
        self.assertEqual(open_performance["success_rate"], 0.5)
        self.assertEqual(open_performance["average_duration_sec"], 3.0)
        self.assertEqual(open_performance["last_status"], "failed")

        self.assertEqual(battle_performance["attempts"], 1)
        self.assertEqual(battle_performance["successes"], 1)
        self.assertEqual(battle_performance["failures"], 0)
        self.assertEqual(battle_performance["average_duration_sec"], 8.0)
        self.assertIsNone(self.repository.get_action_performance("never-executed"))

        conn = self.repository.connect()
        try:
            rows = conn.execute(
                """
                SELECT episode_id, executed_actions_json, outcome_json,
                       evidence_refs_json, user_feedback
                FROM IntelligenceEpisodes
                ORDER BY completed_at
                """
            ).fetchall()
        finally:
            conn.close()

        self.assertEqual([row["episode_id"] for row in rows], [success_episode_id, failure_episode_id])
        self.assertEqual(
            json.loads(rows[0]["executed_actions_json"]),
            ["open-campaign", "start-battle"],
        )
        self.assertEqual(json.loads(rows[0]["outcome_json"])["reward"], 50)
        self.assertEqual(json.loads(rows[0]["evidence_refs_json"]), ["claim-1", "claim-2"])
        self.assertEqual(rows[0]["user_feedback"], "ok")


if __name__ == "__main__":
    unittest.main()
