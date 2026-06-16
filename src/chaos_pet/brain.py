from __future__ import annotations

"""Deterministic mood-weighted idle decisions.

This module is intentionally pure: no Qt imports, no file I/O, and no knowledge
of widgets, pixmaps, menus, timers, or windows. It scores small idle candidates
from stats + personality + runtime context, then returns the highest-scoring
decision with an explainable reason.
"""

from dataclasses import dataclass

from . import config
from .stats import PetStats

KNOWN_PERSONALITIES = frozenset({"playful", "lazy", "grumpy", "affectionate"})


@dataclass(frozen=True)
class BrainContext:
    stats: PetStats
    personality_id: str
    current_state: str
    available_states: frozenset[str]
    time_since_attention_ms: int
    movement_paused: bool
    temporary_animation_active: bool


@dataclass(frozen=True)
class BrainCandidate:
    name: str
    animation_state: str
    speech_trigger: str | None
    score: float
    reason: str


@dataclass(frozen=True)
class BrainDecision:
    name: str
    animation_state: str | None
    speech_trigger: str | None
    score: float
    reason: str

    @classmethod
    def no_op(cls, reason: str) -> "BrainDecision":
        return cls(
            name="no_op",
            animation_state=None,
            speech_trigger=None,
            score=0.0,
            reason=reason,
        )


class WeightedBehaviorBrain:
    """Scores possible idle expressions without randomness.

    Selection is deterministic: candidates are sorted by score, then by a stable
    built-in preference order. Personality changes the weights, but the stats
    remain the main driver.
    """

    _TIE_ORDER = {
        "annoyed_idle": 0,
        "happy_idle": 1,
        "sleepy_idle": 2,
        "look_around": 3,
        "sit": 4,
        "blink": 5,
        "idle": 6,
    }

    def decide(self, context: BrainContext) -> BrainDecision:
        if context.temporary_animation_active:
            return BrainDecision.no_op("temporary animation active")

        candidates = self.candidates(context)
        if not candidates:
            return BrainDecision.no_op("no available idle states")

        winner = max(
            candidates,
            key=lambda item: (item.score, -self._TIE_ORDER.get(item.name, 99), item.name),
        )
        return BrainDecision(
            name=winner.name,
            animation_state=winner.animation_state,
            speech_trigger=winner.speech_trigger,
            score=round(winner.score, 2),
            reason=winner.reason,
        )

    def candidates(self, context: BrainContext) -> tuple[BrainCandidate, ...]:
        if context.temporary_animation_active:
            return ()

        stats = context.stats
        personality = self._normalize_personality(context.personality_id)
        available = context.available_states
        unattended_bonus = min(max(context.time_since_attention_ms, 0) / 30_000.0, 1.0) * 8.0
        paused_penalty = 4.0 if context.movement_paused else 0.0

        candidates: list[BrainCandidate] = []

        if config.DEFAULT_STATE in available:
            candidates.append(
                BrainCandidate(
                    name="idle",
                    animation_state=config.DEFAULT_STATE,
                    speech_trigger=None,
                    score=12.0 + self._neutral_bonus(stats),
                    reason="baseline idle",
                )
            )

        if "blink" in available:
            candidates.append(
                BrainCandidate(
                    name="blink",
                    animation_state="blink",
                    speech_trigger=None,
                    score=24.0 + self._neutral_bonus(stats) + unattended_bonus * 0.4,
                    reason="neutral idle",
                )
            )

        if "look_around" in available:
            personality_bias = {
                "playful": 15.0,
                "lazy": -10.0,
                "grumpy": 0.0,
                "affectionate": 4.0,
            }[personality]
            score = (
                22.0
                + self._above(stats.curiosity, 50.0) * 0.85
                + stats.trust * 0.03
                + personality_bias
                + unattended_bonus
                - paused_penalty
                - self._repeat_penalty("look_around", context.current_state)
            )
            candidates.append(
                BrainCandidate(
                    name="look_around",
                    animation_state="look_around",
                    speech_trigger="idle" if score >= 58.0 else None,
                    score=score,
                    reason=self._reason(
                        ("curiosity high", stats.curiosity >= 70.0),
                        ("playful", personality == "playful"),
                        fallback="curiosity idle",
                    ),
                )
            )

        if "sit" in available:
            personality_bias = {
                "playful": -6.0,
                "lazy": 16.0,
                "grumpy": 2.0,
                "affectionate": 0.0,
            }[personality]
            candidates.append(
                BrainCandidate(
                    name="sit",
                    animation_state="sit",
                    speech_trigger=None,
                    score=(
                        20.0
                        + self._below(stats.energy, 70.0) * 0.62
                        + personality_bias
                        + unattended_bonus
                        - self._repeat_penalty("sit", context.current_state)
                    ),
                    reason=self._reason(
                        ("low energy", stats.energy <= 35.0),
                        ("lazy", personality == "lazy"),
                        fallback="settled idle",
                    ),
                )
            )

        sleepy_state = self._first_available(available, ("sit", "yawn"))
        if sleepy_state is not None:
            personality_bias = {
                "playful": -5.0,
                "lazy": 18.0,
                "grumpy": 2.0,
                "affectionate": 1.0,
            }[personality]
            score = (
                16.0
                + self._below(stats.energy, 55.0) * 1.05
                + personality_bias
                + unattended_bonus * 0.6
                - self._repeat_penalty(sleepy_state, context.current_state)
            )
            candidates.append(
                BrainCandidate(
                    name="sleepy_idle",
                    animation_state=sleepy_state,
                    speech_trigger="tired" if stats.energy <= 20.0 else None,
                    score=score,
                    reason=self._reason(
                        ("low energy", stats.energy <= 35.0),
                        ("lazy", personality == "lazy"),
                        fallback="sleep-adjacent idle",
                    ),
                )
            )

        if "happy" in available:
            personality_bias = {
                "playful": 4.0,
                "lazy": 0.0,
                "grumpy": -10.0,
                "affectionate": 14.0,
            }[personality]
            annoyance_penalty = stats.annoyance * (0.35 if personality == "grumpy" else 0.25)
            score = (
                18.0
                + self._above(stats.happiness, 70.0) * 0.72
                + self._above(stats.trust, 60.0) * 0.62
                + personality_bias
                - annoyance_penalty
                - self._repeat_penalty("happy", context.current_state)
            )
            candidates.append(
                BrainCandidate(
                    name="happy_idle",
                    animation_state="happy",
                    speech_trigger="happy" if score >= 70.0 else None,
                    score=score,
                    reason=self._reason(
                        ("happiness high", stats.happiness >= 75.0),
                        ("trust high", stats.trust >= 70.0),
                        ("affectionate", personality == "affectionate"),
                        fallback="positive idle",
                    ),
                )
            )

        if "angry" in available:
            personality_bias = {
                "playful": -2.0,
                "lazy": 0.0,
                "grumpy": 18.0,
                "affectionate": -10.0,
            }[personality]
            if personality == "affectionate" and stats.annoyance < 70.0:
                personality_bias -= 8.0
            score = (
                8.0
                + stats.annoyance * 0.9
                + personality_bias
                + (10.0 if stats.annoyance >= 70.0 else 0.0)
                - max(0.0, stats.trust - 70.0) * 0.1
                - self._repeat_penalty("angry", context.current_state)
            )
            candidates.append(
                BrainCandidate(
                    name="annoyed_idle",
                    animation_state="angry",
                    speech_trigger="angry" if score >= 70.0 else None,
                    score=score,
                    reason=self._reason(
                        ("annoyance high", stats.annoyance >= 70.0),
                        ("grumpy", personality == "grumpy"),
                        fallback="irritated idle",
                    ),
                )
            )

        return tuple(candidates)

    @staticmethod
    def _normalize_personality(personality_id: str) -> str:
        cleaned = str(personality_id or "").strip().lower()
        if cleaned in KNOWN_PERSONALITIES:
            return cleaned
        return config.DEFAULT_PERSONALITY_ID

    @staticmethod
    def _neutral_bonus(stats: PetStats) -> float:
        """Small boost when no strong mood is dominating."""
        deviations = (
            abs(stats.curiosity - 50.0),
            abs(stats.energy - 70.0),
            abs(stats.happiness - 80.0),
            stats.annoyance,
        )
        return max(0.0, 10.0 - sum(deviations) / 16.0)

    @staticmethod
    def _above(value: float, baseline: float) -> float:
        return max(0.0, value - baseline)

    @staticmethod
    def _below(value: float, baseline: float) -> float:
        return max(0.0, baseline - value)

    @staticmethod
    def _repeat_penalty(state: str, current_state: str) -> float:
        if state != config.DEFAULT_STATE and state == current_state:
            return 6.0
        return 0.0

    @staticmethod
    def _first_available(available: frozenset[str], states: tuple[str, ...]) -> str | None:
        for state in states:
            if state in available:
                return state
        return None

    @staticmethod
    def _reason(*parts: tuple[str, bool], fallback: str) -> str:
        active = [label for label, enabled in parts if enabled]
        return " + ".join(active) if active else fallback
