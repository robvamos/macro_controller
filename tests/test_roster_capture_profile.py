import unittest

from doomsday.vision.roster_capture_profile import load_roster_capture_profile


class RosterCaptureProfileTests(unittest.TestCase):
    def test_validated_home_label_maps_to_reference_and_half_size(self):
        profile = load_roster_capture_profile()

        reference = profile.region_pixels("home.hero_section_label", client_size=(3440, 1440))
        half = profile.region_pixels("home.hero_section_label", client_size=(1720, 720))

        self.assertEqual(reference, (3162, 1362, 3240, 1392))
        self.assertEqual(half, (1581, 681, 1620, 696))
        self.assertEqual(profile.stage_status["hero_stats"], "visible_in_profile_roi_pending")
        self.assertEqual(profile.stage_status["hero_skills"], "full_frame_observed_roi_pending")

    def test_incompatible_aspect_ratio_is_rejected(self):
        profile = load_roster_capture_profile()
        with self.assertRaisesRegex(ValueError, "aspect ratio"):
            profile.region_pixels("home.hero_section_label", client_size=(1920, 1080))


if __name__ == "__main__":
    unittest.main()
