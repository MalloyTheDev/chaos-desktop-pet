from __future__ import annotations

import math
import random
from dataclasses import dataclass

from PyQt6.QtCore import QPoint, QPointF, QRect

from . import config


@dataclass(frozen=True)
class BehaviorStep:
    position: QPoint
    moving: bool
    distance_to_cursor: float
    motion_state: str = "idle"


class PetBehavior:
    def __init__(
        self,
        *,
        walk_speed_px: float = config.WALK_SPEED_PX,
        sleep_after_ms: int = config.SLEEP_AFTER_MS,
    ) -> None:
        self.walk_speed_px = walk_speed_px
        self.sleep_after_ms = sleep_after_ms
        self._rng = random.Random()
        self._last_attention_ms = 0
        self._next_blink_ms = 0
        self._next_idle_variation_ms = 0
        self._hop_origin: QPointF | None = None
        self._hop_vector = QPointF(0.0, 0.0)
        self._hop_frame = 0
        self._schedule_next_blink(0)
        self._schedule_next_idle_variation(0)

    def notice(self, now_ms: int) -> None:
        self._last_attention_ms = now_ms
        if self._next_blink_ms <= now_ms:
            self._schedule_next_blink(now_ms)

    def begin_knockback(self, position: QPoint, pet_center: QPointF, cursor: QPointF) -> None:
        direction = pet_center - cursor
        length = math.hypot(direction.x(), direction.y())
        if length <= 0.001:
            direction = QPointF(1.0, 0.0)
            length = 1.0

        unit = QPointF(direction.x() / length, direction.y() / length)
        self._hop_origin = QPointF(float(position.x()), float(position.y()))
        self._hop_vector = QPointF(
            unit.x() * config.KNOCKBACK_DISTANCE_PX,
            unit.y() * config.KNOCKBACK_DISTANCE_PX * 0.35,
        )
        self._hop_frame = 0

    def cancel_motion(self) -> None:
        self._hop_origin = None
        self._hop_vector = QPointF(0.0, 0.0)
        self._hop_frame = 0

    def step(
        self,
        position: QPoint,
        cursor: QPointF,
        pet_size: tuple[int, int],
        screen_rect: QRect,
        *,
        allow_motion: bool,
        allow_follow: bool,
    ) -> BehaviorStep:
        if not allow_motion:
            self.cancel_motion()
            return BehaviorStep(
                position=position,
                moving=False,
                distance_to_cursor=self._distance_to_cursor(QPointF(position), cursor, pet_size),
            )

        if self._hop_origin is not None:
            next_position = self._step_hop()
            return BehaviorStep(
                position=self._clamp_hop(next_position, pet_size, screen_rect),
                moving=True,
                distance_to_cursor=self._distance_to_cursor(next_position, cursor, pet_size),
                motion_state="fall",
            )

        current = QPointF(float(position.x()), float(position.y()))
        distance = self._distance_to_cursor(current, cursor, pet_size)

        if not allow_follow:
            return BehaviorStep(position=position, moving=False, distance_to_cursor=distance)

        if (
            distance <= config.CURSOR_STOP_DISTANCE_PX
            or distance > config.CURSOR_FOLLOW_DISTANCE_PX
        ):
            return BehaviorStep(position=position, moving=False, distance_to_cursor=distance)

        center = QPointF(current.x() + pet_size[0] / 2, current.y() + pet_size[1] / 2)
        direction = cursor - center
        length = math.hypot(direction.x(), direction.y())
        if length <= 0.001:
            return BehaviorStep(position=position, moving=False, distance_to_cursor=distance)

        motion_state = "run" if distance >= config.RUN_DISTANCE_PX else "walk"
        speed = self.walk_speed_px
        if motion_state == "run":
            speed *= config.RUN_SPEED_MULTIPLIER

        step_size = min(speed, max(0.0, length - config.CURSOR_STOP_DISTANCE_PX))
        next_position = QPointF(
            current.x() + direction.x() / length * step_size,
            current.y() + direction.y() / length * step_size,
        )
        return BehaviorStep(
            position=self._clamp_to_screen(next_position, pet_size, screen_rect),
            moving=True,
            distance_to_cursor=distance,
            motion_state=motion_state,
        )

    def should_sleep(self, now_ms: int) -> bool:
        return now_ms - self._last_attention_ms >= self.sleep_after_ms

    def should_blink(self, now_ms: int) -> bool:
        if now_ms < self._next_blink_ms:
            return False
        self._schedule_next_blink(now_ms)
        return True

    def next_idle_variation(self, now_ms: int) -> str | None:
        if now_ms < self._next_idle_variation_ms:
            return None
        self._schedule_next_idle_variation(now_ms)
        return "look_around" if self._rng.random() < 0.65 else "sit"

    def cursor_counts_as_attention(self, distance_to_cursor: float) -> bool:
        return distance_to_cursor <= config.CURSOR_ATTENTION_DISTANCE_PX

    def _step_hop(self) -> QPointF:
        assert self._hop_origin is not None

        self._hop_frame += 1
        progress = min(1.0, self._hop_frame / config.KNOCKBACK_FRAMES)
        y_arc = -math.sin(progress * math.pi) * config.KNOCKBACK_HOP_HEIGHT_PX
        next_position = QPointF(
            self._hop_origin.x() + self._hop_vector.x() * progress,
            self._hop_origin.y() + self._hop_vector.y() * progress + y_arc,
        )

        if progress >= 1.0:
            self._hop_origin = None
            self._hop_vector = QPointF(0.0, 0.0)
            self._hop_frame = 0

        return next_position

    def _schedule_next_blink(self, now_ms: int) -> None:
        self._next_blink_ms = now_ms + self._rng.randint(
            config.BLINK_MIN_DELAY_MS,
            config.BLINK_MAX_DELAY_MS,
        )

    def _schedule_next_idle_variation(self, now_ms: int) -> None:
        self._next_idle_variation_ms = now_ms + self._rng.randint(
            config.IDLE_VARIATION_MIN_DELAY_MS,
            config.IDLE_VARIATION_MAX_DELAY_MS,
        )

    @staticmethod
    def _distance_to_cursor(position: QPointF, cursor: QPointF, pet_size: tuple[int, int]) -> float:
        center = QPointF(position.x() + pet_size[0] / 2, position.y() + pet_size[1] / 2)
        return math.hypot(cursor.x() - center.x(), cursor.y() - center.y())

    @staticmethod
    def _clamp_to_screen(position: QPointF, pet_size: tuple[int, int], screen_rect: QRect) -> QPoint:
        max_x = screen_rect.right() - pet_size[0] + 1
        max_y = screen_rect.bottom() - pet_size[1] + 1
        x = min(max(position.x(), screen_rect.left()), max_x)
        y = min(max(position.y(), screen_rect.top()), max_y)
        return QPoint(round(x), round(y))

    @staticmethod
    def _clamp_hop(position: QPointF, pet_size: tuple[int, int], screen_rect: QRect) -> QPoint:
        # Like _clamp_to_screen, but lets the upward hop arc rise up to one hop
        # height above the work-area top, so a knockback near the top edge still
        # shows an arc instead of a flat slide.
        max_x = screen_rect.right() - pet_size[0] + 1
        max_y = screen_rect.bottom() - pet_size[1] + 1
        min_y = screen_rect.top() - config.KNOCKBACK_HOP_HEIGHT_PX
        x = min(max(position.x(), screen_rect.left()), max_x)
        y = min(max(position.y(), min_y), max_y)
        return QPoint(round(x), round(y))


class ClickTracker:
    """Counts rapid successive clicks for combo escalation.

    A click within ``window_ms`` of the previous one increments the combo;
    a longer gap resets it to 1. Returns the running combo length.
    """

    def __init__(self, window_ms: int = config.CLICK_COMBO_WINDOW_MS) -> None:
        self.window_ms = window_ms
        self._count = 0
        self._last_ms: int | None = None

    def register(self, now_ms: int) -> int:
        if self._last_ms is None or (now_ms - self._last_ms) > self.window_ms:
            self._count = 1
        else:
            self._count += 1
        self._last_ms = now_ms
        return self._count

    def reset(self) -> None:
        self._count = 0
        self._last_ms = None
