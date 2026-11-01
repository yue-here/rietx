# WP-2041 — a tutorial shows the indexer abstain

Milestone: unscheduled · Status: 🔄 2026-10-24 — example found (a 45° cut); held until WP-1956 lands, by the maintainer's choice
Track: The repo's own process
Depends on: 1956
Priority: P4 2026-10-24 — teaching content, held on WP-1956: that repair changes both the example's caveats and the notebook's confident count

## Goal

One tutorial runs a search that ends with `best_or_none()` returning `None`, and its prose reads
the verdict line and the `INDEX_ABSTAINED` diagnostic off that output.

## Context

- Notebook 03 (`examples/tutorials/03_peaks_indexing_lebail.py`) used to be the example. Since
  WP-2002 removed the U, V and Y width floors (`879fb1bcc`), its candidate validates with 0 of
  105 reflections absent and grades `high`, so the verdict line names the cell. WP-2039 checked
  this on an `origin/main` snapshot (`e921947a0`), rewrote the section to what the output shows,
  and gave the search `budget_seconds=120`, because at the 30 s default a busy machine left svd
  unfinished and flipped the verdict to NO CELL.
- So "why the indexer abstains" now has no worked example in the tutorials. The section keeps
  one sentence on it and a link to `reference/diagnostics-indexing.html#index-abstained`.
- An abstention that depends on wall clock is the wrong example: it flips with machine load.
  The example needs a search that abstains on its evidence. Two candidates, neither measured: a
  peak list with too few lines for the gate, or one carrying stray lines past the allowance
  (WP-1969's defect, so it may stop abstaining when that WP lands).
- Edit `examples/tutorials/NN_*.py` and rebuild with `build.py`. Never edit the `.ipynb`.
  `build.py` lists every cell whose text output a rebuild changed; reread each one.
- **Measured 2026-10-24 on `41d76f6c1`** (arm64 venv, `[dev]`). The notebook's own pattern,
  cropped with `data.crop(10, hi)`, re-picked and searched with the notebook's `spec`:

  | 2θ max | lines | verdict | caveats on the true cell (all three engines found it) |
  |---|---|---|---|
  | 30 | 4 | NO CELL, nothing searched | `INDEX_DATA_INSUFFICIENT` |
  | 35 | 7 | NO CELL | panel_disagrees, panel_reduced, absent 5/14, shift assumed |
  | 40 | 15 | NO CELL | panel_reduced, absent 6/22, shift assumed; a 2 300 ppm off |
  | 45 | 15 | NO CELL | panel_reduced, absent 5/27, shift assumed; cell to 0.0006 Å |
  | 50 | 20 | NO CELL | absent 5/37, shift assumed |
  | 60 | 30 | NO CELL | absent 4/56 |
  | 80 (notebook) | 54 | CELL, `high` | none; absent 0/105, shift measured from 8 pairs |

  The 45° cut gave the same output on three concurrent runs beside eight CPU-bound processes
  on ten cores (23 s each against 11.5 s alone).
- **Every absent reflection in every cut is a P m c n extinction** — (010) 11.09°, (001)
  15.43°, (101) 23.68°, (120) 28.71°, (201) 39.54° — counted against the cell because the
  validation tests the lattice in Pmmm (the indexing CLAUDE.md's `predicted_but_absent` rule).
  **The full range's 0 of 105 is the validation fit's background, not the data**: it sits at
  125 counts over 10-11° and 46 over 75-78° against a true flat 200, and 10-19° holds no allowed
  reflection at all. So the notebook's `high` passes because the refuting caveat went blind —
  issue #916's mechanism (a candidate's fit buys its absences by sinking the background) on the
  *correct* cell. WP-1956 owns the repair; this WP changes no indexer code.

### Inherited

- **2026-10-27, from WP-2011: notebook 03's indexing prose was rewritten for the
  Pawley validation.** The candidate now validates at Rwp 0.044 with 0 unmatched
  peaks, so the `INDEX_IMPURITY_LINES` paragraph went, and the row's 24 of 87
  absent lines are stated with what the gate reads of them: the absent lines no
  space group could remove, inside the first twenty lines, of which there are
  none (`examples/tutorials/03_peaks_indexing_lebail.py`, near line 163). The
  verdict is still `high`. The 125-against-200 background quoted in § Context
  was the Le Bail fit's; not re-measured under Pawley.

## Non-goals

- Changing when the indexer abstains: WP-1969 and `src/rietx/indexing/`.

## Tasks

- [x] Find a shipped pattern or a peak-list cut of one that abstains on evidence, stable across
      three runs on a loaded machine. Record the verdict line and the grade in the handover.
- [x] **Decision (maintainer):** how much the notebook says about the full range's sunk
      validation background. *Decided 2026-10-24: hold this WP until WP-1956 lands* (option
      C of four: correct the confident section now and add the example; add the example
      alone; hold; do nothing).
- [ ] After WP-1956: re-run the 45° cut and the full range on `main`. Add the cut to notebook
      03 after the confident search, with prose that reads the output, and rewrite the
      confident section's "none of the reflections it predicts is missing" to what the
      repaired count says.
- [ ] Skill: none. The skill's indexing reference already covers `best_or_none()`.

## Acceptance

```sh
.venv/bin/python examples/tutorials/build.py --check
.venv/bin/python -m pytest tests/test_tutorials.py -q
```

## References

None.

## Handover log

### 2026-10-24 (2nd session) — an abstaining example found, and the confident grade it sits beside rests on a sunk background

Tutorial 03's own pattern, cut at 2θ = 45°, makes the indexer abstain on its evidence. All
three engines find the true cell and the grade is `low`, the same on three runs under load.
The search also showed why the notebook's existing confident verdict passes. Over the full
range the indexer's validation fit puts its background up to 154 counts below the data, so
the space group's forbidden reflections read as present and the missing count is 0 of 105.
WP-1956 owns that repair. The maintainer chose to hold this WP until it lands, because the
repair changes both the example's caveats and the confident section's numbers.

- *Measured* (arm64 venv, `[dev]`, macOS, on `41d76f6c1`): the table in Context. The 45°
  cut prints `NO CELL: the result abstains — see the diagnostics below.` Its candidate is
  orthorhombic P 7.9706 5.7388 4.9614 Å, `low` for fom_panel_reduced, predicted_but_absent
  and shift_allowance_assumed, found by dichotomy, svd and trial_error, 14 of 15 lines,
  Le Bail Rwp 0.0827, 5 of 27 absent. It took 11.5 s alone. Three concurrent runs beside
  eight CPU-bound processes on ten cores took 22.9-23.1 s each, with identical output and
  no engine at its cap.
- *Decided*: see the Tasks entry.
- *Gotchas*: the probes lived in the session scratchpad and are gone. Each is a dozen
  lines: the notebook's setup cell, `data.crop(10, hi)`, `rx.pick_peaks(cut, lab)`, then
  `rx.index_pattern(peaks, data=cut, instrument=lab, spec=spec)`. The background numbers
  come from `indexing.workflow.validate_by_lebail(c, cut, lab, peaks=peaks,
  with_result=True)`.
- *Forward*: WP-1956's `### Inherited` carries the aragonite case and asks its closer to
  write the post-repair grades into this WP's `### Inherited`.
- *Not run*: the code review (a prose-only branch), the fast suite (no code or test
  changed), the generality judge (no heuristic added).

Next: when WP-1956 lands, read the note it leaves here, then re-run the 45° cut and the
full range on `main`. If the cut still abstains on its two capping caveats, write the
second task on that output. If the full range drops to NO CELL, the notebook's confident
section needs rethinking before anything is added, and that is the maintainer's call.

- **2026-10-24** — Created from WP-2039's inherited note to WP-2040, because no open WP owns
  tutorial content: WP-1969 changes when the indexer abstains, and WP-2040 adds links only.
  Next: the first task.
