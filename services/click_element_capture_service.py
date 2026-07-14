"""Capture and catalogue the UI element under a recorded macro click."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
import re

from doomsday.vision.click_context_guard import capture_context_image
from doomsday.vision.game_element_recovery import search_game_window_elements
from services.game_element_ingestion_service import (
    build_game_element_description,
    create_or_merge_game_element,
    prepare_game_element_asset,
)


DEFAULT_CLICK_CAPTURE_RADIUS_PX = 180
DEFAULT_CONTOUR_PADDING_PX = 14
DOOMSDAY_GRAPH_ID = "doomsday-default-ui-graph"
UNKNOWN_VIEW_NODE_ID = "unknown_main_view"
REGION_VIEW_NODE_ID = "exterior_region_view"
SHELTER_VIEW_NODE_ID = "shelter_interior_view"
EMPTY_SPACE_DISMISSAL_NODE_ID = "empty_space_popup_dismissal_band_4"
EMPTY_SPACE_DISMISSAL_ELEMENT_NAME = "semantic_empty_space_popup_dismissal_band_4"


@dataclass(slots=True)
class ClickedElementCrop:
    image: object
    capture_bounds: tuple[int, int, int, int]
    crop_bounds: tuple[int, int, int, int]
    click_offset_in_crop: tuple[int, int]
    contour_confidence: float
    shape_family: str = "unknown"


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
    semantic_node_id: str | None = None
    semantic_role: str | None = None
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
    """Capture a square click context and trim it from the center outward."""
    half_width_px = int(half_width_px or radius_px or DEFAULT_CLICK_CAPTURE_RADIUS_PX)
    half_height_px = int(half_height_px or radius_px or DEFAULT_CLICK_CAPTURE_RADIUS_PX)
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
        crop_box, confidence, shape_family = _find_probable_element_box(
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
        shape_family=shape_family,
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
    infer_spatial_semantic_actions=True,
) -> ClickedElementObservation:
    """Persist the clicked visual element and attach semantic graph context in metadata."""
    view_node_id = view_node_id or classify_doomsday_view(window_rect)
    semantic_action = None
    if infer_spatial_semantic_actions:
        semantic_action = _infer_semantic_action(
            normalized_x=normalized_x,
            normalized_y=normalized_y,
            view_node_id=view_node_id,
        )
    if semantic_action is not None:
        return _register_semantic_click_action(
            macro_name=macro_name,
            event_time_ms=event_time_ms,
            button=button,
            abs_x=abs_x,
            abs_y=abs_y,
            normalized_x=normalized_x,
            normalized_y=normalized_y,
            window_rect=window_rect,
            view_node_id=view_node_id,
            sequence_index=sequence_index,
            previous_element_id=previous_element_id,
            semantic_action=semantic_action,
        )

    crop = capture_clicked_element_crop(abs_x=abs_x, abs_y=abs_y, window_rect=window_rect)
    try:
        semantic_role = _infer_semantic_role(crop.shape_family)
        semantic_hint = (
            f"recorded click element; graph={DOOMSDAY_GRAPH_ID}; "
            f"view={view_node_id}; macro={macro_name}; role={semantic_role}; shape={crop.shape_family}"
        )
        asset = prepare_game_element_asset(crop.image, source_format="PNG", semantic_hint=semantic_hint)
        metadata = {
            "source": "macro_recording_click_capture",
            "graph_id": DOOMSDAY_GRAPH_ID,
            "view_node_id": view_node_id,
            "semantic_node_id": None,
            "semantic_role": semantic_role,
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
            "shape_family": crop.shape_family,
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
        upsert_result = create_or_merge_game_element(
            name,
            description,
            image=asset.image,
            formato_immagine=asset.storage_format,
        )
    finally:
        close_fn = getattr(crop.image, "close", None)
        if callable(close_fn):
            close_fn()

    return ClickedElementObservation(
        element_id=upsert_result.element_id,
        element_name=upsert_result.element_name,
        graph_id=DOOMSDAY_GRAPH_ID,
        view_node_id=view_node_id,
        macro_name=macro_name,
        event_time_ms=event_time_ms,
        click_position=(int(abs_x), int(abs_y)),
        normalized_position=(normalized_x, normalized_y),
        capture_bounds=crop.capture_bounds,
        crop_bounds=crop.crop_bounds,
        contour_confidence=crop.contour_confidence,
        semantic_node_id=None,
        semantic_role=semantic_role,
        reused_existing=upsert_result.reused_existing,
    )


def build_recorded_click_element_name(*, macro_name, event_time_ms, abs_x, abs_y) -> str:
    macro_slug = _slugify(macro_name or "macro")
    event_part = "unknown_time" if event_time_ms is None else f"{int(event_time_ms):06d}ms"
    return f"recorded_click_{macro_slug}_{event_part}_{int(abs_x)}x{int(abs_y)}"


def build_recorded_click_element_description(metadata) -> str:
    human_description = (
        "Elemento acquisito automaticamente durante la registrazione macro.\n"
        f"Grafo: {metadata['graph_id']}\n"
        f"Nodo vista stimato: {metadata['view_node_id']}\n"
        f"Macro sorgente: {metadata['macro_name']}"
    )
    return build_game_element_description(
        human_description + "\nAUTO_CLICK_ELEMENT_METADATA:" + json.dumps(metadata, ensure_ascii=False, sort_keys=True),
        "",
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


def _infer_semantic_action(*, normalized_x, normalized_y, view_node_id):
    if is_empty_space_popup_dismissal_band(normalized_y):
        return {
            "node_id": EMPTY_SPACE_DISMISSAL_NODE_ID,
            "element_name": EMPTY_SPACE_DISMISSAL_ELEMENT_NAME,
            "semantic_role": "spatial_popup_dismissal",
            "description": (
                "Click in area vuota della schermata per chiudere popup bloccanti privi di bottone stabile. "
                "Elemento semantico condiviso tra popup diversi."
            ),
        }
    return None


def _register_semantic_click_action(
    *,
    macro_name,
    event_time_ms,
    button,
    abs_x,
    abs_y,
    normalized_x,
    normalized_y,
    window_rect,
    view_node_id,
    sequence_index,
    previous_element_id,
    semantic_action,
):
    semantic_hint = (
        f"semantic click action; graph={DOOMSDAY_GRAPH_ID}; view={view_node_id}; "
        f"role={semantic_action['semantic_role']}; node={semantic_action['node_id']}"
    )
    placeholder_image = _build_semantic_action_image(semantic_action["semantic_role"])
    try:
        asset = prepare_game_element_asset(placeholder_image, source_format="PNG", semantic_hint=semantic_hint)
        metadata = {
            "source": "macro_recording_semantic_click_action",
            "graph_id": DOOMSDAY_GRAPH_ID,
            "view_node_id": view_node_id,
            "semantic_node_id": semantic_action["node_id"],
            "semantic_role": semantic_action["semantic_role"],
            "macro_name": macro_name,
            "event_time_ms": event_time_ms,
            "button": button,
            "click_position": {"x": int(abs_x), "y": int(abs_y)},
            "normalized_position": {"x": normalized_x, "y": normalized_y},
            "capture_bounds": _rect_to_dict(window_rect),
            "crop_bounds": _rect_to_dict(window_rect),
            "stored_size": {"width": asset.stored_size[0], "height": asset.stored_size[1]},
            "click_offset_in_crop": {"x": 0, "y": 0},
            "contour_confidence": 1.0,
            "shape_family": "semantic_action",
            "sequence_index": sequence_index,
            "previous_element_id": previous_element_id,
            "sequence_relation": "after_previous_click" if previous_element_id else "sequence_start",
        }
        description = build_game_element_description(
            semantic_action["description"] + "\nAUTO_CLICK_ELEMENT_METADATA:" + json.dumps(metadata, ensure_ascii=False, sort_keys=True),
            semantic_hint,
        )
        upsert_result = create_or_merge_game_element(
            semantic_action["element_name"],
            description,
            image=asset.image,
            formato_immagine=asset.storage_format,
        )
    finally:
        close_fn = getattr(placeholder_image, "close", None)
        if callable(close_fn):
            close_fn()

    return ClickedElementObservation(
        element_id=upsert_result.element_id,
        element_name=upsert_result.element_name,
        graph_id=DOOMSDAY_GRAPH_ID,
        view_node_id=view_node_id,
        macro_name=macro_name,
        event_time_ms=event_time_ms,
        click_position=(int(abs_x), int(abs_y)),
        normalized_position=(normalized_x, normalized_y),
        capture_bounds=window_rect,
        crop_bounds=window_rect,
        contour_confidence=1.0,
        semantic_node_id=semantic_action["node_id"],
        semantic_role=semantic_action["semantic_role"],
        reused_existing=upsert_result.reused_existing,
    )


def _build_semantic_action_image(label):
    try:
        from PIL import Image, ImageDraw
    except ImportError as exc:
        raise RuntimeError("Pillow non disponibile per generare l'elemento semantico.") from exc

    image = Image.new("RGBA", (96, 96), (36, 32, 60, 255))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((6, 6, 90, 90), radius=14, outline=(208, 196, 140, 255), width=4, fill=(52, 48, 82, 255))
    draw.ellipse((26, 26, 70, 70), outline=(240, 235, 215, 255), width=4)
    draw.line((48, 18, 48, 78), fill=(240, 235, 215, 255), width=4)
    draw.line((18, 48, 78, 48), fill=(240, 235, 215, 255), width=4)
    draw.rectangle((18, 76, 78, 86), fill=(110, 130, 190, 255))
    return image


def _infer_semantic_role(shape_family):
    role_map = {
        "compact_icon": "interactive_icon",
        "medium_icon": "interactive_icon",
        "large_panel": "panel_or_complex_entry",
        "wide_button": "text_button",
        "semantic_action": "spatial_popup_dismissal",
        "fallback": "unknown_click_target",
    }
    return role_map.get(shape_family, "generic_click_target")


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
    for window_rank, radius in enumerate(_iter_expanding_windows(image_width, image_height), start=1):
        window_box = (
            max(0, click_x - radius),
            max(0, click_y - radius),
            min(image_width, click_x + radius),
            min(image_height, click_y + radius),
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
            radius=radius,
            window_rank=window_rank,
            padding_px=padding_px,
            source_bonus=0.28,
        )

        edges = cv2.Canny(roi, 35, 110)
        kernel_width = 5 if radius <= 32 else 7 if radius <= 80 else 9
        kernel = np.ones((5, kernel_width), np.uint8)
        edges = cv2.dilate(edges, kernel, iterations=1)
        _append_contour_candidates(
            candidates,
            edges,
            origin=(x1, y1),
            local_click=local_click,
            image_size=image.size,
            window_size=(x2 - x1, y2 - y1),
            radius=radius,
            window_rank=window_rank,
            padding_px=padding_px,
            source_bonus=0.0,
        )
    if not candidates:
        return _fallback_click_box(image.size, local_click), 0.0, "fallback"

    score, x, y, width, height, contains_click, _shape_family = _select_best_candidate(candidates, image.size)
    shape_family = _classify_shape_family(width, height, image_width, image_height)
    shape_padding = _padding_for_shape_family(shape_family, base_padding=padding_px)
    left = max(0, x - shape_padding)
    top = max(0, y - shape_padding)
    right = min(image_width, x + width + shape_padding)
    bottom = min(image_height, y + height + shape_padding)
    left, top, right, bottom = _normalize_crop_box_for_shape(
        left,
        top,
        right,
        bottom,
        image_width=image_width,
        image_height=image_height,
        shape_family=shape_family,
    )
    confidence = 0.85 if contains_click else 0.55
    return (left, top, right, bottom), confidence, shape_family


def _iter_expanding_windows(image_width, image_height):
    base_windows = (28, 42, 60, 82, 108, 138, 172, 210)
    max_radius = max(8, min(image_width, image_height) // 2)
    for radius in base_windows:
        yield min(radius, max_radius)


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
    window_rank,
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
        max_distance = math.hypot(radius, radius) or 1.0
        window_area = max(1, window_width * window_height)
        fill_ratio = min(1.0, area / float(window_area))
        shape_family = _classify_shape_family(width, height, image_width, image_height)
        shape_bonus = _shape_bonus(width, height, shape_family=shape_family)
        strip_penalty = _wide_strip_penalty(width, height, image_height)
        size_bonus = min(0.24, math.sqrt(area / float(max(1, image_width * image_height))))
        centered_bonus = max(0.0, 0.32 - (distance / max_distance) * 0.32)
        score = (
            (1.25 if contains_click else 0.35)
            + fill_ratio
            + shape_bonus
            + size_bonus
            + centered_bonus
            + source_bonus
            - strip_penalty
            - min(1.0, distance / max_distance)
            - (0.012 * window_rank)
        )
        candidates.append((score, abs_x, abs_y, width, height, contains_click, shape_family, window_rank))


def _shape_bonus(width, height, *, shape_family):
    ratio = width / float(max(1, height))
    if shape_family == "compact_icon":
        return 0.24
    if shape_family == "medium_icon":
        return 0.18
    if shape_family == "large_panel":
        return 0.06
    if shape_family == "wide_button":
        return 0.22 if ratio >= 2.0 else 0.08
    if ratio > 3.0:
        return -0.10
    return 0.0


def _padding_for_shape_family(shape_family, *, base_padding):
    if shape_family == "compact_icon":
        return max(base_padding, 18)
    if shape_family == "medium_icon":
        return max(base_padding, 22)
    if shape_family == "large_panel":
        return max(base_padding, 24)
    if shape_family == "wide_button":
        return max(base_padding, 18)
    return max(base_padding, 16)


def _classify_shape_family(width, height, image_width, image_height):
    ratio = width / float(max(1, height))
    area_ratio = (width * height) / float(max(1, image_width * image_height))
    if ratio >= 1.6 and height >= 20:
        return "wide_button"
    if area_ratio >= 0.14 or height >= int(image_height * 0.40):
        return "large_panel"
    if 0.72 <= ratio <= 1.40 and width <= int(image_width * 0.48):
        return "compact_icon"
    if 0.55 <= ratio <= 1.8:
        return "medium_icon"
    return "unknown"


def _wide_strip_penalty(width, height, image_height):
    ratio = width / float(max(1, height))
    if ratio >= 4.0 and height <= max(18, int(image_height * 0.32)):
        return 0.42
    return 0.0


def _looks_like_wide_strip(width, height, image_width, image_height):
    ratio = width / float(max(1, height))
    return ratio >= 4.4 and width >= int(image_width * 0.50) and height <= max(16, int(image_height * 0.30))


def _select_best_candidate(candidates, image_size):
    image_width, image_height = image_size
    sorted_candidates = sorted(candidates, reverse=True)
    best_global = sorted_candidates[0]
    max_rank = max(candidate[7] for candidate in sorted_candidates)
    for rank in range(1, max_rank + 1):
        window_candidates = [candidate for candidate in sorted_candidates if candidate[7] == rank and candidate[5]]
        if not window_candidates:
            continue
        accepted = _pick_progressive_candidate(window_candidates, image_width, image_height)
        if accepted is not None:
            return accepted[:7]

    anchored = [candidate for candidate in sorted_candidates if candidate[5]]
    if anchored:
        return anchored[0][:7]

    non_strip = [
        candidate
        for candidate in sorted_candidates
        if not _looks_like_wide_strip(candidate[3], candidate[4], image_width, image_height)
    ]
    if non_strip:
        return non_strip[0][:7]

    return best_global[:7]


def _pick_progressive_candidate(candidates, image_width, image_height):
    accepted_thresholds = {
        "compact_icon": 0.95,
        "medium_icon": 1.00,
        "large_panel": 0.90,
        "wide_button": 1.00,
        "unknown": 1.12,
    }
    non_strip_candidates = [
        candidate
        for candidate in candidates
        if not _looks_like_wide_strip(candidate[3], candidate[4], image_width, image_height)
    ]
    pool = non_strip_candidates or candidates
    accepted = []
    for candidate in pool:
        threshold = accepted_thresholds.get(candidate[6], 1.12)
        if candidate[0] >= threshold:
            accepted.append(candidate)
    if not accepted:
        return None

    best_candidate = accepted[0]
    wide_candidates = [candidate for candidate in accepted if candidate[6] == "wide_button"]
    if wide_candidates and best_candidate[6] != "wide_button":
        best_wide = wide_candidates[0]
        if best_wide[0] >= best_candidate[0] - 0.35 and best_wide[3] >= int(best_candidate[3] * 1.4):
            return best_wide
    for candidate in accepted:
        if candidate[6] == best_candidate[6]:
            return candidate
    return None


def _normalize_crop_box_for_shape(left, top, right, bottom, *, image_width, image_height, shape_family):
    width = max(1, right - left)
    height = max(1, bottom - top)
    center_x = left + width / 2.0
    center_y = top + height / 2.0

    if shape_family == "compact_icon":
        target_side = max(84, width, height)
        return _build_centered_box(center_x, center_y, target_side, target_side, image_width, image_height)
    if shape_family == "medium_icon":
        target_side = max(104, width, height)
        return _build_centered_box(center_x, center_y, target_side, target_side, image_width, image_height)
    if shape_family == "large_panel":
        target_side = max(132, width, height)
        return _build_centered_box(center_x, center_y, target_side, target_side, image_width, image_height)
    if shape_family == "wide_button":
        target_width = max(180, width)
        target_height = max(64, height)
        return _build_centered_box(center_x, center_y, target_width, target_height, image_width, image_height)
    target_side = max(96, width, height)
    return _build_centered_box(center_x, center_y, target_side, target_side, image_width, image_height)


def _build_centered_box(center_x, center_y, target_width, target_height, image_width, image_height):
    half_width = target_width / 2.0
    half_height = target_height / 2.0
    left = int(round(center_x - half_width))
    top = int(round(center_y - half_height))
    right = int(round(center_x + half_width))
    bottom = int(round(center_y + half_height))

    if left < 0:
        right -= left
        left = 0
    if top < 0:
        bottom -= top
        top = 0
    if right > image_width:
        shift = right - image_width
        left = max(0, left - shift)
        right = image_width
    if bottom > image_height:
        shift = bottom - image_height
        top = max(0, top - shift)
        bottom = image_height

    if right <= left:
        right = min(image_width, left + 1)
    if bottom <= top:
        bottom = min(image_height, top + 1)
    return left, top, right, bottom


def _fallback_click_box(image_size, local_click, fallback_radius=72):
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
