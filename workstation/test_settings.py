"""Regression checks for isolated workstation profiles and portable paths."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest

from settings import CONFIG_ENV, PROFILE_ENV, initialize, load_settings


class WorkstationSettingsTests(unittest.TestCase):
    def test_separate_profiles_resolve_paths_from_checkout_not_caller(self):
        with tempfile.TemporaryDirectory(prefix="DD assistant second workstation ") as temp:
            root = Path(temp) / "checkout with spaces"
            root.mkdir()
            initialize("desktop", root=root)
            initialize("laptop", root=root)

            desktop_file = root / "workstation/local/desktop/settings.json"
            laptop_file = root / "workstation/local/laptop/settings.json"
            desktop_file.write_text(
                json.dumps({"workspaceRoot": "workspace one", "gameShortcutPath": "Games/Do Not Share.lnk"}),
                encoding="utf-8",
            )
            laptop_file.write_text(json.dumps({"workspaceRoot": "workspace two"}), encoding="utf-8")

            previous = Path.cwd()
            other_cwd = Path(temp) / "different launch directory"
            other_cwd.mkdir()
            try:
                os.chdir(other_cwd)
                desktop = load_settings(root=root, env={PROFILE_ENV: "desktop"})
                laptop = load_settings(root=root, env={PROFILE_ENV: "laptop"})
            finally:
                os.chdir(previous)

            self.assertEqual(desktop["projectRoot"], str(root.resolve()))
            self.assertEqual(desktop["workspaceRoot"], str((root / "workspace one").resolve()))
            self.assertEqual(desktop["gameShortcutPath"], str((root / "Games/Do Not Share.lnk").resolve()))
            self.assertNotEqual(desktop["runtimeDir"], laptop["runtimeDir"])
            self.assertTrue(desktop["runtimeDir"].startswith(str(root / "workstation/local/desktop")))
            self.assertTrue(laptop["runtimeDir"].startswith(str(root / "workstation/local/laptop")))

    def test_explicit_config_override_and_environment_precedence(self):
        with tempfile.TemporaryDirectory(prefix="DD assistant settings ") as temp:
            root = Path(temp)
            initialize("desktop", root=root)
            target = root / "workstation/local/desktop/settings.json"
            target.write_text(
                json.dumps({"gameInstallDir": "C:/Local/Game"}),
                encoding="utf-8",
            )

            settings = load_settings(
                root=root,
                env={
                    PROFILE_ENV: "missing",
                    CONFIG_ENV: "workstation/local/desktop/settings.json",
                    "DDGAMEASS_GAME_INSTALL_DIR": "D:/Environment/Game",
                },
                overrides={"gameInstallDir": "E:/Override/Game"},
            )
            self.assertEqual(settings["gameInstallDir"], str(Path("E:/Override/Game").resolve()))
            self.assertEqual(settings["runtimeDir"], str((target.parent / "runtime").resolve()))

            from_environment = load_settings(
                root=root,
                env={PROFILE_ENV: "desktop", "DDGAMEASS_GAME_INSTALL_DIR": "D:/Environment/Game"},
            )
            self.assertEqual(from_environment["gameInstallDir"], str(Path("D:/Environment/Game").resolve()))

    def test_hostname_profile_is_detected_without_disclosing_it(self):
        with tempfile.TemporaryDirectory(prefix="DD assistant host ") as temp:
            root = Path(temp)
            initialize("workstation-a", root=root)
            loaded = load_settings(root=root, env={}, hostname="WORKSTATION-A")
            self.assertEqual(loaded["profileDir"], str((root / "workstation/local/workstation-a").resolve()))

    def test_missing_invalid_profiles_and_unknown_settings_fail_closed(self):
        with tempfile.TemporaryDirectory(prefix="DD assistant invalid ") as temp:
            root = Path(temp)
            for profile in ("missing", "../desktop", "", "a/b", "con"):
                with self.subTest(profile=profile), self.assertRaises(ValueError):
                    load_settings(root=root, env={PROFILE_ENV: profile})
            with self.assertRaises(ValueError):
                load_settings(root=root, env={CONFIG_ENV: "workstation/local/missing/settings.json"})
            with self.assertRaises(ValueError):
                load_settings(root=root, env={}, file="")

            initialize("desktop", root=root)
            target = root / "workstation/local/desktop/settings.json"
            target.write_text('{"unknownSecret":"must not be accepted"}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Invalid or unknown"):
                load_settings(root=root, env={PROFILE_ENV: "desktop"})

    def test_initialization_preserves_existing_profile(self):
        with tempfile.TemporaryDirectory(prefix="DD assistant preserve ") as temp:
            root = Path(temp)
            path = initialize("desktop", root=root)
            original = path.read_text(encoding="utf-8")
            with self.assertRaises(FileExistsError):
                initialize("desktop", root=root)
            self.assertEqual(path.read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main()
