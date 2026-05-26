"""Percorsi centrali del progetto."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
STYLES_DIR = CONFIG_DIR / "styles"
DATA_DIR = PROJECT_ROOT / "data"
DOCS_DIR = PROJECT_ROOT / "docs"
DOOMSDAY_DIR = DATA_DIR / "doomsday"
DOOMSDAY_CATALOG_DIR = DOOMSDAY_DIR / "catalog"
DOOMSDAY_ROSTER_DIR = DOOMSDAY_DIR / "roster"
DOOMSDAY_OCR_OUTPUT_DIR = DOOMSDAY_DIR / "ocr_output"
DOOMSDAY_SCREENSHOTS_DIR = DOOMSDAY_DIR / "screenshots"

APP_CONFIG_PATH = CONFIG_DIR / "config.json"
LEGACY_APP_CONFIG_PATH = PROJECT_ROOT / "config.json"

DB_PATH = DATA_DIR / "macro_recorder.db"
LEGACY_DB_PATH = PROJECT_ROOT / "macro_recorder.db"
DOOMSDAY_DB_PATH = DOOMSDAY_DIR / "doomsday_roster.db"


def style_path(style_name: str) -> Path:
    """Restituisce il percorso del file stile richiesto."""
    return STYLES_DIR / f"style_{style_name}.json"


def legacy_style_path(style_name: str) -> Path:
    """Restituisce il percorso legacy del file stile richiesto."""
    return PROJECT_ROOT / f"style_{style_name}.json"


def ensure_project_directories() -> None:
    """Crea le cartelle logiche del progetto se non esistono."""
    CONFIG_DIR.mkdir(exist_ok=True)
    STYLES_DIR.mkdir(exist_ok=True)
    DATA_DIR.mkdir(exist_ok=True)
    DOCS_DIR.mkdir(exist_ok=True)
    DOOMSDAY_DIR.mkdir(exist_ok=True)
    DOOMSDAY_CATALOG_DIR.mkdir(exist_ok=True)
    DOOMSDAY_ROSTER_DIR.mkdir(exist_ok=True)
    DOOMSDAY_OCR_OUTPUT_DIR.mkdir(exist_ok=True)
    DOOMSDAY_SCREENSHOTS_DIR.mkdir(exist_ok=True)
