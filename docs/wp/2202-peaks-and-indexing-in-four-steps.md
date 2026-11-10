# WP-2202 — Peaks and indexing in four steps: pick, fit, index, judge

Milestone: gui-overhaul · Status: 🔄 2026-11-10 — filed and started by a ghostshift runner
Depends on: 2123, 2124, 2130 (the shell, the indexing server half, the coverage line and Adopt on every row)

## Goal

The Peaks tab in the model panel walks a person through indexing in four steps, named as the
maintainer named them: Pick peaks, Fit peaks, Index, Judge. Each step shows only what that step
needs. Index ends in a candidate table of eight columns, Judge holds one candidate's evidence,
its extinction screen and Adopt. The pattern marks the picked peaks with lenses that echo the
reflection ticks, and the fit windows draw each line's own curve under the group's sum.

## Context

### Where this comes from

Round 11 of the GUI design rounds (2026-11-08) built the indexing workflow on rietx's own output
for fluorapatite (`FAP.XRA`, the shipped lab Cu Kα pattern) and the maintainer closed it with
"looks good"; all 35 of its settled calls stand. On 2026-11-09 the maintainer asked that the
Peaks panel look like that design, so the redesign became a filed piece
(`docs/milestones/gui-overhaul.md`, the "Peaks and indexing" row). WP-2130 fixed two gaps in
the old panel first: the search coverage is said above the list whatever the run found, and
every row can be adopted. Both stay.

The authority is `gui/STYLE.md` (WP-2142, approved 2026-11-09). A piece is judged against the
guide, completed by its motives where the prototype is unfinished, and visual questions the
guide does not settle go to the maintainer.

### The design, restated (round 11 and its follow-ups, 2026-11-08)

The four steps sit as a step strip at the top of the Peaks tab: numbered buttons, the current
one raised. STYLE: "A workflow keeps the window and shows its steps across the model panel."
The workflow menu that will open it is its own milestone row; until it exists the Peaks tab is
the workflow's home, so no route or tab becomes unreachable.

1. **Pick peaks.** Before the first pick: the picker's three options (2θ range, "Look for
   shoulders", "Flag Kβ and tungsten lines", `pick_peaks`'s own) and one filled Pick peaks
   button. After it: a segmented filter (All, Used, Not used) over a table of every line with a
   tickbox (use in the search), 2θ, d, intensity and a note in words (the flags, "added by
   you", "moved by you"). Unused lines are greyed rows whose tickbox brings them back. The
   picker's notes sit under a disclosure, and so do the picking settings with Pick peaks again,
   which says how many edits it replaces before it runs (round 11c call 29, 11d). A row click
   frames its line on the plot (interaction rule 5).
2. **Fit peaks.** The overlap groups, filtered "To look at" (χ²ᵣ above 10, or a flag other than
   asymmetry: call 13, measured on FAP, where χ²ᵣ > 3 flags 84 of 117 groups and asymmetry is
   on 36 lines) or "All groups", with the 2θ span, the line count, χ²ᵣ and the notes. The graph
   shows the group windows: data, the fit, the background envelope, the line marks and the
   residual in esd. Each line's own curve is drawn under the sum, as a tinted fill with a line,
   including its Kα2 partner, with numbered toggles per window (round 11b and 11c, calls 23
   and 30). Refit a group from its row.
3. **Index.** Three settings show: crystal systems, the largest volume and the time limit (call
   4; GSAS-II and DASH show three or four). Everything else sits one disclosure down. While the
   search runs: per-system status, elapsed and remaining time, and Stop (call 5). When it ends,
   what was not reached is said above the list (WP-2130's coverage line, WP-1042's rule), then
   the candidate table with eight columns: cell, lattice, V, M₂₀, unindexed, predicted absent,
   Rwp, grade (call 7). Related rows are marked, not merged: "same cell as #2", "#2 with c
   doubled" (call 8). A row selects the candidate and draws its ticks; Judge opens it.
4. **Judge.** Previous and next, the cell with esds, the grade and its caveats (refuting ones in
   the danger colour), the Le Bail check, every figure of merit, the engines, then the
   extinction screen: classes by ΔBIC with the absences tested, "rietx's pick" on the class the
   gate names, refuted classes muted (call 17). Choosing a class offers its space groups as a
   segmented choice; the default is the class's representative as rietx names it (call 10, 12).
   Adopt is the step's one filled button, with the grade and caveats beside it (ruling B,
   2026-11-08). A row the gate did not pick says its `why`, the sentence its node records.

**Marks** (round 11c and 11d). Lenses, the reflection ticks' shape, larger and higher above the
peak. A used line's mark is filled; an unused line has no mark on the pattern, and its greyed
row frames it with a dotted line. A selected mark is larger with a ring in `--fg`. Their colour
waits for the palette piece (ruled 2026-11-09), so `--plot-peak` stays as it is here.

### What the server already serves, and what it lacks

- `POST /api/peaks` takes all three pick options since WP-2124 (`shoulders`,
  `two_theta_range`, `flag_contamination`); the milestone's owed line about it is stale. The
  panel has sent none of them.
- `PeakEditor.curves` (`src/rietx/gui/peaks.py`) serves each group's sum (`y_fit`), its
  envelope and its residual. The per-line curves are new: the group model is linear in each
  component's area (`indexing.peakfit.group_profile`), so evaluating it with one area at a time
  gives each line's curve, and the lines sum to the group's model to rounding. They ride on the
  group as `lines`, beside `y_fit`, rather than on a route of their own: the panel draws them
  from the same payload, and a group carries one or a few lines of its own window's points.
- `GET /api/index/result` serves candidates with `ambiguity` (partners in another setting) and
  `supercell_checks`. Lattice relations between candidates ("c doubled", "a × √3") do not exist
  in rietx, so this piece marks only the relations rietx states and names the rest as a
  follow-up (the milestone's owed line).
- The Le Bail check's absent lines are positions in its own refined frame, about 0.011° from
  the candidate's ticks on FAP. Serving them as tick indices is a follow-up; Judge prints the
  counts and draws the ticks as today.

### The pieces

- `src/rietx/gui/peaks.py` `PeakEditor.curves`: the `lines` arm; `tests/test_gui_peaks.py`.
- `gui/src/lib/peaks.ts`: the pure helpers (steps, filters, the to-look-at rule, the eight
  columns, the relation line), tested in `lib/peaks.test.ts`.
- `gui/src/panels/Peaks.svelte`: the four steps.
- `gui/src/panels/PeakFits.svelte` (new): the group windows with per-line curves, drawn in the
  Single peaks graph while the Peaks tab is up.
- `gui/src/lib/pattern.ts` `peakMarkers`: the lenses.
- The manual's `reference/gui-guide.md` § Peaks; `tests/test_gui_peaks_browser.py`.

### The tier of each rule this WP adds

One threshold is new to the package: "To look at" (χ²ᵣ above 10, or a flag other than
`asymmetry_unmodelled`) is a view filter over the picker's own numbers. It changes which rows a
person sees first, never which lines reach the search, so it is a display choice in the GUI and
not a heuristic of the package (`rietx._audit` audits the package's diagnostics, defaults and
suggestions, and this is none of them).

## Non-goals

- The workflow menu, the plot's interaction grammar (select, a selection bar, Delete,
  Option-click, Esc to undo a drag), right-click context menus and undo for peak edits. They
  are adopted rules (2026-11-08) and belong to the plot across Pattern and Background as well,
  so a piece of their own builds them (§ Follow-ups).
- The peak-mark colour (the palette piece, ruled 2026-11-09).
- Lattice relations computed in rietx, the absent lines as tick indices, and an overrule that
  remembers which flags a person overruled (a `peaks.json` format change).
- "Search these" running a narrowed search, and keeping the indexing result across a restart (a
  stored-format change).

## Tasks

- [x] 1. File this WP and give it the milestone's "Peaks and indexing" row.
- [x] 2. Per-line curves: `PeakEditor.curves` serves `lines` per group; a pytest holds their sum
  to the group's model.
- [x] 3. `lib/peaks.ts` helpers for the steps, filters, groups to look at, the candidate columns
  and relations; vitest.
- [ ] 4. The Peaks tab in four steps (`Peaks.svelte`), the pick options sent to the route.
- [ ] 5. The fit windows with per-line curves (`PeakFits.svelte`) in the Single peaks graph
  while the Peaks tab is up.
- [ ] 6. Lens peak marks on the pattern; no mark for an unused line.
- [ ] 7. Manual § Peaks, browser tests updated, dist rebuilt, screenshots beside the
  prototype's.
- [ ] Skill: none. The skill drives the Python API, and this piece changes only the GUI.

## Acceptance

- `npm --prefix gui test` and `npm --prefix gui run check` pass; the dist is rebuilt and
  `tests/test_gui_dist.py` passes.
- `tests/test_gui_peaks.py`: each group's lines sum to its `y_fit` minus the envelope.
- Every `tests/*_browser.py` passes locally, with the Peaks steps driven by real clicks.
- `tests/test_gui_manual.py` passes: every route and tab stays reachable and documented.
- The maintainer has looked at the piece on screen (milestone acceptance row 10).

## Handover log

- **2026-11-10** — created by a ghostshift runner, which holds it in this session. No open WP owned the Peaks redesign: WP-2130 fenced it out as a later piece, and the milestone listed it as designed, not filed.
