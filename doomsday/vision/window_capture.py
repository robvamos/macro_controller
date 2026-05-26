"""Cattura della finestra di gioco e immagini dagli appunti."""

from __future__ import annotations

from pathlib import Path


def find_window(title_prefix: str = "Doomsday"):
    """Trova la prima finestra con titolo compatibile."""
    try:
        import pygetwindow as gw
    except ImportError as exc:
        raise RuntimeError("pygetwindow non disponibile.") from exc

    for window in gw.getWindowsWithTitle(title_prefix):
        if window.title.lower().startswith(title_prefix.lower()):
            return window
    return None


def screenshot_window(window):
    """Restituisce uno screenshot PIL della finestra data."""
    try:
        from PIL import ImageGrab
    except ImportError as exc:
        raise RuntimeError("Pillow non disponibile per la cattura schermo.") from exc

    bbox = (window.left, window.top, window.right, window.bottom)
    return ImageGrab.grab(bbox=bbox)


def save_clipboard_image(destination_path: str | Path) -> Path:
    """Salva un'immagine presente negli appunti."""
    try:
        from PIL import Image, ImageGrab
    except ImportError as exc:
        raise RuntimeError("Pillow non disponibile per gli appunti.") from exc

    image = ImageGrab.grabclipboard()
    if not isinstance(image, Image.Image):
        raise ValueError("Nessuna immagine valida trovata negli appunti.")

    destination = Path(destination_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination)
    return destination

