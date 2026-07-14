import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from subprocess import CompletedProcess

from doomsday.runtime.discovery import (
    GameRuntimeDiscoveryService,
    load_runtime_registry,
    parse_bluestacks_config,
    parse_vbox_machine_readable,
)


class GameRuntimeDiscoveryTests(unittest.TestCase):
    def test_bluestacks_parser_keeps_only_allowlisted_instance_metadata(self):
        parsed = parse_bluestacks_config(
            '\n'.join(
                (
                    'bst.installed_images="Nougat64,Pie64"',
                    'bst.instance.Pie64.adb_port="5555"',
                    'bst.instance.Pie64.cpus="4"',
                    'bst.instance.Pie64.enable_root_access="0"',
                    'bst.instance.Pie64.fb_width="1600"',
                    'bst.instance.Pie64.secret_android_id="do-not-copy"',
                    'bst.user_guid="do-not-copy"',
                )
            )
        )

        self.assertEqual(parsed["installed_images"], ["Nougat64", "Pie64"])
        self.assertEqual(parsed["instances"][0]["adb_port"], 5555)
        self.assertFalse(parsed["instances"][0]["enable_root_access"])
        self.assertNotIn("secret_android_id", parsed["instances"][0])
        self.assertNotIn("user_guid", json.dumps(parsed))

    def test_vbox_parser_handles_quoted_paths(self):
        parsed = parse_vbox_machine_readable(
            'name="Android"\nVMState="poweroff"\nCfgFile="F:\\\\_VMs\\\\Android\\\\Android.vbox"\n'
        )

        self.assertEqual(parsed["name"], "Android")
        self.assertEqual(parsed["VMState"], "poweroff")
        self.assertTrue(parsed["CfgFile"].endswith("Android.vbox"))

    def test_discovery_does_not_invoke_adb_or_start_commands(self):
        commands = []

        def runner(command):
            commands.append(command)
            if command[-2:] == ["list", "vms"]:
                return CompletedProcess(command, 0, '"Android" {abc}\n', "")
            return CompletedProcess(command, 0, 'name="Android"\nVMState="poweroff"\n', "")

        service = GameRuntimeDiscoveryService(
            command_runner=runner,
            process_provider=lambda: [],
            now_provider=lambda: datetime(2026, 7, 14, tzinfo=timezone.utc),
            hostname_provider=lambda: "TESTHOST",
        )
        result = service.discover()

        self.assertTrue(result["safety"]["starts_adb_daemon"] is False)
        self.assertTrue(all("adb" not in " ".join(command).casefold() for command in commands))

    def test_registry_loader_rejects_unknown_schema(self):
        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "registry.json"
            path.write_text(json.dumps({"schema": "other", "runtimes": []}), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_runtime_registry(path)


if __name__ == "__main__":
    unittest.main()
