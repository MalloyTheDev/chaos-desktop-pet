from __future__ import annotations

"""Project-local deterministic daily diary.

The diary is simple structured game memory: daily interaction counters, the
latest ending stats snapshot, and a deterministic average/favorite spot estimate.
It has no Qt dependency and never reads or writes outside ``data/``.
"""

import logging
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from . import config
from .persistence import is_path_within, read_json, write_json_atomic
from .stats import PetStats

LOGGER = logging.getLogger(__name__)


@dataclass
class DailyDiaryEntry:
    date: str
    feeds: int = 0
    clicks: int = 0
    rapid_clicks: int = 0
    drags: int = 0
    sleeps: int = 0
    wakes: int = 0
    ending_stats: dict[str, float] = field(default_factory=dict)
    favorite_x: int | None = None
    favorite_y: int | None = None
    favorite_spot_samples: int = 0

    @property
    def favorite_spot(self) -> tuple[int, int] | None:
        if self.favorite_x is None or self.favorite_y is None:
            return None
        return self.favorite_x, self.favorite_y

    def record_click(self, *, rapid: bool) -> None:
        self.clicks += 1
        if rapid:
            self.rapid_clicks += 1

    def record_position(self, x: int, y: int) -> None:
        samples = max(0, self.favorite_spot_samples)
        if self.favorite_x is None or self.favorite_y is None or samples == 0:
            self.favorite_x = int(x)
            self.favorite_y = int(y)
            self.favorite_spot_samples = 1
            return

        self.favorite_x = round((self.favorite_x * samples + int(x)) / (samples + 1))
        self.favorite_y = round((self.favorite_y * samples + int(y)) / (samples + 1))
        self.favorite_spot_samples = samples + 1

    def record_ending_stats(self, stats: PetStats) -> None:
        self.ending_stats = stats.to_dict()

    def to_dict(self) -> dict[str, Any]:
        return {
            "date": self.date,
            "feeds": self.feeds,
            "clicks": self.clicks,
            "rapid_clicks": self.rapid_clicks,
            "drags": self.drags,
            "sleeps": self.sleeps,
            "wakes": self.wakes,
            "ending_stats": dict(self.ending_stats),
            "favorite_spot": {
                "x": self.favorite_x,
                "y": self.favorite_y,
                "samples": self.favorite_spot_samples,
            },
        }

    @classmethod
    def from_dict(cls, data: object, *, fallback_date: str) -> "DailyDiaryEntry":
        if not isinstance(data, dict):
            return cls(date=fallback_date)

        entry_date = _date_key(data.get("date"), fallback=fallback_date)
        entry = cls(date=entry_date)
        entry.feeds = _nonnegative_int(data.get("feeds"))
        entry.clicks = _nonnegative_int(data.get("clicks"))
        entry.rapid_clicks = min(_nonnegative_int(data.get("rapid_clicks")), entry.clicks)
        entry.drags = _nonnegative_int(data.get("drags"))
        entry.sleeps = _nonnegative_int(data.get("sleeps"))
        entry.wakes = _nonnegative_int(data.get("wakes"))
        if isinstance(data.get("ending_stats"), dict):
            entry.ending_stats = PetStats.from_dict(data["ending_stats"]).to_dict()

        spot = data.get("favorite_spot")
        if isinstance(spot, dict):
            samples = _nonnegative_int(spot.get("samples"))
            try:
                x = int(spot["x"])
                y = int(spot["y"])
            except (KeyError, TypeError, ValueError):
                x = y = None
            if x is not None and y is not None and samples > 0:
                entry.favorite_x = x
                entry.favorite_y = y
                entry.favorite_spot_samples = samples

        return entry


@dataclass
class PetDiary:
    schema_version: int = config.DIARY_SCHEMA_VERSION
    days: dict[str, DailyDiaryEntry] = field(default_factory=dict)

    def entry_for(self, day: date | str | None = None) -> DailyDiaryEntry:
        key = _date_key(day)
        entry = self.days.get(key)
        if entry is None:
            entry = DailyDiaryEntry(date=key)
            self.days[key] = entry
            self._prune_old_days()
        return entry

    def record_feed(self, stats: PetStats, *, day: date | str | None = None) -> None:
        entry = self.entry_for(day)
        entry.feeds += 1
        entry.record_ending_stats(stats)

    def record_click(self, *, rapid: bool, stats: PetStats, day: date | str | None = None) -> None:
        entry = self.entry_for(day)
        entry.record_click(rapid=rapid)
        entry.record_ending_stats(stats)

    def record_drag(self, *, day: date | str | None = None) -> None:
        self.entry_for(day).drags += 1

    def record_sleep(self, stats: PetStats, *, day: date | str | None = None) -> None:
        entry = self.entry_for(day)
        entry.sleeps += 1
        entry.record_ending_stats(stats)

    def record_wake(self, stats: PetStats, *, day: date | str | None = None) -> None:
        entry = self.entry_for(day)
        entry.wakes += 1
        entry.record_ending_stats(stats)

    def record_position(self, x: int, y: int, *, day: date | str | None = None) -> None:
        self.entry_for(day).record_position(x, y)

    def record_ending_stats(self, stats: PetStats, *, day: date | str | None = None) -> None:
        self.entry_for(day).record_ending_stats(stats)

    def today_summary(self, *, day: date | str | None = None) -> str:
        entry = self.entry_for(day)
        spot = entry.favorite_spot
        spot_text = "none" if spot is None else f"{spot[0]}, {spot[1]}"
        return (
            f"Feeds {entry.feeds} | Clicks {entry.clicks} | Rapid {entry.rapid_clicks} | "
            f"Drags {entry.drags} | Sleeps {entry.sleeps} | Wakes {entry.wakes} | Spot {spot_text}"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": config.DIARY_SCHEMA_VERSION,
            "days": {key: self.days[key].to_dict() for key in sorted(self.days)},
        }

    @classmethod
    def from_dict(cls, data: object) -> "PetDiary":
        diary = cls()
        if not isinstance(data, dict):
            return diary
        days = data.get("days")
        if not isinstance(days, dict):
            return diary
        for key, value in days.items():
            day_key = _date_key(key, fallback="")
            if not day_key:
                continue
            diary.days[day_key] = DailyDiaryEntry.from_dict(value, fallback_date=day_key)
        diary._prune_old_days()
        return diary

    @classmethod
    def load(cls, path: Path = config.DIARY_PATH) -> "PetDiary":
        if not is_path_within(path, config.DATA_DIR):
            LOGGER.warning("Refusing to load diary outside data dir: %s. Using defaults.", path)
            return cls()
        return cls.from_dict(read_json(path, {}))

    def write(self, path: Path = config.DIARY_PATH) -> bool:
        if not is_path_within(path, config.DATA_DIR):
            LOGGER.warning("Refusing to write diary outside data dir: %s", path)
            return False
        self._prune_old_days()
        return write_json_atomic(path, self.to_dict())

    def _prune_old_days(self) -> None:
        max_days = max(1, int(config.DIARY_HISTORY_DAYS))
        while len(self.days) > max_days:
            oldest = sorted(self.days)[0]
            del self.days[oldest]


def _date_key(value: date | str | object | None, *, fallback: str | None = None) -> str:
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip()).isoformat()
        except ValueError:
            pass
    if fallback is not None:
        return fallback
    return date.today().isoformat()


def _nonnegative_int(value: object) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, parsed)
