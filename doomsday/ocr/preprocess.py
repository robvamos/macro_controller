"""Deterministic PIL-only OCR preprocessing profiles."""

from __future__ import annotations

from PIL import Image, ImageOps


OCR_PREPROCESS_PROFILES = {"raw", "grayscale_autocontrast", "grayscale_autocontrast_2x"}


def preprocess_for_ocr(image: Image.Image, profile: str = "grayscale_autocontrast_2x") -> Image.Image:
    if profile not in OCR_PREPROCESS_PROFILES:
        raise ValueError(f"Unknown OCR preprocessing profile: {profile}")
    if profile == "raw":
        return image.copy()
    processed = ImageOps.autocontrast(ImageOps.grayscale(image))
    if profile.endswith("_2x"):
        processed = processed.resize((processed.width * 2, processed.height * 2), Image.Resampling.LANCZOS)
    return processed


__all__ = ["OCR_PREPROCESS_PROFILES", "preprocess_for_ocr"]
