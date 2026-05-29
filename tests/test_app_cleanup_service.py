import logging
import tempfile
import unittest
from pathlib import Path

from services.app_cleanup_service import cleanup_runtime_artifacts, close_logging_handlers


class AppCleanupServiceTests(unittest.TestCase):
    def test_cleanup_runtime_artifacts_removes_contents_but_preserves_root_dirs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            logs_dir = project_root / "logs"
            exports_dir = project_root / "exports"
            nested_dir = exports_dir / "session"
            logs_dir.mkdir()
            nested_dir.mkdir(parents=True)
            (logs_dir / "debug.log").write_text("debug", encoding="utf-8")
            (nested_dir / "capture.tmp").write_text("tmp", encoding="utf-8")

            summary = cleanup_runtime_artifacts(
                [logs_dir, exports_dir],
                project_root=project_root,
            )

            self.assertEqual(summary["errors"], 0)
            self.assertEqual(summary["files_removed"], 1)
            self.assertEqual(summary["dirs_removed"], 1)
            self.assertTrue(logs_dir.exists())
            self.assertTrue(exports_dir.exists())
            self.assertEqual(list(logs_dir.iterdir()), [])
            self.assertEqual(list(exports_dir.iterdir()), [])

    def test_cleanup_runtime_artifacts_refuses_paths_outside_project(self):
        with tempfile.TemporaryDirectory() as temp_dir, tempfile.TemporaryDirectory() as outside_dir:
            project_root = Path(temp_dir)
            outside_file = Path(outside_dir) / "keep.log"
            outside_file.write_text("keep", encoding="utf-8")

            summary = cleanup_runtime_artifacts([outside_file], project_root=project_root)

            self.assertEqual(summary, {"files_removed": 0, "dirs_removed": 0, "errors": 0})
            self.assertTrue(outside_file.exists())

    def test_close_logging_handlers_releases_file_handlers(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "app.log"
            handler = logging.FileHandler(log_path, encoding="utf-8")
            root_logger = logging.getLogger()
            original_handlers = root_logger.handlers[:]
            for original_handler in original_handlers:
                root_logger.removeHandler(original_handler)
            root_logger.addHandler(handler)

            try:
                close_logging_handlers()
            finally:
                for original_handler in original_handlers:
                    if original_handler not in root_logger.handlers:
                        root_logger.addHandler(original_handler)

            self.assertNotIn(handler, root_logger.handlers)


if __name__ == "__main__":
    unittest.main()
