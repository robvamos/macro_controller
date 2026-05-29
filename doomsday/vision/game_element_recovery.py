"""Primitive per cercare elementi grafici di recovery nella finestra di gioco."""

from __future__ import annotations

from dataclasses import dataclass

from game_elements import blob_to_image
from repositories.game_element_repository import get_game_element_by_name


@dataclass(slots=True)
class GameElementMatch:
    element_name: str
    score: float
    location: tuple[int, int]
    size: tuple[int, int]
    center: tuple[int, int]
    scale: float


@dataclass(slots=True)
class GameScreenElementSearchResult:
    requested_elements: tuple[str, ...]
    found: bool
    expected_presence: bool
    condition_satisfied: bool
    matched_element_name: str | None
    score: float | None
    center: tuple[int, int] | None
    location: tuple[int, int] | None
    size: tuple[int, int] | None
    scale: float | None
    threshold: float
    window_rect: tuple[int, int, int, int]


def load_game_element_template_by_name(element_name: str):
    """Carica un elemento grafico dal catalogo e lo converte in template grayscale."""
    element = get_game_element_by_name(element_name)
    if not element:
        return None

    image = blob_to_image(element["immagine"], element["formato_immagine"])
    try:
        return _to_cv_grayscale(image)
    finally:
        close_fn = getattr(image, "close", None)
        if callable(close_fn):
            close_fn()


def capture_window_for_matching(window_rect):
    """Cattura l'intera area client della finestra per il template matching."""
    try:
        from doomsday.vision.click_context_guard import _capture_context_image_win32
    except ImportError as exc:
        raise RuntimeError("Cattura nativa non disponibile per il matching.") from exc

    left, top, right, bottom = window_rect
    return _capture_context_image_win32(left, top, right, bottom)


def find_game_element_match(element_name, window_rect, *, threshold=0.85, scales=None):
    """Cerca un elemento grafico catalogato nella finestra target."""
    template_gray = load_game_element_template_by_name(element_name)
    if template_gray is None:
        return None

    if scales is None:
        scales = (0.85, 0.925, 1.0, 1.075, 1.15)

    screenshot = capture_window_for_matching(window_rect)
    try:
        screenshot_gray = _to_cv_grayscale(screenshot)
    finally:
        close_fn = getattr(screenshot, "close", None)
        if callable(close_fn):
            close_fn()

    try:
        return find_best_scaled_match(
            element_name,
            template_gray,
            screenshot_gray,
            window_rect=window_rect,
            threshold=threshold,
            scales=scales,
        )
    finally:
        _release_cv_image(template_gray)
        _release_cv_image(screenshot_gray)


def search_game_window_elements(window_rect, *, element_names, threshold=0.85, scales=None, expected_presence=True):
    """Ricerca uno o più elementi nell'intera finestra e restituisce un risultato comune riusabile."""
    if isinstance(element_names, str):
        requested_elements = (element_names,)
    else:
        requested_elements = tuple(name for name in (element_names or ()) if name)

    best_match = None
    for element_name in requested_elements:
        match = find_game_element_match(element_name, window_rect, threshold=threshold, scales=scales)
        if match and (best_match is None or match.score > best_match.score):
            best_match = match

    found = best_match is not None
    condition_satisfied = found if expected_presence else not found
    return GameScreenElementSearchResult(
        requested_elements=requested_elements,
        found=found,
        expected_presence=expected_presence,
        condition_satisfied=condition_satisfied,
        matched_element_name=best_match.element_name if best_match else None,
        score=best_match.score if best_match else None,
        center=best_match.center if best_match else None,
        location=best_match.location if best_match else None,
        size=best_match.size if best_match else None,
        scale=best_match.scale if best_match else None,
        threshold=float(threshold),
        window_rect=window_rect,
    )


def find_best_scaled_match(element_name, template_gray, screenshot_gray, *, window_rect, threshold=0.85, scales=None):
    """Esegue il matching provando più scale del template."""
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("opencv-python non disponibile.") from exc

    if scales is None:
        scales = (1.0,)

    best_candidate = None
    for scale in scales:
        scaled_template = _resize_template(template_gray, scale)
        if scaled_template is None:
            continue
        try:
            match = _find_best_match_cv(scaled_template, screenshot_gray)
        finally:
            _release_cv_image(scaled_template)
        if match is None:
            continue
        score, location, width, height = match
        if score < threshold:
            continue
        if best_candidate is None or score > best_candidate.score:
            left, top, _, _ = window_rect
            center_x = left + location[0] + (width // 2)
            center_y = top + location[1] + (height // 2)
            best_candidate = GameElementMatch(
                element_name=element_name,
                score=score,
                location=(left + location[0], top + location[1]),
                size=(width, height),
                center=(center_x, center_y),
                scale=float(scale),
            )
    return best_candidate


def _find_best_match_cv(template_gray, screenshot_gray):
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("opencv-python non disponibile.") from exc

    if template_gray is None or screenshot_gray is None:
        return None

    template_height, template_width = template_gray.shape[:2]
    screenshot_height, screenshot_width = screenshot_gray.shape[:2]
    if template_width > screenshot_width or template_height > screenshot_height:
        return None

    result = cv2.matchTemplate(screenshot_gray, template_gray, cv2.TM_CCOEFF_NORMED)
    _, max_value, _, max_location = cv2.minMaxLoc(result)
    return float(max_value), max_location, int(template_width), int(template_height)


def _resize_template(template_gray, scale):
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("opencv-python non disponibile.") from exc

    if abs(scale - 1.0) < 0.0001:
        return template_gray.copy()

    height, width = template_gray.shape[:2]
    new_width = max(4, int(width * scale))
    new_height = max(4, int(height * scale))
    return cv2.resize(template_gray, (new_width, new_height), interpolation=cv2.INTER_LINEAR)


def _to_cv_grayscale(image):
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise RuntimeError("Dipendenze immagine non disponibili.") from exc

    rgb_image = image.convert("RGB")
    rgb_array = np.array(rgb_image)
    return cv2.cvtColor(rgb_array, cv2.COLOR_RGB2GRAY)


def _release_cv_image(image):
    close_fn = getattr(image, "close", None)
    if callable(close_fn):
        close_fn()
