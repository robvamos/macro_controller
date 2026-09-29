"""Remove incompatible third-party package overlays from inherited Python paths."""

from __future__ import annotations

import importlib.machinery
import os
from pathlib import Path
import sys


_EXTENSION_PROBES = (
    (Path("numpy"), Path("_core") / "_multiarray_umath"),
    (Path("PIL"), Path("_imaging")),
)


def _has_runtime_extension(base: Path, package: Path, module: Path) -> bool:
    prefix = base / package / module
    return any(Path(str(prefix) + suffix).is_file() for suffix in importlib.machinery.EXTENSION_SUFFIXES)


def _is_incomplete_dependency_overlay(value: str) -> bool:
    try:
        base = Path(value).resolve()
        for package, module in _EXTENSION_PROBES:
            if (base / package).is_dir() and not _has_runtime_extension(base, package, module):
                return True
    except (OSError, RuntimeError, ValueError):
        return False
    return False


def sanitize_runtime_env() -> None:
    """Drop only paths that shadow NumPy/Pillow with ABI-incompatible copies."""
    pythonpath = os.environ.get("PYTHONPATH")
    if pythonpath:
        entries = [
            entry
            for entry in pythonpath.split(os.pathsep)
            if entry and not _is_incomplete_dependency_overlay(entry)
        ]
        if entries:
            os.environ["PYTHONPATH"] = os.pathsep.join(entries)
        else:
            os.environ.pop("PYTHONPATH", None)

    sys.path[:] = [
        entry
        for entry in sys.path
        if not entry or not _is_incomplete_dependency_overlay(entry)
    ]


__all__ = ["sanitize_runtime_env"]
