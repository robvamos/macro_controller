"""Record support tools installed on this workstation (without installing any)."""

from __future__ import annotations

from datetime import datetime, timezone
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any

# Make direct execution (python scripts/collect_support_inventory.py) resolve
# the top-level workstation package the same way as the application launcher.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from workstation.settings import load_settings


PACKAGE_REQUIREMENTS = {
    "keyboard": "required",
    "mouse": "required",
    "numpy": "required",
    "opencv-python": "required",
    "Pillow": "required",
    "psutil": "required",
    "PyGetWindow": "required",
    "pywin32": "required on Windows",
    "mitmproxy": "optional network observation",
}


def _run_version(command: list[str]) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=8,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"installed": False, "verified": False, "error": type(exc).__name__}
    output = (completed.stdout or completed.stderr).strip()
    return {
        "installed": completed.returncode == 0,
        "verified": completed.returncode == 0 and bool(output),
        "version_output": output.splitlines()[0] if output else "",
        "details": output,
        "return_code": completed.returncode,
    }


def collect() -> dict[str, Any]:
    settings = load_settings()
    packages = {}
    for name, requirement in PACKAGE_REQUIREMENTS.items():
        try:
            version = importlib.metadata.version(name)
            packages[name] = {"requirement": requirement, "installed": True, "verified": True, "version": version}
        except importlib.metadata.PackageNotFoundError:
            packages[name] = {"requirement": requirement, "installed": False, "verified": False}

    tesseract = settings.get("tesseractExe") or shutil.which("tesseract") or ""
    if tesseract:
        tesseract_info = _run_version([tesseract, "--version"])
        language_info = _run_version([tesseract, "--list-langs"])
        tesseract_info["path"] = str(Path(tesseract).resolve())
        tesseract_info["languages_verified"] = language_info.get("verified", False)
        tesseract_info["languages_output"] = language_info.get("details", "")
    else:
        tesseract_info = {"installed": False, "verified": False}

    tshark = settings.get("wiresharkExe") or shutil.which("tshark") or ""
    tshark_info = _run_version([tshark, "--version"]) if tshark else {"installed": False, "verified": False}
    if tshark:
        tshark_info["path"] = str(Path(tshark).resolve())

    mitmproxy_dir = Path(settings["networkObserverDir"])
    mitmdump = mitmproxy_dir / "Scripts" / "mitmdump.exe"
    mitm_info = _run_version([str(mitmdump), "--version"]) if mitmdump.is_file() else {
        "installed": False,
        "verified": False,
    }
    mitm_info["path"] = str(mitmdump) if mitmdump.is_file() else ""

    powershell = shutil.which("pwsh") or shutil.which("powershell")
    powershell_info = _run_version([powershell, "--version"]) if powershell else {
        "installed": False,
        "verified": False,
    }
    git = shutil.which("git")
    git_info = _run_version([git, "--version"]) if git else {"installed": False, "verified": False}

    configured_paths = {
        key: settings[key]
        for key in (
            "gameShortcutPath",
            "gameInstallDir",
            "bluestacksInstallDir",
            "bluestacksDataDir",
            "virtualboxInstallDir",
            "androidVmConfig",
            "androidVmDisk",
            "androidVmInstallerIso",
            "pythonExe",
            "tesseractExe",
            "wiresharkExe",
            "networkObserverDir",
        )
        if settings.get(key)
    }
    path_checks = {
        key: {"path": value, "exists": Path(value).exists()}
        for key, value in configured_paths.items()
    }
    return {
        "schema": "ddgameass.workstation-support-inventory.v1",
        "collected_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "workstation_profile": Path(settings["profileDir"]).name,
        "python": {
            "version": sys.version.split()[0],
            "executable": sys.executable,
            "architecture": sys.maxsize.bit_length() + 1,
        },
        "platform": {"system": sys.platform, "os_name": os.name},
        "tools": {
            "git": git_info,
            "powershell": powershell_info,
            "tesseract": tesseract_info,
            "tshark": tshark_info,
            "mitmproxy": mitm_info,
        },
        "python_packages": packages,
        "configured_paths": path_checks,
        "external_setup_performed": False,
    }


def main() -> int:
    settings = load_settings()
    destination = Path(settings["profileDir"]) / "support-inventory.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(collect(), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(destination)
    print(f"Inventario locale aggiornato: {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
