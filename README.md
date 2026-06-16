# chaos-desktop-pet

A tiny pixel-art monkey (default name **Bongo**) that lives on your desktop. It
loads local 64×64 transparent PNG frames, scales them crisply with
nearest-neighbor filtering, and shows the pet in a transparent, always-on-top
PyQt6 window with moods, reactions, feeding, and local speech bubbles.

**Status:** v0.4.0 · local-only · fully offline · no AI/network/telemetry.

The goal is a creature that feels *alive* — responsive and moody — entirely
offline and deterministic. The big picture and roadmap are in
[ROADMAP.md](ROADMAP.md); how the code fits together is in
[ARCHITECTURE.md](ARCHITECTURE.md).

> The app is non-invasive: it does not create startup entries, edit the registry,
> install services, collect telemetry, use any AI/network/API, or run on boot.
> The only files it writes are inside this project folder (`data/` and `logs/`).

## Project docs

| Doc | What's in it |
| --- | --- |
| [ROADMAP.md](ROADMAP.md) | Vision, principles, current status, release history, what's next |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Module map, runtime loops, data flow, extension points |
| [CHANGELOG.md](CHANGELOG.md) | Per-version changes (Added/Changed/Fixed/Security) + known issues |
| [AUDITS.md](AUDITS.md) | Audit history and per-finding resolution status |
| [SECURITY.md](SECURITY.md) | Standing safety guarantees and what the app writes |

## What it does today

- Crisp transparent rendering; cached frames; missing optional states fall back to
  `idle` (and a missing `idle` fails with a clear error).
- Animation **priority/interrupt policy** — one-shots don't thrash; click-spam is safe.
- Idle wander, cursor follow (`walk`/`run`), screen-edge clamping, drag-to-move.
- **Moods** (`hunger, energy, happiness, annoyance, curiosity, trust`) that drift and react.
- Escalating left-clicks (1 happy/curious · 3 angry · 5 jump+knockback), banana feeding,
  right-click context menu, pause/resume, toggle size.
- Local, offline **speech bubbles** (editable lines, disableable).
- Sleep cycle (`yawn`→`sleep`→`wake`); project-local save/settings/logs.

See [ROADMAP.md](ROADMAP.md) for the full feature history (v0.1 → v0.4) and what's next.

## Setup

From this folder:

```powershell
cd "F:\Codex Projects\Chaos Pet\chaos-desktop-pet"
py -3.11 -m venv .venv          # or: python -m venv .venv  (Python 3.11+)
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

The only dependency is PyQt6.

## Run

```powershell
python main.py
```

Controls:

- `Esc` — quit (works regardless of focus, via an app-level shortcut)
- **Left-click** — 1 click = happy/curious, 3 rapid = angry, 5 rapid = jump + knockback
  (rapid clicking also raises annoyance)
- **Left-drag** — reposition the pet
- **Right-click** — context menu: Feed banana, Toggle size, Pause/Resume, Speech on/off, Quit
- **System tray** — hide/show, Feed, pause/resume, quit; double-click to hide/show

Feeding plays `eat` → `happy` → `idle` and is non-interruptible, so click-spam can't
corrupt it. Speech bubbles are local, temporary, click-through, never steal focus,
and can be disabled.

## Project layout

```
main.py                    entrypoint (python main.py)
settings.json              legacy settings (migrated once into data/settings.json)
src/chaos_pet/
  config.py                paths + tuning constants
  settings.py  save.py     persistence.py    persistence (atomic, project-local)
  stats.py                 mood/needs model (PetStats)
  asset_loader.py          sprite discovery/validation/cache
  animation.py             AnimationController + priority policy
  behavior.py              movement/idle/sleep + ClickTracker
  speech.py                local voice lines + bubble
  app.py                   PetWindow + run() (Qt + wiring)
tools/                     validate_assets, smoke_test, run_tests, behavior_scenarios
assets/monkey/<state>/     your real 64x64 PNG frames
data/  logs/               created at runtime (save, settings, voice lines, log)
```

Full module responsibilities and data flow: [ARCHITECTURE.md](ARCHITECTURE.md).

## Assets

Animation frames live under `assets/monkey/<state>/`:

```txt
assets/monkey/
  idle/  walk/  run/  happy/  angry/  sleep/  jump/  eat/  blink/
  fall/  land/  look_around/  sit/  yawn/  wake/
    e.g. idle_0.png, idle_1.png, idle_2.png ...
```

The loader auto-discovers every subfolder, so you can add states without code
changes. Frames must be transparent **64×64 PNGs** (no GIFs at runtime). `idle` is
mandatory; every other state is optional and falls back to `idle`.

## Settings, Save, and Logs (project-local)

All runtime data lives inside this project folder. Nothing is written elsewhere.

- `data/settings.json` — user settings (created on first run; migrated once from the
  legacy `./settings.json`, where the old `sprite_scale` becomes `scale`).
- `data/save.json` — saved position, last animation state, mood stats, and identity.
  Written atomically (temp file then replace); a corrupt save logs a warning and
  falls back to defaults. *Delete it for a fresh start.*
- `data/voice_lines.json` — local speech lines you can edit (no AI/network).
- `logs/chaos_pet.log` — rotating log (startup/shutdown, asset validation, save/load,
  caught errors). Never logs clipboard, screenshots, window titles, or private data.

`data/settings.json` schema:

```json
{
  "schema_version": 1,
  "scale": 2,
  "pet_name": "Bongo",
  "personality_id": "playful",
  "speech_enabled": true,
  "debug_enabled": false,
  "movement_speed_multiplier": 1.0,
  "animation_speed_multiplier": 1.0,
  "walk_speed_px": 2.4,
  "sleep_after_ms": 30000,
  "starting_corner": "bottom_right",
  "start_margin_px": 80,
  "movement_paused": false
}
```

Valid `starting_corner` values: `top_left`, `top_right`, `bottom_left`,
`bottom_right`, `center`. Out-of-range or wrong-typed values are rejected with a
logged warning and replaced by defaults.

> Note: `personality_id` and `debug_enabled` are persisted but not yet wired to
> behavior — they're placeholders for the next patch (see [ROADMAP.md](ROADMAP.md)).

## Mood / stats

Six 0–100 stats drift over time: hunger rises, energy falls while awake and
recovers while asleep, annoyance decays, happiness/curiosity normalize. Feeding
lowers hunger and raises happiness/trust; rapid clicking raises annoyance. Low
energy nudges the pet toward sleep; high annoyance can trigger an evasive angry
flash.

## Validate, smoke-test, and test

No-window checks (offscreen Qt; no pytest needed):

```powershell
python tools\validate_assets.py      # per-PNG 64x64 + alpha, and the mandatory 'idle' state
python tools\smoke_test.py           # load settings + assets, check idle fallback, no window
python tools\run_tests.py            # 33 unit tests: stats, save/load, animation policy, settings, combos
python tools\behavior_scenarios.py   # 19 movement/animation scenario tests
```

## Known limitations

- No sound yet (planned v0.5 — deliberately deferred until behavior felt good)
- No AI behavior, and none planned for the offline build — see [ROADMAP.md](ROADMAP.md)
- No installer or EXE packaging yet; no startup integration (by design)
- `personality_id` / `debug_enabled` / `animation_speed_multiplier` are partial (see roadmap)
- Movement is intentionally simple and may need tuning after playtesting
