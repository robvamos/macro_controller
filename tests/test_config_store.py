import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import config_store


class ConfigStoreTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.config_dir = self.base / "config"
        self.styles_dir = self.config_dir / "styles"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.styles_dir.mkdir(parents=True, exist_ok=True)
        self.app_config_path = self.config_dir / "config.json"
        self.legacy_config_path = self.base / "config.json"

        self.patches = [
            patch.object(config_store, "APP_CONFIG_PATH", self.app_config_path),
            patch.object(config_store, "LEGACY_APP_CONFIG_PATH", self.legacy_config_path),
            patch.object(config_store, "style_path", lambda style_name: self.styles_dir / f"style_{style_name}.json"),
            patch.object(config_store, "legacy_style_path", lambda style_name: self.base / f"style_{style_name}.json"),
            patch.object(config_store, "ensure_project_directories", self._ensure_dirs),
        ]
        for active_patch in self.patches:
            active_patch.start()

    def tearDown(self):
        for active_patch in reversed(self.patches):
            active_patch.stop()
        self.tempdir.cleanup()

    def _ensure_dirs(self):
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.styles_dir.mkdir(parents=True, exist_ok=True)

    def test_load_app_config_creates_defaults(self):
        config = config_store.load_app_config()

        self.assertEqual(config["selected_style"], "default")
        self.assertTrue(self.app_config_path.exists())
        for style_name in config_store.DEFAULT_STYLE_MAP:
            self.assertTrue((self.styles_dir / f"style_{style_name}.json").exists())

    def test_migrate_legacy_layout_moves_old_files(self):
        self.legacy_config_path.write_text(json.dumps({"selected_style": "neon"}), encoding="utf-8")
        (self.base / "style_neon.json").write_text(json.dumps({"background_color": "#111111"}), encoding="utf-8")

        config_store.migrate_legacy_layout()

        self.assertFalse(self.legacy_config_path.exists())
        self.assertTrue(self.app_config_path.exists())
        self.assertTrue((self.styles_dir / "style_neon.json").exists())

    def test_set_and_get_window_geometry(self):
        config_store.save_app_config(dict(config_store.DEFAULT_APP_CONFIG))
        config_store.set_window_geometry("macro_manager_window", x=10, y=20, width=300, height=200)

        geometry = config_store.get_window_geometry("macro_manager_window")

        self.assertEqual(
            geometry,
            {"x": 10, "y": 20, "width": 300, "height": 200},
        )


if __name__ == "__main__":
    unittest.main()
