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
  kept differentiable; optional `[jax]` and `[torch]` (both v0.4) extras.
  Hard constraint discovered in research: **no Apple GPU supports fp64 in any
  framework** (MPS/MLX fp32-only; jax-metal abandoned), and JᵀJ squares the
  condition number ⇒ GPUs compute fp32 Jacobian columns only, fp64 host solve.
  - *Amendment (2026-07-24).* `[torch]` is pulled into **v0.4** as WP-0408.
    Because jax-metal is abandoned, Apple-GPU acceleration can only come
    through torch, and torch-MPS is also what validates the fp32-Jacobian-
    column policy (WP-0403) on real hardware instead of CPU simulation — the
    maintainer has no CUDA machine. The "one autodiff backend at a time"
    discipline is preserved by **sequencing rather than by milestone**: torch
    starts only once the jax path (WP-0402) and the cross-backend agreement
    CI (WP-0404) are green, so the second backend lands against an existing
    agreement harness. v0.6 keeps the solver and agent-surface work.
  - *Measured (2026-07-27, WP-0408 landed).* Both halves of that amendment
    came in, and only one of them came in the way it was expected to. The
    **fp32-column policy is confirmed on real hardware**: an MPS refinement of
    SRM 676a corundum, with the whole peak chain and every Jacobian column
    computed in fp32 on the GPU, lands 3.5×10⁻⁸ Å from the numpy fp64 cell and
    5×10⁻¹¹ in Rwp — the trust region re-measures each step against an fp64
    cost, so reduced columns perturb the path and not the answer, exactly as
    `backend/linalg64.py` argues. **Apple-GPU acceleration did not
    materialise**: MPS runs 60-125× *slower* than numpy
    (`examples/bench_torch_mps.py`). The cause is the loop shape, not the
    device — the residual evaluates ~130 frozen windows of 200-900 points one
    at a time in python, and MPS per-op cost is *flat* at 110-165 µs from 64 to
    65 536 elements, i.e. pure launch latency. It behaves like a GPU only at
    ~10⁶ elements per kernel (255 µs vs numpy's 1588 µs).
  - *Measured again (2026-07-27, after the above).* The obvious remedy was
    over-claimed on first writing and is corrected here. Batching the peak loop
    into one padded reflection × window tensor **does** collapse the dispatch
    cost — at fixed total work, 128×900 → 1×115 200 takes MPS from 10.6 ms to
    ~0.4 ms — **but it takes numpy from 1.36 ms to ~0.55 ms.** Sweeping one
    kernel across sizes locates the two numbers that settle every "should this
    run on the GPU" question here:
    - **break-even ≈ 50-65 k elements per kernel** (65 k → 0.99×, 131 k → 1.47×);
    - **the ceiling is ≈2.5-3×**, not an order of magnitude. The peak chain is
      ~17 flops per element, i.e. memory-bound, so a GPU's arithmetic throughput
      never participates (~10 G-element/s device vs ~3 G-element/s host, and
      about half of even that gap is fp32 moving half the bytes of fp64).
    Two consequences, both load-bearing:
    - **The batched peak loop is a numpy-path optimisation** (≈2.4×, no optional
      dependency, every user) that happens to also be a GPU precondition. It is
      scoped as a measure-then-decide spike in WP-0605, justified on that basis
      and not on device acceleration.
    - **The GPU case is a bigger problem, not a better backend** — and is worth
      ≈2.5-3× when it arrives. One batched kernel per pattern is 121 k elements
      (11-BM NAC), 38 k (lab corundum), 17 k (SRM 660c), so the plateau needs
      **≈10 synchrotron or ≈60 lab patterns processed together**: a `vmap`-batched
      in-situ/parametric series, which sits in the v2 fence below and is the
      honest place to revisit device acceleration. A single lab pattern is below
      break-even even after batching.
    `torch.compile` is not a way around this either: on CPU it is 2.5× *slower*
    than eager (13.5 vs 5.4 ms) after a 38 s compile, and on MPS it fails —
    dynamo specialises on each window's literal `(i0, i1)` bounds and hits its
    recompile limit trying to build one graph per reflection. The loop shape
    defeats compilation for the same reason it defeats the device. Until a
    batched loop exists, torch's value here is being an independent third
    opinion in the agreement matrix.
  - *Decided (2026-07-27, v0.4 sign-off).* Given the above, **`[torch]` is an
    experimental extra** (`backend.api.EXPERIMENTAL_BACKENDS`), never installed
    by default and never the recommendation for running a refinement. It is
    kept for two reasons that have nothing to do with speed: it is an
    independent opinion on the analytic Jacobian, and it is the only backend
    for which using the forward model as a differentiable *layer* is idiomatic
    — see "What the differentiable core unlocks" below. jax stays the vehicle
    for gradient-heavy CPU work: on the FCJ-heavy corundum state its Jacobian
    runs at 0.48× numpy against torch's 0.08×, a 6× gap on identical
    mathematics.
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

## Absorption: a correction that cannot improve the fit

Cylindrical (capillary) absorption, WP-0501, is worth recording as a design
case because it inverts the usual test for whether a correction is working.

**Convention first, by physics not letters.** The forward model multiplies by
the **transmission** coefficient A ≤ 1 (ITC Vol. C eq. 6.3.3.1). Most
tabulations print the **absorption correction** A\* = 1/A ≥ 1 (eq. 6.3.3.2)
instead. Both equal 1 at µR = 0, so an identity test cannot tell them apart —
only the *direction* of the θ-dependence can (A increases with 2θ, because the
mean path through a cylinder shortens toward backscatter).

**The correction is an exact reparameterisation.** Rouse et al. (1970) fit the
cylinder integral over 0 ≤ µR ≤ 1 with

    A(µR, θ) = exp{−(a₁ + b₁sin²θ)µR − (a₂ + b₂sin²θ)µR²} = K(µR)·exp(c(µR)·sin²θ)

which factors *exactly* into a constant times a Debye-Waller shape. So applying
it to a model with a free phase scale and free displacement parameters cannot
change the residual at all — Rwp is provably identical. Its entire physical
content is that a Biso refined without it comes back low by ΔB = c·λ²/2, which
is 0.13 Å² at µR = 0.5 and **0.49 Å² at µR = 1.0** for Cu Kα: comparable to Biso
itself, and 19σ against the esd the value is quoted with.

Three consequences, each of which shaped an interface:

- **µR is computed and held fixed, never refined.** It is not a
  strongly-correlated parameter; it is an *exactly singular direction* in the
  normal equations alongside the scale and Biso. `Geometry.mu_r` is therefore a
  plain float, not a `Parameter` — the type is the guard, and a test asserts it.
  The same argument fixes `packing_fraction`, which is exactly degenerate with
  µR in turn.
- **The result carries the bias, because no fit statistic can.**
  `RefinementResult.absorption` reports the applied µR and the equivalent ΔB. A
  user who only looked at Rwp would conclude the correction did nothing.
- **The acceptance test asserts equality of Rwp, not an improvement.** Written
  the obvious way — "the corrected fit should be better" — it would assert
  something the physics cannot deliver, and would fail for the right reason.

**Flat plate is fenced** for the mirror-image reason: reflection off a thick
specimen has A = 1/2µ (ITC Table 6.3.3.1(1a)) with no θ at all, so it is not
merely degenerate with the phase scale, it *is* the phase scale. Only the
finite-thickness and transmission cases carry a signature; they need a sample
thickness the schema does not have, and go to WP-0508.

**Validation lesson.** The coefficient b₂ is printed as "−0·0375" in the
available scan of Rouse when it is −0·3750. That error is invisible against a
constant-θ slice of the paper's own table — which constrains only a₁ and a₂ —
and is 0.08 wrong at µR = 1. It was caught by a quadrature of the exact ITC
integral, which shares no constant with any published fit. The general rule:
**a fit of two arguments must be validated across both**, and the strongest
anchor is the integral a fit approximates, not another code's transcription of
the same fit.

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
Backend drift → small op vocabulary + mandatory cross-backend tests, and
(2026-07-27) **one implementation instead of agreeing copies**: the row layout
in `model/rows.py`, the traced residual in `backend/traced.py`, and a
conformance suite driven by the backend registry rather than a hand-written
list, so a new backend inherits every rule and cannot ship without its
agreement rows.
**Scope (the biggest risk)** → strict per-milestone acceptance tests, one
backend at a time, a real v2 fence, and the validation suite doubling as the
recruiting hook for co-maintainers. Licensing → GPL never ported; provenance
documented in ATTRIBUTION.md. Performance → analytic columns (v0.2), jax jit
(v0.4); honest documentation that the numpy-FD path is the slow-but-correct
reference.

## What the differentiable core unlocks (deferred, not planned)

Recorded 2026-07-27, when v0.4 shipped, because the question "what is a
differentiable backend actually *for*, given it is slower?" deserves a written
answer rather than being re-derived each time. Nothing here is scheduled; each
item would need its own work package, and several sit behind the v2 fence.

**Start from the measurement that reframes it.** On a fully-freed lab state —
28 free parameters across every family — **0 fall back to finite differences**:
the analytic chain covers everything shipped. So for someone *running a
refinement today* the backends offer no accuracy or capability the numpy path
lacks, and cost 10-30× in Jacobian time (v0.4 record). Their present value is
to the maintainer: they are how the analytic Jacobian is validated, which is
why torch keeps a place after the GPU story collapsed. Everything below is
about what the *property* of being differentiable makes possible, not about
what the backends do now.

- **Gradients for physics nobody has hand-differentiated yet.** That "0 of 28"
  is a maintenance obligation, not a permanent state: every new parameter
  family (v0.5's absorption, surface roughness, Stephens strain, anomalous
  f′f″) either gets a hand-derived analytic column or drops to *forward*
  finite differences — measured at 6.2e-3 relative error on SRM 660c's cell `a`
  against 4.3e-5 for central differences, an error that lands in that
  parameter's esd. With autodiff, new physics is exact on day one and the
  analytic column becomes a later optimisation, validated against the autodiff
  one by the agreement matrix that already exists. That inverts the workflow
  from derive-then-ship to ship-then-optimise.
- **Honest uncertainties — the strongest candidate.** Today's esds are
  χ²·(JᵀJ)⁻¹ with a Bérar-Lelann inflation: Gaussian, symmetric, and purely
  local curvature at the minimum. A differentiable forward model supports
  gradient-based MCMC (NUTS via numpyro on jax, Pyro on torch) and therefore an
  actual posterior — asymmetric, correlation-aware, able to say a parameter is
  multimodal. For a package whose stated rule is *never return a confident
  wrong singleton*, that is the closest philosophical fit on this list, and it
  needs no GPU: jax on CPU is the vehicle.
- **Objectives other than weighted least squares.** The analytic chain is
  hardwired to r = √w·(y_obs − y_calc). Autodiff differentiates whatever is
  written: a true Poisson log-likelihood instead of the √max(y,1) Gaussian
  approximation the readers fall back on (which biases at low counts), Huber
  losses for detector spikes, explicit priors.
- **Exact second derivatives.** Gauss-Newton discards the second-order term; an
  exact Hessian gives true Newton steps and profile-likelihood intervals rather
  than quadratic ones — directly relevant to WP-0601's bounded LM.
- **torch specifically: the model as a layer.** Dropping the forward model into
  a torch training loop — learning a background or texture prior across many
  datasets, fitting instrument constants jointly with a neural component — is a
  real workflow, and torch is the only backend for which it is idiomatic. This
  is the argument that keeps `[torch]` alive as an **experimental** extra; it is
  not a performance argument.

**The costs, so the trade stays visible:** an optional ~500 MB dependency,
Jacobians ~10× slower than the analytic assembly, one more traced residual to
keep honest (now structural — `model/rows.py` owns the row layout and
`backend/traced.py` the traced twin, so a new backend inherits both), and the
torch-MPS trap collection in WP-0408's handover.

**And the two autodiff backends are not interchangeable.** jax's jit collapses
the dispatch overhead that dominates this problem: on the FCJ-heavy corundum
state its Jacobian runs at 0.48× numpy against torch's 0.08× — a **6× gap
between the two on identical mathematics** (measured, v0.4 record). For
gradient-heavy CPU work jax is the vehicle; torch's distinct argument is
ecosystem interop, not speed.
