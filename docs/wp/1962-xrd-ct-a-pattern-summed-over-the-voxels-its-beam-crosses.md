# WP-1962 — XRD-CT: a pattern summed over the voxels its beam crosses

Milestone: unscheduled · Status: ⬜
Track: Candidates — named on a use case, not yet on a measurement
Depends on: 1325 (the scalable joint solver, and coordinates in any number of dimensions)
Priority: P3 2026-10-14 — named on a use case, not on a measurement; 1325's blocked solver makes reconstruct-then-fit a working route to ~1 400 voxel patterns, and the direct route still needs a matrix-free solver

## Goal

rietx can fit X-ray diffraction computed tomography (XRD-CT) data **from the
measured scans**. Each recorded pattern is computed as the sum of
contributions from every voxel (small volume element) its beam crosses. Each
voxel's parameters (phase density, cell, crystallite size) are then refined
against the raw data, rather than against patterns reconstructed from it.
Parallax is modelled instead of smeared, and every voxel parameter comes back
saying what its esd means under the regularisation the fit needed. That is
the deliverable *if* the first task's measurement says it is worth building;
otherwise this WP closes as a finding.

## Context

**This is a candidate**, filed 2026-10-14 by the WP-1325 session on the
maintainer's decision. Nothing in `docs/` mentioned tomography before it. Its
first task is the measurement that decides whether it opens.

### What XRD-CT measures

A pencil beam is translated across a slice of the sample, and the slice is
rotated. That gives one powder pattern per (translation, angle) pair. Stacked
by 2θ channel, these are **sinograms**. Each pattern is the path-length
weighted sum of what every voxel along the beam scatters. Two routes analyse
it.

- **Reconstruct, then fit.** Standard CT reconstruction (filtered back
  projection, or an iterative algebraic method), run per 2θ channel, turns
  the scans into one pattern per voxel. Each voxel's pattern is then refined.
  - Frølich et al. (2016) refined each voxel separately.
  - Wragg et al. (2015) refined a whole slice as one parametric TOPAS
    refinement, which is [1325](1325-parametric-series.md)'s library case with
    (x, y, z) coordinates. That WP covers this route once its coordinates are
    3-D.
  - Two catches, both this WP's to answer. Reconstructed intensities are not
    counts: they can be negative, and their noise is correlated between
    neighbouring voxels and channels. So the weights rule (the file's esd
    column, else Poisson √max(y,1)) has no honest σ to give. And
    reconstruction cannot represent **parallax** (below), so it ends up as
    extra peak width.
- **Direct.** Fit the raw sinograms with the projection inside the residual:
  y_k = Σ_v A_kv · f_k(p_v) + b_k. Here A_kv is the length of pattern k's
  beam inside voxel v, f_k is voxel v's calculated pattern as seen from scan
  k, and b_k is a per-scan background. Vamvakeros et al. (2020, "DLSR") did
  this with TOPAS. It is the only route that removes parallax, and the
  authors call it generic to any chemical tomography with an accurate forward
  model.

**Parallax** is a large sample's geometry error. Scattering from the near and
far sides of the sample reaches the detector from different distances, so
one 2θ lands on several detector pixels. Which way it shifts depends on the
voxel's position and the projection angle. In the direct route it is a
**known** per-(scan, voxel) shift of the 2θ axis, computable from geometry
and frozen per stage like every other discrete quantity. In reconstruction it
is averaged over angles into broadening, which biases cell and size (DLSR's
measured motivation).

**The analogue elsewhere is dynamic PET.** Kamasak et al. (2005) estimated
kinetic parameters directly from sinograms rather than from reconstructed
frames, and got lower variance. One later study measured 30-60 % lower
coefficient of variation, with the gain shrinking at high counts. The
measurement here should expect the same shape.

### What rietx lacks for the direct route (survey, 2026-10-14)

- **No sum over specimens.** A calculated pattern is one `Structure`'s phases
  summed (`CompiledModel.evaluate`, `model/forward.py:1986-1999`). Mixing
  voxels with different cells today would mean one phase copy per voxel. That
  is a seam, not a workaround, and it is this WP's central design item.
- **No solver at this size.** A 100 × 100 slice is 10⁴ voxels. With a few
  parameters each, that is 10⁴-10⁵ columns against ~10⁴ scans × ~10³ points
  of rows. The joint Jacobian is dense today (`least_squares.py:2459`).
  1325's block-structured solver covers the reconstruct-then-fit library.
  The direct route also couples every voxel on a beam path, so its normal
  matrix is not block-diagonal with a border. It needs a **matrix-free**
  iterative solver that only ever forms J·v and Jᵀ·v. The jax and torch
  backends produce exactly those by automatic differentiation (`jvp`/`vjp`)
  without building J.
- **No regularisation in a joint fit, and esds that would have to say so.**
  Tomography is ill-posed without a penalty (smoothness or total variation).
  A penalty is a row block below the data in the joint residual, the seam
  [1995](1995-soft-restraints-in-a-joint-fit.md) built for soft restraints
  (`least_squares._multi_closures`). A
  penalised fit's esds are conditional on the penalty weight, and the report
  must say so rather than quote them bare (the "never a confident wrong
  singleton" rule).
- **No honest σ for reconstructed patterns**, as above.

### GPU: when a device pays (v0.4 record, `docs/milestones/v0.4.md:168-194`)

- One pattern on the Apple GPU ran **46-182× slower** than numpy. Per-call
  overhead is flat at ~80-100 µs, and one pattern is thousands of tiny calls,
  one per peak window.
- Batched into big calls, the device **breaks even at ≈ 65 k values per
  call**. It plateaus at **≈ 2.5-2.7×**, because the peak arithmetic is
  memory-bound (~17 operations per value read).
- The plateau needs ≈ 10 synchrotron or ≈ 60 lab patterns in one batch. A
  tomography slice is far past that, so this is the first workload where a
  device pays at all.
- Three unknowns:
  - the CPU default has since gained compiled multi-threaded kernels
    (WP-1115, WP-1940), so the 2.5× was against a slower baseline;
  - it was measured on Apple unified memory, so a data-centre GPU with its
    own memory bandwidth and full fp64 may gain more (a hypothesis: CUDA is
    unvalidated on hardware, v0.4 record item 4);
  - nothing batches patterns today. `multi.py` loops over histograms, and
    patterns with different peak windows need padding to batch.
- The fp64 boundary (`backend/linalg64.py`) still holds. Columns may be fp32
  on a device; cost, statistics and the solve stay fp64 on the host.
- **Order: solver first, device second.**

### Licensing

TOPAS is closed, so DLSR is read from its paper only. Check the licence of
any open XRD-CT toolkit (nDTomo, the DLSR authors' own) before reading its
code; until then, concepts only. scikit-image's `radon`/`iradon` are BSD and
usable for the synthetic phantom's reconstruction, as a dev-only dependency.

### Inherited

- **2026-10-14, from WP-1325: the blocked joint solver landed, and its
  blocks are per pattern.**
  - **What it is.** `optimize/blocked.py`'s `BlockJacobian` holds each
    histogram's rows against its own columns. The LM driver scatters the
    normal equations into a dense n×n A and keeps its BVLS / projected-CG
    step, and the covariance is the Schur complement of the arrow.
  - **What it measured.** On a synthetic (x, y) library at 3 000 points a
    pattern, N = 300 (3 004 columns) ran in 48 s and 1 GiB. Its own limit is
    the n×n arrays, about 1 400 patterns at that width (extrapolated). The
    serial per-histogram Jacobian loop is 45 % of the fit (WP-1325
    § Measured: scaling).
  - **What it means here.** For the direct route this is the shape, not the
    answer: a voxel's columns sit in many patterns' rows, so the blocks are not
    disjoint, and 10⁴-10⁵ columns overflow a dense A. The matrix-free item
    above stands. What carries over:
    - `blocked.choose_layout` and `LSQOutcome.jacobian_layout`, the seam for
      a third layout;
    - the Schur covariance's equilibration and pseudo-inverse cut.
  - **On choosing the penalty weight.** 1325 surveyed and measured a kernel
    (smoothness) prior across patterns (§ A kernel over the coordinates,
    § Measured: where one pattern cannot see the parameter). REML on the
    per-pattern trajectory misled badly in the weak-signal regime, which bears
    on how this WP chooses its penalty weight.
- **2026-10-14 (later), from WP-1325: the per-pattern Jacobian is python-bound,
  so threads do not parallelise it.**
  - At 60 patterns the Rust kernels are under 3 % of the fit. A thread pool
    across patterns ran at 0.49× on 4 threads, with or without openblas,
    OpenMP and the kernel pool held to one thread, so it is the GIL.
  - 71-76 % of the Jacobian is the peak chain, re-run once per column.
    Columns that reach one target share it, which is 1325's new task
    (1.48-1.52× on the Jacobian loop).
  - For the voxel solver: budget the per-pattern Jacobian at 2.4-2.6 ms of
    python for 3 000 points of a simple phase. Plan cross-pattern
    parallelism as processes, not threads (WP-1325 § Measured: where the
    joint Jacobian's time goes).
- **2026-10-15, from WP-1960: the texture model this WP's Non-goals waits on
  has landed.** `Phase.texture` refines a spherical-harmonics texture under
  cylindrical sample symmetry, one sample angle per geometry. Texture
  tomography stays a non-goal here, but its reason is now "not this WP" rather
  than "texture does not exist". A per-voxel texture would need the
  non-cylindrical sample symmetry that WP-1960 left out (its Non-goals).

## Non-goals

- Texture tomography (spherical harmonics per voxel; Liebi et al. 2015 for
  SAXS). That waits on texture itself, which
  [1960](1960-spherical-harmonics-texture.md) scopes.
- PDF-CT, absorption-contrast CT, and full 3-D or helical acquisition. A
  stack of 2-D slices comes first.
- Reconstruct-then-fit as a feature: it is 1325's library case. This WP owns
  only its σ question.
- Real-time or beamline-side processing.

## Tasks

- [ ] **The measurement that decides whether this opens.**
  - Build a synthetic phantom slice (≤ 32 × 32 voxels, one or two phases,
    with a known gradient in cell and crystallite size). Simulate
    pencil-beam scans with rietx's forward model, with and without parallax,
    at a stated sample diameter and detector distance.
  - Run reconstruct-then-fit: reconstruct per 2θ channel, then fit each voxel
    independently, then fit jointly through 1325 with a smooth spatial basis.
  - Report cell and size bias and scatter against truth, per voxel.
  - Open if parallax biases a refined parameter by more than its esd at a
    realistic geometry. Close as a finding if reconstruct-then-fit recovers
    truth within its esds there.
- [ ] **The σ of a reconstructed pattern**: propagated through the
  reconstruction, or bootstrapped over scans. Decide how the weights rule
  treats a pattern whose σ is neither measured nor Poisson.
- [ ] **The design of the sum over specimens**:
  - y_k = Σ_v A_kv · f_k(p_v) + b_k, with A and the parallax shifts frozen
    per stage;
  - where A lives, and how voxel parameters compose with 1325's coordinates
    and basis (a voxel is a specimen with coordinates);
  - which `CompiledModel` state is per voxel and which is shared (the
    reflection list is shared per phase; windows are per voxel under
    parallax).
- [ ] **The solver**: matrix-free (J·v and Jᵀ·v from the traced backends, or
  analytic), with a regularisation penalty in the joint path and esds stated
  as conditional on its weight.
- [ ] **A device measurement at tomography size**: the batched forward on a
  CUDA machine against today's compiled CPU tier, quoted with both machines.
- [ ] **Data**: a public XRD-CT dataset with a licence that permits a test
  fixture, or synthetic only (say which).
- [ ] Tests: the phantom's truth recovered within esds by the direct route
  where reconstruct-then-fit is biased. obs/calc/diff PNGs to
  `tests/output/`.
- [ ] Skill: a routing row for "an XRD-CT dataset", or "none" and why.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_xrd_ct.py
.venv/bin/python -m ruff check src tests examples
```

## References

- Vamvakeros, A. et al. (2020). *J. Appl. Cryst.* 53, 1531-1541 — DLSR: a
  solution to the parallax artefact in X-ray diffraction computed tomography
  data.
- Wragg, D. S., O'Brien, M. G., Di Michiel, M. & Lønstad-Bleken, F. (2015).
  *J. Appl. Cryst.* 48, 1719-1728 — Rietveld analysis of computed tomography
  and its application to methanol to olefin reactor beds.
- Frølich, S. et al. (2016). *J. Appl. Cryst.* 49, 103-109 — diffraction
  tomography and Rietveld refinement of a hydroxyapatite bone phantom.
- Kamasak, M. E., Bouman, C. A., Morris, E. D. & Sauer, K. (2005). *IEEE
  Trans. Med. Imaging* 24, 636-650 — direct reconstruction of kinetic
  parameter images from dynamic PET data.
- Liebi, M. et al. (2015). *Nature* 527, 349-352 — nanostructure surveys of
  macroscopic specimens by small-angle scattering tensor tomography.
- `docs/milestones/v0.4.md` — the device measurements quoted above.

## Handover log

- **2026-10-14** — created by the WP-1325 session on the maintainer's
  decision to keep direct XRD-CT out of 1325 and file it as its own candidate.
  No open WP owns it: a grep of `docs/` for tomography, XRD-CT and voxel found
  nothing. The first task is the measurement.
