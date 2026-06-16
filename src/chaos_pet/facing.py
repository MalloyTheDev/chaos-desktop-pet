from __future__ import annotations

"""Pure facing-direction tracker for directional sprite display."""

from dataclasses import dataclass
from math import isfinite

VALID_FACING = frozenset({"left", "right"})


@dataclass
class FacingTracker:
    facing: str = "right"
    min_delta_px: float = 2.0

    def __post_init__(self) -> None:
        if self.facing not in VALID_FACING:
            self.facing = "right"
        try:
            min_delta = float(self.min_delta_px)
        except (TypeError, ValueError):
            min_delta = 2.0
        self.min_delta_px = min_delta if isfinite(min_delta) and min_delta >= 0.0 else 2.0

    @property
    def should_flip(self) -> bool:
        return self.facing == "left"

    def update_from_delta(self, dx: float) -> str:
        if dx >= self.min_delta_px:
            self.facing = "right"
        elif dx <= -self.min_delta_px:
            self.facing = "left"
        return self.facing

    def update_from_positions(self, previous_x: float, next_x: float) -> str:
        return self.update_from_delta(next_x - previous_x)
