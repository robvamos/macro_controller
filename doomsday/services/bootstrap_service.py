"""Bootstrap del database Doomsday e import iniziale dataset."""

from __future__ import annotations

from doomsday.repositories.catalog_repository import get_catalog_stats, import_catalog_datasets
from doomsday.repositories.database import setup_doomsday_tables
from doomsday.repositories.roster_repository import get_roster_stats, import_roster_datasets


def bootstrap_doomsday_data() -> dict:
    """Prepara il DB Doomsday e importa catalogo + roster locale."""
    setup_doomsday_tables()
    catalog_import = import_catalog_datasets()
    roster_import = import_roster_datasets()
    return {
        "catalog_import": catalog_import,
        "roster_import": roster_import,
        "catalog_stats": get_catalog_stats(),
        "roster_stats": get_roster_stats(),
    }
