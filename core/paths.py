"""Portable project paths and workstation-local writable state."""

import os
from pathlib import Path

from workstation.settings import load_settings


PROJECT_ROOT = Path(__file__).resolve().parent.parent
WORKSTATION_SETTINGS = load_settings(root=PROJECT_ROOT)
WORKSTATION_DIR = Path(WORKSTATION_SETTINGS["profileDir"])
RUNTIME_DIR = Path(WORKSTATION_SETTINGS["runtimeDir"])
LOCAL_CONFIG_DIR = WORKSTATION_DIR / "config"
_configured_shortcut = WORKSTATION_SETTINGS.get("gameShortcutPath", "")
DOOMSDAY_SHORTCUT_PATH = (
    Path(_configured_shortcut)
    if _configured_shortcut
    else Path(os.environ.get("PUBLIC", str(Path.home().parent))) / "Desktop" / "Doomsday.lnk"
)

# Versioned, read-only assets stay inside the checkout.
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"
DOCS_DIR = PROJECT_ROOT / "docs"
DOOMSDAY_DIR = DATA_DIR / "doomsday"
DOOMSDAY_CATALOG_DIR = DOOMSDAY_DIR / "catalog"
DOOMSDAY_ROSTER_DIR = DOOMSDAY_DIR / "roster"
DOOMSDAY_KNOWLEDGE_DIR = DOOMSDAY_DIR / "knowledge"
DOOMSDAY_INTELLIGENCE_DIR = DOOMSDAY_DIR / "intelligence"
DOOMSDAY_DOMAIN_REGISTRY_PATH = DOOMSDAY_INTELLIGENCE_DIR / "domain_registry.json"
DOOMSDAY_SOURCE_REGISTRY_OVERLAY_PATH = DOOMSDAY_INTELLIGENCE_DIR / "source_registry.overlay.json"

# User state, logs, captures and databases stay in the selected local profile.
DOOMSDAY_LOCAL_DIR = RUNTIME_DIR / "doomsday"
DOOMSDAY_OCR_OUTPUT_DIR = DOOMSDAY_LOCAL_DIR / "ocr_output"
DOOMSDAY_SCREENSHOTS_DIR = DOOMSDAY_LOCAL_DIR / "screenshots"
DOOMSDAY_INTELLIGENCE_DB_PATH = DOOMSDAY_LOCAL_DIR / "intelligence.db"
DOOMSDAY_RUNTIME_DIR = DOOMSDAY_LOCAL_DIR
DOOMSDAY_RUNTIME_REGISTRY_PATH = DOOMSDAY_RUNTIME_DIR / "game_runtime_registry.json"
DOOMSDAY_DB_PATH = DOOMSDAY_LOCAL_DIR / "doomsday_roster.db"
DOOMSDAY_LIVE_ROSTER_DB_PATH = DOOMSDAY_LOCAL_DIR / "live_roster.db"
LEGACY_DOOMSDAY_DB_PATH = DOOMSDAY_DIR / "doomsday_roster.db"
LEGACY_DOOMSDAY_LIVE_ROSTER_DB_PATH = DOOMSDAY_DIR / "roster" / "live_roster.db"

APP_CONFIG_PATH = LOCAL_CONFIG_DIR / "config.json"
MACRO_CONFIG_PATH = LOCAL_CONFIG_DIR / "macro_config.json"
STYLES_DIR = LOCAL_CONFIG_DIR / "styles"
BUNDLED_STYLES_DIR = CONFIG_DIR / "styles"
LEGACY_APP_CONFIG_PATH = CONFIG_DIR / "config.json"
LEGACY_ROOT_APP_CONFIG_PATH = PROJECT_ROOT / "config.json"
LEGACY_MACRO_CONFIG_PATH = CONFIG_DIR / "macro_config.json"

DB_PATH = RUNTIME_DIR / "macro_recorder.db"
LEGACY_DB_PATH = DATA_DIR / "macro_recorder.db"
LEGACY_ROOT_DB_PATH = PROJECT_ROOT / "macro_recorder.db"

LOGS_DIR = RUNTIME_DIR / "logs"
EXPORTS_DIR = RUNTIME_DIR / "exports"
LEARNING_SESSIONS_DIR = RUNTIME_DIR / "learning_sessions"
RECOVERED_LEARNING_SESSIONS_DIR = DOOMSDAY_LOCAL_DIR / "recovered_learning_sessions"


def style_path(style_name: str) -> Path:
    """Return the workstation-local style file for a named theme."""
    return STYLES_DIR / f"style_{style_name}.json"


def bundled_style_path(style_name: str) -> Path:
    """Return the read-only, versioned default style file."""
    return BUNDLED_STYLES_DIR / f"style_{style_name}.json"


def legacy_style_path(style_name: str) -> Path:
    """Return the old root-level style file used by previous releases."""
    return PROJECT_ROOT / f"style_{style_name}.json"


def ensure_project_directories() -> None:
    """Create writable profile directories without writing into shared assets."""
    LOCAL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    STYLES_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DOOMSDAY_CATALOG_DIR.mkdir(parents=True, exist_ok=True)
    DOOMSDAY_ROSTER_DIR.mkdir(parents=True, exist_ok=True)
    for path in (
        RUNTIME_DIR,
        DOOMSDAY_LOCAL_DIR,
        DOOMSDAY_OCR_OUTPUT_DIR,
        DOOMSDAY_SCREENSHOTS_DIR,
        LOGS_DIR,
        EXPORTS_DIR,
        LEARNING_SESSIONS_DIR,
        RECOVERED_LEARNING_SESSIONS_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)
