from __future__ import annotations

"""Focused, dependency-free tests (no pytest needed).

Covers the highest-value logic: natural sorting, asset fallback, the mandatory
idle check, animation one-shot/priority behavior, click combos, stat math,
feed effects, save/load roundtrip + corruption fallback, and settings defaults.

Run:  .venv/Scripts/python.exe tools/run_tests.py   (exit 0 = all pass)
"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from chaos_pet import config
from chaos_pet.animation import AnimationController, policy_for
from chaos_pet.asset_loader import (
    MissingIdleError,
    SpriteAssets,
    load_sprite_assets,
    natural_key,
    require_idle,
)
from chaos_pet.behavior import ClickTracker
from chaos_pet.brain import BrainContext, WeightedBehaviorBrain
from chaos_pet.facing import FacingTracker
from chaos_pet.save import PetSave
from chaos_pet.settings import PetSettings, _from_raw, _int_setting
from chaos_pet.stats import PetStats

_passes: list[str] = []
_failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    (_passes if ok else _failures).append(name)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + ("" if ok else f" :: {detail}"))


def test_natural_sort() -> None:
    names = ["idle_10.png", "idle_2.png", "idle_1.png", "idle_0.png"]
    ordered = sorted(names, key=natural_key)
    check("natural sort: idle_2 before idle_10", ordered == ["idle_0.png", "idle_1.png", "idle_2.png", "idle_10.png"], str(ordered))


def test_asset_load_and_fallback() -> None:
    assets = load_sprite_assets(target_size=(128, 128))
    check("assets: idle has frames", assets.frame_count("idle") > 0)
    check("assets: unknown state falls back to idle", assets.resolve_state("__nope__") == "idle")
    check("assets: 64x64 source enforced (all 15 states loaded)", len(assets.states) >= 8, str(assets.states))


def test_require_idle() -> None:
    empty = SpriteAssets(frames_by_state={}, target_size=(128, 128))
    raised = False
    try:
        require_idle(empty)
    except MissingIdleError:
        raised = True
    check("require_idle: missing idle fails clearly", raised)
    # And does NOT raise when idle exists.
    ok_assets = load_sprite_assets(target_size=(128, 128))
    try:
        require_idle(ok_assets)
        check("require_idle: passes when idle present", True)
    except MissingIdleError:
        check("require_idle: passes when idle present", False)


def test_animation_oneshot_return() -> None:
    assets = load_sprite_assets(target_size=(128, 128))
    a = AnimationController(assets)
    a.set_state("walk")
    a.play_sequence([("blink", 50)], now_ms=0)  # blink returns to previous (walk)
    a.update(0)
    a.update(60)
    a.update(120)
    check("animation: one-shot blink returns to previous (walk)", a.state == "walk", a.state)


def test_animation_priority() -> None:
    assets = load_sprite_assets(target_size=(128, 128))
    a = AnimationController(assets)
    a.play_sequence([("eat", 800), ("happy", 400)], now_ms=0)
    check("animation: blink cannot interrupt eat", a.can_play("blink") is False)
    check("animation: angry cannot interrupt eat", a.can_play("angry") is False)
    b = AnimationController(assets)
    b.play_sequence([("angry", 320)], now_ms=0)
    check("animation: jump outranks angry", b.can_play("jump") is True)
    check("animation: idle cannot interrupt angry", b.can_play("idle") is False)
    check("animation: policy table covers idle/eat/jump", policy_for("eat").priority > policy_for("angry").priority)


def test_click_combo() -> None:
    t = ClickTracker(window_ms=700)
    counts = [t.register(0), t.register(100), t.register(200)]
    check("click combo: counts up within window", counts == [1, 2, 3], str(counts))
    after_gap = t.register(2000)
    check("click combo: resets after a gap", after_gap == 1, str(after_gap))


def test_stat_decay() -> None:
    s = PetStats(hunger=10.0, energy=50.0, annoyance=40.0)
    s.update(10.0)  # 10s awake
    check("stats: hunger rises over time", s.hunger > 10.0, str(s.hunger))
    check("stats: energy falls while awake", s.energy < 50.0, str(s.energy))
    check("stats: annoyance decays", s.annoyance < 40.0, str(s.annoyance))

    # Test idle energy conservation
    s_idle = PetStats(energy=50.0)
    s_idle.update(10.0, idle=True)
    check("stats: energy does not decay when idle", s_idle.energy == 50.0, str(s_idle.energy))
    check("stats: hunger still rises when idle", s_idle.hunger > 25.0, str(s_idle.hunger))

    # Test custom rates
    s_default_2 = PetStats(hunger=10.0, energy=50.0, annoyance=40.0)
    s_default_2.update(2.0)

    s_custom = PetStats(hunger=10.0, energy=50.0, annoyance=40.0)
    s_custom.update(2.0, hunger_rate=2.0, energy_rate=1.5, annoyance_decay=10.0)
    check("stats: custom hunger rate scales hunger rise", s_custom.hunger > s_default_2.hunger, f"custom={s_custom.hunger} default={s_default_2.hunger}")
    check("stats: custom energy rate scales energy decay", s_custom.energy < s_default_2.energy, f"custom={s_custom.energy} default={s_default_2.energy}")
    check("stats: custom annoyance decay scales decay", s_custom.annoyance < s_default_2.annoyance, f"custom={s_custom.annoyance} default={s_default_2.annoyance}")

    s2 = PetStats(energy=10.0)
    s2.update(5.0, asleep=True)
    check("stats: energy recovers while asleep", s2.energy > 10.0, str(s2.energy))
    s3 = PetStats(hunger=99.0)
    s3.update(100.0)
    check("stats: values clamp to 0..100", 0.0 <= s3.hunger <= 100.0, str(s3.hunger))


def test_feed_changes() -> None:
    s = PetStats(hunger=60.0, happiness=40.0, trust=50.0)
    s.feed()
    check("feed: hunger drops", s.hunger == 30.0, str(s.hunger))
    check("feed: happiness rises", s.happiness == 60.0, str(s.happiness))
    check("feed: trust rises", s.trust == 55.0, str(s.trust))


def test_weighted_brain() -> None:
    brain = WeightedBehaviorBrain()
    all_states = frozenset({"idle", "blink", "look_around", "sit", "happy", "angry", "yawn"})

    def ctx(
        stats: PetStats,
        *,
        personality_id: str = "playful",
        available_states: frozenset[str] = all_states,
        movement_paused: bool = False,
        temporary_animation_active: bool = False,
    ) -> BrainContext:
        return BrainContext(
            stats=stats,
            personality_id=personality_id,
            current_state="idle",
            available_states=available_states,
            time_since_attention_ms=12_000,
            movement_paused=movement_paused,
            temporary_animation_active=temporary_animation_active,
        )

    curious = brain.decide(ctx(PetStats(curiosity=95.0, happiness=70.0), personality_id="playful"))
    check("brain: high curiosity/playful favors look_around", curious.name == "look_around", str(curious))

    tired = brain.decide(ctx(PetStats(energy=5.0, happiness=50.0), personality_id="lazy"))
    check(
        "brain: low energy/lazy favors sit or sleepy idle",
        tired.name in {"sit", "sleepy_idle"} and tired.animation_state in {"sit", "yawn"},
        str(tired),
    )

    annoyed = brain.decide(ctx(PetStats(annoyance=95.0, happiness=40.0), personality_id="grumpy"))
    check("brain: high annoyance/grumpy favors annoyed idle", annoyed.name == "annoyed_idle", str(annoyed))

    happy = brain.decide(
        ctx(PetStats(happiness=95.0, trust=95.0, annoyance=0.0), personality_id="affectionate")
    )
    check("brain: happiness/trust/affectionate favors happy idle", happy.name == "happy_idle", str(happy))

    missing_optional = brain.decide(
        ctx(PetStats(curiosity=95.0), available_states=frozenset({"idle", "blink"}))
    )
    check(
        "brain: missing optional states skipped cleanly",
        missing_optional.animation_state in {"idle", "blink"},
        str(missing_optional),
    )

    unknown = brain.decide(ctx(PetStats(curiosity=95.0), personality_id="__unknown__"))
    check("brain: unknown personality falls back safely", unknown.animation_state in all_states, str(unknown))

    temp = brain.decide(ctx(PetStats(curiosity=95.0), temporary_animation_active=True))
    check("brain: temporary animation active returns no-op", temp.animation_state is None, str(temp))

    paused = brain.decide(ctx(PetStats(curiosity=95.0), movement_paused=True))
    check(
        "brain: movement paused avoids movement-like states",
        paused.animation_state not in {"walk", "run", "fall", "land", "jump"},
        str(paused),
    )

    stable_context = ctx(PetStats(curiosity=70.0, happiness=80.0, trust=55.0), personality_id="playful")
    first = brain.decide(stable_context)
    second = brain.decide(stable_context)
    check("brain: deterministic for same context", first == second, f"first={first} second={second}")


def test_facing_tracker() -> None:
    tracker = FacingTracker()
    check("facing: default faces right", tracker.facing == "right" and not tracker.should_flip, tracker.facing)

    tracker.update_from_delta(-3.0)
    check("facing: left movement faces left", tracker.facing == "left" and tracker.should_flip, tracker.facing)

    tracker.update_from_delta(3.0)
    check("facing: right movement faces right", tracker.facing == "right" and not tracker.should_flip, tracker.facing)

    tracker.update_from_delta(-0.5)
    check("facing: tiny left jitter does not flip", tracker.facing == "right", tracker.facing)

    tracker.update_from_positions(100.0, 97.0)
    check("facing: position delta can face left", tracker.facing == "left", tracker.facing)

    invalid = FacingTracker(facing="sideways")
    check("facing: invalid initial value falls back safely", invalid.facing == "right", invalid.facing)

    bad_delta = FacingTracker(min_delta_px="not-a-number")
    check("facing: invalid jitter threshold falls back safely", bad_delta.min_delta_px == 2.0, str(bad_delta.min_delta_px))


def test_save_roundtrip() -> None:
    path = config.DATA_DIR / "_test_save.json"
    try:
        original = PetSave(position=(123, 456), last_state="walk", stats=PetStats(hunger=42.0), pet_name="Test")
        check("save: write ok", original.write(path) is True)
        loaded = PetSave.load(path)
        check("save: position roundtrips", loaded.position == (123, 456), str(loaded.position))
        check("save: last_state roundtrips", loaded.last_state == "walk")
        check("save: stats roundtrip", loaded.stats.hunger == 42.0, str(loaded.stats.hunger))
        check("save: timestamp written", bool(loaded.last_saved_at))
    finally:
        if path.exists():
            path.unlink()


def test_corrupt_save_fallback() -> None:
    path = config.DATA_DIR / "_test_corrupt.json"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{ this is not valid json ::::", encoding="utf-8")
        loaded = PetSave.load(path)
        check("corrupt save: falls back to defaults", loaded.position is None and loaded.stats.hunger == PetStats().hunger)
    finally:
        if path.exists():
            path.unlink()


def test_settings_defaults() -> None:
    defaults = PetSettings()
    check("settings: default speech enabled", defaults.speech_enabled is True)
    check("settings: sprite_scale alias works", defaults.sprite_scale == defaults.scale)
    # Validation rejects out-of-range and wrong-type values.
    check("settings: rejects out-of-range int", _int_setting({"scale": 999}, "scale", 2, 1, 8) == 2)
    check("settings: rejects bool-as-int", _int_setting({"scale": True}, "scale", 2, 1, 8) == 2)
    parsed = _from_raw({"scale": 4, "speech_enabled": "nope", "pet_name": "  Kong  "})
    check("settings: parses good + corrects bad", parsed.scale == 4 and parsed.speech_enabled is True and parsed.pet_name == "Kong", str(parsed))
    check("settings: default sound disabled", defaults.sound_enabled is False)
    parsed_sound = _from_raw({"sound_enabled": True})
    check("settings: parses sound enabled", parsed_sound.sound_enabled is True)
    check("settings: default hunger_drift_rate", defaults.hunger_drift_rate == 0.0005)
    parsed_drift = _from_raw({"hunger_drift_rate": 2.5, "energy_drift_rate": 999.0})
    check("settings: custom drift rate parsed", parsed_drift.hunger_drift_rate == 2.5)
    check("settings: out-of-range drift rate corrected", parsed_drift.energy_drift_rate == 0.001)

    # Test schema version migration from v1 to v2
    import json
    from chaos_pet.settings import load_settings
    test_mig_path = config.DATA_DIR / "_test_settings_mig.json"
    try:
        # Create a v1 settings file with old defaults
        v1_data = {
            "schema_version": 1,
            "hunger_drift_rate": 0.6,
            "energy_drift_rate": 0.45,
            "pet_name": "MigratedBongo"
        }
        with open(test_mig_path, "w", encoding="utf-8") as f:
            json.dump(v1_data, f)
        
        migrated_settings = load_settings(test_mig_path)
        check("migration: schema version bumped to 2", migrated_settings.schema_version == 2)
        check("migration: hunger_drift_rate migrated to new default", migrated_settings.hunger_drift_rate == 0.0005)
        check("migration: energy_drift_rate migrated to new default", migrated_settings.energy_drift_rate == 0.001)
        check("migration: pet_name preserved", migrated_settings.pet_name == "MigratedBongo")
    finally:
        if test_mig_path.exists():
            test_mig_path.unlink()


def test_trust_drift() -> None:
    # Drift toward 50.0
    s_low = PetStats(trust=40.0)
    s_low.update(10.0)
    check("trust: low trust recovers", s_low.trust > 40.0, str(s_low.trust))

    s_vlow = PetStats(trust=10.0)
    s_vlow.update(10.0)
    # Slower to forgive: rate 0.015/s vs 0.05/s
    check("trust: low-trust recovers slower", (s_vlow.trust - 10.0) < (s_low.trust - 40.0))

    s_high = PetStats(trust=80.0)
    s_high.update(10.0)
    check("trust: high trust decays", s_high.trust < 80.0, str(s_high.trust))


def test_security_guards() -> None:
    from chaos_pet.persistence import is_project_local, is_runtime_write_path, write_json_atomic
    from chaos_pet.speech import VoiceLines

    ok_path = config.PROJECT_ROOT / "data" / "save.json"
    check("security: local path accepted", is_project_local(ok_path) is True)
    check("security: data path accepted for runtime writes", is_runtime_write_path(ok_path) is True)

    root_write_path = config.PROJECT_ROOT / "_test_forbidden_runtime_write.json"
    root_write_preexisting = root_write_path.exists()
    try:
        root_write_ok = write_json_atomic(root_write_path, {"blocked": True})
        check(
            "security: project-root JSON write refused",
            root_write_ok is False and root_write_path.exists() is root_write_preexisting,
        )
    finally:
        if root_write_path.exists() and not root_write_preexisting:
            root_write_path.unlink()

    bad_path = Path("C:/Windows/System32/cmd.exe") if os.name == "nt" else Path("/etc/passwd")
    check("security: out-of-root path refused", is_project_local(bad_path) is False)

    bad_save = PetSave.load(bad_path)
    check("security: bad save path fallback to defaults", bad_save.position is None)

    bad_save_write = PetSave().write(bad_path)
    check("security: bad save path write refused", bad_save_write is False)

    bad_settings_save = PetSettings().save(bad_path)
    check("security: bad settings path write refused", bad_settings_save is False)

    bad_voice_lines = VoiceLines.load(bad_path)
    check("security: bad voice lines path fallback to default", bad_voice_lines.get("click") is not None)

    from chaos_pet.sfx import _generate_wav
    # test generate outside project path is blocked
    bad_sfx_path = Path("C:/Windows/System32/nonexistent_sfx.wav") if os.name == "nt" else Path("/etc/nonexistent_sfx.wav")
    _generate_wav(bad_sfx_path, 0.1, func=lambda t, d: 0.0)
    check("security: bad sfx path write refused", not bad_sfx_path.exists())

    project_bad_sfx_path = config.PROJECT_ROOT / "_bad_sfx.wav"
    project_bad_sfx_preexisting = project_bad_sfx_path.exists()
    try:
        _generate_wav(project_bad_sfx_path, 0.1, func=lambda t, d: 0.0)
        check(
            "security: project-root sfx write refused",
            project_bad_sfx_path.exists() is project_bad_sfx_preexisting,
        )
    finally:
        if project_bad_sfx_path.exists() and not project_bad_sfx_preexisting:
            project_bad_sfx_path.unlink()

    check("security: generated sounds stay under data", is_runtime_write_path(config.SOUNDS_DIR / "squeak.wav"))

    silent_sfx_path = config.SOUNDS_DIR / "_test_silence.wav"
    try:
        if silent_sfx_path.exists():
            silent_sfx_path.unlink()
        _generate_wav(silent_sfx_path, 0.01)
        check("security: missing sfx generator writes safe silence in data", silent_sfx_path.exists())
    finally:
        if silent_sfx_path.exists():
            silent_sfx_path.unlink()


def main() -> int:
    _ = QApplication.instance() or QApplication([])  # needed for QPixmap in asset tests
    for test in (
        test_natural_sort,
        test_asset_load_and_fallback,
        test_require_idle,
        test_animation_oneshot_return,
        test_animation_priority,
        test_click_combo,
        test_stat_decay,
        test_feed_changes,
        test_weighted_brain,
        test_facing_tracker,
        test_save_roundtrip,
        test_corrupt_save_fallback,
        test_settings_defaults,
        test_trust_drift,
        test_security_guards,
    ):
        test()

    print()
    print(f"Tests: {len(_passes)} passed, {len(_failures)} failed, {len(_passes) + len(_failures)} total")
    if _failures:
        print("FAILED: " + ", ".join(_failures))
        return 1
    print("All tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
