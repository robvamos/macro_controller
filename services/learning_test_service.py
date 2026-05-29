from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean

from services.musical_convergence_service import ConvergenceProfile, MusicalConvergenceService


@dataclass
class LearningGridBeat:
    sample_name: str
    segment_label: str
    beat_number: int
    beat_in_bar: int
    start_sec: float
    end_sec: float
    target_sec: float
    bpm: float | None
    weight: float
    phase_tolerance_ms: float


@dataclass
class LearningObservation:
    beat_number: int
    beat_in_bar: int
    offset_ms: float
    confidence: float
    is_fast: bool
    within_tolerance: bool


@dataclass
class LearningSession:
    sample_name: str
    target_segments: list[dict]
    grid: list[LearningGridBeat]
    current_grid_index: int = 0
    observations: list[LearningObservation] = field(default_factory=list)
    feedback_log: list[str] = field(default_factory=list)
    resync_count: int = 0
    cut_bar_count: int = 0
    status: str = "ready"


class LearningTestService:
    def __init__(self) -> None:
        self.session: LearningSession | None = None
        self.convergence_service = MusicalConvergenceService()

    def build_learning_grid(self, sample_name: str, payload: dict) -> list[LearningGridBeat]:
        grid: list[LearningGridBeat] = []
        beat_number = 1

        for segment in payload.get("segments", []):
            bpm = segment.get("bpm")
            if not bpm:
                continue

            beat_duration_sec = 60.0 / float(bpm)
            beat_count = max(1, int(round(float(segment["duration_sec"]) / beat_duration_sec)))
            for beat_index in range(beat_count):
                start_sec = float(segment["start_sec"]) + beat_index * beat_duration_sec
                end_sec = min(float(segment["end_sec"]), start_sec + beat_duration_sec)
                beat_in_bar = (beat_index % 4) + 1
                is_bar_one = beat_in_bar == 1
                grid.append(
                    LearningGridBeat(
                        sample_name=sample_name,
                        segment_label=segment["label"],
                        beat_number=beat_number,
                        beat_in_bar=beat_in_bar,
                        start_sec=round(start_sec, 3),
                        end_sec=round(end_sec, 3),
                        target_sec=round(start_sec, 3),
                        bpm=float(bpm),
                        weight=1.7 if is_bar_one else 1.0,
                        phase_tolerance_ms=70.0 if is_bar_one else 110.0,
                    )
                )
                beat_number += 1

        return grid

    def start_session(self, sample_name: str, payload: dict) -> LearningSession:
        grid = self.build_learning_grid(sample_name, payload)
        self.session = LearningSession(
            sample_name=sample_name,
            target_segments=payload.get("segments", []),
            grid=grid,
            status="listening" if grid else "ready",
        )
        return self.session

    def record_observation(self, *, offset_ms: float, confidence: float, observed_beat_in_bar: int) -> LearningObservation:
        if self.session is None or not self.session.grid:
            raise ValueError("Nessuna sessione learning attiva.")

        grid_index = min(self.session.current_grid_index, len(self.session.grid) - 1)
        expected = self.session.grid[grid_index]
        within_tolerance = abs(offset_ms) <= expected.phase_tolerance_ms and observed_beat_in_bar == expected.beat_in_bar
        observation = LearningObservation(
            beat_number=expected.beat_number,
            beat_in_bar=observed_beat_in_bar,
            offset_ms=offset_ms,
            confidence=confidence,
            is_fast=offset_ms < 0,
            within_tolerance=within_tolerance,
        )
        self.session.observations.append(observation)
        self.session.current_grid_index = min(self.session.current_grid_index + 1, len(self.session.grid) - 1)
        self.session.status = "tracking" if within_tolerance else "correcting"
        return observation

    def apply_feedback(self, feedback_code: str) -> None:
        if self.session is None:
            raise ValueError("Nessuna sessione learning attiva.")
        self.session.feedback_log.append(feedback_code)
        if feedback_code in {"too_slow", "too_fast", "late_bar_start"}:
            self.session.status = "correcting"
        elif feedback_code == "good_lock":
            self.session.status = "tracking"

    def reset_sync(self, *, cut_current_bar: bool, reason: str) -> None:
        if self.session is None:
            raise ValueError("Nessuna sessione learning attiva.")
        self.session.resync_count += 1
        if cut_current_bar:
            self.session.cut_bar_count += 1
        self.session.status = f"resync:{reason}"

    def get_summary(
        self,
        *,
        recognizable_pattern_score: float = 0.0,
        bpm_stability_score: float = 0.0,
        correction_readiness_score: float = 0.0,
    ) -> dict:
        if self.session is None:
            return {
                "status": "idle",
                "target_lock_pct": 0.0,
                "average_offset_ms": 0.0,
                "correction_speed": "n/a",
                "last_beat_reaction": "n/a",
                "resync_count": 0,
                "cut_bar_count": 0,
                "beat_one_accuracy_pct": 0.0,
                "convergence_profile": self._build_convergence_profile(
                    recognizable_pattern_score=recognizable_pattern_score,
                    bpm_stability_score=bpm_stability_score,
                    correction_readiness_score=correction_readiness_score,
                    target_lock_pct=0.0,
                    beat_one_accuracy_pct=0.0,
                    resync_count=0,
                ),
            }

        observations = self.session.observations
        if not observations:
            return {
                "status": self.session.status,
                "target_lock_pct": 0.0,
                "average_offset_ms": 0.0,
                "correction_speed": "waiting",
                "last_beat_reaction": "waiting",
                "resync_count": self.session.resync_count,
                "cut_bar_count": self.session.cut_bar_count,
                "beat_one_accuracy_pct": 0.0,
                "convergence_profile": self._build_convergence_profile(
                    recognizable_pattern_score=recognizable_pattern_score,
                    bpm_stability_score=bpm_stability_score,
                    correction_readiness_score=correction_readiness_score,
                    target_lock_pct=0.0,
                    beat_one_accuracy_pct=0.0,
                    resync_count=self.session.resync_count,
                ),
            }

        accurate = [item for item in observations if item.within_tolerance]
        beat_one_hits = [item for item in observations if item.beat_in_bar == 1 and item.within_tolerance]
        beat_one_total = [item for item in observations if item.beat_in_bar == 1]

        recent_window = observations[-4:]
        recent_avg = mean(abs(item.offset_ms) for item in recent_window)
        previous_window = observations[-8:-4]
        previous_avg = mean(abs(item.offset_ms) for item in previous_window) if previous_window else None
        if previous_avg is None:
            correction_speed = "warming_up"
        elif recent_avg < previous_avg * 0.8:
            correction_speed = "fast"
        elif recent_avg < previous_avg:
            correction_speed = "improving"
        else:
            correction_speed = "slow"

        last = observations[-1]
        last_beat_reaction = "fast" if last.is_fast else "slow"
        target_lock_pct = round((len(accurate) / len(observations)) * 100.0, 1)
        beat_one_accuracy_pct = round((len(beat_one_hits) / len(beat_one_total)) * 100.0, 1) if beat_one_total else 0.0
        return {
            "status": self.session.status,
            "target_lock_pct": target_lock_pct,
            "average_offset_ms": round(mean(item.offset_ms for item in observations), 1),
            "correction_speed": correction_speed,
            "last_beat_reaction": last_beat_reaction,
            "resync_count": self.session.resync_count,
            "cut_bar_count": self.session.cut_bar_count,
            "beat_one_accuracy_pct": beat_one_accuracy_pct,
            "current_grid_index": self.session.current_grid_index,
            "grid_size": len(self.session.grid),
            "convergence_profile": self._build_convergence_profile(
                recognizable_pattern_score=recognizable_pattern_score,
                bpm_stability_score=bpm_stability_score,
                correction_readiness_score=correction_readiness_score,
                target_lock_pct=target_lock_pct,
                beat_one_accuracy_pct=beat_one_accuracy_pct,
                resync_count=self.session.resync_count,
            ),
        }

    def _build_convergence_profile(
        self,
        *,
        recognizable_pattern_score: float,
        bpm_stability_score: float,
        correction_readiness_score: float,
        target_lock_pct: float,
        beat_one_accuracy_pct: float,
        resync_count: int,
    ) -> ConvergenceProfile:
        return self.convergence_service.build_profile(
            recognizable_pattern_score=recognizable_pattern_score,
            bpm_stability_score=bpm_stability_score,
            correction_readiness_score=correction_readiness_score,
            target_lock_pct=target_lock_pct,
            beat_one_accuracy_pct=beat_one_accuracy_pct,
            resync_count=resync_count,
        )
