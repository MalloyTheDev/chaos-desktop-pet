from __future__ import annotations

"""Deterministic, window-free scenario tests for the pet's 'alive' logic.

Drives the REAL PetBehavior + AnimationController modules through concrete
situations and asserts on their outputs. No QApplication window is opened, so
this is safe to run in CI / headless and is fully repeatable.

Run:  .venv/Scripts/python.exe tools/behavior_scenarios.py
Exit code 0 = all scenarios passed, 1 = at least one failed.
"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QPoint, QPointF, QRect
from PyQt6.QtWidgets import QApplication

from chaos_pet import config
from chaos_pet.animation import AnimationController
from chaos_pet.asset_loader import load_sprite_assets
from chaos_pet.behavior import PetBehavior

SCREEN = QRect(0, 0, 1920, 1080)
PET_SIZE = (128, 128)

_failures: list[str] = []
_passes: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        _passes.append(name)
        print(f"[PASS] {name}")
    else:
        _failures.append(name)
        print(f"[FAIL] {name} :: {detail}")


def fresh_behavior() -> PetBehavior:
    return PetBehavior(walk_speed_px=config.WALK_SPEED_PX, sleep_after_ms=config.SLEEP_AFTER_MS)


def scenario_follow_walk_and_run() -> None:
    b = fresh_behavior()
    # Cursor far to the right but within follow range -> should move toward it.
    pos = QPoint(400, 400)
    cursor = QPointF(700.0, 460.0)  # ~236px from center -> walk range (< RUN_DISTANCE 260)
    step = b.step(pos, cursor, PET_SIZE, SCREEN, allow_motion=True, allow_follow=True)
    moved_right = step.position.x() > pos.x()
    check("follow: walks toward in-range cursor", step.moving and moved_right,
          f"moving={step.moving} pos={step.position}")
    check("follow: chooses walk under run distance", step.motion_state == "walk",
          f"motion_state={step.motion_state}")

    # Distant-but-in-range cursor -> run. Center is (464,464); place cursor 350px
    # away on the x-axis: > RUN_DISTANCE_PX (260) and < CURSOR_FOLLOW_DISTANCE_PX (420).
    cursor_run = QPointF(814.0, 464.0)
    step_run = b.step(QPoint(400, 400), cursor_run, PET_SIZE, SCREEN,
                      allow_motion=True, allow_follow=True)
    check("follow: chooses run for distant cursor", step_run.motion_state == "run",
          f"motion_state={step_run.motion_state} (dist must be 260-420px from center)")


def scenario_too_far_and_too_close() -> None:
    b = fresh_behavior()
    pos = QPoint(400, 400)
    # Beyond CURSOR_FOLLOW_DISTANCE_PX (420) -> ignore.
    far = QPointF(2000.0, 400.0)
    step = b.step(pos, far, PET_SIZE, SCREEN, allow_motion=True, allow_follow=True)
    check("follow: ignores cursor beyond follow range", not step.moving,
          f"moving={step.moving}")

    # Within stop distance -> ignore.
    center = QPointF(pos.x() + 64, pos.y() + 64)
    near = QPointF(center.x() + 10, center.y())
    step2 = b.step(pos, near, PET_SIZE, SCREEN, allow_motion=True, allow_follow=True)
    check("follow: holds still inside stop distance", not step2.moving,
          f"moving={step2.moving}")


def scenario_pause_blocks_motion() -> None:
    b = fresh_behavior()
    pos = QPoint(400, 400)
    cursor = QPointF(650.0, 460.0)
    step = b.step(pos, cursor, PET_SIZE, SCREEN, allow_motion=False, allow_follow=False)
    check("pause: no movement when motion disallowed",
          (not step.moving) and step.position == pos, f"pos={step.position} moving={step.moving}")


def scenario_knockback_arc() -> None:
    b = fresh_behavior()
    pos = QPoint(500, 500)
    center = QPointF(564.0, 564.0)
    cursor = QPointF(564.0, 564.0)  # same as center -> forced default direction (1,0)
    b.begin_knockback(pos, center, cursor)
    positions = []
    moving_flags = []
    for _ in range(config.KNOCKBACK_FRAMES + 2):
        s = b.step(QPoint(positions[-1].x() if positions else pos.x(),
                          positions[-1].y() if positions else pos.y()),
                   QPointF(0, 0), PET_SIZE, SCREEN, allow_motion=True, allow_follow=True)
        positions.append(s.position)
        moving_flags.append(s.moving)
    drifted = positions[-1].x() != pos.x() or positions[0].x() != pos.x()
    check("knockback: produces a hop trajectory", any(moving_flags) and drifted,
          f"start={pos} end={positions[-1]}")
    # After the arc completes, a subsequent step should settle (no longer hopping).
    settled = b.step(positions[-1], QPointF(0, 0), PET_SIZE, SCREEN,
                     allow_motion=True, allow_follow=True)
    check("knockback: settles after arc completes", not settled.moving or settled.motion_state != "fall",
          f"motion_state={settled.motion_state} moving={settled.moving}")


def scenario_sleep_after_idle_and_wake() -> None:
    b = fresh_behavior()
    b.notice(0)
    check("sleep: not sleepy immediately", not b.should_sleep(1000), "")
    check("sleep: sleepy after sleep_after_ms", b.should_sleep(config.SLEEP_AFTER_MS + 1), "")
    # Attention resets the timer.
    b.notice(config.SLEEP_AFTER_MS + 1)
    check("sleep: attention resets the timer",
          not b.should_sleep(config.SLEEP_AFTER_MS + 2), "")


def scenario_screen_clamp() -> None:
    b = fresh_behavior()
    # Start near right edge; cursor pulls further right -> must clamp inside screen.
    pos = QPoint(SCREEN.right() - 130, 500)
    cursor = QPointF(SCREEN.right() + 500, 564.0)
    step = b.step(pos, cursor, PET_SIZE, SCREEN, allow_motion=True, allow_follow=True)
    within = (SCREEN.left() <= step.position.x() <= SCREEN.right() - PET_SIZE[0] + 1)
    check("edge: clamps inside screen bounds", within, f"pos={step.position}")


def scenario_animation_sequence_and_fallback() -> None:
    app = QApplication.instance() or QApplication([])  # noqa: F841 (needed for QPixmap)
    assets = load_sprite_assets(target_size=PET_SIZE)
    anim = AnimationController(assets)
    check("anim: starts in default state", anim.state == config.DEFAULT_STATE,
          f"state={anim.state}")

    # Play a temporary sequence and confirm it is flagged temporary and returns valid frames.
    anim.play_sequence([("eat", 100), ("happy", 100)], now_ms=0, then=config.DEFAULT_STATE)
    check("anim: sequence marks controller temporary", anim.is_temporary, "")
    first = anim.update(0)
    check("anim: temporary frame is non-null", not first.isNull(), "")

    # Advance past both durations -> should fall back to 'then' state.
    anim.update(50)
    anim.update(150)   # past first
    anim.update(260)   # past second
    anim.update(270)
    check("anim: returns to default after sequence", anim.state == config.DEFAULT_STATE,
          f"state={anim.state}")

    # Unknown state resolves to idle fallback without raising.
    resolved = assets.resolve_state("__does_not_exist__")
    check("anim: unknown state falls back to idle", resolved == config.DEFAULT_STATE,
          f"resolved={resolved}")


def scenario_idle_variation_and_blink() -> None:
    b = fresh_behavior()
    # Blink should not fire before its scheduled time, and should fire after.
    fired_early = b.should_blink(0)
    fired_late = b.should_blink(config.BLINK_MAX_DELAY_MS + 1)
    check("idle: blink respects schedule", (not fired_early) and fired_late,
          f"early={fired_early} late={fired_late}")
    var = b.next_idle_variation(config.IDLE_VARIATION_MAX_DELAY_MS + 1)
    check("idle: variation returns a known action", var in {"look_around", "sit"},
          f"variation={var}")


def scenario_trust_modulates_movement() -> None:
    b = fresh_behavior()
    pos = QPoint(400, 400)
    cursor = QPointF(500.0, 464.0)

    # 1. Neutral trust (50.0) -> Normal stop distance (28px). Cursor is 36px away, so it should move.
    step_neutral = b.step(pos, cursor, PET_SIZE, SCREEN, allow_motion=True, allow_follow=True, trust=50.0)
    check("trust: neutral trust follows cursor", step_neutral.moving is True)

    # 2. High trust (80.0) -> Stays closer (stop distance 20px). Speed multiplier 1.25x.
    step_high = b.step(pos, cursor, PET_SIZE, SCREEN, allow_motion=True, allow_follow=True, trust=80.0)
    check("trust: high trust follows cursor and is moving", step_high.moving is True)

    # Compare speed
    dist_neutral = abs(step_neutral.position.x() - pos.x())
    dist_high = abs(step_high.position.x() - pos.x())
    check("trust: high trust moves faster than neutral", dist_high > dist_neutral, f"high={dist_high} neutral={dist_neutral}")

    # 3. Low trust (20.0) -> Keeps distance (stop distance 88px). Speed multiplier 0.5x.
    # Distance is 36px. Since 36 <= 88, it should NOT move.
    step_low = b.step(pos, cursor, PET_SIZE, SCREEN, allow_motion=True, allow_follow=True, trust=20.0)
    check("trust: low trust holds still when cursor is within keeping-distance range", step_low.moving is False, f"moving={step_low.moving}")

    # For distant cursor, it moves, but slower than neutral.
    cursor_far = QPointF(614.0, 464.0)
    step_neutral_far = b.step(pos, cursor_far, PET_SIZE, SCREEN, allow_motion=True, allow_follow=True, trust=50.0)
    step_low_far = b.step(pos, cursor_far, PET_SIZE, SCREEN, allow_motion=True, allow_follow=True, trust=20.0)
    dist_neutral_far = abs(step_neutral_far.position.x() - pos.x())
    dist_low_far = abs(step_low_far.position.x() - pos.x())
    check("trust: low trust moves slower than neutral", dist_low_far < dist_neutral_far, f"low={dist_low_far} neutral={dist_neutral_far}")


def main() -> int:
    scenario_follow_walk_and_run()
    scenario_too_far_and_too_close()
    scenario_pause_blocks_motion()
    scenario_knockback_arc()
    scenario_sleep_after_idle_and_wake()
    scenario_screen_clamp()
    scenario_animation_sequence_and_fallback()
    scenario_idle_variation_and_blink()
    scenario_trust_modulates_movement()

    print()
    print(f"Scenarios: {len(_passes)} passed, {len(_failures)} failed, "
          f"{len(_passes) + len(_failures)} total")
    if _failures:
        print("FAILED: " + ", ".join(_failures))
        return 1
    print("All behavior scenarios passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
