"""Dedicated persistence for evidence and learning episodes.

This store is intentionally separate from the conflicted macro database and the
offline roster bootstrap database.
"""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from typing import Any, Iterable, Mapping
from uuid import uuid4

from doomsday.intelligence.evidence import ProviderContribution
from doomsday.intelligence.models import GamePlan, to_primitive, utc_now_iso


SCHEMA_VERSION = 3


class IntelligenceRepository:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path, timeout=10.0)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 10000")
        conn.row_factory = sqlite3.Row
        return conn

    def setup(self) -> None:
        conn = self.connect()
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS IntelligenceSchema (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS EvidenceContributions (
                    contribution_id TEXT PRIMARY KEY,
                    subject_id TEXT NOT NULL,
                    field_name TEXT NOT NULL,
                    provider_id TEXT NOT NULL,
                    observed_at TEXT,
                    game_version TEXT,
                    payload_json TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_evidence_subject_field
                    ON EvidenceContributions(subject_id, field_name, observed_at);
                CREATE TABLE IF NOT EXISTS IntelligenceEpisodes (
                    episode_id TEXT PRIMARY KEY,
                    plan_id TEXT NOT NULL,
                    mode_id TEXT,
                    ruleset_id TEXT,
                    objective_id TEXT,
                    status TEXT NOT NULL,
                    plan_json TEXT NOT NULL,
                    executed_actions_json TEXT NOT NULL,
                    outcome_json TEXT NOT NULL,
                    evidence_refs_json TEXT NOT NULL,
                    user_feedback TEXT,
                    started_at TEXT NOT NULL,
                    completed_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS ActionPerformance (
                    action_id TEXT PRIMARY KEY,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    successes INTEGER NOT NULL DEFAULT 0,
                    failures INTEGER NOT NULL DEFAULT 0,
                    total_duration_sec REAL NOT NULL DEFAULT 0,
                    last_status TEXT,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS SemanticCampaigns (
                    campaign_id TEXT PRIMARY KEY,
                    label TEXT NOT NULL,
                    campaign_kind TEXT NOT NULL,
                    objective TEXT NOT NULL,
                    operation_tags_json TEXT NOT NULL,
                    asset_domains_json TEXT NOT NULL,
                    game_version TEXT NOT NULL,
                    status TEXT NOT NULL,
                    notes TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS CampaignMacroBindings (
                    binding_id TEXT PRIMARY KEY,
                    campaign_id TEXT NOT NULL,
                    macro_id INTEGER NOT NULL,
                    operation_id TEXT NOT NULL,
                    relation_type TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    validation_status TEXT NOT NULL,
                    notes TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(campaign_id, macro_id, operation_id),
                    FOREIGN KEY(campaign_id) REFERENCES SemanticCampaigns(campaign_id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_campaign_macro_bindings_macro
                    ON CampaignMacroBindings(macro_id, validation_status, updated_at DESC);
                CREATE TABLE IF NOT EXISTS CampaignSequenceEvidence (
                    evidence_id TEXT PRIMARY KEY,
                    campaign_id TEXT NOT NULL,
                    macro_id INTEGER NOT NULL,
                    sequence_hash TEXT NOT NULL,
                    event_count INTEGER NOT NULL,
                    ui_nodes_json TEXT NOT NULL,
                    element_ids_json TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    source_kind TEXT NOT NULL,
                    notes TEXT NOT NULL,
                    FOREIGN KEY(campaign_id) REFERENCES SemanticCampaigns(campaign_id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_campaign_sequence_campaign
                    ON CampaignSequenceEvidence(campaign_id, macro_id, observed_at DESC);
                CREATE TABLE IF NOT EXISTS CampaignRuns (
                    run_id TEXT PRIMARY KEY,
                    campaign_id TEXT NOT NULL,
                    macro_id INTEGER,
                    operation_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    pre_state_json TEXT NOT NULL,
                    post_state_json TEXT NOT NULL,
                    evidence_refs_json TEXT NOT NULL,
                    user_feedback TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT NOT NULL,
                    FOREIGN KEY(campaign_id) REFERENCES SemanticCampaigns(campaign_id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_campaign_runs_campaign
                    ON CampaignRuns(campaign_id, completed_at DESC);
                """
            )
            conn.execute(
                "INSERT OR IGNORE INTO IntelligenceSchema(version, applied_at) VALUES (?, ?)",
                (SCHEMA_VERSION, utc_now_iso()),
            )
            conn.commit()
        finally:
            conn.close()

    def record_contribution(
        self,
        contribution: ProviderContribution,
        *,
        contribution_id: str | None = None,
    ) -> str:
        self.setup()
        contribution_id = contribution_id or str(uuid4())
        conn = self.connect()
        try:
            conn.execute(
                """
                INSERT OR IGNORE INTO EvidenceContributions(
                    contribution_id, subject_id, field_name, provider_id, observed_at,
                    game_version, payload_json, recorded_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    contribution_id,
                    contribution.subject_id,
                    contribution.field_name,
                    contribution.provider_id,
                    contribution.observed_at,
                    contribution.game_version,
                    _json(contribution),
                    utc_now_iso(),
                ),
            )
            conn.commit()
            return contribution_id
        finally:
            conn.close()

    def list_contributions(self, *, subject_id: str, field_name: str) -> tuple[dict[str, Any], ...]:
        self.setup()
        conn = self.connect()
        try:
            rows = conn.execute(
                """
                SELECT contribution_id, payload_json
                FROM EvidenceContributions
                WHERE subject_id = ? AND field_name = ?
                ORDER BY observed_at DESC, recorded_at DESC
                """,
                (subject_id, field_name),
            ).fetchall()
            return tuple(
                {"contribution_id": row["contribution_id"], **json.loads(row["payload_json"])}
                for row in rows
            )
        finally:
            conn.close()

    def record_episode(
        self,
        plan: GamePlan,
        *,
        status: str,
        executed_action_ids: Iterable[str],
        outcome: Mapping[str, Any] | None = None,
        durations_sec: Mapping[str, float] | None = None,
        evidence_refs: Iterable[str] = (),
        user_feedback: str = "",
        started_at: str = "",
        completed_at: str = "",
    ) -> str:
        self.setup()
        episode_id = str(uuid4())
        executed = tuple(dict.fromkeys(str(item) for item in executed_action_ids))
        durations = dict(durations_sec or {})
        now = utc_now_iso()
        success = status.lower() in {"success", "completed", "objective_complete"}
        conn = self.connect()
        try:
            conn.execute(
                """
                INSERT INTO IntelligenceEpisodes(
                    episode_id, plan_id, mode_id, ruleset_id, objective_id, status,
                    plan_json, executed_actions_json, outcome_json, evidence_refs_json,
                    user_feedback, started_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    episode_id,
                    plan.plan_id,
                    plan.mode_id,
                    plan.ruleset_id,
                    plan.objective_id,
                    status,
                    _json(plan),
                    _json(executed),
                    _json(outcome or {}),
                    _json(tuple(evidence_refs)),
                    user_feedback,
                    started_at or plan.created_at,
                    completed_at or now,
                ),
            )
            for action_id in executed:
                duration = max(0.0, float(durations.get(action_id, 0.0)))
                conn.execute(
                    """
                    INSERT INTO ActionPerformance(
                        action_id, attempts, successes, failures, total_duration_sec,
                        last_status, updated_at
                    ) VALUES (?, 1, ?, ?, ?, ?, ?)
                    ON CONFLICT(action_id) DO UPDATE SET
                        attempts = attempts + 1,
                        successes = successes + excluded.successes,
                        failures = failures + excluded.failures,
                        total_duration_sec = total_duration_sec + excluded.total_duration_sec,
                        last_status = excluded.last_status,
                        updated_at = excluded.updated_at
                    """,
                    (action_id, 1 if success else 0, 0 if success else 1, duration, status, now),
                )
            conn.commit()
            return episode_id
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def get_action_performance(self, action_id: str) -> dict[str, Any] | None:
        self.setup()
        conn = self.connect()
        try:
            row = conn.execute(
                """
                SELECT action_id, attempts, successes, failures, total_duration_sec,
                       last_status, updated_at
                FROM ActionPerformance WHERE action_id = ?
                """,
                (action_id,),
            ).fetchone()
            if row is None:
                return None
            result = dict(row)
            attempts = int(result["attempts"])
            result["success_rate"] = result["successes"] / attempts if attempts else 0.0
            result["average_duration_sec"] = result["total_duration_sec"] / attempts if attempts else 0.0
            return result
        finally:
            conn.close()

    def create_campaign(
        self,
        *,
        label: str,
        campaign_kind: str,
        objective: str,
        operation_tags: Iterable[str] = (),
        asset_domains: Iterable[str] = (),
        game_version: str = "",
        status: str = "draft",
        notes: str = "",
        campaign_id: str | None = None,
    ) -> str:
        self.setup()
        campaign_id = campaign_id or str(uuid4())
        now = utc_now_iso()
        conn = self.connect()
        try:
            conn.execute(
                """
                INSERT INTO SemanticCampaigns(
                    campaign_id, label, campaign_kind, objective, operation_tags_json,
                    asset_domains_json, game_version, status, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    campaign_id, label, campaign_kind, objective,
                    _json(tuple(operation_tags)), _json(tuple(asset_domains)), game_version,
                    status, notes, now, now,
                ),
            )
            conn.commit()
            return campaign_id
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def list_campaigns(self) -> tuple[dict[str, Any], ...]:
        self.setup()
        conn = self.connect()
        try:
            rows = conn.execute(
                """
                SELECT campaign_id, label, campaign_kind, objective, operation_tags_json,
                       asset_domains_json, game_version, status, notes, created_at, updated_at
                FROM SemanticCampaigns ORDER BY updated_at DESC, created_at DESC
                """
            ).fetchall()
            return tuple(_campaign_row(row) for row in rows)
        finally:
            conn.close()

    def bind_campaign_macro(
        self,
        *,
        campaign_id: str,
        macro_id: int,
        operation_id: str,
        relation_type: str = "candidate",
        confidence: float = 0.0,
        validation_status: str = "unverified",
        notes: str = "",
    ) -> str:
        self.setup()
        binding_id = str(uuid4())
        now = utc_now_iso()
        conn = self.connect()
        try:
            conn.execute(
                """
                INSERT INTO CampaignMacroBindings(
                    binding_id, campaign_id, macro_id, operation_id, relation_type,
                    confidence, validation_status, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(campaign_id, macro_id, operation_id) DO UPDATE SET
                    relation_type = excluded.relation_type,
                    confidence = excluded.confidence,
                    validation_status = excluded.validation_status,
                    notes = excluded.notes,
                    updated_at = excluded.updated_at
                """,
                (binding_id, campaign_id, int(macro_id), operation_id, relation_type,
                 max(0.0, min(1.0, float(confidence))), validation_status, notes, now, now),
            )
            row = conn.execute(
                """
                SELECT binding_id FROM CampaignMacroBindings
                WHERE campaign_id = ? AND macro_id = ? AND operation_id = ?
                """,
                (campaign_id, int(macro_id), operation_id),
            ).fetchone()
            conn.commit()
            return str(row["binding_id"])
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def list_campaign_macro_bindings(self, *, campaign_id: str | None = None, macro_id: int | None = None) -> tuple[dict[str, Any], ...]:
        self.setup()
        conn = self.connect()
        try:
            query = """
                SELECT binding_id, campaign_id, macro_id, operation_id, relation_type,
                       confidence, validation_status, notes, created_at, updated_at
                FROM CampaignMacroBindings WHERE 1 = 1
            """
            params: list[Any] = []
            if campaign_id is not None:
                query += " AND campaign_id = ?"
                params.append(campaign_id)
            if macro_id is not None:
                query += " AND macro_id = ?"
                params.append(int(macro_id))
            query += " ORDER BY validation_status DESC, confidence DESC, updated_at DESC"
            return tuple(dict(row) for row in conn.execute(query, params).fetchall())
        finally:
            conn.close()

    def record_campaign_sequence_evidence(
        self,
        *,
        campaign_id: str,
        macro_id: int,
        sequence_hash: str,
        event_count: int,
        ui_nodes: Iterable[str] = (),
        element_ids: Iterable[int] = (),
        observed_at: str = "",
        source_kind: str = "macro_recording",
        notes: str = "",
    ) -> str:
        self.setup()
        evidence_id = str(uuid4())
        conn = self.connect()
        try:
            conn.execute(
                """
                INSERT INTO CampaignSequenceEvidence(
                    evidence_id, campaign_id, macro_id, sequence_hash, event_count,
                    ui_nodes_json, element_ids_json, observed_at, source_kind, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (evidence_id, campaign_id, int(macro_id), sequence_hash, int(event_count),
                 _json(tuple(ui_nodes)), _json(tuple(element_ids)), observed_at or utc_now_iso(), source_kind, notes),
            )
            conn.commit()
            return evidence_id
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def record_campaign_run(
        self,
        *,
        campaign_id: str,
        macro_id: int | None,
        operation_id: str,
        status: str,
        pre_state: Mapping[str, Any] | None = None,
        post_state: Mapping[str, Any] | None = None,
        evidence_refs: Iterable[str] = (),
        user_feedback: str = "",
        started_at: str = "",
        completed_at: str = "",
    ) -> str:
        self.setup()
        if status not in {"observed_success", "observed_failure", "incomplete", "cancelled"}:
            raise ValueError(f"Unsupported campaign-run status: {status}")
        run_id = str(uuid4())
        now = utc_now_iso()
        conn = self.connect()
        try:
            conn.execute(
                """
                INSERT INTO CampaignRuns(
                    run_id, campaign_id, macro_id, operation_id, status, pre_state_json,
                    post_state_json, evidence_refs_json, user_feedback, started_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (run_id, campaign_id, macro_id, operation_id, status, _json(pre_state or {}),
                 _json(post_state or {}), _json(tuple(evidence_refs)), user_feedback,
                 started_at or now, completed_at or now),
            )
            conn.commit()
            return run_id
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def list_campaign_runs(self, *, campaign_id: str) -> tuple[dict[str, Any], ...]:
        self.setup()
        conn = self.connect()
        try:
            rows = conn.execute(
                """
                SELECT run_id, campaign_id, macro_id, operation_id, status, pre_state_json,
                       post_state_json, evidence_refs_json, user_feedback, started_at, completed_at
                FROM CampaignRuns WHERE campaign_id = ? ORDER BY completed_at DESC
                """,
                (campaign_id,),
            ).fetchall()
            return tuple(_campaign_run_row(row) for row in rows)
        finally:
            conn.close()


def _json(value: Any) -> str:
    return json.dumps(to_primitive(value), ensure_ascii=False, sort_keys=True, default=str)


def _campaign_row(row: sqlite3.Row) -> dict[str, Any]:
    result = dict(row)
    result["operation_tags"] = tuple(json.loads(result.pop("operation_tags_json")))
    result["asset_domains"] = tuple(json.loads(result.pop("asset_domains_json")))
    return result


def _campaign_run_row(row: sqlite3.Row) -> dict[str, Any]:
    result = dict(row)
    for key in ("pre_state_json", "post_state_json", "evidence_refs_json"):
        result[key.removesuffix("_json")] = json.loads(result.pop(key))
    return result


__all__ = ["IntelligenceRepository", "SCHEMA_VERSION"]
