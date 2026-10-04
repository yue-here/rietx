# WP-1534 — a scale and a B the fitted range cannot separate

Milestone: unscheduled · Status: 🔄 2026-10-02 — the hold and `SCALE_B_INSEPARABLE` landed (PR #673); task 2's guideline reading is owed, and the default-bounds decision is the maintainer's
Track: What fires, and what stays silent
Depends on: —
Priority: P3 2026-10-02 — was P1: the hold that stops the silent 0.000 ± 0.000 wt% landed in PR #673; what remains is task 2's reading (needs the paper corpus) and the maintainer's call on the default bounds

## Goal

A fit whose angular range cannot separate a phase's scale from its
displacement parameters says so, and does not return a confident phase
fraction from one arbitrary point on that ridge. It does this whatever the
bounds on B are. If that holds, the 0–25 Å² default on `Atom.biso` stops being
load-bearing, and whether to keep it becomes a choice rather than a defence.

## Context

**The defect (issue #204, recorded in WP-1321).** On a narrow 25–50° lab
Cu Kα scan of a four-phase mixture, Fe's Biso ran to −165 Å² with its scale at
4.66e-12. Two staging orders returned Fe at 0.0 wt% and 80.9 wt% (TOPAS:
27.1) at an Rwp agreeing to 11 significant figures. Both were the same
solution. A phase's intensity is `scale · exp(−2B·s²)` times terms neither
parameter touches, with s = sinθ/λ. Where s² barely varies across the phase's
reflections, ln(scale) and B move together along one flat ridge. The record
measured `ln(scale ratio)/(ΔB·s²) = 1.98 ≈ 2`, which is that relation. The
caller's `Parameter` had dropped the declared bounds. PR #206 restored them,
and that is all that stops the walk today.

**Why the bounds are only a backstop.** The 0 Å² floor stops a negative walk.
The 25 Å² ceiling does not protect the fraction. Over 25–50° Cu Kα, mean s² is
0.047 Å⁻². So a walk from B = 0.5 to 25 Å² moves the scale by
exp(2 × 24.5 × 0.047) ≈ 10×. That figure is arithmetic on the record's
relation, not a run. `BISO_UNUSUALLY_LARGE` would fire well before 25 Å², so
that walk is flagged but not prevented. The record's own fix measurement used
bounds of 0.5–4.0 Å², not the default.

**Why this WP exists (PR #663, 2026-10-02).** The maintainer asked to accept
every Biso value and warn where needed, as TOPAS, FullProf, GSAS and GSAS-II
do. Fully unbounding `Atom.biso` was tried and rejected, because it brings
#204 back. #663 instead keeps the default bounds and has readers widen them to
hold a file's value (`schemas.structure.biso_bounds`, `BISO_BOUND_WIDENED`).
It also adds `BISO_NEGATIVE` beside `BISO_UNUSUALLY_LARGE`. The ridge itself
is untouched. This WP is that fix.

**Machinery to reuse, not rebuild.**

- **The flat-direction hold** (WP-1301, root CLAUDE.md § Invariants). A phase
  the data cannot see is held for the stage, recorded in `StageResult.held`
  and reported by `PHASE_UNCONSTRAINED`. Support is re-measured at the
  answer. The scale–B ridge is the same shape: a direction the data does not
  constrain, held rather than bounded. Read `_run_stage`'s hold before
  designing a second one.
- **The covariance already propagates to the fraction.** `qpa.weight_fractions`
  carries an esd through the whole covariance, and root CLAUDE.md says a
  direction the data does not move has no esd rather than a small one. On a
  true ridge, the fraction's esd may already say "unmeasured". Nobody has
  checked on this case. That is task 1.
- **The pair guards.** `HIGH_CORRELATION` and `FLAT_DIRECTION` fire on the
  scale–B pair if the ridge is sharp enough. WP-1460 owns how those rows are
  reported. This WP owns acting on the ridge.
- **Where the hold is declared.** A hold lives in the table
  (`ParameterTable.set_vary`, `Entry.held`), never at call sites (WP-1435).

**Task 1, measured (2026-10-02).** The fixture: corundum, zincite, fluorite
and bcc Fe at equal scales (2e-4; true 71.778 / 3.569 / 23.443 / 1.211 wt%),
25–50° in 0.01° steps (2500 points), `Instrument.bragg_brentano("CuKa")`,
Poisson noise at seed 3. Fe has exactly one reflection there, (110) at 44.67°,
which is #204's shape: #204's walking phase was Fe on 25–50° too. The fit starts
from scales of 1e-4 and B at the truth. Two staging orders were run, cell before
B and B before cell, each with `biso` unbounded and with the default 0–25 Å².

- **Unbounded, both orders walk.** Fe reaches B = −150.0 and −150.9 Å² with its
  scale at 2.4e-12 and 2.2e-12. Its fraction is **0.000 ± 0.000 wt%** in both
  orders, at an Rwp of 0.0763697470 in both. `ln(scale ratio)/(ΔB·s²)` is
  ≈ 2.0, #204's relation again. Fe's B esd is 0.22 Å² at −150 Å².
- **Bounded, the two orders differ.** Fe comes back at 1.283 and 1.236 wt%,
  at an Rwp of 0.0763722 in both. Zincite O sits at the 0 floor (`BOUND_HIT`).
- **The esd does not say it, and the reason is the covariance's cut.** Fe's
  scale and B Jacobian columns are collinear to rounding:
  1 − |cos| = 2.2e-16 at the answer, against 9.6e-3 for fluorite, 3.5e-2 for
  zincite and 0.28 for corundum. In the equilibrated normal matrix, their
  combined direction has eigenvalue −3.8e-18 unbounded and 6.3e-16 bounded.
  Both are below `pinv`'s cut of 1e-15 × λmax = 2.9e-15, so the direction is
  *discarded* and gets zero variance. Fe's scale comes back "measured" to 2.7 %,
  bounded and unbounded alike, which is conditional on a B the data never saw.
  This is WP-1110 item 14's confident wrong esd, here for a *combination* of
  two live columns rather than for one column. Fluorite's near-ridge eigenvalue
  (7.3e-11 and 9.9e-10) survives the cut. Its esds are therefore honest and
  huge: Ca B ± 2 070–15 150 Å², W ± 2 000–14 650 wt%. Through the sum in the
  normalisation, those esds reach every fraction (corundum ± 1 900–14 000 wt%).
- **Which guards fire.** `HIGH_CORRELATION` and `FLAT_DIRECTION` fire on
  `phases.3.scale ~ phases.3.atoms.0.biso`, and on fluorite's pairs, in all four
  runs. `BISO_NEGATIVE` fires on Fe when unbounded. Nothing names a fraction.

So the fix is an **action**, and the test needs no tuned number. A phase whose
reflections in the fitted range sit at **one d-spacing** gives the data one
intensity for it. On that range `ln S − 2B·s²` is one coordinate, by the
algebra of the structure factor rather than by any threshold. A phase with two
or more distinct d-spacings is separable in principle, and there the
covariance's esd is honest. Fluorite above is that case.

**The test (task 3, 2026-10-02): the separation of two columns, against
the covariance's own cut.** At stage start, for each phase with a free
displacement column, take its weighted phase component `a = y_p/σ` (the
scale's column, up to a factor) and `b`, the change in `y_p/σ` when every
isotropic B of the phase moves together by a small step. The separation is
`r = |b − (a·b/a·a)·a| / |b|`, the sine of the angle between the two columns.
On the fixture it is 2.2e-16 for Fe (rounding), and 0.138 for fluorite (from
cos = 0.99042), the nearest phase that *is* separable. The threshold is the
covariance's own cut, not a tuned number. `normal_factors` hands the
equilibrated normal matrix to `pinv`, whose `rcond` is numpy's 1e-15. The
pair's 2×2 block `[[1, c], [c, 1]]` has eigenvalues `1 ± |c|`, with
`1 − |c| = r²/(1 + |c|) ≈ r²/2`. So the pair, taken alone, is discarded when
`r²/2 < rcond · 2`, that is when `r < 2√rcond ≈ 6.3e-8`. In the full matrix,
λmax can be up to P rather than 2, which moves the real cut up by as much as
√(P/2). Measured cases sit eleven decades either side of the threshold, so
that factor does not decide them. The hold therefore fires where the esd
would otherwise lie, and nowhere else. A near-ridge like fluorite keeps its
honest, huge esd, and `HIGH_CORRELATION` already names it. This test is
preferred over counting distinct d-spacings because a count needs an equality
tolerance and is fooled by a reflection whose |F|² is zero by site symmetry.
The separation reads the intensity the phase actually puts in the data.
Task 2's guideline reading is still owed. It can add a *near*-ridge statement,
but this test does not wait on it.

**Task 5, re-measured with the hold (2026-10-02): the decision PR #663
deferred.** Same fixture, same four runs (bounded and unbounded, both
staging orders):

| run | Fe wt% (true 1.211) | zincite | fluorite | corundum | Rwp |
|---|---|---|---|---|---|
| unbounded, either order | 1.284 | 3.492 | 25.67 | 69.55 | 0.0763697470 |
| bounded, either order | 1.283 | 3.585 | 25.65 | 69.48 | 0.0763722 |

Before the hold, the unbounded runs gave Fe 0.000 wt% and the bounded runs
1.283 and 1.236. Now every run gives `SCALE_B_INSEPARABLE` on
`phases.3.atoms.0.biso` and nothing else of the kind. **On #204's shape, the
0–25 Å² default is no longer load-bearing.** Bounded and unbounded agree on
every fraction to 0.1 wt%. Where they differ, the cause is zincite's O, at
B = −0.88 ± 3.3 Å² unbounded (`BISO_NEGATIVE`) against the 0 floor bounded
(`BOUND_HIT`). That is a zero within one esd either way. Two things the bounds
still do, which the maintainer weighs:

- **The near ridge is not held, and the bounds do not bind it either.**
  Fluorite's Ca B lands at 2.44 Å² (true 0.55) in all four runs, with an esd
  of ± 3 700–7 700 Å². That esd is honest, and it is why every fraction's QPA
  esd reads in thousands of wt%. The hold covers the *exact* ridge only, by
  design: above the cut, the covariance already tells the truth.
- **A mildly negative B reads as `BISO_NEGATIVE` instead of `BOUND_HIT`.**

One fixture and one shape, so this is evidence for the decision rather than
the decision itself.

**Not this WP, filed as
[WP-1535](1535-a-discarded-direction-reads-as-measured.md).** The
covariance's cut zeroes the variance of *any* exactly degenerate combination
of live columns. One hypothesised example is a one-site phase's occupancy
against its scale, on any range. `_cov_free` catches only a column with no
gradient.

**What a fix may not do.** A threshold is quoted from a source or measured
here, never set by eye (root CLAUDE.md, WP-1448). An Rwp comparison is not
evidence for a correction. A fix ships with a record field or diagnostic
stating what it changed.

### Inherited

- **2026-10-04, from WP-1523: the support test leaves displacements out
  because of this ridge.** A phase is now seen when its scale is 3σ from zero
  by a marginal esd (`refine._answer_significance`), and that marginal skips
  every column that moves only displacements or occupancies. With them in it,
  `tests/test_scale_b_ridge.py`'s fluorite read 153.7σ on the screen and
  0.02σ marginal, and was held as absent. Any change to what the scale-B hold
  frees should re-run that file and `tests/test_phase_significance.py`.

## Non-goals

- Reporting each correlated pair once. That is WP-1460.
- Changing `Atom.biso`'s default bounds. Task 5 measures whether they are
  still needed, and the decision goes to the maintainer.
- Per-atom B instability on light atoms. That is the same ridge one level
  down (an atom's B against its occupancy). Note it if seen, but do not fold
  it in.

## Tasks

- [x] **Measure first.** Build a synthetic narrow-range mixture: two or more
      phases, 25–50° Cu Kα, known fractions, `biso` freed with
      `min=-inf, max=inf`. Reproduce the walk. Record whether the fraction's
      esd already marks it unmeasured, and which existing guards fire. This
      decides whether the fix is a report or an action. Re-rate the Priority
      line from it.
- [ ] **Read what the guidelines prescribe for a short range.** McCusker et
      al. (1999) and the IUCr QPA round robin (Madsen et al., 2001) first.
      Search the local corpus before asking for either. Write what they say,
      with page, into Context.
- [x] **Name the test.** The separability of a phase's scale and B on the
      fitted range is a property of the data and the reflection list. It is
      computable before a stage frees B: for example, the intensity-weighted
      spread of s² over that phase's reflections, or the measured angle
      between the two Jacobian columns. Pick one from task 1's numbers and
      task 2's guidance. Write where its threshold comes from.
- [x] **Act on it** the way WP-1301 does: hold B for the stage where the test
      fails, record it in `StageResult.held`, and report a finding that names
      the phase and the fraction's consequence. Or, if task 1 shows the esd
      already says it, add only the finding. Either way, a diagnostic states
      what was done.
- [x] **Re-measure #204's shape unbounded.** With the fix in place, run task
      1's fixture with `Atom.biso` unbounded. If the fraction lands within the
      fixture's tolerance, or is marked unmeasured, the default bounds are no
      longer load-bearing. Put that result to the maintainer as the decision
      PR #663 deferred.
- [x] Tests (unit + the synthetic fixture) + obs/calc/diff PNGs to
      `tests/output/`.
- [x] Manual Part 2: the ridge relation as a displayed equation with its
      `*Source:*` line, if the fix adds physics.
- [x] Skill: a row for the new finding, and a line in the QPA reference on
      short ranges.

## Acceptance

On the synthetic fixture with B unbounded, the fit either returns the
fractions within a tolerance taken from task 1's measured spread, or reports
the affected fractions as unmeasured with a finding naming the phase. It never
returns two different confident fractions at one Rwp, as #204 did.

```sh
.venv/bin/python -m pytest tests/test_scale_b_ridge.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- Issue #204, and WP-1321's record of it.
- PR #206 (the bound inheritance), PR #663 (widening at read, `BISO_NEGATIVE`).
- WP-1301 (the flat-direction hold), WP-1435 (a hold in the table),
  WP-1460 (reporting a degeneracy once).
- McCusker, L. B., Von Dreele, R. B., Cox, D. E., Louër, D. & Scardi, P.
  (1999). J. Appl. Cryst. 32, 36–50.
- Madsen, I. C., Scarlett, N. V. Y., Cranswick, L. M. D. & Lwin, T. (2001).
  J. Appl. Cryst. 34, 409–426.

## Handover log

### 2026-10-02 (2nd session) — the hold landed; the guideline reading is owed

A phase with only one reflection in the fitted range can no longer return a
confident weight fraction from an arbitrary point on the scale–B ridge. The
shape of issue #204 is now a synthetic test: four phases on 25–50° Cu Kα, with bcc Fe
having one reflection. It showed the covariance was not saying "unmeasured".
It said 0.000 ± 0.000 wt%, because the covariance's pseudo-inverse discards
exactly that direction and reports it at zero variance. Each stage now
detects the case before solving, by the same cut the covariance uses. It
holds the phase's B at the value supplied and reports `SCALE_B_INSEPARABLE`,
which names the phase and says how far the fraction moves per Å² of error in
B. Fe now comes back at 1.284 wt% (truth 1.211) whether B is bounded or not,
so on this shape the 0–25 Å² default is no longer what protects the answer.
Whether to keep it is now a choice for the maintainer.

*Done*, in order:

- Task 1 measured (`ff362fb`), and task 3 named the test (`bae258c`).
- The hold, `StageResult.scale_b_held` (schema 0.40), the finding, its
  skill row and the manual Part 1 row (`146916c`). This was laned; see
  *Measured*.
- Task 5's re-measure (`546cc01`).
- Manual Part 2's ridge section with two equations and live substitutions
  (`2b27daa`).
- The QPA short-range section in the skill (`38d7652`).
- The review fix (`a4a7126`): a phase that the support hold took at stage
  start and released mid-stage now gets the probe before its second solve.
  The new test `test_a_phase_released_inside_the_stage_is_asked_before_its_second_solve`
  covers it.
- `session_usage.py` (`f3d7199`): it finds a lane filed under the worktree's
  project directory, and `baseline` survives an empty band.

**Task 2 is not done.** The paper corpus is maintainer-local and was not in
this cloud container. The test needs no threshold from the papers, so
nothing waited on it.

*Measured* (`[dev]`, Linux x86-64, 4 cores; `main` had not moved, so the
branch tree is the merged tree):

- The probe at stage start reads Fe at 1.0e-12, its rounding floor. The other
  three phases read 0.19–0.40. The floor is 6.3e-8.
- The fast selection: 7854 passed, 172 skipped, 1 failed, in 20:13 with nothing
  else running. `tests/test_scale_b_ridge.py` adds 18 cases, all passing, and
  no new skip. The one failure is environmental:
  `test_merge_replay.py::test_a_conflict_the_driver_resolves_counts_only_as_text`
  fails alone in 0.36 s because this container's git 2.43 has no `merge-tree`
  `diff-algorithm` option, and nothing this branch touched is involved.
- The added tests' cost (`tests.added_test_times`, one run on this machine):
  22.2 s over 13 tests. The largest is
  `test_fe_b_is_held_in_every_stage_that_frees_it` at 7.37 s for two cases,
  which share the module fixture's two fits. None of them joins the slow
  tail.
- **The full suite did not complete.** It was launched once, alone, on the
  final tree. The 4-core container stopped it at its 2-hour background limit
  before any summary printed, so no full count is quoted. The slow
  acceptance suites on this change are left to CI's nightly `full` job.
- The lane trial (`session_usage.py lanes c77ba4ec`):

  | lane | est | requests | main at dispatch | lane base | re-read | main requests | left in main | main edits after | redo | lane $ | main $ | in-session $ | saved $ |
  |---|---|---|---|---|---|---|---|---|---|---|---|---|---|
  | act-on-it | 45 | 143 | 242K | 79K | 0K of 174K | 11 | 39K | 0 | 0 | 7.78 | 0.99 | 14.16 | +5.17 |

  Kept items: name-the-test (est 4, 3 requests), re-measure-unbounded (4, 2),
  tests (1, 0), manual-equation (12, 6), skill (6, 7). The row went into
  `process.md`. A re-run at the end of the handover, on `main`'s
  `subagent_dirs`, read saved +7.43 (+23%): the in-session model moves as the
  session grows, so the row keeps the step-3b figure.
- The `baseline` replay in this container covers **one** session, this one,
  not the record's 174. Its selective row reads "0 items laned, +0%", which
  is not comparable to the record, so WP-1903 has to re-run it on the
  maintainer's machine. The crossover at this session's context was 40
  requests at 250K for an 80K lane base. The 143-request lane cleared it, but
  my estimate of 45 was a third of the actual.
- **Lane quality:** the review raised one correctness finding on lane-written
  code, the released-phase gap. The lane prompt had pointed at `phase_held`
  but did not name the release path as a second entry. The lane deviated
  three times, and all three were sound, reported calls: a `None` default for
  "never looked", a probe only where the phase's own scale is free, and U^ij
  names in the displacement match.

*Declined review findings*, one line each:

- An all-anisotropic phase is never probed. Fixing it needs a uniform-U step
  in each site's ADP basis, which is new physics. It is noted in WP-1535 as a
  candidate shape.
- The joint runner has no probe. That goes to WP-1341's Inherited, and
  `multi.DIAGNOSTIC_SCOPES` declares it ABSENT.
- The summary still labels moment holds "phase-unsupported". That predates
  this branch, and the comment now says so.
- `_intensity_weighted_s2` weights the nuclear component only. That affects
  only the message on a split magnetic phase.

*Gotchas*:

- `test_the_ramp_reproduction_no_longer_runs_away` fails its 60 s guard under
  a loaded `-n auto` on 4 cores: 81.6 s on this branch, 81.9 s on the base. It
  passes alone in 17 s. This is its fifth recorded trip, now in WP-1420's
  Inherited.
- The repo's worktree hook blocks edits in a cloud session's main checkout.
  This session worked in `.claude/worktrees/wp1534-scale-b-ridge` on local
  branch `wp1534-scale-b-ridge`, and pushed to the designated remote branch
  `claude/quirky-noether-39b0el`.

*Forward references*: WP-1535 is filed, for the covariance's zero-variance
direction on any exactly degenerate combination. Inherited entries went to
1341 (the joint probe), 1420 (the ramp guard) and 1903 (the lane row and the
two script defects).

*Next*:

1. The maintainer decides PR #663's deferred question from task 5's table:
   keep the 0–25 Å² default as a choice, or drop it. The hold now carries
   #204's shape either way.
2. Task 2 in a session that has the paper corpus. It can add a *near*-ridge
   statement for the case fluorite shows: B 2.44 Å² against 0.55, with an
   honest esd of thousands. If the papers prescribe action there, that
   becomes a task here.
3. Close this WP after (2).

### 2026-10-02 (1st session) — created from PR #663's review

No open WP owns acting on a scale–B ridge: WP-1460 reports correlated pairs
and WP-1420 re-enters a held phase. Fully unbounding `Atom.biso` was rejected
because #204 measured this ridge walking to −165 Å². This WP removes the
reason the bounds are needed. Next: task 1, because it decides whether the fix
is a report or an action.
