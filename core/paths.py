"""Percorsi centrali del progetto."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
STYLES_DIR = CONFIG_DIR / "styles"
DATA_DIR = PROJECT_ROOT / "data"
DOCS_DIR = PROJECT_ROOT / "docs"

APP_CONFIG_PATH = CONFIG_DIR / "config.json"
LEGACY_APP_CONFIG_PATH = PROJECT_ROOT / "config.json"

DB_PATH = DATA_DIR / "macro_recorder.db"
LEGACY_DB_PATH = PROJECT_ROOT / "macro_recorder.db"


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

