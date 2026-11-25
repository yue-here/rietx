# WP-2230 — An estimable combination keeps its esd

Milestone: unscheduled · Status: 🔄 2026-11-23 — PR #1736 merged on 2026-11-21 and every task done; waits on Mike's ruling on the moment-pair fold, the one call on his path that Claude settled
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

- **2026-11-23** — a close attempt by a ghostshift runner (batch close-2026-11-23, PR #1815),
  which left the WP open.

  The work is on `main` and every task is ticked, but one call in it belongs to Mike and he
  has not ruled on it. Since PR #1736, a degenerate moment pair reports an esd on its
  quadrature sum √(m_a² + m_b²) when the data determine that sum. That is what a magnetic fit
  prints, and Mike rules the magnetic path's reader output (#1075, 2026-11-04). The
  2026-11-21 entry settled it by Claude (*Settled by Claude* 3), and the generality judge
  wrote that the ruling stays open for him. The WP closes once he rules, or once Yue says the
  merge settles it.

  - *Checked*: all seven tasks ticked. `gh pr view 1736` shows it merged on 2026-11-21 at
    10:39 UTC by yue-here (merge commit 02d105ba1), with no comments or reviews. #1075 holds
    no ruling of Mike's on the fold, and neither do `docs/milestones/magnetic.md` and
    WP-2219.
  - *Also on his side since*: Mike took the distortion-mode work on #1075 on 2026-11-22, after
    the merge. A distortion block's total amplitude (`RefinementResult.distortion_totals`)
    regained its esd in the same PR, so the question can name it too.
  - *Changed*: the Status line only.
  - *Question for Mike, drafted for Yue to post on #1075* (a public act, so the runner did not
    post it): "@mustachefeeling, since PR #1736 a number the data determine keeps its esd even
    when the parameters it is built from have none (Searle 1971, p. 169). Two of them are on
    your side. A degenerate moment pair's quadrature sum √(m_a² + m_b²) now reports an esd,
    and so does a distortion block's total amplitude. Each matches, to 0.02 %, the esd of a fit
    of that number alone, and each source modulus or amplitude still reports none. Do you
    accept both as they merged? _Written by Claude._"

  Next: Yue posts the question, or rules that the merge settles it. On a yes the WP closes:
  delete `Priority:`, move the 2026-11-21 entry's narrative to the v1.13 record, mark ✅. On a
  no, a follow-up reverts the fold on `main`, and the strict xfail returns.

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

  *Generality* (the `generality-review` judge, pasted unedited; `_audit.py` untouched, second
  trigger). The judge's one doc gap, the `stderr_diagonal` docstring, is fixed in
  `schemas/results.py`. The moment-pair ruling stays open for Mike, as *Settled by Claude* 3
  says.

  ## `statistics.estimable` (the esd test for a combination)

  **holds**: the case for is stronger. A linear combination whose gradient is orthogonal to every discarded direction is estimable (Searle 1971 p. 169), and no program withholds the esd of such a combination.

  | Q | Author (where) | Found | Verdict |
  |---|---|---|---|
  | 1 | Keeps an esd on a tie or derived number built on touched columns (docstring) | Agreed. "Touched" means a column that a discarded direction loads on. | ok |
  | 2 | none given (no row) | Kind 1, arithmetic | — |
  | 3 Against | — | none found. GSAS-II and TOPAS quote a truncated-SVD esd for every parameter (docs/practice.md § esds). They dissent only toward quoting more. | — |
  | 4 For | "1.0002× the esd of the combination fitted alone" (handover) | Measured in both Rietveld and Pawley mode. Without the test the zero shift had no esd although the data determine it. | strong |
  | 5 | "no tolerance is new" (docstring) | Tier 1. The factor-1 cut (lost ≥ kept, about √2 short) is WP-2219's inline touched test. Neither has an audit row. | weak point |
  | 6 | lost/kept 5e-19 to 1.5e-18 for the sum, 2.3e14 for each source | One family: a synthetic three-way zero shift, plus a synthetic LaB6 cell split. The reference is a fit of the combination alone, which verifies only. The 32-decade gap makes the cut's exact position immaterial on this case. | narrow |
  | 7 | none given | No field says the esd was kept. Only the source rows' absent esds show it. | gap |

  Would change: a real fit whose lost/kept ratio falls between 1e-6 and 1e6.

  ## `ParameterTable.unmeasured_functions` (one-column rule, dead columns)

  **holds**: the case for is stronger. Both clauses restate rules already in force.

  | Q | Author | Found | Verdict |
  |---|---|---|---|
  | 1 | "A function that moves one column alone is that column" (docstring) | Agreed. | ok |
  | 2 | — | Kind 1 | — |
  | 3 | — | none found | — |
  | 4 | WP-2219's column rule; WP-1110's dead-column rule | The test is scale-invariant, so for k·eᵢ the clause is redundant with it. It only guards against rounding. The dead-column clause is the existing rule that consumers mark rather than clamp. | ok |
  | 5 | — | Tier 1. No test isolates the `> 1` clause. | minor |
  | 6 | — | not applicable | — |
  | 7 | — | The absent esd | ok |

  Would change: a case where `c != 0` counts a rounding-level entry as a second column.

  ## Kept row: `stderr_diagonal = None`

  **holds**: the case for is stronger. A diagonal sum over sources that are not estimable depends on which inverse was taken (docs/practice.md, Searle row).

  | Q | Author | Found | Verdict |
  |---|---|---|---|
  | 1 | "a sum of diagonal terms would quote" unmeasured variances (geometry `_sigmas` docstring) | Agreed. | ok |
  | 3 Against | — | none found | — |
  | 4 For | WP-1072: an unmeasured number is absent (handover, settled 2) | Agreed. | ok |
  | 5 | — | Tier 1. Pinned by `test_a_cell_tied_to_a_sum_keeps_its_volume_and_bonds`. | ok |
  | 7 | — | `stderr` set while `stderr_diagonal` is None. The schema docstring (`schemas/results.py` ~l.730) still names only two causes of None. | doc gap |

  Would change: none foreseen.

  ## `report/magnetic._estimable_pair_esd` (moment-pair fold)

  **holds** on the arithmetic, which is linearised estimability at the answer. The ruling is open: decisions on the magnetic path are Mike's (#1075, the magnetic-path ruling). The handover settles this one by Claude, citing no ruling of his.

  | Q | Author | Found | Verdict |
  |---|---|---|---|
  | 1 | Fold "only when the sum is estimable" (docstring) | Agreed. A result read back without its fit does not fold. | ok |
  | 3 Against | — | none found | — |
  | 4 For | "1.0002× … one site carrying the quadrature modulus" (handover) | `test_two_starting_splits_report_the_same_quadrature_number` now passes. It was a strict xfail. | strong |
  | 6 | — | One synthetic degenerate pattern. It verifies only. | narrow |
  | 7 | — | The pair's note text | ok |

  Would change: a ruling from Mike.

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
