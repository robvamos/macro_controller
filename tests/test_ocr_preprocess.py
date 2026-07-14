import unittest

from PIL import Image

from doomsday.ocr.preprocess import preprocess_for_ocr


class OcrPreprocessTests(unittest.TestCase):
    def test_grayscale_autocontrast_2x_is_deterministic(self):
        image = Image.new("RGB", (12, 8), (100, 120, 140))
        processed = preprocess_for_ocr(image, "grayscale_autocontrast_2x")

        self.assertEqual(processed.mode, "L")
        self.assertEqual(processed.size, (24, 16))

    def test_raw_returns_independent_copy(self):
        image = Image.new("RGB", (4, 4), "red")
        processed = preprocess_for_ocr(image, "raw")
        self.assertIsNot(processed, image)
        self.assertEqual(processed.getpixel((0, 0)), image.getpixel((0, 0)))


if __name__ == "__main__":
    unittest.main()
