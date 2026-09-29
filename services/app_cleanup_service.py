"""Runtime cleanup helpers for logs and temporary application artifacts."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Iterable

from core.paths import (
    DOOMSDAY_OCR_OUTPUT_DIR,
    DOOMSDAY_SCREENSHOTS_DIR,
    EXPORTS_DIR,
    LOGS_DIR,
    PROJECT_ROOT,
)


DEFAULT_RUNTIME_CLEANUP_DIRS = (
    LOGS_DIR,
    EXPORTS_DIR,
    DOOMSDAY_SCREENSHOTS_DIR,
    DOOMSDAY_OCR_OUTPUT_DIR,
)


def cleanup_runtime_artifacts(
    paths: Iterable[Path | str] | None = None,
    *,
    project_root: Path | str = PROJECT_ROOT,
) -> dict[str, int]:
    """Remove files generated during a local app run while preserving the root folders."""
    root = Path(project_root).resolve()
    summary = {"files_removed": 0, "dirs_removed": 0, "errors": 0}

    for raw_path in paths or DEFAULT_RUNTIME_CLEANUP_DIRS:
        target = Path(raw_path)
        if not target.is_absolute():
            target = root / target
        target = target.resolve()
        if not _is_inside(target, root) or not target.exists():
            continue
        if target.is_file():
            _remove_file(target, summary)
            continue
        for child in list(target.iterdir()):
            _remove_path(child, summary)

    return summary


def close_logging_handlers() -> None:
    """Flush and close logging handlers so log files can be deleted on Windows."""
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        try:
            handler.flush()
            handler.close()
        except Exception:
            pass
    logging.shutdown()


def _remove_path(path: Path, summary: dict[str, int]) -> None:
    try:
        if path.is_dir():
            shutil.rmtree(path)
            summary["dirs_removed"] += 1
        else:
            path.unlink()
            summary["files_removed"] += 1
    except FileNotFoundError:
        pass
    except Exception:
        summary["errors"] += 1


def _remove_file(path: Path, summary: dict[str, int]) -> None:
    try:
        path.unlink()
        summary["files_removed"] += 1
    except FileNotFoundError:
        pass
    except Exception:
        summary["errors"] += 1


def _is_inside(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


__all__ = [
    "DEFAULT_RUNTIME_CLEANUP_DIRS",
    "cleanup_runtime_artifacts",
    "close_logging_handlers",
]
