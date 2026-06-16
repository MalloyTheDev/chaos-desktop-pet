# Changelog

All notable changes to this project are documented here. Format is based on
[Keep a Changelog](https://keepachangelog.com/). Entries are tagged
**Added / Changed / Fixed / Security / Docs**. Audit findings and their
resolution status live in [AUDITS.md](AUDITS.md); the safety posture is in
[SECURITY.md](SECURITY.md).

## [0.5.0] - 2026-06-16

### Added
- **Sound Effects (v0.5)**: Synthetic local SFX (click squeak, feed munch, sleep snore, jump boing) programmatically generated on startup and managed via `QMediaPlayer` + `QAudioOutput`. Off by default, toggleable in settings and menus.
- **Memory & Loyalty Behavior**: Trust stat modulates follow speeds and stop distances (high trust -> stays closer/faster; low trust -> keeps distance/moves slower).
- **Trust Drift**: Trust slowly normalizes over time, with a penalty that makes the pet slower to forgive when trust is very low.
- **Interactive Drag Animations**: The pet enters the `fall` sprite loop when dragged and executes a `land` cushioning animation on release.
- **Pet Status Dialog**: Premium dark-themed status dashboard dialog displaying Needs progress bars (with orange-to-pink linear gradients), editable name textbox, and personality dropdown that syncs settings in real-time.
- **Customizable Needs Rates**: Settings fields (`hunger_drift_rate`, `energy_drift_rate`, `annoyance_decay_rate`) to customize Needs drift behavior.
- **Mood Alert Speeches**: Awake pets complain occasionally if Hunger (>= 75) or Energy (<= 15) metrics cross critical thresholds.
- **Idle Energy Conservation**: Stamina depletion is paused when Bongo is in passive idle states (`idle`, `sit`, `blink`, `look_around`, `yawn`, `wake`), only draining during active actions (walking, running, eating, jumping, knockback).
- **Tuned Needs Drift Rates**: Balanced default hunger drift rate (reduced from `0.6` to `0.05`) and active energy decay rate (reduced from `0.45` to `0.08`) to ensure Bongo behaves like a low-maintenance companion rather than a high-maintenance pet.

### Changed
- Wired `personality_id` to modulate stat drift rates and voice line selection.
- Applied `animation_speed_multiplier` to scale one-shot sequence durations.
- Integrated `debug_enabled` live stats overlay to track real-time stats.

### Fixed
- **HIGH** - Clamped speech bubble position using the pet's current monitor geometry, resolving alignment displacement on multi-monitor setups with negative coordinates.
- **MEDIUM** - Hardened `write_json_atomic` to prevent file descriptor leaks if wrapping fails.
- **MEDIUM** - Enforced project-local path guards in `PetSave` load/write and `VoiceLines` load to prevent out-of-root directory traversal.

## [0.4.1] - 2026-06-16

### Added
- MIT `LICENSE`.

### Fixed (closes the remaining open items from the 2026-06-15 audit — see [AUDITS.md](AUDITS.md))
- An idle/displaced pet is now re-clamped onto its screen every tick, recovering a
  window stranded off-screen after a monitor is unplugged.
- Knockback arc no longer flattens at the top screen edge — the upward hop may
  rise up to one hop-height above the work-area top.
- Removed the redundant double `set_state(idle)` in the behavior tick (dead code).
- Tray `QMenu` now has an explicit parent (ownership hardening), matching the
  right-click context menu.

## [0.4.0] - 2026-06-16

### Added
- `PetStats` mood/needs model (hunger, energy, happiness, annoyance, curiosity,
  trust) with time drift and interaction effects (`stats.py`).
- Animation priority/interrupt policy (`StatePolicy`): looping vs one-shot,
  priority ladder, interruptible flags, return-to-idle/previous — prevents
  blink-interrupts-eat, idle-overrides-angry, and click-spam corruption.
- Escalating left-click combos (1 = happy/curious, 3 = angry, 5 = jump+knockback),
  right-click context menu, banana feeding (`eat`→`happy`→`idle`), toggle size.
  Wires the previously-unused `jump` state.
- Local, offline speech bubbles (`speech.py`) with editable `data/voice_lines.json`.
- Project-local persistence: atomic `data/save.json` + `data/settings.json`
  (`persistence.py`, `save.py`); rotating `logs/chaos_pet.log`.
- Tests: `tools/run_tests.py` (33 unit tests) and `tools/behavior_scenarios.py`
  (19 scenarios). Strengthened `smoke_test.py` and `validate_assets.py`.
- Docs: `ROADMAP.md`, `ARCHITECTURE.md`, `SECURITY.md`, `AUDITS.md`, this changelog.

### Changed
- Settings expanded (`schema_version`, `scale`, `pet_name`, `personality_id`,
  `speech_enabled`, `debug_enabled`, movement/animation multipliers); migrates the
  legacy `./settings.json` once into `data/settings.json` (`sprite_scale`→`scale`).
- Right-click now opens a context menu (previously triggered eat directly);
  feeding moved into the menu.

### Fixed (from the 2026-06-15 audit)
- **HIGH** — `Esc` now actually quits: the frameless tool window gets a focus
  policy plus an application-level shortcut (was a dead handler).
- **MEDIUM** — guarded `screen.availableGeometry()` against a missing screen in
  the behavior tick and clamp helper (no more crash on display loss / RDP).
- **MEDIUM** — follow and knockback now clamp to the pet's own monitor instead of
  the cursor's, fixing the multi-monitor teleport/snap.
- **LOW** — context-menu `QMenu` given an explicit parent; smoke test now requires
  `angry/eat/happy/jump`; corrected the misleading fallback-frame label.

### Security
- Introduces the project's first runtime file writes — `data/` and `settings`
  and `logs/` — all **atomic** (temp file then replace) and strictly inside the
  project folder. Still no network, registry, autostart, services, subprocess,
  dynamic code execution, or telemetry.

## [0.3.0] - 2026-06-15

### Added
- Idle variety (`look_around`, `sit`, `blink`), sleep transition
  (`yawn`→`sleep`→`wake`), and tray hide/show.

## [0.2.0] - 2026-06-15

### Added
- Movement with cursor follow (`walk`/`run`), left/right-click reactions,
  drag-to-reposition, `settings.json`, tray pause, and a no-window smoke test.

## [0.1.0] - 2026-06-15

### Added
- Initial PyQt6 desktop pet: asset loader, natural-sorted cached frames, idle
  animation, transparent always-on-top window.
