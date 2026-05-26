"""Matching template base per elementi UI Doomsday."""

from __future__ import annotations

import json
from pathlib import Path


def load_templates(templates_dir: str | Path) -> dict:
    """Carica template descritti da file JSON legacy."""
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("opencv-python non disponibile.") from exc

    templates = {}
    templates_dir = Path(templates_dir)
    for metadata_file in templates_dir.glob("*.json"):
        try:
            metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
            image_name = metadata.get("immagine")
            action_name = metadata.get("azione")
            if not image_name or not action_name:
                continue
            image_path = templates_dir / image_name
            if not image_path.exists():
                continue
            templates[action_name] = {
                "image": cv2.imread(str(image_path), 0),
                "metadata": metadata,
                "path": image_path,
            }
        except Exception:
            continue
    return templates


def find_best_match(template_image, screenshot_gray, threshold: float = 0.85):
    """Restituisce info match se il template supera la soglia."""
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("opencv-python non disponibile.") from exc

    result = cv2.matchTemplate(screenshot_gray, template_image, cv2.TM_CCOEFF_NORMED)
    _, max_value, _, max_location = cv2.minMaxLoc(result)
    if max_value < threshold:
        return None
    return {
        "score": float(max_value),
        "location": max_location,
        "width": int(template_image.shape[1]),
        "height": int(template_image.shape[0]),
    }

