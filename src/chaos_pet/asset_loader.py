from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QImageReader, QPainter, QPen, QPixmap

from . import config


LOGGER = logging.getLogger(__name__)
_NATURAL_PARTS = re.compile(r"(\d+)")


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def natural_key(path: Path | str) -> list[int | str]:
    name = path.name if isinstance(path, Path) else str(path)
    parts: list[int | str] = []
    for part in _NATURAL_PARTS.split(name.lower()):
        if part.isdigit():
            parts.append(int(part))
        elif part:
            parts.append(part)
    return parts


@dataclass
class SpriteAssets:
    frames_by_state: dict[str, list[QPixmap]]
    target_size: tuple[int, int]
    fallback_state: str = config.DEFAULT_STATE
    _warned_states: set[str] = field(default_factory=set)
    _placeholder: QPixmap | None = None

    @property
    def states(self) -> tuple[str, ...]:
        return tuple(self.frames_by_state.keys())

    def resolve_state(self, state: str) -> str:
        if state in self.frames_by_state:
            return state

        if self.fallback_state in self.frames_by_state:
            self._warn_once(
                state,
                "Animation state '%s' is missing; using '%s'.",
                state,
                self.fallback_state,
            )
            return self.fallback_state

        if self.frames_by_state:
            fallback = next(iter(self.frames_by_state))
            self._warn_once(
                state,
                "Animation state '%s' is missing and no '%s' state exists; using '%s'.",
                state,
                self.fallback_state,
                fallback,
            )
            return fallback

        self._warn_once(
            state,
            "Animation state '%s' is missing and no sprites were loaded; using a placeholder.",
            state,
        )
        return "__placeholder__"

    def frames_for(self, state: str) -> list[QPixmap]:
        resolved = self.resolve_state(state)
        if resolved == "__placeholder__":
            return [self.placeholder()]
        return self.frames_by_state[resolved]

    def frame_count(self, state: str) -> int:
        return len(self.frames_for(state))

    def placeholder(self) -> QPixmap:
        if self._placeholder is None:
            width, height = self.target_size
            pixmap = QPixmap(width, height)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            painter.setPen(QPen(QColor(255, 0, 180), 2))
            painter.drawRect(2, 2, width - 4, height - 4)
            painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "?")
            painter.end()
            self._placeholder = pixmap
        return self._placeholder

    def _warn_once(self, key: str, message: str, *args: object) -> None:
        if key in self._warned_states:
            return
        self._warned_states.add(key)
        LOGGER.warning(message, *args)


def discover_state_dirs(asset_root: Path) -> Iterable[Path]:
    if not asset_root.exists():
        LOGGER.warning("Asset root does not exist: %s", asset_root)
        return []
    if not asset_root.is_dir():
        LOGGER.warning("Asset root is not a directory: %s", asset_root)
        return []

    resolved_root = asset_root.resolve()
    state_dirs: list[Path] = []
    for path in sorted(asset_root.iterdir(), key=natural_key):
        if not path.is_dir():
            continue
        resolved_path = path.resolve()
        if not is_relative_to(resolved_path, resolved_root):
            LOGGER.warning("Skipping asset state outside asset root: %s", path)
            continue
        state_dirs.append(path)
    return state_dirs


def load_sprite_assets(
    asset_root: Path = config.ASSET_ROOT,
    target_size: tuple[int, int] = config.DISPLAY_SPRITE_SIZE,
) -> SpriteAssets:
    frames_by_state: dict[str, list[QPixmap]] = {}
    resolved_root = asset_root.resolve()

    for state_dir in discover_state_dirs(asset_root):
        frame_paths = sorted(state_dir.glob("*.png"), key=natural_key)
        if not frame_paths:
            LOGGER.warning("Animation state '%s' has no PNG frames.", state_dir.name)
            continue

        frames: list[QPixmap] = []
        for frame_path in frame_paths:
            pixmap = load_sprite_frame(frame_path, resolved_root, target_size)
            if pixmap is None:
                continue
            frames.append(pixmap)

        if frames:
            frames_by_state[state_dir.name] = frames
            LOGGER.info("Loaded %d frame(s) for state '%s'.", len(frames), state_dir.name)
        else:
            LOGGER.warning("Animation state '%s' had PNGs, but none could be loaded.", state_dir.name)

    if not frames_by_state:
        LOGGER.warning("No sprite frames were loaded from %s.", asset_root)

    return SpriteAssets(frames_by_state=frames_by_state, target_size=target_size)


class MissingIdleError(RuntimeError):
    """Raised when the mandatory 'idle' animation cannot be loaded."""


def require_idle(assets: SpriteAssets) -> None:
    """Fail clearly if the required default ('idle') state is missing/empty.

    Optional states fall back to idle, but idle itself is mandatory: without it
    there is nothing safe to fall back to. The app calls this at startup.
    """
    frames = assets.frames_by_state.get(config.DEFAULT_STATE)
    if not frames:
        raise MissingIdleError(
            f"Required '{config.DEFAULT_STATE}' animation is missing or has no valid frames. "
            f"Add transparent 64x64 PNG frames under "
            f"{config.ASSET_ROOT / config.DEFAULT_STATE} and re-run."
        )
    LOGGER.info("Required state '%s' present with %d frame(s).", config.DEFAULT_STATE, len(frames))


def load_sprite_frame(
    frame_path: Path,
    resolved_asset_root: Path,
    target_size: tuple[int, int],
) -> QPixmap | None:
    resolved_frame = frame_path.resolve()
    if not is_relative_to(resolved_frame, resolved_asset_root):
        LOGGER.warning("Skipping sprite frame outside asset root: %s", frame_path)
        return None

    reader = QImageReader(str(frame_path))
    if not reader.canRead():
        LOGGER.warning("Could not decode sprite frame as PNG: %s", frame_path)
        return None

    source_size = reader.size()
    expected_width, expected_height = config.SOURCE_SPRITE_SIZE
    if (source_size.width(), source_size.height()) != config.SOURCE_SPRITE_SIZE:
        LOGGER.warning(
            "Skipping sprite frame with unexpected size %sx%s; expected %sx%s: %s",
            source_size.width(),
            source_size.height(),
            expected_width,
            expected_height,
            frame_path,
        )
        return None

    image = reader.read()
    if image.isNull():
        LOGGER.warning("Could not load sprite frame: %s", frame_path)
        return None

    if not image.hasAlphaChannel():
        LOGGER.warning("Skipping sprite frame without transparency support: %s", frame_path)
        return None

    pixmap = QPixmap.fromImage(image)
    if pixmap.isNull():
        LOGGER.warning("Could not convert sprite frame to pixmap: %s", frame_path)
        return None

    return pixmap.scaled(
        target_size[0],
        target_size[1],
        Qt.AspectRatioMode.IgnoreAspectRatio,
        Qt.TransformationMode.FastTransformation,
    )
