from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from core.paths import DATA_DIR, ensure_project_directories


LEARNING_DIR = DATA_DIR / "learning"
EVALUATIONS_PATH = LEARNING_DIR / "config_evaluations.json"


class LearningConfigurationService:
    def __init__(self, evaluations_path: Path | None = None) -> None:
        self.evaluations_path = evaluations_path or EVALUATIONS_PATH

    def _ensure_storage(self) -> None:
        ensure_project_directories()
        self.evaluations_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.evaluations_path.exists():
            self.evaluations_path.write_text(json.dumps({"evaluations": []}, indent=2), encoding="utf-8")

    def load_evaluations(self) -> list[dict]:
        self._ensure_storage()
        payload = json.loads(self.evaluations_path.read_text(encoding="utf-8"))
        return payload.get("evaluations", [])

    def save_evaluations(self, evaluations: list[dict]) -> None:
        self._ensure_storage()
        self.evaluations_path.write_text(
            json.dumps({"evaluations": evaluations}, indent=2),
            encoding="utf-8",
        )

    def build_configuration_snapshot(
        self,
        *,
        sample_name: str,
        analysis,
        learning_summary: dict,
    ) -> dict:
        profile = learning_summary["convergence_profile"]
        return {
            "sample_name": sample_name,
            "dominant_bpm": getattr(analysis, "dominant_bpm", 0.0),
            "bpm_stability_score": getattr(analysis, "bpm_stability_score", 0.0),
            "recognizable_pattern_score": getattr(analysis, "recognizable_pattern_score", 0.0),
            "correction_readiness_score": getattr(analysis, "correction_readiness_score", 0.0),
            "target_lock_pct": learning_summary.get("target_lock_pct", 0.0),
            "beat_one_accuracy_pct": learning_summary.get("beat_one_accuracy_pct", 0.0),
            "resync_count": learning_summary.get("resync_count", 0),
            "convergence_stage": profile.stage,
            "output_intensity_pct": profile.output_intensity_pct,
            "component_complexity_pct": profile.component_complexity_pct,
            "effect_depth_pct": profile.effect_depth_pct,
        }

    def save_evaluation(
        self,
        *,
        sample_name: str,
        configuration_snapshot: dict,
        rating: str,
        note: str,
    ) -> dict:
        evaluations = self.load_evaluations()
        entry = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "sample_name": sample_name,
            "rating": rating,
            "note": note.strip(),
            "configuration": configuration_snapshot,
        }
        evaluations.append(entry)
        self.save_evaluations(evaluations)
        return entry

    def list_evaluations_for_sample(self, sample_name: str) -> list[dict]:
        return [item for item in self.load_evaluations() if item.get("sample_name") == sample_name]

    def recommend_for_sample(self, sample_name: str) -> str:
        evaluations = self.list_evaluations_for_sample(sample_name)
        if not evaluations:
            return "Nessuna valutazione ancora salvata per questo campione."

        score_map = {"scarso": 1, "debole": 2, "buono": 3, "ottimo": 4}
        average = sum(score_map.get(item["rating"], 0) for item in evaluations) / max(len(evaluations), 1)
        latest = evaluations[-1]
        latest_stage = latest["configuration"].get("convergence_stage", "-")
        if average >= 3.5:
            return f"Configurazione storicamente forte. Ultimo stage valido: {latest_stage}."
        if average >= 2.5:
            return f"Configurazione promettente ma non ancora stabile. Ultimo stage: {latest_stage}."
        return f"Configurazione ancora fragile. Conviene tenerla discreta e raccogliere altre valutazioni. Ultimo stage: {latest_stage}."

    def build_evaluation_prompt(self, sample_name: str, summary: dict) -> str:
        profile = summary["convergence_profile"]
        return (
            f"Valuta la configurazione corrente per {sample_name}: "
            f"stage {profile.stage}, lock {summary.get('target_lock_pct', 0.0)}%, "
            f"beat 1 {summary.get('beat_one_accuracy_pct', 0.0)}%."
        )
