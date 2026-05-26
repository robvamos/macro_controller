import tempfile
import unittest
from pathlib import Path

from doomsday.ocr.hero_extractor import analyze_ocr_text, process_hero_images, save_hero_data_to_json
from doomsday.ocr.stats_parser import parse_stats_from_ocr
from doomsday.ocr.talents_parser import parse_talents_from_ocr


class DoomsdayOcrTests(unittest.TestCase):
    def test_parse_stats_from_ocr_extracts_values(self):
        text = "ATK 1200 DEF 950 HP 18000 SPD 122 CRT 11.5 RES 22.1"

        stats, defaults_used = parse_stats_from_ocr(text)

        self.assertEqual(stats["ATK"], 1200)
        self.assertEqual(stats["DEF"], 950)
        self.assertEqual(stats["HP"], 18000)
        self.assertEqual(stats["SPD"], 122)
        self.assertEqual(stats["CRT"], 11.5)
        self.assertEqual(stats["RES"], 22.1)
        self.assertGreater(defaults_used, 0)

    def test_parse_talents_from_ocr_extracts_branch_and_levels(self):
        text = "\n".join(
            [
                "Offensivo",
                "Gun Rush 3/5 infligge danno bonus",
                "Supporto",
                "Charm Shot 1/5 riduce difesa",
                "Cynthia Calamity",
            ]
        )

        parsed = parse_talents_from_ocr(text)

        self.assertEqual(parsed["nome_completo_eroe"], "Cynthia Calamity")
        self.assertIn("Offensivo", parsed["rami_talenti_trovati"])
        self.assertIn("Supporto", parsed["rami_talenti_trovati"])
        self.assertEqual(len(parsed["talenti"]), 2)
        self.assertEqual(parsed["talenti"][0]["livello_attuale"], 3)
        self.assertEqual(parsed["talenti"][1]["livello_massimo"], 5)

    def test_process_hero_images_combines_stats_and_talents(self):
        image_files = ["cynthia_stats.png", "cynthia_talents.png"]

        def fake_ocr(image_path):
            if "stats" in image_path.name:
                return "ATK 1000 DEF 800 HP 15000 SPD 110"
            return "Offensivo\nDual Mayhem 2/5 bonus critico\nCynthia Calamity"

        hero_data, defaults_used = process_hero_images("cynthia", image_files, image_to_text=fake_ocr)

        self.assertEqual(hero_data["ATK"], 1000)
        self.assertEqual(hero_data["SPD"], 110)
        self.assertEqual(hero_data["nome_completo_eroe"], "Cynthia Calamity")
        self.assertEqual(hero_data["talenti"][0]["nome_talento"], "Dual Mayhem")
        self.assertGreaterEqual(defaults_used, 0)

    def test_analyze_ocr_text_falls_back_to_talents(self):
        parsed, _ = analyze_ocr_text("Rider\nGun Rush 1/5 bonus\nCynthia Calamity")
        self.assertIn("talenti", parsed)

    def test_save_hero_data_to_json_writes_file(self):
        with tempfile.TemporaryDirectory() as tempdir:
            output_path = save_hero_data_to_json({"ATK": 100}, "cynthia", output_dir=tempdir)
            self.assertTrue(Path(output_path).exists())


if __name__ == "__main__":
    unittest.main()
