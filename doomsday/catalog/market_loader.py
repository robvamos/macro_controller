"""Utility per caricare dataset statici Doomsday importati dal legacy."""

from __future__ import annotations

import json
from pathlib import Path

from doomsday.config import CATALOG_MARKET_DIR, CATALOG_PROFILE_PACK_DIR, DOOMSDAY_ROSTER_DIR


def _load_json(path: str | Path) -> dict | list:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def normalize_profile_name(name: str) -> str:
    """Normalizza nomi file/profilo legacy in etichetta leggibile."""
    stem = Path(name).stem
    return stem.replace("_", " ").strip()


def load_market_profiles(base_dir: str | Path | None = None) -> list[dict]:
    """Carica i profili JSON di mercato/catalgo."""
    market_dir = Path(base_dir) if base_dir is not None else CATALOG_MARKET_DIR
    profiles = []
    if not market_dir.exists():
        return profiles
    for file_path in sorted(market_dir.glob("*.json")):
        if file_path.name.lower().startswith("totaleeroi_"):
            continue
        data = _load_json(file_path)
        if isinstance(data, dict):
            data.setdefault("_source_file", file_path.name)
            data.setdefault("_display_name", normalize_profile_name(file_path.name))
            profiles.append(data)
    return profiles


def load_roster_summary(roster_dir: str | Path | None = None) -> dict:
    """Carica il riepilogo roster personale legacy."""
    base_dir = Path(roster_dir) if roster_dir is not None else DOOMSDAY_ROSTER_DIR
    summary_path = base_dir / "total.json"
    if not summary_path.exists():
        return {}
    return _load_json(summary_path)


def load_beast_roster(roster_dir: str | Path | None = None) -> dict:
    """Carica il roster bestie legacy."""
    base_dir = Path(roster_dir) if roster_dir is not None else DOOMSDAY_ROSTER_DIR
    beast_path = base_dir / "bestie.json"
    if not beast_path.exists():
        return {}
    return _load_json(beast_path)


def load_profile_pack(base_dir: str | Path | None = None) -> dict:
    """Carica i file utili del profile pack legacy."""
    profile_dir = Path(base_dir) if base_dir is not None else CATALOG_PROFILE_PACK_DIR
    result = {}
    for name in ("beasts_registry.json", "chips_registry.json", "hero_profile_cynthia.json"):
        path = profile_dir / name
        if path.exists():
            result[path.stem] = _load_json(path)
    return result

