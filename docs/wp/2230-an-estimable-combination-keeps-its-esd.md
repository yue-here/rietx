# WP-2230 — An estimable combination keeps its esd

Milestone: unscheduled · Status: 🔄 2026-11-21 — PR #1736 in review; every task done, the 535 found an artefact of the probe
Track: What fires, and what stays silent
Depends on: 2219 (the no-esd rule this refines, PR #1718); 2062 soft (cross-phase overlap groups)
Priority: P3 2026-11-21 — unblocked, WP-2219 merged (PR #1718); an esd the data do determine is withheld, and nothing wrong is printed; quoting the source parameters' combination by hand is the workaround

## Goal

A derived row whose value the data determine keeps its esd, even when the free columns it is
built from sit on a direction the covariance discards. A tie such as `zero_shift = za + zb + zc`
and the moment-pair quadrature sum are the two known cases. The 535 Pawley intensities on a
discarded direction outside every overlap group are explained, and fixed if a missed
near-overlap put them there.

## Context

**What WP-2219 did.** Since PR #1718 a free column that `statistics.discarded_directions`
names as touched gets esd `inf` in `least_squares._guarded_covariance`. Every consumer that
marks gradient-free columns then marks it too. `ParameterTable.unmeasured_rows`
(`params/vector.py`) marks a tied row when it draws on any such column, and
`model/geometry.py` marks a geometry row only if its partials touch one. A tie therefore
inherits its sources' blindness whole.

**Why that is too coarse.** A linear function c·θ of non-estimable parameters can itself be
estimable. It is estimable exactly when c lies in the row space of J, which means c is
orthogonal to every discarded direction (Searle 1971, *Linear Models*, p. 169, the same page
WP-2219 rests on). Its variance is then c·(JᵀJ)⁺·cᵀ for any generalized inverse, and the
pseudo-inverse already gives the right number. WP-2219's handover names two cases that lose
an esd the data determine:

- A tie `zero_shift = za + zb + zc` over three free columns on one discarded direction. The
  sum may be measured while each term is not.
- The moment-pair quadrature sum √(m_a² + m_b²), built in
  `report/magnetic._pair_degenerate_moments` from the two moduli's esds. With each modulus now
  `inf`, the pair skips (its `magnitude_esd is None` branch) and the quadrature number has no
  esd. `tests/test_moment_pair_degenerate.py::test_two_starting_splits_report_the_same_quadrature_number`
  is a strict xfail since WP-2219.

**The proposed test.** Per derived row, take its gradient g over the free columns (a row of C
for a tie, the partials for a geometry row, ∂m/∂d for the quadrature sum). The row keeps its
esd when the projection of the equilibrated g onto the discarded eigenvectors is below a
tolerance relative to ‖g‖. `discarded_directions` already forms the discarded subspace, so it
can return the vectors beside the touched set. The tolerance needs measuring: the discarded
eigenvalues sit under `PINV_RCOND`·|λ|max, and a gradient exactly orthogonal in exact
arithmetic is orthogonal to about 1e-12 in fp64.

**The magnetic half is Mike's.** The quadrature sum is on the magnetic path, whose design
decisions Mike rules since #1075 (2026-11-04). Read that issue for "Ruled by Mike" before
changing what the pair reports, and route a question there rather than to the maintainer.

**The 535 Pawley intensities.** WP-2219's probe over the full suite found 357 Pawley solves
that discarded a direction through the intensity block. They touched 6 758 intensity columns:
5 800 in an overlap group, 423 off the data, and 535 in neither. Those 535 carry no esd and no
report names them. That is settled: no new message (DESIGN Rule 4; `None` already says it; the
maintainer's 2026-11-03 reversal of warnings that restate what the reader sees). What is open
is why they sit in no overlap group. A pair closer than `PAWLEY_OVERLAP_FWHM_FRAC` of a FWHM
that the grouping missed would be a grouping defect. WP-2062 already owns one candidate cause:
overlap groups are built per phase (`model/forward.py`), so coincident reflections of two
phases are neither restrained nor flagged. If the 535 are cross-phase, the fix folds into
WP-2062's task and this WP records the count.

**Tier.** The estimability test is physics (linear-models theory, Searle 1971). It replaces no
threshold that is a judgement, though its tolerance is a numerical one and needs its window
measured into the docstring.

### Inherited

(none yet)

## Non-goals

- Changing `PINV_RCOND`, the equilibration, or which free columns get no esd (WP-2219's rule
  stands for a column).
- A message naming the 535 intensities (settled 2026-11-20, above).
- Cross-phase overlap grouping itself (WP-2062 owns it).

## Tasks

- [x] `discarded_directions` (and `blocked.discarded_directions` for the joint layout) returns
      the discarded eigenvectors in equilibrated coordinates beside the touched set.
- [x] A per-row estimability test in `ParameterTable.unmeasured_rows`; a tied row whose C row
      is orthogonal to the discarded subspace keeps its propagated esd. Test on a synthetic
      `zero_shift = za + zb + zc` tie.
- [x] The same test in `model/geometry.py` for a geometry row.
- [x] The quadrature sum (magnetic path, Mike's to rule): the pair's esd from gᵀ·Cov·g when g is
      orthogonal to the discarded subspace; the strict xfail becomes a pass.
- [x] Probe: list the 535 intensities by reflection and phase over the slow selection, and say
      whether each is a cross-phase coincidence, a missed near-overlap or neither.
- [x] Tests, and the reader-output diff (`python -m tests.reader_output`) for the maintainer.
- [x] Skill: the `COVARIANCE_DIRECTION_DISCARDED` reference row says which derived numbers keep
      their esd, or "none" and why.

## Acceptance

A synthetic three-term tie and the degenerate moment pair each report a finite esd on the
estimable combination, within 10 % of the esd a fit on the combination alone gives, while each
source column still reports none. The 535 are accounted for by cause.

```sh
.venv/bin/python -m pytest tests/test_discarded_direction.py tests/test_moment_pair_degenerate.py
.venv/bin/python -m ruff check src tests examples
```

## References

- Searle, S. R. (1971). *Linear Models*. Wiley, p. 169 (estimable functions).
- WP-2219 and PR #1718 (the rule this refines, and the probe counts).
- WP-2062 (overlap groups built per phase).

## Handover log

- **2026-11-21** — A number the data determine now keeps its esd when the parameters it is
  built from have none. A zero shift tied to the sum of three variables, a cell volume or bond
  on a cell tied that way, a distortion block's total amplitude and a degenerate moment pair's
  quadrature sum each report the esd that a fit of the combination alone gives, to 0.02 %.
  Each source parameter still reports none, as WP-2219 rules for a column. The test that
  decides is WP-2219's own touched test asked of the number's gradient, so no new tolerance
  entered. The 535 Pawley intensities were an artefact of WP-2219's probe arithmetic: every
  touched intensity sits in an overlap group, so WP-2062 gains no work. PR #1736.

  *Done.*
  - `statistics.discarded_directions(basis=True)`, and its blocked twin, returns the discarded
    subspace in the matrix's columns over √cut. `_guarded_covariance` scales it to the
    reported covariance's units. It returns it with the pseudo-inverse's own esds as a
    `DiscardedSubspace`, carried on `LSQOutcome.discarded_subspace`. A chart's ±1 signs its
    rows; a chart matrix drops it, so those numbers stay absent.
  - `statistics.estimable(grad, cov, lost)` says c is not estimable when ‖lostᵀc‖² ≥ cᵀ·Cov·c.
    For c = eᵢ that is the column test. `ParameterTable.unmeasured_functions` applies it to a
    gradient over entries. `stderr_physical`, `unmeasured_rows` and `physical_covariance` take
    `discarded=`. A function that moves one column alone stays unmeasured.
  - Consumers: `refine._build_result` (ties, geometry, volumes, distortion totals), the
    tied-bound guard, the history node's esds, the joint fit's per-histogram esds,
    `Refinement.geometry()`, and the magnetic pair fold through `analyse_moments(covariance=)`
    and `build_report(covariance=)`. `report()`, a stage report, the magnetic solve's rows and
    a series' moment arm pass it. `Refinement._answer_covariance` is a 6-tuple, the subspace
    last.
  - A geometry row or volume kept this way has `stderr_diagonal = None`, because the sources'
    own variances are not measured.
  - Help entry, skill row, theory paragraph, release notes. The wp2219 fragment is corrected.
  - Review (`/code-review high --fix`, d5c0ea871): the guard, the history node and the stage
    report now read the same esds as the result. Geometry keeps `cov_full` bit for bit and
    reads the pseudo-inverse covariance for kept rows only. Three performance fixes, and the
    `Capture` fake in `test_distortion_totals.py`, which was red on the branch.
    Declined: (1) a gradient mixing a touched column with a loosely determined free one could
    pass the test. That is the column test's tolerance, by design, and a real case needs the
    free column's variance about 1e14 times the touched one's (the measured lost/kept ratio of
    a touched column is 2.3e14). (2) A NamedTuple for `_answer_covariance`. A test fake builds
    a 5-tuple, and the change is wider than this WP. (3) A joint fit's `report()` passes no
    covariance, since a joint fit has no `_answer_covariance`.

  *Measured* (macOS arm64, `[dev]`, tree merged with origin/main at 63fbb8d65, no other suite
  running, through ghostshift's serial lock):
  - Tie esd: 1.0002× the esd of the combination fitted alone, in Rietveld and Pawley mode.
    Lost/kept variance for the sum: 5e-19 to 1.5e-18. For each source: 2.3e14.
  - Moment pair: quadrature esd 1.0002× the esd of one site carrying the quadrature modulus.
  - Fast selection: 15029 passed, 442 skipped, 32 xfailed. Five tests added, all fast,
    1.32 s together (`tests.added_test_times`).
  - Full suite: 15986 passed, 453 skipped, 52 xfailed. The strict xfail on the moment
    pair now passes.
  - `python -m tests.reader_output`: exit 0, unchanged on the standard fit.
  - Probe over the full suite: 312 Pawley solves touched 5804 intensities, all in overlap
    groups, 427 of them also centred off the data. 48 joint solves of
    `test_a_pawley_joint_ramp_recovers_its_line_without_bias` touched 958, every one the cubic
    (330)/(411) coincidence, grouped and centred 0.3-0.4° past the data's end (23.99°). None is
    cross-phase and no same-phase pair closer than the grouping threshold was missed.
    WP-2219's "535 in neither" was 6758 − 5800 − 423. Its 423 off-data intensities were all
    inside the 5800, and its probe could not see the joint fit's block, so it counted that
    fit's 958 as neither. 958 − 423 = 535.

  *Settled by Claude.*
  1. The estimability tolerance is WP-2219's touched test asked of the gradient, under
     Searle 1971 p.169 and the measured ratios above. The alternative was a new tolerance on
     ‖Pg‖/‖g‖, which the WP proposed measuring. It would add a second threshold for one
     question.
  2. A kept geometry row or volume reports no diagonal-only esd, under WP-1072's rule that a
     number not measured is absent. The alternative was a diagonal sum that quotes the
     unmeasured source variances.
  3. The moment pair folds through the fit's live covariance (magnetic path, Mike's since
     #1075). The grounds are Q5's existing contract and the strict xfail WP-2219 wrote. The
     alternative was to leave the xfail for Mike.
  4. The review's widening to the guard, history node and stage report, under the rule that
     a projection matches its authority. The alternative was leaving them on the column rule.

  *Not generalised.* QPA weight fractions still mark the whole block when any scale is
  touched. W normalises by a sum, so a fraction is estimable only if the whole block is, and
  that needs its own test.

  Next: maintainer review. Returned esds change on fits with a discarded direction: ties,
  geometry, volumes, A_τ and the moment-pair fold regain an esd, and `stderr_diagonal` is
  None for kept rows. The standard fit's reader output does not move. Mike may want to look at
  the magnetic fold.

- **2026-11-20** — created from WP-2219's two open calls, after the maintainer ruled that PR
  #1718 merges as it stands and the calls go to a follow-up. No open WP owns either: WP-1535 is
  closed, WP-1915 covers indexing's covariance only, and WP-2062 owns the cross-phase half of
  the Pawley question, cited above. Next: the eigenvectors out of `discarded_directions`, then
  the tie test.
