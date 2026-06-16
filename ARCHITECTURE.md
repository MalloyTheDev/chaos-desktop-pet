# Chaos Desktop Pet — Architecture

How the code fits together (v0.7). For the vision and roadmap see
[ROADMAP.md](ROADMAP.md); for setup/usage see [README.md](README.md).

## Design shape

One thin Qt + I/O layer (`app.py`) on top of small, **pure, testable** modules.
Decision logic (moods, movement, animation policy) lives outside the widget so it
can be unit-tested with no window. The widget mostly **renders the current frame,
handles input, shows menus, and delegates**.

```
main.py
  └─ chaos_pet.app.run()
        └─ PetWindow (QWidget)  ── the only Qt + I/O layer
              ├─ AnimationController + StatePolicy   (animation.py)
              ├─ PetBehavior + ClickTracker          (behavior.py)
              ├─ WeightedBehaviorBrain                (brain.py)
              ├─ FacingTracker                        (facing.py)
              ├─ PetStats                             (stats.py)
              ├─ SpriteAssets                         (asset_loader.py)
              ├─ SpeechBubble + VoiceLines            (speech.py)
              ├─ PetSettings                          (settings.py)
              ├─ PetSave                              (save.py → persistence.py)
              ├─ SoundManager                         (sfx.py)
              └─ PetStatusDialog                      (dialogs.py)
```

## Modules

| Module | Responsibility | Qt? | I/O? |
| --- | --- | --- | --- |
| `main.py` | Entrypoint; puts `src/` on the path; calls `app.run()` | no | no |
| `config.py` | All paths + tuning constants (one source of truth) | no | no |
| `persistence.py` | Atomic JSON read/write (`temp file → os.replace`); read never raises | no | **yes** |
| `settings.py` | `PetSettings`: validated load, legacy `./settings.json` migration, atomic save | no | yes |
| `save.py` | `PetSave`: position/state/stats/identity to `data/save.json` | no | yes |
| `stats.py` | `PetStats`: 6-stat mood/needs model — drift + interaction effects (pure) | no | no |
| `asset_loader.py` | `SpriteAssets`: discover/validate (64×64 + alpha)/natural-sort/cache; `require_idle` | Qt pixmaps | reads PNGs |
| `animation.py` | `AnimationController` + `StatePolicy` priority/interrupt table | Qt pixmaps | no |
| `behavior.py` | `PetBehavior` (follow/sleep/blink/idle/knockback) + `ClickTracker` (pure math) | minimal | no |
| `brain.py` | `WeightedBehaviorBrain`: deterministic mood/personality weighted idle decisions (pure) | no | no |
| `facing.py` | `FacingTracker`: deterministic left/right facing from movement deltas (pure) | no | no |
| `speech.py` | `VoiceLines` (local JSON) + `SpeechBubble` (click-through popup) | yes | reads/writes JSON |
| `sfx.py` | `SoundManager` + WAV generator: programmatically builds / plays local synthetic SFX | yes (Qt Audio) | yes |
| `dialogs.py` | `PetStatusDialog`: Premium QSS dark-themed dashboard showing stats & name/personality edit | yes | yes (saves settings) |
| `app.py` | `PetWindow` + `run()`: timers, rendering, input, menus, wiring, logging | yes | yes |

## Runtime loops (timers)

`PetWindow` runs four `QTimer`s; everything is single-threaded on the Qt event loop.

| Timer | Rate | Job |
| --- | --- | --- |
| animation | `FRAME_INTERVAL_MS` 140ms (~7fps) | `AnimationController.update()` → `QPixmap` → `QLabel` |
| behavior | `BEHAVIOR_INTERVAL_MS` 33ms (~30Hz) | movement step + state-machine decisions |
| stats | `STATS_TICK_MS` 1000ms | `PetStats.update(dt)` + mood→behavior nudges |
| autosave | `AUTOSAVE_INTERVAL_MS` 30000ms | `PetSave.write()` (also on quit/close) |

## Data flow

- **Render:** animation timer → `AnimationController.update(now)` cycles frames of
  the current state → `FacingTracker` decides whether the displayed pixmap should
  be mirrored → label pixmap.
- **Decide:** behavior timer → `_on_behavior_tick` asks `PetBehavior.step(...)` for a
  move, then asks `WeightedBehaviorBrain` for an idle decision when the pet is not
  moving and not in a temporary animation. Follow → `walk`/`run`; weighted idle →
  `blink`/`look_around`/`sit`/`happy`/`angry`/sleepy-adjacent idle when available;
  tired → `yawn`→`sleep`. State changes go through the animation **policy gate**.
- **Input:** mouse press/move/release → drag, or `ClickTracker` combo → reaction;
  right-click → context menu. Each interaction also nudges `PetStats`.
- **Moods:** stats timer drifts the six stats and applies triggers
  (low energy → seek sleep; high annoyance → evasive `angry`).
- **Persist:** autosave + quit → `PetSave.write()`; settings changes (toggle size,
  speech) → `PetSettings.save()`.

## The four "alive" systems

1. **Moods give behavior *causes* (`stats.py`).** Stats drift and respond to
   interaction; the widget reads `is_tired` / `is_irritated` to decide actions, so
   the pet's choices have visible reasons.
2. **The weighted brain chooses idle expression (`brain.py`).** It scores available
   idle candidates from stats, `personality_id`, attention timing, pause state, and
   temporary-animation state. It is deterministic game-AI-style logic: no AI, no
   LLM, no network, no file I/O, no Qt.
3. **Policy stops animation thrashing (`animation.py`).** Each state has
   `(loop, priority, interruptible, return_to)`. A new request starts only if
   nothing one-shot is playing, the current one-shot is interruptible, or the new
   priority is higher (`force=True` for deliberate escalation). Priority ladder:
   `idle/walk/sleep (0) < blink/happy (1) < angry (2) < jump (3) < eat (4)`. This is
   why blink can't interrupt eat, idle can't override angry, and click-spam is safe.
4. **Behavior is movement personality (`behavior.py`).** Functions for follow/run
   thresholds, knockback arc, sleep timing, blink/idle scheduling, and screen-edge
   clamping — fully tested without opening a window.

## Asset pipeline

`assets/monkey/<state>/*.png` → discovered per-folder → validated (64×64, has
alpha) → natural-sorted (`idle_2` before `idle_10`) → scaled once with
`FastTransformation` (nearest-neighbor) → **cached** in `SpriteAssets`. The
animation loop reads cached pixmaps (no per-frame disk reads). `idle` is mandatory
(`require_idle` raises a clear error); every other state is optional and falls back
to `idle`.

## Determinism

The weighted brain uses score-based selection with a stable tie order. Remaining
local pseudo-random choices (blink/idle schedule timing, occasional mood alerts,
evasive odds, and speech line selection) use `config.DETERMINISTIC_RNG_SEED`
instead of unseeded randomness.

## Files written at runtime (all project-local)

```
data/settings.json     user settings (atomic; migrated once from ./settings.json)
data/save.json         position, last state, stats, identity (atomic; corrupt → defaults)
data/voice_lines.json  editable local speech lines
data/sounds/*.wav      generated synthetic sound effects
logs/chaos_pet.log     rotating log (no private/system data)
```

Nothing is written outside `data/` and `logs/`. No network, registry,
subprocess, dynamic code execution, autostart, or telemetry anywhere in the app.

## Extension points

- **New animation state** — drop `assets/monkey/<state>/*.png` (auto-discovered).
  Add a `POLICIES` entry in `animation.py` only if it needs non-default priority.
- **New voice lines** — edit `data/voice_lines.json` (keys are triggers:
  `idle/feed/happy/angry/sleep/wake/click`).
- **New mood rule** — add drift/trigger logic in `stats.py` (stays unit-testable).
- **New idle decision** — add or tune candidate scoring in `brain.py`.
- **Directional-specific sprites later** — keep `facing.py` as the direction source;
  replace runtime mirroring only if separate left/right assets are introduced.
- **New setting** — add a field to `PetSettings` + a validator in `settings.py`.

## Tests

No window, no pytest dependency:

- `tools/run_tests.py` — natural sort, asset fallback, mandatory-idle, animation
  one-shot/priority, click combos, stat decay, feed effects, save/load roundtrip,
  corrupt-save fallback, settings defaults, weighted brain decisions, facing.
- `tools/behavior_scenarios.py` — movement/animation scenarios (follow/run,
  knockback arc, sleep/wake, edge-clamp, sequencing).
- `tools/smoke_test.py` — offscreen load + required-state check.
- `tools/validate_assets.py` — per-PNG 64×64/alpha validation + mandatory-idle check.
