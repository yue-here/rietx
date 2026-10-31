# rietx — Design record

Stable design rationale behind the architecture. Produced from a researched,
adversarially-reviewed plan (two review passes: a design critique and a
fact-check of load-bearing technical claims). Moved here from ROADMAP.md
2026-07-22 when the roadmap was split into per-work-package docs; milestone
tracking lives in [ROADMAP.md](ROADMAP.md), shipped acceptance records in
[milestones/](milestones/). This file changes rarely — read the specific
section a work package links, not the whole file.

## Why this package exists

**rietx exists so that a scientist can trust a Rietveld refinement they did not drive
by hand.** Trust is built four ways. Every result is checked against an independent
measurement where one exists, and where none does the method, its source and its code are
stated plainly. The package decides alone only where every competent refiner would
decide the same way; where the data can rank the alternatives it ranks them, and where
they cannot it reports the number and stops. Every action is recorded. The report says
what was refined, how well, and what to look at next, so an expert can audit and a
non-expert can learn to steer. The API follows current Python practice, and the whole
of powder diffraction is in scope.

*Written 2026-10-18. The founding statement of 2026-07 and what superseded it are in
§ History.*

## Rules

Four, each a consequence of the paragraph above. Milestones and rulebooks cite them by
number. A sentence that nobody would use to make a choice does not belong here.

1. **Decisions.** Ambiguity comes in three kinds, and the package answers each
   differently.
   - *The data settle it.* Every competent refiner, shown the number, would take the
     same action: the physics, the arithmetic, established practice. The package acts
     and records that it did. The absent-phase hold is the example.
   - *The data can rank it.* The hypotheses are enumerable and the data score them,
     though not always to one winner. The package enumerates, scores each with its
     evidence, and presents the ranking without picking. Indexing, extinction symbols,
     structure solution, a choice of peak shape. It picks in two cases only, and
     returns the whole ranking with the pick. In the first, the caller asked for a pick
     by calling a function made for it, such as `best_or_none`, and no default path
     calls one. In the second, the top candidate leads by a margin every competent
     refiner would accept, so taking it is an action of the first kind.
   - *The data cannot settle it.* The explanation depends on facts outside the pattern:
     sample history, a temperature ramp, a beam dump. The package reports the
     statistic with its meaning and stops, because only an agent told those facts can
     weigh them. A series discontinuity is the example.

   The gate on the first kind is unanimity: if a competent refiner who would act
   otherwise can be named, the action moves to the second or third kind. That line is
   drawn by the physics and by practice and does not move as agents improve. Every
   withheld verdict leaves its statistic. Where a rerun is expensive (an hour-long
   search, a 200-pattern batch, a write into a project's history) the package protects
   work already done: it keeps the best attempt, seeds no successor from a diverged
   fit, refuses to overwrite history, and records each. A fit costs seconds and an
   agent's reasoning costs tokens, so the right default reaches a correct answer in the
   fewest calls; a default that forces ten reruns to learn what one unanimous action
   would have shown costs more than the action. The provenance audit of every threshold
   (whose number is it: the physics', the literature's, or ours) is
   [milestones/generality.md](milestones/generality.md) § The rule.

2. **Verification and validation.** rietx is written by agents, so both are its
   foundation and not a check at the end. The words carry the field's meanings (Roache
   1998; Oberkampf & Roy 2010, chapters 2 and 10 to 13). A check compares a result with
   a *reference value*, and the kind of reference value decides which of the two the
   check is.

   *Verification* asks whether the code computes its model correctly, and it is the
   package's gate: a feature ships verified or does not ship. Its forms: an exact
   identity (a reparameterisation that provably cannot move the fit, a sum that must
   close); an analytic Jacobian against finite differences; a refactor that reproduces
   every number; two backends agreeing on one residual; and, weakest, two codes
   agreeing on the same data under the same protocol, or a published refinement of the
   same pattern reproduced under its protocol. The last is weakest because its
   reference value is a model's answer and can share the model's error. Under a
   different protocol it verifies nothing and measures only drift. In
   `tests/validation_matrix.py`'s tiers, `identity`, `own_result` and `cross_code`
   verify. `characterisation`, which records the shape of a known error or that a model
   is inadmissible, claims no accuracy and is neither. Every physics function cites its
   source.

   *Validation* asks whether the model matches the specimen, and its reference value is
   an *independent measurement*: a certified cell, a weighed composition (judged against
   the inter-laboratory spread of refinements), a composition from another probe. A
   prediction written down before the measurement validates only against an
   independent measurement; checked against the package's own arithmetic or another
   code, it verifies. So `certificate` and `spread` validate, and `prediction` validates
   where its reference value is an independent measurement. A validation result reports
   the mismatch in the quantity's own units, with the measurement's uncertainty and the
   fit's esd beside it, over a stated domain (the families, laboratories and instruments
   it was measured on), never only a pass; and it says whether the data is development
   data. Where no claim compares a topic with an independent measurement, the equation,
   its source and its code are stated plainly, and the topic is recorded *not yet
   validated* until one does. A result that reports a number from such a topic says so
   once in its report, naming each such number. That is the one place the fact reaches a
   reader of results (the writer is WP-2010's). That state is
   separate from *provisional*, which rietx keeps for an API that may still change (PEP
   411's sense). The validation record is for the developers. An agent or a user
   chooses a feature by the sample and the data, and whether the package has validated
   the feature should not move that choice. So the record is kept in the matrix and its
   generated page, and no surface an agent reads to choose a feature carries a
   validation verdict: `capabilities()`, the help entries, the agent skill and the GUI's
   help (ruled 2026-10-27).

   *A dataset is unused, sealed or development data.* Data that nobody who changes the
   package has run is unused. A family is sealed when its first run is on the tree as it
   stood when the work it judges began (a milestone's open, or the commit its acceptance
   row names), and nothing between then and the close is chosen or reworked on it by
   anyone who changes the package. Running it for another purpose, such as a benchmark
   whose results steer no change, leaves the seal intact. It is run again at the close,
   its mismatch against each reference value is reported for both runs, and it is then
   spent. Every other dataset that has been run is development data: data used to choose
   a threshold, a default or a plan, data a change was reworked on until a number came
   back, and data whose results the developers have seen (Oberkampf & Roy pp. 31-32, 44
   and 401). An independent measurement it carries calibrates as much as it validates. A
   test on it still measures, but weakly, and the record says so. Nothing goes from
   development data back to sealed. A pinned number that moves has moved for
   the right reason only if the new value is no further from its reference value than
   the old; that rule tunes the package toward the development data, and only the sealed
   families show whether the tuning generalises.

3. **Feedback teaches.** The report, each diagnostic's explanation and the manual bring
   a non-expert to competent steering, since steering is what the package leaves to
   them. The agent skill does the same for an agent: it makes the API and the feedback
   surface known accurately so the first call is right, and beyond that names only a
   trap or a practice with a source outside rietx's own runs. The vocabulary is
   generated from the live surface, the manual is reachable from inside the package,
   and the skill shrinks as models learn the package. A rule whose only evidence is a
   run on rietx's own test data is the code's overfit in prose form and is cut.

4. **Design tests.** One per kind of change, each with what passes. The mechanisms
   that enforce them are the project `CLAUDE.md` § Invariants.

   *A new output.* An agent can write the next call from it without a rerun. The
   statistic travels with any verdict, and an unmeasured value is `None`, never a
   default that reads as an answer.

   *A new default or automatic action.* Its kind of ambiguity is stated (Rule 1).
   Kind 1 names a dissenting competent refiner or says none exists, and records that
   it fired. Kind 2 ranks with evidence and picks only in Rule 1's two cases. Kind 3
   reports the number and stops. An Rwp comparison is never its evidence.

   *A new topic.* A test that verifies it lands with the code (Rule 2's gate). Where an
   independent measurement exists, it is named before the code is written: the dataset,
   the measured value with its uncertainty, and the mismatch the test will report. Where
   none exists, the topic is recorded not yet validated. Its equation is in the manual
   with its source, and its off state reproduces every earlier number.

   *A new API.* It takes the shape the surface already has: a verb in, a typed result
   out, a raise on failure, documented or deferred with a reason. The signature and
   docstring are enough for a first call to be right.

   *A new skill row.* It names a field, a verb, a code, or a trap or practice with a
   source outside rietx's own runs. Anything else is cut.

## Locked decisions

- **Backend**: numpy/scipy fp64 core (~50 MB default install); forward model
  kept differentiable; optional `[jax]` and `[torch]` (both v0.4) extras.
  Hard constraint discovered in research: **no Apple GPU supports fp64 in any
  framework** (MPS/MLX fp32-only; jax-metal abandoned), and JᵀJ squares the
  condition number ⇒ GPUs compute fp32 Jacobian columns only, fp64 host solve.
  - *Amendment (2026-07-24).* `[torch]` is pulled into **v0.4** as WP-0408.
    Because jax-metal is abandoned, Apple-GPU acceleration can only come
    through torch, and torch-MPS is also what verifies the fp32-Jacobian-
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
  - *Resolved (2026-07-28, WP-0605).* The spike ran and the answer is **no-go
    on the batched rewrite**: the ≈2.4× above was fixed-work at NAC's shape,
    and on the real states the FCJ node-padded plane is a **0.58× regression**
    (node counts 8-29 padded to the max — ~2.5× wasted elements), bucketing by
    node count recovers only 1.15×, and `derivative_bases` (2× the forward)
    would have to batch too. What survives, measured: symmetric-row batching is
    1.55-1.6× *and exactly bit-equal* (`examples/bench_batched_peak_loop.py`) —
    banked as the starting point for the v2 `vmap` series — and the production
    win came from removing redundant FCJ node generation instead (input-equality
    memo + axial-variant skip, 1.23× on SRM 660c, bit-identical).
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
  one autodiff backend at a time; FPA/neutron/TOF fenced in v2 (MCP was on
  that list until 2026-10-18, when the maintainer dropped it: a sandboxed
  python call costs an agent fewer tokens than a JSON round trip, measured);
  every milestone has a concrete measured acceptance test.
  - *GUI fence revised (2026-07-29).* "GUI/notebook widgets" was a v2+ line
    item, deliberately: this file's founding argument is that every existing
    Rietveld code is GUI-first with automation bolted on, and inverting that
    was the point. The inversion has paid off — and it also means the package
    is unusable by the audience it is for, with ~27 concrete API gaps behind
    any UI (no parameters-as-data, no `set_vary`/`set_value` on `Refinement`
    despite history reserving those NodeKinds since v0.2, no project
    container, no cancellation, `StageSpec`/`PlanSpec` existing twice in
    incompatible shapes). The **human GUI half is pulled into v1.0**
    (WP-1004…1017), before the API freeze (WP-1003), precisely so the GUI
    forces that API into existence and the freeze covers a surface a real
    consumer has exercised rather than one designed on paper. Notebook
    widgets stay fenced. This is a revision of the fence's *timing* on
    API-first grounds, not a retreat from API-first: the GUI is a view over
    the public API (every action echoes its API call), never a second
    implementation.
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
  - *FPA fence, literature on hand (2026-07-28 intake).* The papers-only route
    is now supplied and read: Cheary & Coelho 1992 (founding paper); Cheary &
    Coelho 1998 I, JAC 31, 851 (full axial model — incident-beam divergence
    β ≠ 0 puts the asymmetry minimum at 2θ ≈ 120°, which an FCJ-shaped β = 0
    model cannot express); Cheary, Coelho & Cline 2004, J. Res. NIST 109, 1
    (review: the five-Lorentzian CuKα table, tube tails, monochromator
    "learned spectrum", and a documented axial↔absorption profile correlation
    at 2θ = 50–100° — a canonical nested-fit case for the report's
    non-separability gate); Hölzer et al. 1997, Phys. Rev. A 56, 4554 (Kα/Kβ
    Lorentzian decompositions, on the wavelength scale this package already
    ships — the CuKα doublet in `schemas/instrument.py` and the Kβ ghost in
    `background/diagnostics.py` both match Hölzer Table IV byte-for-byte);
    Mendenhall, Mullen & Cline 2015, J. Res. NIST 120, 223 (FPAPC, the
    public-domain reference implementation — NIST↔TOPAS agree to 2 fm on
    SRM 660c/640e — since bundled into GSAS-II); Coelho 2018, JAC 51, 210
    (TOPAS architecture; its solver content routed to WP-0601 `## Inherited`).
    One correction to the note above: the "FPA→pseudo-Voigt term mapping
    (Mendenhall et al. 2022)" is properly **Denney, Mattei, Mendenhall, Cline,
    Khalifah & Toby (2022), JAC 55**, and its mechanism sharpens the cheap
    first step: generate synthetic FPA peaks from the *instrument geometry*
    (NIST code), fit the existing profile terms to them, and emit the same
    artifact `save_instrument_profile` already writes — a "calibrate from
    geometry" complement to `lab_calibrate`, whose FPA-vs-fitted difference
    curve doubles as the measured ceiling on what TCHZ can express for a
    given configuration. Two pieces are extractable without opening the
    fence: (a) **emission fine structure** — Hölzer's two Lorentzians per
    CuKα component plus the 2004 satellite row (the CuKa5 model); acceptance
    is that the summed profile's peak reproduces the shipped `_KA_DOUBLETS`
    wavelengths, and what it buys is physical attribution of the spectral
    width currently absorbed into fitted Lorentzian X at high angle.
    (b) **specimen-transparency profile aberration** (1992 eq. 14; 2004
    §4.4): breadth δ = sin2θ/(2µR), significant only for µ ≲ 100 cm⁻¹, and
    its finite-thickness form consumes exactly the µt/thickness the v0.5
    absorption seam already declares — per the v0.5 method result this
    ships as a diagnostic (predicted δ vs FWHM) first, not a correction.
    For any eventual convolution stack the numerical discipline is already
    written down: 1992 Fig. 1 shows histogram convolution biasing fitted 2θ
    with the internal step; Mendenhall's F₀ helper (singularities integrated
    exactly, area *and centroid* exact on the discrete grid) is the FPA
    analogue of frozen-per-stage discreteness; and even the reference codes
    carry a documented, unexplained position bias where asymmetry is worst
    (2015 Fig. 7b). Every derivative in this literature is a forward
    difference — a differentiable FPA is unclaimed territory, and the v0.4
    backends are the prerequisite. **Still fenced.**
  - *Magnetic fence revised (2026-09-02).* "Magnetic structures" was a v2+
    line item under the same neutron fence as TOF. Three things changed the
    grounds. CW neutron shipped in v1.1 (WP-1134), so the premise "neutron
    is fenced" no longer holds. The package now states the gap itself: three
    readers refuse a magnetic construct with one sentence, and the
    unexplained-intensity report names a magnetic contribution as a cause
    it cannot test. And the seams it needs exist: a per-site opt-in block
    (`Atom.aniso`, `Phase.microstrain`), a per-species table frozen at stage
    compile (`PhaseSites.f_anom`), a reflection list frozen per stage, the
    orbit average the dispersion path already takes, and the hold rule for a
    flat direction (WP-1301). An outside proposal (PR #221) asked; the
    track is ROADMAP § Unscheduled, WPs 1326–1329, with the two decisions
    the proposal left open taken in 1327. **What stays fenced**: the
    incommensurate case (superspace, with modulated structures), polarised
    neutrons, magnetic X-ray scattering, and TOF.
  - *Structure fence revised (2026-09-28).* Rigid bodies and Z-matrices
    (#195), structure solution from an indexed cell, and stacking faults were
    v2+ line items. The grounds changed with one run: `solution case 1` in
    the private corpus map, a collaborator's agent that took a lab pattern to
    a disordered, faulted structure in two days on rietx 1.4.0. It built each
    of the three for itself, and every one of them sat on a seam the package
    already has. Its annealing ran on `Refinement.predict()` at 20-35 ms an
    evaluation. Its ring shape went back in as `BondRestraint` rows across
    symmetry images, and its diffuse term as a tabulated additive curve.
    Where it wrote its own code, that code carried the defects the package
    already guards against: periodic images missed through every annealing
    stage, and a diffuse lock that breaks on a later release. It also did not
    use FOX or GSAS-II, having found an earlier FOX pipeline untrustworthy,
    so the host an agent picks is the package it is already driving. The
    track is ROADMAP § Unscheduled, WPs 1510-1517. Each of the three
    measured larger than one WP, so 1514-1516 each scope a milestone and the
    maintainer decides each draft. **What stays fenced**: maximum-entropy
    maps (#197), modulated structures and total scattering (#192).
    **Decided 2026-09-30:** difference Fourier (#197) and charge flipping
    (#198) leave the fence with direct-space solution, in the order map,
    direct space, charge flipping (milestone structure-solution, queued as v1.9).
  - *Texture fence revised (2026-10-14).* Spherical-harmonics texture (Von
    Dreele 1997) was a v2+ line item. Its cost is now on the record. A
    contributor's SRM 1976a sintered-alumina plate was rejected as an
    acceptance case for want of it (#131), an outside lab that relies on TOPAS
    names it as its other gap (WP-1325, 2026-10-13), and both the TOPAS and
    the GSAS-II readers drop the coefficients they meet. The seams it needs
    exist. It is a per-phase opt-in block over a reflection list frozen per
    stage, a multiplier linear in its coefficients with the identity at zero,
    the `LinearInequality` the Stephens cone already uses for positivity, and
    a basis derived from the operators as `stephens.py` and `adp_basis` derive
    theirs. GSAS-II runs in rietx-bench, so agreement with it is a
    measurement rather than a reading. The maintainer decided the move; the
    work is WP-1960, ROADMAP § Unscheduled. **What stays fenced**: an
    orientation distribution refined from several sample orientations, any
    sample symmetry below cylindrical, and odd orders.

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
Transforms: none since WP-1938 (2026-10-11). Every parameter refines in its
own units, with its declared `min`/`max` as box bounds the driver holds. v0.1
used softplus for widths and scales, because hard lower bounds stall TRF, and
logit for occupancies. Near zero a softplus column is expit(u)·∂r/∂p, which
falls below rounding: BT-1's `profile.x` esd read 0.0032, 0.0066 or 0.0089 at
one χ², and LaB₆ + cBN reached four minima from five starts 1e-14 apart. The
bounded LM below answers the stall instead, by putting a value exactly on its
bound. An old file's `transform` word folds into bounds at read.

**Rigid bodies: a typed `derived` block, not a linearisation inside C** *(measured
2026-10-01, WP-1803; issue #561).* A body atom's coordinates
x = o + M⁻¹·Exp(δω)·R₀·r are not affine in the rotation increment, and the table's one
affine block cannot carry them. Two seams were measured on a synthetic body. **Linearised
inside C** (x ≈ x₀ + M⁻¹[−R₀r]×·δω per stage, re-exponentiated at commit) keeps C constant
and every reader of C untouched, but the body is rigid only to θ²/2 inside a stage —
0.137 % (0.0019 Å on a 1.39 Å bond, 0.0026 Å on 1.90 Å) for a 3° step, 1.5 % (0.029 Å) at
10° — and one linearised stage leaves the committed body **4.4 σ** from the converged answer
at 3° and **22–43 σ** at 10°, so the stage has to be repeated until the increment vanishes
(4–5 passes, 16–21 TRF iterations, |δω| falling 3.0° → 0.025° → 2e‑7 rad → 3e‑11 rad), and
its esds are exact only on that closing zero‑increment pass (0.955–1.030 of the exact
chain rule after a 3° stage, 0.84–1.12 after 10°, within 5e‑9 of 1 at the closing pass). **The
exact map in `decode`** converges in one solve of 6–8 TRF iterations to the same body
(≤ 4e‑8 Å apart), commits a structure rigid to 1e‑15 Å, and needs **no new Jacobian
branch**: a body column takes `_peak_chain_column`, which differences θ *through*
`decode`, so the data‑row column is exact at every iteration (8e‑11 relative against the
whole‑model FD; `_STRUCTURAL_PATH` never matches a body path, `_structural_column` is
never entered). The derived block is therefore the seam, and "constant during a run"
narrows to the affine rows.

*What the block changes, and what it does not.* `decode` applies the blocks after the
affine matmul and is bit‑identical when none is declared. `stderr_physical` and
`physical_covariance` take the block's **local Jacobian at θ** for the derived rows — the
anchor rows in C are 2.3–2.9 % off after a 3° solve and 8–24 % after 10°, exact only at
δω = 0. The restraint block `(R_phys @ C)` takes the same Jacobian. The pattern readers
(`moving_paths`, `column_reach`, `entry_reach`, `unmeasured_rows`, `_column_extras`) read
a **declared** `reach_pattern()`, never the Jacobian's numbers: on the planar test body one
rotation column's numeric reach was 28 rows where its declared reach is 42, an
instantaneous zero that a freeze must not rest on. The traced twin applies the same map
after its dense matmul, in the `xp` ops WP‑1801 wrote. `commit` and `apply_to_models`
write derived rows from the map in the slot `_refresh_moment_components` holds. The
moment keeps its own rule ("no C row, no esd"); it is not migrated.

*The Cartesian frame.* `crystallography.adp.cartesian_basis` already *is* the TOPAS frame
(x ∥ a, y in the a–b plane, z ∥ a × b): the Cholesky factor with a positive diagonal is
unique, and the closed form
M = [[a, b cos γ, c cos β], [0, b sin γ, c (cos α − cos β cos γ)/sin γ], [0, 0, V/(a b sin γ)]]
agrees with it to 1.9e‑15 relative over 2000 random cells. The closed form, in `xp`
ops, is the frame the body map and the traced twin use; `cartesian_basis` keeps its
Cholesky and a test pins the two; its docstring's "no convention" disclaimer is retired.

*The cell is a live input to the map.* Measured with the cell free beside the body
(start 0.4 %/−0.3 %/0.2 % off): with M⁻¹ **frozen** per stage the committed body is
non‑rigid in the committed cell by 0.6 ε per bond (0.0073 Å at ε = 0.4 %), re‑placing it
at commit moves atoms by 0.013 Å and lifts the cost 1410 → 1737 at the stage boundary,
and one more stage (6 iterations, 0.16° of correction) is needed to recover; with M⁻¹
**live** the body is rigid throughout, the next stage is a zero‑increment pass (0.004°),
and the answer is the same (cell to 1e‑6 relative, orientation to 1e‑4°). Live is the
rule. Its consequences are declared, not discovered: the cell columns are in every body
row's `reach_pattern()`; a cell‑only stage and Le Bail move a body's *fractional*
coordinates while its geometry in Å stays fixed, which is what a rigid molecule in a
breathing cell does; and a hold is honoured on the body's own DOFs (origin, rotation),
never on a body atom's coordinate row, which the body owns as symmetry owns a special
position.
A hold or tie on the rotation must leave 0, 1 or all of a body's turn
directions free: two turns compose into the third, so two free directions are not
closed under composition and no re-chart maps them exactly (WP-1805, answered
2026-10-08, measured there).

*An anchored rotation composes.* R₀ ← Exp(δω)·R₀ and δω ← 0 at every commit; the record
is the absolute unit quaternion with w ≥ 0 (WP‑1801). The subtraction rule of
`rebase_anchored_dofs`/`reanchor_dofs` is wrong for a rotation by O(v²) — 0.0147°
orientation error and 0.125 % stretch at v = 3°, 0.34° and 1.4 % at 10° — so a rotation
DOF is never in `_anchored_dofs` and nothing rebases it. `displace_anchored_dofs` (the
series carry, WP‑1333) sets a body's increment from the record, δω = Log(R_target·R₀ᵀ)
and δo = o_target − o₀, exact; a series carries the quaternion and the origin, never the
increment.

*Ties a body refuses.* A body atom's coordinate row and DOF are locked and are refused as
tie targets by `Refinement.tie` today ("structurally fixed", "already follows … symmetry
outranks a user tie"). A derived row as a tie **source** is refused by the public verb
today but is flattened into `d` by `ParameterTable.set_tie` with no error (measured: the
dependent's C row empties, it leaves `moving_paths`); the table‑level refusal is added,
mirroring `apply_value_scale`. A body increment (δω, δo) as a source of anything that
does not reset with it is refused by name: measured, the dependent read 0.07 after the
commit and snapped back to 0.02 on the next build. A body DOF may follow another body DOF
of the same kind, since both reset together.

*Anti‑bump pairs are frozen per plan.* The candidate list is built once at plan compile
from pairs within r₀ + a margin, its rows exist for the whole plan (zero inside the
one‑sided term), and a plan‑end diagnostic names pairs that entered r₀ from outside the
list. A per‑stage rebuild would move the restraint row count that `rows.layout`,
WP‑1074's per‑stage c_w and the stage‑boundary Jacobian test assume constant. This is a
design judgement, not a measurement; what would change it is a plan that moves an atom
further than the margin, and the remedy then is a wider margin.

*Conditions of every figure above.* A synthetic C₆Br body (ideal D6h ring,
C–C 1.39 Å, C–Br 1.90 Å) in a triclinic P‑1 cell (7.21, 8.13, 9.47 Å, 84.3°,
97.6°, 104.2°), Cu Kα Bragg–Brentano, 2θ 8–70° (3100 points, 467 reflections),
Poisson noise, two seeds; origin, rotation increment and phase scale free;
numpy backend, one process. Iteration counts and every non-timing figure were
identical across four executions, the last on a fresh tree at `beb48147`. The
spike script is not merged (the WP's non-goal); timings are not quoted beyond
"one solve against four or five", since whole routes took 0.05–0.21 s with
±40 % noise between executions. Not measured: a many-atom body (the accuracy
of the one-sided FD through a long map), a body on a special position, and
restraints across a body under the live cell.

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

*Measured (2026-07-28, WP-0601 — `optimize/lm.py` + `optimize/bccg.py`,
selected with `solver="lm"`).* The bounded LM is **not** a speed play and did
not turn out to be one: 0.74-1.04× against TRF across the SRM 660c, 11-BM NAC
and round-robin corundum protocols, reaching an identical minimum on two of the
three and ΔBIC −13 on the third. That is what the arithmetic predicted — the
normal-equation solve is a minority of the runtime here (`derivative_bases`
costs ~2× the forward evaluation), so the Amdahl ceiling on solver work is
≈1.25×, and Coelho's own λ_new gains with a *full* A matrix are R_ν 0.96-1.19
(the 1.19-2.07 figures are all BFGS-approximated A, which this package has no
reason to use). **Its reason to exist is constraint vocabulary**: bounds
enforced inside the linear solve, and linear inequalities on *functionals* of θ
— the shape of the Stephens positivity cone σ²(M) = T·θ ≥ 0, unreachable for
`scipy.optimize.least_squares`, whose only vocabulary is a box. On round-robin
brucite that takes the fit from 12 of 43 reflections outside the cone to 0 of
43, at a *higher* Rwp. It does not make those coefficients measured — they stay
start-dependent across seeds — but an inadmissible answer stops being one of
the outcomes.

*Superseded in part (2026-10-11, WP-1938): the bounded LM is the default.* It
flipped together with the physical coordinates above, because each change
alone was worse than TRF in softplus coordinates. On WP-1937's grid of 14
acceptance fits, each started five ways 1e-14 apart, the fits whose χ²_red
spread passed 1e-9 numbered 3 under softplus + TRF, 7 under softplus + LM, 4
under physical + TRF and 1 under physical + LM. In softplus coordinates LM's
exact step drove widths to u ≈ −400, where their columns die. Since then the
step holds the linear inequalities inside its quadratic programme (Lawson and
Hanson's LSI → LDP → NNLS), rather than truncating a box step against them.
The Γ_G² ≥ 1e-8 floor at every reflection is the second inequality. TRF stays
selectable as `solver="trf"`.

Two properties of the driver are load-bearing rather than incidental, and any
future driver must keep both. The cost is always a **fresh fp64 residual
evaluation**, never an extrapolation from the same reduced-precision quantities
that built the columns — that is what lets a backend compute Jacobian columns
in fp32 and still land on the fp64 answer (WP-0403/0408). And θ is never
jittered between the residual and the Jacobian, so the FCJ node memo's
exact-input-equality hit survives (WP-0605).

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
(BSD-3) was carried as an optional `baselines` extra for its full algorithm
zoo; **that extra was deleted in v1.0** because nothing ever imported it —
arPLS and SNIP are implemented here from the papers, and an extra that no code
path reaches is a dependency a user installs for nothing.

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
  Le Bail-vs-Rietveld Rwp gap (structural-vs-profile triage). *(The
  low-frequency half landed 2026-08-12 as `FitReport.background` — WP-1055 —
  which pairs it with the block-absorption table, since the two background
  failure modes are opposite and neither statistic sees the other's.)*
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
+ a stdlib-http auto-refresh page (`rietx watch`) with a **console pane**
tailing the structured event stream — every line paired with its equivalent
API call, so the log doubles as a reproducible session script. Zero viz deps
in the base install; the FitReport itself is pure numpy.

*Amendment (2026-07-29, v1.0 GUI — stack decision).* The full human GUI is
un-fenced into v1.0 (WP-1004…1017; grounds under Locked decisions → scope
discipline). Stack: a **local web app** — `pip install rietx[gui]`,
`rietx gui` opens the browser. Server stays stdlib `http.server`
(the `compare_app.py`/`watch.py` precedent twice over: zero new deps, offline
and air-gap safe, and a single-user localhost app with ~25 routes gains
nothing from FastAPI/uvicorn); SSE on `ThreadingHTTPServer`; every verb a
plain method on a `GuiSession` with `server.py` as transport only, so a Tauri
shell can wrap it later. Frontend is real TypeScript (Svelte 5 + Vite — the
fine-grained-reactivity fit for a table of hundreds of independently-updating
parameter cells), but **built assets are committed and ship in the wheel** —
users never need node; `[gui]` = plotly only, served from the installed
package as compare already does. "Never Qt/wx in base" stands. The power-user
surface is a Profex-lineage synced text pane (`.rxt`, single server-side
parser, explicit apply). The `rietx watch` design above is unchanged — GUI
run events are teed to the same `live/` stream, so watch and the GUI are two
views of one stream.

*Amendment (2026-09-26, charts).* plotly is gone from every page. Each 2D
chart draws with one module, `viz/static/rxplot.mjs`, over a vendored uPlot
(WP-1461), and the structure viewer with its own WebGL2 renderer (WP-1462).
plotly's evaluation blocked every GUI open for 0.7-0.8 s, and the self-contained
HTML it wrote was 6.49 MB against the module's 1.23 MB on NAC, measured
before the exports joined the page. It is 1.36 MB with them. The `gui` extra
is empty and the `viz` extra is matplotlib alone. The measurements and the
decisions are in the two WP files.

## Absorption: a correction that cannot improve the fit

Cylindrical (capillary) absorption, WP-0501, is worth recording as a design
case because it inverts the usual test for whether a correction is working.
Its flat-plate siblings (WP-0508) then invert it back, which is why both are
recorded here together rather than as one rule.

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

**Flat plate, WP-0508: the same family, and every one of the four bullets above
comes out differently.** Reflection off a *thick* specimen has A = 1/2µ (ITC
Table 6.3.3.1(1a)) with no θ at all, so it is not merely degenerate with the
phase scale, it *is* the phase scale — that case stays unimplemented, and it is
what this package assumes whenever a flat specimen declares no thickness. The
two cases that do carry a signature are finite-thickness reflection (ITC (2))
and symmetric transmission (ITC (3a)), and they differ from the cylinder in
ways worth stating because they are counter-intuitive:

- **Not an exact reparameterisation.** ln A is not affine in sin²θ for either,
  so 1–40 % of the correction survives a free scale and a free Biso. Applying
  it *does* move Rwp, and the acceptance therefore asserts the opposite of the
  capillary one: on a genuinely thick specimen, declaring a thickness makes the
  fit **worse** (round-robin fluorite, µt = 0.5: Rwp 0.1793 → 0.1830), which is
  the correction correctly refusing a specimen that is not there.
- **Much larger, and the other sign.** ΔBiso reaches −1.5 Å² at µt = 0.2 over a
  Cu Kα range, an order of magnitude past the capillary's, and it is *negative*:
  a thin specimen runs out of material where the beam penetrates deepest, so the
  missing high-angle intensity reads as thermal motion.
- **The identity is µt = ∞, not µt = 0.** The reflection expression is
  normalised by its own thick limit, so "off" is an infinitely thick specimen
  and µt = 0 is a specimen of no thickness. That inverts the convention every
  other correction here follows, so it is enforced rather than documented: the
  schema refuses `mu_t = 0` under reflection and `CompiledModel.mu_t` is
  `None`-able rather than defaulting to `0.0`.
- **µt is still not refinable, but on weaker evidence, and the difference is
  recorded rather than smoothed over.** `mu_t_identifiable_fraction` measures a
  few per cent to tens of per cent surviving the {scale, Biso} projection —
  real, unlike µR's identical zero. It is held fixed on three grounds instead:
  µt is knowable from the specimen, a free one sits in the ill-conditioned
  {scale, Biso, background} corner, and what it would silently re-apportion is
  the ADPs the correction exists to protect. The measurement is pinned by a test
  so a future session revisiting the choice starts from numbers.

Transmission adds one thing the other geometries have no analogue for: its
unnormalised intensity peaks at **µt = 1**, so µt *is* the plate thickness in
units of the optimal one and `intensity_fraction_of_optimal = µt·e^(1−µt)` says
how many counts the specimen preparation cost. It is reported, never acted on —
a badly chosen thickness costs statistics, not accuracy.

**Verification lesson.** The coefficient b₂ is printed as "−0·0375" in the
available scan of Rouse when it is −0·3750. That error is invisible against a
constant-θ slice of the paper's own table — which constrains only a₁ and a₂ —
and is 0.08 wrong at µR = 1. It was caught by a quadrature of the exact ITC
integral, which shares no constant with any published fit. The general rule:
**a fit of two arguments must be checked across both**, and the strongest
anchor is the integral a fit approximates, not another code's transcription of
the same fit.

## Testing & validation policy

- Unit tests against published values (form factors, multiplicities,
  absences, TCH polynomials); hypothesis property tests (profile
  normalization, F symmetry invariance, Jacobian agreement incl. stage
  boundaries).
- FitReport verification by **synthetic misfit injection**: perturb exactly one
  known cause, assert the report recovers it, ranks it first, and reports
  *low confidence* in deliberately-collinear setups; calibration over the
  injection ensemble. Without this the confidence numbers are decorative.
- Absolute accuracy anchors to NIST certificates (with stated uncertainties);
  GSAS-II results are cross-code verification (Rule 2) with convention-aware
  tolerances.
- Real-data acceptance per milestone, committed in `tests/` and marked
  `slow`; provenance for every dataset in `tests/data/README.md`.

**The policy above is enumerated, per assertion, in
[VALIDATION.md](VALIDATION.md)** (WP-1001) — every acceptance bar in the tree
sorted by what it is *referenced to*, under a closed eight-name vocabulary.
Two things about that document are load-bearing. It is **generated** from
`tests/validation_matrix.py` and a fast test fails when the two drift, so it
cannot go stale the way the hand-maintained README table did (it claimed eight
suites while nine were committed). And the vocabulary needed **seven**
tiers where this section's prose implies three: alongside `certificate`,
`cross_code` and `spread` sit `identity` (referenced to floating-point
arithmetic, not to any physical quantity), `own_result`, and two that are
kinds of *evidence* rather than kinds of tolerance — `characterisation` (a row
asserting a model is inadmissible, or that a disagreement has a particular
shape) and `prediction` (a parameter-free claim written down before the
measurement). The last two exist because of the v0.5 method result: judged by
agreement indices alone, that milestone's eight corrections would score as
having delivered nothing.

**A test that pins a number declares its physics explicitly rather than
inheriting a default.** WP-1001 measured the cost of the alternative when
`Source.dispersion` became the package default: 21 tests moved at once, and
nine of them were bit-identity goldens with no opinion about dispersion —
they simply inherited it. The failures could not distinguish "this protocol
deliberately excludes the correction" from "nobody thought about it". This is
the protocol-adoption lesson one level up: a suite whose numbers move when a
default moves is not pinning a protocol.

**Learned in v0.2 — comparing against another code means adopting its
protocol, not just its numbers.** The fluorapatite acceptance was built by
reading GSAS's converged `FAP.EXP` refine flags and mirroring exactly what it
refined (zero held, displacement refined, GU/GV/GW held, sample LX/LY
refined, >130° excluded). Guessing a plausible protocol instead gave Rwp
16 % and a +390 ppm cell; the mirrored one gave 9.73 % against GSAS's
10.05 % on a channel count that matches its record exactly (5750). A
cross-code number computed over different channels with a different free set
is not a comparison.

**Where the suite runs, and what that can and cannot prove** (WP-1002; resized
by WP-1060; un-shaped at WP-1003's visibility flip). Per push and per PR
(`ci.yml`, the branch-protection required checks): ruff plus the fast suite
on 3.11 and 3.14 (3.12 and 3.13 nightly since WP-1547) and a `[dev,jax]`
fast job, Linux, no path filter — a
filtered job is a required check that never reports on a docs-only PR. A
**draft** PR runs ruff alone (the draft guard, `ci.yml`'s header): the claim
ritual opens a draft PR on a WP branch's first commit, so before it the whole
matrix fired on every intermediate push, 41 of the 71 runs over 30 WP branches
in the ritual's first two days and 12 of them over the claim commit's markdown
edit alone. Nightly (`nightly.yml`): the whole suite including `slow` acceptance under
`[dev,jax]` on Linux, the Windows fast suite backing the OS classifier row,
macOS fast plus the informational goldens step, and the `[torch]` agreement
rows.

**The budget was a design input while the repo was private** (superseded
2026-08-16, kept as the record of why the cadences had their pre-1.0 shape).
A private repo on the free plan gets 2000 Actions minutes a month, billed per
job rounded up to the whole minute, with a default $0 spending limit — so an
over-budget matrix does not produce a bill, it produces a month with no CI at
all. The first version of this one billed **21 minutes per push** (four
Pythons plus a jax job) plus a nightly full suite, which together left room
for about seventeen pushes a month — hence the per-push/weekly/monthly
tiering the flip undid. Totals are deliberately not written down here or in
the workflow comments — a written cross-workflow total rots (one sat at 303
against a measured ≈495); read spend from the Actions usage page or
`gh run list`.

One limit is stated rather than implied by a green badge. The Apple-GPU
(`torch-mps`) assertions **cannot** run on a hosted runner, which has no Metal
device, so the only real-hardware evidence for the fp32-column policy is
maintainer-machine-only. (A second — CI reporting rather than gating, since
branch protection needs a paid plan or a public repo — closed at WP-1003's
flip: `ci.yml`'s jobs are required checks on `main`.)

**A bit-identity gate is pinned to its capture environment, never loosened to
a tolerance.** The multi-platform matrix immediately measured what the goldens
are really pinned to, and it is not what the caveat in `tests/data/README.md`
guessed: a *numpy* change does not move them (2.4.6 and 2.5.1 agree
bit-for-bit), while Linux x86-64 diverges on every state — by 1 ulp on
quantities that are a single arithmetic chain and by ~1100 ulp (1.7e-13
relative) on `y_calc`, which accumulates ~130 windows of transcendental
evaluations. The gradient *with chain length* is what identifies the cause as a
different libm and summation order rather than different code. Relaxing
`np.array_equal` to a tolerance would have made the gate green everywhere and
meaningless everywhere: its entire content is "no refactor changed a single
computed number", and any tolerance wide enough to absorb a libm difference is
wide enough to absorb a real one. So it asserts on `darwin/arm64` and skips
elsewhere *with the measurement in the skip reason*.

Then the same matrix found the sharper version of that fact. A **hosted**
macOS/arm64 runner — same numpy 2.5.1, same scipy 1.18.0, same Accelerate as
the capture machine — reproduced 7 of 8 states and missed `toy_rich` by
*exactly one ulp* on a single element, while local runs at 1/2/4/8 BLAS threads
are bit-stable. So it is not reduction ordering; the residual variable is the
system math library the machine image ships, and nothing visible from Python
distinguishes one image from another. The pin is therefore to a *machine*, and
**no CI environment asserts these bits at all**: the nightly macOS job reports
the comparison and fails only if the goldens *skip*, because a skip and a pass
look identical in a summary line. That makes the gate maintainer-machine
evidence — the same shape as the Apple-GPU gap, and recorded the same way in
[VALIDATION.md](VALIDATION.md) rather than implied to be stronger than it is.

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
to the maintainer: they are how the analytic Jacobian is verified, which is
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
  analytic column becomes a later optimisation, verified against the autodiff
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

## History

Superseded choices, one line each, with where the measurement lives. Kept so that a
mistake is not made twice; the narrative stays in the WP file or milestone record named.

- **2026-07, founding statement.** Existing Rietveld codes (GSAS-II, FullProf, TOPAS,
  BGMN/Profex, RIETAN, MAUD) are GUI-first and every automation effort over them (MCP
  servers over GSAS-II, RPA over RIETAN, TOPAS `.inp` generation by LLMs) is a shim
  bolted on; TOPAS earned its standing through its minimizer and exact analytic
  derivatives by computer algebra (Coelho 2005, 2018); no differentiable, GPU-native,
  API-first open-source engine existed, and rietx would be one, with typed schemas, JSON
  round-trip, staged strategies and machine-readable diagnostics. Superseded 2026-10-18
  by § Why this package exists. What held: API-first, open, the typed model, staged
  strategies, machine-readable diagnostics. What aged: GPU execution (slower than numpy,
  § Locked decisions and the v0.4 record); differentiability as the selling point (a
  default install runs numpy with an analytic Jacobian and compiled kernels; jax and
  torch remain an independent check, WP-1115, WP-1940); the JSON surface (deleted at
  zero measured use, WP-1303).
- **2026-10-18, first north star.** "The package computes and the caller decides", with
  the unanimity test and the skill's role. Absorbed the same day into Rule 1 and Rule 3,
  after a review found it was a design rule in the purpose's slot (generality record
  § The fourth review, and this file's commit history).
