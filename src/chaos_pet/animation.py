from __future__ import annotations

"""Animation controller with a lightweight priority/interrupt policy.

Looping states (idle/walk/sleep) cycle forever at low priority. One-shot
sequences (blink/happy/angry/eat/jump…) run for a duration then fall back to a
"return" state. A policy table decides whether a newly requested animation may
interrupt whatever is currently playing, which prevents the classic bugs:
blink interrupting eat, idle overriding angry, click-spam corrupting state.

Interrupt rule: a new request starts only if nothing one-shot is playing, OR
the currently-playing one-shot is interruptible, OR the new request has a
strictly higher priority. ``force=True`` bypasses the gate for deliberate
escalation (e.g. a rapid-click jump).
"""

from collections import deque
from dataclasses import dataclass
from typing import Iterable

from PyQt6.QtGui import QPixmap

from . import config
from .asset_loader import SpriteAssets

# Priority ladder (higher number wins). Kept internal; the public policy table
# below maps each state onto one of these.
PRIO_LOOP = 0      # idle, walk, run, sleep, sit
PRIO_LIGHT = 1     # blink, look_around, yawn, wake, happy
PRIO_STRONG = 2    # angry (+ its fall/land tail)
PRIO_JUMP = 3      # jump — escalation, outranks angry
PRIO_EAT = 4       # eat (+ happy tail) — most protected


@dataclass(frozen=True)
class StatePolicy:
    loop: bool
    priority: int
    interruptible: bool
    return_to: str  # "idle" or "previous"


# Per-state policy. Unlisted states use DEFAULT_POLICY (one-shot, light, returns idle).
POLICIES: dict[str, StatePolicy] = {
    "idle": StatePolicy(loop=True, priority=PRIO_LOOP, interruptible=True, return_to="idle"),
    "walk": StatePolicy(loop=True, priority=PRIO_LOOP, interruptible=True, return_to="idle"),
    "run": StatePolicy(loop=True, priority=PRIO_LOOP, interruptible=True, return_to="idle"),
    "sit": StatePolicy(loop=True, priority=PRIO_LOOP, interruptible=True, return_to="idle"),
    "sleep": StatePolicy(loop=True, priority=PRIO_LOOP, interruptible=True, return_to="idle"),
    "blink": StatePolicy(loop=False, priority=PRIO_LIGHT, interruptible=True, return_to="previous"),
    "look_around": StatePolicy(loop=False, priority=PRIO_LIGHT, interruptible=True, return_to="previous"),
    "yawn": StatePolicy(loop=False, priority=PRIO_LIGHT, interruptible=True, return_to="idle"),
    "wake": StatePolicy(loop=False, priority=PRIO_LIGHT, interruptible=True, return_to="idle"),
    "happy": StatePolicy(loop=False, priority=PRIO_LIGHT, interruptible=False, return_to="idle"),
    "angry": StatePolicy(loop=False, priority=PRIO_STRONG, interruptible=False, return_to="idle"),
    "fall": StatePolicy(loop=False, priority=PRIO_STRONG, interruptible=False, return_to="idle"),
    "land": StatePolicy(loop=False, priority=PRIO_STRONG, interruptible=False, return_to="idle"),
    "jump": StatePolicy(loop=False, priority=PRIO_JUMP, interruptible=False, return_to="idle"),
    "eat": StatePolicy(loop=False, priority=PRIO_EAT, interruptible=False, return_to="idle"),
}
DEFAULT_POLICY = StatePolicy(loop=False, priority=PRIO_LIGHT, interruptible=True, return_to="idle")


def policy_for(state: str) -> StatePolicy:
    return POLICIES.get(state, DEFAULT_POLICY)


@dataclass(frozen=True)
class TimedState:
    state: str
    duration_ms: int


class AnimationController:
    def __init__(self, assets: SpriteAssets, default_state: str = config.DEFAULT_STATE) -> None:
        self.assets = assets
        self.default_state = default_state
        self.state = self.assets.resolve_state(default_state)
        self.frame_index = 0
        self._temporary_until_ms: int | None = None
        self._temporary_queue: deque[TimedState] = deque()
        self._then_state = default_state
        # Priority/interruptibility of whatever one-shot is currently playing.
        self._active_priority = PRIO_LOOP
        self._active_interruptible = True

    @property
    def is_temporary(self) -> bool:
        return self._temporary_until_ms is not None

    @property
    def active_priority(self) -> int:
        return self._active_priority if self.is_temporary else PRIO_LOOP

    def can_play(self, state: str, *, force: bool = False) -> bool:
        """Would a request for *state* be allowed to start right now?"""
        if force or not self.is_temporary:
            return True
        new_priority = policy_for(state).priority
        return self._active_interruptible or new_priority > self._active_priority

    def set_state(self, state: str, *, restart: bool = False) -> None:
        resolved = self.assets.resolve_state(state)
        if resolved != self.state or restart:
            self.state = resolved
            self.frame_index = 0

    def play_sequence(
        self,
        sequence: Iterable[tuple[str, int] | TimedState],
        now_ms: int,
        *,
        then: str | None = None,
        force: bool = False,
    ) -> bool:
        """Start a one-shot sequence. Returns False (ignored) if policy blocks it.

        Priority/interruptibility are taken from the first state's policy.
        The return state is the explicit *then*, or the first state's policy
        (``"idle"`` -> default, ``"previous"`` -> the looping state we came from).
        """
        timed_states = [item if isinstance(item, TimedState) else TimedState(*item) for item in sequence]
        if not timed_states:
            return False

        first = timed_states[0]
        if not self.can_play(first.state, force=force):
            return False

        policy = policy_for(first.state)
        if then is not None:
            return_state = then
        elif policy.return_to == "previous":
            # The base looping state we should return to once the one-shot ends.
            return_state = self._then_state if self.is_temporary else self.state
        else:
            return_state = self.default_state

        self._temporary_queue = deque(timed_states[1:])
        self._then_state = return_state
        self._active_priority = policy.priority
        self._active_interruptible = policy.interruptible
        self._start_temporary(first, now_ms)
        return True

    def update(self, now_ms: int) -> QPixmap:
        self._advance_temporary_state(now_ms)

        frames = self.assets.frames_for(self.state)
        if not frames:
            frames = self.assets.frames_for(self.default_state)

        frame = frames[self.frame_index % len(frames)]
        self.frame_index = (self.frame_index + 1) % len(frames)
        return frame

    def _start_temporary(self, timed_state: TimedState, now_ms: int) -> None:
        self.set_state(timed_state.state, restart=True)
        self._temporary_until_ms = now_ms + max(1, timed_state.duration_ms)

    def _advance_temporary_state(self, now_ms: int) -> None:
        if self._temporary_until_ms is None or now_ms < self._temporary_until_ms:
            return

        if self._temporary_queue:
            self._start_temporary(self._temporary_queue.popleft(), now_ms)
            return

        self._temporary_until_ms = None
        self._active_priority = PRIO_LOOP
        self._active_interruptible = True
        self.set_state(self._then_state, restart=True)
