# pxrd-refine — Roadmap

Canonical milestone **index**. The content that used to live here is split so
a work session loads only what it needs:

- **[DESIGN.md](DESIGN.md)** — the design record (rationale, locked decisions,
  invariants). Stable; read the specific section a work package links.
- **[milestones/](milestones/)** — shipped-milestone records with the measured
  acceptance blocks (`v0.1.md`, `v0.2.md`, …).
- **[wp/](wp/)** — one self-contained **work package (WP)** per task. Each has
  its own context, commit-sized checklist, acceptance command, and handover
  log. `wp/TEMPLATE.md` defines the format.

## Session protocol

1. **Start** from "Current focus" below (or the WP the user names). Read that
   one WP file — it is self-contained on top of CLAUDE.md. Open DESIGN.md only
   at sections the WP links; do not read other WP files.
2. **During**: land tasks as small commits prefixed with the WP id
   (`WP-0301: …`); check items off in the WP file as they land.
3. **End** — or whenever interruption is a risk: append a dated entry to the
   WP's handover log (done / in flight / next / gotchas), update its Status
   line, and mirror the glyph in the WP index row below.
3b. **Push forward-references downstream.** If this session learned anything
   that changes work in a *not-yet-started* WP — a constant now exported for
   reuse, a design bullet there that has gone stale, a deferral into it, a
   gotcha that would mislead it — edit **that WP's `### Inherited` section**
   (see `wp/TEMPLATE.md`) and name this WP as the source. Step 1 forbids
   reading other WP files, so **a handover log is not a channel to anyone but
   your own successor on the same WP**: a "next WP should…" note left only in
   your own log, or only in "Current focus" below, will never be read. Current
   focus is a rolling narrative and gets rewritten when the next WP lands.
4. **Milestone ships**: record the measured acceptance block in
   `milestones/vX.Y.md`, flip the milestone row here, and check the roadmap
   claims in README.md.

*Step 3b was added 2026-07-24 and applied retroactively the same day: the
handover logs of all 14 then-landed WPs were swept for forward-references and
the results written into 16 downstream WPs' `### Inherited` sections. That
backlog is cleared — new sessions only need to keep up with their own.*

## Current focus

**v0.3 shipped 2026-07-24** — all ten WPs (0301–0310) landed and the full suite
is green (354 tests; 18 `slow` real-data acceptance). Measured acceptance
recorded in [milestones/v0.3.md](milestones/v0.3.md).

**Now: v0.4 — differentiable backends.** All eight WPs were expanded from
stubs on 2026-07-24 and are ready to start; no further planning is needed
before code.

The backend op shim [0401](wp/0401-backend-op-shim.md) **landed 2026-07-24**
(363 tests green, bit-identity goldens in `tests/test_backend_shim.py`): the
hot path speaks `xp.*` and the residual purity refactors (functional
intensity threading, unconditional off-value evaluation, `where`-masked
guards) are in.  The jax backend [0402](wp/0402-jax-backend.md) **landed
2026-07-24**: `backend="jax"` dispatches a scoped-x64, jit-compiled chunked
jacfwd Jacobian (numpy residual/solve untouched); jacfwd matches
analytic/FD on every family and SRM 660c end-to-end matches the numpy `a`
within 1e-6 Å.  The mixed-precision policy
[0403](wp/0403-cuda-mixed-precision.md) **landed 2026-07-24** (388 tests
green): `backend/linalg64.py` is now the single fp64 host boundary —
`MixedPrecisionPolicy` makes an fp32 residual or solve *unspellable*, and
`cast_columns` hooks in at `_jacobian_for`, the exit point every backend
shares.  SRM 660c under simulated fp32 columns moves `a` by 2.6e-11 Å and Rwp
by 1.1e-13; read that margin as proof of *plumbing*, not of device numerics
(the CPU round-trip captures fp32 representation loss only).  Next:
[0404](wp/0404-cross-backend-jacobian-ci.md) (agreement CI — import the bars
from `linalg64` rather than restating them, and note 0402's handover: the FCJ
S/L == H/L subgradient kink needs the same loose bar there) →
[0408](wp/0408-torch-mps-backend.md) (torch-MPS, pulled forward from v0.6;
starts only once 0402+0404 are green, and supplies the first real-hardware
measurement of 0403's policy).

Restraint penalty rows [0406](wp/0406-restraint-penalty-rows.md) **landed
2026-07-24**: bond/angle/value soft restraints as √w·(computed−target)/σ rows
below the data (in JᵀJ, out of Rwp/DW/Bérar-Lelann), with the analytic
nonlinear row-Jacobian chained through the affine constraint block, a
`RestraintReport` + `RESTRAINT_TENSION` diagnostic, and a 6th backend golden
(`toy_restraints`).  Rietveld- and single-histogram-only (multi-histogram
deferred — see WP-0308 `### Inherited`).

True Voigt [0405](wp/0405-faddeeva-voigt.md) **landed 2026-07-24**:
`Instrument.profile.shape="voigt"` selects an opt-in Gaussian⊗Lorentzian peak
built on one backend-agnostic Weideman-N=32 Faddeeva `w(z)` (no per-backend
`wofz`); TCHZ stays the default, the U,V,W,X,Y widths and FCJ are shared, and
numpy↔jax agree to 1e-16 on `w(z)`.

One backend-independent WP remains: [0407](wp/0407-esd-reconciliation.md)
(small — the reported per-parameter esds do not actually carry the
Bérar-Lelann inflation the docstrings claim, because the correlation matrix is
normalised by the inflated diagonal; the same bug leaves the high-correlation
guard dead).

## Milestones

| Milestone | Scope | Status | Acceptance |
|---|---|---|---|
| v0.1 | Vertical slice: synchrotron CW, Rietveld + Le Bail | ✅ **shipped** ([record](milestones/v0.1.md)) | 11-BM NAC: a = 10.251285(12) Å, Rwp 9.2%, CaF₂ impurity auto-flagged |
| v0.2 | Lab diffractometer + FitReport attribution + viz | ✅ **shipped 2026-07-22** ([record](milestones/v0.2.md)) | SRM 660c LaB6: a = 4.156895(25) Å (+28 ppm vs NIST value for this dataset, Bérar-Lelann-inflated esd), Rwp 8.7%; GSAS-II FAP tutorial: Rwp 9.73% vs GSAS's 10.05% on identical channels, cell +116 ppm (uniform d-scale convention offset) |
| v0.3 | Multi-phase QPA, Pawley, aniso ADPs, multi-histogram | ✅ **shipped 2026-07-24** ([record](milestones/v0.3.md)) | SRM 676a corundum: c/a +30 ppm vs certificate (absolute axes −313/−283 ppm, uniform d-scale); IUCr round robin: sample-1 worst 5.1 wt% (traces ≤1.3), sample 2 worst 2.9 wt% with brucite March-Dollase r=0.67, sample 4 characterised as the designed Brindley failure (µR fence fires) |
| v0.4 | Differentiable backends: JAX jacfwd, mixed precision, torch-MPS; true Voigt; restraints | ⬜ | cross-backend Jacobian agreement CI (analytic/FD/jacfwd/torch, incl. stage boundaries, Pawley/Le Bail, multi-histogram) + jit and MPS wall-clock vs numpy on 11-BM NAC (reported, not gated) + existing acceptance unchanged on the numpy path |
| v0.5 | Corrections & microstructure (absorption, Stephens, f′f″) | ⬜ | capillary/absorption vs GSAS-II consistency |
| v0.6 | TOPAS-style bounded LM, agent surface, torch-MPS | ⬜ | solver benchmark vs scipy TRF |
| v1.0 | Hardening, API freeze, PyPI | ⬜ | full validation matrix green |
| v2+ | FPA, neutron/TOF, texture, MCP server | ⬜ fenced | — |

## Work packages

### v0.3 — multi-phase workflows (detailed, ready to start)

| WP | Title | Status | Depends on |
|---|---|---|---|
| [0301](wp/0301-wyckoff-constraints.md) | Wyckoff/site-symmetry constraints (affine p = C·θ + d) | ✅ 2026-07-22 | — |
| [0302](wp/0302-atomic-coordinates.md) | Atomic-coordinate refinement | ✅ 2026-07-23 | 0301 |
| [0303](wp/0303-anisotropic-adps.md) | Anisotropic ADPs | ✅ 2026-07-23 | 0301 |
| [0304](wp/0304-qpa-hill-howard.md) | QPA: Hill-Howard ZMV mass fractions | ✅ 2026-07-23 | — |
| [0305](wp/0305-brindley-microabsorption.md) | Brindley microabsorption | ✅ 2026-07-23 | 0304 |
| [0306](wp/0306-pawley-mode.md) | Pawley mode | ✅ 2026-07-23 | — |
| [0307](wp/0307-march-dollase.md) | March-Dollase preferred orientation | ✅ 2026-07-23 | — |
| [0308](wp/0308-multi-histogram.md) | Multi-histogram stacked residuals | ✅ 2026-07-24 | — |
| [0309](wp/0309-exporters.md) | Exporters: reflection table, CIF+esds (structure side landed in 0303), QPA table | ✅ 2026-07-24 | 0304 |
| [0310](wp/0310-acceptance-srm676a-qpa.md) | Acceptance: SRM 676a + IUCr QPA round robin | ✅ 2026-07-24 | 0304, 0305 |

### v0.4 — differentiable backends (expanded 2026-07-24; ready to start)

| WP | Title | Status | Depends on |
|---|---|---|---|
| [0401](wp/0401-backend-op-shim.md) | Backend op shim (~41 ops, `window_add`) + residual purity refactors | ✅ 2026-07-24 | — |
| [0402](wp/0402-jax-backend.md) | JAX backend: chunked jacfwd | ✅ 2026-07-24 | 0401 |
| [0403](wp/0403-cuda-mixed-precision.md) | Mixed-precision policy (CUDA-deferred, CPU-testable) | ✅ 2026-07-24 | 0402 |
| [0404](wp/0404-cross-backend-jacobian-ci.md) | Cross-backend Jacobian CI | ⬜ | 0402 |
| [0405](wp/0405-faddeeva-voigt.md) | True Voigt via shared Faddeeva w(z) | ✅ 2026-07-24 | 0401 |
| [0406](wp/0406-restraint-penalty-rows.md) | Restraint penalty rows | ✅ 2026-07-24 | — |
| [0407](wp/0407-esd-reconciliation.md) | esd reconciliation (Bérar-Lelann placement) | ⬜ | — |
| [0408](wp/0408-torch-mps-backend.md) | torch backend (MPS fp32 forward) — moved from v0.6 | ⬜ | 0401, 0402, 0404 |

### v0.5 — corrections & microstructure (stubs)

| WP | Title | Status | Depends on |
|---|---|---|---|
| [0501](wp/0501-absorption-corrections.md) | Capillary + flat-plate absorption | ⬜ | — |
| [0502](wp/0502-surface-roughness.md) | Surface roughness | ⬜ | — |
| [0503](wp/0503-stephens-anisotropic-strain.md) | Stephens anisotropic strain | ⬜ | — |
| [0504](wp/0504-anomalous-scattering-xraydb.md) | Anomalous f′,f″ via xraydb | ⬜ | — |
| [0505](wp/0505-sequential-refinement.md) | SequentialRefinement warm start | ⬜ | — |
| [0506](wp/0506-secondary-extinction.md) | Secondary extinction (Sabine) | ✅ 2026-07-23 | — |
| [0507](wp/0507-anode-wavelengths.md) | Additional anode wavelengths (Co/Cr/Fe/Mo/Ag) | ⬜ | — |

### v0.6 — solver & agents (stubs)

| WP | Title | Status | Depends on |
|---|---|---|---|
| [0601](wp/0601-bounded-lm-solver.md) | TOPAS-style bounded LM | ⬜ | — |
| [0602](wp/0602-agent-json-surface.md) | Agent JSON surface hardened | ⬜ | — |
| [0604](wp/0604-theory-manual.md) | Sphinx + MyST theory manual | ⬜ | — |

(0603 — the torch/MPS backend — moved to v0.4 as
[0408](wp/0408-torch-mps-backend.md) on 2026-07-24.)

### v1.0 — hardening & release (stubs)

| WP | Title | Status | Depends on |
|---|---|---|---|
| [1001](wp/1001-validation-matrix.md) | Validation matrix + tolerance policy | ⬜ | — |
| [1002](wp/1002-ci-matrix.md) | CI matrix | ⬜ | — |
| [1003](wp/1003-api-freeze-pypi.md) | API freeze + PyPI | ⬜ | 1001, 1002 |

## v2+ (seams pre-built, implementations fenced out)

Fundamental Parameters Approach as a differentiable convolution stack
(Cheary-Coelho 1992); neutron CW; TOF (new Source/Profile implementations
behind the frozen seams); spherical-harmonics texture (Von Dreele 1997);
rigid bodies; MCP server wrapping `refine_json`; internal-standard/amorphous
QPA; `vmap`-batched in-situ series; GUI/notebook widgets.

No WP files for v2+ on purpose — the fence is a scope-discipline decision
([DESIGN.md](DESIGN.md#locked-decisions)), and pre-writing packages invites
scope creep.
