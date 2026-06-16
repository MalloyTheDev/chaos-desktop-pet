from __future__ import annotations

"""PetStats: a tiny, deterministic mood/needs model.

Intentionally simple (NOT a full Tamagotchi). All six stats live on a 0-100
scale. `update(dt_s)` applies slow drift; interaction methods nudge stats.
The window/behavior layer reads the convenience properties (is_tired,
is_irritated, wants_to_sleep) to decide what the pet does — this module makes
no Qt or I/O calls and is fully unit-testable.
"""

from dataclasses import asdict, dataclass

_STAT_FIELDS = ("hunger", "energy", "happiness", "annoyance", "curiosity", "trust")


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


@dataclass
class PetStats:
    hunger: float = 25.0
    energy: float = 80.0
    happiness: float = 60.0
    annoyance: float = 0.0
    curiosity: float = 50.0
    trust: float = 50.0

    # --- time-based drift -------------------------------------------------
    def update(self, dt_s: float, *, asleep: bool = False) -> None:
        """Advance stats by *dt_s* seconds. Sleeping recovers energy & calms."""
        if dt_s <= 0:
            return
        # Hunger slowly rises.
        self.hunger = clamp(self.hunger + 0.6 * dt_s)
        # Energy falls while awake, recovers while asleep.
        if asleep:
            self.energy = clamp(self.energy + 2.5 * dt_s)
        else:
            self.energy = clamp(self.energy - 0.45 * dt_s)
        # Happiness normalizes toward neutral (50).
        self.happiness = clamp(self.happiness + (50.0 - self.happiness) * 0.03 * dt_s)
        # Annoyance decays.
        self.annoyance = clamp(self.annoyance - 4.0 * dt_s)
        # Curiosity drifts gently back toward neutral.
        self.curiosity = clamp(self.curiosity + (50.0 - self.curiosity) * 0.02 * dt_s)
        # Being very hungry slowly erodes happiness.
        if self.hunger >= 80.0:
            self.happiness = clamp(self.happiness - 0.5 * dt_s)

    # --- interactions -----------------------------------------------------
    def feed(self) -> None:
        self.hunger = clamp(self.hunger - 30.0)
        self.happiness = clamp(self.happiness + 20.0)
        self.trust = clamp(self.trust + 5.0)
        self.annoyance = clamp(self.annoyance - 12.0)
        self.energy = clamp(self.energy + 5.0)

    def register_click(self, *, rapid: bool) -> None:
        """A single friendly click vs. a rapid (spam) click."""
        self.curiosity = clamp(self.curiosity + 4.0)
        if rapid:
            self.annoyance = clamp(self.annoyance + 16.0)
            self.trust = clamp(self.trust - 2.0)
            self.happiness = clamp(self.happiness - 3.0)
        else:
            self.happiness = clamp(self.happiness + 5.0)
            self.trust = clamp(self.trust + 1.0)
            self.annoyance = clamp(self.annoyance + 3.0)

    def on_wake(self) -> None:
        # Energy was recovered while asleep; waking is mildly pleasant.
        self.happiness = clamp(self.happiness + 4.0)

    # --- derived triggers (read by behavior layer) ------------------------
    @property
    def is_tired(self) -> bool:
        return self.energy <= 15.0

    @property
    def is_irritated(self) -> bool:
        return self.annoyance >= 70.0

    @property
    def wants_to_sleep(self) -> bool:
        return self.energy <= 8.0

    @property
    def is_hungry(self) -> bool:
        return self.hunger >= 75.0

    # --- (de)serialization ------------------------------------------------
    def to_dict(self) -> dict[str, float]:
        return {key: round(float(value), 2) for key, value in asdict(self).items()}

    @classmethod
    def from_dict(cls, data: object) -> "PetStats":
        stats = cls()
        if not isinstance(data, dict):
            return stats
        for field_name in _STAT_FIELDS:
            if field_name in data:
                try:
                    setattr(stats, field_name, clamp(float(data[field_name])))
                except (TypeError, ValueError):
                    pass  # keep the default for this field
        return stats
