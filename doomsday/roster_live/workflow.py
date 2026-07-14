"""Use case applicativo per capture, preview, conferma e commit roster."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from doomsday.intelligence.evidence import ProviderContribution
from doomsday.intelligence.persistence import IntelligenceRepository
from doomsday.roster_live.artifact_store import RosterArtifactStore
from doomsday.roster_live.models import (
    ArtifactRecord,
    ChangeDecision,
    ChangeSetPreview,
    CommitResult,
    normalize_hero_id,
    utc_now_iso,
)
from doomsday.roster_live.repository import DEFAULT_LIVE_ROSTER_DB, LiveRosterRepository
from doomsday.services.live_roster_service import (
    CaptureMethod,
    GameRosterCaptureProvider,
    LiveRosterAcquisitionService,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ARTIFACT_ROOT = PROJECT_ROOT / ".tools" / "roster-acquisition"


class LiveRosterWorkflow:
    def __init__(
        self,
        repository: LiveRosterRepository | None = None,
        artifact_store: RosterArtifactStore | None = None,
        acquisition: LiveRosterAcquisitionService | None = None,
    ) -> None:
        self.repository = repository or LiveRosterRepository(DEFAULT_LIVE_ROSTER_DB)
        self.artifact_store = artifact_store or RosterArtifactStore(DEFAULT_ARTIFACT_ROOT)
        self.acquisition = acquisition or LiveRosterAcquisitionService()

    def begin_session(
        self,
        *,
        runtime_id: str,
        capture_method: CaptureMethod | str,
        game_version: str,
        account_scope: str = "local-user",
        started_at: str | None = None,
    ) -> str:
        session_id = str(uuid4())
        return self.repository.create_session(
            session_id=session_id,
            runtime_id=runtime_id,
            capture_method=CaptureMethod(capture_method).value,
            game_version=game_version,
            account_scope=account_scope,
            started_at=started_at or utc_now_iso(),
        )

    def capture(
        self,
        session_id: str,
        *,
        provider: GameRosterCaptureProvider,
        stage: str,
        hero_id: str = "roster",
        metadata: Mapping[str, Any] | None = None,
    ) -> ArtifactRecord:
        session = self._session(session_id)
        if session["runtime_id"] != provider.runtime_id:
            raise ValueError("Il provider non coincide con il runtime della sessione.")
        if session["capture_method"] != provider.capture_method.value:
            raise ValueError("Il provider usa un metodo di cattura diverso dalla sessione.")
        image = provider.capture_frame()
        stored = self.artifact_store.store_image(
            session_id=session_id,
            stage=stage,
            hero_id=hero_id,
            image=image,
        )
        artifact = ArtifactRecord(
            artifact_id=str(uuid4()),
            session_id=session_id,
            stage=stage,
            hero_id=normalize_hero_id(hero_id),
            path=stored.path.as_posix(),
            sha256=stored.sha256,
            width=stored.width,
            height=stored.height,
            captured_at=stored.captured_at,
            metadata={"byte_size": stored.byte_size, **dict(metadata or {})},
        )
        artifact_id = self.repository.add_artifact(artifact)
        if artifact_id != artifact.artifact_id:
            existing = self.repository.get_artifact(artifact_id)
            if existing:
                return ArtifactRecord(
                    artifact_id=artifact_id,
                    session_id=existing["session_id"],
                    stage=existing["stage"],
                    hero_id=existing["hero_id"],
                    path=existing["path"],
                    sha256=existing["sha256"],
                    width=int(existing["width"]),
                    height=int(existing["height"]),
                    captured_at=existing["captured_at"],
                    metadata=existing["metadata"],
                )
        return artifact

    def register_image(
        self,
        session_id: str,
        *,
        image,
        stage: str,
        hero_id: str = "roster",
        metadata: Mapping[str, Any] | None = None,
    ) -> ArtifactRecord:
        class _ImageProvider:
            runtime_id = self._session(session_id)["runtime_id"]
            capture_method = CaptureMethod(self._session(session_id)["capture_method"])

            def capture_frame(_provider_self):
                return image

        return self.capture(
            session_id,
            provider=_ImageProvider(),
            stage=stage,
            hero_id=hero_id,
            metadata=metadata,
        )

    def ingest_fields(
        self,
        session_id: str,
        *,
        artifact_id: str,
        hero_id: str,
        fields: Mapping[str, Any],
        field_confidences: Mapping[str, float],
        observed_at: str | None = None,
        parser_version: str = "manual-v1",
        locale: str = "it-IT",
        notes: tuple[str, ...] = (),
    ) -> tuple[str, ...]:
        session = self._session(session_id)
        artifact = self.repository.get_artifact(artifact_id)
        if artifact is None or artifact["session_id"] != session_id:
            raise ValueError("Artifact non appartenente alla sessione.")
        return self.repository.add_candidates(
            session_id=session_id,
            artifact_id=artifact_id,
            hero_id=normalize_hero_id(hero_id),
            fields=fields,
            field_confidences=field_confidences,
            observed_at=observed_at or datetime.now(timezone.utc).isoformat(),
            source_ref=f"artifact:{artifact['sha256']}",
            stage=artifact["stage"],
            parser_version=parser_version,
            locale=locale,
            notes=notes,
        )

    def ingest_ocr_text(
        self,
        session_id: str,
        *,
        artifact_id: str,
        hero_id: str,
        ocr_text: str,
        locale: str = "it-IT",
        parser_version: str = "hero-ocr-v1",
    ) -> tuple[str, ...]:
        session = self._session(session_id)
        artifact = self.repository.get_artifact(artifact_id)
        if artifact is None:
            raise KeyError("Artifact roster inesistente.")
        observation = self.acquisition.observation_from_ocr_text(
            hero_id=normalize_hero_id(hero_id),
            ocr_text=ocr_text,
            source_ref=f"artifact:{artifact['sha256']}",
            capture_method=CaptureMethod(session["capture_method"]),
            runtime_id=session["runtime_id"],
            game_version=session["game_version"],
        )
        return self.ingest_fields(
            session_id,
            artifact_id=artifact_id,
            hero_id=hero_id,
            fields=observation.fields,
            field_confidences={key: observation.confidence for key in observation.fields},
            observed_at=observation.observed_at,
            parser_version=parser_version,
            locale=locale,
            notes=observation.notes,
        )

    def preview(self, session_id: str) -> ChangeSetPreview:
        return self.repository.create_preview(session_id)

    def decide(
        self,
        change_set_id: str,
        *,
        item_id: str,
        decision: ChangeDecision | str,
        override_value: Any = None,
        reason: str = "",
    ) -> ChangeSetPreview:
        self.repository.decide(
            change_set_id,
            item_id=item_id,
            decision=decision,
            override_value=override_value,
            reason=reason,
        )
        return self.repository.get_preview(change_set_id)

    def confirm(self, change_set_id: str) -> ChangeSetPreview:
        return self.repository.confirm(change_set_id)

    def commit(self, change_set_id: str, *, expected_base_revision: int) -> CommitResult:
        return self.repository.commit(change_set_id, expected_base_revision=expected_base_revision)

    def publish_evidence(
        self,
        intelligence_repository: IntelligenceRepository,
        *,
        limit: int = 100,
    ) -> dict[str, int]:
        result = {"published": 0, "failed": 0}
        for item in self.repository.pending_outbox(limit=limit):
            try:
                payload = item["payload"]
                contribution = ProviderContribution(**payload)
                intelligence_repository.record_contribution(
                    contribution,
                    contribution_id=item["outbox_id"],
                )
                self.repository.mark_outbox_published(item["outbox_id"])
                result["published"] += 1
            except Exception as exc:
                self.repository.mark_outbox_failed(item["outbox_id"], str(exc))
                result["failed"] += 1
        return result

    def _session(self, session_id: str) -> dict[str, Any]:
        session = self.repository.get_session(session_id)
        if session is None:
            raise KeyError("Sessione roster inesistente.")
        return session


__all__ = ["DEFAULT_ARTIFACT_ROOT", "LiveRosterWorkflow"]
