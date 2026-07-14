"""Cattura Win32 del desktop, adatta anche a finestre DirectX visibili."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FrameQuality:
    valid: bool
    mean_luma: float
    dark_fraction: float
    luma_range: int
    reason: str


def capture_screen_region(left: int, top: int, right: int, bottom: int):
    """Restituisce una regione PIL del desktop tramite BitBlt.

    La finestra deve essere visibile: questa funzione non legge framebuffer,
    memoria di processo o superfici nascoste del gioco.
    """
    if right <= left or bottom <= top:
        raise ValueError("Area di cattura non valida.")
    try:
        import win32con
        import win32gui
        import win32ui
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Dipendenze Win32/Pillow non disponibili per la cattura.") from exc

    width = int(right - left)
    height = int(bottom - top)
    hwnd = win32gui.GetDesktopWindow()
    window_dc = win32gui.GetWindowDC(hwnd)
    if not window_dc:
        raise RuntimeError("Impossibile ottenere il device context del desktop.")

    src_dc = None
    mem_dc = None
    bitmap = None
    try:
        src_dc = win32ui.CreateDCFromHandle(window_dc)
        mem_dc = src_dc.CreateCompatibleDC()
        bitmap = win32ui.CreateBitmap()
        bitmap.CreateCompatibleBitmap(src_dc, width, height)
        mem_dc.SelectObject(bitmap)
        mem_dc.BitBlt((0, 0), (width, height), src_dc, (int(left), int(top)), win32con.SRCCOPY)
        info = bitmap.GetInfo()
        image = Image.frombuffer(
            "RGB",
            (info["bmWidth"], info["bmHeight"]),
            bitmap.GetBitmapBits(True),
            "raw",
            "BGRX",
            0,
            1,
        )
        return image.copy()
    finally:
        if bitmap is not None:
            win32gui.DeleteObject(bitmap.GetHandle())
        if mem_dc is not None:
            mem_dc.DeleteDC()
        if src_dc is not None:
            src_dc.DeleteDC()
        win32gui.ReleaseDC(hwnd, window_dc)


def is_blank_frame(image, *, dark_threshold: float = 2.0) -> bool:
    """Segnala frame quasi neri, tipici di ImageGrab su alcune DirectX."""
    grayscale = image.convert("L").resize((32, 32))
    pixels = grayscale.tobytes()
    return not pixels or (sum(pixels) / len(pixels)) <= dark_threshold


def assess_frame_quality(image) -> FrameQuality:
    """Rileva frame neri e catture DirectX parzialmente bucate."""
    grayscale = image.convert("L").resize((96, 54))
    pixels = grayscale.tobytes()
    if not pixels:
        return FrameQuality(False, 0.0, 1.0, 0, "Frame senza pixel.")
    mean_luma = sum(pixels) / len(pixels)
    dark_fraction = sum(value <= 3 for value in pixels) / len(pixels)
    luma_range = max(pixels) - min(pixels)
    if mean_luma <= 2.0:
        reason = "Frame quasi completamente nero."
        valid = False
    elif dark_fraction >= 0.45:
        reason = "Troppe aree nere: possibile cattura DirectX incompleta."
        valid = False
    elif luma_range < 8:
        reason = "Frame privo di variazione visiva sufficiente."
        valid = False
    else:
        reason = "Frame visivamente utilizzabile."
        valid = True
    return FrameQuality(valid, round(mean_luma, 3), round(dark_fraction, 4), luma_range, reason)


__all__ = ["FrameQuality", "assess_frame_quality", "capture_screen_region", "is_blank_frame"]
