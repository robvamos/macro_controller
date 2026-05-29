from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ConvergenceProfile:
    stage: str
    confidence_pct: float
    subtlety_pct: float
    output_intensity_pct: float
    component_complexity_pct: float
    effect_depth_pct: float
    reaction_mode: str
    should_expand_components: bool
    should_enable_effects: bool
    rationale: str


class MusicalConvergenceService:
    """Decide quanto il sistema debba diventare significativo senza essere invasivo all'inizio."""

    def build_profile(
        self,
        *,
        recognizable_pattern_score: float,
        bpm_stability_score: float,
        correction_readiness_score: float,
        target_lock_pct: float,
        beat_one_accuracy_pct: float,
        resync_count: int,
    ) -> ConvergenceProfile:
        confidence_pct = self._compute_confidence(
            recognizable_pattern_score=recognizable_pattern_score,
            bpm_stability_score=bpm_stability_score,
            correction_readiness_score=correction_readiness_score,
            target_lock_pct=target_lock_pct,
            beat_one_accuracy_pct=beat_one_accuracy_pct,
            resync_count=resync_count,
        )

        if confidence_pct < 35.0:
            stage = "listening"
            reaction_mode = "non_invasive"
            subtlety_pct = 92.0
            output_intensity_pct = 8.0
            component_complexity_pct = 5.0
            effect_depth_pct = 0.0
            rationale = "Il pattern non è ancora abbastanza stabile: il sistema deve ascoltare e restare leggero."
        elif confidence_pct < 60.0:
            stage = "aligning"
            reaction_mode = "guarded"
            subtlety_pct = 72.0
            output_intensity_pct = 24.0
            component_complexity_pct = 18.0
            effect_depth_pct = 6.0
            rationale = "Il tempo sta convergendo ma non è ancora il momento di diventare troppo presente."
        elif confidence_pct < 80.0:
            stage = "supporting"
            reaction_mode = "supportive"
            subtlety_pct = 46.0
            output_intensity_pct = 48.0
            component_complexity_pct = 42.0
            effect_depth_pct = 18.0
            rationale = "La convergenza è buona: il sistema può iniziare a sostenere in modo riconoscibile."
        else:
            stage = "assertive"
            reaction_mode = "confident"
            subtlety_pct = 18.0
            output_intensity_pct = 74.0
            component_complexity_pct = 68.0
            effect_depth_pct = 34.0
            rationale = "La confidenza è alta: il sistema può usare più presenza e componenti senza sbilanciarsi."

        return ConvergenceProfile(
            stage=stage,
            confidence_pct=round(confidence_pct, 1),
            subtlety_pct=subtlety_pct,
            output_intensity_pct=output_intensity_pct,
            component_complexity_pct=component_complexity_pct,
            effect_depth_pct=effect_depth_pct,
            reaction_mode=reaction_mode,
            should_expand_components=component_complexity_pct >= 40.0,
            should_enable_effects=effect_depth_pct >= 15.0,
            rationale=rationale,
        )

    def _compute_confidence(
        self,
        *,
        recognizable_pattern_score: float,
        bpm_stability_score: float,
        correction_readiness_score: float,
        target_lock_pct: float,
        beat_one_accuracy_pct: float,
        resync_count: int,
    ) -> float:
        base = (
            recognizable_pattern_score * 0.22
            + bpm_stability_score * 0.24
            + correction_readiness_score * 0.20
            + target_lock_pct * 0.20
            + beat_one_accuracy_pct * 0.14
        )
        penalty = min(20.0, resync_count * 4.0)
        return max(0.0, min(100.0, base - penalty))
