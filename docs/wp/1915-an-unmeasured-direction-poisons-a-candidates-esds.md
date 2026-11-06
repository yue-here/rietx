# WP-1915 — an unmeasured direction poisons every esd of an indexing candidate

Milestone: unscheduled · Status: ✅ 2026-11-03 — the refusal of #1232 stands, measured and pinned; the goal's surviving candidate would carry wrong esds
Track: What fires, and what stays silent
Depends on: —

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
- [x] `python -m tests.unit_replay` digests unchanged on corundum and
  `synthmono_ip`, and `tests/test_acceptance_indexing.py` green (the indexing
  CLAUDE.md's rule for anything an engine calls).

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_indexing_core.py tests/test_indexing_engines.py
.venv/bin/python -m pytest tests/test_acceptance_indexing.py
```

## Handover log

- **2026-11-03** — closed, the goal withdrawn by measurement. An indexing fit whose
  lines leave a metric cross term unconstrained looks as if it has only one angle
  unmeasured, and this WP asked for it to survive with its lengths' esds intact. It
  cannot: the inverse metric puts every cross term into every length, so the data fit a
  whole family of cells with different a, b and c equally well, and any finite esd on
  those lengths is a confident wrong number. Main has refused such a fit since #1232,
  and that refusal is now pinned with its reason. No code path changed.

  *Done.* Goal and Context marked superseded in part (#1232 landed after this WP was
  filed). The helper task is withdrawn: `refine_candidate` is the only place a
  `cov_af` is formed and it refuses a non-finite free variance, so none of the four
  sites sees an infinity. `test_a_dead_cross_term_leaves_no_direct_length_measured`
  (tests/test_indexing_core.py) replaces the asked-for test with its inverse: the
  triclinic fixture raises on the variance message, the monoclinic fit to the same
  lines (D and F held out of the basis) gives finite esds, and Q is bit-identical
  along D while each length moves by more than 10x its esd. With the refusal patched
  out it fails as DID NOT RAISE. A comment in `refine_candidate` and one rule in the
  indexing CLAUDE.md say why (cap 361 -> 365, logged).

  *Measured* (macOS arm64, `[dev]`, this worktree's venv). The fixture: truth
  (5.1, 6.3, 7.2, 90, 101, 90), eleven h0l and 0k0 lines, sigma 1e-4 Q. Main raises
  "not a lattice". Bypassing the raise: diag cov is inf on D and F; the naive
  propagation gives NaN in all 36 `cov_af` entries and all six esds. With the
  infinities zeroed, a, b, c, beta esds equal the monoclinic fit's to the printed digit
  (1.3003e-4, 1.8187e-4, 2.6175e-4, 3.53e-3) and alpha, gamma read 0. The cell
  Jacobian's D and F columns are exactly 0 on a, b, c at D = F = 0, which is why the
  first-order numbers are finite. At D = 0.01, Q identical to the bit, the cell is
  (5.105, 6.469, 7.393, 103.1, 101.3, 87.5): b +2.7 %, c +2.7 %, a +0.1 %; at
  D = 0.0137 b is +5.2 %. The refinement side's declared-reach rule
  (`ParameterTable._reach`, WP-1804) would mark all six cell quantities, so "inf or
  NaN" never arises. `bravais_screen` already refuses a non-finite esd (#1232), and
  the dedup never meets one.
  Gates: `tests/test_acceptance_indexing.py` 45 passed (14:27, alone under serial.py).
  `python -m tests.unit_replay` on corundum and `synthmono_ip`, 15 units, all complete:
  corundum dichotomy hexagonal ffe7a8cb, tetragonal 60ad7492, trigonal 93b93a15;
  svd hexagonal 82e6c268, trigonal 7d4f4297; trial_error hexagonal 6f277e25,
  tetragonal 77c695ae, trigonal 397c20a8; synthmono_ip dichotomy 89046549, svd
  45622b10, trial_error 0b4a059e; the cubic units empty (e3b0c442). No main baseline
  was replayed: the src diff is comment-only, so they are unchanged by construction.
  Fast selection: 13753 passed, 318 skipped, 34 xfailed, 1 failed (8:24, alone under serial.py); the one failure was `test_the_wp_index_is_the_generators_output`, the index left stale by this close's header edit mid-run, regenerated after and green below. The added test costs 0.01 s.
  `python -m tests.reader_output`: exit 0, unchanged.

  *Review.* `/code-review high` found seven; four fixed (the test now matches the
  variance message rather than `cell_from_af`'s shared "not a lattice"; the comment
  says the unguarded propagation gives NaN; b's shift corrected from 5 % to 2.7 %;
  `conventional_fit` named as a carrier of `cov_af`). Declined: the bit-identical-Q
  assertion is fixture arithmetic by design, being the point it illustrates; the
  CLAUDE.md bullet's parenthesis is its one-clause evidence, which protocol rule 4
  allows; the missing-entry cross-reference is this entry.
  *Generality:* no audit row, default or heuristic added; judge not dispatched.

  *For the maintainer.* This withdraws the WP's own goal in favour of #1232's
  refusal. If a surviving candidate with its dead angles marked is still wanted, it
  needs reciprocal-cell esds (a\*, b\*, c\* are measured), not direct ones, and a
  new WP. PR #1393.

  Next: none on this WP.

- **2026-10-07** — filed from WP-1545, whose notebook 03 surfaced the class on
  CI. No open WP owns covariance propagation in indexing. WP-1520 calls the
  same function, but it is a gated speed WP, and 1913's `.esd` is about scripts
  agents wrote.
