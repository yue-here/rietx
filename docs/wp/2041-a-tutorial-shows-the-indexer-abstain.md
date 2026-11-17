# WP-2041 — a tutorial shows the indexer abstain

Milestone: unscheduled · Status: ✅ 2026-11-15 — PR #1570; notebook 03 shows the indexer abstain on a 45° cut
Track: The repo's own process
Depends on: 1956

## Goal

One tutorial runs a search that ends with `best_or_none()` returning `None`, and its prose reads
the verdict line and the `INDEX_ABSTAINED` diagnostic off that output.

## Context

*Superseded in part 2026-11-15: the abstaining example has landed in notebook 03, and the
full range now reads 24 of 87 lines absent under the Pawley validation. See the newest
handover entry. The bullets below are the record as written.*

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

## Non-goals

- Changing when the indexer abstains: WP-1969 and `src/rietx/indexing/`.

## Tasks

- [x] Find a shipped pattern or a peak-list cut of one that abstains on evidence, stable across
      three runs on a loaded machine. Record the verdict line and the grade in the handover.
- [x] **Decision (maintainer):** how much the notebook says about the full range's sunk
      validation background. *Decided 2026-10-24: hold this WP until WP-1956 lands* (option
      C of four: correct the confident section now and add the example; add the example
      alone; hold; do nothing).
- [x] After WP-1956: re-run the 45° cut and the full range on `main`. Add the cut to notebook
      03 after the confident search, with prose that reads the output, and rewrite the
      confident section's "none of the reflections it predicts is missing" to what the
      repaired count says. *(The rewrite had already landed with WP-2011; the full range's
      output is unchanged, so the confident section stands.)*
- [x] Skill: none. The skill's indexing reference already covers `best_or_none()`.

## Acceptance

```sh
.venv/bin/python examples/tutorials/build.py --check
.venv/bin/python -m pytest tests/test_tutorials.py -q
```

## References

None.

## Handover log

### 2026-11-15 — notebook 03 shows the indexer abstain on a 45° cut

Tutorial 03 now runs a second indexing search on its own pattern cut at 45° 2θ, and that
search abstains. The true cell still ranks first, found by all three engines, but at `medium`.
Two caveats hold it there, and both say the data are too short: 15 lines is below the 20 the
classical figures of merit are scored on, and 15 lines give no measured 2θ shift. The prose reads
the verdict line, `INDEX_ABSTAINED` and `best_or_none()` returning `None` off that output. The
full range's confident section needed no change, because WP-2011 had already rewritten it and
its output is the same on today's `main`. One thing in the new output is a false alarm: an
`INDEX_IMPURITY_LINES` warning on the strongest line's tail, which the prose explains and
WP-2113 inherits.

- *Measured* (arm64 venv, `[dev]`, macOS, on `978bf43c1` = `main` `98d7ba8e3` plus the claim;
  load average 9-11 throughout). Probe `~/.cache/ghostshift/rietx/wp-2041/probe.py <hi>`: the
  notebook's setup cell, `data.crop(10, hi)`, `rx.pick_peaks`, then `rx.index_pattern` with the
  notebook's `spec` (`budget_seconds=120`).
  - 45° cut, three sequential runs, byte-identical output, 13.6, 16.5 and 13.8 s: `NO CELL: the
    result abstains`. Rank 1 orthorhombic P 7.97064 5.73879 4.96143 Å, V = 226.94 Å³, `medium`,
    not higher because `fom_panel_reduced`, `shift_allowance_assumed`; found by dichotomy, svd and
    trial_error; 14 of 15 lines; Pawley Rwp 0.0474; 6 of 23 lines absent. Same grade and caveats
    as the 2026-10-24 record on `0070d696`, so #1177, #1302 and WP-2076 moved nothing here.
    New since then: `INDEX_IMPURITY_LINES`, 1 region near 25.540°.
  - Full range, one run, 16.1 s: CELL at `high`, identical to the committed notebook (51 of 54
    lines, Pawley Rwp 0.0444, 24 of 87 absent, 0 uncancellable in window).
  - The impurity region is the 26.22° line's low-angle tail. The Pawley calculated curve sits at
    its background (211) up to 25.60° and starts the line's profile at 25.62°. The truth there is
    251-282 counts, and a noise high at 25.54° (307 observed) reaches Δ/σ 5.5. Plot of the
    validation fit looked at (`val_45.png` in the scratch directory). Recorded in WP-2113.
  - The rebuild also moved notebook 03's Le Bail cells, through code that landed since the
    1.11.0 rebuild: best pass Rwp 0.0533 → 0.0515, GoF 1.24 → 1.20, Y −0.0061(58) →
    −0.0052(56). Their prose ("no diagnostic", Y zero within its esd, ticks over no peak near
    11° and 15.5°) still holds; the plot was looked at.
- *Done* (PR #1570): the new section in `examples/tutorials/03_peaks_indexing_lebail.py`, the rebuilt
  notebook, the tutorials README row. The old one-line pointer to `INDEX_ABSTAINED` moved into
  the section.
- *Code review* (`/code-review high --fix`, eight findings). Fixed: the manual's tutorial
  table row (`docs/docs/start/tutorials.md`) now matches the README's; the assumed 0.050° is
  added "in quadrature"; the runtime line names two searches; "15 usable lines" became "15
  lines", since the cell shows only the indexing header. Declined: a timing report for the
  fast tier (no test added; the new cell adds one search, 13.6-16.5 s at load 9-11); this
  Context (now marked superseded in part). Not fixed here, no owner found: `INDEX_PANEL_REDUCED`
  says "The search runs over cubic, hexagonal, orthorhombic, tetragonal, trigonal", reading
  `quality.systems_supported` (`indexing/diagnostics.py:626`), while the search ran
  orthorhombic only (`spec.systems` ∩ supported, `workflow._restrict_to_supported`). The new
  cell prints it beside `INDEX_SYSTEMS_NOT_COVERED`, which says four of those were not
  searched. A fix changes reader output, so it goes to the maintainer.
- *Runtime not re-measured quietly*: the notebook still claims "under a minute". A rebuild at
  load average 23 on 10 cores took 137 s wall, 99.5 s user CPU.
- *Not run*: the generality judge (no heuristic added); the fast and full suites (no library
  code or test changed). The acceptance ran: `build.py --check` clean, and
  `tests/test_tutorials.py` 35 passed (arm64 macOS, `[dev]`), before the review's markdown-only
  fixes; after them `build.py --check` is clean and the outputs rebuilt unchanged.
- *Forward*: WP-2113's `### Inherited` (the tail family, and that a fix there changes this
  notebook's output).
- *CI on PR #1570* (steward, 2026-11-15) found two failures. `ruff format --check
  examples/tutorials` refused the new `index_pattern` call at 87 columns. And the section put
  notebook 03's markdown twin at 55 688 characters, over the page contract's 50 000
  (`tests/test_manual.py::test_every_page_has_a_twin_that_keeps_the_contract`, whose remedy
  is "split it"). So the section moved to its own notebook, `03b_when_the_indexer_abstains`,
  as 02's steering moved to 02b in 1.10. It repeats notebook 03's setup cell and reads notebook
  03's full-range numbers by name. Notebook 03 is back to `main`'s cells, plus a two-line
  pointer to 03b where the old one-line pointer to `INDEX_ABSTAINED` stood. Both tutorial
  tables carry a 03b row. *Settled by Claude under the page contract's cap and the 02b
  precedent*; the alternative was to trim notebook 03's outputs, which no cut of the new
  section alone brings under the cap (printing it without explanations saves 2 485).

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
