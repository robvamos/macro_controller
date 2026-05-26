"""Repository SQLite per catalogo e roster Doomsday."""

from .catalog_repository import (
    get_catalog_stats,
    import_catalog_datasets,
    list_beast_profiles,
    list_catalog_profiles,
    list_chip_profiles,
    list_hero_profile_notes,
)
from .database import connect_doomsday_db, get_doomsday_db_path, setup_doomsday_tables
from .roster_repository import (
    get_roster_stats,
    import_roster_datasets,
    load_roster_beasts,
    load_roster_summary,
)

__all__ = [
    "connect_doomsday_db",
    "get_catalog_stats",
    "get_doomsday_db_path",
    "get_roster_stats",
    "import_catalog_datasets",
    "import_roster_datasets",
    "list_beast_profiles",
    "list_catalog_profiles",
    "list_chip_profiles",
    "list_hero_profile_notes",
    "load_roster_beasts",
    "load_roster_summary",
    "setup_doomsday_tables",
]

