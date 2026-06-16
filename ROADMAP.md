# Chaos Desktop Pet — Vision & Roadmap

**Status: v0.5.0 · local-only · fully offline · no AI/network**

This document is the big picture: what the project is, the principle behind it,
where it is now, and where it's going. For setup/usage see [README.md](README.md);
for how the code fits together see [ARCHITECTURE.md](ARCHITECTURE.md).

---

## The idea

A small pixel-art monkey (default name **Bongo**) that lives on your desktop. The
goal isn't a "smart" assistant — it's a creature that feels *alive*: responsive,
moody, and a little chaotic. It should feel like it has a tiny inner life long
before any AI is involved.

## The guiding principle: feel alive *before* AI

> good desktop pet = **animation + mood + memory + feedback + surprise**

Not "smart" yet — just **responsive**. Behavior should have *causes* (a tired pet
sleeps, an annoyed pet lashes out), so nothing feels random. Everything is local
and deterministic. AI is explicitly **not** part of the current product, and the
offline experience must be genuinely good on its own first.

## Hard constraints (these define the project)

- ✅ Local-only, offline, deterministic
- ✅ PyQt6, asset-folder driven, real 64×64 transparent PNG frames (no GIFs at runtime)
- ✅ Safe in a VM / sandbox; non-invasive to the OS
- ❌ No AI / no LLM / no Claude or OpenAI API / no networking / no telemetry
- ❌ No autostart, no registry edits, no admin, no global installs, no services
- ❌ Never touches files outside this project folder (only `data/` and `logs/`)
- ❌ No EXE/installer yet; no Desktop-Goose-style invasive behavior (no moving other
  windows, stealing the cursor, or blocking the desktop)

---

## Where we are now (v0.5)

The original "feel-alive" roadmap below was planned as v0.1 → v0.8. As of **v0.5**
all of those feel-first milestones have landed. Current capabilities:

| System | What works today |
| --- | --- |
| **Rendering** | Transparent always-on-top window; cached 64×64 frames, nearest-neighbor scaling; missing optional states fall back to `idle`, mandatory `idle` fails loudly |
| **Animation** | Looping + one-shot states with a **priority/interrupt policy** (no thrashing; one-shots return to idle/previous) |
| **Movement** | Idle wander, cursor follow (walk/run), screen-edge clamping (to the pet's own monitor), drag-to-reposition with `fall`/`land` animations |
| **Moods** | `PetStats` (hunger, energy, happiness, annoyance, curiosity, trust) drift over time and react to interaction. Starts at `80.0` content target. |
| **Interaction** | Escalating left-clicks (1 happy/curious · 3 angry · 5 jump+knockback), right-click context menu, banana feeding, pause/resume, toggle size, QSS Pet Status dialog |
| **Speech** | Local, offline voice lines in temporary click-through bubbles (editable JSON, disableable) and critical needs alerts |
| **Persistence** | Atomic project-local `data/save.json` + `data/settings.json` (schema v2); rotating `logs/chaos_pet.log` |
| **Sleep cycle** | `yawn` → `sleep`, `wake` on attention; low energy nudges sleep sooner |
| **Sound** | Synthetic sound generator (click squeak, feed munch, sleep snore, jump boing) generated programmatically on startup |

### Release history

- **v0.1** — Display + animation loader (real PNG frames, crisp scaling, idle loop)
- **v0.2** — Movement + mouse following + click/right-click reactions + drag + `settings.json` + tray pause
- **v0.3** — Idle variety (`look_around`/`sit`/`blink`), sleep transition (`yawn`→`sleep`→`wake`), tray hide/show
- **v0.4** — Mood stats, animation priority policy, click-combo escalation, banana feeding (+`jump`),
  local speech bubbles, save/settings/logs, and robustness fixes (Esc-quit, no-screen guard, multi-monitor clamp)
- **v0.5** — Synthetic local sound effects (squeak, munch, snore, boing), personality modulations,
  trust-based behavior, drag-to-fall/release-to-land animations, status dashboard dialog,
  low-maintenance needs & happiness stats tuning, and schema v2 settings migration

---

## Where we're going

The core feel-first foundation and local sound system are fully in place. Next steps focus on further polish and packaging:

### Next / polish
- Multi-monitor speech-bubble clamping (done); richer idle variety; further gameplay balance adjustments.
- Optional packaging to a portable EXE (config script at `tools/build_exe.py`).

### Explicitly out of scope (for now, by design)
- **AI layer.** Someday an *optional, opt-in* AI could read the same
  `personality_id` / stats to generate lines or reactions — but only once the
  offline pet is genuinely great, and never as a requirement. The codebase keeps
  personality/stats in plain data files precisely so a future AI could read them
  without rearchitecting. Until then: no AI, no network, no API.

---

## How to think about contributions

Small, in-place, offline, deterministic. Add a state by dropping a sprite folder;
add a voice line by editing JSON; add a mood rule in `stats.py`. Keep the Qt/IO in
`app.py` and the decision logic in the pure modules (`stats`, `behavior`,
`animation` policy) so it stays testable. See [ARCHITECTURE.md](ARCHITECTURE.md).
