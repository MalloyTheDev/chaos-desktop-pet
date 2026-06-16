# Changelog

All notable changes to this project are documented here. Format is based on
[Keep a Changelog](https://keepachangelog.com/). Entries are tagged
**Added / Changed / Fixed / Security / Docs**. Audit findings and their
resolution status live in [AUDITS.md](AUDITS.md); the safety posture is in
[SECURITY.md](SECURITY.md).

## [Unreleased]

### Known issues (open audit items — see [AUDITS.md](AUDITS.md))
- An idle pet is not re-clamped every tick if a monitor is unplugged while it
  sits idle (startup re-clamps; active movement clamps to the pet's screen).
- Knockback arc flattens against the very top screen edge (cosmetic).
- Redundant double `set_state` to idle in the behavior tick (dead code).
- Tray `QMenu` has no explicit parent (no leak today; the right-click context
  menu was hardened with a parent).

### Planned
- Wire `personality_id` to stat-drift rates and line selection.
- `debug_enabled` → on-screen live stats overlay.
- Apply `animation_speed_multiplier` to one-shot sequence durations.
- v0.5: local sound effects (off by default).

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
