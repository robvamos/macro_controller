import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from core import windows_elevation

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MACRO_MANAGER_SCRIPT = str(PROJECT_ROOT / "gui_macro_manager.py")


class WindowsElevationTests(unittest.TestCase):
    def test_target_requires_elevation_when_target_is_admin_and_app_is_not(self):
        with (
            patch.object(windows_elevation, "is_current_process_elevated", return_value=False),
            patch.object(windows_elevation, "get_process_ids_by_name", return_value=[101, 202]),
            patch.object(windows_elevation, "_get_process_elevation", side_effect=[None, True]),
        ):
            result = windows_elevation.target_requires_elevation("Doomsday.exe")

        self.assertTrue(result["requires_restart"])
        self.assertEqual(result["reason"], "target_process_elevated")

    def test_target_requires_elevation_skips_restart_when_app_is_already_admin(self):
        with patch.object(windows_elevation, "is_current_process_elevated", return_value=True):
            result = windows_elevation.target_requires_elevation("Doomsday.exe")

        self.assertFalse(result["requires_restart"])
        self.assertEqual(result["reason"], "current_process_already_elevated")

    def test_build_relaunch_command_prefers_pythonw_for_script_runs(self):
        fake_python = str(PROJECT_ROOT / ".venv" / "Scripts" / "python.exe")
        fake_script = MACRO_MANAGER_SCRIPT

        with (
            patch.object(windows_elevation.sys, "frozen", False, create=True),
            patch.object(windows_elevation.sys, "executable", fake_python),
            patch.object(windows_elevation.sys, "argv", [fake_script, "--debug"]),
            patch.object(windows_elevation.Path, "exists", return_value=True),
        ):
            executable, parameters, working_directory = windows_elevation._build_relaunch_command()

        self.assertTrue(executable.endswith("pythonw.exe"))
        self.assertIn("gui_macro_manager.py", parameters)
        self.assertIn("--debug", parameters)
        self.assertEqual(Path(working_directory), PROJECT_ROOT)

    def test_close_duplicate_macro_manager_instances_terminates_matching_processes(self):
        duplicate = Mock()
        duplicate.info = {
            "pid": 222,
            "cmdline": ["pythonw.exe", MACRO_MANAGER_SCRIPT],
        }
        duplicate.pid = 222
        duplicate.is_running.side_effect = [False]

        current = Mock()
        current.info = {
            "pid": 111,
            "cmdline": ["pythonw.exe", MACRO_MANAGER_SCRIPT],
        }
        current.pid = 111

        with (
            patch.object(windows_elevation, "is_current_process_elevated", return_value=True),
            patch.object(windows_elevation, "_get_current_script_path", return_value=MACRO_MANAGER_SCRIPT.casefold()),
            patch.object(windows_elevation.psutil, "process_iter", return_value=[current, duplicate]),
            patch.object(windows_elevation, "_matches_macro_manager_instance", return_value=True),
            patch.object(windows_elevation, "get_macro_manager_window_process_ids", return_value=[]),
        ):
            closed = windows_elevation.close_duplicate_macro_manager_instances(current_pid=111)

        duplicate.terminate.assert_called_once()
        self.assertEqual(closed, [222])

    def test_enforce_single_instance_rejects_secondary_non_elevated_instance(self):
        duplicate = Mock()
        duplicate.info = {"pid": 222, "cmdline": ["pythonw.exe", MACRO_MANAGER_SCRIPT]}
        duplicate.pid = 222

        with (
            patch.object(windows_elevation, "_get_current_script_path", return_value=MACRO_MANAGER_SCRIPT.casefold()),
            patch.object(windows_elevation.psutil, "process_iter", return_value=[duplicate]),
            patch.object(windows_elevation, "_matches_macro_manager_instance", return_value=True),
            patch.object(windows_elevation, "is_current_process_elevated", return_value=False),
        ):
            result = windows_elevation.enforce_single_macro_manager_instance(current_pid=111)

        self.assertFalse(result["keep_current"])
        self.assertEqual(result["duplicate_pids"], [222])

    def test_collect_duplicates_includes_window_titled_instances(self):
        proc = Mock()
        proc.info = {"pid": 333, "cmdline": []}
        proc.pid = 333

        with (
            patch.object(windows_elevation.psutil, "process_iter", return_value=[]),
            patch.object(windows_elevation, "get_macro_manager_window_process_ids", return_value=[333]),
            patch.object(windows_elevation.psutil, "Process", return_value=proc),
        ):
            duplicates = windows_elevation._collect_duplicate_macro_manager_processes(
                current_pid=111,
                current_script=MACRO_MANAGER_SCRIPT.casefold(),
            )

        self.assertEqual([item.pid for item in duplicates], [333])


if __name__ == "__main__":
    unittest.main()
