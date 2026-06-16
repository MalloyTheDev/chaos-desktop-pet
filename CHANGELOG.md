# Changelog

All notable changes to this project are documented here. Format is based on
[Keep a Changelog](https://keepachangelog.com/). Entries are tagged
**Added / Changed / Fixed / Security / Docs**. Audit findings and their
resolution status live in [AUDITS.md](AUDITS.md); the safety posture is in
[SECURITY.md](SECURITY.md).

## [0.7.1] - 2026-06-16

### Fixed
- Hardened `FacingTracker` against invalid or non-finite jitter thresholds.
- Hardened private WAV generation so a missing generator function writes safe
  silence in `data/sounds/` instead of raising.

### Tests
- Added coverage for invalid facing jitter thresholds and safe-silence SFX
  generation.

## [0.7.0] - 2026-06-16

### Added
- `facing.py`: a pure left/right `FacingTracker` that updates from horizontal
  movement deltas and ignores tiny jitter.
- Directional sprite flip in `PetWindow`: rendered pixmaps are mirrored when the
  pet is facing left, with a small cache so repeated frames are not transformed
  every tick.
- Facing tests for default direction, left/right deltas, jitter resistance,
  position-delta updates, and invalid initial values.

### Changed
- Drag movement and cursor-follow movement now update facing direction from the
  actual clamped window delta.

## [0.6.1] - 2026-06-16

### Security
- Moved generated synthetic SFX output from `assets/sounds/` to
  `data/sounds/`, keeping runtime writes inside the approved `data/` and
  `logs/` roots.
- Hardened `write_json_atomic` so JSON writes are refused outside `data/` and
  `logs/`, even for other paths inside the project folder.
- Hardened sound generation and playback with runtime-write-root checks and a
  fixed sound-name allowlist.

### Tests
- Extended security tests for project-root write refusal, project-root SFX
  refusal, and `data/sounds/` placement.

## [0.6.0] - 2026-06-16

### Added
- `brain.py`: a pure deterministic weighted idle decision layer that scores
  `blink`, `look_around`, `sit`, `happy_idle`, `annoyed_idle`, and
  `sleepy_idle` candidates from `PetStats`, `personality_id`, available sprite
  states, attention timing, pause state, and temporary-animation state.
- Brain decision tests covering curiosity/playful, tired/lazy, annoyed/grumpy,
  happy/trust/affectionate, missing optional states, unknown personalities,
  temporary animation no-op, movement-pause safety, and deterministic stability.
- Debug overlay now includes the latest brain decision, reason, and score when
  debug mode is enabled.

### Changed
- Replaced the old random idle variation action picker with deterministic
  weighted brain decisions while keeping existing movement, sleep, click,
  feeding, speech, sound, drag, and animation priority behavior intact.
- `PetBehavior` now owns idle/blink timing and attention age; the new brain owns
  idle action choice.
- Seeded remaining local pseudo-random choices with a fixed project seed so
  blink/idle scheduling, mood-alert odds, evasive odds, and speech line selection
  are replayable instead of unseeded.

### Docs
- Updated README, roadmap, and architecture docs for v0.6.
- Removed the stale README claim that `personality_id` and `debug_enabled` were
  placeholders; both were already wired in v0.5 and remain active in v0.6.
- Preserved the offline roadmap for v0.7 directional sprite flip, v0.8 local
  diary, v0.9 particle overlays, and v1.0 polish + portable package.

### Security
- Preserves the no-AI, no-network, no-telemetry, no screen/clipboard reading,
  no autostart, no registry, no services, and project-local-write guarantees.

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
- **Tuned Needs Drift Rates & Automatic Migration**: Reduced default hunger drift rate to `0.0005/s` (originally `0.6/s`) and active energy decay rate to `0.001/s` (originally `0.45/s`). Tuned happiness mechanics by setting starting value/neutral content target to `80.0` (was starting at `60.0`, drifting down to `50.0`), slowing normal normalization drift to `0.0002/s` (was `0.03/s` - 150x slower), and reducing hunger erosion to `0.005/s` (was `0.5/s` - 100x slower) to deliver a content and relaxing desktop companion experience. Added a settings schema version 2 migration that automatically upgrades existing version 1 `data/settings.json` configurations on startup.

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
