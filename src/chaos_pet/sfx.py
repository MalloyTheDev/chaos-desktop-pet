from __future__ import annotations

import logging
import math
import struct
import wave
from pathlib import Path

from PyQt6.QtCore import QObject, QUrl
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer

from . import config

LOGGER = logging.getLogger(__name__)


def _generate_wav(path: Path, duration: float, sample_rate: int = 22050, func=None) -> None:
    num_samples = int(duration * sample_rate)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with wave.open(str(path), "wb") as w:
            w.setnchannels(1)  # mono
            w.setsampwidth(2)  # 16-bit
            w.setframerate(sample_rate)
            for i in range(num_samples):
                t = i / sample_rate
                value = func(t, duration)
                value = max(-1.0, min(1.0, value))
                sample = int(value * 32767)
                w.writeframesraw(struct.pack("<h", sample))
        LOGGER.info("Generated synthetic SFX at %s", path)
    except OSError as exc:
        LOGGER.warning("Could not generate SFX at %s: %s", path, exc)


def _squeak_func(t: float, duration: float) -> float:
    f = 1000.0 + 1500.0 * (t / duration)
    env = 1.0 - (t / duration)
    return env * math.sin(2.0 * math.pi * f * t)


def _munch_func(t: float, duration: float) -> float:
    bite_duration = 0.08
    bite_spacing = 0.15
    bite_index = int(t / bite_spacing)
    bite_t = t - (bite_index * bite_spacing)
    if bite_t < bite_duration:
        noise = math.sin(t * 10000.0) * math.cos(t * 13579.0)
        env = 1.0 - (bite_t / bite_duration)
        crackly = 1.0 if math.sin(t * 8000.0) > 0.0 else -1.0
        return env * (0.6 * noise + 0.4 * crackly)
    return 0.0


def _snore_func(t: float, duration: float) -> float:
    cycle_pos = t / duration
    if cycle_pos < 0.6:
        env = math.sin((cycle_pos / 0.6) * math.pi)
        freq = 90.0
        val = (
            math.sin(2.0 * math.pi * freq * t)
            + 0.5 * math.sin(2.0 * math.pi * freq * 2.0 * t)
            + 0.25 * math.sin(2.0 * math.pi * freq * 3.0 * t)
        )
        return 0.25 * env * val
    else:
        env = math.sin(((cycle_pos - 0.6) / 0.4) * math.pi)
        noise = math.sin(t * 5000.0) * math.cos(t * 7000.0)
        return 0.08 * env * noise


def _boing_func(t: float, duration: float) -> float:
    f_start = 180.0
    f_end = 480.0
    f = f_start + (f_end - f_start) * (t / duration)
    vibrato = 1.0 + 0.15 * math.sin(2.0 * math.pi * 18.0 * t)
    env = math.sin((t / duration) * math.pi) * (1.0 - 0.5 * (t / duration))
    return env * math.sin(2.0 * math.pi * f * vibrato * t)


def check_and_generate_sounds(sounds_dir: Path = config.SOUNDS_DIR) -> None:
    """Verifies sound directory and generates default WAVs if they do not exist."""
    sounds = {
        "squeak.wav": (0.08, _squeak_func),
        "munch.wav": (0.45, _munch_func),
        "snore.wav": (1.2, _snore_func),
        "boing.wav": (0.25, _boing_func),
    }

    for filename, (duration, func) in sounds.items():
        path = sounds_dir / filename
        if not path.exists():
            _generate_wav(path, duration, func=func)


class SoundManager(QObject):
    def __init__(self, parent=None, enabled: bool = False) -> None:
        super().__init__(parent)
        self.enabled = enabled
        self._player: QMediaPlayer | None = None
        self._audio_output: QAudioOutput | None = None

        if enabled:
            self._init_player()

    def _init_player(self) -> None:
        if self._player is not None:
            return
        try:
            self._player = QMediaPlayer(self)
            self._audio_output = QAudioOutput(self)
            self._player.setAudioOutput(self._audio_output)
            self._audio_output.setVolume(0.5)  # volume range: 0.0 to 1.0
        except Exception as exc:
            LOGGER.warning("Could not initialize Qt audio system: %s", exc)
            self._player = None
            self._audio_output = None

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        if enabled:
            self._init_player()
        else:
            if self._player is not None:
                try:
                    self._player.stop()
                except Exception:
                    pass

    def play(self, name: str) -> None:
        if not self.enabled:
            return

        self._init_player()  # lazy initialization if needed
        if self._player is None:
            return

        sound_path = config.SOUNDS_DIR / f"{name}.wav"
        if not sound_path.exists():
            LOGGER.warning("Sound file not found: %s", sound_path)
            return

        try:
            self._player.stop()
            self._player.setSource(QUrl.fromLocalFile(str(sound_path.resolve())))
            self._player.play()
        except Exception as exc:
            LOGGER.warning("Failed to play sound %s: %s", name, exc)
