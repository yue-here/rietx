# pxrd-refine — Design record

Stable design rationale behind the architecture. Produced from a researched,
adversarially-reviewed plan (two review passes: a design critique and a
fact-check of load-bearing technical claims). Moved here from ROADMAP.md
2026-07-22 when the roadmap was split into per-work-package docs; milestone
tracking lives in [ROADMAP.md](ROADMAP.md), shipped acceptance records in
[milestones/](milestones/). This file changes rarely — read the specific
section a work package links, not the whole file.

## Why this package exists

Existing Rietveld codes (GSAS-II, FullProf, TOPAS, BGMN/Profex, RIETAN,
MAUD…) are GUI-first; every recent automation/agentic effort (MCP servers
over GSAS-II, RPA over RIETAN, TOPAS `.inp` generation by LLMs) is a shim
bolted onto them. TOPAS earned its industry-standard status largely through
its minimizer: full-matrix Newton + Marquardt damping + line search, a
bound-constrained conjugate-gradient normal-equation solver (Coelho 2005,
~84× faster than LU), and **exact analytic derivatives via computer algebra**
(Coelho 2018) — the closed-source analog of autodiff. As of mid-2026 no
differentiable/GPU-native, API-first open-source Rietveld engine existed.
pxrd-refine fills that gap: typed schemas, JSON round-trip, staged strategies,
and machine-readable diagnostics, with the forward model written to stay
differentiable from day one.

## Locked decisions

- **Backend**: numpy/scipy fp64 core (~50 MB default install); forward model
  kept differentiable; optional `[jax]` (v0.4) then `[torch]` (v0.6) extras.
  Hard constraint discovered in research: **no Apple GPU supports fp64 in any
  framework** (MPS/MLX fp32-only; jax-metal abandoned), and JᵀJ squares the
  condition number ⇒ GPUs compute fp32 Jacobian columns only, fp64 host solve.
- **Scope**: constant-wavelength X-ray powder first; `Source`/`Geometry`/
  profile/`IntensityModel` are the frozen extension seams for neutron/TOF/FPA.
- **License**: MIT. Port only from permissive sources (CrysPy MIT, cctbx
  BSD-style, Dans_Diffraction Apache-2.0, pymatgen MIT, lmfit BSD-3,
  pybaselines BSD-3, GSAS-II BSD-style — verify its LICENSE before any
  snippet reuse). **GPL codes (BGMN, Profex, xrayutilities) are studied
  conceptually only — never ported.** TOPAS/FullProf: papers only.
- **Scope discipline** (review finding: this is multi-person-year work):
  one autodiff backend at a time; MCP/FPA/neutron/TOF fenced in v2; every
  milestone has a concrete measured acceptance test.
  - *FPA fence, clarified (2026-07-23 cross-code review).* The single biggest
    scientific gap versus an empirical-Caglioti package is the
    **fundamental-parameters (FPA) peak shape** (Cheary & Coelho 1992): a
    convolution of physical instrument aberrations rather than fitted U V W X
    Y. It stays v2-fenced — a differentiable convolution stack is a milestone
    of its own — but two facts refine the rationale rather than reopen it.
    (a) The full FPA convolution is not the only route: the **NIST
    FPA→pseudo-Voigt term mapping (Mendenhall et al. 2022)** emits
    physically-derived pseudo-Voigt widths that drop straight into the
    *existing* TCHZ machinery, so if the fence ever opens the cheaper first
    step is a term-mapping layer, not a new profile. (b) BGMN's headline
    feature — decoupling a *per-device* instrument function from the
    sample — is **already paralleled** here at the Caglioti level by the
    `save_instrument_profile` / `load_instrument_profile` workflow
    (calibrate on a standard → freeze → refine the sample). So the fence
    costs us a physically-parameterised profile, not the instrument/sample
    separation itself. **Note only — do not un-fence.**

## Architecture invariants

(Also in CLAUDE.md — duplicated here because they are design decisions.)

1. **Frozen-per-stage discreteness.** hkl lists, symmetry-op subsets,
   FCJ quadrature nodes, and per-(line, reflection) window index ranges are
   computed at stage compile and never change during a least-squares run;
   regenerate only between stages. Freezing the hkl list alone is *not*
   enough — window membership depends on refined cell/zero parameters and
   creates gradient bias exactly on the parameters that matter most.
   FCJ detail learned in v0.2: freezing node *counts* is still not enough if
   fixed-fraction nodes sweep across the overlap-trapezoid kink at
   ξ = |S/L − H/L| as the axial parameters refine (O(h) steps in the
   derivative); the quadrature is therefore *split at the kink* into two
   Gauss-Legendre segments whose endpoints track the parameters smoothly.
2. **fp64 correctness boundary.** The residual used for cost/statistics and
   the parameter solve/covariance are always fp64 on host. GPU fp32 is
   restricted to Jacobian columns (relative-accuracy tolerant).
3. **No pydantic in the hot loop.** The tree compiles once per stage to
   static index maps; per-iteration decode is plain float/array work.
4. **Weighting.** File esd columns always win; Poisson √max(y,1) is a
   fallback with a diagnostic when data look normalized. Estimated
   backgrounds are held additively, never subtracted (keeps weights valid).
5. **Documented physics.** Every equation cites author/year/journal in its
   docstring; conventions documented by physics, not letters (size↔1/cosθ,
   strain↔tanθ; GSAS and FullProf swap the X/Y labels).

## Parameter system

lmfit-style `Parameter{value, vary, min, max, expr, transform}` on every
refinable scalar. Compile: tree → partition free/tied/fixed → flat fp64 θ.
Symmetry and linear ties are one affine map p_phys = C·θ + d (constant
matmul — exact under autodiff); v0.1 implements the identity-tie subset
(crystal-system cell constraints), v0.3 generalizes to Wyckoff constraints.
Nonlinear ties (`expr`) will use a tiny AST-whitelisted DSL emitted as
backend ops — **asteval and sympy were evaluated and rejected** (asteval
cannot run on autodiff tracers; sympy's torch lambdify printer is immature).
Transforms: identity + native TRF bounds by default; softplus for widths and
scales (hard lower bounds stall TRF); logit for occupancies.

## Minimizer strategy

v1 workhorse: `scipy.optimize.least_squares(method="trf")` — fp64, box
bounds, accepts our Jacobian callable. The Jacobian is assembled from exact
analytic columns where the model is linear (Chebyshev coefficients = design
matrix rows; Rietveld phase scales = phase component / scale) plus forward
differences for nonlinear parameters; v0.2 adds closed-form cell→2θ and
width columns (the dominant FD cost), v0.4 adds jacfwd. v0.6 adds the
TOPAS-style bounded LM as an alternative driver behind the same interface.
Esds from χ²_red·(JᵀJ)⁻¹ with pinv guarding singular normal matrices;
Bérar-Lelann inflation in v0.2. Guards: correlation threshold, bound hits,
divergence — surfaced as structured diagnostics.

## Background subsystem (automation-first)

Two-stage default: (1) diagnostics on the raw pattern → structured object an
agent can reason over; (2) robust estimate via arPLS (default) / iarPLS
(amorphous hump) / SNIP (dense patterns), λ auto-selected; then either hold
the estimate additively + small Chebyshev correction (v0.1 behavior) or —
the v0.2 default — co-refine a **penalized P-spline** whose 2nd-difference
smoothness penalty rides as extra residual rows: linear, differentiable,
esd-propagating, and physically unable to absorb broad Bragg intensity (the
documented nanocrystalline/QPA failure mode). Precedent: GSAS-II's 2024-25
auto-background wraps pybaselines' Whittaker methods into fixed points; we
make the penalized spline first-class in the least squares. pybaselines
(BSD-3) stays an optional extra for its full algorithm zoo.

## Outputs & fit assessment (the agent-native design)

Humans judge fits by looking — especially at peak-shape misfit — not by Rwp.
VLM benchmarks (CharXiv, ChartMuseum, ExChart) show frontier models fail
precise value extraction from dense plots, and one PNG costs ~1,000-1,600
tokens ≈ 50 regions of exact numbers. All three prior agentic Rietveld
systems (AgentBuild, Rongzai, guillemot) feed plot images to a VLM and all
report the same gap: locally-bad/globally-fine fits. Hence the FitReport,
three gated layers:

- **Layer 0 — model-free (always trustworthy, ships in v0.1).** All
  quantities w-weighted. Residual peak-finding; obs↔calc matching →
  `unmatched_obs` (impurity candidates) / `unmatched_calc`; cumulative-χ²
  breakpoints (David 2004); low-frequency vs sharp residual decomposition;
  Le Bail-vs-Rietveld Rwp gap (structural-vs-profile triage).
- **Layer 1 — gated linear attribution (v0.2).** Regions from the *union* of
  calc ticks and observed/residual peaks (segmentation must not be circular).
  Per region, a per-reflection shape-derivative basis {Ω, ∂Ω/∂pos, ∂Ω/∂width,
  ∂Ω/∂η, ∂Ω/∂asym} — built analytically from the profile, *not* the parameter
  Jacobian — fit as one joint weighted solve with the Gram covariance and
  condition number reported (the basis is non-orthogonal; independent
  dot-products cross-contaminate). Gates: local R², validity radius
  (~0.3-0.5 FWHM — a peak 5 FWHM off must trigger "re-detect, don't
  linearize", never a confident small-offset reading), overlap resolvability,
  and a global maturity gate that makes the report **abstain** from
  parameter-level output when the model is immature. Plus hkl-grouped
  intensity (Q-trend→ADP, element→occupancy, axis-angle→March-Dollase) and
  width (direction→Stephens) analyses that per-region views structurally miss.
- **Layer 2 — typed suggested actions, advisory only (v0.2).** Trend
  regression against constant/cosθ/secθ (zero/displacement/cell) and
  1/cosθ vs tanθ (size/strain) templates as nested model comparison with
  inter-template correlations — over narrow 2θ ranges these are collinear
  (Williamson-Hall separability), so ambiguity is reported, never a
  confident wrong singleton. Closed-enum versioned action schema; the
  **staged-strategy engine holds veto authority**; predict-then-verify with
  rollback; Hamilton/ΔBIC justification before adding parameters. Token
  *budget*: top-N regions verbatim + aggregate rollup; thresholds pinned and
  versioned in provenance for reproducible agent behavior.

Images are secondary evidence: `plot_for_vlm()` renders what VLMs *can* read
(annotated multi-panel montage, worst regions auto-zoomed from the report,
Δ/σ panel, high contrast, never JPEG).

Human GUI (bumps/refnx precedent, never Qt/wx in base): plotly Scattergl
self-contained HTML default; live monitoring by rewriting HTML/JSON per stage
+ a stdlib-http auto-refresh page (`pxrdref watch`) with a **console pane**
tailing the structured event stream — every line paired with its equivalent
API call, so the log doubles as a reproducible session script. Zero viz deps
in the base install; the FitReport itself is pure numpy.

## Testing & validation policy

- Unit tests against published values (form factors, multiplicities,
  absences, TCH polynomials); hypothesis property tests (profile
  normalization, F symmetry invariance, Jacobian agreement incl. stage
  boundaries).
- FitReport validation by **synthetic misfit injection**: perturb exactly one
  known cause, assert the report recovers it, ranks it first, and reports
  *low confidence* in deliberately-collinear setups; calibration over the
  injection ensemble. Without this the confidence numbers are decorative.
- Absolute accuracy anchors to NIST certificates (with stated uncertainties);
  GSAS-II results are consistency checks with convention-aware tolerances.
- Real-data acceptance per milestone, committed in `tests/` and marked
  `slow`; provenance for every dataset in `tests/data/README.md`.

**Learned in v0.2 — comparing against another code means adopting its
protocol, not just its numbers.** The fluorapatite acceptance was built by
reading GSAS's converged `FAP.EXP` refine flags and mirroring exactly what it
refined (zero held, displacement refined, GU/GV/GW held, sample LX/LY
refined, >130° excluded). Guessing a plausible protocol instead gave Rwp
16 % and a +390 ppm cell; the mirrored one gives 9.73 % against GSAS's
10.05 % on a channel count that matches its record exactly (5750). A
cross-code number computed over different channels with a different free set
is not a comparison.

**And a disagreement's *shape* is evidence.** The residual +116/+113 ppm cell
offset is the same relative amount on both axes — a uniform d-scale
(peak-position convention) difference, not a structural one. The test asserts
that uniformity explicitly, so the tolerance encodes a characterised
systematic rather than a shrug.

## Risks & mitigations

Ill-conditioning → staged strategy, guards, reparameterization, cond
reporting. Background eating peaks → penalized spline + correlation
guardrails. fp32 contamination → fp64 host residual/solve + agreement gate.
Backend drift → small op vocabulary + mandatory cross-backend tests.
**Scope (the biggest risk)** → strict per-milestone acceptance tests, one
backend at a time, a real v2 fence, and the validation suite doubling as the
recruiting hook for co-maintainers. Licensing → GPL never ported; provenance
documented in ATTRIBUTION.md. Performance → analytic columns (v0.2), jax jit
(v0.4); honest documentation that the numpy-FD path is the slow-but-correct
reference.
