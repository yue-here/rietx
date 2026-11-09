# WP-2124 — the indexing routes the GUI port needs: an ungated screen, any cell adopted, the pick's options

Milestone: unscheduled · Status: ✅ 2026-11-09 — the screen without a phase, any cell adopted, the pick's three options; candidate relations filed as a follow-up
Track: Render what the fit already knows
Depends on: —

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

- [x] 1. The extinction screen runs on a project with no phase. Take `extinction` out of the refusal, which leaves it only fit, stage and series, so it can no longer read "a extinction run". Test: a pattern-only project screens a candidate and gets classes back.
- [x] 2. Adopt takes any candidate. `index_adopt` drops `ADOPT_GATED`; an unpicked candidate's label records "not the gate's pick", its grade and its caveats. The `adopt` arm per row: `allowed` keeps the gate's pick for the old panel, `picked` says the same under its true name, `why` is the sentence the node will record. Tests: adopt a `low` candidate, read the node label.
- [x] 3. The pick route takes `two_theta_range` and `flag_contamination` beside `shoulders`; `pick_options` records all three, and the editor's later refits use the detection and marks the stored list was picked with. Tests: a narrowed range, contamination off and kept off through an edit.
- [x] 4. Lattice relations between candidates ("c doubled", "a × √3", "same cell"): measured, not taken. The premise is stale: under the GUI's default search on `63d7c120a`, 8 of FAP's 12 candidates carry a `supercell_checks` entry, not 2. What stays unnamed is a different relation, and naming it is a new field, so it goes to the follow-up below.
- [x] Tests: `test_gui_manual.py` and `test_manual_api.py` pass unchanged. No route was added or renamed; the `adopt` arm gained `picked` and the pick route three body keys.
- [x] Skill: none. The skill drives the python API, whose `best_or_none()` and `pick_peaks` do not change.

### Follow-up, not taken here

- **Name the relation between candidates.** On FAP's default search (122.6 s, cubic, hexagonal and trigonal searched, trigonal stopped early) four of 12 candidates carry no relation: rank 1 (a = 9.374, c = 13.825, c × 2.007 of rank 0), rank 2 (rank 0's metric labelled trigonal), rank 3 (within 0.06 % of rank 0) and rank 11 (a × 1.732, c +0.15 % of rank 0). The eight that do carry one say only `index` and the parent's cell, not which axis multiplied. Two kinds are missing. A same-metric relation ("same cell, trigonal setting", "within 0.2 %") is no supercell, so `SupercellCheck` cannot hold it. A worded transform ("c doubled", "a × √3") needs the sublattice's matrix, which the check does not keep. Either is a new field on `CellCandidate`, which changes what an indexing answer hands a reader (Yue's ruling of 2026-11-01), and the words are a name on the main user surface. Round 11 of the workshop computes them from the a and c ratios, for hexagonal axes only. It belongs to whichever gui-overhaul piece redraws the candidate table.

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

- **2026-11-09** — closed (PR #1478). A pattern-only project can now be indexed, screened and adopted through the GUI's routes, which on fluorapatite it could not: the extinction screen ran only once a phase existed, and Adopt refused every candidate because none reaches `high` there. Following Yue's ruling B of 2026-11-08, any candidate can be adopted, and one the gate did not pick writes its grade and caveats into the history node. The pick route takes all three of `pick_peaks`'s options, and the list keeps them through every edit. Next: the gui-overhaul piece that redraws the Peaks panel reads the arm's `picked` and `why`, enables Adopt on every row, and takes the candidate-relations follow-up above.
  - *Done*: items 1-4 as ticked; the `/code-review high --fix` pass made five fixes (5cda4d2be): a range holding no channels and a non-boolean flag answer 400 naming their field, the echo writes a whole-pattern pick under later limits as `two_theta_range=None` and keeps 12 digits, and the editor reuses a list its caller already read. Two findings declined: a `space_group` from another candidate's screen is not checked against the adopted cell (`structure_from_candidate` already refuses a group the cell cannot carry; refusing a compatible one is a product call), and the repeated "limits as a tuple" expression predates this branch.
  - *Sibling closed*: the pick declined the contamination marks while every refit re-added them, and a reopened session's editor detected with shoulders on regardless of the pick. Both were the editor ignoring the list's own options; it is now built from `PeakDoc.pick_options` (`peaks.settings_of`). Deliberately not generalised: the `f"a {x}"` article pattern elsewhere in `src/` (each site's values start with a consonant or are quoted), and the project's limits moving after a pick, which now leaves the editor on the pick's range rather than the new limits.
  - *Measured* (`[dev]` venv, darwin/arm64, alone on the lock): fast suite 14340 passed, 416 skipped, 32 xfailed in 11:27. Added tests: two new (`test_the_pick_route_takes_the_range_and_the_contamination_marks` 0.17 s, `test_a_list_picked_without_contamination_marks_gains_none_from_an_edit` 0.34 s) and one renamed (`test_adopt_is_gated_on_best_or_none_server_side` became `test_any_candidate_can_be_adopted_and_an_unpicked_one_records_why`, 0.03 s), so passed+skipped moves by +2 against main. Item 1's and item 3's tests were each failed once on purpose against the old code. FAP's default search: 122.6 s, 12 candidates, 8 with a supercell check. `python -m tests.reader_output` exit 0; `python -m tests.audit_delta` no row changed; the generality judge was not triggered (no table change, no new heuristic). Full suite not run: the change moves no measured number.
  - *Gotcha*: the gui-overhaul record on WP-2123's branch says `supercell_checks` relates 2 of FAP's 12 candidates; on `63d7c120a` it relates 8. The Milestone line stays `unscheduled` because that milestone has no ROADMAP section on `main` yet.
- **2026-11-09** — filed by a ghostshift runner from the gui-overhaul workshop's list of rietx defects owed to the port (round 11's indexing decisions). No open WP owns these: WP-1027 is closed, and the open indexing WPs (1969, 2076, 2078, 2112) touch the engines, not the session routes. Open PRs checked: none edits `session.py`; the contributor's `idx/c7-extinction-gate` merged as #939 and gates the screen's reference fit, not the phase refusal. The Milestone line moves to gui-overhaul once WP-2123 lands that milestone on `main`.
