"""Capture and catalogue the UI element under a recorded macro click."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
import re

from doomsday.vision.click_context_guard import compute_context_similarity
from doomsday.vision.click_context_guard import capture_context_image
from doomsday.vision.game_element_recovery import search_game_window_elements
from game_elements import image_to_blob
from game_elements import blob_to_image
from repositories.game_element_repository import create_game_element, get_all_game_elements, update_game_element
from services.game_element_ingestion_service import prepare_game_element_asset


DEFAULT_CLICK_CAPTURE_RADIUS_PX = 112
DEFAULT_CLICK_CAPTURE_HALF_WIDTH_PX = 160
DEFAULT_CLICK_CAPTURE_HALF_HEIGHT_PX = 96
DEFAULT_CONTOUR_PADDING_PX = 8
DEFAULT_DUPLICATE_ELEMENT_SIMILARITY = 0.93
STRUCTURED_METADATA_MARKERS = (
    "AUTO_CLICK_ELEMENT_METADATA:",
    "GENERAL_CLICK_SEMANTIC_NOTE:",
)
DOOMSDAY_GRAPH_ID = "doomsday-default-ui-graph"
UNKNOWN_VIEW_NODE_ID = "unknown_main_view"
REGION_VIEW_NODE_ID = "exterior_region_view"
SHELTER_VIEW_NODE_ID = "shelter_interior_view"
EMPTY_SPACE_DISMISSAL_NODE_ID = "empty_space_popup_dismissal_band_4"


@dataclass(slots=True)
class ClickedElementCrop:
    image: object
    capture_bounds: tuple[int, int, int, int]
    crop_bounds: tuple[int, int, int, int]
    click_offset_in_crop: tuple[int, int]
    contour_confidence: float


@dataclass(slots=True)
class ClickedElementObservation:
    element_id: int
    element_name: str
    graph_id: str
    view_node_id: str
    macro_name: str
    event_time_ms: int | None
    click_position: tuple[int, int]
    normalized_position: tuple[float | None, float | None]
    capture_bounds: tuple[int, int, int, int]
    crop_bounds: tuple[int, int, int, int]
    contour_confidence: float
    reused_existing: bool = False


def classify_doomsday_view(window_rect, *, threshold=0.85) -> str:
    """Infer the current main view from the bottom-left view switch button."""
    search_result = search_game_window_elements(
        window_rect,
        element_names=("region_view_switch_globe_icon", "shelter_view_switch_home_icon"),
        threshold=threshold,
        expected_presence=True,
    )
    if not search_result.found:
        return UNKNOWN_VIEW_NODE_ID
    if search_result.matched_element_name == "region_view_switch_globe_icon":
        return SHELTER_VIEW_NODE_ID
    if search_result.matched_element_name == "shelter_view_switch_home_icon":
        return REGION_VIEW_NODE_ID
    return UNKNOWN_VIEW_NODE_ID


def capture_clicked_element_crop(
    *,
    abs_x,
    abs_y,
    window_rect,
    radius_px=DEFAULT_CLICK_CAPTURE_RADIUS_PX,
    half_width_px=None,
    half_height_px=None,
    contour_padding_px=DEFAULT_CONTOUR_PADDING_PX,
) -> ClickedElementCrop:
    """Capture a broad click context and trim it to the most likely clicked shape."""
    half_width_px = int(half_width_px or DEFAULT_CLICK_CAPTURE_HALF_WIDTH_PX or radius_px)
    half_height_px = int(half_height_px or DEFAULT_CLICK_CAPTURE_HALF_HEIGHT_PX or radius_px)
    left, top, right, bottom = _build_capture_bounds(
        abs_x,
        abs_y,
        window_rect,
        half_width_px=half_width_px,
        half_height_px=half_height_px,
    )
    context_image = _capture_rect_image(left, top, right, bottom)
    try:
        local_click = (int(abs_x - left), int(abs_y - top))
        crop_box, confidence = _find_probable_element_box(
            context_image,
            local_click=local_click,
            padding_px=contour_padding_px,
        )
        cropped = context_image.crop(crop_box)
    finally:
        close_fn = getattr(context_image, "close", None)
        if callable(close_fn):
            close_fn()

    crop_left, crop_top, crop_right, crop_bottom = crop_box
    absolute_crop_bounds = (
        left + crop_left,
        top + crop_top,
        left + crop_right,
        top + crop_bottom,
    )
    click_offset_in_crop = (
        max(0, min(cropped.size[0], int(abs_x - absolute_crop_bounds[0]))),
        max(0, min(cropped.size[1], int(abs_y - absolute_crop_bounds[1]))),
    )
    return ClickedElementCrop(
        image=cropped,
        capture_bounds=(left, top, right, bottom),
        crop_bounds=absolute_crop_bounds,
        click_offset_in_crop=click_offset_in_crop,
        contour_confidence=confidence,
    )


def register_recorded_click_element(
    *,
    macro_name,
    event_time_ms,
    button,
    abs_x,
    abs_y,
    normalized_x=None,
    normalized_y=None,
    window_rect,
    view_node_id=None,
    sequence_index=None,
    previous_element_id=None,
) -> ClickedElementObservation:
    """Persist the clicked visual element and attach semantic graph context in metadata."""
    view_node_id = view_node_id or classify_doomsday_view(window_rect)
    crop = capture_clicked_element_crop(abs_x=abs_x, abs_y=abs_y, window_rect=window_rect)
    try:
        semantic_hint = (
            f"recorded click element; graph={DOOMSDAY_GRAPH_ID}; "
            f"view={view_node_id}; macro={macro_name}"
        )
        asset = prepare_game_element_asset(crop.image, source_format="PNG", semantic_hint=semantic_hint)
        metadata = {
            "source": "macro_recording_click_capture",
            "graph_id": DOOMSDAY_GRAPH_ID,
            "view_node_id": view_node_id,
            "macro_name": macro_name,
            "event_time_ms": event_time_ms,
            "button": button,
            "click_position": {"x": int(abs_x), "y": int(abs_y)},
            "normalized_position": {"x": normalized_x, "y": normalized_y},
            "capture_bounds": _rect_to_dict(crop.capture_bounds),
            "crop_bounds": _rect_to_dict(crop.crop_bounds),
            "stored_size": {"width": asset.stored_size[0], "height": asset.stored_size[1]},
            "click_offset_in_crop": {
                "x": crop.click_offset_in_crop[0],
                "y": crop.click_offset_in_crop[1],
            },
            "contour_confidence": round(crop.contour_confidence, 4),
            "sequence_index": sequence_index,
            "previous_element_id": previous_element_id,
            "sequence_relation": "after_previous_click" if previous_element_id else "sequence_start",
        }
        name = build_recorded_click_element_name(
            macro_name=macro_name,
            event_time_ms=event_time_ms,
            abs_x=abs_x,
            abs_y=abs_y,
        )
        description = build_recorded_click_element_description(metadata)
        element_id, element_name, reused_existing = _find_or_create_game_element(
            base_name=name,
            description=description,
            image=asset.image,
            image_format=asset.storage_format,
        )
    finally:
        close_fn = getattr(crop.image, "close", None)
        if callable(close_fn):
            close_fn()

    return ClickedElementObservation(
        element_id=element_id,
        element_name=element_name,
        graph_id=DOOMSDAY_GRAPH_ID,
        view_node_id=view_node_id,
        macro_name=macro_name,
        event_time_ms=event_time_ms,
        click_position=(int(abs_x), int(abs_y)),
        normalized_position=(normalized_x, normalized_y),
        capture_bounds=crop.capture_bounds,
        crop_bounds=crop.crop_bounds,
        contour_confidence=crop.contour_confidence,
        reused_existing=reused_existing,
    )


def build_recorded_click_element_name(*, macro_name, event_time_ms, abs_x, abs_y) -> str:
    macro_slug = _slugify(macro_name or "macro")
    event_part = "unknown_time" if event_time_ms is None else f"{int(event_time_ms):06d}ms"
    return f"recorded_click_{macro_slug}_{event_part}_{int(abs_x)}x{int(abs_y)}"


def build_recorded_click_element_description(metadata) -> str:
    return (
        "Elemento acquisito automaticamente durante la registrazione macro.\n"
        f"Grafo: {metadata['graph_id']}\n"
        f"Nodo vista stimato: {metadata['view_node_id']}\n"
        f"Macro sorgente: {metadata['macro_name']}\n"
        "AUTO_CLICK_ELEMENT_METADATA:"
        + json.dumps(metadata, ensure_ascii=False, sort_keys=True)
    )


def classify_horizontal_band_from_bottom(normalized_y, *, bands=5):
    """Return a 1-based horizontal band index, counted from the bottom of the screen."""
    if normalized_y is None:
        return None
    try:
        clamped_y = max(0.0, min(0.999999, float(normalized_y)))
    except (TypeError, ValueError):
        return None
    top_based_index = int(clamped_y * bands)
    return bands - top_based_index


def is_empty_space_popup_dismissal_band(normalized_y):
    """Known fallback area: empty click in band 4 from the bottom often dismisses blocking popups."""
    return classify_horizontal_band_from_bottom(normalized_y) == 4


def _capture_rect_image(left, top, right, bottom):
    try:
        from doomsday.vision.click_context_guard import _capture_context_image_win32
        return _capture_context_image_win32(left, top, right, bottom)
    except Exception:
        try:
            from PIL import ImageGrab
        except ImportError as exc:
            raise RuntimeError("Pillow non disponibile per catturare il click.") from exc
        return ImageGrab.grab(bbox=(left, top, right, bottom))


def _build_capture_bounds(abs_x, abs_y, window_rect, *, half_width_px, half_height_px):
    window_left, window_top, window_right, window_bottom = window_rect
    left = max(int(window_left), int(abs_x - half_width_px))
    top = max(int(window_top), int(abs_y - half_height_px))
    right = min(int(window_right), int(abs_x + half_width_px))
    bottom = min(int(window_bottom), int(abs_y + half_height_px))
    if right <= left or bottom <= top:
        raise ValueError("Area di cattura click non valida.")
    return left, top, right, bottom


def _find_probable_element_box(image, *, local_click, padding_px):
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise RuntimeError("opencv-python e numpy sono necessari per ritagliare il click.") from exc

    rgb = image.convert("RGB")
    gray = cv2.cvtColor(np.array(rgb), cv2.COLOR_RGB2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    image_width, image_height = image.size
    click_x, click_y = local_click
    candidates = []
    for radius_x, radius_y in _iter_expanding_windows(image_width, image_height):
        window_box = (
            max(0, click_x - radius_x),
            max(0, click_y - radius_y),
            min(image_width, click_x + radius_x),
            min(image_height, click_y + radius_y),
        )
        x1, y1, x2, y2 = window_box
        roi = blurred[y1:y2, x1:x2]
        if roi.size == 0:
            continue

        background_value = _estimate_background_value(roi)
        contrast_mask = cv2.absdiff(roi, background_value)
        _, contrast_mask = cv2.threshold(contrast_mask, 12, 255, cv2.THRESH_BINARY)
        contrast_kernel = np.ones((5, 13), np.uint8)
        contrast_mask = cv2.morphologyEx(contrast_mask, cv2.MORPH_CLOSE, contrast_kernel, iterations=1)
        _append_contour_candidates(
            candidates,
            contrast_mask,
            origin=(x1, y1),
            local_click=local_click,
            image_size=image.size,
            window_size=(x2 - x1, y2 - y1),
            radius=(radius_x, radius_y),
            padding_px=padding_px,
            source_bonus=0.28,
        )

        edges = cv2.Canny(roi, 35, 110)
        kernel_width = 9 if radius_x > radius_y else 5
        kernel = np.ones((5, kernel_width), np.uint8)
        edges = cv2.dilate(edges, kernel, iterations=1)
        _append_contour_candidates(
            candidates,
            edges,
            origin=(x1, y1),
            local_click=local_click,
            image_size=image.size,
            window_size=(x2 - x1, y2 - y1),
            radius=(radius_x, radius_y),
            padding_px=padding_px,
            source_bonus=0.0,
        )
    if not candidates:
        return _fallback_click_box(image.size, local_click), 0.0

    candidates.sort(reverse=True)
    _, x, y, width, height, contains_click = candidates[0]
    left = max(0, x - padding_px)
    top = max(0, y - padding_px)
    right = min(image_width, x + width + padding_px)
    bottom = min(image_height, y + height + padding_px)
    confidence = 0.85 if contains_click else 0.55
    return (left, top, right, bottom), confidence


def _iter_expanding_windows(image_width, image_height):
    base_windows = (
        (14, 14),
        (22, 18),
        (32, 24),
        (48, 32),
        (68, 42),
        (92, 52),
        (122, 64),
        (155, 78),
    )
    for radius_x, radius_y in base_windows:
        yield min(radius_x, image_width // 2), min(radius_y, image_height // 2)


def _estimate_background_value(roi):
    try:
        import numpy as np
    except ImportError as exc:
        raise RuntimeError("numpy non disponibile.") from exc

    height, width = roi.shape[:2]
    strips = [
        roi[: max(1, height // 10), :],
        roi[-max(1, height // 10) :, :],
        roi[:, : max(1, width // 10)],
        roi[:, -max(1, width // 10) :],
    ]
    border = np.concatenate([strip.reshape(-1) for strip in strips])
    return int(np.median(border))


def _append_contour_candidates(
    candidates,
    mask,
    *,
    origin,
    local_click,
    image_size,
    window_size,
    radius,
    padding_px,
    source_bonus,
):
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("opencv-python non disponibile.") from exc

    x1, y1 = origin
    click_x, click_y = local_click
    image_width, image_height = image_size
    window_width, window_height = window_size
    radius_x, radius_y = radius
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for contour in contours:
        x, y, width, height = cv2.boundingRect(contour)
        area = width * height
        if area < 36 or width < 6 or height < 6:
            continue
        abs_x = x1 + x
        abs_y = y1 + y
        contains_click = (
            abs_x - padding_px <= click_x <= abs_x + width + padding_px
            and abs_y - padding_px <= click_y <= abs_y + height + padding_px
        )
        center_x = abs_x + width / 2.0
        center_y = abs_y + height / 2.0
        distance = math.hypot(center_x - click_x, center_y - click_y)
        max_distance = math.hypot(radius_x, radius_y) or 1.0
        window_area = max(1, window_width * window_height)
        fill_ratio = min(1.0, area / float(window_area))
        shape_bonus = _shape_bonus(width, height)
        text_bonus = _text_like_bonus(width, height, radius_x, radius_y, contains_click)
        size_bonus = min(0.24, math.sqrt(area / float(max(1, image_width * image_height))))
        score = (
            (1.25 if contains_click else 0.35)
            + fill_ratio
            + shape_bonus
            + text_bonus
            + size_bonus
            + source_bonus
            - min(1.0, distance / max_distance)
            - (0.015 * (radius_x + radius_y) / 20.0)
        )
        candidates.append((score, abs_x, abs_y, width, height, contains_click))


def _shape_bonus(width, height):
    ratio = width / float(max(1, height))
    if 0.6 <= ratio <= 1.8:
        return 0.16
    if 1.8 < ratio <= 6.5:
        return 0.10
    return 0.0


def _text_like_bonus(width, height, radius_x, radius_y, contains_click):
    ratio = width / float(max(1, height))
    if ratio >= 2.2 and radius_x >= 48 and height <= radius_y * 1.2:
        return 0.5 if contains_click else 0.24
    return 0.0


def _fallback_click_box(image_size, local_click, fallback_radius=48):
    image_width, image_height = image_size
    click_x, click_y = local_click
    return (
        max(0, int(click_x - fallback_radius)),
        max(0, int(click_y - fallback_radius)),
        min(image_width, int(click_x + fallback_radius)),
        min(image_height, int(click_y + fallback_radius)),
    )


def _create_unique_game_element(base_name, description, image_blob, image_format):
    candidate = base_name
    suffix = 2
    while True:
        try:
            return create_game_element(candidate, description, image_blob, image_format)
        except ValueError as exc:
            if "esiste" not in str(exc):
                raise
            candidate = f"{base_name}_{suffix}"
            suffix += 1


def _find_or_create_game_element(*, base_name, description, image, image_format):
    matched_element = _find_matching_game_element(image)
    if matched_element is not None:
        merged_description = _merge_game_element_descriptions(
            matched_element.get("descrizione"),
            description,
        )
        if merged_description != (matched_element.get("descrizione") or ""):
            update_game_element(matched_element["id"], descrizione=merged_description)
        return int(matched_element["id"]), matched_element["nome"], True

    image_blob = image_to_blob(image, image_format)
    element_id = _create_unique_game_element(base_name, description, image_blob, image_format)
    return element_id, base_name, False


def _find_matching_game_element(image, *, similarity_threshold=DEFAULT_DUPLICATE_ELEMENT_SIMILARITY):
    for element in get_all_game_elements(include_image=True):
        existing_blob = element.get("immagine")
        if not existing_blob:
            continue
        existing_image = None
        try:
            existing_image = blob_to_image(existing_blob, element.get("formato_immagine") or "PNG")
            if not _sizes_are_compatible(image.size, existing_image.size):
                continue
            score = compute_context_similarity(
                existing_image,
                image,
                resize_px=48,
                translation_tolerance_px=2,
            )
            if score >= similarity_threshold:
                return element
        except Exception:
            continue
        finally:
            close_fn = getattr(existing_image, "close", None)
            if callable(close_fn):
                close_fn()
    return None


def _sizes_are_compatible(size_a, size_b, *, tolerance_ratio=0.18):
    width_a, height_a = size_a
    width_b, height_b = size_b
    if min(width_a, height_a, width_b, height_b) <= 0:
        return False
    width_delta = abs(width_a - width_b) / float(max(width_a, width_b))
    height_delta = abs(height_a - height_b) / float(max(height_a, height_b))
    return width_delta <= tolerance_ratio and height_delta <= tolerance_ratio


def _merge_game_element_descriptions(existing_description, new_description):
    existing = (existing_description or "").strip()
    incoming = (new_description or "").strip()
    if not incoming:
        return existing
    if not existing:
        return incoming
    if incoming in existing:
        return existing

    semantic_hint = _extract_semantic_hint(incoming)
    merged = existing
    if semantic_hint and semantic_hint not in existing:
        merged = f"{merged}\n[semantic_hint] {semantic_hint}".strip()

    for marker in STRUCTURED_METADATA_MARKERS:
        block = _extract_marker_block(incoming, marker)
        if block and block not in merged:
            merged = f"{merged}\n{block}".strip()

    plain_incoming = _strip_structured_metadata(incoming)
    if plain_incoming and plain_incoming not in merged:
        merged = f"{merged}\n{plain_incoming}".strip()
    return merged


def _extract_semantic_hint(description):
    match = re.search(r"\[semantic_hint\]\s*(.+)", description or "")
    return match.group(1).strip() if match else ""


def _extract_marker_block(description, marker):
    if not description:
        return ""
    marker_index = description.find(marker)
    if marker_index < 0:
        return ""
    return description[marker_index:].strip()


def _strip_structured_metadata(description):
    cleaned = description or ""
    semantic_marker = "[semantic_hint]"
    if semantic_marker in cleaned:
        cleaned = cleaned.split(semantic_marker, 1)[0]
    for marker in STRUCTURED_METADATA_MARKERS:
        if marker in cleaned:
            cleaned = cleaned.split(marker, 1)[0]
    return cleaned.strip()


def _rect_to_dict(rect):
    left, top, right, bottom = rect
    return {"left": left, "top": top, "right": right, "bottom": bottom}


def _slugify(value):
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", str(value).strip().lower()).strip("_")
    return slug[:48] or "macro"


__all__ = [
    "ClickedElementCrop",
    "ClickedElementObservation",
    "DOOMSDAY_GRAPH_ID",
    "EMPTY_SPACE_DISMISSAL_NODE_ID",
    "REGION_VIEW_NODE_ID",
    "SHELTER_VIEW_NODE_ID",
    "UNKNOWN_VIEW_NODE_ID",
    "build_recorded_click_element_description",
    "build_recorded_click_element_name",
    "capture_clicked_element_crop",
    "classify_horizontal_band_from_bottom",
    "classify_doomsday_view",
    "is_empty_space_popup_dismissal_band",
    "register_recorded_click_element",
]
