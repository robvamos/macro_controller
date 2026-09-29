"""Portable, per-workstation settings for DDGameAss.

Configuration files are local to a checkout. Relative paths are always resolved
from the repository root, never from the caller's current directory.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import socket
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = Path(__file__).with_name("settings.schema.json")
SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
PROFILE_ENV = SCHEMA["profileEnv"]
CONFIG_ENV = SCHEMA["configEnv"]


def profile_directory(root: str | Path, profile: str) -> Path:
    if (
        not isinstance(profile, str)
        or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", profile)
        or re.fullmatch(r"con|prn|aux|nul|com[1-9]|lpt[1-9]", profile)
    ):
        raise ValueError("Invalid workstation profile identifier.")
    return Path(root) / "workstation" / "local" / profile


def _resolve_selector(root: Path, env: Mapping[str, str], explicit_file: str | Path | None,
                      hostname: str | None) -> tuple[Path, Path, bool, bool]:
    selected_file = explicit_file if explicit_file is not None else env.get(CONFIG_ENV)
    selected_profile = env.get(PROFILE_ENV) if selected_file is None else None
    is_explicit = selected_file is not None or selected_profile is not None

    if selected_file is not None:
        if not isinstance(selected_file, (str, Path)) or not str(selected_file).strip():
            raise ValueError("Invalid workstation configuration selector.")
        raw = os.path.expandvars(os.path.expanduser(str(selected_file)))
        if re.search(r"[\x00-\x1f]", raw):
            raise ValueError("Invalid workstation configuration selector.")
        target = Path(raw)
        if not target.is_absolute():
            target = root / target
        target = target.resolve()
        local_root = (root / "workstation" / "local").resolve()
        profile_root = target.parent
        if target.name == "settings.json" and profile_root.parent == local_root:
            directory = profile_root
        else:
            directory = Path(str(target) + ".runtime")
        return target, directory, True, is_explicit

    if selected_profile is not None:
        directory = profile_directory(root, selected_profile)
        return directory / "settings.json", directory, True, is_explicit

    host = (socket.gethostname() if hostname is None else hostname).strip().lower()
    try:
        host_directory = profile_directory(root, host)
    except ValueError:
        host_directory = None
    if host_directory is not None and (host_directory / "settings.json").is_file():
        return host_directory / "settings.json", host_directory, True, False

    legacy_directory = root / "workstation" / "local"
    legacy_file = legacy_directory / "settings.json"
    if legacy_file.is_file():
        return legacy_file, legacy_directory, False, False

    # A fresh clone gets a host-specific runtime location without needing a
    # machine-specific value in Git. Its profile file can be initialized later.
    if host_directory is None:
        raise ValueError("Unable to derive a valid workstation profile name.")
    return host_directory / "settings.json", host_directory, True, False


def load_settings(
    *,
    root: str | Path = ROOT,
    env: Mapping[str, str] | None = None,
    file: str | Path | None = None,
    overrides: Mapping[str, Any] | None = None,
    hostname: str | None = None,
) -> dict[str, str]:
    """Load validated local settings, with explicit overrides taking priority."""
    root = Path(root).resolve()
    env = os.environ if env is None else env
    overrides = {} if overrides is None else overrides
    if not isinstance(overrides, Mapping):
        raise ValueError("Invalid workstation settings.")

    target, directory, isolated, is_explicit = _resolve_selector(root, env, file, hostname)
    try:
        local = json.loads(target.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        if is_explicit:
            raise ValueError("Selected workstation configuration is missing.") from None
        local = {}
    except (OSError, json.JSONDecodeError):
        raise ValueError("Invalid workstation configuration.") from None

    if not isinstance(local, dict):
        raise ValueError("Invalid workstation configuration.")
    properties = SCHEMA["properties"]
    if set(local) - properties.keys() or set(overrides) - properties.keys():
        raise ValueError("Invalid or unknown workstation settings.")

    result: dict[str, str] = {
        "projectRoot": str(root),
        "profileDir": str(directory.resolve()),
    }
    for key, rule in properties.items():
        default = rule.get("default", "")
        if isolated and "profileDefault" in rule:
            default = str(directory / rule["profileDefault"])
        variable = rule.get("env")
        value = overrides.get(
            key,
            env.get(variable, local.get(key, default)) if variable else local.get(key, default),
        )
        if rule["type"] != "string" or not isinstance(value, str):
            raise ValueError("Invalid workstation setting: " + key)
        value = os.path.expandvars(os.path.expanduser(value))
        if len(value.strip()) < rule.get("minLength", 0) or re.search(r"[\x00-\x1f]", value):
            raise ValueError("Invalid workstation setting: " + key)
        if rule.get("kind") == "path" and value:
            path = Path(value)
            if not path.is_absolute():
                path = root / path
            value = str(path.resolve())
        result[key] = value
    return result


def initialize(profile: str | None = None, *, root: str | Path = ROOT) -> Path:
    """Create one local profile from the portable example without overwriting it."""
    if profile is None:
        profile = socket.gethostname().strip().lower()
    directory = profile_directory(Path(root).resolve(), profile)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / "settings.json"
    with target.open("x", encoding="utf-8") as handle:
        handle.write(Path(__file__).with_name("settings.example.json").read_text(encoding="utf-8"))
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--init", metavar="PROFILE", nargs="?", const=socket.gethostname().lower())
    parser.add_argument("--get", metavar="SETTING", choices=sorted(SCHEMA["properties"]))
    args = parser.parse_args(argv)
    try:
        if args.init is not None:
            initialize(args.init)
            print("Local profile created; add workstation-specific values there.")
        else:
            settings = load_settings()
            if args.get:
                print(settings[args.get])
            else:
                print("Workstation configuration valid (values omitted).")
    except (ValueError, OSError) as exc:
        message = str(exc) if isinstance(exc, ValueError) else "Could not read or create the workstation profile."
        parser.exit(1, f"Workstation configuration failed: {message}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
