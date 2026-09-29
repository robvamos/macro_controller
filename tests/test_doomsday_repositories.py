import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from doomsday import config as doomsday_config
from doomsday.catalog import market_loader
from doomsday.repositories import catalog_repository, database as dd_database, roster_repository
from doomsday.services.bootstrap_service import bootstrap_doomsday_data


class DoomsdayRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.db_path = self.base / "doomsday_roster.db"
        self.catalog_dir = self.base / "catalog"
        self.market_dir = self.catalog_dir / "market_profiles"
        self.profile_pack_dir = self.catalog_dir / "profile_pack"
        self.roster_dir = self.base / "roster"
        self.market_dir.mkdir(parents=True, exist_ok=True)
        self.profile_pack_dir.mkdir(parents=True, exist_ok=True)
        self.roster_dir.mkdir(parents=True, exist_ok=True)

        (self.market_dir / "Cynthia_Calamity.json").write_text(
            json.dumps(
                {
                    "name": "Cynthia Calamity",
                    "rarity": "Legendary",
                    "type": "Rider",
                    "roles": ["Zombie Killer"],
                    "abilities": ["Gun Rush"],
                    "talent_branches": ["Rider"],
                    "web_sources": [],
                }
            ),
            encoding="utf-8",
        )
        (self.profile_pack_dir / "beasts_registry.json").write_text(
            json.dumps({"Zanne di fuoco": {"type": "CRIT", "element": "Fuoco", "level": 56, "skills": ["Colpo"]}}),
            encoding="utf-8",
        )
        (self.profile_pack_dir / "chips_registry.json").write_text(
            json.dumps({"Matrice sacrafiamma": {"stars": 3, "bonus": "Contrattacco +50", "role": "Leader"}}),
            encoding="utf-8",
        )
        (self.profile_pack_dir / "hero_profile_cynthia.json").write_text(
            json.dumps({"name": "Cynthia Calamity", "level": 60, "beast": "Zanne di fuoco", "allies": ["Park"], "enemies": [], "skills": []}),
            encoding="utf-8",
        )
        (self.roster_dir / "total.json").write_text(
            json.dumps({"formazioni_riders": {"prima_marcia": ["Cynthia"]}}),
            encoding="utf-8",
        )
        (self.roster_dir / "bestie.json").write_text(
            json.dumps({"Toro Cadavere": {"elemento": "Terra", "ruolo_strategico": ["Critico"], "sinergie": ["Cynthia"]}}),
            encoding="utf-8",
        )

        self.patches = [
            patch.object(dd_database, "DOOMSDAY_DB_PATH", self.db_path),
            patch.object(dd_database, "LEGACY_DOOMSDAY_DB_PATH", self.base / "missing-legacy.db"),
            patch.object(dd_database, "ensure_project_directories", self._ensure_dirs),
            patch.object(doomsday_config, "CATALOG_MARKET_DIR", self.market_dir),
            patch.object(doomsday_config, "CATALOG_PROFILE_PACK_DIR", self.profile_pack_dir),
            patch.object(doomsday_config, "DOOMSDAY_ROSTER_DIR", self.roster_dir),
            patch.object(market_loader, "CATALOG_MARKET_DIR", self.market_dir),
            patch.object(market_loader, "CATALOG_PROFILE_PACK_DIR", self.profile_pack_dir),
            patch.object(market_loader, "DOOMSDAY_ROSTER_DIR", self.roster_dir),
        ]
        for active_patch in self.patches:
            active_patch.start()

    def tearDown(self):
        for active_patch in reversed(self.patches):
            active_patch.stop()
        self.tempdir.cleanup()

    def _ensure_dirs(self):
        self.base.mkdir(parents=True, exist_ok=True)

    def test_catalog_and_roster_import_populate_database(self):
        catalog_import = catalog_repository.import_catalog_datasets()
        roster_import = roster_repository.import_roster_datasets()

        self.assertEqual(catalog_import["catalog_profiles"], 1)
        self.assertEqual(catalog_import["beast_profiles"], 1)
        self.assertEqual(catalog_import["chip_profiles"], 1)
        self.assertEqual(catalog_import["hero_profile_notes"], 1)
        self.assertEqual(roster_import["roster_documents"], 1)
        self.assertEqual(roster_import["roster_beasts"], 1)

        self.assertEqual(len(catalog_repository.list_catalog_profiles()), 1)
        self.assertEqual(len(catalog_repository.list_beast_profiles()), 1)
        self.assertEqual(len(catalog_repository.list_chip_profiles()), 1)
        self.assertEqual(len(roster_repository.load_roster_beasts()), 1)

    def test_bootstrap_doomsday_data_returns_stats(self):
        result = bootstrap_doomsday_data()

        self.assertEqual(result["catalog_stats"]["CatalogProfiles"], 1)
        self.assertEqual(result["catalog_stats"]["BeastProfiles"], 1)
        self.assertEqual(result["roster_stats"]["RosterDocuments"], 1)
        self.assertEqual(result["roster_stats"]["RosterBeasts"], 1)


if __name__ == "__main__":
    unittest.main()
