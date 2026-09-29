"""Inventario read-only dei client e degli emulatori Doomsday locali.

Il probe legge soltanto registry, file di configurazione, processi e metadati
VirtualBox. Non avvia emulatori, VM, ADB o il gioco.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
from typing import Any, Callable, Iterable, Mapping

from core.paths import DOOMSDAY_RUNTIME_REGISTRY_PATH, DOOMSDAY_SHORTCUT_PATH, WORKSTATION_SETTINGS

DEFAULT_RUNTIME_REGISTRY_PATH = DOOMSDAY_RUNTIME_REGISTRY_PATH
DEFAULT_DOOMSDAY_SHORTCUT_PATH = DOOMSDAY_SHORTCUT_PATH

_BLUESTACKS_INSTANCE_FIELDS = {
    "adb_port",
    "cpus",
    "dpi",
    "enable_root_access",
    "fb_height",
    "fb_width",
    "first_boot",
    "ram",
}
_INTEGER_FIELDS = {"adb_port", "cpus", "dpi", "fb_height", "fb_width", "ram"}


def _portable_path(value: str | Path | None) -> str:
    if value is None:
        return ""
    return str(value).replace("\\", "/").rstrip("/")


def _safe_path_exists(path: Path) -> bool:
    """Treat inaccessible optional evidence paths as absent during read-only discovery."""
    try:
        return path.exists()
    except OSError:
        return False


def _resolve_windows_shortcut(path: Path) -> dict[str, str]:
    """Resolve allowlisted launcher metadata without executing the shortcut."""

    if not _safe_path_exists(path):
        return {}
    try:
        import pywintypes
        import win32com.client
    except ImportError:
        return {}

    try:
        shortcut = win32com.client.Dispatch("WScript.Shell").CreateShortcut(str(path))
        return {
            "target_path": _portable_path(shortcut.TargetPath),
            "arguments": str(shortcut.Arguments or ""),
            "working_directory": _portable_path(shortcut.WorkingDirectory),
        }
    except (AttributeError, OSError, pywintypes.com_error):
        return {}


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1]
    return value


def parse_bluestacks_config(text: str) -> dict[str, Any]:
    """Estrae solo metadati tecnici allowlisted da ``bluestacks.conf``.

    Identificativi dispositivo, account, campagne e altri valori potenzialmente
    sensibili non entrano mai nel risultato.
    """
    instances: dict[str, dict[str, Any]] = {}
    installed_images: list[str] = []
    for raw_line in text.splitlines():
        if "=" not in raw_line:
            continue
        key, raw_value = raw_line.split("=", 1)
        value = _unquote(raw_value)
        if key == "bst.installed_images":
            installed_images = [item.strip() for item in value.split(",") if item.strip()]
            continue
        match = re.fullmatch(r"bst\.instance\.([^.]+)\.([^.]+)", key)
        if not match or match.group(2) not in _BLUESTACKS_INSTANCE_FIELDS:
            continue
        instance_name, field_name = match.groups()
        if field_name in _INTEGER_FIELDS:
            try:
                normalized: Any = int(value)
            except ValueError:
                normalized = value
        elif field_name in {"enable_root_access", "first_boot"}:
            normalized = value == "1"
        else:
            normalized = value
        instances.setdefault(instance_name, {"name": instance_name})[field_name] = normalized

    return {
        "installed_images": installed_images,
        "instances": [instances[name] for name in sorted(instances, key=str.casefold)],
    }


def parse_vbox_machine_readable(text: str) -> dict[str, str]:
    """Converte l'output machine-readable di VBoxManage in un dizionario."""
    result: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        result[key.strip().strip('"')] = _unquote(raw_value)
    return result


def _default_command_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=8,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def _read_registry_key(path: str) -> dict[str, Any]:
    if os.name != "nt":
        return {}
    try:
        import winreg

        values: dict[str, Any] = {}
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path) as key:
            index = 0
            while True:
                try:
                    name, value, _kind = winreg.EnumValue(key, index)
                except OSError:
                    break
                values[name] = value
                index += 1
        return values
    except OSError:
        return {}


def _find_uninstall_product(display_name: str) -> dict[str, Any]:
    if os.name != "nt":
        return {}
    try:
        import winreg

        roots = (
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
            r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
        )
        for root in roots:
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, root) as parent:
                    for index in range(winreg.QueryInfoKey(parent)[0]):
                        child_name = winreg.EnumKey(parent, index)
                        values = _read_registry_key(f"{root}\\{child_name}")
                        if str(values.get("DisplayName", "")).casefold() == display_name.casefold():
                            return values
            except OSError:
                continue
    except ImportError:
        pass
    return {}


def _process_snapshots() -> list[dict[str, Any]]:
    try:
        import psutil
    except ImportError:
        return []
    snapshots = []
    for process in psutil.process_iter(("name", "pid", "cmdline")):
        try:
            snapshots.append(
                {
                    "name": process.info.get("name") or "",
                    "pid": process.info.get("pid"),
                    "cmdline": tuple(process.info.get("cmdline") or ()),
                }
            )
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            continue
    return snapshots


class GameRuntimeDiscoveryService:
    """Rileva runtime noti senza alterarli né collegarsi via ADB."""

    def __init__(
        self,
        *,
        command_runner: Callable[[list[str]], subprocess.CompletedProcess[str]] | None = None,
        process_provider: Callable[[], Iterable[Mapping[str, Any]]] | None = None,
        now_provider: Callable[[], datetime] | None = None,
        hostname_provider: Callable[[], str] | None = None,
    ) -> None:
        self.command_runner = command_runner or _default_command_runner
        self.process_provider = process_provider or _process_snapshots
        self.now_provider = now_provider or (lambda: datetime.now(timezone.utc))
        self.hostname_provider = hostname_provider or socket.gethostname
        self.settings = WORKSTATION_SETTINGS

    def discover(self) -> dict[str, Any]:
        processes = list(self.process_provider())
        runtimes = [
            item
            for item in (
                self._discover_virtualbox_android(),
                self._discover_bluestacks(processes),
                self._discover_native_client(processes),
            )
            if item is not None
        ]
        active_id = next(
            (item["runtime_id"] for item in runtimes if item.get("current")),
            None,
        )
        return {
            "schema": "doomsday.runtime.registry.v1",
            "observed_at": self.now_provider().astimezone(timezone.utc).isoformat(),
            "workstation": self.hostname_provider(),
            "active_runtime_id": active_id,
            "runtimes": runtimes,
            "excluded_candidates": [
                {
                    "kind": "android_sdk_avd",
                    "status": "not_observed",
                    "reason": "Nessun AVD Android SDK rilevato durante il sopralluogo iniziale.",
                },
                {
                    "kind": "hyper_v_vm",
                    "status": "not_observed",
                    "reason": "Hyper-V è disponibile ma non risultano VM registrate per Doomsday.",
                },
                {
                    "kind": "windows_subsystem_for_android",
                    "status": "unverified",
                    "reason": "Nessuna installazione WSA associabile al gioco è stata verificata.",
                },
            ],
            "safety": {
                "read_only_probe": True,
                "starts_game_or_emulator": False,
                "starts_adb_daemon": False,
                "captures_credentials": False,
            },
        }

    def write_snapshot(self, path: str | Path = DEFAULT_RUNTIME_REGISTRY_PATH) -> Path:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(self.discover(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return destination

    def _discover_native_client(self, processes: list[Mapping[str, Any]]) -> dict[str, Any] | None:
        product = _find_uninstall_product("Doomsday")
        shortcut = _resolve_windows_shortcut(DEFAULT_DOOMSDAY_SHORTCUT_PATH)
        configured_root = self.settings.get("gameInstallDir") or ""
        install_root_value = product.get("InstallLocation") or configured_root
        if not install_root_value and shortcut.get("target_path"):
            target_path = Path(shortcut["target_path"])
            if target_path.name.casefold() == "doomsdaylastsurvivors.exe":
                install_root_value = str(target_path.parent)
        if not install_root_value:
            return None
        install_root = Path(str(install_root_value))
        if not install_root.exists() and not product:
            return None
        versions: list[tuple[tuple[int, ...], str, Path]] = []
        if install_root.exists():
            for directory in install_root.glob("Doomsday_*"):
                version_file = directory / "version.dat"
                version = (
                    version_file.read_text(encoding="utf-8-sig", errors="replace").strip()
                    if version_file.exists()
                    else directory.name.removeprefix("Doomsday_")
                )
                numeric = tuple(int(value) for value in re.findall(r"\d+", version))
                versions.append((numeric, version, directory))
        versions.sort(reverse=True)
        game_version = versions[0][1] if versions else ""
        game_dir = versions[0][2] if versions else install_root
        matching = [
            process
            for process in processes
            if str(process.get("name", "")).casefold() == "doomsday.exe"
        ]
        local_low = Path.home() / "AppData" / "LocalLow" / "IGG"
        data_roots = [
            path
            for path in (
                local_low / "Doomsday Last Survivors",
                local_low / "Doomsday_ Last Survivors",
            )
            if _safe_path_exists(path)
        ]
        return {
            "runtime_id": "native-windows",
            "kind": "native_windows_client",
            "lifecycle": "active" if matching else "available",
            "current": bool(matching),
            "version": game_version,
            "launcher_package_version": str(product.get("DisplayVersion") or ""),
            "paths": {
                "install_root": _portable_path(install_root),
                "game_directory": _portable_path(game_dir),
                "game_executable": _portable_path(game_dir / "Doomsday.exe"),
                "launcher_executable": _portable_path(install_root / "DoomsdayLastSurvivors.exe"),
                "launcher_shortcut": _portable_path(DEFAULT_DOOMSDAY_SHORTCUT_PATH),
                "launcher_shortcut_target": shortcut.get("target_path", ""),
                "launcher_working_directory": shortcut.get("working_directory", ""),
                "local_data_roots": [_portable_path(path) for path in data_roots],
            },
            "process": {
                "running": bool(matching),
                "pids": [process.get("pid") for process in matching if process.get("pid")],
            },
            "access_strategy": "launcher_shortcut_then_win32_window_capture_then_supervised_ui_ocr",
            "evidence": [
                "Windows uninstall registry",
                "version.dat del client",
                "process list read-only",
            ],
            "notes": [
                "È il runtime preferito quando la finestra Doomsday è attiva.",
                "L'avvio supportato usa il collegamento del launcher; Doomsday.exe non va eseguito direttamente.",
                "I cache locali non sono trattati come fonte canonica del roster.",
            ],
        }

    def _discover_bluestacks(self, processes: list[Mapping[str, Any]]) -> dict[str, Any] | None:
        values = _read_registry_key(r"SOFTWARE\BlueStacks_nxt")
        data_value = values.get("DataDir") or self.settings.get("bluestacksDataDir") or ""
        install_value = values.get("InstallDir") or self.settings.get("bluestacksInstallDir") or ""
        if not data_value and not install_value:
            return None
        data_dir = Path(str(data_value)) if data_value else None
        install_dir = Path(str(install_value)) if install_value else None
        user_value = values.get("UserDefinedDir")
        user_dir = Path(str(user_value)) if user_value else (
            data_dir.parent if data_dir else install_dir
        )
        config_path = user_dir / "bluestacks.conf" if user_dir else None
        if not values and (config_path is None or not config_path.exists()):
            return None
        config = (
            parse_bluestacks_config(config_path.read_text(encoding="utf-8", errors="replace"))
            if config_path is not None and config_path.exists()
            else {"installed_images": [], "instances": []}
        )
        running_instances: set[str] = set()
        for process in processes:
            if str(process.get("name", "")).casefold() not in {"hd-player.exe", "bluestacks.exe"}:
                continue
            command_line = tuple(str(item) for item in (process.get("cmdline") or ()))
            for index, value in enumerate(command_line[:-1]):
                if value == "--instance":
                    running_instances.add(command_line[index + 1])
        instances = []
        for raw_instance in config["instances"]:
            if data_dir is not None and not (data_dir / raw_instance["name"]).exists():
                continue
            instance = dict(raw_instance)
            instance["running"] = instance["name"] in running_instances
            instance["root_enabled"] = bool(instance.pop("enable_root_access", False))
            instances.append(instance)
        return {
            "runtime_id": "bluestacks5",
            "kind": "android_emulator",
            "lifecycle": "active" if running_instances else "available",
            "current": False,
            "version": str(values.get("Version") or ""),
            "paths": {
                "install_directory": _portable_path(install_dir),
                "data_directory": _portable_path(data_dir),
                "configuration": _portable_path(config_path),
            },
            "installed_images": config["installed_images"],
            "instances": instances,
            "access_strategy": "adb_screencap_only_when_instance_is_already_running",
            "evidence": ["BlueStacks registry", "allowlisted bluestacks.conf fields"],
            "notes": [
                "Il probe non esegue adb devices perché avvierebbe il daemon ADB.",
                "Con root disabilitato, il roster va letto dalla UI e non da /data/data.",
            ],
        }

    def _discover_virtualbox_android(self) -> dict[str, Any] | None:
        values = _read_registry_key(r"SOFTWARE\Oracle\VirtualBox")
        install_value = values.get("InstallDir") or self.settings.get("virtualboxInstallDir") or ""
        install_dir = Path(str(install_value)) if install_value else None
        manage_command = shutil.which("VBoxManage")
        configured_manage = Path(manage_command) if manage_command else None
        if install_dir is None and configured_manage is not None:
            install_dir = configured_manage.parent
        if install_dir is None:
            return None
        manage = install_dir / "VBoxManage.exe"
        fallback_value = self.settings.get("androidVmConfig") or ""
        fallback_config = Path(fallback_value) if fallback_value else None
        if not manage.exists():
            return None
        listed = self.command_runner([str(manage), "list", "vms"])
        if listed.returncode != 0:
            return None
        vm_names = re.findall(r'^"(.+)"\s+\{[^}]+\}$', listed.stdout, flags=re.MULTILINE)
        target = next((name for name in vm_names if "android" in name.casefold()), None)
        if target is None and fallback_config is not None and fallback_config.exists():
            target = "Android"
        if target is None:
            return None
        details_result = self.command_runner([str(manage), "showvminfo", target, "--machinereadable"])
        details = parse_vbox_machine_readable(details_result.stdout) if details_result.returncode == 0 else {}
        config_value = details.get("CfgFile")
        config_path = Path(config_value) if config_value else fallback_config
        disk_path = next(
            (Path(value) for key, value in details.items() if key.endswith("-0-0") and value.lower().endswith(".vdi")),
            config_path.with_suffix(".vdi") if config_path is not None else None,
        )
        distribution = "Android-x86"
        installer_iso = self.settings.get("androidVmInstallerIso") or ""
        if config_path is not None and config_path.exists():
            config_text = config_path.read_text(encoding="utf-8", errors="replace")
            iso_match = re.search(r'location="([^"]*android-x86[^"]*\.iso)"', config_text, re.IGNORECASE)
            if iso_match:
                installer_iso = _portable_path(iso_match.group(1))
                version_match = re.search(r"android-x86_64-([\d.]+-r\d+)\.iso", installer_iso, re.IGNORECASE)
                if version_match:
                    distribution = f"Android-x86 {version_match.group(1)}"
        state = details.get("VMState", "unknown")
        return {
            "runtime_id": "virtualbox-android-legacy",
            "kind": "virtualbox_vm",
            "lifecycle": "historical",
            "current": False,
            "version": distribution,
            "vm": {
                "name": target,
                "state": state,
                "last_state_change": details.get("VMStateChangeTime", ""),
                "memory_mb": int(details.get("memory", 0) or 0),
                "cpus": int(details.get("cpus", 0) or 0),
            },
            "paths": {
                "virtualbox_directory": _portable_path(install_dir),
                "configuration": _portable_path(config_path),
                "virtual_disk": _portable_path(disk_path),
                "installer_iso": installer_iso,
            },
            "disk": {
                "allocated_bytes": disk_path.stat().st_size if disk_path is not None and disk_path.exists() else None,
                "encryption": "disabled" if details.get("encryption") == "disabled" else "unknown",
            },
            "access_strategy": "legacy_evidence_only_do_not_start_automatically",
            "evidence": ["VBoxManage read-only metadata", "Android.vbox installer media"],
            "notes": [
                "Conferma lo stack Android ricordato dall'utente.",
                "Non è ancora verificato se Doomsday sia tuttora installato nel disco virtuale.",
            ],
        }


def load_runtime_registry(path: str | Path = DEFAULT_RUNTIME_REGISTRY_PATH) -> dict[str, Any]:
    registry_path = Path(path)
    if not registry_path.exists():
        return {}
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    if payload.get("schema") != "doomsday.runtime.registry.v1":
        raise ValueError("Schema del registro runtime non supportato.")
    if not isinstance(payload.get("runtimes"), list):
        raise ValueError("Registro runtime non valido: manca la lista runtimes.")
    return payload


__all__ = [
    "DEFAULT_DOOMSDAY_SHORTCUT_PATH",
    "DEFAULT_RUNTIME_REGISTRY_PATH",
    "GameRuntimeDiscoveryService",
    "load_runtime_registry",
    "parse_bluestacks_config",
    "parse_vbox_machine_readable",
]
