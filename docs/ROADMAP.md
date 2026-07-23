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
4. **Milestone ships**: record the measured acceptance block in
   `milestones/vX.Y.md`, flip the milestone row here, and check the roadmap
   claims in README.md.

## Current focus

**v0.3** — WP-0301, WP-0302, WP-0303, WP-0304 and WP-0306 are done
(site-constraint machinery covers coordinates *and* aniso ADPs; QPA weight
fractions land off `RefinementResult.qpa`; Pawley whole-pattern mode). Next: any
⬜ WP with no unmet dependency — [0305](wp/0305-brindley-microabsorption.md) and
[0309](wp/0309-exporters.md) are now unblocked by 0304, alongside
[0307](wp/0307-march-dollase.md), [0308](wp/0308-multi-histogram.md).

## Milestones

| Milestone | Scope | Status | Acceptance |
|---|---|---|---|
| v0.1 | Vertical slice: synchrotron CW, Rietveld + Le Bail | ✅ **shipped** ([record](milestones/v0.1.md)) | 11-BM NAC: a = 10.251285(12) Å, Rwp 9.2%, CaF₂ impurity auto-flagged |
| v0.2 | Lab diffractometer + FitReport attribution + viz | ✅ **shipped 2026-07-22** ([record](milestones/v0.2.md)) | SRM 660c LaB6: a = 4.156895(25) Å (+28 ppm vs NIST value for this dataset, Bérar-Lelann-inflated esd), Rwp 8.7%; GSAS-II FAP tutorial: Rwp 9.73% vs GSAS's 10.05% on identical channels, cell +116 ppm (uniform d-scale convention offset) |
| v0.3 | Multi-phase QPA, Pawley, aniso ADPs, multi-histogram | ⬜ | SRM 676a / IUCr QPA round-robin fractions |
| v0.4 | JAX backend: autodiff Jacobians, CUDA, mixed precision | ⬜ | cross-backend Jacobian agreement CI |
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
| [0305](wp/0305-brindley-microabsorption.md) | Brindley microabsorption | ⬜ | 0304 |
| [0306](wp/0306-pawley-mode.md) | Pawley mode | ✅ 2026-07-23 | — |
| [0307](wp/0307-march-dollase.md) | March-Dollase preferred orientation | ⬜ | — |
| [0308](wp/0308-multi-histogram.md) | Multi-histogram stacked residuals | ⬜ | — |
| [0309](wp/0309-exporters.md) | Exporters: reflection table, CIF+esds (structure side landed in 0303), QPA table | ⬜ | 0304 |
| [0310](wp/0310-acceptance-srm676a-qpa.md) | Acceptance: SRM 676a + IUCr QPA round robin | ⬜ | 0304, 0305 |

### v0.4 — differentiable backend (stubs; expand before starting)

| WP | Title | Status | Depends on |
|---|---|---|---|
| [0401](wp/0401-backend-op-shim.md) | Backend op shim (~40 ops, scatter_add) | ⬜ | — |
| [0402](wp/0402-jax-backend.md) | JAX backend: chunked jacfwd | ⬜ | 0401 |
| [0403](wp/0403-cuda-mixed-precision.md) | CUDA + mixed-precision policy | ⬜ | 0402 |
| [0404](wp/0404-cross-backend-jacobian-ci.md) | Cross-backend Jacobian CI | ⬜ | 0402 |
| [0405](wp/0405-faddeeva-voigt.md) | True Voigt via shared Faddeeva w(z) | ⬜ | 0401 |
| [0406](wp/0406-restraint-penalty-rows.md) | Restraint penalty rows | ⬜ | — |

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
| [0603](wp/0603-torch-mps-backend.md) | torch backend (MPS fp32 forward) | ⬜ | 0401 |
| [0604](wp/0604-theory-manual.md) | Sphinx + MyST theory manual | ⬜ | — |

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
