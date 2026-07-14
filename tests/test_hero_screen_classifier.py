import unittest

from doomsday.vision.hero_screen_classifier import classify_hero_screen


class HeroScreenClassifierTests(unittest.TestCase):
    def test_classifies_observed_hero_screens_from_ocr_anchors(self):
        cases = {
            "Punti talento: 0 Consigliato Squadra rider": "hero_talents_detail_view",
            "Info abilità Eroe Battaglia Anteprima miglioramento": "hero_skills_detail_view",
            "Armamenti dell'Eroe Panoramica degli attributi di armamento Attributi di base": "hero_equipment_view",
            "Armamenti dell'Eroe In possesso: 10 Effetti abilità": "hero_equipment_item_detail_view",
            "Livello 60 ESP DAN DIF PS Squadra 230000": "hero_profile_view",
            "Zaino Alleanza Bestia Eroe Regione": "home_view",
        }
        for text, expected in cases.items():
            with self.subTest(expected=expected):
                result = classify_hero_screen(text)
                self.assertEqual(result.node_id, expected)
                self.assertEqual(result.status, "labeled")

    def test_unknown_text_stays_unlabeled(self):
        result = classify_hero_screen("testo parziale senza ancore")
        self.assertEqual(result.node_id, "unknown_main_view")
        self.assertEqual(result.status, "observed_unlabeled")


if __name__ == "__main__":
    unittest.main()
