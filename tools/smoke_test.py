from __future__ import annotations

import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

# This keeps the smoke test from opening a real desktop window.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from chaos_pet.animation import AnimationController
from chaos_pet.asset_loader import load_sprite_assets
from chaos_pet.settings import load_settings


REQUIRED_STATES = {
    "idle",
    "walk",
    "run",
    "fall",
    "land",
    "sleep",
    "blink",
    "look_around",
    "sit",
    "yawn",
    "wake",
    # interaction states the app plays on feed / click reactions
    "angry",
    "eat",
    "happy",
    "jump",
}


def main() -> int:
    app = QApplication.instance() or QApplication([])

    settings = load_settings()
    assets = load_sprite_assets(target_size=settings.display_sprite_size)
    if not assets.states:
        print("INVALID: no animation states were loaded")
        return 1

    missing_states = sorted(REQUIRED_STATES.difference(assets.states))
    if missing_states:
        print(f"INVALID: missing required animation states: {', '.join(missing_states)}")
        return 1

    idle_frames = assets.frame_count("idle")
    if idle_frames <= 0:
        print("INVALID: idle fallback has no frames")
        return 1

    animation = AnimationController(assets)
    fallback_frames = assets.frame_count("__missing_state_for_smoke_test__")
    first_frame = animation.update(0)
    if first_frame.isNull():
        print("INVALID: animation returned a null pixmap")
        return 1

    print("Smoke test OK")
    print(f"Settings: scale={settings.sprite_scale}, size={settings.display_sprite_size}")
    print(f"States: {', '.join(assets.states)}")
    print(f"Idle frames: {idle_frames}")
    # An unknown state resolves to 'idle', so this equals the idle frame count.
    print(f"Unknown-state -> idle fallback frame count: {fallback_frames}")

    app.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
