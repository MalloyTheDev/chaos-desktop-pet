from __future__ import annotations

"""Safe, project-local JSON persistence helpers.

All writes are atomic (write to a temp file in the same directory, then
os.replace) so a crash mid-write can never corrupt an existing save. Reads
never raise: a missing or corrupt file logs a warning and returns the caller's
default. Nothing here ever touches a path outside the project's data dir — the
caller supplies the path, and the app only ever passes paths under config.DATA_DIR.
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
    try:
        path.resolve().relative_to(config.PROJECT_ROOT.resolve())
    except ValueError:
        return False
    return True


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
