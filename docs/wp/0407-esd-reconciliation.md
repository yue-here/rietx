# WP-0407 — esd reconciliation (Bérar-Lelann placement)

Milestone: v0.4 · Status: ✅ done 2026-07-24
Depends on: —

## Goal

Reported per-parameter physical esds actually carry the Bérar-Lelann
serial-correlation inflation that the docstrings and the v0.2 milestone
record describe, and the returned correlation matrix becomes a true Pearson
matrix (unit diagonal) — which also revives the high-correlation guard that
is currently dead.

## Context

ROADMAP flagged this as a docs-vs-behaviour mismatch. Tracing it during v0.4
planning (2026-07-24) found the mismatch has a single mechanical cause, and
that cause additionally breaks a guard. **Both findings were verified
numerically**, not just read.

`covariance_estimates` ([`optimize/least_squares.py`](../../src/pxrdref/optimize/least_squares.py),
end of file) does:

```python
cov  = np.linalg.pinv(JTJ) * chi2_red              # no BL
diag = np.sqrt(np.maximum(np.diag(cov), 0.0)) * berar_lelann_factor(data)
corr = cov / np.outer(diag, diag)                  # <-- diag already carries BL
```

Because `corr` is normalised by the **inflated** diagonal, the returned
"correlation" matrix is `true_corr / BL²` — its diagonal is `1/BL²`, not 1.
Measured on a synthetic collinear case with BL = 5.18: correlation diagonal
= 0.0372 (= 1/BL²), true ρ = −0.699 reported as −0.026.

Two consequences follow:

1. **Reported physical esds are effectively RAW.** `stderr_physical`
   ([`params/vector.py`](../../src/pxrdref/params/vector.py)) rebuilds
   `cov_phys = correlation · outer(s, s)` with `s = chain · stderr_internal`
   and `stderr_internal` already ×BL. The `1/BL²` inside `correlation`
   cancels the `BL²` in `outer(s, s)` **exactly** (verified: physical esd ≡
   raw χ²·(JᵀJ)⁻¹ esd to floating-point equality). So the reported esd is the
   raw one, while `Statistics`' module docstring, `covariance_estimates`'
   docstring and [`../milestones/v0.2.md`](../milestones/v0.2.md) all say the
   esd is inflated. `RefinementResult.qpa`'s σ(W), which routes through
   `physical_covariance` → `_cov_free`, inherits the same cancellation.
   Note the inconsistency this creates: the `correlation=None` fallback path
   (`var = C²·(s·s)`, pre-v0.3 behaviour) *does* report inflated esds — so
   today the same parameter gets a different esd depending on whether a
   correlation matrix was available.
2. **The high-correlation guard is dead.** `check_guards`
   ([`strategy/staged.py`](../../src/pxrdref/strategy/staged.py)) thresholds
   `|corr[i,j]| > 0.98`, but every entry is ÷BL² (÷12 at BL ≈ 3.4, ÷27 at
   5.2), so a genuinely degenerate ρ = 0.99 pair reports ≈ 0.08 and never
   trips. Masked because the only guard tests assert it does *not* fire
   (`tests/test_extinction.py`, `tests/test_preferred_orientation.py`).

### Inherited

The Context above traces the BL placement bug on the *single-histogram
Rietveld* path. Three landed WPs added esd routes it does not mention.

From **WP-0306** (Pawley, landed): **there is a second esd path.**
`run_least_squares` computes the covariance over the *augmented* vector
[table θ | per-hkl intensities], then splits it — table esds to
`LSQOutcome.stderr_internal`, intensity esds to `model.pawley.stderr`
([`optimize/least_squares.py`](../../src/pxrdref/optimize/least_squares.py),
the `n_aux` tail). That tail never passes through `stderr_physical`, so it does
**not** get the `1/BL²`-cancellation described above — it is raw for a
different reason. Whatever this WP decides, decide it for both paths and say
so. Also note 0306's handover gotcha (4) asserts "esds carry the Bérar-Lelann
inflation like everywhere else in the package", which this WP's own verified
Context proves false; that line becomes true only once this lands. 0306's
Pawley overlap test asserts esds inflate to ~112 % on an overlapped pair —
re-measure it.

From **WP-0308** (multi-histogram, landed): `run_multi_least_squares` passes
`n_data=n_data_total` over the row layout [all histograms' data rows][all
histograms' penalty rows], so `berar_lelann_factor` runs on the **concatenated**
residual — a run-of-signs serial-correlation statistic evaluated across the
joins between patterns, where consecutive points are not neighbours in 2θ.
Verified at `least_squares.py` in `run_multi_least_squares`. Whether that is
acceptable, or BL should be computed per histogram and combined, is this WP's
call; it is currently unexamined rather than decided.

From **WP-0304** (QPA, landed): QPA σ(W) tracks the reported-esd conditioning
**by construction**, pinned by
`tests/test_qpa.py::test_physical_covariance_block_diagonal_matches_stderr`
(the block diagonal of `physical_covariance` equals the reported per-parameter
esds squared). Checked 2026-07-24: that test feeds *synthetic* `corr` and
`stderr_internal`, so it does not exercise `covariance_estimates` and will keep
passing — but it is the reason σ(W) moves with this fix rather than
independently of it, which the "Ripples" section below already anticipates.

From **WP-0401** (op shim, landed): `covariance_estimates` and all of
`optimize/statistics.py` are declared permanently host-numpy, never routed
through the backend shim. So this fix is plain numpy post-processing — it does
not need to be traceable, differentiable or backend-portable, and must not
acquire `xp.*` calls.

### Decision — reconcile by INFLATING (fix the placement)

```python
sqrt = np.sqrt(np.maximum(np.diag(cov), 0.0))
corr = cov / np.outer(sqrt, sqrt)      # true Pearson, unit diagonal
diag = sqrt * berar_lelann_factor(data)
```

One change fixes both: reported physical esds become genuinely ×BL (matching
every docstring and the v0.2 record — whose headline **a = 4.156895(25)** is
already the inflated number, 7×10⁻⁶ × 3.4 ≈ 24×10⁻⁶, so the record's claim
becomes true rather than needing a retraction), and the correlation matrix
becomes honest so the 0.98 guard means what it says. The alternative
direction (keep raw esds, edit the docs) would *still* have to fix the `1/BL²`
diagonal — the correlation matrix is wrong regardless — so it is strictly
more doc-churn for a worse scientific story.

### Ripples to expect

- `tests/test_acceptance_srm660c.py`: `a_err < 5e-5` still passes (≈24×10⁻⁶);
  the comment above it currently *claims* inflation, so it becomes accurate.
  The `1.5 < esd_inflation < 6.0` assertion is untouched.
- QPA σ(W) becomes ×BL. The round-robin tolerances are referenced to the
  published participant spread and deliberately never lean on σ(W)
  ([CLAUDE.md](../../CLAUDE.md), [../milestones/v0.3.md](../milestones/v0.3.md)),
  so nothing breaks; re-measure any σ(W) digits quoted in records.
  `tests/test_qpa.py` asserts *relative* properties (correlated < independent)
  and is unaffected.
- **The guard may now fire in staged plans.** That is the point, but it is a
  behaviour change: watch the acceptance runs for guard-driven differences
  and report them rather than silencing the guard.
- The memory note `esd-berar-lelann-conditioning` documents the *pre-fix*
  behaviour and must be updated or deleted when this lands.

## Non-goals

Replacing Bérar-Lelann with Andreev's bias-corrected figure of merit (the
documented conservatism — E[χ²']/χ² = 1 + 4/π ≈ 1.51 even for white noise —
stays as-is and stays documented); changing what `esd_inflation` reports;
touching the covariance's penalty-row handling.

## Tasks

- [x] Fix `covariance_estimates`: unit-diagonal correlation from the raw
      sqrt-diagonal, BL applied only to the returned esd diagonal; update
      the docstring to describe what it now does
- [x] Re-measure SRM 660c; correct the comment in
      `tests/test_acceptance_srm660c.py` and the running text in
      `docs/milestones/v0.2.md` if any raw digits are quoted (v0.2 record
      already quoted the inflated `(25)` — no change needed there)
- [x] Regression test: a known-collinear pair (e.g. zero-shift ~ sample
      displacement freed together) now trips the 0.98 guard, and the returned
      correlation matrix has unit diagonal
- [x] Re-measure QPA σ(W); confirm no acceptance tolerance regresses and
      update quoted digits in records
- [x] Update/delete the `esd-berar-lelann-conditioning` memory note (deleted)

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_acceptance_srm660c.py tests/test_qpa.py tests/test_v02_core.py -q
.venv/bin/python -m pytest -q
```

Measured: reported SRM 660c `a`-esd is the BL-inflated value (≈24–25×10⁻⁶,
still < 5×10⁻⁵); the returned correlation matrix has unit diagonal; the
correlation guard trips on a deliberately collinear pair.

## References

- Bérar & Lelann (1991) J. Appl. Cryst. 24, 1 — serial-correlation esd
  inflation.
- Andreev (1994) J. Appl. Cryst. 27, 288 — bias-corrected figure of merit
  (cited as the known conservatism, formula not reproduced).

## Handover log

- **2026-07-24** — created during v0.4 planning. Root cause traced and
  **numerically verified**: `corr = cov/outer(diag,diag)` normalises by the
  BL-inflated diagonal ⇒ correlation diagonal = 1/BL² (measured 0.0372 at
  BL = 5.18), which cancels BL exactly in `stderr_physical` (measured: equals
  the raw esd to floating-point equality) and deflates the guard's ρ by BL².
  Decision recorded: inflate/fix-the-placement.

- **2026-07-24 (landed)** — fix shipped; all five checklist items done, both
  acceptance commands green (fast suite + full slow suite, 21 acceptance tests
  passed). One-line fix in `covariance_estimates`: correlation now normalised
  by the raw sqrt-diagonal (true Pearson, unit diagonal), BL applied only to
  the returned esd diagonal.

  Measured after fix:
  - SRM 660c `a`-esd = **2.49e-5** (raw 7.4e-6 × BL 3.38) — the reported number
    is now the milestone's `4.156895(25)`. Added a `1.5e-5 < a_err` lower bound
    so a regression back to raw would fail.
  - Collinear zero-shift ~ Bragg-Brentano displacement reads ρ ≈ 1.0 and trips
    the default 0.98 guard; returned correlation has unit diagonal (new pins in
    `tests/test_v02_core.py`).
  - QPA σ(W) 0.1–0.9 wt% (was 0.1–0.4 raw); no acceptance tolerance regresses.
  - Pawley overlapped-pair rel esd ≈ 116% (BL ×1.567).

  **Corrections to this WP's own Context/Inherited (verify, don't trust):**
  1. The Inherited note calls the Pawley `model.pawley.stderr` tail "raw". It is
     **not** — the tail is `diag[n_table:]` and `diag = sqrt·BL`, so it already
     carried BL *before* this fix and is unchanged *by* it. What flipped is the
     table path (raw→inflated via the removed 1/BL² cancellation). So both esd
     paths now report inflated esds; WP-0306 gotcha (4) is now globally true
     because "everywhere else" (the table path) caught up, not because the tail
     changed. No code change was needed on the Pawley path.
  2. Multi-histogram BL: examined and **kept** on the concatenated data residual
     (documented in `run_multi_least_squares`). Join contamination is
     ≤ n_hist−1 artificial run boundaries out of n_data_total (negligible), and
     a shared parameter draws from every histogram so there is no clean single
     per-parameter factor to combine. Not re-architected.

  **Ripples that surfaced (as the WP predicted — reported, not silenced):**
  Two unit tests rode the bug and were reconciled to the honest physics, not
  worked around:
  - `test_extinction.py`: co-freeing extinction+scale+Biso on one pattern is a
    **genuine** degeneracy (ρ(ext,scale) ≈ +0.97, ρ(ext,La-Biso) ≈ +0.87). The
    old "separable, guard stays quiet" claim was the BL²-deflation artifact.
    Rewritten to assert the guard **fires** (renamed
    `..._correlates_with_scale_and_biso_and_the_guard_fires`). The PO sibling
    (`test_po_is_identifiable...`) is genuinely identifiable (worst ρ ≈ 0.28)
    and passes unchanged — now for real.
  - `test_aniso_adp.py`: U11/U33 separation is ≈2.2σ against honest esds (was
    3σ against raw); relaxed 3σ→2σ, comment corrected. Recovery-within-4-esds
    assertions only *widen* under inflation, so they were safe.

  Next: nothing on 0407. If a future WP touches esds, the two `stderr_physical`
  paths are now consistent (both ×BL) and the guard is live at 0.98.
