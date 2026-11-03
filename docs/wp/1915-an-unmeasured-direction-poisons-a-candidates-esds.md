# WP-1915 — an unmeasured direction poisons every esd of an indexing candidate

Milestone: unscheduled · Status: 🔄 2026-11-03 — claimed by @mustachefeeling
Track: What fires, and what stays silent
Depends on: —
Priority: P3 2026-10-07 — NaN in every cell esd of a candidate whose lines leave one metric term unconstrained, silent on macOS; it reaches the Bravais screen's tolerance and the χ² dedup

## Goal

A candidate cell whose lines leave some A..F direction unconstrained reports
that direction as unmeasured and every other esd exactly. Today all of them
come back NaN.

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

**Consumers to read before choosing the marker.** `cell_esd` sets the spglib
`symprec` sweep in `reduce.bravais_screen` through `np.max(...)[:3]`, so one NaN
or inf there changes the Bravais screen. `cov_af` is the χ² dedup's covariance
(`engines._dedup_groups`, through `reduce.reduced_covariance`), so its marker
decides whether two candidates merge. The root rule is "consumers mark, never
clamp" (root CLAUDE.md, the equilibration invariant).

## Tasks

- [ ] One propagation helper for the indexing side, on `_cov_free`'s pattern:
  zero the infinite entries, propagate the rest exactly, and return which
  outputs use an unmeasured input. Use it at all four sites.
- [ ] Decide what an unmeasured cell esd is in `CandidateFit.cell_esd`, `inf` or
  NaN, and what `bravais_screen` and the dedup do with it. Measure both on the
  triclinic fixture above before choosing.
- [ ] A test: the triclinic fixture's a, b and c esds are finite and match the
  same fit with D and F held out of the basis.
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
