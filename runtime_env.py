"""Runtime environment sanitization shared by project entrypoints."""

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


def sanitize_runtime_env() -> None:
    os.environ.pop("PYTHONHOME", None)

    pythonpath = os.environ.get("PYTHONPATH")
    if pythonpath:
        entries = [entry for entry in pythonpath.split(os.pathsep) if entry and not _same_path(entry)]
        if entries:
            os.environ["PYTHONPATH"] = os.pathsep.join(entries)
        else:
            os.environ.pop("PYTHONPATH", None)

    sys.path[:] = [entry for entry in sys.path if not entry or not _same_path(entry)]


__all__ = ["sanitize_runtime_env"]
