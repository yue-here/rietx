# WP-1329 — the moment in a series: the onset, the hold, the trajectory

Milestone: magnetic · Status: 🔄 2026-10-31 — all five checklist tasks landed (task 5, the Ba₂FeSbSe₅ ramp, by PR #1073); three folded notes in Inherited are still owed (the provisional declaration, the powder-twin fence, the joint-fit moment hold), so it stays open
Depends on: 1327 (the moment); 1326 soft (the satellite arm per pattern)
Priority: P3 2026-09-23 — waits on 1327's moment; P2 when it lands

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

### Inherited

- **2026-10-14 (review), from [1325](1325-parametric-series.md): the
  critical-exponent law has a WP of its own.** m ∝ (1 − T/T_N)^β was fenced
  with `Parameter.expr` (WP-1119). [1964](1964-a-nonlinear-law-through-the-derived-block.md)
  now owns laws nonlinear in their coefficients, built on WP-1804's derived
  block, and names this moment as a use case. Until it lands, the entry below
  holds: only forms linear in their coefficients are declarable.
- **2026-10-14 (later), from [1325](1325-parametric-series.md): a joint fit
  never holds a per-pattern moment as flat.** Under
  `SharingMap(per_histogram=["phases.*"])`, the series shape, a moment
  degree of freedom is per-histogram. `multi._flat_moments_multi` compares
  the scoped free paths (`hist.{h}.…`) against each table's bare entry
  names, so none matches and nothing is held. `_turn_flat_axes_multi` then
  writes one turn into every table, as it would for a shared moment. Found by
  reading the code, never run. 1325 fixed the same class for a phase's cell
  (`multi._unseen` judges each entry in its own histogram). A joint fit of a
  moment down a ramp is where this one would surface.
- **2026-10-14, from [1325](1325-parametric-series.md): a parameter can now
  be refined as a declared function of each pattern's coordinates, jointly,
  and the joint form measured a gain where one pattern cannot see the
  parameter.**
  - **The tool.** `rx.refine_multi(..., coordinates=rx.CoordinateTable(...),
    parametric=[rx.ParametricTie(...)])`, with `RefinementResult.parametric`
    in user units at the reference.
  - **Only forms linear in their coefficients.** m ∝ (1 − T/T_N)^β stays
    fenced (`Parameter.expr`, WP-1119). A polynomial in T over the ordered
    patterns only, `patterns=[…]`, is declarable. So is one law per side of
    a transition, on disjoint subsets.
  - **What it measured.** On a synthetic ramp whose minor phase fell under
    the WP-1301 hold:
    - the hard tie cut the slope's scatter to 0.72× the line through the
      chain's kept points;
    - under a wrong form (a curve in the gaps) its intervals covered 3 % at
      2 esd.

    A moment that falls toward T_N is that regime, so the moment trajectory
    is the series 1325 named as a further measurement. Run it here with a
    polynomial in (1 − T/T_N) below a declared T_N, and check the form
    against the chain before quoting it.
- **2026-10-11, from WP-1938 D13 (fourth session): the fences read a
  powder twin as path dependence.** Reversing every moment gives the same
  powder pattern, and so does a mirror of the lattice that fixes the site. On
  `tests/test_moment_angle_chart.py`'s series (one Mn on **a** in P m m m)
  the backward chain crosses patterns where the azimuth is unmeasured (esd
  10²-10⁴) and comes out on a twin: φ = 0.077 under LM, −0.077 under TRF,
  against the forward chain's 3.065 at p000, at equal χ². Both fences
  (`sequential._path_dependence_diagnostics`, `_discontinuity_steps`) take an
  angle modulo a turn only (#604), so they report up to 97σ. The test now
  allows that one finding where the two chains are twins. The task this
  opens: compare a moment's direction modulo the twins the powder cannot
  separate. Time reversal is universal, and a phase reverses all its moments
  together. A mirror depends on the crystal and on the site. The GUI's
  disagreement column must measure what the fences do (`sequential._angle_paths`).
  The maintainer asked for a new WP. It was folded here instead, because
  this WP owns the moment's path-dependence flag (task 1) and the template
  folds into an open owner first.
- **2026-09-29, from [1469](1469-what-the-series-fences-cannot-see.md): a
  frame the Rwp fence rejected on every rung now has a code, and PR #522
  named the hook.** `SeriesEntry.above_fence` (derived from the new
  `SeriesEntry.rwp_fence`) is true where `SEQUENTIAL_RWP_OUTLIER` fires. Such
  a pattern is **not** quarantined: it seeds its successor and joins the
  median, because the fence cannot tell a blank frame from a lasting change
  (#481's blank had GoF 1.00 against 1.06). PR #522 said a frame "whose kept
  rung still trips the reseed fence, but whose phase is still visible, gets a
  verdict like any other" and that treating the new code as "no verdict" is
  the natural hook; `above_fence` is the field to read, and the step scan
  already leaves such a pattern out. Both PRs bump `SCHEMA_VERSION`: 1469
  takes 0.35 → 0.36, so whichever lands second renumbers, and
  `tests/test_magnetic.py`'s capability pin moves with it.
- **2026-09-17, from [1436](1436-k-is-the-wavevector-everywhere-else.md):
  `k` is free for the propagation vector.** The earlier note here warned that
  `scattering.py`, `structure_factor.py` and `dispersion.py` all spent `k` on
  sinθ/λ, in the same subpackage `crystallography/magnetic/` lives in, and
  asked this WP to spell the propagation vector out rather than add a second
  bare `k`. 1436 has landed: that quantity is `stol` in python and `s` in
  equations throughout, following Waasmaier & Kirfel and the IUCr core
  dictionary, and a tree-wide sweep found no line left pairing a bare `k` with
  sinθ/λ in `src/`, `tests/`, `examples/` or the manual. **So name the
  propagation vector `k` and add no qualifier.** Root CLAUDE.md § Conventions
  carries the rule that keeps it free. The same note is in 1326, 1327, 1328 and 1418.
- **From WP-1541 (2026-10-03): `MagneticTrajectory` and `MagneticOnset`
  shipped in 1.6.0 without a provisional declaration a test can see.** Both
  are defined in `rietx.schemas.sequential`, beside 102 stable names, so no
  `PROVISIONAL_MODULES` prefix can cover them. The cut named them provisional
  in prose, in `using/compatibility.md` and the 1.6.0 notes. The mechanised
  fix is to move both into a module of their own (for example
  `rietx.schemas.magnetic_series`), re-export them from
  `rietx.schemas.sequential`, and declare it, with the reason that they were
  measured on a synthetic ramp and one two-pattern pair and the bracket-folding
  rule changed after they landed (#589). Then drop their sentence from the
  compatibility page.

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
