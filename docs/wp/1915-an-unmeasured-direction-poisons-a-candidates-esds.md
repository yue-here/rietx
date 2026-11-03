# WP-1915 — an unmeasured direction poisons every esd of an indexing candidate

Milestone: unscheduled · Status: 🔄 2026-11-03 — claimed by @mustachefeeling
Track: What fires, and what stays silent
Depends on: —
Priority: P3 2026-10-07 — NaN in every cell esd of a candidate whose lines leave one metric term unconstrained, silent on macOS; it reaches the Bravais screen's tolerance and the χ² dedup

## Goal

A candidate cell whose lines leave some A..F direction unconstrained reports
that direction as unmeasured and every other esd exactly. Today all of them
come back NaN.

**Superseded in part, 2026-11-03.** Since #1232 (`940e8f950`, 2026-10-29)
`refine_candidate` refuses any fit whose free metric variance is not finite, so
no candidate carries NaN esds and the four sites below never see an infinity.
Measured on the triclinic fixture (handover log, 2026-11-03): the lines' Q are
bit-identical along the dead D direction while a, b, c and α all move (b by
2.7 % at D = 0.01), so a, b and c are *not* measured by those lines. Only their
reciprocal counterparts are. The goal's "every other esd exactly" would have been a finite
esd on an unbounded length. The refusal stands, and the work below pins why.

## Context

`indexing/qspace.refine_candidate` gets its covariance from
`optimize.statistics.normal_covariance`, which reports a gradient-free column as
infinite variance. The refinement side never propagates that infinity:
`ParameterTable._cov_free` zeroes it and `unmeasured_rows` marks what used it
(its docstring has the rutile case, six bond esds lost to one profile term).
The indexing side propagates it directly, three times:

- `qspace.py`, `cov_af = basis.T @ cov[:n_free, :n_free] @ basis`;
- `qspace.cell_esds`, `j @ cov_af @ j.T`;
- `reduce.reduced_covariance`, `t @ cov @ t.T`, and `engines.py`'s volume esd,
  `grad @ cov_af @ grad`.

Every product against a zero coefficient is 0·inf, a NaN.

**Measured** (2026-10-07, macOS arm64, `[dev]`): a triclinic fit to eleven
`h0l` and `0k0` lines leaves D and F unconstrained, returns the right cell, and
gives NaN for all six cell esds and all 36 entries of `cov_af`. a, b and c are
measured by those lines. Accelerate raises no floating-point flag for this, so
no warning shows on a Mac. OpenBLAS does raise one, which is how WP-1545 found
the class: notebook 03's search warned on CI's py3.14 Linux job.

WP-1545 removed only the case where the candidate is rejected anyway. When a
direction is dead in an orthorhombic search, its A..F term is zero and
`cell_from_af` refuses the metric. `refine_candidate` now checks the metric
before forming the covariance (15 such fits in notebook 03's search, unit
digests bit-identical on corundum and synthetic monoclinic). A *surviving*
candidate, a lower-symmetry cell with a dead cross term, still gets NaN.
*(Superseded 2026-11-03: since #1232 such a candidate does not survive. The
fixture's fit raises "not a lattice", and "a, b and c are measured" above holds
only to first order at the minimum-norm D = F = 0.)*

**Consumers to read before choosing the marker.** `cell_esd` sets the spglib
`symprec` sweep in `reduce.bravais_screen` through `np.max(...)[:3]`, so one NaN
or inf there changes the Bravais screen. `cov_af` is the χ² dedup's covariance
(`engines._dedup_groups`, through `reduce.reduced_covariance`), so its marker
decides whether two candidates merge. The root rule is "consumers mark, never
clamp" (root CLAUDE.md, the equilibration invariant).

## Tasks

- [🛑] One propagation helper for the indexing side, on `_cov_free`'s pattern:
  zero the infinite entries, propagate the rest exactly, and return which
  outputs use an unmeasured input. Use it at all four sites.
  *Withdrawn 2026-11-03: since #1232 `refine_candidate` is the only place a
  `cov_af` is formed (`engines.conventional_fit` only carries one through an
  integer change of basis) and it refuses a non-finite free variance, so no
  site sees an infinity, and a helper there would have no input.*
- [x] Decide what an unmeasured cell esd is in `CandidateFit.cell_esd`, `inf` or
  NaN, and what `bravais_screen` and the dedup do with it. Measure both on the
  triclinic fixture above before choosing.
  *Decided 2026-11-03: neither, because the candidate is refused. Measured: with
  the infinities zeroed, a, b, c, β agree with the monoclinic fit and α, γ read
  0, but those are first-order numbers. On the refinement side's own rule
  (`ParameterTable._reach`, WP-1804: a nonlinear output reaches an input
  "anywhere in the map's domain") every cell quantity reaches D and F, so all
  six would be marked, which is the refusal by another name.*
- [x] A test: the triclinic fixture's a, b and c esds are finite and match the
  same fit with D and F held out of the basis.
  *Replaced 2026-11-03 by its inverse:
  `test_a_dead_cross_term_leaves_no_direct_length_measured` asserts the
  triclinic fit raises, that the held-out (monoclinic) fit gives finite esds,
  and that the lines' Q stay bit-identical along D while each length moves by
  more than 10× its esd. Fails as "DID NOT RAISE" with the refusal removed.*
- [ ] `python -m tests.unit_replay` digests unchanged on corundum and
  `synthmono_ip`, and `tests/test_acceptance_indexing.py` green (the indexing
  CLAUDE.md's rule for anything an engine calls).

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_indexing_core.py tests/test_indexing_engines.py
.venv/bin/python -m pytest tests/test_acceptance_indexing.py
```

## Handover log

- **2026-10-07** — filed from WP-1545, whose notebook 03 surfaced the class on
  CI. No open WP owns covariance propagation in indexing. WP-1520 calls the
  same function, but it is a gated speed WP, and 1913's `.esd` is about scripts
  agents wrote.
