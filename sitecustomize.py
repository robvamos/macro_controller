"""Project-wide Python runtime sanitization.

This workspace sometimes inherits a global PYTHONPATH entry pointing at
`F:/_CODEX/tools/pdf/python-packages`, which bundles a partial Pillow layout
used by unrelated tooling. When that path comes before the real site-packages,
imports such as `from PIL import Image` fail because `_imaging` is missing.

Python imports `sitecustomize` automatically during startup, so this is the
lowest-friction place to remove that foreign path for every app, tool, and
test command running inside DDassistant.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys


BROKEN_PDF_PYTHONPACKAGES = Path("F:/_CODEX/tools/pdf/python-packages").resolve()


def _same_path(value: str) -> bool:
    try:
        return Path(value).resolve() == BROKEN_PDF_PYTHONPACKAGES
    except Exception:
        return False


def _sanitize_pythonpath_env() -> None:
    pythonpath = os.environ.get("PYTHONPATH")
    if not pythonpath:
        return
    entries = [entry for entry in pythonpath.split(os.pathsep) if entry and not _same_path(entry)]
    if entries:
        os.environ["PYTHONPATH"] = os.pathsep.join(entries)
    else:
        os.environ.pop("PYTHONPATH", None)


def _sanitize_sys_path() -> None:
    sys.path[:] = [entry for entry in sys.path if not entry or not _same_path(entry)]


_sanitize_pythonpath_env()
_sanitize_sys_path()
