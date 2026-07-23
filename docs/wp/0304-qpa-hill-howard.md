# WP-0304 — QPA: Hill-Howard ZMV mass fractions

Milestone: v0.3 · Status: ✅ done 2026-07-23
Depends on: —

## Goal

Report quantitative phase-analysis weight fractions from the refined phase
scales via the Hill-Howard/Bish-Howard ZMV relation, with propagated
uncertainties, as a typed result object.

## Context

The relation (Hill & Howard 1987): for phase p with Rietveld scale S_p,

    W_p = S_p·(ZMV)_p / Σ_q S_q·(ZMV)_q

where Z = formula units per cell, M = formula mass, V = cell volume. All three
are already derivable from the refined model: V from
[`crystallography/lattice.py`](../../src/pxrdref/crystallography/lattice.py),
M and Z from the phase's atom list + site multiplicities
([`crystallography/symmetry.py`](../../src/pxrdref/crystallography/symmetry.py))
— **do not ask the user to type Z·M·V by hand**; that is the GUI-era ritual
this package exists to remove. Occupancies enter M (a partially occupied site
weighs less), so compute M from the *refined* occupancies, not the formula
string.

Important scope caveat to document in the API, not hide: these are fractions
of the **crystalline, modelled** content. An unmodelled amorphous fraction or
a missing phase makes them sum to 1 anyway. Internal-standard/amorphous QPA is
fenced to v2; say so in the docstring and in the report field.

Uncertainty propagation: W_p is a ratio of correlated refined scales, so
σ(W_p) must come from the scale block of the covariance matrix (the full
Cov is available in [`optimize/least_squares.py`](../../src/pxrdref/optimize/least_squares.py)),
not from σ(S_p) treated as independent. Carry the Bérar-Lelann inflation
through — the reported esds elsewhere in the package do, and a QPA number with
a differently-conditioned uncertainty would be inconsistent.

Result surface: a typed pydantic object (JSON round-trip, `extra="forbid"`)
hanging off `RefinementResult` in
[`schemas/results.py`](../../src/pxrdref/schemas/results.py) — one row per
phase with W, σ(W), Z, M, V, S. WP-0309 exports it as a table; WP-0305 adds
the Brindley correction as an adjustment to the same object.

## Non-goals

- Brindley microabsorption (WP-0305) — separate, and separately validated.
- Internal-standard / amorphous quantification (v2 fence).
- The round-robin acceptance run (WP-0310).

## Tasks

- [x] Z, M, V derivation from the refined model (occupancy-weighted M;
      multiplicity-aware Z); unit test against hand-computed values for a
      couple of known structures
- [x] `QuantitativePhaseAnalysis` result schema + attachment to
      `RefinementResult`; JSON round-trip test
- [x] Weight fractions from refined scales; σ(W) from the scale block of the
      covariance (correlated ratio propagation), Bérar-Lelann carried through
- [x] Docstring + field-level statement that fractions are of the modelled
      crystalline content only
- [x] Two-phase synthetic test with known mixing ratio: recovered fractions
      within propagated σ

## Acceptance

Weight fractions on a synthetic two-phase mixture with a known ratio agree
within the propagated uncertainty; σ(W) demonstrably differs from the naive
independent-scale propagation (assert the correlated path is being used).

```sh
.venv/bin/python -m pytest tests/test_qpa.py -q
```

## References

- Hill & Howard (1987) J. Appl. Cryst. 20, 467 — ZMV scale-factor QPA.
- Bish & Howard (1988) J. Appl. Cryst. 21, 86.
- Madsen et al. (2001) J. Appl. Cryst. 34, 409 — IUCr QPA round robin
  (dataset target for WP-0310).

## Handover log

- **2026-07-22** — created from the ROADMAP split; not started.
- **2026-07-23** — **done.** Landed in five commits:
  1. `optimize/qpa.py` core — `atomic_weight` (gemmi, guards gemmi's
     placeholder element "X": unknown symbols map to Z=0/weight≈1.0, *not* an
     error, so we check `atomic_number == 0`), `phase_zmv` (occupancy-weighted
     cell mass Z·M from orbit multiplicities via `expand_positions`), and
     `weight_fractions` (Hill-Howard ratio + correlated/independent σ).
  2. `PhaseQuantity`/`QuantitativePhaseAnalysis` schema (re-exported from
     `pxrdref.schemas`) + optional `RefinementResult.qpa`.
  3. `ParameterTable.physical_covariance` + `_cov_free`/`_phys_sigma_free`
     (factored out of `stderr_physical`); `compute_qpa`; wired into
     `_build_result` (Rietveld only — Le Bail scales are degenerate).
  4. Two-phase synthetic acceptance (LaB6 + CaF₂): recovered W within σ.
  5. This log + ROADMAP/CLAUDE sync.
- **Z/M split is display-only.** QPA rests on the unambiguous `cell_mass` (Z·M,
  occupancy-weighted) and `cell_volume`; `z` is a best-effort GCD of the
  integer per-element cell counts (falls back to `z=1`, `molar_mass=cell_mass`
  under partial occupancy — see `test_zmv_partial_occupancy…`). Note 0.5×(mult 8)
  = 4 is still integer, so half-occupancy does *not* trigger the fallback; a
  non-integer count (e.g. occ 0.3) does.
- **σ(W) conditioning gotcha (verified empirically, not changed here).**
  `covariance_estimates` returns per-parameter esds already ×BL, but the
  correlation matrix it returns carries `1/BL²` on its diagonal, so
  `correlation ⊙ outer(s,s)` — the `Cov_free` both `stderr_physical`'s
  correlated path *and* `physical_covariance` use — reconstructs the **raw**
  χ²·(JᵀJ)⁻¹ covariance (BL cancels). Consequence: the reported per-parameter
  esds on `RefinementResult` (built via the correlated path) are raw, with BL
  reported separately in `Statistics.esd_inflation`. QPA σ(W) matches that
  conditioning **by construction** (proved by
  `test_physical_covariance_block_diagonal_matches_stderr`). The
  `Statistics.esd_inflation` docstring still claims reported esds are ×BL —
  that is a pre-existing correlated-path discrepancy, out of scope for this WP;
  worth a dedicated fix (touches every esd, would perturb tolerances).
- **Next**: 0304 unblocks 0305 (Brindley), 0309 (QPA table export) and 0310
  (round-robin acceptance). `compute_qpa` returns the typed object 0309 will
  tabulate and 0305 will adjust in place.
- **2026-07-23 — review follow-up** (multi-angle code review). Fixed:
  1. **Multiplicities are now taken frozen from the compiled model**
     (`len(PhaseSites.ops[j][0])`) instead of re-running `expand_positions` on
     *refined* coordinates. An atom refined within the ~1e-4 dedup tolerance of
     a special position was collapsing its orbit (verified: (0.49996, ½, ½) in
     P m -3 m gave mult 1 not 6), mis-weighing the cell and every W. `phase_zmv`
     keeps the coordinate path for standalone/ideal-coord use (the ZMV unit
     tests); `compute_qpa`/`_build_result` pass the frozen counts.
  2. **`element_symbol` valence fallback.** A greedy 2-letter parse read the
     Waasmaier-Kirfel valence key `"Cval"` as the non-element `"Cv"` and crashed
     `_build_result` after a good fit; now tries the 2- then 1-letter prefix
     against gemmi (`"Cval"`→C, `"Siva"`→Si, `"Fe3+"`→Fe).
  3. **σ(W) degeneracy.** `weight_fractions` returns `None` esds for an all-zero
     scale block (no scale freed ⇒ absence of information, not σ(W)=0) and
     raises on a non-positive scaled total instead of emitting NaN.
  4. Two-phase test now asserts the *wired* σ(W) differs from the naive
     independent propagation from σ(S) alone (proves the correlated block is
     used end-to-end), and unit tests cover the valence species + degenerate
     covariance. Fast+slow suites green, ruff clean.
