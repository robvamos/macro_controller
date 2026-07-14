import subprocess
import sys
import unittest
from pathlib import Path

from PIL import Image

from doomsday.ocr.engine import OcrEngineError, TesseractCliEngine


TSV = (
    "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
    "5\t1\t1\t1\t1\t1\t10\t20\t40\t12\t92.45\tEroe\n"
    "5\t1\t1\t1\t2\t1\t55\t40\t30\t12\t80.00\tATK\n"
)


class TesseractEngineTests(unittest.TestCase):
    def test_recognize_uses_png_stdin_and_parses_tsv_confidence(self):
        calls = []

        def runner(command, **kwargs):
            calls.append((command, kwargs))
            return subprocess.CompletedProcess(command, 0, TSV.encode(), b"")

        engine = TesseractCliEngine(Path(sys.executable), runner=runner)
        result = engine.recognize(Image.new("RGB", (100, 40), "white"), language="ita+eng", page_segmentation_mode=11)

        command, kwargs = calls[0]
        self.assertIn("ita+eng", command)
        self.assertIn("11", command)
        self.assertEqual(command[-1], "tsv")
        self.assertTrue(kwargs["input"].startswith(b"\x89PNG"))
        self.assertEqual(result.text, "Eroe\nATK")
        self.assertAlmostEqual(result.mean_confidence, 86.225)
        self.assertEqual(result.words[0].left, 10)

    def test_timeout_and_nonzero_exit_are_errors(self):
        def timeout_runner(command, **kwargs):
            raise subprocess.TimeoutExpired(command, kwargs["timeout"])

        timeout_engine = TesseractCliEngine(Path(sys.executable), runner=timeout_runner, timeout_seconds=1)
        with self.assertRaisesRegex(OcrEngineError, "timed out"):
            timeout_engine.recognize(Image.new("RGB", (10, 10)))

        def failed_runner(command, **kwargs):
            return subprocess.CompletedProcess(command, 2, b"", b"missing language")

        failed_engine = TesseractCliEngine(Path(sys.executable), runner=failed_runner)
        with self.assertRaisesRegex(OcrEngineError, "missing language"):
            failed_engine.recognize(Image.new("RGB", (10, 10)))


if __name__ == "__main__":
    unittest.main()
