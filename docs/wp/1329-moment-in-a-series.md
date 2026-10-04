# WP-1329 — the moment in a series: the onset, the hold, the trajectory

Milestone: magnetic · Status: 🔄 2026-10-01 — tasks 1–4 and both review follow-ups landed (PRs #522, #589); task 5, a real ramp longer than the Cr₂WO₆ pair, remains
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
- [ ] A real ramp, if one is public: search the corpus, then ask.

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
