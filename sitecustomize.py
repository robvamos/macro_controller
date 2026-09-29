"""Clean inherited paths that shadow native packages with incompatible wheels.

This module is intentionally discovery-based: it contains no workstation path.
"""

from __future__ import annotations

import importlib.machinery
import os
from pathlib import Path
import sys


def _has_compatible_extension(base: Path, package: str, module: str) -> bool:
    prefix = base / package / module
    return any(Path(str(prefix) + suffix).is_file() for suffix in importlib.machinery.EXTENSION_SUFFIXES)


def _is_incomplete_overlay(value: str) -> bool:
    try:
        base = Path(value).resolve()
        for package, module in (("numpy", "_core/_multiarray_umath"), ("PIL", "_imaging")):
            if (base / package).is_dir() and not _has_compatible_extension(base, package, module):
                return True
    except (OSError, RuntimeError, ValueError):
        return False
    return False


def _sanitize_pythonpath() -> None:
    pythonpath = os.environ.get("PYTHONPATH")
    if not pythonpath:
        return
    entries = [
        entry
        for entry in pythonpath.split(os.pathsep)
        if entry and not _is_incomplete_overlay(entry)
    ]
    if entries:
        os.environ["PYTHONPATH"] = os.pathsep.join(entries)
    else:
        os.environ.pop("PYTHONPATH", None)


def _sanitize_sys_path() -> None:
    sys.path[:] = [
        entry
        for entry in sys.path
        if not entry or not _is_incomplete_overlay(entry)
    ]


_sanitize_pythonpath()
_sanitize_sys_path()
