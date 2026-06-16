# Audit Log

A running record of security/correctness audits and how each finding was
resolved. New audits are appended at the top. Fixes are cross-referenced in
[CHANGELOG.md](CHANGELOG.md); the standing safety posture is in
[SECURITY.md](SECURITY.md).

Status legend: ✅ fixed · 🟡 partially addressed · ⬜ open · ♻️ standing (no defect).

---

## 2026-06-15 — Multi-agent code audit (v0.3 baseline)

**Method.** Four independent auditors (safety/system-impact, Qt-correctness,
behavior-logic, robustness) each read the full source; every finding was then
adversarially verified by a separate reviewer that tried to refute it.
**Result:** 16 confirmed, 1 walked back on verification, 0 false positives.

### Safety — all clean (♻️ standing)

No file writes, registry, autostart, network, subprocess, dynamic code
execution, or telemetry. Asset/settings path-traversal guards
(`resolve()`-then-`relative_to()`) are sound.

> Change since audit: **v0.4 intentionally introduces atomic, project-local
> writes** to `data/` and `logs/`. This is by design and stays inside the project
> folder — see [SECURITY.md](SECURITY.md). It does not weaken any other guarantee.

### Correctness / robustness findings

| Severity | Finding | File | Status |
| --- | --- | --- | --- |
| HIGH | `Esc` handler never fires (frameless tool window takes no focus) → advertised quit hotkey dead | `app.py` | ✅ v0.4 — `setFocusPolicy(StrongFocus)` + an `ApplicationShortcut` `QShortcut` |
| MEDIUM | `screen.availableGeometry()` unguarded in behavior tick → crash if all displays vanish at runtime | `app.py` | ✅ v0.4 — `if screen is None: return` guard |
| MEDIUM | Same unguarded `availableGeometry()` in `_clamp_to_screen` | `app.py` | ✅ v0.4 — None guard added |
| MEDIUM | Follow path clamps to the **cursor's** screen, not the pet's → multi-monitor teleport/snap | `app.py` | ✅ v0.4 — clamp via `screenAt(self._pet_center())` |
| MEDIUM | Knockback hop clamped to the cursor's screen mid-arc | `app.py` | ✅ v0.4 — same pet-screen clamp |
| MEDIUM | Idle/paused pet returns an unclamped position → can be stranded off-screen after a monitor change | `behavior.py` | ✅ v0.4.1 — per-tick re-clamp onto the pet's screen recovers a displaced window (v0.4 re-clamped only at startup) |
| LOW | Context-menu `QMenu()` created without a parent | `app.py` | ✅ v0.4.1 — both the right-click menu and the tray menu are now `QMenu(self)` |
| LOW | Knockback arc flattens against the top screen edge | `behavior.py` | ✅ v0.4.1 — hop may rise up to one hop-height above the work-area top (`_clamp_hop`) |
| LOW | Smoke test omitted `angry/eat/happy` → missing interaction art passed silently | `tools/smoke_test.py` | ✅ v0.4 — added (incl. `jump`) to `REQUIRED_STATES` |
| LOW | Smoke test's "missing-state fallback frames" label was misleading | `tools/smoke_test.py` | ✅ v0.4 — relabeled |
| INFO | Redundant double `set_state` to idle in the behavior tick | `app.py` | ✅ v0.4.1 — removed |
| INFO | Settings out-of-root guard is effectively unreachable defensive code | `settings.py` | ♻️ retained (still defensive for the new `data/` path) |

**Net:** as of **v0.4.1**, every actionable finding from this audit is fixed
(v0.4 closed all HIGH/MEDIUM crash + multi-monitor issues; v0.4.1 closed the
remaining cosmetic/dead-code items). The only standing entries are informational
"all-clear" confirmations.

### Live test evidence (2026-06-15 / 06-16)
- `validate_assets.py`: 60/60 PNGs valid (15 states × 4 frames, 64×64 RGBA).
- `smoke_test.py`: all required states load; idle fallback verified.
- `behavior_scenarios.py`: 19/19. `run_tests.py`: 33/33.
- Live launch: window renders, follows cursor, sleeps/wakes, saves on quit, exit 0.

---

## How to add a new audit entry

1. Run the four no-window checks (validate, smoke, run_tests, behavior_scenarios).
2. Add a dated `##` section at the top: method, result summary, a findings table
   with a **Status** column, and live-test evidence.
3. Reflect fixes in [CHANGELOG.md](CHANGELOG.md) and update [SECURITY.md](SECURITY.md)
   if the safety posture changed.
