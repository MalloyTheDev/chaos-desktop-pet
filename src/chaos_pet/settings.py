from __future__ import annotations

"""User settings, validated and project-local.

v0.4 reads/writes ``data/settings.json`` (atomic). It stays backward compatible:
if ``data/settings.json`` is absent, values are migrated from the original
``./settings.json`` (the legacy ``sprite_scale`` maps onto the new ``scale``).
Corrupt/missing files fall back to defaults and never crash. All paths are
project-local; an out-of-project path is refused.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import config
from .persistence import is_project_local, is_runtime_write_path, read_json, write_json_atomic

LOGGER = logging.getLogger(__name__)
VALID_STARTING_CORNERS = {"top_left", "top_right", "bottom_left", "bottom_right", "center"}


@dataclass
class PetSettings:
    schema_version: int = config.SETTINGS_SCHEMA_VERSION
    scale: int = config.SPRITE_SCALE
    walk_speed_px: float = config.WALK_SPEED_PX
    sleep_after_ms: int = config.SLEEP_AFTER_MS
    starting_corner: str = config.STARTING_CORNER
    start_margin_px: int = config.START_MARGIN_PX
    movement_paused: bool = config.MOVEMENT_PAUSED
    pet_name: str = config.DEFAULT_PET_NAME
    personality_id: str = config.DEFAULT_PERSONALITY_ID
    speech_enabled: bool = config.SPEECH_ENABLED
    debug_enabled: bool = config.DEBUG_ENABLED
    sound_enabled: bool = config.SOUND_ENABLED
    movement_speed_multiplier: float = config.MOVEMENT_SPEED_MULTIPLIER
    animation_speed_multiplier: float = config.ANIMATION_SPEED_MULTIPLIER
    hunger_drift_rate: float = config.HUNGER_DRIFT_RATE
    energy_drift_rate: float = config.ENERGY_DRIFT_RATE
    annoyance_decay_rate: float = config.ANNOYANCE_DECAY_RATE

    # Backward-compatible alias: older code asks for ``sprite_scale``.
    @property
    def sprite_scale(self) -> int:
        return self.scale

    @property
    def display_sprite_size(self) -> tuple[int, int]:
        return (
            config.SOURCE_SPRITE_SIZE[0] * self.scale,
            config.SOURCE_SPRITE_SIZE[1] * self.scale,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": config.SETTINGS_SCHEMA_VERSION,
            "scale": self.scale,
            "pet_name": self.pet_name,
            "personality_id": self.personality_id,
            "speech_enabled": self.speech_enabled,
            "debug_enabled": self.debug_enabled,
            "sound_enabled": self.sound_enabled,
            "movement_speed_multiplier": self.movement_speed_multiplier,
            "animation_speed_multiplier": self.animation_speed_multiplier,
            "hunger_drift_rate": self.hunger_drift_rate,
            "energy_drift_rate": self.energy_drift_rate,
            "annoyance_decay_rate": self.annoyance_decay_rate,
            "walk_speed_px": self.walk_speed_px,
            "sleep_after_ms": self.sleep_after_ms,
            "starting_corner": self.starting_corner,
            "start_margin_px": self.start_margin_px,
            "movement_paused": self.movement_paused,
        }

    def save(self, path: Path = config.USER_SETTINGS_PATH) -> bool:
        if not is_runtime_write_path(path):
            LOGGER.warning("Refusing to write settings outside data/logs runtime roots: %s", path)
            return False
        ok = write_json_atomic(path, self.to_dict())
        if ok:
            LOGGER.info("Settings saved to %s", path)
        return ok


def load_settings(path: Path | None = None) -> PetSettings:
    """Load settings from ``data/settings.json``, migrating the legacy file once."""
    target = path or config.USER_SETTINGS_PATH
    raw, migrated_from_legacy = _load_raw(target)

    # Perform settings schema migration
    schema_ver = raw.get("schema_version", 1)
    migrated_schema = False

    if schema_ver < config.SETTINGS_SCHEMA_VERSION:
        # Migrate old default rates to new v0.5+ ultra low maintenance defaults
        # Old values in v0.4 and early v0.5 draft:
        old_hunger_defaults = {0.6, 0.05, 0.005}
        old_energy_defaults = {0.45, 0.08, 0.01}

        if "hunger_drift_rate" not in raw or raw.get("hunger_drift_rate") in old_hunger_defaults:
            raw["hunger_drift_rate"] = config.HUNGER_DRIFT_RATE
            migrated_schema = True
        if "energy_drift_rate" not in raw or raw.get("energy_drift_rate") in old_energy_defaults:
            raw["energy_drift_rate"] = config.ENERGY_DRIFT_RATE
            migrated_schema = True

        raw["schema_version"] = config.SETTINGS_SCHEMA_VERSION
        migrated_schema = True

    settings = _from_raw(raw)

    # Persist a canonical data/settings.json on first run / after migration so the
    # user has a discoverable, editable file. Best-effort; failure is non-fatal.
    if path is None and (not target.exists() or migrated_from_legacy or migrated_schema):
        settings.save(target)

    return settings


# --------------------------------------------------------------------------- #
# Loading helpers
# --------------------------------------------------------------------------- #
def _load_raw(target: Path) -> tuple[dict[str, Any], bool]:
    if not is_project_local(target):
        LOGGER.warning("Refusing to read settings outside project root: %s. Using defaults.", target)
        return {}, False

    if target.exists():
        raw = read_json(target, {})
        return (raw if isinstance(raw, dict) else {}), False

    # No data/settings.json yet: migrate from the legacy ./settings.json if present.
    legacy = config.LEGACY_SETTINGS_PATH
    if legacy.exists():
        raw = read_json(legacy, {})
        if isinstance(raw, dict):
            LOGGER.info("Migrating legacy settings from %s", legacy)
            # Map the old key name onto the new one.
            if "sprite_scale" in raw and "scale" not in raw:
                raw = {**raw, "scale": raw["sprite_scale"]}
            return raw, True
    return {}, False


def _from_raw(raw: dict[str, Any]) -> PetSettings:
    return PetSettings(
        scale=_int_setting(raw, "scale", config.SPRITE_SCALE, 1, 8),
        walk_speed_px=_float_setting(raw, "walk_speed_px", config.WALK_SPEED_PX, 0.0, 20.0),
        sleep_after_ms=_int_setting(raw, "sleep_after_ms", config.SLEEP_AFTER_MS, 5_000, 600_000),
        starting_corner=_corner_setting(raw, "starting_corner", config.STARTING_CORNER),
        start_margin_px=_int_setting(raw, "start_margin_px", config.START_MARGIN_PX, 0, 500),
        movement_paused=_bool_setting(raw, "movement_paused", config.MOVEMENT_PAUSED),
        pet_name=_str_setting(raw, "pet_name", config.DEFAULT_PET_NAME),
        personality_id=_str_setting(raw, "personality_id", config.DEFAULT_PERSONALITY_ID),
        speech_enabled=_bool_setting(raw, "speech_enabled", config.SPEECH_ENABLED),
        debug_enabled=_bool_setting(raw, "debug_enabled", config.DEBUG_ENABLED),
        sound_enabled=_bool_setting(raw, "sound_enabled", config.SOUND_ENABLED),
        movement_speed_multiplier=_float_setting(
            raw, "movement_speed_multiplier", config.MOVEMENT_SPEED_MULTIPLIER, 0.1, 5.0
        ),
        animation_speed_multiplier=_float_setting(
            raw, "animation_speed_multiplier", config.ANIMATION_SPEED_MULTIPLIER, 0.1, 5.0
        ),
        hunger_drift_rate=_float_setting(raw, "hunger_drift_rate", config.HUNGER_DRIFT_RATE, 0.0, 10.0),
        energy_drift_rate=_float_setting(raw, "energy_drift_rate", config.ENERGY_DRIFT_RATE, 0.0, 10.0),
        annoyance_decay_rate=_float_setting(raw, "annoyance_decay_rate", config.ANNOYANCE_DECAY_RATE, 0.0, 20.0),
    )


def _int_setting(raw: dict[str, Any], key: str, default: int, minimum: int, maximum: int) -> int:
    value = raw.get(key, default)
    if isinstance(value, bool):
        LOGGER.warning("Setting '%s' must be an integer; using %s.", key, default)
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        LOGGER.warning("Setting '%s' must be an integer; using %s.", key, default)
        return default
    if parsed < minimum or parsed > maximum:
        LOGGER.warning("Setting '%s' must be between %s and %s; using %s.", key, minimum, maximum, default)
        return default
    return parsed


def _float_setting(raw: dict[str, Any], key: str, default: float, minimum: float, maximum: float) -> float:
    value = raw.get(key, default)
    if isinstance(value, bool):
        LOGGER.warning("Setting '%s' must be a number; using %s.", key, default)
        return default
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        LOGGER.warning("Setting '%s' must be a number; using %s.", key, default)
        return default
    if parsed < minimum or parsed > maximum:
        LOGGER.warning("Setting '%s' must be between %s and %s; using %s.", key, minimum, maximum, default)
        return default
    return parsed


def _bool_setting(raw: dict[str, Any], key: str, default: bool) -> bool:
    value = raw.get(key, default)
    if isinstance(value, bool):
        return value
    LOGGER.warning("Setting '%s' must be true or false; using %s.", key, default)
    return default


def _str_setting(raw: dict[str, Any], key: str, default: str, max_len: int = 32) -> str:
    value = raw.get(key, default)
    if not isinstance(value, str):
        LOGGER.warning("Setting '%s' must be a string; using %s.", key, default)
        return default
    cleaned = value.strip()
    if not cleaned:
        return default
    return cleaned[:max_len]


def _corner_setting(raw: dict[str, Any], key: str, default: str) -> str:
    value = str(raw.get(key, default)).strip().lower()
    if value in VALID_STARTING_CORNERS:
        return value
    LOGGER.warning("Setting '%s' must be one of %s; using %s.", key, ", ".join(sorted(VALID_STARTING_CORNERS)), default)
    return default


