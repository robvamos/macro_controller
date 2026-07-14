import unittest
from unittest.mock import patch

from doomsday.services.live_roster_service import CaptureMethod, LiveRosterAcquisitionService


class RosterOcrMappingTests(unittest.TestCase):
    def test_legacy_italian_talent_keys_are_canonicalized(self):
        parsed = {
            "nome_completo_eroe": "Catherine Calamity",
            "talenti": [{"nome_talento": "Assalto"}],
            "rami_talenti_trovati": ["Danno"],
        }
        with patch("doomsday.services.live_roster_service.analyze_ocr_text", return_value=(parsed, 0)):
            observation = LiveRosterAcquisitionService().observation_from_ocr_text(
                hero_id="catherine-calamity",
                ocr_text="sample",
                source_ref="artifact:abc",
                capture_method=CaptureMethod.NATIVE_WIN32,
                runtime_id="runtime",
            )

        self.assertEqual(observation.fields["display_name"], "Catherine Calamity")
        self.assertEqual(observation.fields["talents"][0]["nome_talento"], "Assalto")
        self.assertEqual(observation.fields["talent_branches"], ["Danno"])
        self.assertNotIn("talenti", observation.fields)


if __name__ == "__main__":
    unittest.main()
