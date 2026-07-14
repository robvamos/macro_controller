"""Contratto supervisionato per osservare il roster dalla UI del gioco."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Protocol
import uuid

from doomsday.intelligence.evidence import ProviderContribution
from doomsday.config import DEFAULT_STAT_VALUES
from doomsday.ocr.hero_extractor import analyze_ocr_text
from doomsday.ocr.field_mapping import canonicalize_ocr_fields
from doomsday.vision.desktop_capture import assess_frame_quality
from doomsday.vision.window_capture import find_window, screenshot_window_native


class CaptureMethod(str, Enum):
    NATIVE_WIN32 = "native_win32"
    BLUESTACKS_ADB = "bluestacks_adb"
    MANUAL_SCREENSHOT = "manual_screenshot"


class CaptureStage(str, Enum):
    HERO_LIST = "hero_list"
    HERO_OVERVIEW = "hero_overview"
    HERO_STATS = "hero_stats"
    HERO_SKILLS = "hero_skills"
    HERO_TALENTS = "hero_talents"


@dataclass(frozen=True, slots=True)
class RosterCaptureTarget:
    stage: CaptureStage
    hero_name: str = ""
    required_fields: tuple[str, ...] = ()
    instructions: str = ""


@dataclass(frozen=True, slots=True)
class RosterObservation:
    hero_id: str
    fields: Mapping[str, Any]
    confidence: float
    observed_at: str
    source_ref: str
    capture_method: CaptureMethod
    game_version: str = ""
    runtime_id: str = ""
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.hero_id:
            raise ValueError("hero_id è obbligatorio.")
        if not self.fields:
            raise ValueError("Una osservazione deve contenere almeno un campo.")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence deve essere compresa tra 0 e 1.")

    def to_contributions(self) -> tuple[ProviderContribution, ...]:
        """Emette campi atomici senza sovrascrivere il roster esistente."""
        return tuple(
            ProviderContribution(
                provider_id=f"game-ui:{self.runtime_id or self.capture_method.value}",
                provider_type="first-party-game-ui",
                subject_id=f"hero:{self.hero_id}",
                field_name=field_name,
                field_value=value,
                confidence=self.confidence,
                observed_at=self.observed_at,
                source_ref=self.source_ref,
                trust_score=0.95,
                game_version=self.game_version,
                normalization_notes=self.notes,
                metadata={"capture_method": self.capture_method.value},
            )
            for field_name, value in self.fields.items()
        )


@dataclass(slots=True)
class RosterCaptureSession:
    runtime_id: str
    capture_method: CaptureMethod
    game_version: str = ""
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    observations: list[RosterObservation] = field(default_factory=list)

    def add_observation(self, observation: RosterObservation) -> None:
        if observation.runtime_id and observation.runtime_id != self.runtime_id:
            raise ValueError("L'osservazione appartiene a un runtime diverso.")
        if observation.capture_method != self.capture_method:
            raise ValueError("Il metodo di cattura non coincide con la sessione.")
        self.observations.append(observation)

    def contributions(self) -> tuple[ProviderContribution, ...]:
        return tuple(
            contribution
            for observation in self.observations
            for contribution in observation.to_contributions()
        )


class GameRosterCaptureProvider(Protocol):
    runtime_id: str
    capture_method: CaptureMethod

    def capture_frame(self): ...


class NativeWindowCaptureProvider:
    """Provider read-only per una finestra Doomsday già aperta e visibile."""

    runtime_id = "native-windows"
    capture_method = CaptureMethod.NATIVE_WIN32

    def __init__(self, *, title_prefix: str = "Doomsday") -> None:
        self.title_prefix = title_prefix

    def capture_frame(self):
        window = find_window(self.title_prefix)
        if window is None:
            raise RuntimeError("Finestra Doomsday non trovata.")
        frame = screenshot_window_native(window)
        quality = assess_frame_quality(frame)
        if not quality.valid:
            raise RuntimeError(quality.reason)
        return frame


class LiveRosterAcquisitionService:
    """Orchestra catture esplicite; non effettua click o navigazione autonoma."""

    def capture_supervised_frame(
        self,
        provider: GameRosterCaptureProvider,
        *,
        destination: str | Path,
    ) -> Path:
        frame = provider.capture_frame()
        output = Path(destination)
        output.parent.mkdir(parents=True, exist_ok=True)
        frame.save(output, format="PNG")
        return output

    def observation_from_ocr_text(
        self,
        *,
        hero_id: str,
        ocr_text: str,
        source_ref: str,
        capture_method: CaptureMethod,
        runtime_id: str,
        game_version: str = "",
        observed_at: str | None = None,
    ) -> RosterObservation:
        """Normalizza OCR esistente scartando i valori di default non osservati."""
        parsed, defaults_used = analyze_ocr_text(ocr_text)
        parsed = canonicalize_ocr_fields(parsed)
        fields = {
            key: value
            for key, value in parsed.items()
            if key not in DEFAULT_STAT_VALUES
            or value != DEFAULT_STAT_VALUES[key]
            or (isinstance(value, list) and bool(value))
        }
        fields = {key: value for key, value in fields.items() if value not in ("", [], None)}
        if not fields:
            raise ValueError("L'OCR non contiene dati roster affidabili.")
        confidence = max(0.35, 0.9 - min(defaults_used, 8) * 0.06)
        return RosterObservation(
            hero_id=hero_id,
            fields=fields,
            confidence=round(confidence, 2),
            observed_at=observed_at or datetime.now(timezone.utc).isoformat(),
            source_ref=source_ref,
            capture_method=capture_method,
            game_version=game_version,
            runtime_id=runtime_id,
            notes=("normalizzato da OCR della UI di gioco",),
        )


DEFAULT_CAPTURE_SEQUENCE = (
    RosterCaptureTarget(
        CaptureStage.HERO_LIST,
        required_fields=("owned", "hero_name"),
        instructions="Apri Eroe e mostra la griglia senza popup sovrapposti.",
    ),
    RosterCaptureTarget(
        CaptureStage.HERO_OVERVIEW,
        required_fields=("level", "stars", "rarity", "squad_type"),
        instructions="Apri il profilo dell'eroe selezionato.",
    ),
    RosterCaptureTarget(
        CaptureStage.HERO_STATS,
        required_fields=("ATK", "DEF", "HP", "SPD"),
        instructions="Mostra il pannello statistiche completo.",
    ),
    RosterCaptureTarget(
        CaptureStage.HERO_SKILLS,
        required_fields=("skills", "skill_levels"),
        instructions="Mostra abilità e livelli senza tooltip sovrapposti.",
    ),
    RosterCaptureTarget(
        CaptureStage.HERO_TALENTS,
        required_fields=("talents",),
        instructions="Mostra la pagina talenti dell'eroe.",
    ),
)


__all__ = [
    "CaptureMethod",
    "CaptureStage",
    "DEFAULT_CAPTURE_SEQUENCE",
    "GameRosterCaptureProvider",
    "LiveRosterAcquisitionService",
    "NativeWindowCaptureProvider",
    "RosterCaptureSession",
    "RosterCaptureTarget",
    "RosterObservation",
]
