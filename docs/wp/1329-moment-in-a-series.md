# WP-1329 — the moment in a series: the onset, the hold, the trajectory

Milestone: magnetic · Status: ✅ 2026-11-01 — all five tasks landed (task 5, the Ba₂FeSbSe₅ ramp, by PR #1073); the three folded notes moved to WP-1327
Depends on: 1327 (the moment); 1326 soft (the satellite arm per pattern)

## Goal

A temperature series through a magnetic ordering transition refines the
moment on every pattern below the onset, holds it at its floor above, and
reports |m| against temperature as a measured trajectory with esds, with the
onset located by the data rather than declared. The k = 0 ambiguity 1326
names on one pattern is resolved the only way a powder can resolve it: by
the pattern of the same specimen above the transition.

## Context

Fourth rung of the magnetic scattering track (ROADMAP § Unscheduled). The
package's strength is the in-situ series (`sequential.py`, WP-1051, 1127,
1305), and an ordering transition is the series a neutron user runs: the
same specimen through T_N, the moment growing from zero.

**The hold is already the rule; the series is where it earns its keep.**
1327 holds a moment block at its floor when the data does not support it
(WP-1301's shape: a flat direction is held for the stage, never bounded, and
re-measured at the answer). Chained by warm start across 68 patterns, that
rule decides on every pattern whether the moment is *released* (the block
lifts off its floor) or *held*, exactly as 1301 decides whether a phase has
appeared. The onset is then the first pattern, in each direction of the
chain, where the block is released; `direction="both"` flags the two
disagreeing (`SEQUENTIAL_PATH_DEPENDENT`), and `SEQUENTIAL_PERSISTENT_FINDING`
says "held on 42 of 68" for what no per-pattern finding can say.

**What the trajectory is.** |m|(T) is the order parameter, and its esd on
each pattern is conditional on that pattern's fit; the series prints the
trajectory (WP-1305's fourth deliverable) with the held patterns marked as
held, not as zero with an esd. A critical-exponent fit m ∝ (1 − T/T_N)^β is
nonlinear in its coefficients and stays fenced with `Parameter.expr`
(WP-1119, WP-1325); the trajectory is the deliverable, and a user fits the
exponent to it.

**The satellites per pattern** (1326's arm) give the onset a second reading
for k ≠ 0: the pattern where the satellites first carry extracted intensity.
Two readings that disagree are reported as a disagreement, not averaged.

**Cost.** A magnetic supercell (1327) multiplies the atom and reflection
count on every pattern of the chain; the ratio against the nuclear-only
chain on the same data is reported as a range, never gated.

## Non-goals

- A joint fit over the series with one θ (`multi.py`), or the parametric
  form of m(T): WP-1325's question, measured there.
- Locating T_N by any means other than the hold and the satellites.
- Anything the single-pattern rungs own.

## Tasks

- [x] The series drives 1327's hold per pattern: released/held recorded in
      each entry, the onset in each direction of the chain, the
      path-dependence flag when they disagree. (PRs #522, #589)
- [x] The trajectory: |m|(T) with esds, held patterns marked as held, printed
      by 1305's series view; the satellite reading beside it for k ≠ 0.
- [x] Manual Part 1 (`using/series.md`), skill row, the diagnostic's
      protocol row. (Ticked 2026-10-03 from the tree: `using/series.md`
      § A moment through an ordering transition, `references/series.md`
      § the same, `SEQUENTIAL_MOMENT_HOLD`/`_ONSET`.)
- [x] Tests on a synthetic ramp built from 1327's model (moment following a
      declared m(T), noise from the pattern's own σ): the onset lands within
      one pattern of the declared T_N in both directions; obs/calc/diff PNGs
      and the trajectory plot to `tests/output/`.
- [x] A real ramp, if one is public: search the corpus, then ask.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_magnetic_series.py -q
.venv/bin/python -m ruff check src tests examples
```

- On the synthetic ramp, every pattern above the declared T_N reports the
  block held; every pattern below reports it released; the onset agrees
  between directions within one pattern.
- The trajectory's held entries carry no esd; the released entries' esds
  come from each pattern's covariance.
- The Cr₂WO₆ pair (4 K released, 150 K held) as a two-pattern series gives
  the same answers as 1327's single-pattern fits, bit-identical.

## References

- Stinton, G. W. & Evans, J. S. O. (2007). *J. Appl. Cryst.* **40**, 87 —
  parametric Rietveld, the form this WP does not take (WP-1325 measures it).
- [1327](1327-magnetic-structure.md) the moment and its hold;
  [1326](1326-satellites-without-a-moment.md) the satellite arm;
  [1301](1301-hold-unsupported-phase.md) the hold rule;
  [1305](1305-series-deliverable.md) the series view;
  [1325](1325-parametric-series.md) the parametric question.

## Handover log

- **2026-11-01** (ghostshift close-batch, PR #1287) — closed. A temperature series through an ordering transition refines the moment where the data support it, holds it at its floor above the onset, and reports |m|(T) with esds. A real k ≠ 0 ramp (Ba₂FeSbSe₅ on LLB G4.1, PR #1073) brackets the onset at 50 → 55 K in both chain directions, against the bulk T_N of 58 K. The three notes that stopped yesterday's close are folded into WP-1327 (the owner of the moment and its hold), so nothing is lost.
  *Done*: the maintainer ruled on 2026-11-01 to fold the three owed notes into an open WP where a seam fits. All three went to WP-1327's `### Inherited`: the joint-fit hold of a per-histogram moment, the powder-twin reading of path dependence, and the provisional declaration for `MagneticTrajectory` and `MagneticOnset`. WP-1327 is held by no session and no open pull request names it. WP-1418 and WP-1419 were not used, since the contributor has open PRs on both. This WP's `Priority:` line and `### Inherited` section are deleted, and the narrative moved to the v1.11 record. The other Inherited notes were informational (1964 owns the critical-exponent law; the `k` naming rule is in root CLAUDE.md; `above_fence` is built).
  *Release*: none owed (P3).

- **2026-10-31** (ghostshift close-batch, not closed) — the checklist is finished and the WP is not. Five of five tasks are ticked and verified (task 5 by PR #1073, merged 2026-10-25, its test `test_ba2fesbse5_ramp_the_moment_grows_below_the_onset_both_ways` is in `tests/test_magnetic_series.py`). But `### Inherited` still holds three notes that ask for work and sit on no checklist, so closing would delete them: nothing reads a closed WP again (`closed_wp_writes.py`). The WP stays open until each is done or handed to an owner.
  *Still owed, each checked against the tree today*:
  (1) **The provisional declaration for `MagneticTrajectory` and `MagneticOnset`** (from WP-1541, 2026-10-03). Both are still defined in `rietx.schemas.sequential`, and `PROVISIONAL_MODULES` (`tests/api_surface.py`) has no key for that module or a magnetic-series module. Only the compatibility page's prose names them provisional (`reference/compatibility.md`, § Provisional by declaration). The note's fix: move both into their own module, re-export from `rietx.schemas.sequential`, declare it, drop the prose sentence.
  (2) **The powder twin read as path dependence** (from WP-1938 D13, 2026-10-11). The maintainer asked for a new WP and it was folded here by the fold-first rule. `sequential._angle_paths` and the two fences still take an angle modulo a turn only; nothing in `sequential.py` compares a moment's direction modulo the twins a powder cannot separate (time reversal for all moments of a phase, a mirror that fixes the site). The note's test series is `tests/test_moment_angle_chart.py`.
  (3) **A joint fit never holds a per-pattern moment as flat** (from WP-1325, 2026-10-14). `multi._flat_moments_multi` still compares scoped free paths against bare entry names. The note says it was found by reading the code and never run, and this session did not run it either.
  The other Inherited notes are informational (1964 owns the critical-exponent law; the `k` naming rule is in root CLAUDE.md; PR #522's `above_fence` hook is built) and can go with the section when it is deleted.
  *Next*: a maintainer ruling on where (1)-(3) live. Cheapest: tick them here as tasks and run them in one session (the twin fence and the joint hold share `sequential.py`/`multi.py` and the moment-angle fixtures). Or file one WP for them under the magnetic milestone and close this one. Either way the close then moves this narrative to the v1.11 record.

### 2026-10-25 — task 5 landed: the Ba₂FeSbSe₅ ramp on LLB G4.1, by `/pr-review`

Task 5's real ramp is in the tree. PR #1073 (outside contributor) merged as
`4cfd4598`. It vendors twelve of the 23 corrected G4.1 neutron patterns of
Ba₂FeSbSe₅ (λ = 2.426 Å, 1.5-200 K). The co-author M. W. Gaultois released
them under CC BY 4.0 in a comment on the PR, and the README and
`ATTRIBUTION.md` rows link it. It adds
`test_ba2fesbse5_ramp_the_moment_grows_below_the_onset_both_ways`: a slow
test, characterisation tier, and the first k ≠ 0 series in the tree. The model
is the class a blind `solve_magnetic` ranked first (k = (½, 0, ½), BNS 11.55).
The plan is the one `solve_magnetic` ships, run with `direction="both"`. Both
chains bracket the onset at 50 → 55 K, 3 K under the bulk T_N of 58 K. The
moment at 55 K is only 1.9 times its esd, so a verdict-based onset sits below
T_N. The 1.5 K moment is 3.875 ± 0.131 μ_B forward and 3.882 ± 0.124 μ_B
backward, against the paper's 4.13(4) under another code. All 24 fits
converge.

*Done:* the protocol fits from 5.2° (above the direct-beam tail), with the
data-sized P-spline background, and ties the 28 child Biso to their 7 parent
sites through `site_map`. Untied, the Fe Biso ran from −8.8 to +23.6 Å². The
tie costs Rwp 5.21 → 6.13 % at 1.5 K, and that misfit is unidentified; a
displacive distortion is one candidate. The fixture runs on the numpy path,
declared. Gated in a stack with #1111 on tree `1923c693` (main `f9a983d7` +
both PRs; macOS arm64, Python 3.12.10, `[dev,jax]`, nothing else running): the
whole suite, slow tests included, 12 255 passed, 206 skipped, 43 xfailed in
35 min; the ramp test took 120 s. Main after the last merge is that tree.
*What it does not do:* free the magnetic widths, which cost BIC at every
temperature measured (WP-1343's business). It does not identify the misfit the
Biso tie exposes. It vendors only twelve of 23 patterns; the other eleven stay
out.
*Gotcha:* `BISO_NEGATIVE` stays on Ba at 1.5-100 K, within its esd. These
patterns do not determine the parent Biso (esds 2.6-5.8 Å² in the nuclear fit),
so one overall B moves the moment by under 0.3 esd.
*Next:* every task is done, so the WP is ready to close.

### 2026-10-21 — the two codes' skill rows moved to the magnetic file, by `/pr-review`

The skill's rows for `SEQUENTIAL_MOMENT_HOLD` and `SEQUENTIAL_MOMENT_ONSET`
now sit in `references/magnetic.md`, in a new § Series codes, beside the rest of
the magnetic family. That is issue #286's ruling (one order-parameter question,
one file), and PR #385 set the precedent of moving codes to where their reader
meets them. An agent reading a moment series now finds both codes in the file
it is already reading for the moment.

*Done:* PR #1062 (`0669ea6e`, outside contributor), merged as `e1cab2ee` by
`/pr-review`, in a five-PR stack gated together. The row text moved unchanged.
`series.md` keeps a pointer beside its `SEQUENTIAL_PERSISTENT_FINDING` one, and
its count went from eleven to nine, so nine table rows, the abstention and the
two moment codes still make "the twelfth" true. All three skill copies were
re-synced byte for byte. The gate was the fast suite and the full `-m slow`
suite on the merged tree of main `05ac4bac` and the five PRs. `main` after the
last merge is that tree.
*What it does not do:* touch task 5. PR #1073 (row H, Ba₂FeSbSe₅ on LLB G4.1)
is an open outside PR for task 5, not yet reviewed.
*Gotcha:* the PR landed after #1050 had edited `references/magnetic.md`. The two
merged clean, and the combined file was read before the merge.
*Next:* task 5 (#1073 is the candidate).

### 2026-10-03 — the checklist follows the status, by a cleanup session

Tasks 1-4 had landed in PRs #522 and #589 with their boxes left open. They
are ticked, each checked against the tree: the manual's § A moment through an
ordering transition, the skill's `references/series.md` row, and the
`SEQUENTIAL_MOMENT_HOLD`/`_ONSET` codes. *Next:* task 5, a real ramp; GSAS-II's
tutorials are where WP-1326 found its public neutron data, so look there first.

### 2026-10-01 (2nd session) — both review follow-ups landed

Both follow-ups from PR #522's review are on `main`. Two chains that bracket the
onset in one place now agree only when they order the same side, and
`SeriesEntry.magnetic` names its real writer. Task 5 is what remains.

*Done:* PR #589 (`66ca3d7c`), merged as `b83fd06c` by `/pr-review`.
`_with_onset_agreement` needs `mine.sense == other.sense` as well as overlap, and
opposite senses get their own `warning` with the `_COMPARE_CHAINS` advice.
*Next:* task 5, a real ramp longer than the Cr₂WO₆ pair.

- **2026-10-01** — A sequential magnetic refinement now reports the moment
  per pattern and where it switches on. Each `SeriesEntry` carries the moment
  arm, `SeriesResult` brackets the onset in each direction of the chain and
  folds the two readings, and the trajectory plot marks the held patterns.
  *Done:* PR #522 (`67e9737e`), merged as `05646879` by `/pr-review`, closing
  #481; `SCHEMA_VERSION` is 0.38. Tested on a synthetic ramp and on the public
  Cr₂WO₆ HB-2A pair. It was reviewed over five rounds; the last head was a
  rebase, and `git range-diff` shows only the claim commit changed.
  *Gotchas:* `SeriesEntry.magnetic`'s comment names `_entry_from_result` as
  its writer, but the writer is `_moment_evidence`, called in `_chain`
  (`sequential.py:1577`). `_with_onset_agreement` does not compare `sense`, so
  two brackets that overlap with opposite senses read as agreeing. Both were
  posted as follow-ups. *Next:* the two follow-ups. Task 5, a real public ramp
  (search the corpus, then ask), is open.

- **2026-09-02** — created, from the assessment of PR #221, which did not
  reach the series. Added because the ordering transition is the neutron
  series a user runs, and the hold rule the moment needs on one pattern is
  the onset detector on many. No code touched. First task is the per-pattern
  hold record.
