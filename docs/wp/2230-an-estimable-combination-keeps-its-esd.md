# WP-2230 — An estimable combination keeps its esd

Milestone: unscheduled · Status: ⬜
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

- [ ] `discarded_directions` (and `blocked.discarded_directions` for the joint layout) returns
      the discarded eigenvectors in equilibrated coordinates beside the touched set.
- [ ] A per-row estimability test in `ParameterTable.unmeasured_rows`; a tied row whose C row
      is orthogonal to the discarded subspace keeps its propagated esd. Test on a synthetic
      `zero_shift = za + zb + zc` tie.
- [ ] The same test in `model/geometry.py` for a geometry row.
- [ ] The quadrature sum (magnetic path, Mike's to rule): the pair's esd from gᵀ·Cov·g when g is
      orthogonal to the discarded subspace; the strict xfail becomes a pass.
- [ ] Probe: list the 535 intensities by reflection and phase over the slow selection, and say
      whether each is a cross-phase coincidence, a missed near-overlap or neither.
- [ ] Tests, and the reader-output diff (`python -m tests.reader_output`) for the maintainer.
- [ ] Skill: the `COVARIANCE_DIRECTION_DISCARDED` reference row says which derived numbers keep
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

- **2026-11-20** — created from WP-2219's two open calls, after the maintainer ruled that PR
  #1718 merges as it stands and the calls go to a follow-up. No open WP owns either: WP-1535 is
  closed, WP-1915 covers indexing's covariance only, and WP-2062 owns the cross-phase half of
  the Pawley question, cited above. Next: the eigenvectors out of `discarded_directions`, then
  the tie test.
