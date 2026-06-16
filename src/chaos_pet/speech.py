from __future__ import annotations

"""Local, offline speech bubbles.

NO AI, NO network, NO API. Lines come from a local list (overridable via
``data/voice_lines.json``). The bubble is a frameless, click-through,
focus-less popup that auto-hides after a short delay and can be disabled
entirely via settings (``speech_enabled``).
"""

import logging
import random
from pathlib import Path

from PyQt6.QtCore import QRect, Qt, QTimer
from PyQt6.QtWidgets import QApplication, QLabel, QWidget

from . import config
from .persistence import is_project_local, read_json, write_json_atomic

LOGGER = logging.getLogger(__name__)

# Trigger -> candidate lines. Kept short and offline.
DEFAULT_VOICE_LINES: dict[str, list[str]] = {
    "idle": ["I live here now.", "Got any bananas?", "What are we building today?", "*scratches head*"],
    "feed": ["Banana acquired.", "Nom nom nom.", "You may continue coding.", "Good human."],
    "happy": ["Banana acquired.", "Yay!", "Best day.", "*happy monkey noises*"],
    "angry": ["HEY.", "You poked the monkey.", "I remember this betrayal.", "Rude."],
    "sleep": ["Zzz...", "Five more minutes.", "*soft snore*"],
    "wake": ["Huh? What?", "I'm up, I'm up.", "Was I asleep?"],
    "click": ["Hi!", "Boop.", "What's up?", "Yes?"],
    "drag": ["Whoa!", "Put me down!", "Where are we going?", "Wheee!", "Hold on!"],
    "hungry": ["I'm starving...", "Banana please?", "Hungry monkey!", "*tummy rumbles*"],
    "tired": ["So sleepy...", "*yawns*", "Need a nap.", "Time to sleep?"],
}


class VoiceLines:
    """Loads local voice lines, falling back to built-in defaults."""

    def __init__(self, lines: dict[str, list[str]], *, rng_seed: int = config.DETERMINISTIC_RNG_SEED) -> None:
        self._lines = lines
        self._rng = random.Random(rng_seed)

    @classmethod
    def load(cls, path: Path = config.VOICE_LINES_PATH) -> "VoiceLines":
        lines = {key: list(value) for key, value in DEFAULT_VOICE_LINES.items()}
        if not is_project_local(path):
            LOGGER.warning("Refusing to load voice lines outside project root: %s", path)
            return cls(lines)
        if path.exists():
            raw = read_json(path, {})
            if isinstance(raw, dict):
                for key, value in raw.items():
                    if isinstance(value, list):
                        cleaned = [str(item) for item in value if isinstance(item, str) and item.strip()]
                        if cleaned:
                            lines[key] = cleaned
        else:
            # Create a discoverable, editable copy on first run (best effort).
            write_json_atomic(path, DEFAULT_VOICE_LINES)
        return cls(lines)

    def get(self, trigger: str, personality_id: str = "playful") -> str | None:
        options = self._lines.get(f"{trigger}_{personality_id}")
        if not options:
            options = self._lines.get(trigger)
        if not options:
            return None
        return self._rng.choice(options)


class SpeechBubble(QWidget):
    """A tiny temporary popup shown above the pet. Never takes focus or input."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        # Click-through: the bubble must never block the desktop or the pet.
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self._label = QLabel(self)
        self._label.setStyleSheet(
            "QLabel {"
            " background: rgba(255, 255, 255, 235);"
            " color: #1b1b1b;"
            " border: 2px solid rgba(0, 0, 0, 60);"
            " border-radius: 10px;"
            " padding: 5px 9px;"
            " font-family: 'Segoe UI', sans-serif;"
            " font-size: 11px;"
            "}"
        )
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

    def say(self, text: str, anchor: QRect, *, duration_ms: int = config.SPEECH_BUBBLE_MS) -> None:
        if not text:
            return
        self._label.setText(text)
        self._label.adjustSize()
        self.resize(self._label.size())

        # Center horizontally over the pet, sit just above it.
        x = anchor.center().x() - self.width() // 2
        y = anchor.top() - self.height() - 6

        # Clamp to the screen containing the pet (the anchor center) to support multi-monitor setups correctly.
        screen = QApplication.screenAt(anchor.center()) or QApplication.primaryScreen()
        if screen is not None:
            screen_rect = screen.availableGeometry()
            x = min(max(x, screen_rect.left()), screen_rect.right() - self.width() + 1)
            y = min(max(y, screen_rect.top()), screen_rect.bottom() - self.height() + 1)

        self.move(x, y)
        self.show()
        self.raise_()
        self._timer.start(max(400, duration_ms))

    def stop(self) -> None:
        self._timer.stop()
        self.hide()
