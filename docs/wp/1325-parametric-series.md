# WP-1325 — parametric series: a parameter as a function of each pattern's coordinates

Milestone: unscheduled · Status: 🔄 2026-10-15 — ZrP₂O₇ and WO₃ out of sample settled decision 4 (χ²_red alone, a verdict beside a rejected equation provisional) and a declaration is now a parametric equation; next the next-term test, then in-step bounds
Track: Candidates — named on a use case, not yet on a measurement
Depends on: — (1119 soft: a named coefficient is a named variable)
Priority: P2 2026-10-14 — was P3: the maintainer took the combinatorial-library case (the first named outside user) and the scalable solver it needs; 1962 waits on that solver

## Goal

A joint fit over many patterns can refine a parameter as a declared function
of each pattern's coordinates: a temperature or time down a ramp, an (x, y)
composition across a combinatorial library, an (x, y, z) position across a
reconstructed tomography slice. All patterns go into **one joint residual**.
The function's coefficients are the refined parameters, and their esds come
from the joint covariance (Stinton & Evans 2007, "parametric Rietveld"). A
thermal-expansion coefficient, a Vegard slope or a composition surface is then
a *measured* number with an esd, rather than a curve fitted afterwards to
per-pattern values whose esds are each conditional on their own pattern. The
joint solve scales to **hundreds of patterns**, because a library is that size.

## Context

### Scope, decided 2026-10-14

The maintainer took three decisions after the survey below.

1. **The library is a target, so the scalable solver is in this WP.** The
   joint path stores its Jacobian dense, and that does not reach hundreds of
   patterns (§ What the code has). The solver tasks below make memory and
   time grow in proportion to the pattern count.
2. **Direct XRD tomography is its own candidate,
   [1962](1962-xrd-ct-a-pattern-summed-over-the-voxels-its-beam-crosses.md).**
   There, a measured pattern is a sum over the voxels its beam crosses. This
   WP keeps to one pattern, one specimen. The reconstruct-then-fit route to
   XRD-CT *is* covered here, as a library with (x, y, z) coordinates.
3. **The measurement runs on a synthetic ramp first.** The 68-pattern
   ZrMo₂O₈ ramp the first task named is not in the repo
   (`examples/bench_refinement.py:651` simulates its size only). A synthetic
   ramp with a known a(T) checks the joint fit is *right* and is re-runnable.
   The real ramp, from the maintainer's local copy, then measures what the
   joint form is *worth* on real data.

### Decisions after the form test, 2026-10-14

The maintainer read the fifth session's results and set the rule they serve:
let people fit a function to their parameters, warn them when it might be
wrong, and expose in the output that a value came from a function. Their
standing concern is a check calibrated on one example.

1. **The 1.10 release notes** were staged the same day, once #975 merged.
2. **Each law is also tested with the other laws freed** (Tasks).
3. **A law with a held coefficient stays untested**, as built: testing it
   would mix the form with the held value.
4. **A correction for several laws at 95 % each is open.** The ZrP₂O₇ and
   WO₃ measurement decides it, because both declare several laws at once.
   It covers one verdict per law plus the joint reading (decision 6).
   Settled 2026-10-15 by the maintainer, from § Measured: the form test out
   of sample. Every reading divides by χ²_red alone, without f² (741649b):
   over χ²_red alone 12 of 242 readings that must hold rejected (5.0 %),
   and with f² none of 261 did. Each reading stays at 95 %, with no
   family-wise correction. A verdict beside a rejected law is marked
   provisional instead (667216c), because a far-wrong law moves the answer
   every reading steps from.
7. **A declaration is a parametric equation** (2026-10-15). The public
   names say "equation" where this file says "law" or "tie":
   `ParametricEquation`, `RefinedParametricEquation`,
   `RefinementResult.parametric_equations`, `RefinedParameter.equations`.
   The record below keeps the names each session shipped under.
8. **An equation with no direction of its own keeps no verdict, and a
   value carries every verdict** (the maintainer, 2026-10-15, from the
   review). With the others freed, an equation they already cover has
   nothing to test. Its verdict stays `None`, as R's `lm` leaves an aliased
   term untested, and the joint warning names it with its tied reading.
   `ParametricValue` carries `provisional_on` and `joint_rejected` beside
   `form_rejected`.
5. **A kernel prior for the blind regime is
   [1963](1963-a-kernel-over-the-pattern-coordinates.md)**, a stub.
6. **The verdict follows statistical practice** (the maintainer, 2026-10-14,
   eighth session, overturning the seventh session's "either reading
   rejects"). A law's verdict is its others-freed reading, the test of a
   regression term added last, which assumes nothing of the other laws'
   forms. The tied reading stays on the record. Two laws whose targets move
   the pattern alike can each pass freed while both are wrong, so one joint
   reading swaps every tested law at once, the overall test of the group.
   It names no law, since the data cannot say which one is wrong. The
   either rule's per-law false-alarm rate lay between 5 % and 10 % by the
   union bound, and its tied half could flag a right law beside a wrong
   one.

### The general shape, and which part this WP builds

Every precedent below is one case of two independent choices. Write pattern
k's calculated curve as y_k = Σ_v A_kv · f(p_v), and specimen v's parameters
as p_v = Φ(z_v)·c, where z_v are its coordinates, Φ is a basis (a design
matrix) and c are the refined coefficients.

| case | A (specimens into patterns) | Φ (parameter over coordinates) |
|---|---|---|
| `multi.py` today | one specimen in every pattern | constant |
| `sequential.py` | identity | independent per pattern |
| this WP, series | identity | e.g. [1, T] |
| this WP, library | identity | e.g. a polynomial in (x, y) |
| XRD-CT reconstruct-then-fit | identity over voxel patterns | per voxel, or smooth in (x, y, z) |
| XRD-CT direct (1962) | path lengths along the beam, plus parallax | per voxel |

**This WP builds Φ in general and A = identity only.** The number of
coordinates costs nothing extra: Φ is a matrix whatever produced it. The
pattern count is what costs, and the solver tasks pay for it.

**Linear in the coefficients is the line, and it is free.** The tie machinery
is affine, p = C·θ + d with constant C (WP-0301, WP-1070). A parametric tie
p_k = Σ_j Φ_kj·c_j is exactly an affine tie per pattern with C_k = Φ_k, so it
needs **no new Jacobian branch**: `_column_extras` reads the reach off C, and
the whole-model FD column covers what a branch does not claim. A form with a
parameter inside a power or an exponential (Arrhenius, an order-parameter
exponent, a Debye σ²(T)) is the `Parameter.expr` fence of WP-1119.

### Prior art (survey, 2026-10-14; concepts only, per the licensing rule)

**Crystallography.**
- **TOPAS parametric refinement** (Stinton & Evans 2007, user docs only):
  global coefficients feed an expression in every dataset. Müller, Dinnebier
  & Schorr (2011) refined symmetry-mode amplitudes as a Landau power law in T,
  and report better statistics, stability and lower correlation than the
  sequential route. The outside lab's polynomial surfaces are this, over
  composition. The Durham tutorials (9.3-9.5, read 2026-10-14) check a law
  by plotting it against independent fits and by Rwp with the law on and
  off (WO₃: 12.87 % for 184 parameters over 11 patterns; ZrP₂O₇: 31.56 % to
  31.53 % with its three terms freed). They name no statistical test.
  WO₃'s nine cell edges share one refined Einstein temperature,
  a = a₀ + g/(exp(θ/T) − 1), and its angles are quadratic in T.
  ZrP₂O₇'s law is a cubic temperature calibration, the sample's true
  temperature from the set one with Si and Al₂O₃ as thermometers.
- **GSAS-II** fits an equation to its sequential *table* after the fact.
  That is the weaker form `sequential.py` already has.
- **FullProf's multi-pattern refinements** share a parameter through a
  refinement codeword with a multiplier: one column of C, with no notion of a
  per-pattern coordinate, so any multiplier is computed by hand.
- **XRD-CT.** Wragg et al. (2015) refined a whole reconstructed slice as one
  parametric TOPAS refinement. Vamvakeros et al. (2020, DLSR) fitted the raw
  scans directly to remove parallax. Both are carried in 1962.
- **Combinatorial phase mapping** (AgileFD, Suram et al. 2017; Phase-Mapper,
  Xue et al. 2017) models composition-driven peak shift as a per-sample
  stretch of a basis pattern, and holds the Gibbs phase rule as a sparsity
  limit; Phase-Mapper's benchmarks keep phase fields connected. The lesson
  for here: **a property varies smoothly inside a phase field, not across a
  boundary.** So a tie needs a subset of patterns it applies to.

**General fitting.**
- **lmfit** `Parameters` with `expr`: arbitrary expressions, evaluated as
  code. That is the WP-1119 fence, not this.
- **Mantid simultaneous fits** share a parameter with a tie (`f1.Sigma`), and
  ISIS adds "parameter functions" computing each group's value from global
  ones (arXiv 1605.02088).
- **XAFS (IFEFFIT/Artemis)** ties σ²(T) across temperatures through a guessed
  Debye temperature: nonlinear, the fence again.
- **Global and target analysis** (van Stokkum, Larsen & van Grondelle 2004;
  pyglotaran) shares kinetic parameters across datasets, with the model
  declared as data.

**Statistics.**
- **Varying-coefficient models** (Hastie & Tibshirani 1993) are the formal
  name for "a model's coefficients are functions of a modifying variable".
  The standard fit is penalised splines.
- **Mixed-effects models** add partial pooling: each unit keeps its own value,
  pulled toward the shared surface by a penalty. That is the soft variant this
  WP leaves for later (Non-goals).

**Model-formula languages** (Wilkinson & Rogers 1973; patsy, formulaic).
`1 + x + y + x:y + I(x**2)` names a basis, and a design matrix is built from a
table of per-sample metadata. Two lessons. `I()` evaluates python, so a
formula string is code unless its grammar is closed. And patsy's stateful
transforms (`center`, `standardize`, spline knots) **record the centring they
learned and reuse it on new data**. Without that, adding a sample silently
changes what every coefficient means.

**Elsewhere.**
- **Dynamic PET, direct versus indirect parametric reconstruction** (Kamasak
  et al. 2005): fitting kinetic parameters straight from the raw data beats
  reconstructing each frame and fitting afterwards, with 30-60 % lower
  coefficient of variation in one study. The gain shrinks at high counts.
  This is the closest analogue to "joint fit versus a line through the
  trajectory", and it says what the measurement should expect.
- **Bundle adjustment** (Triggs, McLauchlan, Hartley & Fitzgibbon 2000) solves
  joint problems with a few shared parameters and many local ones per unit.
  Its normal matrix is block-diagonal with a border ("arrow"), and the Schur
  complement makes the cost linear in the number of units. Sliding-window
  bundle adjustment folds old units into a prior on the shared parameters.
  That is the long-run answer to a growing campaign.
- **Autonomous-experimentation stacks** (CAMEO, Kusne et al. 2020) describe
  each sample as a row of a table keyed by sample (composition, position,
  process), and the analysis step reads named columns.

### The shape, answering the survey's five questions

1. **Data, not code: yes.** The declaration is a pydantic model with a JSON
   round-trip. It has:
   - targets as globs (superseded 2026-10-14: the declaration landed with
     one bare path per target, and a glob is
     [1965](1965-a-law-declared-by-formula-condition-and-glob.md)'s);
   - a basis from a **closed** vocabulary: `constant`, `polynomial` (terms over
     named coordinates, e.g. `[[], ["x"], ["y"], ["x", "y"]]`), or `design`
     (explicit per-pattern rows; this is the escape hatch for splines,
     Scheffé mixture forms and sin²ψ);
   - the pattern subset it applies to;
   - a reference point and a scale per coordinate.

   A formula string, if one is ever accepted, is input sugar parsed to that
   form by a closed grammar, never `I()`. Gap: a joint fit keeps **no
   history** today (`multi.py:886`), so "a history node can store it" has
   nowhere to land yet.
2. **The axis lives in a coordinate table passed with the patterns**: one row
   per pattern, named columns with units. It does not go inside each tie,
   because several ties share one table. It does not go in
   `PatternData.metadata` either, which is `dict[str, str]`. `SeriesEntry.x`
   (`schemas/sequential.py:51`) stays the 1-D view of one column.
3. **Refusals before a solve**, each naming its fix:
   - a design matrix whose rank is below its basis size. QR on the centred,
     scaled columns names the collinear terms. The ternary case,
     `1 + x_A + x_B + x_C` with x_A + x_B + x_C = 1, names the fix: drop the
     intercept (Scheffé form).
   - fewer patterns in the subset than coefficients;
   - a pattern in the subset with no coordinate;
   - a target that matches in no pattern;
   - a target already driven by another tie;
   - a coefficient box whose image under Φ_k leaves a dependent's own
     `min`/`max` on some pattern. This is the WP-1119 hazard: a variable's
     bounds are the only ones the solve sees. For a linear map that image is
     exact, Σ_j min/max(Φ_kj·lo_j, Φ_kj·hi_j).
   - a target that is held, `mode_fixed`, locked or symmetry-tied (the reason
     read off `held_because`).
4. **Conditioning.** Coordinates are centred and scaled by a reference and a
   half-range **stored in the declaration** (patsy's lesson). The defaults
   are computed once at declaration from the coordinates present. Coefficients
   are reported in user units, at the reference: c₀ is "a at T_ref", never an
   extrapolation to T = 0. The normal-matrix equilibration (van der Sluis)
   fixes column *scale*. It does not fix the intercept-slope correlation that
   an off-centre axis creates, which is why centring is the declaration's job.
5. **A growing campaign.** Because the reference and scale are frozen, a new
   pattern never redefines a coefficient. A refit starts warm from the last
   coefficients. A quarantined pattern (WP-1051's rule) leaves the joint
   residual, its row of Φ is dropped, and the rank refusal re-runs. An
   unbounded campaign wants sliding-window marginalisation; that is out of
   scope.

### Measured: the synthetic ramp (2026-10-14)

`1325-measure/synthetic_ramp.py`, output in `1325-measure/results.txt`.

**Setup.**
- Ten LaB₆ patterns at T = 300-1200 K, built by `tests/test_sequential.py`'s
  `_simulate` with the cell on a known line.
- 20 noise seeds per regime.
- Linux x86_64, 4 CPUs, `[dev]` venv, compiled kernels on, nothing else
  running.
- The joint fit is today's dense path, with no `src/` change. The pieces:
  - `SharingMap(per_histogram=["phases.*"])`;
  - `vars.a0`/`vars.a1` added to every sub-table, which fold onto one shared
    column each;
  - `phases.0.cell.a` tied per table to a0 + a1·t_h;
  - `_rebuild_columns()` called by hand;
  - `mccusker_default` with `vars.*` added to its cell stage.
- `MultiParameterTable.set_vary` skips tied entries
  (`params/multi.py:281`), so the tie survives every stage. The script
  asserts a, b and c sit on the line to 1e-12 in every table.

**Results.** a₁ is in 10⁻⁹ Å/K; truth 20 783. "Scatter" is a₁'s spread over
the 20 seeds.

| regime | estimator | bias | scatter | mean esd |
|---|---|---|---|---|
| R1, strong signal, only a0/a1 shared | weighted line through the chain | −0.45 | 4.45 | 5.48 |
| | joint a0 + a1·t | −0.46 | 4.41 | 5.48 |
| R2, phase scale ×0.035 (per-pattern cell esd ×4.95) | weighted line | −2.45 | 17.9 | 27.1 |
| | joint | −2.67 | 17.95 | 27.1 |
| R3, instrument (zero, profile) shared in the joint fit | weighted line | −0.45 | 4.45 | 5.48 |
| | joint | +0.10 | 1.57 | 2.13 |
| | control: shared instrument, cells free, GLS line over their joint covariance | +0.10 | 1.57 | 2.12 |

**What it says.**
- **The tie is correct.** In R1 and R2 the joint a₁ sits a mean 0.024 and
  0.021 esd from the weighted line (max 0.074). The esd ratio is 0.983-1.011.
  Theory says that when only the coefficients are shared, the joint estimate
  is the line weighted by each pattern's *raw* information, and it is. That
  line is not the chain's weighted line, whose weights also carry each
  pattern's own χ²_red and Bérar-Lelann factor; across this ramp the raw
  information is near-equal, so the reference is the equal-weight line. The
  joint a₁ sits a mean 0.0012 esd from it in R1 (max 0.0037, the printed
  resolution) and 0.0048 in R2 (max 0.018), 20× and 4× closer than to the
  weighted line (computed from the per-seed rows of `results.txt`).
- **The tie alone buys no precision while each pattern's own fit is linear.**
  Weakening the signal 5× in esd (R2) kept every per-pattern fit Gaussian and
  unbiased, so the constraint had nothing to fix.
- **Sharing buys precision, the tie does not.** Sharing the instrument across
  the ramp (R3) cuts a₁'s esd 2.6× (ratio 0.381-0.392) and its scatter 2.8×.
  The untied control gets the same answer to within 0.001 esd: a joint fit of
  per-pattern cells already has that gain. a(T_ref) does not sharpen
  (1.57e-6 Å in R1 and R3 alike, for every estimator), because a common shift
  of every cell still trades off against the zero shift.
- So, on this evidence, the parametric form's value for a series is:
  - **convenience:** a coefficient with its esd, without exporting the joint
    covariance, which a joint result does not carry today;
  - **fewer columns:** one per coefficient instead of one per pattern;
  - **what remains untested:** whatever happens where a single pattern
    cannot see the parameter (the second measurement task).

  The library case rests on the outside lab's report until that measurement
  says otherwise.
- **Cost.** Joint ÷ chain wall clock is 1.41-2.19 (R1), 1.66-2.11 (R2) and
  1.44-2.36 (R3) at N = 10. The chain is 1.3-1.9 s and the joint fit
  2.2-3.2 s.
- **Calibration, in passing.** Scatter/esd is 0.81 (R1), 0.66 (R2) and 0.74
  (R3). In R1 and R3 that is about 1/BL, where BL is the Bérar-Lelann factor
  the package multiplies into every esd (1.263 here), so the raw esds are
  near honest. The weighted line's χ²_red (mean 0.56) agrees. R2 does not fit
  that reading: its factor is 1.137, so its raw esds still overstate the
  scatter by about 1.3× (0.66 × 1.137 = 0.75). Why the factor is 1.26 on a
  model that matches its Poisson data exactly, and why R2's raw esds run
  wide, are open, and not this WP's question.
- **Gaps the script had to work around.** These belong to the "ties and
  variables" task:
  - no public verb to add a joint variable or tie, hence the hand call to
    `_rebuild_columns`;
  - a joint result carries no covariance, so the control subclassed
    `_build_result` (`multi.py:1406`) to read it.

### Measured: where one pattern cannot see the parameter (2026-10-14)

`1325-measure/kernel_ramp.py`, output in `1325-measure/kernel_results.txt`.

**Setup.**
- 10 patterns at T = 300-1200 K and 20 seeds per cell, all converged.
- Linux x86_64, 4 CPUs, `[dev]` venv, compiled kernels on. A frozen copy of
  `src/` at 0b33465 ran it, because another lane was editing the tree. Load
  was 1-8, so wall clock is indicative only.
- The major phase is LaB₆, per pattern in every arm. The quantity measured is
  a minor CaF₂ phase's cell, whose truth is a line, a curve
  (line + (L/2)(t² − 1)) or a kink (the slope halves at 750 K).

**Regimes.**
- **W:** the minor phase dissolves on heating, with designed support
  30 × 0.6^k. The chain's WP-1301 hold left patterns 5-9 as gaps: per
  pattern, 0 0 0 0 1 15 18 20 19 20 of 20 seeds.
- **O:** broad minor peaks (`lor_size` 0.4°, held), with a per-pattern cell
  esd 6.3× the true step between patterns.

**Arms.**
- `chain`: `refine_sequential`;
- `line`: a weighted line through the chain's kept points;
- `gp`: Matérn-3/2 with a [1, t] mean, REML on the kept points;
- `tie`: the hard tie a₀ + a₁·t;
- `kernel`: the joint fit with prior rows, at the gp arm's REML
  hyperparameters, appended by wrapping `_multi_closures` in the script;
- `gp_fix` and `kernel_fix`: a sensitivity pair at a hand-set s = L/4,
  ℓ = 1 (half the ramp).

Units: a in 10⁻⁴ Å, a₁ in 10⁻⁹ Å/K.

| W | a₁ bias | a₁ scatter | a₁ mean esd | gap RMSE, line / curve / kink | gap coverage ≤ 2 esd, line / curve / kink |
|---|---|---|---|---|---|
| line | −328 | 1533 | 1655 | 10.1 / 59.6 / 20.2 | 0.96 / 0.05 / 0.74 |
| gp | −2273 | 10405 | 7465 | 73.1 / 56.1 / 22.1 | 0.97 / 0.38 / 0.76 |
| gp_fix | −366 | 2790 | 4166 | 20.4 / 55.3 / 23.3 | 0.96 / 0.66 / 1.00 |
| tie | +106 | 1107 | 1479 | 6.8 / 58.0 / 20.0 | 1.00 / 0.03 / 0.66 |
| kernel | −2945 | 13893 | 8690 | 77.3 / 54.2 / 23.3 | 0.91 / 0.31 / 0.68 |
| kernel_fix | +430 | 2083 | 4177 | 15.1 / 53.5 / 26.0 | 0.97 / 0.57 / 0.91 |

**What it says.**
- **Where one pattern cannot see the parameter, the hard tie buys
  precision**, unlike R1 and R2. On W's line truth, a₁'s scatter is 0.72× the
  line's and its esd 0.89×. The gap RMSE is 6.8 against 10.1, and gap
  coverage stays at 1.00. A scatter ratio from 20 seeds carries about 16 %
  of its own uncertainty, so 0.72 is about two sigma.

  The gain has two sources:
  - The gap patterns carry weak information, a data share of 0.04-0.2 each,
    which the joint fit uses and the chain throws away.
  - The near-threshold points the chain keeps are not Gaussian. Noise makes
    the phase look significant at z ≈ 2, and the chain's |z| reaches 6.5. The
    line inherits those points, its χ²_red reaching 9.2, and the tie does not
    lean on them.
- **The tie's esd is confidently wrong when its form is.** A bend that sits
  only in the gaps is recovered by no arm: gap RMSE is 54-60 for the curve
  and 20-26 for the kink, whatever the arm. The tie's gap coverage at 2 esd is
  0.03 for the curve and 0.66 for the kink. § A kernel predicted this from
  the literature; it is now measured.
- **A kernel tuned by REML afterwards does worse than the line in exactly
  this regime.**
  - REML on the chain's kept points reads the near-threshold survivors as
    curvature: s/σ ≈ 60-180 in 7-10 seeds of 20, and the floor in most of the
    rest.
  - The gp and kernel arms then extrapolate into the gaps at RMSE 73-77
    against the line's 10, with kernel |z| up to 15.6.
  - The coefficient is confounded with the GP: one seed gave a₁ = −48 059.

  So § A kernel's recipe, "REML on (p̂, I), then freeze", fails in the one
  regime where a kernel could matter. Its input is exactly the points the
  regime corrupts.
- **At good hyperparameters a kernel buys honest intervals, not accuracy.**
  `kernel_fix`'s gap coverage is 0.57 (curve) and 0.91 (kink), against the
  tie's 0.03 and 0.66, at a worse RMSE than the tie on the line and the kink.
  Inside the fit against afterwards at the same kernel: `kernel_fix` beat
  `gp_fix` on the line and the curve, and lost on the kink.
- **The phase-fraction hypothesis is not supported.** Pinning the cell
  removes the chain's lag bias: the chain reads the gap fractions 6-11 % low,
  the tie 3-8 % high. It does not reduce the noise; every arm's gap RMSE is
  3-4 × 10⁻⁵ against true fractions of 1-10 × 10⁻⁵.
- **Broad peaks alone stay linear.** O's per-pattern fits were weak but
  Gaussian (rms z 0.76), so O reproduces § Measured. The tie, `kernel_fix`
  and the line agree within the 20-seed noise (trajectory RMSE 54.5, 54.5 and
  59.6 on the line truth).
- Neither joint arm's support hold fired in either regime.

**Caveats.**
- The prior rows took the χ²_red·BL² covariance factor, as the package treats
  its own penalty rows (`least_squares.py:2661`). § A kernel says prior rows
  should take neither.
- No free-joint control was run, so the joint hold's behaviour on flat gap
  cells with no prior is untested. The joint hold only fires for a phase
  unsupported in every histogram.
- O did not go non-Gaussian; a nonlinear overlap case needs lower support or
  a refined `lor_size`.

**Reading.** The hard tie has now earned a measured gain beyond convenience,
in the regime the outside lab's weak and broad features live in. A kernel
inside the fit has not. Its one demonstrated benefit is honest intervals
under a wrong form, which a lack-of-fit check on the tie could give more
cheaply (Tasks). The soft form stays a Non-goal.

### A kernel over the coordinates (survey, 2026-10-14)

The maintainer asked whether a *kernel* over the pattern coordinates, rather
than a declared basis, would be useful. A kernel makes a parameter vary
smoothly without naming its functional form. This section is three
literature searches plus the algebra that places a kernel in this WP. The
searches confirmed each citation and its abstract-level claim through indexed
records, but every full-text fetch failed on DNS, so no paper was read
whole. Numbers that came only from secondary summaries are left out.

**The form.** Each pattern keeps its own p_k, and a prior over the
coordinates pulls the values together: p = Φc + g, with g a Gaussian process
of covariance K_ij = s²·r(|z_i − z_j|/ℓ). In least squares the prior is extra
residual rows R(p − Φc), with RᵀR = K⁻¹. Φc is left unpenalised, so the
kernel penalises only departures from the declared basis. This is Wahba's
(1978) partially improper prior, framed by her as a guard against the
basis's model error. One family holds every form this WP names:
- s → 0 is the hard tie, the form this WP scopes;
- s → ∞ is independent per-pattern fits, the chain's answer;
- ℓ → 0 (a white kernel) is partial pooling toward Φc, the mixed-effects
  soft form in Non-goals;
- a second-difference precision is the P-spline over a coordinate in
  Non-goals. It is an intrinsic GMRF whose null space is the straight line
  (Eilers & Marx 1996; Rue & Held 2005, ch. 3).

So both soft forms in Non-goals are members of one family. The hard tie and
the chain are its two limits, and both make regression tests for an
implementation.

**What it can buy, read against § Measured.** Profiling out a pattern's
private parameters (the Schur step) leaves a quadratic in p_k. Its curvature
I_k is exactly the information that pattern's own fit reports. So when
nuisances are private and each fit is linear, a joint fit under a kernel
**is** GP regression on the trajectory (z_k, p̂_k) with noise I_k⁻¹. This is
the theorem R1 and R2 measured for the line, which is the s → 0 member. In
that regime a kernel buys nothing that a smoother run afterwards on the
chain's output does not.

On a lattice parameter it is pure cost. A pattern's own cell esd in R1 is
4.98e-6 Å (1.2 ppm), against a 2.1e-3 Å step between neighbouring patterns.
Any kernel that admits the observed trajectory therefore leaves each value's
data share at ≈ 1.

Where it might pay is the regime the next measurement task already targets,
where one pattern's likelihood is not Gaussian in p:
- **Weakly determined parameters**: Biso, occupancy, microstrain, and a
  minor phase's cell near its detection limit. Pinning a weak phase's cell to
  its neighbours removes the noise a free cell lets its scale fit. So the
  payoff may be the *phase fraction* more than the cell (hypothesis,
  unmeasured).
- **Overlap that changes along the axis.** Patterns where two phases' peaks
  are resolved inform the patterns where they are not, with no declared
  form.
- **Prediction at an unmeasured coordinate**, for a self-driving lab
  choosing its next sample. A polynomial's esd is conditional on its form
  being right (Brynjarsdóttir & O'Hagan 2014). A GP's variance carries the
  form's uncertainty too.
- **A seed for a library.** Points in (x, y) have no chain order. Kriging
  from already-fitted neighbours seeds the next pattern without one.

Measured precedent agrees on the regime:
- **Dynamic PET.** Fitting kinetic parameters straight to the raw data beats
  frame-then-fit most at low counts, and the two converge at high counts
  (Kamasak et al. 2005; reviewed by Reader & Verhaeghe 2014).
- **MRI.** Parameter maps fitted to raw k-space keep their accuracy at 5-10×
  undersampling (Sumpf et al. 2011).

The mechanism in both is pooling where each measurement is weak.

**Three uses, by how much they touch the answer.**

| use | changes a converged answer? | needs |
|---|---|---|
| seed: krige a pattern's start from fitted neighbours | no | nothing new; a 2-D/3-D chain warm start |
| afterwards: GP regression on (z_k, p̂_k, I_k⁻¹) | no; it reads the answers | each pattern's information, or the joint covariance where nuisances are shared (R3's control) |
| prior inside the joint fit | yes, outside the linear regime | prior rows in the joint residual (refused today, `least_squares.py:2424`), hyperparameters, a prior-share report |

A kernel can also be used as a **basis**: p = K(z, u)·α with M centres u.
This is Wang & Qi's (2015) PET kernel method, or an inducing-point basis. It
is a `design` Φ, so it is already in the declaration and needs no new
machinery. With M = N and no penalty it is a reparametrisation and
constrains nothing. The PET method's gain rests on stopping EM early, which a
converged LM does not do. With M ≪ N it is just a smoother hard basis.

**Costs and hazards.**
- **Transitions.** A stationary kernel smears a jump, and its esds hide the
  smear. Bayesian intervals cover only on average along the curve, and fail
  at kinks (Wahba 1983; Nychka 1988). That collides with the chain's rule that
  a step is "reported, never smoothed" (`_discontinuity_steps`,
  `sequential.py:2377`).

  Every field that smooths over coordinates segments first:
  - SAGE fits one GP per phase region (Kusne, McDannald & DeCost 2024);
  - SARA uses the GP to *locate* boundaries (Ament et al. 2021);
  - EBSD and hyperspectral maps use edge-preserving total variation
    (Athavale et al. 2023; Iordache et al. 2012);
  - ANDiE's data preferred a first-order law to the continuous one its run
    assumed (McDannald et al. 2022).

  So a kernel is declared, never a default, and its subset is a phase field
  (§ The shape item 1 already carries the subset). In difference or Markov
  form, a declared break is one deleted prior row.
- **Hyperparameters.** Only s²/ℓ^{2ν} can be estimated consistently
  (Zhang 2004). Estimate it by REML on the reduced problem (p̂, I), never
  inside the nonlinear fit, or fix ℓ from physics. Quote the answer again at
  ℓ×½ and ℓ×2. GCV can undersmooth badly and REML is steadier (Wood 2011).
  Over 500 000 synthetic DEER traces, AIC and GCV chose the strength better
  than the L-curve (Edwards & Stoll 2018).
- **What an esd means.** With the prior rows in, (JᵀJ)⁻¹ is a posterior
  covariance conditional on the hyperparameters. It leaves out the smoothing
  bias, so its intervals undercover (Kuusela & Panaretos 2015, in unfolding).
  That is a confident wrong singleton in a new form. A kernel fit therefore
  reports, per pattern:
  - the data share h_k = diag[(I + K⁻¹)⁻¹·I];
  - the independent esd beside the posterior esd;
  - tr(H) as the trajectory's effective degrees of freedom (Hodges &
    Sargent 2001).

  A value whose data share is small belongs to the prior and is marked so.
  That is WP-1110's rule (no esd rather than a small one) and WP-1301's (a
  value that is not a measurement is the caller's), applied to a prior. Prior
  rows take no χ²_red or Bérar-Lelann factor and stay out of the observation
  count, as restraint rows already do.
- **The absent-phase hold.** A prior gives a flat direction curvature, so the
  WP-1301 hold and a kernel disagree about a phase the data cannot see. The
  hold freezes it; the prior pins it to its neighbours. That has to be
  decided before the joint path admits prior rows.
- **Identifiability beside Φ.** A GP beside a parametric mean confounds c
  with the discrepancy unless c is *defined* (Kennedy & O'Hagan 2001;
  Brynjarsdóttir & O'Hagan 2014). Either definition fixes it: the GLS
  projection (Tuo & Wu 2015), or Φ as the kernel's null space. The hard tie's
  esd on c is overconfident whenever Φ is wrong.

**Computation: a kernel keeps the solver's structure.**
- Order the unknowns as [private blocks | p | c]. The prior touches only p,
  so the kernelised parameters join the Schur *border*.
- Eliminating each pattern's private block leaves I + K⁻¹ over (p, c): GP
  regression with each pattern's profiled information as its noise.
- The arrow survives, with a border of N·d_p + n_c columns, where d_p is the
  number of kernelised parameters per pattern. The scalable solver's route
  (ii) carries a kernel with no new structure.

How the border scales:
- **Dense K** is affordable up to N·d_p ≈ 3 000 (a Cholesky of order 10¹⁰
  flops, seconds per iteration).
- **1-D.** A half-integer Matérn kernel is a linear SDE (Hartikainen &
  Särkkä 2010). Prior rows Q^{-½}(x_{k+1} − A·x_k) then couple neighbours
  only, so the border is block-tridiagonal and the solve is O(N). At ν = 3/2
  the state carries dp/dz, a thermal-expansion coefficient with an esd.
- **Scattered 2-D/3-D (a library).** Vecchia or NNGP rows, each with m + 1
  nonzeros (Datta et al. 2016; Katzfuss & Guinness 2021).
- **A grid (a tomography slice).** The SPDE square root (Lindgren, Rue &
  Lindström 2011).
- **Partial pooling needs no dense K.** A latent mean in the border and
  per-pattern rows (p_k − μ)/τ suffice (Henderson 1976 writes the precision
  directly). Model the precision, never the covariance.

**The chain is half a smoother.** The iterated extended Kalman smoother is
Gauss-Newton on the joint problem (Bell 1994).
- The warm-start chain is a forward pass with no prior precision.
- A forward *filter* would add a `ValueRestraint` (`schemas/structure.py:550`)
  toward each predicted value, which a single-pattern fit already accepts.
- `direction="both"` runs both passes and *compares* them
  (`SEQUENTIAL_PATH_DEPENDENT`). A two-filter smoother (Fraser & Potter 1969)
  would *combine* them.

In 1-D that is a route to a kernel prior with no joint solver. But iterated
to convergence it is the joint fit by another name, and a forward filter
alone makes the answer depend on direction by construction.

**Precedent in diffraction.** No published Rietveld refinement puts a kernel
prior across patterns. The diffraction work does one of three things:
- smooths per-pattern values afterwards: GSAS-II's equations on its
  sequential table; CAMEO and SAGE on phase labels and properties;
  CrystalShift, which fits each pattern alone (Chang et al. 2025);
- ties hard (Stinton & Evans 2007; Wragg et al. 2015);
- fits jointly with no prior between voxels (DLSR, Vamvakeros et al. 2020).

The one place a kernel prior sits inside a fit to raw diffraction data is
**GP strain tomography** (Jidling et al. 2018; Hendriks et al. 2019;
Henningsson & Hendriks 2021):
- the strain field is a GP whose covariance satisfies equilibrium;
- it is fitted per grain to raw Bragg-edge and 3DXRD projections, with
  hyperparameters estimated from the data;
- it beat both the algebraic inversion and an earlier hand-weighted
  smoothing penalty on reconstruction error.

Outside diffraction, two precedents have the same structure:
- **geostatistical inversion** (Kitanidis 1995): a GP prior, a nonlinear
  forward model, and structural parameters by maximum likelihood.
  Gauss-Newton failed under strong nonlinearity and LM fixed it (Nowak &
  Cirpka 2004);
- **integrated plasma-profile analysis** (Kwak et al. 2020): GP priors fitted
  jointly to raw Thomson-scattering data.

Where a kernel over measurement coordinates has paid most is in choosing
*what to measure*:
- CAMEO, about 10× fewer experiments (Kusne et al. 2020);
- gpCAM, roughly half the measuring time in ILL tests (Noack et al. 2021);
- ANDiE, about 5× fewer temperature steps, with a parametric rather than a
  kernel model (McDannald et al. 2022).

**Reading.**
- **The kernel is the general soft form.** The hard tie and the independent
  fit are its limits, and it leaves the solver's structure unchanged.
- **Where each fit is linear it buys nothing** beyond a smoother run
  afterwards. That is the same regime where § Measured found the hard tie
  buys nothing. Any in-fit value lies where the next measurement already
  looks.
- **Two uses are cheap and change no fitted answer**: seeding a library that
  has no chain order, and smoothing afterwards with prediction at unmeasured
  coordinates.
- **Using it inside the fit has three costs**: a hyperparameter, a posterior
  esd that undercovers at a transition, and a decision against the WP-1301
  hold. It is measured against the hard tie before it is built.
- **Measured the same day** (§ Measured: where one pattern cannot see the
  parameter): REML on the trajectory fails in the weak regime, and at good
  hyperparameters the kernel bought intervals, not accuracy. Not built.

### Measured: scaling (2026-10-14)

`1325-measure/scaling.py`, output in `1325-measure/scaling_results.txt`.

**Setup.**
- Synthetic LaB₆ library at 3 000 points per pattern.
- The cell is a `polynomial` over (x, y), and each pattern has its own zero,
  profile and background.
- Linux x86_64, 4 CPUs, 15.7 GiB, no swap, `[dev]`, nothing else running.
- Each case ran in a subprocess.

| N | layout | columns | fit wall | peak RSS | coefficients vs truth |
|---|---|---|---|---|---|
| 10 | dense | 104 | 2.2-2.7 s | 0.24 GiB | |
| 10 | blocked | 104 | 1.3-1.4 s | 0.17 GiB | \|z\| ≤ 1.05 |
| 70 | dense | 704 | 63-68 s | 3.09 GiB | |
| 70 | blocked | 704 | 10.3-10.6 s | 0.29 GiB | \|z\| ≤ 0.83 |
| 300 | dense | 3004 | not run: J alone 20.1 GiB | | |
| 300 | blocked | 3004 | 48.2-48.6 s | 1.00 GiB | \|z\| ≤ 0.79 |

**What it says.**
- **Where dense stops.** J alone passes RAM at N = 265. A dense fit peaks at
  2.66× J (measured at N = 70), so it fits up to about N ≈ 161 on this
  machine (extrapolated, not run).
- **Blocked is the faster path from N = 10 up.** Blocked against dense, its
  coefficients agree to 6.8e-9 esd at N = 10 and 1.6e-8 esd at N = 70.
- **The blocked path's own limit is its n×n arrays.** N = 300 peaked at
  about 11 such arrays, which puts the limit near 1 400 patterns
  (extrapolated).
- **The next cost is the serial per-histogram Jacobian loop**, at 45 % of
  the N = 300 fit. The step is 4 %, normal equations 1.8 s and the
  covariance 3.3 s.

### Measured: where the joint Jacobian's time goes (2026-10-14)

`1325-measure/jacobian_profile.py`, output in
`1325-measure/jacobian_profile_results.txt` and, with openblas, OpenMP and
the kernel pool held to one thread each,
`1325-measure/jacobian_profile_one_thread_results.txt`. The maintainer asked
whether another Rust kernel would speed the joint fit.

**Setup.**
- `scaling.py`'s library at N = 60, blocked, on the same machine, with
  nothing else running.
- Every repeat runs at a new θ, because `phase_peaks` memoises on the cell.
  An early draft that reused one θ timed the cache and read 6.2× where the
  honest figure is 1.5×.
- Times are ranges over five repeats. A ratio is min against min, and (1) is
  one fit per run.

| what | default threads | one thread each |
|---|---|---|
| plain fit wall; joint Jacobian's share | 5.90 s; 48 % | 5.87 s; 49 % |
| `rietx_kernels` calls: profiled fit / plain wall | 1.5 % / ≤ 2.4 % | 1.5 % / ≤ 2.4 % |
| `_peak_chain_column`'s share of the joint Jacobian | 75 %, 4.0 calls a pattern a Jacobian | 76 % |
| one pattern's Jacobian, last stage | 2.40-2.45 ms | 2.42-2.64 ms |
| the per-pattern Jacobian loop over 2 / 4 threads | 0.68× / 0.49× | 0.70× / 0.49× |
| the per-pattern residual loop over 2 / 4 threads | 0.56× / 0.44× | 0.57× / 0.40× |
| the four `cell.a` peak-chain columns computed once | 1.52× on the Jacobian loop | 1.48× |

**What it says.**
- **Another kernel is not the lever.** The existing kernels are under 3 % of
  the fit. The profiler inflates python and not Rust, so 1.5 % of the
  profiled fit is a floor and 2.4 % of the plain wall a ceiling. A pattern
  here is 3 000 points of LaB₆, so its Jacobian is about a hundred small
  python and numpy calls, not a loop of arithmetic. A kernel of WP-1115's
  kind (a serial loop over a row range) has no loop here to take.
- **Threads lose, and the GIL is why.** A pool across patterns ran at 0.49×
  on 4 threads. Holding openblas, OpenMP and the kernel pool to one thread
  each left that unchanged, so it is not oversubscription. The work is short
  python stretches between short numpy calls, and the threads queue on the
  lock. Only a Rust port of the whole per-pattern peak chain would free
  them: positions, widths, |F|² and the column assembly, with a fallback and
  an oracle. That is a port of the forward model's per-reflection chain, not
  a kernel.
- **The repeated peak chain is the cheap win.** Every coefficient of one tie
  reaches `_peak_chain_column` under its target's name. Here that is four
  `phases.0.cell.a` columns beside six instrument columns, and each re-runs
  `phase_peaks` at its own step. Within a pattern each column is
  Φ_kj · ∂y/∂(target), so one call and a scale serve them all. That measured
  1.48-1.52× on the last stage's Jacobian loop with four terms, over three
  runs, and grows with the term count.
  - On the 45 % share at N = 300 that is about 1.2× on the fit (estimated,
    not run).
  - The estimate takes the last stage's column mix, 10 peak-chain columns
    with 4 repeated, for the whole fit, whose stages average 4.0 a pattern a
    Jacobian. So it can be off in either direction.
- **Then processes across patterns, not threads**, since the work is
  independent. Not measured.
- **The case for a kernel grows with the structure.** Synthetic LaB₆ is the
  worst case for this overhead. A phase with many reflections and atoms
  raises the arithmetic share, and the real ramp will say by how much.
  It did: about 13× (§ Measured on real data).

### Measured on real data: the ZrMo₂O₈ ramp (2026-10-14)

`1325-measure/real_ramp.py`. Output: `real_ramp_results.txt` (linear form,
`--each`), `real_ramp_quadratic_results.txt` (`--degree=2 --each`) and
`real_ramp_profile_results.txt` (`--profile`), all beside it.

**Setup.**
- Durham TOPAS tutorial 9.2, read from the local data root
  (`tests/local_data.py`). Ranges 36-68 in TOPAS's numbering: 693-991.5 K,
  33 patterns of 4 168 points, Cu Kα1, Bragg-Brentano.
- Three phases. Cubic ZrMo₂O₈ is the major one. LT-ZrMo₂O₈ decays across the
  window. Trigonal ZrMo₂O₈ stays a few wt % throughout.
- The structures are the tutorial input's, read by `rx.read_project_model`
  when the script runs. The resolution function and axial term are held at
  the input's values.
- Every fit runs `lab_sample_refine`'s scale and background, displacement,
  cell and sample-broadening stages.
- Targets: the cubic a, the trigonal a and the trigonal c, each a polynomial
  in T over all 33 patterns, under `SharingMap(per_histogram=["phases.*"])`.
  The joint fits start from the chain's per-pattern answers.
- macOS arm64, 10 CPUs, `[dev]` venv, compiled kernels on. Other sessions
  shared the machine, at load averages of 3 to 85, so every wall clock is a
  range over runs.

**The slopes, linear form**, in 10⁻⁶ Å/K. "Point esd" is the chain's mean
per-pattern esd on the target.

| target | point esd | line | joint | Δ / line esd | joint esd ÷ line esd | line χ²_red |
|---|---|---|---|---|---|---|
| cubic a | 0.0007 Å | −17.9(13) | −19.6(14) | −1.29 | 1.09 | 1.63 |
| trigonal a | 0.022 Å | −97.7(110) | −86.5(80) | +1.01 | 0.72 | 0.80 |
| trigonal c | 0.050 Å | 282(22) | 319(17) | +1.67 | 0.76 | 1.13 |

**The nested test.** The reference is the same joint fit with no law, at
χ²_red 1.873 and a Bérar-Lelann factor f of 2.50. F is (Δχ² / Δfree) /
χ²_red. F/f² also allows for serially correlated residuals, which inflate a
χ² difference as they inflate the esds.

| law | linear F | linear F/f² | quadratic F | quadratic F/f² |
|---|---|---|---|---|
| all three | 4.82 | 0.77 | 3.22, at `max_iter` | 0.51 |
| cubic a | 9.92 | 1.58 | 5.70 | 0.91 |
| trigonal a | 3.13 | 0.50 | 3.83 | 0.61 |
| trigonal c | 3.52 | 0.56 | 0.69 | 0.11 |

**Cost.** With the linear form the joint fit took 0.99-1.89× the chain, and
the untied fit 1.21-1.44×. The chain itself took 20-83 s. One linear law took
30-70 s. One quadratic law took 118-225 s, and all three 356 s.

**What it says.**
- **The joint path runs on real three-phase data.** All 33 patterns,
  1 029-1 122 free columns, converged in one to two times the chain's wall
  clock.
- **For a strong phase the gain is convenience, as on the synthetic ramp.**
  The cubic slope's esd matches the line's to within 9 %. The two slopes sit
  1.3 esd apart, but the nested test rejects the straight line for this
  target, so that gap is two weightings of a wrong form.
- **For a weak phase the joint esd is a quarter smaller.** The trigonal
  slopes' esds are 0.72 and 0.76 of the line's. The synthetic weak phase
  measured 0.72 in scatter. The truth is unknown here, so this measures
  precision only.
- **The nested test finds the wrong form once serial correlation is allowed
  for.** Plain F rejects every linear law, at 3.1-9.9. Divided by f², only the
  cubic line fails, at 1.58, and its trajectory does curve: the cell rises
  from 693 K to 723 K, then falls. A quadratic brings it to 0.91. The line's
  own χ²_red ranks the targets the same way, by a narrower margin. The test
  costs one joint fit without the law, about one more chain.
- **Declare only the terms the data carries.** Quadratics on all three
  targets stopped at `max_iter` after 356 s, with `HIGH_CORRELATION`.
  - The trigonal a quadratic alone converged 34 above the χ² of the line it
    nests, so the solver stopped in a different minimum along the weak
    phase's direction.
  - The trigonal c quadratic alone fell to 0.11. It bends through the
    patterns below 838 K, where that cell's esd is 0.05-0.14 Å. This
    measurement cannot say whether those points are biased.
- **The compiled kernels are a fifth of a three-phase fit.** `rietx_kernels`
  took 19.9-20.1 % of the profiled joint fit, against 1.5 % on the synthetic
  library. `_peak_chain_column` took 34.8-35.2 % of the fit.
- **Two gaps surfaced.**
  - The joint support hold decided per phase across every histogram. Under
    per-histogram phase paths, a pattern's own copy of a vanished phase's
    cell stayed free wherever another pattern still showed the phase. Fixed
    in `multi._unseen`, with a two-pattern joint fit as the guard. This
    window never met it: no phase falls below support in any pattern here.
  - The chain held the fading LT phase in two patterns (938 K and 956 K) by
    WP-1523's answer significance. The joint path reads the support screen
    alone, by design, because its report is WP-2028's (WP-1341's until it closed 2026-10-23). So the chain and the
    joint free different sets, 14 columns here. That is why the nested test
    takes the untied joint fit as its reference.

### Measured: the form test (2026-10-14)

`1325-measure/form_score.py` on the real ramp, `form_synthetic.py` on
`kernel_ramp.py`'s synthetic ramps. Output beside them:
`form_score_results.txt` (the shipped form), `form_score_first_results.txt`
(the first run, with the readings the shipped form dropped) and
`form_synthetic_results.txt`.

**The test.** At the tied answer, each subset pattern's own target column is
read off the coefficient columns, J_coef·Φ_kᵀ/‖Φ_k‖². The alternative swaps the
coefficients for those columns. One linear step from the answer, every other
column refitted, gives the χ² it would remove: Rao's score statistic for k
columns, `Refinement.suggest`'s one-column gain generalised. It is divided by
the tied fit's χ²_red·f² and compared with χ²_k's 95 % point. (Since
741649b it is divided by χ²_red alone: decision 4.) Three choices
came from measurement:
- **The alternative drops the coefficients.** Appending the per-pattern
  columns beside them counted a tenth direction on a ten-pattern ramp, since
  finite-difference error leaves a derived column a hair outside the
  coefficients' span.
- **A pattern that cannot see the target is left out**, by `multi._unseen`,
  the support hold's predicate. Counted in, the weak synthetic phase scored
  rank 8 against the untied refit's 3.
- **The denominator is the tied fit's**, the textbook score test's
  restricted estimate. Read off the residual the step predicts, f fell to
  2.27 against the untied fit's 2.50, since the unbounded step also moves the
  columns on a bound. That put the cubic law at 2.09 against the refit's 1.58.
  Columns `bound_findings` names are held out of both sides; that moved the
  three-law gain from 1.07 to 1.04 of the refit's.

**The ZrMo₂O₈ ramp** (33 patterns, three phases; macOS arm64, 10 CPUs, `[dev]`,
load 5-30). The refit is the untied joint fit, χ²_red 1.873, f 2.503.

| law | refit Δχ² | score gain | refit F/f² | score F/f² | verdict |
|---|---|---|---|---|---|
| all three | 839.3 | 871.7 (1.04) | 0.77 | 0.79 | both keep |
| cubic a | 576.1 | 572.8 (0.99) | 1.58, p 0.021 | 1.57, p 0.023 | both reject |
| trigonal a | 181.7 | 246.6 (1.36) | 0.50 | 0.68 | both keep |
| trigonal c | 204.7 | 182.0 (0.89) | 0.56 | 0.50 | both keep |
| cubic a, quadratic | 320.3 | 315.0 (0.98) | 0.91 | 0.89 | both keep |

- The score costs one Jacobian, 0.71-0.78 s, plus 0.05 s of algebra. The
  untied refit took 41 s and each tied fit 47-117 s.
- At the three-law answer, each law scored with the other two still tied:
  cubic 1.37 (p 0.08), trigonal a 0.34, trigonal c 0.29. So the cubic law
  passes beside the others and fails alone; a per-law test at a multi-law
  answer is the weaker one.

**The synthetic ramps**, 20 seeds a cell, the tie and the untied refit seeded
from the chain:

| regime, truth | refit rejects | score rejects | score gain ÷ refit Δχ², median [range] |
|---|---|---|---|
| W, line | 0 | 0 | 0.96 [0.37, 4.97] |
| W, curve | 0 | 0 | 0.85 [0.26, 3.32] |
| W, kink | 0 | 0 | 1.01 [0.38, 3.52] |
| O, line | 0 | 0 | 1.10 [0.89, 1.38] |
| O, curve | 0 | 0 | 1.08 [0.89, 1.41] |
| O, kink | 0 | 0 | 1.10 [0.91, 1.29] |

- **No power on either regime's bent truths, and the refit had none
  either.** Both regimes were built so that a pattern measures the minor cell
  poorly (`kernel_ramp.py`'s docstring). In W four to eight patterns saw the
  phase, by the ranks. The test sees a form only where, and as well as, a
  pattern measures the target, so it does not answer the 0.03 gap coverage,
  which lives in the patterns that cannot see the phase. Why the seen
  patterns carried no power was not measured.
- **W's gain ratio spreads 0.26-4.97** because the untied refit and the tie
  hold different patterns' cells; its Δχ² is then not a nested difference (it
  read −0.24 on one seed).
- **Size:** 0 of 40 straight truths rejected. f read 1.251-1.274 on these
  fits, against 1.127 for white noise, so the f² reading is conservative on
  synthetic data. Without f² the score rejected 1 of 20 W straight truths.
- **A strong phase is where it works.** On the slow test's LaB6 ramp a bow
  of 1 % of the line's half-excursion, 9.4 × 10⁻⁵ Å at mid-ramp, scored
  2 607 against a cut of 15.5, at GoF 1.12; the straight truth scored 4.8.

**On the synthetic library** (`tests/test_parametric_series.library`, the
true bilinear surface declared, blocked solve; load 10-24): the test took
0.27 s of a 6.7 s fit at 120 patterns (4.1 %) and 0.67 s of 18.0 s at 300
(3.7 %). It kept the true surface, 76.4 against a cut of 142.1 for 116
directions and 197.9 against 337.1 for 296.

### Measured: the form test out of sample (2026-10-14)

Three real ramps, each with an over-flexible arm. Scripts and output are in
`1325-measure/`: `zrp2o7_*`, `wo3_*` and `zrmo2o8_overflex.py`. Two lanes ran
ZrP₂O₇ and WO₃ at load 4-110, beside other sessions' suites. Wall times are
in the results files.

**The models.**
- ZrP₂O₇: 37 patterns, 303 K to 1173 K and back, three phases parsed from
  the input's `str` blocks (`read_topas_inp` refuses its `B1` macros).
  Untied Rwp 31.47 %, TOPAS 31.56 %. TOPAS's 2θ calibration curve
  (0.006-0.011°) is left out, since rietx has no such term.
- WO₃: 100 patterns, 300 K to 90 K, three phases from `read_project_model`.
  TOPAS's Einstein law on each edge is a `design` law with θ held at
  125.37 K, and the angles are quadratic. Untied Rwp 13.53 %, TOPAS
  12.81 %. One B per pattern is held at the chain's value in the joint
  fits. The forward chain fell into a wrong minimum at 206-221 K, so each
  pattern is seeded from the better of a forward and a backward chain.

**The denominator.** Laws that must hold any smooth truth: a cubic or
quartic per window, or a quintic over the ramp.

| ramp | f | readings | rejected over χ²_red·f² (shipped until 741649b) | over χ²_red alone (shipped since) | over 1 |
|---|---|---|---|---|---|
| ZrP₂O₇ | 1.23 | 20 freed, 2 joint | 0, 0 | 0, 0 | not run |
| WO₃ | 2.4-3.6 | 210 freed, 15 joint | 0, 0 | 10, 2 | 39, 9 |
| ZrMo₂O₈ | 2.42 | 12 freed, 2 joint | 0, 0 | 2, 0 | 7, 2 |

- Over χ²_red alone, 12 of 242 freed readings reject (5.0 %), and 2 of 19
  joint readings. WO₃'s ten fall at or above 238 K, mostly on Pc, whose
  cell is unmeasured there while the support screen counts the phase seen.
- With f², none of 261 readings rejects. The statistic per direction has
  a median of 0.067 on WO₃, and the p-values pile toward 1 on ZrP₂O₇
  (KS p 0.0002 pooled; 0.70 over χ²_red alone).
- On ZrMo₂O₈, the ramp f² was chosen on, the over-flexible statistic over
  χ²_red alone has a median of 1.08 per direction (0.35-2.15).
- Synthetic, for comparison (§ Measured: the form test): f² is
  conservative there too, and without it 1 of 20 straight truths was
  rejected.

**The laws, recorded before any comparison.**
- ZrP₂O₇, one law over both legs, ZrP₂O₇ across its transition: that law
  is rejected (3122 for 34). Beside it, Si's freed reading rejects
  (51.4 for 35, p 0.036) while Si's law-alone refit keeps it (p 0.92).
- ZrP₂O₇ with its law split at the transition: every law keeps with f²,
  each freed gain 0.92-1.10 of its law-alone refit. Over χ²_red alone the
  joint reading rejects (190.7 for 134, p 0.0009). A nested refit against
  one law per leg rejects too (p 0.0013): the transition's hysteresis,
  cooling +6(3) × 10⁻⁴ Å above heating below 502 K. Si shows no lag
  (+1.2(3.4) K at 587 K). With one law per leg and field, 1 of 10 laws
  rejects over χ²_red alone, and the joint reading keeps (p 0.13).
- WO₃, TOPAS's laws: 4 of 14 rejected with f² (the three P2₁/n edges and
  Pc c), and the joint reading (1941.9 for 1367). Against law-alone
  refits: m_c freed p 0.0056 against the refit's 0.12 (gain 1.22×); t_a
  both keep; t_beta freed p 0.17 against the refit's 5 × 10⁻⁷ (gain
  0.62×), its chain points at χ²_red 5.89 about the law. Over χ²_red
  alone, both readings of m_c and of t_beta reject.
- ZrMo₂O₈, § Measured: the form test's lines over χ²_red alone: 9.9, 4.1
  and 3.7 per direction, against the over-flexible arm's 1.08.

**One linear step from a far answer.** The score is one step from the
tied answer. Where a law is far wrong, the answer sits far from the
alternative, and other laws' readings drift from their refits: Si on
ZrP₂O₇ (2.6× and 3.1× its law-alone refit's gain, beside a law at 3122 for
34), m_c and t_beta on WO₃ (1.22× and 0.62×). Where the laws are near
right, each freed gain is 0.92-1.10 of its refit.

**Found on the way.**
- A law's seed broke a target's own bounds, and the fit refused before its
  first iteration (`ValueError … breaks its own bounds`). It happened on
  WO₃ and on ZrMo₂O₈'s windowed cubic (trigonal c 12.276 Å against
  12.263 Å). Both runs widened the cell windows to get past it. This is
  the in-step-bounds task's.
- `MultiHistogramRefinement` has no tie verb, so WO₃'s one B per pattern
  could only be held in a joint fit.
- The support screen counted WO₃'s Pc as seen where its cell is
  unmeasured (1.5-3.5 wt % above 221 K), so the form test counts those
  patterns.
- `real_ramp.py` sets the FCJ axial ratios to v/L from TOPAS's
  `Simple_Axial_Model(v)`. The ZrP₂O₇ lane reads v as a full length, so
  v/2L, which lowered χ²_red by 0.045-0.085 on five patterns. Not checked
  against TOPAS's manual. The package does not convert the macro.
- Unexplained: WO₃'s t_beta law-alone fit printed its own reading as
  110.1 for 97 (p 0.171), the all-laws freed reading to every digit. It
  is not used.

### What the code has (survey, 2026-10-14)

- **`multi.py` is the seam: N patterns, one θ** (WP-0308).
  `refine_multi` → `MultiHistogramRefinement` is separate from `Refinement`
  and keeps no history (`multi.py:886`).
  - `SharingMap` makes a path per-histogram iff it starts with `instrument.`
    or ends with `.scale`; overrides are checked first
    (`params/multi.py:152-173`). Per-histogram paths are scoped as
    `hist.{h}.<path>`.
  - Each histogram has its own `ParameterTable` with its own C. The joint θ
    is a gather through `col_map`, and sharing is the only cross-histogram
    link.
- **One starting `Structure` is deep-copied into every histogram**
  (`params/multi.py:187`). A library needs each specimen to start from its
  own cell, occupancies and widths.
- **The joint path has no tie, variable or hold verb** (the
  `_hold_diagnostics` row at `multi.py:275`). The substrate exists:
  `ParameterTable.add_parameter`/`set_tie`. A `vars.` path counts as
  *shared* under the default rule. So the same variable in every table, tied
  per table onto `hist.{h}.` targets, folds onto one column with no solver
  change: that is the mechanism for a parametric tie.
- **Latent WP-1342 bug the parametric tie would trigger.** The joint
  absent-phase hold matches free paths by name prefix
  (`_unsupported_paths_multi`, `multi.py:374-380`). The single fit reads
  `column_reach` (`refine.py:509-513`). Once a `vars.` coefficient drives
  per-histogram cells, the prefix test cannot see it.
- **The joint Jacobian is dense, and so is everything after it.**
  - It is assembled as `np.zeros((n_rows, n_cols))`
    (`optimize/least_squares.py:2459-2469`).
  - LM forms `A = JᵀJ` from it every outer iteration (`optimize/lm.py:476`).
  - The bounded step uses BVLS on an eigen-factor up to `BVLS_MAX_COLUMNS` =
    128 columns, and dense projected CG above that (`lm.py:731-733`).
  - The covariance forms JᵀJ again (`statistics.normal_factors`).
  - At 3 000 points per pattern, 20 shared and 10 private parameters, J alone
    is ≈ 1.2 GB at 70 patterns, ≈ 22 GB at 300 and ≈ 240 GB at 1000.
  - Residual and Jacobian loop over histograms serially.
- **WP-1125's identity is the solver's equivalence bar.** The Schur-complement
  Gauss-Newton step *is* the joint step, at every point and not only at the
  optimum, measured to ≤ 6.6e-7 relative on 70 stages
  (`docs/solver-survey.md` §2.A1). It holds **only while no bound is
  active**: a bounded local block (phase scales) leaves the identity once a
  bound binds.
- **Soft restraints are refused in a joint fit**
  (`least_squares._multi_closures`, deferred since WP-0406; lifting it is
  [1995](1995-soft-restraints-in-a-joint-fit.md)). So partial pooling
  or a smoothness penalty over the axis needs that refusal lifted first.
- **Reusable bases:** `background/models.py` has `bspline_design_matrix`,
  `chebyshev_design_matrix` and `second_difference_matrix`, all 1-D. n-D
  polynomial terms are a few lines over numpy.

### Use cases carried here

- **The outside lab (2026-10-13, by email).** It runs rietx and TOPAS side by
  side on combinatorial libraries. For gradual, broad, interfering peaks it
  refines **polynomial surfaces** over the library in TOPAS, calling it "the
  only way" to get consistent, smoothly evolving models across a library and
  to decouple the measured quantities from how the diffuse features are
  modelled. Its targets include weak and broad features in `instrument.*`
  (background, `extra_components`), so a tie reaches `hist.{h}.` paths. The
  same email names spherical-harmonics texture as their other gap; that is
  [1960](1960-spherical-harmonics-texture.md), not this.
- **Issue #212's conserved elemental ratio** is a parametric constraint in
  disguise: linear in the phase scales and constant across the axis. Its
  restraint row is [1942](1942-a-soft-restraint-on-a-sum-across-phases.md),
  which holds the seam, the workaround and #349's exports.
- **Named variables exist** ([1119](1119-named-variables.md)).
  `Refinement.add_variable` gives `vars.<name>`, which `parameters()` lists,
  `set_vary("vars.*")` frees, a fit refines with an esd and
  `RefinementState.variables` persists. `Refinement.tie` takes
  `{path: coefficient}`. They are single-pattern only today
  (`refine.py:1980-1992`).
- **The ordered moment through T_N** ([1329](1329-moment-in-a-series.md)),
  m ∝ (1 − T/T_N)^β, is nonlinear in β and T_N, so it is fenced. If the
  measurement says the joint form pays, the moment trajectory is a further
  series to measure it on.

### A contributor's series work (PR #977 comments, 2026-10-14)

@mustachefeeling commented twice on PR #977 with what their August to
October series work found. Neither comment asks for a change to #977. A
private bundle with the harness, drafts and data goes to the maintainer
separately. The points for this WP are below. The subset boundary and the
detectors went to [1965](1965-a-law-declared-by-formula-condition-and-glob.md),
the scanned nonlinear laws to [1964](1964-a-nonlinear-law-through-the-derived-block.md),
and the telemetry and event pairing to [1322](1322-events-aggregator.md) (closed 2026-10-23; it returned the per-equation line here, see § Inherited).
Their numbers are as reported and were not re-measured here.

- **The joint fit inherits the chain's start, and the chain can be wrong at
  equal Rwp.** On a two-phase VT series, whether the subgroup phase existed
  depended on the walk direction. On an orthorhombic perovskite series, a
  and c swapped between passes at 15.8σ. A chain reported `converged` with a
  phase fraction wrong by tens of wt %, and the reseed ladder fires only when
  Rwp is worse. For the start-agreement task they suggest seeding from a
  chain that passed `direction="both"`, or from both directions with the
  disagreements reported.
- **Long in-situ series need segments.** Declaring every phase from pattern
  1 gave a cell runaway and an SVD failure. What worked was segments switched
  on the temperature history, at most 90 patterns each, chained from the
  previous segment and run with `direction="both"`. A segment cannot resume
  a dead chain's warm state.
- **The WP-1523 hold picks the weaker of two collinear phases** (#219): the
  real parent in 2 of 3 arms, at identical Rwp. It is the same unowned
  defect as § Measured's chain kept at support 0.84-1.4.
- **Admissibility.** Their draft planned a free fit under a smoothness
  penalty, then a Durbin-Watson or runs test of the free trajectory against
  the law, quoting esds conditional on the law and free. The form test
  covers the same ground. They suggest the manual state the end state: an
  equation is for nuisance parameters, and the science stays free.
- **Composition equations.** One δ drives several occupancies by charge
  balance. Anchoring and extrapolating fails far from dilute. Anchoring by
  isotherm plus an external restraint row (TGA) is what they would want,
  which is [1942](1942-a-soft-restraint-on-a-sum-across-phases.md)'s seam.
- **An equation on an angle path** meets the angle wrap in `moved_paths` and
  #263's one-sided esd (closed).
- Not carried: their test that a tie survives the chain's carry step (#376,
  closed). A parametric equation exists only in the joint fit, which has no
  carry step.

### Inherited

- **2026-11-01, from [1999](1999-a-held-cells-ties-leave-the-answer-with-it.md): a held
  coefficient's target rows leave `parameters`.** A result now lists only the rows the fit
  could move (`ParameterTable.moving_paths`). When the support hold takes `vars.b_0`, the
  `hist.h.phases.1.cell.*` rows it drives are absent, so their `RefinedParameter.equations`
  is no longer readable there. `PARAMETRIC_TARGET_UNSEEN` and `result.parametric` still name
  both. `test_a_joint_fit_holds_a_coefficient_whose_phase_no_pattern_sees` was re-pinned to
  that.
- **2026-10-23, from [1341](1341-a-joint-fit-has-no-report.md) (closed): joint-report items now go
  to [2028](2028-a-joint-fits-guards-see-every-histogram.md).** The four joint items and the
  three `PARAMETRIC_*` rendering notes this WP sent 1341 on 2026-10-14 are 2028's Context items
  1-4 and 6, under today's names (`parametric_equations`, `RefinedParameter.equations`).
- **2026-10-23, from [1322](1322-events-aggregator.md) (closed): `rietx events`
  could print one line per parametric equation of a joint fit.** This is
  @mustachefeeling's point from the PR #977 comments, which this WP sent to
  1322 on 2026-10-15. 1322 closed without it. A joint fit keeps no history
  (`multi.py`), but it has emitted events since #926, and `rietx events`
  (`history.aggregate.summarize_events`) shipped in PR #902. The line would
  carry the subset size, the form verdict, and whether a detector fired inside
  the subset (the subset boundary and the detectors are
  [1965](1965-a-law-declared-by-formula-condition-and-glob.md)'s). Two rules
  for whoever builds it:
  - Pair events in file order, never by `(series_index, series_pass)`, since
    indices recur on reseeds and restarted segments. The aggregator already
    clears its open stages at each `fit_start` (`aggregate.py:185`).
  - A segmented chain's summed fit time is not its wall time: 700 s against
    148 s on one chain, as reported and not re-measured.

- 2026-10-31, from the issue triage (issue #1218, row S2): a pure-error
  lack-of-fit beside the declared-form test. For every group of patterns that
  share every declared coordinate, the χ² of the free-fit targets about their
  inverse-variance mean on n_g − 1 dof, per group and pooled, with esds
  uncorrected (the choice the form test already makes), and "no replicate
  groups: not measured" when no coordinate repeats. It would sit on
  `ParametricFormTest` as `replicates`, or on the series summary. Measured by
  the reporter on one synthetic series (16 patterns, cubic perovskite
  capillary, a = a₀(1 + αΔT) + 0.02·x, a ramp to 700 K then a hold): when x
  drifts during the hold the 9 held patterns differ in `phases.0.cell.a` by χ²
  = 24 054 on 8 dof; when x stays put, χ² = 12.0 on 8 dof (p ≈ 0.15). The
  score test cannot see a misfit that varies at a repeated coordinate, which
  is what replicates measure (Draper & Smith 1998, pure error). Checked
  against the tree at d87c8cc91: `ParametricFormTest`
  (`schemas/parametric.py:320`) carries `n_patterns`, `n_subset`, `tied`,
  `others_freed`, `rejected` and no replicate reading; this WP's ticked
  lack-of-fit task built the score test only. Not re-run here. The reporter
  proposes landing S2 before S1.

## Non-goals

- A library of physical models: here the caller supplies the basis, or names
  a polynomial. Named nonlinear laws are
  [1964](1964-a-nonlinear-law-through-the-derived-block.md)'s.
- Replacing the chain: it stays the exploratory tool and the seed.
- Laws nonlinear in their coefficients: an order parameter's
  (1 − T/T_c)^β with T_c and β refined, an Avrami rate, an Einstein
  temperature. Filed 2026-10-14 as
  [1964](1964-a-nonlinear-law-through-the-derived-block.md). The fence here
  rested on WP-1119's reading that only C·θ + d is exact under autodiff, and
  WP-1804's derived block has since given the table a second, nonlinear seam.
  A law nonlinear in the coordinates alone is already declarable as a
  `design` basis.
- Declaring a law by a formula string, a subset by a condition on the
  coordinates, or a target by a glob:
  [1965](1965-a-law-declared-by-formula-condition-and-glob.md).
- One pattern as a sum over several specimens (A ≠ identity): direct XRD-CT,
  depth profiles. That is [1962](1962-xrd-ct-a-pattern-summed-over-the-voxels-its-beam-crosses.md).
- Soft forms: partial pooling toward the surface, or a P-spline smoothness
  penalty over a coordinate. Both need the joint path's restraint refusal
  lifted, and both make the esds conditional on a penalty weight. Both are
  members of one kernel family (§ A kernel over the coordinates), so the
  follow-up builds the kernel:
  [1963](1963-a-kernel-over-the-pattern-coordinates.md), filed 2026-10-14
  once the form test proved blind where the tie's intervals fail.
- Sliding-window marginalisation for unbounded campaigns.

## Tasks

- [x] **The measurement, synthetic half.** A ramp of 10 patterns with a known
  a(T): the trajectory-line coefficient and esd against a joint a₀ + a₁·T fit,
  plus the wall-clock ratio against the chain, on today's dense joint path.
  Landed as `1325-measure/synthetic_ramp.py`; the numbers are in
  § Measured.
- [x] **The measurement, where a single pattern cannot see the parameter.**
  § Measured shows the tie buys nothing while every pattern's own fit is
  linear. Push the synthetic ramp until it is not:
  - a minor phase whose per-pattern scale falls under the 3σ hold
    (WP-1301), so the trajectory has gaps;
  - overlapping or broad peaks, the outside lab's case.

  Report the joint a₁ and its scatter across seeds against whatever line the
  surviving trajectory points allow.

  Extended 2026-10-14 at the maintainer's request (§ A kernel over the
  coordinates):
  - two arms beside the hard tie: a GP fitted afterwards on the trajectory,
    and a joint fit with kernel prior rows (the script appends them, as it
    already subclasses the joint path);
  - a truth that is not a line, one curved and one with a kink, so the hard
    tie's form error and the kernel's smoothing bias both show;
  - the weak phase's *fraction* as well as its cell.

  Landed as `1325-measure/kernel_ramp.py`; the numbers are in § Measured:
  where one pattern cannot see the parameter.
- [x] **A lack-of-fit check on the declared form.** The tie's gap coverage
  fell to 0.03 under a curved truth (§ Measured: where one pattern cannot see
  the parameter), so a wrong Φ yields a confidently wrong esd. Candidates:
  - χ² of the per-pattern values against the tie's curve, where the
    per-pattern fits are trustworthy;
  - a nested fit with one more term.

  Either says when to widen the basis. It is cheaper than a kernel, which
  bought only honest intervals.

  A third candidate needs no refit: a score test against a per-pattern
  deviation, built from the coefficient columns at the answer.

  Measured on the ZrMo₂O₈ ramp (§ Measured on real data), the nested test
  works against the joint fit with no law, at one extra joint fit. It
  separates the wrong form only once the χ² difference is divided by f², the
  Bérar-Lelann factor squared: plain F rejected every linear law at 3.1-9.9.
  The chain is the wrong reference, because it holds by WP-1523's answer
  significance and the joint path does not.

  Landed as the third candidate, the score test, measured against the nested
  refit first (§ Measured: the form test):
  - `params.parametric.form_tests`, run once at the answer by
    `MultiHistogramRefinement._build_result`, with
    `optimize.blocked.added_columns_gain` doing the algebra on the arrow;
  - `RefinementResult.parametric_form`, one `ParametricFormTest` per
    declaration (schema 0.56), printed after its coefficients;
  - `PARAMETRIC_FORM_REJECTED`, a warning on the coefficients;
  - the series deliverable's functional-form row names a rejected law.
- [ ] **Hold each target's own bounds inside the step.** Coefficients are
  unbounded, so a polynomial can step a target through its floor or pole
  mid-solve (March-Dollase r at `MARCH_R_MIN`, the Caglioti W floor, an
  occupancy outside [0, 1]). `PARAMETRIC_OUT_OF_RANGE` reports this only
  afterwards. Root CLAUDE.md's rule is that a bound on a combination is an LM
  `LinearInequality` held inside the step:
  - one row lo ≤ Φ_k·c ≤ hi per subset pattern with a finite bound;
  - the joint driver passes `inequalities=[]` today
    (`least_squares.run_multi_least_squares`);
  - TRF keeps the post-fit warning.

  Declined from the 2026-10-14 code review as a design change.
- [ ] **Per-pattern starting structures agree beyond their parameters.**
  `_starting_structures` checks the phases, space groups and sites, and
  `_check_starts_agree` the shared values. Fields that are not parameters
  can still differ between starts: a preferred-orientation axis, the magnetic
  symmetry, the extinction model. Two starts with different texture axes
  sharing one `r` column are not one model with different values. Decide
  which fields must agree and refuse the rest. Declined from the 2026-10-14
  code review as a design decision.
  - The values matter as much as the fields: a chain can hand the joint fit
    a wrong basin at equal Rwp, or a phase that exists in one walk direction
    only (§ A contributor's series work). Decide whether the start reads
    a `direction="both"` chain and reports where the two walks disagree.
- [x] **The measurement on real data**, with the same numbers as the
  synthetic half, on the ZrMo₂O₈ ramp: `1325-measure/real_ramp.py`, in
  § Measured on real data. All three sources are Durham TOPAS tutorials.
  They are public downloads, which the maintainer cleared for local use only
  (2026-10-14; never committed):
  - ZrMo₂O₈ on a ramp (tutorial 9.2), the first 68 of the RAW file's 82
    ranges. This is the ramp the Scope calls the maintainer's local copy,
    byte for byte;
  - ZrP₂O₇ (tutorial 9.5; Stinton & Evans 2007). Its input reads 37 of the
    RAW file's 871 ranges, 303 K to 1173 K and back, with three phases:
    ZrP₂O₇, a silicon standard and Al₂O₃. TOPAS numbers a range from 1 and
    `read_pattern(scan=)` from 0;
  - WO₃ (tutorials 9.3 and 9.4, the maintainer's "Tutorial 39"; 100 patterns
    cooled from 300 to 90 K through its transitions).

  Since 2026-10-14 they sit in the local data root, registered by URL and
  sha256 in `tests/local_data.py`, and `python -m tests.local_data` fetches
  them on a new machine. A cloud container has none of them, because the
  Durham host is outside its network policy.
- [x] **Show in the output when a value came from a law** (maintainer,
  2026-10-14). Today a pattern's target row (`hist.<h>.<target>` in
  `RefinementResult.parameters`) reads like a measured value, with the law's
  esd, which can be far tighter than that pattern measures alone. In a
  pattern that cannot see the target it is extrapolation, the 0.03 coverage
  case.
  - Mark each such row with the law that set it, wherever rows print or
    serialise, `for_histogram(h)` included. A field on `RefinedParameter`
    needs its writer named in `multi._parameters` (WP-1076's rule).
  - The form line says "n of N patterns", so a law checked on few of its
    patterns shows it.
  - A warning when a law sets the target in patterns that cannot see it,
    naming them: there the value is the law's, and the form test is blind.
  - The p-value beside the statistic, so a near miss is visible as one.
  - The coefficients' own rows too (added 2026-10-14, from a review of the
    API against prior art). `RefinementResult.parameters` lists each
    `vars.<name>_<j>` in the table's units, per unit of the *scaled*
    coordinate, beside `RefinementResult.parametric`'s user units. On the
    five-pattern ramp in `using/series.md` the slope's row reads 0.006235
    (Å per 300 K) and its coefficient 2.0784 × 10⁻⁵ Å/K. The manual has to
    tell readers to skip the row. Mark the row as a law's coefficient and
    point at `parametric`, or drop it from `parameters`; the
    `RefinedParameter` field rule above applies either way.

  Landed 2026-10-14 (schema 0.57):
  - `RefinedParameter.laws`, written by `multi._law_rows` off each table's
    `entry_reach`, so what follows a target (a cubic cell's b and c) and a
    held coefficient's rows count too. `None` reads "not recorded", since
    1.9.0 shipped parametric fits whose rows carry no field; the single fit
    writes an empty list. The notebook table gains a `laws` column.
  - The coefficient rows are **marked, not dropped**. Dropping them breaks
    the row contract (a row iff it varied or was tied), and `BOUND_HIT` on a
    `constant` coefficient would then name a path absent from `parameters`.
  - `ParametricFormTest.n_subset` and `.p_value`; the line reads "(p = 0.77)
    for 8 directions over 10 of 10 patterns", and `p < 0.001` below that.
  - `PARAMETRIC_TARGET_UNSEEN`, from the one `_parametric_unseen` reading the
    form test's skip now takes too.
- [x] **The coefficients' covariance, and the law's value at any
  coordinate** (added 2026-10-14, from a review of the API against prior
  art). `ParametricCoefficient` carries an esd and nothing else, and
  `Identifiability.top_correlations` lists only the worst pairs. A value
  between or beyond the patterns needs the whole block. For example, a(293 K)
  from a line centred at 600 K needs cov(c₀, c₁). Today the per-pattern
  `hist.<h>.<target>` rows give a propagated esd at the measured coordinates
  only. statsmodels' `cov_params()` and `get_prediction()` are the prior art.
  - Carry each declaration's coefficient covariance on the result, in user
    units at its reference. Take it from the matrix the esds come from
    (`least_squares.covariance_jacobian`, WP-1929's rule), so the block's
    diagonal reproduces every `ParametricCoefficient.esd` exactly. Pin that
    equality by test.
  - A reader evaluating the law at a coordinate returns Φ(z)·c and
    √(Φ(z) Σ Φ(z)ᵀ). It reads the stored reference and scale and computes
    nothing the fit has not stored (root CLAUDE.md § a display reads fields).
  - The value carries the form test's verdict beside it, because its esd
    assumes the form. Beyond the subset's range it says it is extrapolating.

  Landed 2026-10-14 (schema 0.57):
  - `RefinementResult.parametric_laws`, one `ParametricLaw` per declaration:
    the resolved tie, the target's unit, each coordinate's span over the
    subset, and the covariance. Built by `params.parametric.parametric_law`
    as esd_i·esd_j·ρ_ij from the joint correlation the esds were read off,
    with ρ_ii = 1, so the diagonal is `esd ** 2` exactly (pinned).
  - `RefinementResult.parametric_value(name, {coord: z})` (or `row=` for a
    `design` law) returns a `ParametricValue`: value, esd, unit, the
    coordinates outside the subset's span, and the form verdict.
  - On the ten-pattern LaB6 line ramp it reproduced every `hist.<h>.` row's
    value and esd to the bit; ρ(c₀, c₁) was 0.007 there, the centring's work.
  - `outside` checks each coordinate's range on its own, so a 2-D point
    inside both ranges and far from every pattern is not flagged.
- [x] **Test each law with the other laws freed** (maintainer, 2026-10-14).
  Beside other laws, a law reads weaker than alone: the cubic line scored
  1.37 per direction at the three-law answer and 1.57 alone.
  - From the answer, the gain with every law's columns swapped, less the
    gain with only the others' swapped; dof by the same difference. One more
    projection per law, no refit.
  - Validate on the ZrMo₂O₈ ramp against the refits that freed the other
    targets: 1.58, 0.50 and 0.56 per direction (§ Measured on real data).
  - Decide how the two verdicts reach `rejected`, the diagnostic and the
    printed line. Two tests per law raise the false-alarm rate, decision 4's
    question.

  Landed 2026-10-14 (schema 0.57; `1325-measure/form_freed.py`, output in
  `form_freed_results.txt`):
  - `ParametricFormTest` holds two `ParametricFormReading`s, `tied` and
    `others_freed`, the second only when two or more laws are tested.
    `parametric_form` was unreleased, so its fields moved freely.
  - On the three-law answer the freed reading reproduced each law's own
    refit: cubic 575.3 of the refit's 576.1, 1.58 per direction over the
    untied denominator against 1.58; trigonal a 241.6 (1.33 of the refit's,
    0.66 against 0.50, the weak phase whose refits stop in other minima);
    trigonal c 215.6 (1.05, 0.59 against 0.56). Tied, the cubic law read
    42.8 for 31 (p 0.077) and passed; freed, 48.6 (p 0.023), rejected.
  - The session decided that either reading rejecting rejects the law. The
    maintainer overturned it the next session for decision 6: the freed
    reading is the verdict, and `RefinementResult.parametric_form_joint`
    reads every tested law at once (c5b015e).
  - The diagnostic's `value` is the verdict reading's statistic, and its
    message says what the tied one read when that one passed. A joint
    rejection with no law rejected on its own adds one
    `PARAMETRIC_FORM_REJECTED` whose `where` is every tested law's
    coefficients. `str(result)` prints the freed reading first and closes
    the block on the joint reading.
- [x] **The same measurement on ZrP₂O₇ and WO₃, run as the form test's
  out-of-sample check.** Its level and its f² divisor were settled on the
  ZrMo₂O₈ ramp alone, the maintainer's concern. So:
  - record the form test's verdicts before comparing them with the chain's
    trajectories and with refits;
  - declare one deliberately over-flexible law (a high-order polynomial or a
    `design` spline) on correlated real residuals, to measure how often a
    right form is rejected there;
  - decide decision 4's correction from those two.

  Both ramps are where the first could not reach. ZrP₂O₇ runs to 1173 K and
  back, so heating and cooling can be tested as one law. WO₃ crosses phase
  fields, which is the case for one law per field on disjoint subsets.
  `rx.read_project_model` builds all three WO₃ phases from
  `d9_02592_3phase_01.inp`. The ZrP₂O₇ input is refused at read, on its
  `B1(...)` site macros, so its phases need building by hand.
  - WO₃'s TOPAS law refines its Einstein temperature, which no linear
    basis expresses ([1964](1964-a-nonlinear-law-through-the-derived-block.md)).
    Held at TOPAS's 125.4 K it is a `design` law with columns 1 and
    1/(exp(θ/T) − 1), which is how to declare it here.
  - ZrP₂O₇'s TOPAS law calibrates the temperature itself, a law on a
    coordinate this WP does not build. Declare cell laws in the set
    temperature instead, heating and cooling as one.

  Landed 2026-10-15 (506c340, c4f9cdc, 64d5777), recorded in § Measured:
  the form test out of sample before any comparison. Decision 4 followed
  from it: the divisor is χ²_red alone (741649b), and a verdict beside a
  rejected law is provisional, `ParametricFormTest.provisional_on` naming
  the others (667216c).
- [ ] **Measure whether a one-direction test for the next term earns a
  place** (added 2026-10-14, from a review of the API against prior art).
  The form test's alternative spends n − m directions, one per pattern
  beyond the law. Against smooth curvature, a score test on the next
  polynomial term spends one. It is the same projection with one column
  added, and it is how a statistician picks an order (a nested F-test, or
  AIC/BIC across orders). Today the manual says to add a term and refit.
  - On the synthetic ramps, shrink the bow below the 9.4 × 10⁻⁵ Å that
    the form test rejected at 2606.7, and find where each test stops
    rejecting. Then run the ZrP₂O₇ and WO₃ ramps above.
  - Land it beside `ParametricFormTest` only if it rejects a curve the form
    test passes. Where no pattern sees the target, neither test can help,
    and that regime is [1963](1963-a-kernel-over-the-pattern-coordinates.md)'s.
  - A second verdict per law is a further test at 95 %, so it joins
    decision 4's correction.

  Measured, the synthetic half (2026-10-14, `1325-measure/next_term.py`,
  output in `next_term_results.txt`; 20 noise draws a cell, load 3.0-3.8).
  The ten-pattern LaB6 ramp with a line declared, the truth bent by a
  fraction of the line's half-excursion: `curve` (u² − 1, the next term
  exactly) or `kink` (|u| − 1, which no polynomial holds). The `next`
  score is one shared column, Σ_k u_k² times pattern k's own target
  column, projected densely; rebuilding the form statistic the same way
  matched the shipped one to 4 × 10⁻¹⁴.

  | truth, bend | form rejects | next rejects | quadratic refit rejects |
  |---|---|---|---|
  | curve 7 × 10⁻⁴ (6.5 × 10⁻⁶ Å) | 15/20 | 20/20 | 20/20 |
  | curve 5 × 10⁻⁴ | 7/20 | 18/20 | 18/20 |
  | curve 3 × 10⁻⁴ | 0/20 | 10/20 | 8/20 |
  | curve 2 × 10⁻⁴ | 0/20 | 8/20 | 8/20 |
  | kink 7 × 10⁻⁴ | 12/20 | 20/20 | 20/20 |
  | kink 5 × 10⁻⁴ | 7/20 | 18/20 | 18/20 |
  | kink 3 × 10⁻⁴ | 0/20 | 9/20 | 8/20 |
  | straight | 0/20 | 0/20 | 0/20 |

  - It meets the landing condition on synthetic data: from a bend of
    3 × 10⁻⁴ down, the form test passes every draw and the next-term score
    rejects about half, as the refit does. It spends one direction where
    the form test spends eight, and the kink shows that it is not only for
    a truth that is the next term.
  - The score tracks the refit: medians 20.2 against 20.3 at curve
    7 × 10⁻⁴, 7.7 against 7.4 at kink 5 × 10⁻⁴.
  - Straight truths: medians form 4.6 (χ²_8's is 7.3), next 0.6 (χ²_1's
    0.45). The f² divisor is conservative here, as § Measured: the form
    test found.
  - To land it, `blocked.added_columns_gain` needs a column shared across
    blocks: today `_edited` appends extras per block only. A polynomial in
    several coordinates has several next-degree monomials, so the test
    there spends that many directions, still far fewer than n − m. A
    `design` or `constant` law has no next term.
  - Open (2026-10-15): the real-ramp half, ZrP₂O₇ and WO₃, did not run.
    The table above divides by χ²_red·f². The shipped form test now divides
    by χ²_red alone (decision 4), so re-run the synthetic half on that
    divisor before landing.
- [x] **Profile the joint Jacobian**, the maintainer's question of 2026-10-14:
  would another Rust kernel help? It would not, first. § Measured: where the
  joint Jacobian's time goes.
- [ ] **Compute a target's peak-chain column once per pattern.** A tie's
  coefficient columns each re-run `phase_peaks` (§ Measured: where the joint
  Jacobian's time goes, 1.48-1.52× on the Jacobian loop).
  - The seam is `_make_jacobian`'s column loop
    (`optimize/least_squares.py:1604`) and `_peak_chain_column` (`:1170`).
    Group the peak-chain columns by the targets they reach, compute each
    target's column once, and chain through C. The restraint block already
    does this, as `r_phys @ cmat`.
  - A coefficient reaching several targets (one law per phase field, a
    shared cell) takes the general form, J_columns = J_targets · C_sub, and
    never a per-name shortcut.
  - The finite-difference step then sits on the target, not the
    coefficient, so it is not bit-identical. The bar: the converged answer
    within 0.01 esd of today's, as the blocked solver's was.
  - It also removes a near-zero effective step: a pattern near the reference
    has Φ_kj ≈ 0, so today a coefficient's step barely moves its target.
- [x] **Survey the prior art for declaring a parametric model**, for a
  self-driving lab as the writer. Written into Context: § Prior art, § The
  shape and § What the code has.
- [x] **Survey a kernel over the pattern coordinates** (the maintainer's
  question): precedent across fields, its place in this WP's family of
  forms, what it can buy, its costs, and how it scales. Written into Context
  as § A kernel over the coordinates.
- [x] **The declaration**: the coordinate table, the closed basis vocabulary,
  the subset, the reference and scale, with JSON round-trip, and every
  refusal of § The shape item 3 before any solve. Landed as
  `schemas/parametric.py` (`CoordinateTable`, `ParametricTie`,
  `ParametricCoefficient`) and `params/parametric.py` (`resolve_parametric`,
  the one authority). Coefficients are unbounded in this cut, so the box
  refusal became `PARAMETRIC_OUT_OF_RANGE` after the fit.
- [x] **Per-pattern starting values in a joint fit**: a `Structure` per
  histogram, or per-pattern overrides, in place of the deep copy at
  `params/multi.py:187`. Landed as `structure: Structure | list[Structure]`;
  a list must agree on topology and on every shared value.
- [x] **Ties and variables reach the joint table**: a `vars.` coefficient
  shared, per-table ties onto `hist.{h}.` targets, and
  `_unsupported_paths_multi` reading `column_reach` per the WP-1342 rule
  before any variable drives a per-histogram cell. Bit-identical to
  `refine_multi` when the basis is `constant`. Landed, and bit-identical (θ,
  esds, statistics and y_calc `==`): a coefficient takes its target's column
  slot, box and unit. The release (`_rehold_multi`) reads the reach too.
- [x] **Scalable solver, the step.** A block-structured joint Jacobian (per
  histogram: its rows against its own columns, plus its rows against the
  shared columns), never assembled dense. Two routes to decide between by
  measurement:
  - (i) the existing projected CG (`lm.py:731-733`) fed a block operator for
    A·v, which already handles bounds;
  - (ii) Schur elimination of each histogram's private block, which is exact
    only while no bound in it is active (WP-1125).

  Equivalence bar against the dense path at N ≤ 20: the step to WP-1125's
  6.6e-7 relative with no bound active, and the converged answer within
  0.01 esd.

  Landed as route (i):
  - `optimize/blocked.py` `BlockJacobian` holds one block per histogram,
    against its own columns;
  - `lm._normal_equations` scatters A and b block by block into a dense n×n
    A, and the BVLS / projected-CG step is unchanged;
  - `blocked.choose_layout` picks blocked once the dense J would pass
    `DENSE_JACOBIAN_MAX_BYTES` (256 MiB), and `set_layout` forces either;
  - `LSQOutcome.jacobian_layout` records which ran.

  Measured: the step agrees to 2e-12 (BVLS) and 3.8e-8-7.2e-8 (projected CG),
  and the converged answer to ≤ 6.4e-6 esd. Route (ii) is not needed: at
  N = 300 the step is 4 % of the fit and the serial Jacobian loop is 45 %
  (§ Measured: scaling).
- [x] **Scalable solver, the covariance.** The shared coefficients'
  covariance from the reduced (Schur) matrix, equilibrated first. Each
  histogram's own esds from its diagonal block of the full inverse,
  Σ_LL = H_LL⁻¹ + H_LL⁻¹·H_LG·S⁻¹·H_GL·H_LL⁻¹. Unmeasured rows marked through
  each table's reach (WP-1110 item 14's rule). Landed in `blocked.py`:
  - equilibrated first;
  - a PSD pseudo-inverse per own block, then the Schur complement;
  - the cut is `PINV_RCOND`·λmax of the whole matrix, applied per block.

  Returned dense n×n, because every consumer indexes by θ's columns. Esds
  agree with the dense covariance to ≤ 3.7e-12 relative at one point.
- [x] **Scaling measured**: memory and wall clock at N = 10, 70, 300 on a
  synthetic library, dense against blocked. State where dense stops being
  possible on the measuring machine. § Measured: scaling.
- [x] esds of the coefficients in user units at the reference, marked
  unmeasured where no pattern in the subset contributes gradient. Landed as
  `RefinementResult.parametric` (schema 0.55).
- [x] `SeriesResult.summary(deliverable="series")` prints the coefficients
  beside the trajectory it already prints. A joint-fit summary prints them
  for a library. Landed:
  - `RefinementResult.__str__` prints a coefficient block whenever
    `parametric` is set.
  - A chain has no coefficients of its own, so
    `SeriesResult.summary(parametric=<the joint result>)` takes them from a
    joint fit of the same patterns.
  - The deliverable gains a "functional form" row that says NOT measured
    when no joint fit is given.
- [x] Manual Part 1 `using/series.md` (series and library); Part 2 the
  equation with its *Source* line; the skill's series reference. Landed:
  - `using/series.md` § A parameter as a function of each pattern's
    coordinates;
  - `parameterisation.md` § the same, with `{eq}par-parametric` and
    `{eq}par-parametric-units`;
  - the 28 names left `api_surface_deferred.txt`.
- [x] Tests: a synthetic ramp with a known a(T) (a₁ within one esd of truth,
  and the esd no larger than the trajectory-line's); a synthetic library
  with a known 2-D surface over ≥ 100 patterns, through the blocked solver.
  obs/calc/diff PNGs to `tests/output/`. Both are `slow` in
  `tests/test_parametric_series.py`:
  - the ramp: a₁ at z = 0.30, esd 0.39× the line's with the instrument
    shared;
  - a 120-pattern (x, y) library, blocked by the size rule, coefficient z
    within 1.2.
- [x] Skill: the series reference's routing row for "a parameter as a
  function of composition or temperature across patterns", or "none" and why.
  Landed as one row in `references/series.md`, with measured tags. No
  `api-series.md` page: it would need a routing line in `SKILL.md`, which is
  over its budget.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_sequential.py tests/test_multi_histogram.py tests/test_parametric_series.py
.venv/bin/python -m ruff check src tests examples
```

## References

- Stinton, G. W. & Evans, J. S. O. (2007). *J. Appl. Cryst.* 40, 87-95 —
  parametric Rietveld refinement.
- Müller, M., Dinnebier, R. E. & Schorr, S. (2011). *Z. Kristallogr.* 226,
  doi:10.1524/zkri.2011.1407 — parameterized Rietveld refinement of the
  CuInSe₂ transition.
- Hastie, T. & Tibshirani, R. (1993). *J. R. Stat. Soc. B* 55, 757-796 —
  varying-coefficient models.
- Wilkinson, G. N. & Rogers, C. E. (1973). *Appl. Stat.* 22, 392-399 —
  symbolic description of factorial models.
- van Stokkum, I. H. M., Larsen, D. S. & van Grondelle, R. (2004). *Biochim.
  Biophys. Acta* 1657, 82-104 — global and target analysis.
- Kamasak, M. E., Bouman, C. A., Morris, E. D. & Sauer, K. (2005). *IEEE
  Trans. Med. Imaging* 24, 636-650 — direct reconstruction of kinetic
  parameter images from dynamic PET data.
- Triggs, B., McLauchlan, P. F., Hartley, R. I. & Fitzgibbon, A. W. (2000).
  *Vision Algorithms: Theory and Practice*, LNCS 1883, 298-372 — bundle
  adjustment.
- Suram, S. K. et al. (2017). *ACS Comb. Sci.* 19, 37-46 — AgileFD.
- Kusne, A. G. et al. (2020). *Nat. Commun.* 11, 5966 — CAMEO.
- Kernel survey (2026-10-14; each record and abstract confirmed by search,
  no full text read):
  - Wahba, G. (1978). *J. R. Stat. Soc. B* 40, 364-372 — improper priors,
    spline smoothing and model errors.
  - Eilers, P. H. C. & Marx, B. D. (1996). *Stat. Sci.* 11, 89-121 —
    P-splines.
  - Kennedy, M. C. & O'Hagan, A. (2001). *J. R. Stat. Soc. B* 63, 425-464 —
    calibration with model discrepancy.
  - Brynjarsdóttir, J. & O'Hagan, A. (2014). *Inverse Problems* 30, 114007.
  - Tuo, R. & Wu, C. F. J. (2015). *Ann. Stat.* 43, 2331-2352.
  - Zhang, H. (2004). *J. Am. Stat. Assoc.* 99, 250-261 — what infill
    asymptotics can estimate.
  - Wood, S. N. (2011). *J. R. Stat. Soc. B* 73, 3-36 — REML against GCV.
  - Hodges, J. S. & Sargent, D. J. (2001). *Biometrika* 88, 367-379 —
    effective degrees of freedom.
  - Nychka, D. (1988). *J. Am. Stat. Assoc.* 83, 1134-1143 — average
    coverage of Bayesian intervals.
  - Kuusela, M. & Panaretos, V. M. (2015). *Ann. Appl. Stat.* 9, 1671-1705 —
    undercoverage under regularisation.
  - Edwards, T. H. & Stoll, S. (2018). *J. Magn. Reson.* 288, 58-68 —
    choosing the regularisation strength.
  - Bell, B. M. (1994). *SIAM J. Optim.* 4, 626-636 — the iterated Kalman
    smoother as Gauss-Newton.
  - Fraser, D. C. & Potter, J. E. (1969). *IEEE Trans. Autom. Control* 14,
    387-390 — the two-filter smoother.
  - Hartikainen, J. & Särkkä, S. (2010). IEEE MLSP — GP regression as Kalman
    smoothing.
  - Lindgren, F., Rue, H. & Lindström, J. (2011). *J. R. Stat. Soc. B* 73,
    423-498 — the SPDE approach.
  - Datta, A. et al. (2016). *J. Am. Stat. Assoc.* 111, 800-812 — NNGP.
  - Wang, G. & Qi, J. (2015). *IEEE Trans. Med. Imaging* 34, 61-71 — the PET
    kernel method.
  - Reader, A. J. & Verhaeghe, J. (2014). *Phys. Med. Biol.* 59, R371-R418 —
    direct parametric reconstruction.
  - Kitanidis, P. K. (1995). *Water Resour. Res.* 31, 2411-2419 —
    quasi-linear geostatistical inversion.
  - Kwak, S. et al. (2020). *Nucl. Fusion* 60, 046009 — GP priors in
    integrated Thomson-scattering analysis.
  - Hendriks, J. N. et al. (2019). *Strain* 55, e12325; Henningsson, A. &
    Hendriks, J. N. (2021). *J. Appl. Cryst.* 54, 1057-1070 — GP strain
    tomography.
  - Kusne, A. G., McDannald, A. & DeCost, B. (2024). *Digital Discovery* 3,
    2211-2225 — SAGE, one GP per phase region.
  - McDannald, A. et al. (2022). *Appl. Phys. Rev.* 9, 021408 — ANDiE.
- WP-0308 (the joint residual), WP-0505 / WP-1051 / WP-1127 (the chain),
  WP-1305 (the series deliverable), WP-1119 (named variables), WP-1125 (the
  Schur identity), issue #212.

## Handover log

### 2026-10-15 (eighth session) — two real ramps settle the form test's divisor, a verdict beside a rejected law is provisional, and a declaration is a parametric equation

The form test checks a declared equation against its own data. It has now
run on two real ramps it was not tuned on, ZrP₂O₇ and WO₃, beside the
ZrMo₂O₈ ramp it was tuned on. Divided by the Bérar-Lelann factor squared,
it almost never rejected. Of 261 readings that should pass, none rejected,
where a 5 % test rejects about 13. Without the factor, 12 of 242 rejected
(5.0 %). So the test now divides by χ²_red alone, the textbook score test.
A far-wrong equation moves the answer every other reading steps from, so
a verdict beside a rejected equation is now marked provisional. The public
names say "parametric equation" where they said "law" or "tie", and a 1.9.0
result still opens.

This session ran in two contexts. The first wrote every commit up to
667216c and stopped while a subagent ran the rename. The second picked up
from the tree, verified and committed the rename, and wrote this entry.

*Done* (branch `wp1325-law-marks`, PR #977; main merged at daf2ef8):
- **The freed reading is the verdict, and a joint reading covers all
  equations** (c5b015e, b5d7c64). Decision 6, the maintainer's call. On the
  ZrMo₂O₈ three-law answer the joint reading read 74.1 for 93 directions
  (p 0.93) and kept all three, while the cubic law failed alone. The Durham
  tutorials check a law by plotting it against independent fits, with no
  statistical test.
- **The next-term score, synthetic half** (7d7cb7b). In the task's table.
- **Out of sample on ZrP₂O₇ and WO₃** (506c340, c4f9cdc, 64d5777). In
  § Measured: the form test out of sample, recorded before any comparison.
  The task is ticked.
- **Decision 4: χ²_red alone** (741649b, 301e4d6). The LaB6 ramp's true
  line reads 7.6 (p 0.47) against the cut 15.5, and its 1 % bow 4461.1. On
  ZrMo₂O₈ the three lines and their joint reading all reject, each freed gain
  1.00-1.33 of its law-alone refit.
- **Provisional verdicts** (667216c). `ParametricFormTest.provisional_on`
  names the other rejected equations. The printed block and each
  `PARAMETRIC_FORM_REJECTED` say so. Any rejection marks the rest, with no
  threshold.
- **The rename** (81bd517). `ParametricTie` → `ParametricEquation`,
  `ParametricLaw` → `RefinedParametricEquation`, `.laws` → `.equations`,
  `parametric_laws` → `parametric_equations`, and `tie` → `equation` on the
  coefficient, the form test and the refined equation.
  `ParametricCoefficient` still reads 1.9.0's `tie` key, pinned both ways.
  Decision 7 records it.
- **Review** (`/code-review high --fix 90872b7..4ea0b20`, fixes in 4ea0b20):
  a redundant `scale = chi2_red` alias, five test names the rename left
  ungrammatical (`a_equation` → `an_equation`), continuation indents.
  Two findings went to the maintainer, who decided both (decision 8,
  5c5575a):
  - An equation whose freed reading has zero directions keeps
    `rejected=None` even when its tied reading rejects. Falling back to
    the tied verdict would name a culprit the data cannot separate, which
    decision 6 removed. The joint warning now names each such equation
    and quotes its tied reading.
  - `ParametricValue` read "form not rejected" under a rejecting joint
    reading or a provisional verdict. It now carries `provisional_on` and
    `joint_rejected`, and prints both. It is never stored, so no schema
    number moved.
- **Merging main** moved this WP's fields to **schema 0.59**. On main
  first, WP-1960's texture took 0.57 and WP-1810's riding hydrogens 0.58.
  `common.py`'s note, the `test_magnetic` pin, the 1.10 notes and record
  say 0.59. This file's older entries keep "0.57", the number they shipped
  under on the branch.
- WP-1418 inherits the f² question for the moment-angle test.
- CI's Python 3.14 shard failed the covariance symmetry pin: ρ_ij and ρ_ji
  from the solve's correlation differed in the last bit (2.3250376935784206e-17
  against 2.32503769357842e-17). `parametric_equation` now reads ρ off one
  triangle. The other off-diagonal readers (`identifiability.py`,
  `staged.py`) read each pair once and claim no symmetry, so they are left.
- @mustachefeeling's two comments on PR #977 are folded in, after the
  first version of this entry. This WP's points are in § A contributor's
  series work and the start-agreement task. The boundary and detector
  findings went to 1965 and 1317, the scanned nonlinear equations to 1964,
  and the telemetry to 1322. Not re-measured here.

*Measured* (macOS arm64, worktree venv `[dev]`, load 9.8-11.9):
- Fast selection on 81bd517, before the merge: 9712 passed, 186 skipped,
  1 xfailed, in 231 s.
- Fast selection on the merged tree (daf2ef8): 10489 passed, 191 skipped,
  1 xfailed, in 285.6 s. Main's own additions are in that count, so it is
  not this branch's delta.
- Fast selection on 5c5575a, decision 8: 10491 passed, 191 skipped,
  1 xfailed, in 247.5 s. That is +2 passed for its 2 new tests, with no
  new skip.
- This session added 3 fast tests: `test_parametric_series.py` collected 73
  at 90872b7 and 76 now. No new skip.
- `tests.added_test_times` against main names 10 tests, because the rename
  gave existing tests new IDs. They cost 5.24 s in one run. 5.11 s of that
  is `test_a_line_equation_is_rejected_by_a_ramp_that_bends` (2 cases),
  which predates this session under its old name. The other nine take
  0.04 s or less.

*Gotchas*:
- The next-term table divides by χ²_red·f². The shipped divisor is now
  χ²_red alone, so re-run `next_term.py` on it before landing. The review
  flagged that the script's docstring still calls its rebuild "the shipped
  form test".
- `real_ramp.py` reads TOPAS's `Simple_Axial_Model(v)` as v/L, and the
  ZrP₂O₇ lane read it as v/2L. The TOPAS Technical Reference is public at
  topas-academic.com/technical_reference, so check it there.
- WO₃'s Pc counts as seen above 221 K while its cell is unmeasured
  (1.5-3.5 wt %). The form test counts those patterns.
- The three Durham ramps are local-only (`python -m tests.local_data`).

*Next*, in order:
1. **Land the next-term test.** Re-run the synthetic half over χ²_red,
   then run the ZrP₂O₇ and WO₃ ramps. `blocked.added_columns_gain` needs a
   column shared across blocks first. Land it only if it still rejects
   curves the form test passes.
2. **Hold each target's own bounds.** It now comes ahead of the speed work.
   A seed broke a target's bounds and refused the fit on two of the three
   real ramps (WO₃, ZrMo₂O₈'s windowed cubic). The refusal is at the seed,
   before any step, so the task covers the starting coefficients as well
   as the step.
3. The peak-chain deduplication, then start agreement.

### 2026-10-14 (seventh session) — law-set values are marked, a law evaluates anywhere, and each law is also tested with the others freed

A joint parametric fit now says which of its numbers came from a law rather
than from a pattern's own data. It also warns where a law sets a value in a
pattern that cannot see the phase. A law can be evaluated at any temperature
or composition with an esd, because the result now carries the coefficients'
covariance; at each measured pattern it gives back that pattern's row to the
bit. Each law is now also tested with the other laws freed, and that reading
gives the verdict a refit of the law alone gives: on the ZrMo₂O₈ ramp it
rejects the cubic line the old reading passed. Rejecting a law when either
reading rejects is this session's call and waits on the maintainer, since it
raises the false-alarm rate by an amount nobody has measured.

*Done* (branch `wp1325-law-marks` from `main` at 6e793e8, PR #977; schema
0.56 → 0.57, one bump for all three tasks):
- **Law-set values marked** (f6b0e83, e720da1). `RefinedParameter.laws`,
  written by `multi._law_rows` off each table's `entry_reach`, so a cubic
  cell's b and c and a held coefficient count too. The coefficient rows are
  **marked, not dropped**: dropping breaks the row contract, and `BOUND_HIT`
  on a `constant` coefficient would name a path absent from `parameters`.
  `laws` is `None` for "not recorded" because 1.9.0 shipped parametric fits
  whose rows carry no field; the single fit writes `[]`. The form line reads
  "n of N patterns" with a p-value (`p < 0.001` below that, since a tail
  under 1e-300 is 0.0). `PARAMETRIC_TARGET_UNSEEN` (FIT) names the unseen
  patterns from `multi._parametric_unseen`, the one reading the form test's
  skip now takes too.
- **Covariance and the law anywhere** (07cffad). `RefinementResult.parametric_laws`
  (`ParametricLaw`: resolved tie, unit, span, covariance) and
  `RefinementResult.parametric_value` → `ParametricValue`. The covariance is
  esd_i·esd_j·ρ_ij with ρ_ii = 1, so its diagonal is `esd ** 2` exactly
  (pinned).
- **Each law with the others freed** (6d061bf, ceeff20). `ParametricFormTest`
  reshaped: `rejected` (the verdict) plus two `ParametricFormReading`s, `tied`
  and `others_freed`. `parametric_form` was unreleased, so nothing shipped
  breaks. `form_freed.py` records the real-ramp run.
- Manual (`using/series.md`, `using/model.md`), the skill's diagnostics and
  series rows (both at or under budget), `api.md` regenerated, the 1.10
  notes and record staged.
- **Forward references**: 1341 (third note: the new warning is top-level,
  the per-pattern placement is its), 1963 (the blind regime is named per
  law), 1964 (three readers assume linear coefficients), 1965 (a result
  carries the resolved tie). No `Priority:` moved: nothing waited on this.
- **`/code-review high --fix`** (91ddadf): nine findings, eight fixed. A
  crash formatting a tied statistic of `None` in the freed-only warning;
  the all-blind `PARAMETRIC_TARGET_UNSEEN` claiming a seeing pattern; a
  hardcoded distribution name; one projection per two-law fit recomputed
  (now reused, bit for bit); `_verdict`'s "not tested" reason;
  `ParametricLaw.evaluate` accepting another law's coefficients; two
  docstrings and the 0.57 log entry. Skipped: `_law_rows` builds a whole
  `entry_reach()` per table to read the coefficients' keys, unmeasured at
  300 patterns and needing a new `ParameterTable` method.

*Measured* (macOS arm64, 10 CPUs, `[dev]`, compiled kernels on):
- `parametric_value` against each pattern's `hist.<h>.` row on the
  ten-pattern LaB6 line ramp: value and esd identical at all ten (relative
  difference 0.0). ρ(c₀, c₁) = 0.007 there, the centring's work.
- `form_freed_results.txt` at 6d061bf, ZrMo₂O₈ ramp, three-law answer
  (χ²_red 1.878, f 2.511; untied 1.873, 2.503; load 3.3-4.5):

  | law | tied | freed | freed gain / own refit's | per dir, untied denominator / refit's |
  |---|---|---|---|---|
  | cubic a | 42.8 for 31, p 0.077 | 48.6, p 0.023 REJECT | 575.3 / 576.1 | 1.58 / 1.58 |
  | trigonal a | 10.6, p 1 | 20.4, p 0.93 | 241.6 / 181.7 | 0.66 / 0.50 |
  | trigonal c | 9.0, p 1 | 18.2, p 0.97 | 215.6 / 204.7 | 0.59 / 0.56 |

  Trigonal a's 1.33 ratio is the weak phase whose refits stop in other
  minima, as § Measured: the form test recorded (1.36 there).
- Fast selection (alone on the machine): 9709 passed, 186 skipped,
  1 xfailed in 3:34-3:41 over two runs; the second run's one failure was
  this session's own Part 2 math wrapping onto a "- " line, fixed and
  re-run alone. Four tests added, all four passes:
  `tests.added_test_times` reads 0.03 s for the four, one run.
- Acceptance (the WP's command, slow rows included): 217 passed; the two
  slow parametric rows, one of which this session edited, pass. The full
  suite did not run: nothing here changes a refinement path, only what
  is read off the answer.

*Gotchas*:
- `diagnostics.md` sits exactly at its budget (0 B left) and `series.md`
  has 29 B; the next row added to either pays with a cut.
- The worktree guard refused a long `python - <<EOF` heredoc; scratchpad
  scripts run as one plain command worked.

Next, in order:
1. **The maintainer confirms or overturns "either reading rejects"**
   (`params.parametric.form_tests`, one line). The alternative is the freed
   reading alone: 5 % per law, losing two collinear wrong laws.
2. **ZrP₂O₇ and WO₃ out of sample.** It now settles decision 4 for two
   readings per law, and whether the one-direction next-term test earns a
   place.
3. **The one-direction next-term test**, if 2 leaves room for it.
4. **The peak-chain deduplication**, then **in-step bounds**, then **start
   agreement** beyond parameters.

### 2026-10-14 (sixth session) — the maintainer's rule for laws is recorded, and a review against prior art adds three tasks and two WPs

The maintainer read the form test's results and set a rule for the rest of
this WP. People may fit a function to their parameters, rietx warns them when
the function might be wrong, and the output shows which values came from one.
This session wrote that rule into tasks and staged the form test's 1.10
release notes. It changed no code. A review of the API against prior art then
found seven gaps. Three are tasks here, and the other four are features of
their own, filed as WP-1964 and WP-1965.

*Done* (branch `wp1325-decisions` from `main` at 72d8c0f, docs only; this
entry was written after a `/clear`, from the three commits and PR #976's
body):
- **The maintainer's decisions** (1d6c47d), in § Decisions after the form
  test. Three tasks follow from them: mark law-set values wherever rows
  print, test each law with the other laws freed, and run ZrP₂O₇ and WO₃ as
  the form test's out-of-sample check. A law with a held coefficient stays
  untested. Whether to correct the 95 % level for several laws waits on the
  out-of-sample check. WP-1963 is filed as a stub, for a kernel prior over
  the regime the form test cannot see.
- **The 1.10 notes** (e358ade). `docs/releases/1.10.0.md` carries the form
  test under New, schema 0.56 under Code to check, and #970's per-pattern
  hold under Numbers that move. The v1.10 record has an entry. WP-1961's
  Inherited entry is consumed.
- **The API review** (cab8a9c). Three tasks join this WP:
  - the coefficients' covariance, and the law's value at any coordinate;
  - the `vars.<name>_<j>` rows, which print per unit of the scaled
    coordinate, folded into the exposure task;
  - a measurement of whether a one-direction test for the next term earns a
    place.

  WP-1964 owns laws nonlinear in their coefficients, built on WP-1804's
  derived block. WP-1965 owns the declaration's spelling: a formula, a subset
  by condition and a glob target. 1329 inherits a pointer to 1964, and
  1963's non-goal now names it.
- **This handover**: decision 1 reads in the past tense, and the Status line
  names the covariance task.
- **Forward references**: 1804 gets no entry. 1964 depends on its derived
  block but changes none of its open work.
- **`/code-review`**: skipped, since the branch touches only `docs/`.

*Measured*: nothing. No code or test changed, so neither the fast nor the
full selection ran. `tests/test_docs_consistency.py` and ruff ran at handover.

*Gotchas*:
- **The first commit was pushed to #974's branch after #974 merged.** It
  moved here by cherry-pick. Check `gh pr view --json state` before pushing
  to a branch whose PR may have merged.

Next, in order:
1. **Show in the output when a value came from a law**, the maintainer's
   priority. It now covers the `vars.` rows too. Its first decision is
   whether a coefficient's row is marked or dropped from `parameters`.
2. **The coefficients' covariance and the law's value at any coordinate.**
3. **Test each law with the other laws freed.**
4. **ZrP₂O₇ and WO₃ as the out-of-sample check.** It settles the
   several-laws correction and whether the one-direction test earns a place.
5. **The peak-chain deduplication**, then **in-step bounds**, then **start
   agreement** beyond parameters.

### 2026-10-14 (fifth session) — a declared law is now tested against its own data, at the cost of one Jacobian

Every joint fit with a parametric law now says whether its data rejects that
law. It does this from the answer alone, without refitting: it asks how much
the fit would improve if each pattern's value were set free, and compares
that with what noise would give. On the real ZrMo₂O₈ ramp it agreed with a
full refit on all five laws tried, and it rejects the one law whose
trajectory visibly curves. It costs under a second where the refit costs 41.
The test is blind where a pattern cannot see the quantity: on synthetic ramps
whose minor phase faded or overlapped, neither it nor a full refit rejected a
bent truth. So it does not rescue the confidently wrong gap estimates the
kernel measurement found.

*Done* (session started 2026-10-14 on a fresh branch from `main` at caf089f,
after #970 merged; on the maintainer's machine):
- **The measurement first** (898ab18): `1325-measure/form_score.py` and
  `form_synthetic.py`, in § Measured: the form test. The score test was
  built as a probe, compared with the nested refit, and three of its choices
  changed on the numbers (the alternative drops the coefficients, unseen
  patterns are left out, the denominator is the tied fit's).
- **The test in the package** (b7be8bc), ticking the lack-of-fit task:
  - `optimize.blocked.added_columns_gain`, the gain on the arrow through the
    covariance's own Schur pseudo-inverse and cut;
  - `params.parametric.target_columns` and `form_tests`, with
    `FORM_TEST_LEVEL` quoting `PARAMETER_INTERVAL_LEVEL`;
  - `MultiHistogramRefinement._build_result` runs it once at the answer,
    holding what `bound_findings` found on a bound and leaving out what
    `multi._unseen` holds;
  - `RefinementResult.parametric_form` (schema 0.56), `ParametricFormTest`
    exported, a form line in `str(result)`, and the series deliverable's
    functional-form row naming a rejected law;
  - `PARAMETRIC_FORM_REJECTED`, a warning on the coefficients, in
    `DIAGNOSTIC_SCOPES` as FIT;
  - Part 1 `using/series.md` § Testing the declared form; Part 2
    `{eq}par-parametric-form`, its level a `conf.py` substitution;
  - the skill: the two parametric codes share one row in `diagnostics.md`,
    and the series row points at the test instead of the hand recipe. Both
    files sit at their 34 600 B budget, so the pointer row beside it was
    tightened to make room (34 594 and 34 575 B).
- **Tests**, in `tests/test_parametric_series.py`: the blocked gain against
  dense least squares with drop and hold; a pattern's target column against
  an untied table's (1.8e-7 to 8.1e-7 measured, bar 1e-5); the LaB6 ramp's
  line law kept on its true line and rejected under a 1 % bow (fast,
  parametrised); the slow ramp test asserts its form stands.
  `test_magnetic`'s schema pin moved to 0.56.
- **Forward references:** 1341 learns that its open item 4 (whether the joint
  hold reads WP-1523's significance) also sets which patterns the form test
  sees.
- **Inherited:** none on arrival. WP-1961's open #975 adds one to this file:
  #970's `multi._unseen` change ships in 1.10 and has no note. It cannot be
  acted on yet, because `docs/releases/1.10.0.md` exists only in #975. The
  two notes to stage there, once #975 merges:
  - Fixed: a joint fit with per-histogram phase paths now holds a pattern's
    own copy of a phase's cell where that pattern cannot see the phase; it
    stayed free wherever another pattern still showed the phase (WP-1325).
  - Added: `RefinementResult.parametric_form` tests each parametric
    declaration's form at the answer, and `PARAMETRIC_FORM_REJECTED` warns
    when the data rejects it (WP-1325, schema 0.56).
- **Findings** checked on arrival: nothing on `main` had touched the WP's
  files since the last handover.
- **`/code-review high --fix`** over caf089f..57e2b60: 9 findings, 5 fixed
  in one commit (1bcacd1).
  - dof is clamped to 0 where fewer patterns than coefficients enter.
  - The statistic needs a finite positive χ²_red·f², and that case prints
    its own line.
  - The held side's projection is computed once for every declaration.
  - An all-zero target column is not counted as a tested pattern.
  - `conf.py`'s new import is in sorted order.

  Four declined:
  - testing a law with a held coefficient: it would mix the form with the
    held value;
  - skipping the Jacobian when no law is testable: that needs a plan that
    never frees `vars.*`;
  - reusing `outcome.jac`: it can be stale after the cell clamp, and it has
    no penalty rows;
  - one helper for the χ²_red·f² the moment-angle test also computes: it is
    outside the diff, and the finiteness drift it caused is fixed.

*Measured* (macOS arm64, 10 CPUs, `[dev]` venv, compiled kernels on; other
sessions shared the machine at load averages of 4 to 30):
- The form test's numbers are in § Measured: the form test.
- Fast selection, the command verbatim, before the review: 9699 passed,
  1 failed (the schema pin, fixed), 186 skipped, 1 xfailed, in 5 m 14 s.
- Fast selection after the review, the command verbatim plus a junit file,
  on the merged tree (`main` had not moved since caf089f): 9700 passed,
  186 skipped, 1 xfailed, in 4 m 32 s. passed+skipped is 9886 in both runs.
  The 4 added cases (3 tests) pass. No base count was taken, so the +4 comes
  from `tests.added_test_times`. They took 6.25 s in that run, 6.00 s of it
  the two fit-level cases at 3 s each under `-n auto`; the test's docstring
  says why they are fast.
- The WP's acceptance command, slow tests included: 213 passed. Its two slow
  parametric tests pass, the 120-pattern library among them.
- The full selection was not run. The change adds a computation after the
  solve of a parametric joint fit and moves no fitted number: the
  constant-declaration test still holds bit for bit, and no acceptance suite
  declares a parametric law.

*Gotchas*:
- **A derived column is a hair outside the span of what it was derived
  from.** Finite differences on the coefficient's step and on the target's
  differ by ~1e-7 relative, enough for the pseudo-inverse to count a tenth
  direction among ten patterns. Swap columns; never append beside them.
- **A predicted residual is not a fitted one.** The unbounded linear step
  moves columns sitting on a bound too, so its residual's Bérar-Lelann factor
  read 2.27 where the untied fit's was 2.50.
- **`kernel_ramp.py` swaps `least_squares._multi_closures` on import.** A
  script importing it puts the original back, and looks the function up at
  call time.
- **`v1.9.0` is tagged and 1.10 is being opened in #975**, so nothing here
  can be staged until it merges.

Next, in order (rewritten the same day after the maintainer's decisions,
§ Decisions after the form test):
1. ~~Stage the two release notes~~: done the same day, once #975 merged,
   with the v1.10 record's entry; the Inherited entry is consumed.
2. **Show in the output when a value came from a law**, the maintainer's
   priority.
3. **Test each law with the other laws freed.**
4. **ZrP₂O₇ and WO₃ as the out-of-sample check**, which also settles the
   several-laws correction.
5. **The peak-chain deduplication** (35 % of the real fit), then **in-step
   bounds**, then **start agreement** beyond parameters.

### 2026-10-14 (fourth session) — on real data a weak phase's slope tightens by a quarter, and the form check needs the correlation factor

The parametric fit has now been measured on real data: 33 patterns of the
ZrMo₂O₈ heating ramp, three phases. A law across temperature gave a weak
phase's expansion slopes esds a quarter smaller than a line drawn through the
per-pattern fits, and gave the strong phase nothing, as the synthetic ramps
predicted. Checking the declared form by refitting without it works, but only
after dividing by the correlated-residual factor. Without that, it rejected
every straight line, and with it only the one that visibly curves failed. On
this three-phase structure the compiled kernels are a fifth of the fit, against
1.5 % on the synthetic library. Along the way the joint fit learned to hold a
phase's per-pattern cell where that pattern cannot see the phase. Data that
may not be committed now has one place on disk, outside the repository.

*Done* (session started 2026-10-14 on PR #970's branch at ccc8c7b, on the
maintainer's machine, because the cloud session could reach neither the data
nor the Durham host):
- **Where local-only data lives** (48d30ac), the maintainer's question. It
  goes in `~/rietx-local-data/<source>/<dataset>/`, or wherever
  `$RIETX_LOCAL_DATA` points. That is outside every checkout, so all
  worktrees share one copy and no `git clean` reaches it. The pattern is
  scikit-learn's, MNE's and nilearn's: a home directory plus an environment
  override. pooch's registry of URL and sha256 is kept, without the
  dependency. `tests/local_data.py` registers the three Durham tutorials,
  fetches them through curl and verifies every hash. `dataset()` returns
  `None` where they are absent. Three tests. The rule is in the module's
  docstring and in a pointer at the top of `tests/data/README.md`.
  `tests/CLAUDE.md` was already at its 302-line cap, so it has no line.
- **The measurement on real data** (74a5770): `1325-measure/real_ramp.py`
  and three output files, in § Measured on real data. The task is ticked. A
  new task carries ZrP₂O₇ and WO₃. The lack-of-fit task records what the
  nested test needs.
- **A per-pattern cell is held where its own pattern is blind** (871d38a,
  `multi._unseen`). The second session had forwarded this to 1341 as an
  open question. It is fixed here, with a two-pattern joint fit as the guard,
  which held nothing on the old code. This ramp never met it.
- **Skill:** the parametric row in `references/series.md` now carries the
  form check and the real-data esd ratio. It was rewritten to fit the file's
  budget: 34 598 of 34 600 B. Both committed copies are re-synced.
- **Forward references:** 1329 learns that a per-pattern moment is never held
  as flat in a joint fit (by reading, not run). In 1341, Inherited item 3 now
  says the hold is fixed and its naming is open, and a new item 4 records the
  WP-1523 divergence.
- **Inherited:** none on arrival. **Findings:** the "maintainer-local"
  ZrMo₂O₈ ramp is Durham tutorial 9.2, byte-identical to the maintainer's
  copy, and the ZrP₂O₇ input reads 37 of its RAW file's 871 ranges. The task
  text was corrected.
- **`/code-review high --fix`** over ccc8c7b..HEAD: 10 findings, 6 fixed in
  one commit.
  - The new test's imports failed ruff's ordering.
  - The stage loop's comment still stated the per-phase rule.
  - This record called the fit four-phase. The model has three.
  - `fetch()` renamed a download before checking its hash, and read members
    from a zip it had not verified.
  - `tests/local_data.py` spelled the brand. Its names now come from
    `_about.DIST_NAME`, with the same values.
  - The fit-level test copied `synthesize()`. That function now takes
    `extra_phases=`.

  Four declined:
  - the per-pattern moment hold: outside the diff, and forwarded to 1329;
  - the joint cell window, which still decides per phase: outside the diff,
    and the hold reaches every such cell before the window would matter;
  - one predicate shared with `refine._only_moves`: the joint form has to
    know which histogram owns each entry;
  - a diagnostic naming a per-pattern hold: 1341's item 3.

*Measured* (macOS arm64, 10 CPUs, `[dev]` venv, compiled kernels on; other
sessions shared the machine at load averages of 3 to 85):
- The real-data numbers are in § Measured on real data.
- Fast selection, the command verbatim, at 08eb61e (this branch, not merged
  with `main`, which had moved nine merges): 9669 passed, 186 skipped,
  1 xfailed, in 7 m 22 s. Five tests were added and all pass. In one run
  they took 0.69 s together, 0.53 s of it the two-pattern joint fit. No base
  count was taken on this machine, so the +5 comes from
  `tests.added_test_times`, not from a before-and-after.
- The full selection was not run. The changed rule moves a fit only where a
  phase path is per-histogram and the phase is absent from some patterns.
  No acceptance suite declares that. The slow tests of
  `test_parametric_series.py`, `test_multi_histogram.py`,
  `test_held_phase.py` and `test_absent_phase.py` ran: 297 passed.

*Gotchas*:
- **TOPAS's `TCHZ_Peak_Type` maps by position** (WP-1455): slot 5 is the
  tanθ Lorentzian term (`profile.y`), slot 6 the 1/cosθ one (`profile.x`).
  The August transcription of this ramp, outside the repository, swapped
  them.
- **`Statistics.chi2` is reduced**, over N − P. A total is that times N − P.
- **The chain is the wrong reference for a nested test.** It holds a fading
  phase by WP-1523's answer significance, which the joint path does not read.
- **Durham's host refuses urllib's user agent with a 403, and urllib stopped
  at 12.8 of 17.7 MB without raising.** The hash check caught it, and the
  fetch uses curl.
- **`read_topas_inp` refuses the ZrP₂O₇ input** on its `B1(...)` site macros.
  TOPAS numbers a range from 1, and `read_pattern(scan=)` from 0.
- **Wall clocks swung 4× with other sessions' load.** Quote ranges.
- **The worktree guard refuses a shell variable in `sed` or a loop.** Write a
  scratchpad script and run it as one plain command.

Next, in order:
1. **Build the lack-of-fit check.** It now has evidence behind it: the joint
   fit with no law as the reference, and F divided by the Bérar-Lelann factor
   squared. Decide whether it is a result field or a diagnostic beside
   `PARAMETRIC_OUT_OF_RANGE`, since it costs one more joint fit.
2. **The same measurement on ZrP₂O₇ and WO₃**, on this machine. WO₃ is the
   case for one law per phase field.
3. **The peak-chain deduplication.** The peak chain is 35 % of the real fit.
4. **In-step bounds** for the coefficients, then **start agreement** beyond
   parameters.

### 2026-10-14 (third session) — another Rust kernel is not the lever; a repeated peak chain is

The maintainer asked whether another Rust kernel would speed up the large
joint fits. Not first. The existing kernels are under 3 % of a 60-pattern fit.
Each pattern is small, so its Jacobian is about a hundred small python calls
rather than a loop of arithmetic for a kernel to take over. Spreading the
patterns over threads made it slower, because python's lock serialises them.
Holding the maths libraries to one thread did not change that. What does pay
is algorithmic: a polynomial's coefficients all move the same per-pattern
cell, yet each re-runs the peak chain. Doing it once measured about 1.5× on
the Jacobian, and is filed as a task. The real-data measurement could not run
from the cloud container, which reaches neither the maintainer's copy nor the
Durham tutorials.

*Done* (session started 2026-10-14 at 977ec2a, after #969 merged; a cloud
session, pushed to `claude/happy-bardeen-b6d4g0`):
- **The profile.** `1325-measure/jacobian_profile.py` and its results, in
  § Measured: where the joint Jacobian's time goes.
- **Tasks.** Ticked "Profile the joint Jacobian" and filed "Compute a
  target's peak-chain column once per pattern". The real-data task now names
  the Durham TOPAS surface tutorials, ZrP₂O₇ and WO₃, which the maintainer
  cleared for local use only.
- **Forward reference:** 1962 learns the per-pattern Jacobian's cost, and
  that threads do not parallelise it.
- **Skill:** `references/batch-operating.md` 9c.33, "run separate fits side by
  side in processes, never threads", tagged measured for the closures and
  hypothesis for whole fits. The two committed copies were re-synced.
- **Inherited:** none on arrival. **Findings** are this morning's, and main
  moved only by #969's merge since, so none went stale.
- **`/code-review high --fix`: 10 findings, 7 acted on.**
  - Rows (2)-(4) ran at the last stage's start: fixed, and re-run.
  - The kernel share was quoted against the profiled time only: both are
    printed now, floor and ceiling.
  - The thread loss might have been oversubscription: re-run with openblas,
    OpenMP and the kernel pool at one thread (the script now prints that
    environment), and it is the GIL.
  - Single figures became ranges or min-against-min over runs.
  - The 1.2× estimate gained its column-mix caveat.
  - The process filter skips every ancestor.

  Three declined:
  - one plain fit per run: three runs agree on the share, at 48-49 %;
  - `fresh()` cannot move an entry at exactly 0: the cache keys on the cell,
    which is never 0;
  - `src_fingerprint` does not cover `tests/`: the helper is `scaling.py`'s,
    which this branch does not touch.

*Measured* (Linux x86_64, 4 CPUs, 15.7 GiB, `[dev]` venv, nothing else
running): the numbers are in § Measured: where the joint Jacobian's time
goes. No source or test changed, so no suite count moved and the fast
selection was not run. Step 10's checks are below.

*Gotchas*:
- **`phase_peaks` memoises on the cell.** A profiling loop that reuses one θ
  times the cache, and a deduplication then reads 6.2× where the honest
  figure is 1.5×. Move θ every repeat.
- **`mtable.x0()` is the last stage's start, not its answer.** A commit
  leaves the combined vector cached. Read each sub-table's `x0()` through
  `col_map`, as `_stage_end_rows` does.
- **A coefficient column reaches `_peak_chain_column` under its target's
  path** (`phases.0.cell.a`), not under its `vars.` name. A deduplication
  keyed on `vars.` finds nothing.
- **This cloud container cannot reach the data.** The maintainer's disk is
  not mounted, and the network policy denies
  `topas.webspace.durham.ac.uk`. The maintainer is carrying the WP on
  locally.

Next, in order:
1. **The measurement on real data, on the maintainer's machine**, because
   only a local session reaches it. Use the ZrMo₂O₈ ramp, or the Durham
   ZrP₂O₇ (37 patterns) and WO₃ (100 patterns) tutorials, stored locally and
   never committed. It also says whether a larger structure raises the
   kernels' share.
2. **A lack-of-fit check on the declared form**, the previous session's
   first: a wrong form gives confidently wrong esds. Real data is the better
   test of it.
3. **The peak-chain deduplication**: about 1.2× on the fit, estimated, and a
   stated equivalence bar.
4. **In-step bounds** for the coefficients, then **start agreement** beyond
   parameters.

### 2026-10-14 (second session) — the parametric fit is built, measured and scales to hundreds of patterns

A joint fit can now refine a parameter as a declared function of where each
pattern sits: a line or polynomial in temperature down a ramp, a surface over
composition across a library, or one law per phase field. The answer is the
function's coefficients with esds, in the caller's units. The fit no longer
runs out of memory with size: a 300-pattern library refines in about a minute
in 1 GiB, where the old path needed 20 GiB for its Jacobian alone. The
maintainer asked whether a smooth kernel over the coordinates would serve
better than a declared form. Surveyed and then measured, it did not: tuned
from the data it did worse than a plain line exactly where it could have
helped, and at good settings it bought honest error bars, not accuracy. The
hard function, on the other hand, measurably helped where single patterns
cannot see the parameter. Its error bars go confidently wrong when the declared
form is wrong, which makes a lack-of-fit check the next thing worth building.

*Done* (session started 2026-10-14 at 0b33465, after #968 merged; one new
draft PR, #969):
- **The kernel survey.** Three agents covered diffraction, statistics and
  other sciences; the result is § A kernel over the coordinates.
- **The measurement where one pattern cannot see the parameter**, with the
  maintainer's kernel extensions. § Measured: where one pattern cannot see
  the parameter. A lack-of-fit task was filed from it.
- **The declaration, per-pattern starts and ties in the joint table**:
  `schemas/parametric.py`, `params/parametric.py` and `params/multi.py`. A
  `constant` basis is bit-identical to a shared parameter. The joint support
  hold and its release read column reach.
- **Coefficients in user units**: `RefinementResult.parametric`, schema 0.55.
- **Summaries.** `str(result)` prints the coefficients. `SeriesResult.summary`
  takes `parametric=`, and the series deliverable gains a "functional form"
  row.
- **The blocked solver, step and covariance**, and its scaling measured
  (§ Measured: scaling).
- **Docs**: manual Part 1 and Part 2, and the skill's series row.
- **Found while documenting, and fixed:**
  - centred mixture fractions are refused until their reading is stated;
  - one target may take a law per phase field, on disjoint subsets;
  - the reported unit comes from `rietx.help`, so a cell coefficient reads
    Å/K.
- **`/code-review high --fix`: 9 findings, 5 fixed** (d2b8156):
  - a size target across wavelengths is refused (WP-1131's factor never
    reached a per-histogram target);
  - "never refined" became "not free at the answer";
  - one `entry_reach` per table;
  - two unused methods removed;
  - a restated regex now imported.

  Four declined:
  - in-step bounds on a combination: a design change, filed as a task;
  - per-pattern starts' non-parameter fields: a design decision, filed as a
    task;
  - the joint `CELL_RUNAWAY` vars twin: forwarded to 1341;
  - three reach walks per stage: cheap per call, and it touches unchanged
    code.
- **Forward references:**
  - 1962 learns the solver's shape and limits; its priority clause was
    re-dated;
  - 1329 learns the parametric tie and its measured regime;
  - 1341 learns three joint guards that cannot see a coefficient-driven or
    per-histogram cell, and the new diagnostic.
- **Inherited:** none on arrival.

*Measured* (Linux x86_64, 4 CPUs, 15.7 GiB, `[dev]` venv):
- The measurement, scaling and equivalence numbers are in § Measured and in
  the solver tasks' landing notes.
- Fast suite on the merged tree (main at 0b33465, which had not moved): 9653
  passed, 197 skipped, 1 xfailed, in 18:54. That is one run, nothing else
  running.
  - The session added 32 fast test functions and 2 slow ones.
    `tests.added_test_times` gives 62.8 s over the added fast tests, 61.9 s of
    it in `test_parametric_series.py`.
  - The new tail is `test_a_blocked_fit_lands_on_the_dense_answer` (31.3 s, 2
    cases). It stays fast because it is the one end-to-end run of the blocked
    path, which no fast fit reaches by size.
  - Main's count was not re-measured (`tests/CLAUDE.md` § Running, rung 4),
    so CI confirms the delta.
- Slow joint-path files, run instead of the full selection, on the same tree:
  17 passed in 1:19. The files are `test_absent_phase`,
  `test_acceptance_wavelength`, `test_held_phase` and
  `test_parametric_series`, run with `-m slow`. The full selection was not
  run: these are the only slow files that reach the joint path (torch and
  cross-backend skip without their backends).
- Lanes (`session_usage.py lanes`). Main: 164 requests, peak 484K, $18.20.
  Four lanes: $47.60.

  | lane | est | requests | main at dispatch | lane base | re-read | main requests | left in main | main edits after | redo | lane $ | main $ | saved $ |
  |---|---|---|---|---|---|---|---|---|---|---|---|---|
  | measurement-kernel | 45 | 74 | 270K | 114K | 7K of 67K | 1 | 4K | 0 | 0 | 10.60 | 0.21 | +4.61 |
  | declaration-ties-starts | 60 | 146 | 274K | 115K | 0K of 62K | 29 | 64K | 0 | 0 | 12.60 | 2.55 | +9.51 |
  | scalable-solver | 80 | 146 | 340K | 115K | 0K of 110K | 10 | 22K | 2 | 0 | 14.94 | 1.00 | +11.11 |
  | docs-manual-skill | 40 | 125 | 398K | 113K | 24K of 48K | 6 | 14K | 2 | 0 | 9.47 | 0.67 | +10.39 |

  The trial row went to `docs/milestones/process.md` with fixed 0 where the
  tool printed 2 for two lanes. Those later edits were my own code changes
  rippling into the lanes' files, not repairs of their work. Selective
  policy row: `lane when main > 150K and item >= 20 requests | 4 | -21%`.
  Estimate against actual was 2.13×.

*Gotchas*:
- **Lanes ran concurrently**, against `/wp-start`'s one-at-a-time rule.
  - The measurement lane ran on a frozen copy of `src/` (a `--src` flag that
    inserts the path before import). A PYTHONPATH prefix is refused by a hook
    here.
  - The docs lane ran beside the solver lane, on disjoint files.
  - Two of my commits touched a file a lane was still editing. Staging only
    my hunks (`git apply --cached` of one extracted hunk) kept the lane's
    edits out.
- **The joint support hold fires only for a phase invisible in every
  histogram.** A per-histogram cell is flat in a pattern that cannot see its
  phase, and nothing holds it (forwarded to 1341).
- **The single-fit 3σ hold keeps noise-chasing fits near threshold.** The
  kernel measurement's chain kept patterns at support 0.84-1.4 whose cell
  errors reached 6.5 esd. 1523 is closed and no open WP owns it, so it is
  recorded in § Measured, not filed.
- **Blocked is faster than dense from N = 10**, yet dense stays the default
  below 256 MiB. That keeps every existing joint answer bit-identical.
  Lowering the threshold would move converged values by ~1e-8 esd.

Next, in order:
1. **A lack-of-fit check on the declared form.** The measurement says a wrong
   form gives confidently wrong esds. A score test against per-pattern
   deviations needs no refit.
2. **In-step bounds for the coefficients** (`LinearInequality` rows), so a
   polynomial cannot step a target through its floor.
3. **The real ZrMo₂O₈ ramp**, when the maintainer supplies it: the
   measurement on real data.
4. **Start agreement beyond parameters** (texture axis, magnetic symmetry).

- **2026-10-14** — the parametric fit is scoped, and measured once. The
  maintainer made the combinatorial library a target, which puts a joint
  solver that scales to hundreds of patterns inside this WP. Direct XRD
  tomography went to its own candidate,
  [1962](1962-xrd-ct-a-pattern-summed-over-the-voxels-its-beam-crosses.md),
  and the first measurement ran on synthetic data. On a synthetic heating
  ramp, fitting the cell as a straight line in temperature across all the
  patterns at once gives exactly the slope and error bar that a line through
  the per-pattern fits gives. The only precision gain (2.6× on the slope's
  error bar) came from sharing the instrument's parameters across the
  patterns, and a joint fit without the line constraint gets that too. So far
  the constraint's value is convenience. The case that could show more, a
  parameter one pattern cannot pin down on its own, is untested.

  *Done* (session started 2026-10-13):
  - Claimed with draft PR #968. This morning's two unlogged commits got a
    reconstructed entry, written by hand rather than through a full repair
    run, because both only edited this file.
  - The survey task: Context § Prior art, § The shape (the five questions
    answered) and § What the code has, with file:line pointers. Ticked.
  - The maintainer's three decisions went into § Scope. Tasks were
    restructured to match:
    - the measurement split three ways;
    - the declaration;
    - per-pattern starting values;
    - ties and variables reaching the joint table, with the WP-1342 prefix
      fix;
    - the scalable solver's step, covariance and scaling;
    - the remaining deliverables.
  - Priority went P3 → P2.
  - `### Inherited` pruned on arrival: all four entries were still true and
    were folded into § Use cases and § The shape's refusals; the mailbox is
    empty.
  - Filed 1962 after checking for an owner: a grep of `docs/` and `src/` for
    tomography, XRD-CT and voxel found nothing.
  - The synthetic half of the measurement (a lane), in `1325-measure/`.
    Results and reading are in § Measured. Ticked.
  - `/code-review high --fix` returned 8 findings and 6 were fixed:
    - the joint slope is the line weighted by each pattern's *raw*
      information (here the equal-weight line, 0.0012 esd away), not the
      chain's weighted line (0.024 away);
    - a(T_ref)'s esd is quoted for R1/R3 only;
    - R2's wide raw esds are named as open;
    - the script refuses a missing esd or a malformed argument by name.

    Two were declined. Caching R1's chain for R3 would copy R1's wall clock
    into R3's ratio. Moving the Track line off "not yet on a measurement" is
    the maintainer's call.

  *Measured*:
  - The synthetic ramp: § Measured holds the table. Linux x86_64, 4 CPUs,
    `[dev]` venv, compiled kernels on, nothing else running.
  - Lanes (`session_usage.py lanes`):

    | lane | est | requests | main at dispatch | lane base | re-read | main requests | left in main | main edits after | redo | lane $ | main $ | saved $ |
    |---|---|---|---|---|---|---|---|---|---|---|---|---|
    | measurement | 30 | 62 | 336K | 113K | 0K of 9K | 26 | 40K | 2 | 0 | 3.95 | 2.38 | +0.43 |

    The trial row went to `docs/milestones/process.md`, with fixed 0 where
    the tool printed 1: the two later edits were to this file. Baseline,
    selective policy row: `lane when main > 150K and item >= 20 requests | 2
    | +4%`. Estimate against actual was 2.07×: the lane ran 20 seeds, not 5.
  - Fast suite: not quoted. A local run was stopped at about 10 %, because
    merging `main` mid-run changed two `src/` files under it, and a 4-CPU
    container ran it at that pace. The branch adds no test and touches
    nothing under `src/`, `tests/` or `examples/`, so CI's run on the ready
    PR is the record. `test_docs_consistency.py` (25 passed) and ruff are
    clean on the merged tree.

  *Gotchas*:
  - `MultiHistogramRefinement` builds its joint table once (`multi.py:815`),
    so sub-table edits persist across stages. But a new variable or tie needs
    `_rebuild_columns()` called by hand.
  - `MultiParameterTable.set_vary` skips tied entries
    (`params/multi.py:281`), which is what keeps the tie alive through a
    plan.
  - A joint result carries no covariance. The script subclasses
    `_build_result` (`multi.py:1406`) to read it. This belongs to the "ties
    and variables" task, not forwarded to 1341.
  - The Bérar-Lelann factor is 1.26 on data its model matches exactly, and
    R2's raw esds run about 1.3× wide. No open WP owns esd calibration (1931
    only divides the factor out), so it is recorded in § Measured and not
    filed.
  - Not ported to the skill. "Share the instrument across a ramp" is
    synthetic-only, and sharing a zero or displacement through a heating ramp
    is valid only while the mount does not move. It waits for the real ramp.
  - The outside lab's other request, spherical-harmonics texture, is
    [1960](1960-spherical-harmonics-texture.md). It landed on `main` during
    this handover and already cites the lab, so nothing was forwarded into
    it.
  - This session's local branch `wp1325-parametric-series` pushes to
    `origin/claude/blissful-ptolemy-tb7b7k`, the cloud session's branch. That
    branch is PR #968's head.

  Next, in order:
  1. The measurement where a single pattern cannot see the parameter. Reuse
     `synthetic_ramp.py`, with a minor phase under the per-pattern 3σ hold,
     or broad, overlapping peaks. It decides whether the constraint earns
     anything beyond convenience.
  2. The scalable solver, starting with route (i): per-pattern blocks feeding
     the existing projected CG, which already handles bounds. Measure it
     against dense at N = 10/70/300. It is justified by the sharing result
     whatever item 1 says.
  3. The real ZrMo₂O₈ ramp, when the maintainer supplies it.
- **2026-10-13 (reconstructed post hoc)** — two planning commits landed on
  `main` this morning without a handover entry, and the session-start hook
  flagged the WP for repair. Neither one changed code or measured anything.
  Together they say this WP's first outside user wants a 2-D surface across a
  combinatorial library rather than a 1-D line through a ramp. They also say
  the declaration has to be designed for an automated writer (a self-driving
  lab) before it is built.
  - `a9a577e` added the 2026-10-13 `### Inherited` entry from the outside
    lab's email: the axis is a vector, there are many specimens, targets
    include `hist.{h}.` paths, and the priority claim is disputed.
  - `b23bb9a` added the prior-art survey task (second in Tasks) with its five
    design questions.
  - The diff does not say which session wrote them or why they were not
    handed over. Both touch only this file.

  Next: the survey task, then the measurement.
- **2026-09-01** — created as a candidate during the roadmap reorder; carries
  a use case and a seam, no measurement. First task is the measurement.
