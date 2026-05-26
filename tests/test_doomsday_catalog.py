import json
import tempfile
import unittest
from pathlib import Path

from doomsday.catalog.market_loader import (
    load_beast_roster,
    load_market_profiles,
    load_profile_pack,
    load_roster_summary,
    normalize_profile_name,
)


class DoomsdayCatalogTests(unittest.TestCase):
    def test_normalize_profile_name_replaces_underscores(self):
        self.assertEqual(normalize_profile_name("Cynthia_Calamity.json"), "Cynthia Calamity")

    def test_load_market_profiles_reads_json_files(self):
        with tempfile.TemporaryDirectory() as tempdir:
            base = Path(tempdir)
            (base / "Cynthia_Calamity.json").write_text(json.dumps({"name": "Cynthia"}), encoding="utf-8")
            (base / "totaleEroi_2025.json").write_text(json.dumps({"skip": True}), encoding="utf-8")

            profiles = load_market_profiles(base)

            self.assertEqual(len(profiles), 1)
            self.assertEqual(profiles[0]["name"], "Cynthia")
            self.assertEqual(profiles[0]["_display_name"], "Cynthia Calamity")

    def test_load_roster_summary_and_beast_roster(self):
        with tempfile.TemporaryDirectory() as tempdir:
            base = Path(tempdir)
            (base / "total.json").write_text(json.dumps({"heroes": 3}), encoding="utf-8")
            (base / "bestie.json").write_text(json.dumps({"Toro Cadavere": {}}), encoding="utf-8")

            self.assertEqual(load_roster_summary(base), {"heroes": 3})
            self.assertIn("Toro Cadavere", load_beast_roster(base))

    def test_load_profile_pack_reads_known_files(self):
        with tempfile.TemporaryDirectory() as tempdir:
            base = Path(tempdir)
            for filename in ("beasts_registry.json", "chips_registry.json", "hero_profile_cynthia.json"):
                (base / filename).write_text(json.dumps({"file": filename}), encoding="utf-8")

            pack = load_profile_pack(base)

            self.assertEqual(len(pack), 3)
            self.assertEqual(pack["beasts_registry"]["file"], "beasts_registry.json")


if __name__ == "__main__":
    unittest.main()
