"""Shared helpers for elevated Doomsday learning-mode tools."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from pathlib import Path
import subprocess
import sys
import time


REPO_ROOT = Path(__file__).resolve().parents[1]
SHORTCUT_PATH = "C:/Users/Public/Desktop/Doomsday.lnk"
TARGET_EXE = "Doomsday.exe"
STOP_HOTKEY_TEXT = "CTRL+ALT+S"

VK_LBUTTON = 0x01
VK_RBUTTON = 0x02
VK_CONTROL = 0x11
VK_MENU = 0x12
VK_S = 0x53


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin(script_path) -> int:
    result = ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        sys.executable,
        subprocess.list2cmdline([str(Path(script_path).resolve())]),
        str(REPO_ROOT),
        1,
    )
    if result <= 32:
        print(f"Impossibile aprire la sessione elevata. ShellExecuteW={result}")
        return 1
    print("Sessione elevata richiesta. Conferma il prompt UAC se compare.")
    return 0


def launch_shortcut_elevated(shortcut_path=SHORTCUT_PATH):
    result = ctypes.windll.shell32.ShellExecuteW(None, "runas", shortcut_path, None, None, 1)
    if result <= 32:
        raise RuntimeError(f"Impossibile avviare {shortcut_path} come amministratore. ShellExecuteW={result}")


def wait_for_window_rect(get_process_client_rect, target_exe=TARGET_EXE, *, timeout_sec):
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        if get_process_client_rect(target_exe):
            return True
        time.sleep(1)
    return False


def cursor_position():
    point = wintypes.POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
    return int(point.x), int(point.y)


def key_down(vk_code):
    return bool(ctypes.windll.user32.GetAsyncKeyState(vk_code) & 0x8000)


def stop_hotkey_pressed():
    return key_down(VK_CONTROL) and key_down(VK_MENU) and key_down(VK_S)


def point_inside_rect(x, y, rect):
    left, top, right, bottom = rect
    return left <= x <= right and top <= y <= bottom


def normalize_point(x, y, rect):
    left, top, right, bottom = rect
    width = max(1, right - left)
    height = max(1, bottom - top)
    return (x - left) / width, (y - top) / height


def make_file_logger(log_path):
    path = Path(log_path)
    path.parent.mkdir(exist_ok=True)

    def _log(message):
        text = str(message)
        print(text, flush=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(text + "\n")

    return _log


def prepare_repo_imports():
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))


def resolve_learning_shortcut_path(default_shortcut=SHORTCUT_PATH):
    prepare_repo_imports()
    try:
        from services.system_macro_service import resolve_launch_shortcut_for_current_context

        resolved = (resolve_launch_shortcut_for_current_context() or "").strip()
        if resolved:
            return resolved
    except Exception:
        pass
    return default_shortcut


__all__ = [
    "REPO_ROOT",
    "SHORTCUT_PATH",
    "STOP_HOTKEY_TEXT",
    "TARGET_EXE",
    "VK_LBUTTON",
    "VK_RBUTTON",
    "cursor_position",
    "is_admin",
    "key_down",
    "launch_shortcut_elevated",
    "make_file_logger",
    "normalize_point",
    "point_inside_rect",
    "prepare_repo_imports",
    "relaunch_as_admin",
    "stop_hotkey_pressed",
    "wait_for_window_rect",
]
