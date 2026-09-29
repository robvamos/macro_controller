"""Fail when deployable project files contain workstation-specific paths/state."""

from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import sys
import tomllib


ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {".py", ".ps1", ".bat", ".cmd", ".json", ".toml", ".yml", ".yaml"}
LOCAL_PATH_PATTERNS = (
    re.compile(r"(?i)\b[A-Z]:[\\/](?:_CODEX|Doomsday)(?:[\\/]|$)"),
    re.compile(r"(?i)\b[A-Z]:[\\/]Users[\\/]Public[\\/]Desktop[\\/]Doomsday\.lnk"),
)
SCAN_DIRECTORIES = (
    "core",
    "doomsday",
    "repositories",
    "services",
    "ui",
    "tools",
    "scripts",
    "tests",
    "workstation",
    "setup/windows",
)
SCAN_FILES = (
    "Avvia_Macro_Manager_come_amministratore.bat",
    "project-manifest.json",
    "pyproject.toml",
    "data/doomsday/network/observation_profile.json",
    "data/doomsday/intelligence/source_registry.overlay.json",
)
PRIVATE_TRACKED_PATHS = (
    "config/config.json",
    "config/macro_config.json",
    "data/macro_recorder.db",
    "data/doomsday/doomsday_roster.db",
    "data/doomsday/runtime/game_runtime_registry.json",
    "data/doomsday/knowledge/recovered_learning_sessions",
)
LOCAL_KNOWLEDGE_LABEL = re.compile(
    r"(?i)(?:recorded[_ -]?click|\blocale\b|antartika|musicstati|robva|roberto)"
)


def _source_files() -> list[Path]:
    files = set()
    for relative in SCAN_DIRECTORIES:
        directory = ROOT / relative
        if directory.is_dir():
            files.update(
                path
                for path in directory.rglob("*")
                if (
                    path.is_file()
                    and path.suffix.casefold() in TEXT_SUFFIXES
                    and "local" not in path.relative_to(ROOT).parts
                )
            )
    files.update(ROOT / relative for relative in SCAN_FILES if (ROOT / relative).is_file())
    knowledge = ROOT / "data/doomsday/knowledge"
    if knowledge.is_dir():
        files.update(
            path
            for path in knowledge.rglob("*.json")
            if path.is_file() and "recovered_learning_sessions" not in path.parts
        )
    return sorted(files)


def _check_local_paths() -> list[str]:
    failures = []
    for path in _source_files():
        try:
            text = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError):
            continue
        for pattern in LOCAL_PATH_PATTERNS:
            match = pattern.search(text)
            if match:
                failures.append(f"{path.relative_to(ROOT)} contains a machine-specific absolute path")
                break
    return failures


def _check_manifest() -> list[str]:
    failures = []
    manifest = json.loads((ROOT / "project-manifest.json").read_text(encoding="utf-8"))
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    if manifest.get("version") != pyproject.get("project", {}).get("version"):
        failures.append("project-manifest.json and pyproject.toml versions differ")
    for key in ("path", "local_agents", "hub_root", "project_card"):
        value = Path(manifest.get(key, ""))
        if value.is_absolute():
            failures.append(f"project-manifest.json field '{key}' must be checkout-relative")
    for interface in manifest.get("interfaces", []):
        if Path(interface.get("path", "")).is_absolute():
            failures.append(f"interface path must be checkout-relative: {interface.get('name')}")
    return failures


def _check_private_paths_are_untracked() -> list[str]:
    try:
        tracked = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=ROOT,
            capture_output=True,
            check=True,
        ).stdout.decode("utf-8", errors="replace").split("\0")
    except (OSError, subprocess.CalledProcessError):
        return ["Git is required to verify that workstation-local state is untracked"]
    tracked_set = {item.replace("\\", "/").rstrip("/") for item in tracked if item}
    failures = []
    for item in PRIVATE_TRACKED_PATHS:
        normalized = item.replace("\\", "/").rstrip("/")
        if normalized in tracked_set or any(path.startswith(normalized + "/") for path in tracked_set):
            failures.append(f"workstation-local state is still tracked: {item}")
    return failures


def _check_shared_visual_catalog() -> list[str]:
    manifest_path = ROOT / "data/doomsday/knowledge/game_elements_manifest.json"
    if not manifest_path.is_file():
        return []
    try:
        records = json.loads(manifest_path.read_text(encoding="utf-8-sig")).get("game_elements", [])
    except (OSError, json.JSONDecodeError) as exc:
        return [f"shared visual manifest cannot be read: {type(exc).__name__}"]
    failures = []
    for record in records:
        if not isinstance(record, dict):
            failures.append("shared visual manifest contains a non-object record")
            continue
        label = str(record.get("name") or "")
        if LOCAL_KNOWLEDGE_LABEL.search(label):
            failures.append(f"shared visual element {record.get('id')} has a workstation-specific name")
        paths = record.get("image_paths") or [record.get("image_path")]
        for relative in paths:
            if not isinstance(relative, str) or not relative:
                continue
            if Path(relative).is_absolute() or LOCAL_KNOWLEDGE_LABEL.search(Path(relative).name):
                failures.append(f"shared visual element {record.get('id')} has a non-portable image path")
                continue
            candidate = (ROOT / "data/doomsday/knowledge" / relative).resolve()
            if ROOT not in candidate.parents or not candidate.is_file():
                failures.append(f"shared visual element {record.get('id')} references a missing image")
    return failures


def main() -> int:
    failures = (
        _check_local_paths()
        + _check_manifest()
        + _check_private_paths_are_untracked()
        + _check_shared_visual_catalog()
    )
    if failures:
        print("Portability validation failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print("Portable project paths, manifest versions and local-state tracking verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
