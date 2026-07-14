"""Guardia visiva leggera per validare il contesto attorno ai click macro."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(slots=True)
class ClickContextGuardConfig:
    enabled: bool = True
    radius_px: int = 48
    resize_px: int = 32
    min_similarity: float = 0.8
    stop_on_mismatch: bool = True
    max_reference_images: int = 3
    translation_tolerance_px: int = 2


def capture_context_image(abs_x, abs_y, *, screen_bounds=None, radius_px=48):
    """Cattura un riquadro attorno al punto indicato."""
    left = int(abs_x - radius_px)
    top = int(abs_y - radius_px)
    right = int(abs_x + radius_px)
    bottom = int(abs_y + radius_px)

    if screen_bounds:
        screen_left, screen_top, screen_right, screen_bottom = screen_bounds
        left = max(screen_left, left)
        top = max(screen_top, top)
        right = min(screen_right, right)
        bottom = min(screen_bottom, bottom)

    if right <= left or bottom <= top:
        raise ValueError("Area di cattura non valida per il controllo visivo del click.")

    try:
        return _capture_context_image_win32(left, top, right, bottom)
    except Exception:
        return _capture_context_image_pillow(left, top, right, bottom)


def _capture_context_image_pillow(left, top, right, bottom):
    try:
        from PIL import ImageGrab
    except ImportError as exc:
        raise RuntimeError("Pillow non disponibile per la guardia visiva dei click.") from exc

    return ImageGrab.grab(bbox=(left, top, right, bottom))


def _capture_context_image_win32(left, top, right, bottom):
    # Wrapper mantenuto per compatibilità con i test e i consumer storici.
    from doomsday.vision.desktop_capture import capture_screen_region

    return capture_screen_region(left, top, right, bottom)


def normalize_context_image(image, resize_px=32):
    """Riduce l'immagine a una forma comparabile e robusta."""
    try:
        from PIL import ImageFilter, ImageOps
    except ImportError as exc:
        raise RuntimeError("Pillow non disponibile per la normalizzazione dell'immagine.") from exc

    normalized = ImageOps.grayscale(image)
    normalized = ImageOps.autocontrast(normalized)
    normalized = normalized.filter(ImageFilter.GaussianBlur(radius=1.2))
    return normalized.resize((resize_px, resize_px))


def _iter_shifted_candidates(image, tolerance_px) -> Iterable:
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Pillow non disponibile per lo shift tollerante.") from exc

    if tolerance_px <= 0:
        yield image
        return

    width, height = image.size
    for offset_x in range(-tolerance_px, tolerance_px + 1):
        for offset_y in range(-tolerance_px, tolerance_px + 1):
            yield image.transform(
                (width, height),
                method=Image.AFFINE,
                data=(1, 0, offset_x, 0, 1, offset_y),
            )


def _compute_single_similarity(reference_image, candidate_image):
    reference_pixels = reference_image.tobytes()
    candidate_pixels = candidate_image.tobytes()
    if len(reference_pixels) != len(candidate_pixels):
        raise ValueError("Le immagini normalizzate non hanno la stessa dimensione.")

    mean_abs_diff = sum(abs(int(a) - int(b)) for a, b in zip(reference_pixels, candidate_pixels)) / len(reference_pixels)
    return max(0.0, 1.0 - (mean_abs_diff / 255.0))


def _compute_histogram_similarity(reference_image, candidate_image):
    reference_histogram = reference_image.histogram()
    candidate_histogram = candidate_image.histogram()
    total_reference = max(1, sum(reference_histogram))
    total_candidate = max(1, sum(candidate_histogram))

    distance = 0.0
    for ref_value, cand_value in zip(reference_histogram, candidate_histogram):
        distance += abs((ref_value / total_reference) - (cand_value / total_candidate))
    return max(0.0, 1.0 - min(1.0, distance / 2.0))


def _compute_edge_similarity(reference_image, candidate_image):
    try:
        from PIL import ImageFilter
    except ImportError as exc:
        raise RuntimeError("Pillow non disponibile per il confronto edge.") from exc

    reference_edges = reference_image.filter(ImageFilter.FIND_EDGES)
    candidate_edges = candidate_image.filter(ImageFilter.FIND_EDGES)
    try:
        return _compute_single_similarity(reference_edges, candidate_edges)
    finally:
        close_image(reference_edges)
        close_image(candidate_edges)


def _combine_similarity_scores(reference_image, candidate_image):
    intensity_score = _compute_single_similarity(reference_image, candidate_image)
    edge_score = _compute_edge_similarity(reference_image, candidate_image)
    histogram_score = _compute_histogram_similarity(reference_image, candidate_image)
    return (
        (intensity_score * 0.60)
        + (edge_score * 0.25)
        + (histogram_score * 0.15)
    )


def compute_context_similarity(reference_image, candidate_image, resize_px=32, translation_tolerance_px=2):
    """Restituisce uno score 0..1 più robusto a micro-shift ma più severo sui contenuti diversi."""
    reference = normalize_context_image(reference_image, resize_px=resize_px)
    candidate = normalize_context_image(candidate_image, resize_px=resize_px)
    try:
        best_score = 0.0
        for shifted_candidate in _iter_shifted_candidates(candidate, translation_tolerance_px):
            best_score = max(best_score, _combine_similarity_scores(reference, shifted_candidate))
        return best_score
    finally:
        close_image(reference)
        close_image(candidate)


class ClickContextGuard:
    """Conserva il riferimento del primo click e valida i successivi."""

    def __init__(self, config: ClickContextGuardConfig | None = None):
        self.config = config or ClickContextGuardConfig()
        self.reference_images = []
        self.reference_position = None
        self.fixed_reference_mode = False

    def reset(self):
        """Cancella lo stato precedente mantenendo tutto in memoria volatile."""
        for reference_image in self.reference_images:
            close_image(reference_image)
        self.reference_images = []
        self.reference_position = None
        self.fixed_reference_mode = False

    def has_reference(self):
        return bool(self.reference_images)

    def set_reference_image(self, image, *, abs_x=None, abs_y=None):
        """Imposta un riferimento fisso, senza farlo evolvere durante il playback."""
        if image is None:
            raise ValueError("Immagine di riferimento non valida.")
        self.reset()
        self.add_reference_image(image, abs_x=abs_x, abs_y=abs_y)
        self.fixed_reference_mode = True

    def add_reference_image(self, image, *, abs_x=None, abs_y=None):
        """Aggiunge un riferimento alternativo mantenendo il confronto sullo stesso contesto."""
        if image is None:
            raise ValueError("Immagine di riferimento alternativa non valida.")
        if not self.reference_images and abs_x is not None and abs_y is not None:
            self.reference_position = (abs_x, abs_y)
        self.reference_images.append(image.copy())
        while len(self.reference_images) > self.config.max_reference_images:
            oldest = self.reference_images.pop(0)
            close_image(oldest)

    def freeze_current_reference(self):
        """Congela il riferimento gia' acquisito, impedendo che venga aggiornato nei loop successivi."""
        if self.reference_images:
            self.fixed_reference_mode = True

    def prime_reference(self, abs_x, abs_y, *, screen_bounds=None):
        reference_image = capture_context_image(
            abs_x,
            abs_y,
            screen_bounds=screen_bounds,
            radius_px=self.config.radius_px,
        )
        if not self.reference_images:
            self.reference_position = (abs_x, abs_y)
        self.reference_images.append(reference_image)
        while len(self.reference_images) > self.config.max_reference_images:
            oldest = self.reference_images.pop(0)
            close_image(oldest)
        return reference_image

    def _emit_preview_callback(self, preview_callback, *, reference_preview, candidate_preview, score=None):
        """Invia subito il contesto catturato alla UI, anche prima del punteggio finale."""
        if preview_callback is None:
            return

        preview_callback(
            {
                "reference_preview": reference_preview.copy() if reference_preview is not None else None,
                "candidate_preview": candidate_preview.copy() if candidate_preview is not None else None,
                "score": score,
                "threshold": self.config.min_similarity,
            }
        )

    def verify_or_prime(self, abs_x, abs_y, *, screen_bounds=None, preview_callback=None):
        if not self.config.enabled:
            return {
                "ok": True,
                "primed": False,
                "score": 1.0,
                "threshold": self.config.min_similarity,
            }

        if not self.reference_images:
            reference_image = self.prime_reference(abs_x, abs_y, screen_bounds=screen_bounds)
            if reference_image is None and self.reference_images:
                reference_image = self.reference_images[-1]
            return {
                "ok": True,
                "primed": True,
                "score": 1.0,
                "threshold": self.config.min_similarity,
                "reference_preview": reference_image.copy(),
                "candidate_preview": reference_image.copy(),
            }

        candidate_image = capture_context_image(
            abs_x,
            abs_y,
            screen_bounds=screen_bounds,
            radius_px=self.config.radius_px,
        )
        try:
            last_reference_image = self.reference_images[-1] if self.reference_images else None
            if last_reference_image is not None:
                self._emit_preview_callback(
                    preview_callback,
                    reference_preview=last_reference_image,
                    candidate_preview=candidate_image,
                    score=None,
                )

            best_reference_image = None
            best_score = 0.0
            for reference_image in self.reference_images:
                score = compute_context_similarity(
                    reference_image,
                    candidate_image,
                    resize_px=self.config.resize_px,
                    translation_tolerance_px=self.config.translation_tolerance_px,
                )
                if score >= best_score:
                    best_score = score
                    best_reference_image = reference_image

            reference_preview = best_reference_image.copy() if best_reference_image is not None else None
            candidate_preview = candidate_image.copy()

            accepted = best_score >= self.config.min_similarity
            if accepted and not self.fixed_reference_mode and len(self.reference_images) < self.config.max_reference_images:
                self.prime_reference(abs_x, abs_y, screen_bounds=screen_bounds)

            score = max(
                [best_score]
            )
            return {
                "ok": accepted,
                "primed": False,
                "score": score,
                "threshold": self.config.min_similarity,
                "reference_preview": reference_preview,
                "candidate_preview": candidate_preview,
            }
        finally:
            close_image(candidate_image)


def close_image(image):
    """Rilascia un'immagine PIL se supporta la chiusura esplicita."""
    close_fn = getattr(image, "close", None)
    if callable(close_fn):
        close_fn()
