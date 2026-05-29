from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, median

import numpy as np


@dataclass
class BpmWindow:
    start_sec: float
    end_sec: float
    bpm: float
    confidence: float
    energy: float


@dataclass
class PreprocessingAnalysis:
    sample_name: str
    sample_rate: int
    duration_sec: float
    dominant_bpm: float
    bpm_stability_score: float
    recognizable_pattern_score: float
    correction_readiness_score: float
    onset_density: float
    windows: list[BpmWindow]
    merged_segments: list[dict]


class PreprocessingPipelineService:
    def preprocess_audio(self, audio: np.ndarray, sample_rate: int) -> tuple[np.ndarray, np.ndarray]:
        if audio.size == 0:
            return np.array([], dtype=np.float32), np.array([], dtype=np.float32)

        signal = np.asarray(audio, dtype=np.float32)
        signal = signal - float(np.mean(signal))
        peak = float(np.max(np.abs(signal))) if signal.size else 1.0
        if peak > 0:
            signal = signal / peak

        # High-pass semplice tramite differenza prima per mettere in evidenza onset/transienti.
        high_pass = np.diff(signal, prepend=signal[0])
        rectified = np.abs(high_pass)

        smoothing_samples = max(8, int(sample_rate * 0.02))
        kernel = np.ones(smoothing_samples, dtype=np.float32) / smoothing_samples
        envelope = np.convolve(rectified, kernel, mode="same").astype(np.float32)
        return signal, envelope

    def _estimate_bpm_for_window(self, envelope: np.ndarray, sample_rate: int) -> tuple[float, float]:
        if envelope.size < sample_rate:
            return 0.0, 0.0

        min_bpm = 60.0
        max_bpm = 180.0
        min_lag = int(sample_rate * 60.0 / max_bpm)
        max_lag = int(sample_rate * 60.0 / min_bpm)
        centered = envelope - float(np.mean(envelope))
        autocorr = np.correlate(centered, centered, mode="full")[len(centered) - 1 :]
        autocorr[:min_lag] = 0.0
        if max_lag < len(autocorr):
            autocorr[max_lag + 1 :] = 0.0

        best_lag = int(np.argmax(autocorr))
        best_value = float(autocorr[best_lag]) if best_lag > 0 else 0.0
        if best_lag <= 0 or best_value <= 0:
            return 0.0, 0.0

        bpm = 60.0 * sample_rate / float(best_lag)
        confidence = best_value / (float(np.max(autocorr)) + 1e-6)
        return round(bpm, 2), round(min(max(confidence, 0.0), 1.0), 3)

    def analyze_bpm_windows(
        self,
        *,
        sample_name: str,
        audio: np.ndarray,
        sample_rate: int,
        window_sec: float = 8.0,
        hop_sec: float = 4.0,
    ) -> PreprocessingAnalysis:
        signal, envelope = self.preprocess_audio(audio, sample_rate)
        duration_sec = len(signal) / float(sample_rate) if sample_rate else 0.0
        if signal.size == 0:
            return PreprocessingAnalysis(
                sample_name=sample_name,
                sample_rate=sample_rate,
                duration_sec=0.0,
                dominant_bpm=0.0,
                bpm_stability_score=0.0,
                recognizable_pattern_score=0.0,
                correction_readiness_score=0.0,
                onset_density=0.0,
                windows=[],
                merged_segments=[],
            )

        window_samples = max(sample_rate, int(window_sec * sample_rate))
        hop_samples = max(int(hop_sec * sample_rate), 1)
        windows: list[BpmWindow] = []

        for start in range(0, max(1, len(signal) - window_samples + 1), hop_samples):
            end = min(len(signal), start + window_samples)
            envelope_slice = envelope[start:end]
            bpm, confidence = self._estimate_bpm_for_window(envelope_slice, sample_rate)
            energy = float(np.mean(np.abs(envelope_slice))) if envelope_slice.size else 0.0
            windows.append(
                BpmWindow(
                    start_sec=round(start / sample_rate, 3),
                    end_sec=round(end / sample_rate, 3),
                    bpm=bpm,
                    confidence=confidence,
                    energy=round(energy, 4),
                )
            )

        valid_bpms = [item.bpm for item in windows if item.bpm > 0]
        dominant_bpm = round(float(median(valid_bpms)), 2) if valid_bpms else 0.0
        bpm_spread = mean(abs(item.bpm - dominant_bpm) for item in windows if item.bpm > 0) if valid_bpms else 999.0
        bpm_stability_score = round(max(0.0, 100.0 - bpm_spread * 2.5), 1) if valid_bpms else 0.0
        recognizable_pattern_score = round(mean(item.confidence for item in windows) * 100.0, 1) if windows else 0.0

        onset_threshold = float(np.mean(envelope) + np.std(envelope))
        onset_hits = int(np.sum(envelope > onset_threshold))
        onset_density = round(onset_hits / max(len(envelope), 1), 4)

        correction_readiness_score = round(
            min(
                100.0,
                recognizable_pattern_score * 0.6 + bpm_stability_score * 0.4 + min(onset_density * 600.0, 20.0),
            ),
            1,
        )

        merged_segments = self.merge_windows_to_segments(windows)
        return PreprocessingAnalysis(
            sample_name=sample_name,
            sample_rate=sample_rate,
            duration_sec=round(duration_sec, 3),
            dominant_bpm=dominant_bpm,
            bpm_stability_score=bpm_stability_score,
            recognizable_pattern_score=recognizable_pattern_score,
            correction_readiness_score=correction_readiness_score,
            onset_density=onset_density,
            windows=windows,
            merged_segments=merged_segments,
        )

    def merge_windows_to_segments(self, windows: list[BpmWindow], bpm_tolerance: float = 3.0) -> list[dict]:
        if not windows:
            return []
        merged: list[dict] = []
        current = None
        for window in windows:
            if window.bpm <= 0:
                continue
            if current is None:
                current = {
                    "label": f"detected_{int(round(window.bpm))}",
                    "kind": "detected_tempo",
                    "start_sec": window.start_sec,
                    "end_sec": window.end_sec,
                    "duration_sec": round(window.end_sec - window.start_sec, 3),
                    "bpm": round(window.bpm, 2),
                    "expected_detection": True,
                    "confidence": window.confidence,
                }
                continue

            if abs(current["bpm"] - window.bpm) <= bpm_tolerance:
                current["end_sec"] = window.end_sec
                current["duration_sec"] = round(current["end_sec"] - current["start_sec"], 3)
                current["bpm"] = round((current["bpm"] + window.bpm) / 2.0, 2)
                current["confidence"] = round((current["confidence"] + window.confidence) / 2.0, 3)
            else:
                merged.append(current)
                current = {
                    "label": f"detected_{int(round(window.bpm))}",
                    "kind": "detected_tempo",
                    "start_sec": window.start_sec,
                    "end_sec": window.end_sec,
                    "duration_sec": round(window.end_sec - window.start_sec, 3),
                    "bpm": round(window.bpm, 2),
                    "expected_detection": True,
                    "confidence": window.confidence,
                }
        if current is not None:
            merged.append(current)
        return merged
