"""Gestione centralizzata di configurazione applicativa e temi."""

from __future__ import annotations

import copy
import json
import logging
import shutil
from pathlib import Path

from core.paths import (
    APP_CONFIG_PATH,
    LEGACY_APP_CONFIG_PATH,
    ensure_project_directories,
    legacy_style_path,
    style_path,
)


logger = logging.getLogger(__name__)

DEFAULT_STYLE_MAP = {
    "default": {
        "background_color": "#282c34",
        "text_color": "#abb2bf",
        "button_bg_color": "#61afef",
        "button_fg_color": "#ffffff",
        "border_color": "#3e4452",
        "font_family": "Segoe UI",
        "font_size_large": 12,
        "font_size_medium": 10,
        "font_size_small": 9,
        "status_running_color": "#50fa7b",
        "status_recording_color": "#ff6e6e",
        "status_idle_color": "#6a6a6a",
    },
    "light": {
        "background_color": "#f5f5f5",
        "text_color": "#333333",
        "button_bg_color": "#4285f4",
        "button_fg_color": "#ffffff",
        "border_color": "#e0e0e0",
        "font_family": "Segoe UI",
        "font_size_large": 12,
        "font_size_medium": 10,
        "font_size_small": 9,
        "status_running_color": "#4caf50",
        "status_recording_color": "#f44336",
        "status_idle_color": "#757575",
    },
    "dark_blue": {
        "background_color": "#1e1e2e",
        "text_color": "#cdd6f4",
        "button_bg_color": "#89b4fa",
        "button_fg_color": "#1e1e2e",
        "border_color": "#45475a",
        "font_family": "Segoe UI",
        "font_size_large": 12,
        "font_size_medium": 10,
        "font_size_small": 9,
        "status_running_color": "#a6e3a1",
        "status_recording_color": "#f38ba8",
        "status_idle_color": "#6c7086",
    },
    "neon": {
        "background_color": "#000000",
        "text_color": "#00ff41",
        "button_bg_color": "#ff00ff",
        "button_fg_color": "#000000",
        "border_color": "#00ffff",
        "font_family": "Courier New",
        "font_size_large": 12,
        "font_size_medium": 10,
        "font_size_small": 9,
        "status_running_color": "#00ff41",
        "status_recording_color": "#ff0040",
        "status_idle_color": "#808080",
    },
}

DEFAULT_APP_CONFIG = {
    "theme": copy.deepcopy(DEFAULT_STYLE_MAP["default"]),
    "macro_manager": {
        "window_title": "Macro Manager",
        "listbox_height": 8,
        "loop_interval_sec_default": 5,
    },
    "new_macro_dialog": {
        "window_title": "Nuova Macro",
        "default_exe_name": "Doomsday.exe",
        "default_duration_sec": 10,
    },
    "selected_style": "default",
}


def _merge_dict(base: dict, overrides: dict) -> dict:
    merged = copy.deepcopy(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_dict(merged[key], value)
        else:
            merged[key] = value
    return merged


def _read_json_file(path: Path, default: dict | None = None) -> dict:
    if not path.exists():
        return copy.deepcopy(default or {})

    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except json.JSONDecodeError:
        logger.warning("File JSON malformato: %s", path)
    except OSError as exc:
        logger.warning("Errore lettura file JSON %s: %s", path, exc)
    return copy.deepcopy(default or {})


def _write_json_file(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)


def _ensure_default_style_files() -> None:
    for style_name, style_config in DEFAULT_STYLE_MAP.items():
        style_file = style_path(style_name)
        if not style_file.exists():
            _write_json_file(style_file, style_config)


def migrate_legacy_layout() -> None:
    """Migra file legacy dalla root verso le nuove cartelle logiche."""
    ensure_project_directories()

    if LEGACY_APP_CONFIG_PATH.exists() and not APP_CONFIG_PATH.exists():
        shutil.move(str(LEGACY_APP_CONFIG_PATH), str(APP_CONFIG_PATH))

    for style_name in DEFAULT_STYLE_MAP:
        legacy_file = legacy_style_path(style_name)
        target_file = style_path(style_name)
        if legacy_file.exists() and not target_file.exists():
            shutil.move(str(legacy_file), str(target_file))

    _ensure_default_style_files()


def load_app_config() -> dict:
    """Carica la configurazione applicativa con merge sui default."""
    migrate_legacy_layout()

    loaded = _read_json_file(APP_CONFIG_PATH, default=DEFAULT_APP_CONFIG)
    merged = _merge_dict(DEFAULT_APP_CONFIG, loaded)

    if not APP_CONFIG_PATH.exists():
        save_app_config(merged)

    return merged


def save_app_config(config: dict) -> None:
    """Salva la configurazione applicativa nel percorso centralizzato."""
    migrate_legacy_layout()
    _write_json_file(APP_CONFIG_PATH, config)


def load_style_config(style_name: str) -> dict:
    """Carica la configurazione di uno stile, con fallback sul default."""
    migrate_legacy_layout()
    selected_path = style_path(style_name)
    if not selected_path.exists():
        logger.warning("Stile '%s' non trovato, uso default", style_name)
        selected_path = style_path("default")
    return _read_json_file(selected_path, default=DEFAULT_STYLE_MAP["default"])


def save_selected_style(style_name: str) -> None:
    """Aggiorna lo stile selezionato nella configurazione applicativa."""
    config = load_app_config()
    config["selected_style"] = style_name
    save_app_config(config)


def get_window_geometry(config_key: str) -> dict | None:
    """Restituisce la geometria salvata per una finestra/dialog."""
    return load_app_config().get(config_key)


def set_window_geometry(config_key: str, *, x: int, y: int, width: int, height: int) -> None:
    """Salva la geometria di una finestra/dialog nella configurazione."""
    config = load_app_config()
    config[config_key] = {
        "x": x,
        "y": y,
        "width": width,
        "height": height,
    }
    save_app_config(config)
