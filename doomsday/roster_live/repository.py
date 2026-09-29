"""Repository transazionale e revisionato per il roster live."""

from __future__ import annotations

from collections import defaultdict
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
from typing import Any, Iterable, Mapping
from uuid import uuid4

from core.paths import DOOMSDAY_LIVE_ROSTER_DB_PATH, LEGACY_DOOMSDAY_LIVE_ROSTER_DB_PATH
from doomsday.roster_live.models import (
    ArtifactRecord,
    ChangeDecision,
    ChangeSetPreview,
    ChangeSetState,
    CommitResult,
    PreviewItem,
    SessionState,
    canonical_json,
    parse_utc,
    utc_now_iso,
    validate_field_value,
    value_hash,
)


SCHEMA_VERSION = 1
DEFAULT_LIVE_ROSTER_DB = DOOMSDAY_LIVE_ROSTER_DB_PATH
MIGRATIONS_DIR = Path(__file__).with_name("migrations")


class LiveRosterRepository:
    def __init__(self, path: str | Path = DEFAULT_LIVE_ROSTER_DB) -> None:
        self.path = Path(path)

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path == DEFAULT_LIVE_ROSTER_DB and not self.path.exists() and LEGACY_DOOMSDAY_LIVE_ROSTER_DB_PATH.exists():
            shutil.copy2(LEGACY_DOOMSDAY_LIVE_ROSTER_DB_PATH, self.path)
        connection = sqlite3.connect(self.path, timeout=10.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection

    def setup(self) -> None:
        connection = self.connect()
        try:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS LiveRosterSchema(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
            )
            applied = {
                int(row[0]) for row in connection.execute("SELECT version FROM LiveRosterSchema").fetchall()
            }
            for migration in sorted(MIGRATIONS_DIR.glob("[0-9][0-9][0-9]_*.sql")):
                version = int(migration.name.split("_", 1)[0])
                if version in applied:
                    continue
                connection.executescript(migration.read_text(encoding="utf-8"))
                connection.execute(
                    "INSERT INTO LiveRosterSchema(version, applied_at) VALUES (?, ?)",
                    (version, utc_now_iso()),
                )
            current = connection.execute("SELECT COALESCE(MAX(version), 0) FROM LiveRosterSchema").fetchone()[0]
            if current != SCHEMA_VERSION:
                raise RuntimeError(f"Schema roster live {current}, atteso {SCHEMA_VERSION}.")
            connection.commit()
        finally:
            connection.close()

    def create_session(
        self,
        *,
        session_id: str,
        runtime_id: str,
        capture_method: str,
        game_version: str,
        account_scope: str,
        started_at: str,
    ) -> str:
        self.setup()
        parse_utc(started_at)
        if not all(value.strip() for value in (session_id, runtime_id, capture_method, game_version, account_scope)):
            raise ValueError("Sessione incompleta: runtime, metodo, versione e account_scope sono obbligatori.")
        connection = self.connect()
        try:
            connection.execute(
                """
                INSERT INTO RosterCaptureSessions(
                    session_id, state, runtime_id, capture_method, game_version,
                    account_scope, started_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    SessionState.CAPTURING.value,
                    runtime_id,
                    capture_method,
                    game_version,
                    account_scope,
                    started_at,
                    started_at,
                ),
            )
            connection.commit()
            return session_id
        finally:
            connection.close()

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        self.setup()
        connection = self.connect()
        try:
            row = connection.execute(
                "SELECT * FROM RosterCaptureSessions WHERE session_id = ?", (session_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            connection.close()

    def list_sessions(self, *, limit: int = 50) -> tuple[dict[str, Any], ...]:
        self.setup()
        connection = self.connect()
        try:
            rows = connection.execute(
                "SELECT * FROM RosterCaptureSessions ORDER BY started_at DESC LIMIT ?", (max(1, limit),)
            ).fetchall()
            return tuple(dict(row) for row in rows)
        finally:
            connection.close()

    def add_artifact(self, artifact: ArtifactRecord) -> str:
        self.setup()
        parse_utc(artifact.captured_at)
        if len(artifact.sha256) != 64 or artifact.width <= 0 or artifact.height <= 0:
            raise ValueError("Metadati artifact non validi.")
        connection = self.connect()
        try:
            session = connection.execute(
                "SELECT state FROM RosterCaptureSessions WHERE session_id = ?", (artifact.session_id,)
            ).fetchone()
            if session is None:
                raise KeyError("Sessione roster inesistente.")
            if session["state"] not in {SessionState.CAPTURING.value, SessionState.EXTRACTED.value}:
                raise ValueError("La sessione non accetta nuovi artifact.")
            existing = connection.execute(
                "SELECT artifact_id FROM RosterCaptureArtifacts WHERE session_id = ? AND sha256 = ?",
                (artifact.session_id, artifact.sha256),
            ).fetchone()
            if existing:
                return str(existing["artifact_id"])
            connection.execute(
                """
                INSERT INTO RosterCaptureArtifacts(
                    artifact_id, session_id, stage, hero_id, path, sha256,
                    width, height, captured_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    artifact.artifact_id,
                    artifact.session_id,
                    artifact.stage,
                    artifact.hero_id,
                    artifact.path,
                    artifact.sha256,
                    artifact.width,
                    artifact.height,
                    artifact.captured_at,
                    canonical_json(dict(artifact.metadata)),
                ),
            )
            connection.commit()
            return artifact.artifact_id
        finally:
            connection.close()

    def get_artifact(self, artifact_id: str) -> dict[str, Any] | None:
        self.setup()
        connection = self.connect()
        try:
            row = connection.execute(
                "SELECT * FROM RosterCaptureArtifacts WHERE artifact_id = ?", (artifact_id,)
            ).fetchone()
            if row is None:
                return None
            result = dict(row)
            result["metadata"] = json.loads(result.pop("metadata_json"))
            return result
        finally:
            connection.close()

    def add_candidates(
        self,
        *,
        session_id: str,
        artifact_id: str,
        hero_id: str,
        fields: Mapping[str, Any],
        field_confidences: Mapping[str, float],
        observed_at: str,
        source_ref: str,
        stage: str,
        parser_version: str,
        locale: str,
        notes: Iterable[str] = (),
    ) -> tuple[str, ...]:
        self.setup()
        parse_utc(observed_at)
        if not source_ref or not stage or not parser_version or not locale:
            raise ValueError("Lineage candidato incompleta.")
        if not fields:
            raise ValueError("Nessun campo candidato.")
        connection = self.connect()
        candidate_ids: list[str] = []
        try:
            connection.execute("BEGIN IMMEDIATE")
            session = connection.execute(
                "SELECT state FROM RosterCaptureSessions WHERE session_id = ?", (session_id,)
            ).fetchone()
            artifact = connection.execute(
                "SELECT sha256, session_id FROM RosterCaptureArtifacts WHERE artifact_id = ?", (artifact_id,)
            ).fetchone()
            if session is None or artifact is None or artifact["session_id"] != session_id:
                raise ValueError("Sessione o artifact non coerenti.")
            if session["state"] not in {SessionState.CAPTURING.value, SessionState.EXTRACTED.value}:
                raise ValueError("La sessione non accetta nuovi candidati.")
            for field_name, raw_value in fields.items():
                value = validate_field_value(field_name, raw_value)
                confidence = float(field_confidences.get(field_name, -1))
                if not 0.0 <= confidence <= 1.0:
                    raise ValueError(f"Confidence mancante o non valida per {field_name}.")
                digest = value_hash(value)
                idempotency_key = hashlib.sha256(
                    f"{session_id}|{hero_id}|{field_name}|{digest}|{artifact['sha256']}".encode("utf-8")
                ).hexdigest()
                existing = connection.execute(
                    "SELECT candidate_id FROM RosterObservationCandidates WHERE idempotency_key = ?",
                    (idempotency_key,),
                ).fetchone()
                if existing:
                    candidate_ids.append(str(existing["candidate_id"]))
                    continue
                candidate_id = str(uuid4())
                connection.execute(
                    """
                    INSERT INTO RosterObservationCandidates(
                        candidate_id, session_id, artifact_id, hero_id, field_name,
                        proposed_json, normalized_hash, confidence, observed_at,
                        source_ref, stage, parser_version, locale, notes_json, idempotency_key
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        candidate_id,
                        session_id,
                        artifact_id,
                        hero_id,
                        field_name,
                        canonical_json(value),
                        digest,
                        confidence,
                        observed_at,
                        source_ref,
                        stage,
                        parser_version,
                        locale,
                        canonical_json(tuple(notes)),
                        idempotency_key,
                    ),
                )
                candidate_ids.append(candidate_id)
            connection.execute(
                "UPDATE RosterCaptureSessions SET state = ?, updated_at = ? WHERE session_id = ?",
                (SessionState.EXTRACTED.value, utc_now_iso(), session_id),
            )
            connection.commit()
            return tuple(candidate_ids)
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def create_preview(self, session_id: str) -> ChangeSetPreview:
        self.setup()
        connection = self.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT change_set_id FROM RosterChangeSets WHERE session_id = ?", (session_id,)
            ).fetchone()
            if existing:
                connection.commit()
                return self.get_preview(str(existing["change_set_id"]))
            session = connection.execute(
                "SELECT state FROM RosterCaptureSessions WHERE session_id = ?", (session_id,)
            ).fetchone()
            if session is None:
                raise KeyError("Sessione roster inesistente.")
            if session["state"] != SessionState.EXTRACTED.value:
                raise ValueError("Servono candidati estratti prima dell'anteprima.")
            rows = connection.execute(
                """
                SELECT c.*, a.sha256 AS artifact_sha256
                FROM RosterObservationCandidates c
                JOIN RosterCaptureArtifacts a ON a.artifact_id = c.artifact_id
                WHERE c.session_id = ?
                ORDER BY c.hero_id, c.field_name, c.confidence DESC, c.observed_at DESC
                """,
                (session_id,),
            ).fetchall()
            if not rows:
                raise ValueError("Nessun candidato disponibile.")
            latest_revision = int(
                connection.execute("SELECT COALESCE(MAX(revision_id), 0) FROM RosterRevisions").fetchone()[0]
            )
            change_set_id = str(uuid4())
            now = utc_now_iso()
            connection.execute(
                """
                INSERT INTO RosterChangeSets(change_set_id, session_id, base_revision, state, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (change_set_id, session_id, latest_revision, ChangeSetState.PREVIEW_READY.value, now),
            )
            grouped: dict[tuple[str, str], list[sqlite3.Row]] = defaultdict(list)
            for row in rows:
                grouped[(row["hero_id"], row["field_name"])].append(row)
            for (hero_id, field_name), candidates in grouped.items():
                selected = candidates[0]
                current = connection.execute(
                    "SELECT value_json FROM RosterHeroFacts WHERE hero_id = ? AND field_name = ?",
                    (hero_id, field_name),
                ).fetchone()
                alternatives = [
                    {
                        "candidate_id": row["candidate_id"],
                        "value": json.loads(row["proposed_json"]),
                        "confidence": row["confidence"],
                        "source_ref": row["source_ref"],
                    }
                    for row in candidates
                ]
                conflict = len({row["normalized_hash"] for row in candidates}) > 1
                connection.execute(
                    """
                    INSERT INTO RosterChangeItems(
                        item_id, change_set_id, candidate_id, hero_id, field_name,
                        current_json, proposed_json, confidence, source_ref,
                        artifact_sha256, conflict, alternatives_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid4()),
                        change_set_id,
                        selected["candidate_id"],
                        hero_id,
                        field_name,
                        current["value_json"] if current else None,
                        selected["proposed_json"],
                        selected["confidence"],
                        selected["source_ref"],
                        selected["artifact_sha256"],
                        int(conflict),
                        canonical_json(alternatives),
                    ),
                )
            connection.execute(
                "UPDATE RosterCaptureSessions SET state = ?, updated_at = ? WHERE session_id = ?",
                (SessionState.PREVIEW_READY.value, now, session_id),
            )
            connection.commit()
            return self.get_preview(change_set_id)
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def get_preview(self, change_set_id: str) -> ChangeSetPreview:
        self.setup()
        connection = self.connect()
        try:
            change_set = connection.execute(
                "SELECT * FROM RosterChangeSets WHERE change_set_id = ?", (change_set_id,)
            ).fetchone()
            if change_set is None:
                raise KeyError("Change-set roster inesistente.")
            rows = connection.execute(
                "SELECT * FROM RosterChangeItems WHERE change_set_id = ? ORDER BY hero_id, field_name",
                (change_set_id,),
            ).fetchall()
            items = tuple(
                PreviewItem(
                    item_id=row["item_id"],
                    hero_id=row["hero_id"],
                    field_name=row["field_name"],
                    current_value=json.loads(row["current_json"]) if row["current_json"] is not None else None,
                    proposed_value=json.loads(row["proposed_json"]),
                    confidence=float(row["confidence"]),
                    source_ref=row["source_ref"],
                    artifact_sha256=row["artifact_sha256"],
                    conflict=bool(row["conflict"]),
                    alternatives=tuple(json.loads(row["alternatives_json"])),
                    decision=ChangeDecision(row["decision"]),
                    override_value=json.loads(row["override_json"]) if row["override_json"] else None,
                    decision_reason=row["decision_reason"],
                )
                for row in rows
            )
            return ChangeSetPreview(
                change_set_id=change_set_id,
                session_id=change_set["session_id"],
                base_revision=int(change_set["base_revision"]),
                state=ChangeSetState(change_set["state"]),
                items=items,
            )
        finally:
            connection.close()

    def decide(
        self,
        change_set_id: str,
        *,
        item_id: str,
        decision: ChangeDecision | str,
        override_value: Any = None,
        reason: str = "",
    ) -> None:
        self.setup()
        choice = ChangeDecision(decision)
        if choice == ChangeDecision.UNRESOLVED:
            override_json = None
        elif choice == ChangeDecision.MANUAL_OVERRIDE:
            if override_value is None:
                raise ValueError("Il valore manuale è obbligatorio.")
            override_json = "__pending_validation__"
        else:
            override_json = None
        connection = self.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT i.field_name, c.state
                FROM RosterChangeItems i JOIN RosterChangeSets c USING(change_set_id)
                WHERE i.change_set_id = ? AND i.item_id = ?
                """,
                (change_set_id, item_id),
            ).fetchone()
            if row is None:
                raise KeyError("Voce di anteprima inesistente.")
            if row["state"] != ChangeSetState.PREVIEW_READY.value:
                raise ValueError("Il change-set non accetta decisioni.")
            if choice == ChangeDecision.MANUAL_OVERRIDE:
                override_json = canonical_json(validate_field_value(row["field_name"], override_value))
            connection.execute(
                """
                UPDATE RosterChangeItems
                SET decision = ?, override_json = ?, decision_reason = ?
                WHERE item_id = ?
                """,
                (choice.value, override_json, reason.strip(), item_id),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def confirm(self, change_set_id: str) -> ChangeSetPreview:
        self.setup()
        connection = self.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            change_set = connection.execute(
                "SELECT session_id, state FROM RosterChangeSets WHERE change_set_id = ?", (change_set_id,)
            ).fetchone()
            if change_set is None:
                raise KeyError("Change-set roster inesistente.")
            if change_set["state"] == ChangeSetState.CONFIRMED.value:
                connection.commit()
                return self.get_preview(change_set_id)
            if change_set["state"] != ChangeSetState.PREVIEW_READY.value:
                raise ValueError("Il change-set non è confermabile.")
            unresolved = int(
                connection.execute(
                    "SELECT COUNT(*) FROM RosterChangeItems WHERE change_set_id = ? AND decision = ?",
                    (change_set_id, ChangeDecision.UNRESOLVED.value),
                ).fetchone()[0]
            )
            if unresolved:
                raise ValueError(f"Restano {unresolved} decisioni non risolte.")
            now = utc_now_iso()
            connection.execute(
                "UPDATE RosterChangeSets SET state = ?, confirmed_at = ? WHERE change_set_id = ?",
                (ChangeSetState.CONFIRMED.value, now, change_set_id),
            )
            connection.execute(
                "UPDATE RosterCaptureSessions SET state = ?, updated_at = ? WHERE session_id = ?",
                (SessionState.CONFIRMED.value, now, change_set["session_id"]),
            )
            connection.commit()
            return self.get_preview(change_set_id)
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def commit(self, change_set_id: str, *, expected_base_revision: int) -> CommitResult:
        self.setup()
        connection = self.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            change_set = connection.execute(
                "SELECT * FROM RosterChangeSets WHERE change_set_id = ?", (change_set_id,)
            ).fetchone()
            if change_set is None:
                raise KeyError("Change-set roster inesistente.")
            if change_set["state"] == ChangeSetState.COMMITTED.value:
                revision = int(change_set["committed_revision"])
                counts = connection.execute(
                    "SELECT COUNT(*) AS total, SUM(decision = 'rejected') AS rejected FROM RosterChangeItems WHERE change_set_id = ?",
                    (change_set_id,),
                ).fetchone()
                connection.commit()
                return CommitResult(
                    change_set_id,
                    revision,
                    int(counts["total"] or 0) - int(counts["rejected"] or 0),
                    int(counts["rejected"] or 0),
                    0,
                    True,
                )
            if change_set["state"] != ChangeSetState.CONFIRMED.value:
                raise ValueError("Il change-set deve essere confermato prima del commit.")
            latest_revision = int(
                connection.execute("SELECT COALESCE(MAX(revision_id), 0) FROM RosterRevisions").fetchone()[0]
            )
            if expected_base_revision != int(change_set["base_revision"]) or latest_revision != expected_base_revision:
                raise RuntimeError("Revisione base obsoleta: rigenerare l'anteprima.")
            now = utc_now_iso()
            cursor = connection.execute(
                "INSERT INTO RosterRevisions(parent_revision, change_set_id, created_at) VALUES (?, ?, ?)",
                (latest_revision, change_set_id, now),
            )
            revision_id = int(cursor.lastrowid)
            rows = connection.execute(
                """
                SELECT i.*, c.observed_at, c.parser_version, c.locale, c.stage,
                       c.notes_json, c.artifact_id, s.runtime_id, s.capture_method,
                       s.game_version, s.account_scope
                FROM RosterChangeItems i
                JOIN RosterObservationCandidates c ON c.candidate_id = i.candidate_id
                JOIN RosterCaptureSessions s ON s.session_id = c.session_id
                WHERE i.change_set_id = ? ORDER BY i.hero_id, i.field_name
                """,
                (change_set_id,),
            ).fetchall()
            applied = 0
            rejected = 0
            outbox_count = 0
            for row in rows:
                decision = ChangeDecision(row["decision"])
                if decision == ChangeDecision.REJECTED:
                    rejected += 1
                    continue
                if decision == ChangeDecision.UNRESOLVED:
                    raise RuntimeError("Decisione irrisolta rilevata durante il commit.")
                final_json = row["override_json"] if decision == ChangeDecision.MANUAL_OVERRIDE else row["proposed_json"]
                final_value = validate_field_value(row["field_name"], json.loads(final_json))
                current = connection.execute(
                    "SELECT value_json FROM RosterHeroFacts WHERE hero_id = ? AND field_name = ?",
                    (row["hero_id"], row["field_name"]),
                ).fetchone()
                display_name = row["hero_id"]
                if row["field_name"] in {"display_name", "hero_name"} and isinstance(final_value, str):
                    display_name = final_value
                connection.execute(
                    """
                    INSERT INTO RosterHeroes(hero_id, display_name, created_at, updated_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(hero_id) DO UPDATE SET
                        display_name = CASE
                            WHEN excluded.display_name != excluded.hero_id THEN excluded.display_name
                            ELSE RosterHeroes.display_name
                        END,
                        updated_at = excluded.updated_at
                    """,
                    (row["hero_id"], display_name, now, now),
                )
                connection.execute(
                    """
                    INSERT INTO RosterFactHistory(
                        revision_id, hero_id, field_name, old_json, new_json,
                        candidate_id, decision, changed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        revision_id,
                        row["hero_id"],
                        row["field_name"],
                        current["value_json"] if current else None,
                        canonical_json(final_value),
                        row["candidate_id"],
                        decision.value,
                        now,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO RosterHeroFacts(
                        hero_id, field_name, value_json, revision_id, candidate_id, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(hero_id, field_name) DO UPDATE SET
                        value_json = excluded.value_json,
                        revision_id = excluded.revision_id,
                        candidate_id = excluded.candidate_id,
                        updated_at = excluded.updated_at
                    """,
                    (
                        row["hero_id"],
                        row["field_name"],
                        canonical_json(final_value),
                        revision_id,
                        row["candidate_id"],
                        now,
                    ),
                )
                outbox_id = hashlib.sha256(f"{revision_id}|{row['candidate_id']}".encode("utf-8")).hexdigest()
                payload = {
                    "provider_id": f"game-ui:{row['runtime_id']}",
                    "provider_type": "first-party-game-ui",
                    "subject_id": f"hero:{row['hero_id']}",
                    "field_name": row["field_name"],
                    "field_value": final_value,
                    "confidence": float(row["confidence"]),
                    "observed_at": row["observed_at"],
                    "source_ref": row["source_ref"],
                    "trust_score": 0.95,
                    "game_version": row["game_version"],
                    "server_scope": row["account_scope"],
                    "normalization_notes": json.loads(row["notes_json"]),
                    "metadata": {
                        "capture_method": row["capture_method"],
                        "stage": row["stage"],
                        "parser_version": row["parser_version"],
                        "locale": row["locale"],
                        "artifact_id": row["artifact_id"],
                        "artifact_sha256": row["artifact_sha256"],
                        "decision": decision.value,
                    },
                }
                connection.execute(
                    """
                    INSERT INTO RosterEvidenceOutbox(
                        outbox_id, revision_id, candidate_id, payload_json, created_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (outbox_id, revision_id, row["candidate_id"], canonical_json(payload), now),
                )
                applied += 1
                outbox_count += 1
            connection.execute(
                """
                UPDATE RosterChangeSets SET state = ?, committed_revision = ?
                WHERE change_set_id = ?
                """,
                (ChangeSetState.COMMITTED.value, revision_id, change_set_id),
            )
            connection.execute(
                "UPDATE RosterCaptureSessions SET state = ?, updated_at = ? WHERE session_id = ?",
                (SessionState.COMMITTED.value, now, change_set["session_id"]),
            )
            connection.execute(
                """
                INSERT INTO RosterCommitAudit(change_set_id, revision_id, event_type, payload_json, created_at)
                VALUES (?, ?, 'committed', ?, ?)
                """,
                (
                    change_set_id,
                    revision_id,
                    canonical_json({"applied_items": applied, "rejected_items": rejected}),
                    now,
                ),
            )
            connection.commit()
            return CommitResult(change_set_id, revision_id, applied, rejected, outbox_count)
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def list_roster(self) -> tuple[dict[str, Any], ...]:
        self.setup()
        connection = self.connect()
        try:
            rows = connection.execute(
                """
                SELECT h.hero_id, h.display_name, f.field_name, f.value_json,
                       f.revision_id, f.updated_at
                FROM RosterHeroes h LEFT JOIN RosterHeroFacts f USING(hero_id)
                ORDER BY h.display_name COLLATE NOCASE, f.field_name
                """
            ).fetchall()
            heroes: dict[str, dict[str, Any]] = {}
            for row in rows:
                hero = heroes.setdefault(
                    row["hero_id"],
                    {"hero_id": row["hero_id"], "display_name": row["display_name"], "facts": {}},
                )
                if row["field_name"] is not None:
                    hero["facts"][row["field_name"]] = {
                        "value": json.loads(row["value_json"]),
                        "revision_id": int(row["revision_id"]),
                        "updated_at": row["updated_at"],
                    }
            return tuple(heroes.values())
        finally:
            connection.close()

    def pending_outbox(self, *, limit: int = 100) -> tuple[dict[str, Any], ...]:
        self.setup()
        connection = self.connect()
        try:
            rows = connection.execute(
                """
                SELECT outbox_id, payload_json, attempts FROM RosterEvidenceOutbox
                WHERE status = 'pending' ORDER BY created_at LIMIT ?
                """,
                (max(1, limit),),
            ).fetchall()
            return tuple(
                {
                    "outbox_id": row["outbox_id"],
                    "payload": json.loads(row["payload_json"]),
                    "attempts": int(row["attempts"]),
                }
                for row in rows
            )
        finally:
            connection.close()

    def mark_outbox_published(self, outbox_id: str) -> None:
        self._update_outbox(outbox_id, status="published", error="")

    def mark_outbox_failed(self, outbox_id: str, error: str) -> None:
        self._update_outbox(outbox_id, status="pending", error=error[:1000])

    def _update_outbox(self, outbox_id: str, *, status: str, error: str) -> None:
        self.setup()
        connection = self.connect()
        try:
            connection.execute(
                """
                UPDATE RosterEvidenceOutbox
                SET status = ?, attempts = attempts + 1, last_error = ?,
                    published_at = CASE WHEN ? = 'published' THEN ? ELSE published_at END
                WHERE outbox_id = ?
                """,
                (status, error, status, utc_now_iso(), outbox_id),
            )
            connection.commit()
        finally:
            connection.close()


__all__ = ["DEFAULT_LIVE_ROSTER_DB", "LiveRosterRepository", "SCHEMA_VERSION"]
