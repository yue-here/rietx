# WP-2124 — the indexing routes the GUI port needs: an ungated screen, any cell adopted, the pick's options

Milestone: unscheduled · Status: 🔄 2026-11-09 — claimed by a ghostshift runner
Track: Render what the fit already knows
Depends on: —
Priority: P2 2026-11-09 — the server half of the gui-overhaul port's indexing step; on real lab data the old panel's indexing is a dead end without it

## Goal

A pattern-only project can be indexed, screened and adopted end to end through
the GUI's routes. The extinction screen runs on a project with no phase. Any
candidate cell can be adopted, and one the gate did not pick carries its grade
and caveats into the history node. The pick route takes the three options
`pick_peaks` has: shoulders, the 2θ range and the contamination marks.

## Context

### Where this comes from

The GUI overhaul was designed between 2026-11-06 and 2026-11-08 in twelve rounds
of prototypes the maintainer reviewed on screen. The port runs as the
gui-overhaul milestone (`docs/milestones/gui-overhaul.md`, opened by WP-2123,
whose branch carries the record until it merges; its § Owed to the port lists
these defects). Round 11 built the indexing workflow (pick peaks, fit peaks,
index, judge) on rietx's own output for fluorapatite (`FAP.XRA`, the shipped
real lab Cu Kα pattern). It found that the old GUI's indexing is a dead end on
that pattern, for two server reasons:

1. **The extinction screen is refused on a project with no phase.**
   `GuiSession.run` (`src/rietx/gui/session.py`) refuses the kinds `fit`,
   `stage`, `extinction` and `series` through `_refuse_without_phases` before
   the worker starts (WP-1207, `fb4f87320`, 2026-08-26). The screen needs no
   phase: `determine_extinction_symbol` takes the pattern, the candidate and
   the instrument, and builds its own Le Bail fits. WP-1027 ruled the screen
   ungated ("a screen is a read-only measurement"), and a pattern-only project
   is exactly where indexing starts. The refusal also reads "a extinction run".
   Verified on `origin/main` `63d7c120a` (2026-11-09): the tuple still holds
   `"extinction"`.
2. **Adopt is gated to `best_or_none()`.** `index_adopt` refuses any candidate
   but the one `IndexingResult.best_or_none()` returns, with `ADOPT_GATED`
   (409). `best_or_none()` returns a cell only when exactly one candidate is
   graded `high` with no ambiguity partner. On FAP nothing reaches `high` in
   any of the three runs round 11 made, so no candidate can be adopted, the
   right one included. Verified on `63d7c120a`.

A third gap is smaller. `peaks_pick` passes only `shoulders` to the picker.
The 2θ range comes from the project's fit limits, and `flag_contamination`
(the Kβ and tungsten ghost marks) is reachable only from the library. The
redesigned Pick step offers all three of `pick_peaks`'s options before the
first pick and again under "Picking settings" (round 11b, 2026-11-08).

### The ruling on Adopt (Yue, 2026-11-08)

Options put to the maintainer: (A) keep the gate; (B) any candidate, with its
evidence shown at the Adopt step and recorded in history; (C) any candidate
without a refuting caveat. **Ruled B on 2026-11-08.** A person may adopt any
candidate cell. One the gate did not pick carries its grade and caveats, shown
beside Adopt and recorded in the `edit_model` history node the adoption makes.

This reverses WP-1027's gated Adopt ("Adopt is per-row and disabled with a
tooltip when `confidence != "high"` — the UI must not be the place the gate
leaks") for the GUI. Its ground is WP-1043's governing sentence, the
maintainer's of 2026-08-06: give a person "all the information, and let the
user, human or machine, be the judge". `best_or_none()` itself stays as strict
as it is; it is "a convenience for a caller that has declared it wants one
cell, never the shape of the answer" (WP-1043). Practice agrees: every program
the workshop surveyed (GSAS-II, TOPAS, DASH, FullProf) lets the user pick any
candidate, and none refuses one.

Option C would have blocked the right cell too. FAP's right cell carries
`fom_panel_disagrees`, which is one of the six refuting caveats
(`INDEX_REFUTING_CAVEATS`).

### The pieces

- `src/rietx/gui/session.py`: `run` (the phase refusal), `index_result` (the
  per-row `adopt` arm), `index_adopt` (the gate), `_adopt_refusal`,
  `peaks_pick` and `_peak_editor`. Other runners edit this file for WP-2123 and
  WP-2125, so the edits stay inside these functions.
- `src/rietx/gui/peaks.py`: `PeakEditor.pick` and the editor's lazy detection.
- The old Peaks panel (`gui/src/panels/Peaks.svelte`) reads `adopt[i].allowed`
  for both the Adopt button and its `best_or_none()` badge. This WP does not
  edit `gui/src` (WP-2123 is rebuilding the shell and the committed dist), so
  the arm keeps that field's old meaning for the old panel and adds new ones
  beside it.

### The tier of each rule this WP adds

None. Removing the Adopt gate removes a rule; the grade and caveats recorded
are the package's own fields, quoted. The pick options are the library's
existing arguments passed through.

## Non-goals

Left for later port WPs (not here):

- The Peaks panel hides `systems_searched`, `search_complete` and the
  run-level `INDEX_*` diagnostics whenever there are candidates, against
  WP-1042's rule that what was not searched is said loudly. Frontend.
- The old panel's Adopt button and badge: the button follows the gate's pick
  until the port redraws the panel on the new arm.
- Per-line peak curves (`PeakEditor.curves` serves each group's sum only).
- The peak-mark colour (`--plot-peak`, purple, loses to the data crosses).
- The Le Bail check's absent lines served as tick indices; `.rxt` user
  variables; overruled flags kept by `set_flags`; right-click menus; undo for
  peak edits; the series gaps.

## Tasks

- [x] 1. The extinction screen runs on a project with no phase. Take `extinction` out of the refusal; the message then reads "a fit/stage/series run". Test: a pattern-only project screens a candidate and gets classes back.
- [ ] 2. Adopt takes any candidate. `index_adopt` drops `ADOPT_GATED`; an unpicked candidate's label records "not the gate's pick", its grade and its caveats. The `adopt` arm per row: `allowed` keeps the gate's pick for the old panel, `picked` says the same under its true name, `note` is the sentence the node will record. Tests: adopt a `low` candidate, read the node label.
- [ ] 3. The pick route takes `two_theta_range` and `flag_contamination` beside `shoulders`; `pick_options` records all three, and the editor's later refits use the detection and marks the stored list was picked with. Tests: a narrowed range, contamination off and kept off through an edit.
- [ ] 4. Lattice relations between candidates ("c doubled", "a × √3", "same cell"): measure how many of FAP's candidates `supercell_checks` relates under the GUI's default search. Take it only if the fix is clear-cut inside `indexing/`; otherwise file it here as a follow-up line.
- [ ] Tests: the GUI manual and route partition tests where a route's contract changed.
- [ ] Skill: none expected. The skill drives the python API, whose `best_or_none()` and `pick_peaks` do not change.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_gui_peaks.py tests/test_gui_server.py tests/test_gui_manual.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-1027 (the GUI peak picker; the ungated screen, the gated Adopt this reverses).
- WP-1043 (the indexing evidence view; "let the user, human or machine, be the judge").
- WP-1207 (a phase-free model is legal; the verb refuses).
- The gui-overhaul milestone record, `docs/milestones/gui-overhaul.md` § Owed to the port.

## Handover log

- **2026-11-09** — filed by a ghostshift runner from the gui-overhaul workshop's list of rietx defects owed to the port (round 11's indexing decisions). No open WP owns these: WP-1027 is closed, and the open indexing WPs (1969, 2076, 2078, 2112) touch the engines, not the session routes. Open PRs checked: none edits `session.py`; the contributor's `idx/c7-extinction-gate` merged as #939 and gates the screen's reference fit, not the phase refusal. The Milestone line moves to gui-overhaul once WP-2123 lands that milestone on `main`.
