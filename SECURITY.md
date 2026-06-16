# Security & Safety Posture

`chaos-desktop-pet` is deliberately **local-only and non-invasive**. This file is
the standing statement of what the app does and does not do; per-finding history
lives in [AUDITS.md](AUDITS.md).

## Guarantees

The application (everything under `src/chaos_pet/` and `tools/`) does **not**:

- make any network connection, or send telemetry/analytics anywhere;
- use any AI / LLM / Claude / OpenAI / remote API;
- edit the Windows registry, create autostart/Run keys or scheduled tasks, or run on boot;
- install global packages, create services, or require administrator privileges;
- spawn subprocesses or a shell, or execute dynamic code (`eval`/`exec`/`pickle`/`marshal`);
- read clipboard, screenshots, browser data, or active-window titles;
- write runtime data outside this project's `data/` and `logs/` folders.

## What it does write (and where)

As of v0.8 the app writes only inside the project folder's `data/` and
`logs/` folders. JSON writes are **atomic** (temp file then `os.replace`, so a
crash can't corrupt an existing file):

| Path | Contents |
| --- | --- |
| `data/settings.json` | user settings (migrated once from legacy `./settings.json`) |
| `data/save.json` | window position, last state, mood stats, pet identity |
| `data/diary.json` | daily interaction summary, ending stats, favorite-spot estimate |
| `data/voice_lines.json` | editable local speech lines |
| `data/sounds/*.wav` | programmatically generated synthetic WAV sound files |
| `logs/chaos_pet.log` | rotating log — startup/shutdown, asset validation, save/load, caught errors |

`data/` and `logs/` are git-ignored machine-local runtime state.

## Defensive details

- Asset and settings paths are `resolve()`-then-`relative_to()` guarded, so a
  symlink or `..` cannot escape the project's asset/data roots.
- Runtime write helpers refuse paths outside the approved `data/` and `logs/`
  roots, even if the path is elsewhere inside the project.
- Settings and saves are schema-validated; corrupt or out-of-range values are
  rejected with a logged warning and replaced by defaults (never a crash).
- Logging is scoped to app state only; it never records private/system data.

## How safety is maintained

- Findings and their resolution status are tracked in [AUDITS.md](AUDITS.md).
- Before any release, run the no-window checks:
  `tools/validate_assets.py`, `tools/smoke_test.py`, `tools/run_tests.py`,
  `tools/behavior_scenarios.py`.
- New code must preserve the guarantees above. Anything that would add a network
  call, a runtime write outside `data/` or `logs/`, or a system hook is out of scope by design
  (see [ROADMAP.md](ROADMAP.md)).

## Reporting

This is a personal/hobby project. If you spot a safety concern, open a GitHub
issue describing it.
