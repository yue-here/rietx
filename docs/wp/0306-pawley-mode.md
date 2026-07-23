# WP-0306 — Pawley mode

Milestone: v0.3 · Status: ✅ done 2026-07-23
Depends on: —

## Goal

A third refinement mode alongside `rietveld` and `lebail`: per-hkl intensities
refined **as parameters** (Pawley 1981), with the near-singular normal
equations handled explicitly and the results stored in the history container
already reserved for them.

## Context

The seam exists. `ReflectionState` in
[`schemas/history.py:117`](../../src/pxrdref/schemas/history.py#L117) was
built with `kind: Literal["lebail_extracted", "pawley_refined"]`,
`stderr: list[float] | None` ("Pawley has esds; Le Bail does not") and
`varied: bool` — its docstring states outright that this exists so Pawley mode
never has to push one dot-path per reflection into
`RefinementState.free_paths`. **Honour that**: per-hkl intensities go in the
reflection container, not into the named dot-path table in
[`params/vector.py`](../../src/pxrdref/params/vector.py). The mode seam is
`IntensityModel` (`rietveld`/`lebail`, see
[`model/forward.py`](../../src/pxrdref/model/forward.py) and
`CompiledModel.lebail_update`).

The hard part is conditioning, not bookkeeping. Overlapping reflections make
the intensity block of JᵀJ near-singular — at exact overlap it *is* singular,
and the split between the overlapping intensities is arbitrary. Options in
rough order of preference: soft equality/smoothness restraints on strongly
overlapped groups, an explicit rank-revealing solve with the null-space
directions reported, or a documented pinv fallback. Whatever is chosen, the
package rule applies: **report the ambiguity, never a confident wrong
singleton** (design record, "Outputs & fit assessment"). Overlapped groups
whose split is unresolved must come back flagged, with esds that reflect it.

The intensity block is exactly linear in the parameters, so its Jacobian
columns are analytic and cheap (same argument as the Chebyshev background
coefficients). Take the exact columns; do not let this block hit FD.

Le Bail and Pawley must remain distinguishable in stored state: a node
restored from `kind="lebail_extracted"` reseeds the fixed-point loop, while
`kind="pawley_refined"` restores refined values with their esds.

## Non-goals

- Indexing / space-group determination from Pawley output (v2 territory).
- Structure solution. Pawley here serves cell + profile extraction and
  whole-pattern fitting, same role as Le Bail.

## Tasks

- [x] `mode="pawley"` through `Refinement.fit` / `refine()` and the
      `IntensityModel` seam; per-hkl intensities held in the compiled model,
      serialized via `ReflectionState(kind="pawley_refined", stderr=..., varied=True)`
- [x] Analytic Jacobian columns for the intensity block (linear ⇒ exact)
- [x] Near-singular handling: overlap grouping + restraints and/or
      rank-revealing solve; unresolved splits reported as such with honest esds
- [x] History round-trip: checkout/replay of a Pawley node restores refined
      intensities *and* esds; Le Bail nodes keep reseeding behaviour
- [x] Tests: synthetic pattern with a deliberately overlapped pair —
      the sum is recovered accurately while the split is flagged unresolved;
      Pawley and Le Bail agree on cell within esds on a clean pattern
- [x] obs/calc/diff PNGs to `tests/output/` for every Pawley test refinement

## Acceptance

On a clean synthetic pattern, Pawley and Le Bail recover the same cell within
esds and comparable Rwp; on an overlapped pair the summed intensity is right
and the individual split is reported unresolved rather than confidently split.

```sh
.venv/bin/python -m pytest tests/test_pawley.py -q
```

## References

- Pawley (1981) J. Appl. Cryst. 14, 357.
- Le Bail, Duroy & Fourquet (1988) Mater. Res. Bull. 23, 447 — the contrast.

## Handover log

- **2026-07-22** — created from the ROADMAP split; not started.
- **2026-07-23** — **done.** Implemented `mode="pawley"` end to end.
  - **Seam**: `Mode` (`schemas/common.py`) and `RefinementResult.mode`
    (`results.py`) gained `"pawley"`. `CompiledPhase.lebail_intensity` renamed
    `hkl_intensity` (the buffer is shared by both intensity models — extracted
    in Le Bail, refined in Pawley); `phase_peaks` reads it for both, `intensity
    = base·w_line` (Lp already inside, same as Le Bail).
  - **Intensity block off the ParameterTable**: `PawleyBlock`
    (`model/forward.py`) holds the flat phase→slice layout, the overlapped
    groups, and the restraint rows. `run_least_squares` appends it to θ =
    `[table θ | intensities]`, splits the covariance back (table esds ← top-left
    block; intensity esds → `model.pawley.stderr`), and returns a **table-only**
    `LSQOutcome` (`n_aux` records the tail length) so every existing table
    consumer — `commit`, `stderr_physical`, the guards — is untouched.
  - **Analytic columns**: intensity columns are exactly `−√w·Σ_lines w_line·Ω`
    on the window (`_pawley_intensity_columns`, reusing `derivative_bases` Ω),
    never FD; the overlap-restraint rows are `∂(R·I)/∂I = R`. Verified against
    finite differences over the whole augmented residual in
    `test_pawley_intensity_jacobian_matches_fd`.
  - **Near-singular handling**: overlapped groups (primary-line centres within
    `PAWLEY_OVERLAP_FWHM_FRAC`·mean-FWHM, contiguous) get √λ-scaled *equal-split*
    restraint rows (`build_pawley_restraint`, scaled to the seeded intensities so
    the split-direction esd ≈ intensity/√λ ≈ 100 % at λ=1). This makes the
    regularised covariance report an honest **large** esd for an unresolvable
    split instead of the spuriously tight one a bare pinv of a singular JᵀJ gives.
    Groups where *no* member is data-pinned come back as
    `PAWLEY_OVERLAP_UNRESOLVED` diagnostics naming the hkls (`refine.py`).
  - **History**: `_extract_reflections` tags Pawley nodes `pawley_refined` with
    per-hkl `stderr` + `varied=True`; carry/restore/replay share the by-hkl
    scatter with Le Bail. Round-trip verified (replay reproduces Rwp; stripping
    the hkl→I map wrecks it).
  - **Plan**: `pawley_default` preset (cell + profile, mirrors `profile_only`);
    intensities refine as an implicit block every stage. Seeded by one Le Bail
    partition on the first stage, carried thereafter (never re-partitioned).
  - **Acceptance** (`tests/test_pawley.py`, all green; PNGs in `tests/output/`):
    clean synchrotron LaB6 — Pawley vs Le Bail cell agree within esds, Rwp
    0.0403 vs Le Bail; Cu-LaB6 with the accidental (221)/(300) exact degeneracy
    — summed intensity recovered to 0.6 % (81.4 vs 81.9), split 40.7/40.7 with
    ~112 % esds, flagged unresolved. GoF ≈ 1.03 on both.
  - **Gotchas**: (1) the intensity buffer is a *single* per-phase array shared by
    both modes — don't reintroduce a separate `lebail_intensity`. (2) `n_free`
    for Rexp/GoF counts the whole intensity block (`_pawley_n`); the restraint
    makes that slightly conservative (standard Pawley convention). (3) replay vs
    the as-optimised metric differs by the documented staleness gap — the test
    uses `rel=1e-3`, not exact equality. (4) esds carry the Bérar-Lelann
    inflation like everywhere else in the package.
  - **Not done (out of scope, deferred)**: a per-reflection Pawley table on
    `RefinementResult` — intensities/esds live in the history `ReflectionState`;
    WP-0309 (exporters) is the place to surface a reflection table if wanted.
