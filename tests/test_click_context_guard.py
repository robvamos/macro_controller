import unittest
from unittest.mock import patch

from PIL import Image

from doomsday.vision.click_context_guard import ClickContextGuard, ClickContextGuardConfig, compute_context_similarity


class ClickContextGuardTests(unittest.TestCase):
    def test_similarity_is_high_for_equal_images(self):
        image = Image.new("L", (24, 24), color=120)
        score = compute_context_similarity(image, image, resize_px=16)
        self.assertAlmostEqual(score, 1.0, places=4)

    def test_similarity_is_lower_for_different_images(self):
        reference = Image.new("L", (24, 24), color=10)
        candidate = Image.new("L", (24, 24), color=240)
        score = compute_context_similarity(reference, candidate, resize_px=16)
        self.assertLess(score, 0.4)

    def test_similarity_tolerates_small_translation(self):
        reference = Image.new("L", (24, 24), color=0)
        for x in range(8, 16):
            for y in range(8, 16):
                reference.putpixel((x, y), 255)

        shifted = Image.new("L", (24, 24), color=0)
        for x in range(9, 17):
            for y in range(8, 16):
                if x < 24:
                    shifted.putpixel((x, y), 255)

        score = compute_context_similarity(reference, shifted, resize_px=24, translation_tolerance_px=2)
        self.assertGreater(score, 0.9)

    def test_verify_or_prime_sets_reference_then_uses_threshold(self):
        guard = ClickContextGuard(ClickContextGuardConfig(enabled=True, min_similarity=0.6))
        first = Image.new("L", (24, 24), color=100)
        second = Image.new("L", (24, 24), color=110)

        guard.prime_reference = lambda *args, **kwargs: guard.reference_images.append(first)

        with patch(
            "doomsday.vision.click_context_guard.capture_context_image",
            return_value=second,
        ):
            primed = guard.verify_or_prime(100, 100)
            checked = guard.verify_or_prime(120, 120)

        self.assertTrue(primed["primed"])
        self.assertTrue(checked["ok"])

    def test_reset_clears_previous_reference(self):
        guard = ClickContextGuard(ClickContextGuardConfig(enabled=True))
        guard.reference_images = [Image.new("L", (8, 8), color=50)]
        guard.reference_position = (10, 20)

        guard.reset()

        self.assertEqual(guard.reference_images, [])
        self.assertIsNone(guard.reference_position)

    def test_add_reference_image_keeps_alternative_reference(self):
        guard = ClickContextGuard(ClickContextGuardConfig(enabled=True, max_reference_images=3))
        primary = Image.new("L", (8, 8), color=50)
        alternative = Image.new("L", (8, 8), color=90)

        guard.set_reference_image(primary, abs_x=10, abs_y=20)
        guard.add_reference_image(alternative)

        self.assertEqual(len(guard.reference_images), 2)
        self.assertEqual(guard.reference_position, (10, 20))
        self.assertTrue(guard.fixed_reference_mode)

    def test_guard_can_accumulate_multiple_compatible_references(self):
        guard = ClickContextGuard(ClickContextGuardConfig(enabled=True, min_similarity=0.5, max_reference_images=3))
        first = Image.new("L", (24, 24), color=100)
        second = Image.new("L", (24, 24), color=105)
        third = Image.new("L", (24, 24), color=108)

        with patch(
            "doomsday.vision.click_context_guard.capture_context_image",
            side_effect=[first.copy(), second.copy(), second.copy(), third.copy(), third.copy()],
        ):
            guard.verify_or_prime(100, 100)
            guard.verify_or_prime(100, 100)
            guard.verify_or_prime(100, 100)

        self.assertLessEqual(len(guard.reference_images), 3)
        self.assertGreaterEqual(len(guard.reference_images), 2)

    def test_verify_or_prime_emits_preview_before_final_score(self):
        guard = ClickContextGuard(ClickContextGuardConfig(enabled=True, min_similarity=0.6))
        reference = Image.new("L", (24, 24), color=100)
        candidate = Image.new("L", (24, 24), color=110)
        preview_payloads = []

        guard.reference_images = [reference]
        with patch(
            "doomsday.vision.click_context_guard.capture_context_image",
            return_value=candidate,
        ):
            checked = guard.verify_or_prime(120, 120, preview_callback=preview_payloads.append)

        self.assertEqual(len(preview_payloads), 1)
        self.assertIsNone(preview_payloads[0]["score"])
        self.assertIn("candidate_preview", preview_payloads[0])
        self.assertTrue(checked["ok"])


if __name__ == "__main__":
    unittest.main()
