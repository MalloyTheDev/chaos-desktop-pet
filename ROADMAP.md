# Chaos Desktop Pet — Vision & Roadmap

**Status: v0.7.0 · local-only · fully offline · no AI/network/telemetry**

This document is the big picture: what the project is, the principle behind it,
where it is now, and where it is going. For setup/usage see [README.md](README.md);
for how the code fits together see [ARCHITECTURE.md](ARCHITECTURE.md).

---

## The idea

A small pixel-art monkey (default name **Bongo**) that lives on your desktop. The
goal is not a "smart" assistant. It is a creature that feels *alive*: responsive,
moody, and a little chaotic, with behavior that has readable causes.

## The guiding principle: feel alive without AI

> good desktop pet = **animation + mood + memory + feedback + surprise**

Behavior should have causes: a tired pet drifts toward rest, an annoyed pet can
lash out, a curious pet looks around. The weighted brain is deterministic
game-AI-style scoring, not an AI/LLM/API feature.

## Hard constraints (these define the project)

- Local-only, offline, deterministic
- PyQt6, asset-folder driven, real 64x64 transparent PNG frames (no GIFs at runtime)
- Safe in a VM / sandbox; non-invasive to the OS
- No AI, no LLM, no Claude/OpenAI/Grok/Ollama/API providers
- No HTTP calls, networking, telemetry, screen reading, clipboard reading, OCR, or voice assistant features
- No autostart, registry edits, admin privileges, global installs, services, or global hotkeys
- Runtime writes stay inside the project-local `data/` and `logs/` folders
- No Desktop-Goose-style invasive behavior: no moving other windows, stealing the cursor, or blocking the desktop

---

## Where we are now (v0.7)

The first offline feel-alive foundation is in place, including deterministic
mood-weighted idle behavior and directional facing.

| System | What works today |
| --- | --- |
| **Rendering** | Transparent always-on-top window; cached 64x64 frames, nearest-neighbor scaling; directional pixmap mirroring; missing optional states fall back to `idle`, mandatory `idle` fails loudly |
| **Animation** | Looping + one-shot states with a priority/interrupt policy that prevents thrashing and click-spam corruption |
| **Movement** | Cursor follow (`walk`/`run`), screen-edge clamping to the pet's own monitor, drag-to-reposition with `fall`/`land` animations |
| **Moods** | `PetStats` tracks hunger, energy, happiness, annoyance, curiosity, and trust; personality modulates drift and interaction effects |
| **Weighted brain** | Pure `brain.py` scores idle choices from stats, personality, available animation states, attention timing, pause state, and temporary-animation state |
| **Facing** | Pure `facing.py` tracks left/right direction from movement deltas and ignores tiny jitter |
| **Interaction** | Escalating left-clicks, right-click context menu, banana feeding, pause/resume, toggle size, status dialog |
| **Speech** | Local offline voice lines in temporary click-through bubbles; personality-specific line pools are supported |
| **Persistence** | Atomic project-local `data/save.json` + `data/settings.json`; rotating `logs/chaos_pet.log` |
| **Sleep cycle** | `yawn` -> `sleep`, `wake` on attention; low energy nudges sleep sooner |
| **Sound** | Synthetic local sound effects generated programmatically on startup; off by default and toggleable |

### Release history

- **v0.1** — Display + animation loader (real PNG frames, crisp scaling, idle loop)
- **v0.2** — Movement + mouse following + click/right-click reactions + drag + `settings.json` + tray pause
- **v0.3** — Idle variety (`look_around`/`sit`/`blink`), sleep transition (`yawn` -> `sleep` -> `wake`), tray hide/show
- **v0.4** — Mood stats, animation priority policy, click-combo escalation, banana feeding (+`jump`),
  local speech bubbles, save/settings/logs, and robustness fixes
- **v0.5** — Synthetic local sound effects, personality modulations, trust-based behavior,
  drag-to-fall/release-to-land animations, status dashboard dialog, needs tuning, and schema v2 settings migration
- **v0.6** — Deterministic mood-weighted idle brain with explainable candidate scoring and brain-specific tests
- **v0.6.1** — Runtime write boundary hardening: generated sounds moved to `data/sounds/`,
  and JSON/SFX writes now fail closed outside `data/` and `logs/`
- **v0.7** — Directional sprite flip from movement delta, using runtime pixmap mirroring
  with no asset changes

---

## Roadmap

### v0.8 — Local Diary / Deeper Memory

- Add project-local `data/diary.json` or equivalent.
- Track daily interaction summaries: feeds, clicks, rapid clicks, drags, sleeps,
  wakes, ending stats.
- Add favorite spot / routine memory only if it stays deterministic and project-local.
- Show summary in the status dialog later.

### v0.9 — Particle Overlays

- Add small transparent visual feedback windows or an overlay layer.
- Examples: hearts after feed, Zzz while sleeping, sweat/anger puff when annoyed,
  sparkle on happy.
- Reuse the existing non-invasive popup principles from speech bubbles.

### v1.0 — Polish + Portable Package

- Balance weights and stat drift.
- Clean docs.
- Run asset validation and smoke tests.
- Attempt portable EXE packaging using project-local tooling.
- No installer, autostart, registry edits, services, or admin requirements.

### Explicitly out of scope

- AI companion, LLMs, API keys, HTTP providers, Ollama, OpenAI/Claude/Grok integrations
- Screen capture, OCR, clipboard access, voice assistant behavior
- VS Code extension, background services, global hotkeys, autostart, registry edits

---

## How to think about contributions

Small, in-place, offline, deterministic. Add a state by dropping a sprite folder;
add a voice line by editing JSON; add a mood rule in `stats.py`; add idle
decision scoring in `brain.py`. Keep Qt/IO in `app.py` and decision logic in pure
modules so it stays testable. See [ARCHITECTURE.md](ARCHITECTURE.md).
