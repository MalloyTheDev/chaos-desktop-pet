from __future__ import annotations

"""Safe, project-local JSON persistence helpers.

All writes are atomic (write to a temp file in the same directory, then
os.replace) so a crash mid-write can never corrupt an existing save. Reads
never raise: a missing or corrupt file logs a warning and returns the caller's
default. Runtime writes are restricted to the project's data/logs directories.
"""

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from . import config

LOGGER = logging.getLogger(__name__)


def is_project_local(path: Path) -> bool:
    """Check if the given path is strictly within the project's root directory."""
    return is_path_within(path, config.PROJECT_ROOT)


def is_path_within(path: Path, parent: Path) -> bool:
    """Check if *path* resolves within *parent*."""
    try:
        path.resolve().relative_to(parent.resolve())
    except (OSError, RuntimeError, ValueError):
        return False
    return True


def is_runtime_write_path(path: Path) -> bool:
    """Return True only for paths under the allowed runtime write roots."""
    return (
        is_path_within(path, config.DATA_DIR)
        or is_path_within(path, config.LOGS_DIR)
    )


def read_json(path: Path, default: Any) -> Any:
    """Read JSON from *path*; return *default* on missing/unreadable/corrupt file."""
    if not path.exists():
        LOGGER.info("No file at %s; using defaults.", path)
        return default
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        LOGGER.warning("Could not read %s: %s. Using defaults.", path, exc)
        return default


def write_json_atomic(path: Path, data: Any) -> bool:
    """Atomically write *data* as JSON to *path*. Returns True on success.

    Creates the parent directory if needed. On any OS error the original file
    (if present) is left untouched and the temp file is cleaned up.
    """
    if not is_runtime_write_path(path):
        LOGGER.warning("Refusing JSON write outside data/logs runtime roots: %s", path)
        return False

    tmp_name: str | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            dir=str(path.parent), prefix=path.name + ".", suffix=".tmp"
        )
        try:
            handle = os.fdopen(fd, "w", encoding="utf-8")
        except Exception:
            os.close(fd)
            raise

        with handle:
            json.dump(data, handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)  # atomic on the same filesystem
        tmp_name = None
        return True
    except OSError as exc:
        LOGGER.warning("Could not write %s: %s.", path, exc)
        return False
    finally:
        if tmp_name and os.path.exists(tmp_name):
            try:
                os.remove(tmp_name)
            except OSError:
                pass
