from __future__ import annotations

"""Project-local game save (``data/save.json``).

Stores the pet's position, last animation state, mood stats, and identity.
Loading is crash-proof: a missing or corrupt save logs a warning and returns a
fresh default. Saving is atomic via persistence.write_json_atomic.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from . import config
from .persistence import read_json, write_json_atomic
from .stats import PetStats

LOGGER = logging.getLogger(__name__)


@dataclass
class PetSave:
    schema_version: int = config.SAVE_SCHEMA_VERSION
    position: tuple[int, int] | None = None
    last_state: str = config.DEFAULT_STATE
    stats: PetStats = field(default_factory=PetStats)
    pet_name: str = config.DEFAULT_PET_NAME
    personality_id: str = config.DEFAULT_PERSONALITY_ID
    last_saved_at: str | None = None

    def to_dict(self) -> dict:
        x, y = (self.position if self.position is not None else (None, None))
        return {
            "schema_version": config.SAVE_SCHEMA_VERSION,
            "position": {"x": x, "y": y},
            "last_state": self.last_state,
            "stats": self.stats.to_dict(),
            "pet_name": self.pet_name,
            "personality_id": self.personality_id,
            "last_saved_at": self.last_saved_at,
        }

    @classmethod
    def from_dict(cls, data: object) -> "PetSave":
        save = cls()
        if not isinstance(data, dict):
            return save
        pos = data.get("position")
        if isinstance(pos, dict):
            try:
                if pos.get("x") is not None and pos.get("y") is not None:
                    save.position = (int(pos["x"]), int(pos["y"]))
            except (TypeError, ValueError):
                save.position = None
        if isinstance(data.get("last_state"), str):
            save.last_state = data["last_state"]
        save.stats = PetStats.from_dict(data.get("stats"))
        if isinstance(data.get("pet_name"), str) and data["pet_name"].strip():
            save.pet_name = data["pet_name"].strip()[:32]
        if isinstance(data.get("personality_id"), str) and data["personality_id"].strip():
            save.personality_id = data["personality_id"].strip()[:32]
        if isinstance(data.get("last_saved_at"), str):
            save.last_saved_at = data["last_saved_at"]
        return save

    @classmethod
    def load(cls, path: Path = config.SAVE_PATH) -> "PetSave":
        save = cls.from_dict(read_json(path, {}))
        LOGGER.info("Loaded save from %s (stats=%s)", path, save.stats.to_dict())
        return save

    def write(self, path: Path = config.SAVE_PATH) -> bool:
        self.last_saved_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        ok = write_json_atomic(path, self.to_dict())
        if ok:
            LOGGER.info("Saved game to %s", path)
        else:
            LOGGER.warning("Failed to save game to %s", path)
        return ok
