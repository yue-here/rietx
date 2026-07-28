# Refinement protocol for agents

**Audience: an LLM agent driving `pxrdref` to refine real powder diffraction
data.** Not a tutorial and not an API reference — a *protocol*: what to do, in
what order, what to check before believing a number, and where this package
will tell you that your answer is wrong even though it looks right.

Read this before your first `fit()`. Sections 1–4 are ordinary Rietveld
discipline that would apply in any code; sections 5–10 are specific to running
it without a human at the plot, and were learned by building this one.

> **Orientation for the impatient.** Rwp is not the objective function of your
> job. A Rietveld refinement can converge, report an excellent Rwp, and return
> displacement parameters biased by 100 %, phase fractions wrong by 5 wt %, and
> a cell that is right for the wrong reason. Every section below exists because
> one of those happened and was measured. The package's job is to hand you the
> numbers that reveal it; your job is to look at them.

---

## 1. Before you refine: what the method can and cannot do

Rietveld refinement **fits a structural model you already believe** to a whole
powder pattern. It is a local, gradient-based optimisation of a strongly
non-convex, strongly correlated problem. It is not structure solution, not
phase identification, and not a search.

Preconditions, all of which must hold before `fit()` is meaningful:

| Requirement | How to satisfy it | If you cannot |
|---|---|---|
| Every crystalline phase present is in the model | `Structure.from_cif` per phase | An unmodelled phase's peaks land in the residual; Layer 0's `unmatched_obs` list is how you find them |
| The starting cell is within ~1 % | from the CIF | The peaks are outside their frozen evaluation windows and the refinement cannot walk there; Layer 2 says so with `reindex_or_recheck_cell` rather than reporting a small shift (§6) |
| The wavelength is right | from the beamline `.prm`, the file header, or `Instrument.bragg_brentano(radiation=...)` | Every cell you report is wrong by the same scale factor and *nothing in the fit will tell you* |
| The geometry is right | `Instrument.debye_scherrer` vs `.bragg_brentano` | The aberration model is wrong; displacement/transparency/roughness/absorption are geometry-gated and silently absent |
| The intensities are un-manipulated counts, with esds if available | `read_pattern` reads the file's esd column when present | Weights are wrong ⇒ every esd and every χ² is wrong |

**Never subtract a background before refining.** Subtraction invalidates the
counting-statistics weights and can make intensities negative. Hold an
estimated background *additively* (`BackgroundFixedPlusChebyshev`) or co-refine
it under a smoothness penalty (`BackgroundPSpline`). `background.auto_background(data)`
does the right thing.

---

## 2. The turn-on order, and why it is not negotiable

Free parameters in groups, cumulatively, in a stable order (McCusker, Von
Dreele, Cox, Louër & Scardi, 1999, *J. Appl. Cryst.* **32**, 36). Each group
runs to convergence before the next is freed. The reason is not tradition: the
correlations between groups are severe, and a simultaneous release from a poor
starting point walks into a local minimum that a staged release avoids.

The plans in `strategy/staged.py` encode this. Use them; do not hand-roll a
free set unless you have a reason you can state.

```python
plan="mccusker_default"      # scale+bkg → zero → cell → W → U,V,X,Y      (profile only)
plan="mccusker_structural"   # …then coordinates → displacement → PO → extinction → roughness
plan="lab_bragg_brentano"    # …with sample displacement, Kα2 ratio, FCJ axial
plan="lab_calibrate"         # instrument calibration on a standard, certified cell HELD
plan="lab_sample_refine"     # sample against a frozen calibrated instrument
plan="profile_only"          # Le Bail
plan="pawley_default"        # Pawley
```

Three ordering rules that carry more weight than they look like:

- **Widths last among the profile terms, `W` before `U,V,X,Y`.** `W` is the
  constant term; freeing the tanθ and 1/cosθ terms first lets them absorb a
  constant offset and then fight it.
- **Intensity-scaling corrections go last, after the structure has settled.**
  Preferred orientation, extinction and surface roughness all rescale
  intensities in a Q-dependent way, and so do the scale, the occupancies and
  the displacement parameters. Freeing a correction early lets it eat structure
  that belongs to the structure. This is why `_ROUGHNESS_STAGE` is the final
  stage of every plan that carries it.
- **Anisotropic strain is freed *inside* the sample-broadening stage, not
  after.** A Stephens block locks `lor_strain` — its isotropic direction *is*
  that column — so deferring it would leave the isotropic width unrefined right
  up to the moment fifteen correlated coefficients turn on at once.

**Structure-free first when you can.** Le Bail (`mode="lebail"`) extracts
intensities from the data instead of computing them, so it converges the cell,
zero and profile without any structural assumption. Do that first, then switch
to Rietveld with the converged cell/profile. It is the single most reliable way
to avoid a structural minimum that is really a profile error.

---

## 3. The degeneracies. Memorise these

Almost every wrong-but-good-looking Rietveld result is one of these. They are
not bugs; they are the geometry of the problem.

| Degenerate group | Their angular signatures | Consequence of getting it wrong |
|---|---|---|
| zero shift · sample displacement · cell | const · cosθ · tanθ | Over a narrow 2θ range these are collinear. A cell "refined" against a free zero on 20° of data is not measured. |
| crystallite size · microstrain | 1/cosθ · tanθ | Williamson-Hall separability. Over a short range they are one parameter, not two. |
| phase scale · Biso/ADPs · background · absorption · surface roughness · extinction | all smooth in Q | This is the big one. Every member depresses or lifts intensity as a smooth function of angle. Any of them can absorb any other. |
| preferred orientation · site occupancy | both rescale specific hkl | An occupancy refined against uncorrected texture is a texture measurement. |
| overlapped reflection intensities (Pawley/Le Bail) | identical | The *sum* is determined; the split is not. |

Two practical consequences:

1. **Do not free the second member of a group without checking the first is
   pinned by something outside the fit.** The `lab_calibrate` workflow exists
   for exactly this: refining a certified standard with its **cell held fixed**
   is what decorrelates zero from displacement from cell, because the cell is
   supplied rather than fitted.

2. **A correlation of 0.98+ means you refined one parameter and reported two.**
   The package raises `HIGH_CORRELATION` for you. The correct response is
   almost never "widen the bounds"; it is to fix one, or to extend the data
   range until the signatures separate.

---

## 4. Judging a fit — and what Rwp is actually for

Rwp compares your model to the *data you have*, weighted by counting
statistics. It is dominated by the strongest peaks and by the background level.
It is a useful *relative* number between two fits of the same data over the
same channels, and a nearly useless absolute one.

Judge a fit in this order:

1. **Status and guards.** `result.status`, then `result.diagnostics`. A warning
   here outranks any statistic.
2. **The shape of the difference curve**, region by region — not its size.
   Layer 0 gives you this as numbers: `report.regions` with per-region local
   Rwp and χ² share, and `cumulative_chi2_breakpoints` locating where the model
   starts failing.
3. **Unmatched peaks.** `report.unmatched` with `kind="unmatched_obs"` is an
   impurity or missing phase; `"unmatched_calc"` is a phase you modelled that
   is not there, or an absence error.
4. **Whether the refined values are physically possible.** Negative Biso.
   Occupancies above 1. A cell that moved 0.5 %. An ADP tensor that is not an
   ellipsoid. These are all reported, but you have to read them.
5. **The esds, with their inflation.** `statistics.esd_inflation` is the
   Bérar-Lelann factor for serial correlation. Note it has an expected value of
   ≈1.51 even for perfectly white residuals — treat it as an upper bound on the
   damage, not a measurement of it.
6. **Only then Rwp and GoF.**

**Adding parameters: use ΔBIC, not Hamilton's R-ratio.** Measured on this
package's own data (WP-0503): at 7251 channels Hamilton's test blesses a 0.13 %
χ² improvement that is physically inert. ΔBIC has the sample-size penalty that
makes it meaningful at powder-pattern channel counts.

**Comparing against another code means adopting its protocol, not just reading
its numbers.** Mirror its refined-parameter set, its held parameters and its
excluded regions, then *check the channel count matches* before believing any
Rwp comparison. Measured: guessing a plausible protocol on the GSAS-II
fluorapatite tutorial gave Rwp 16 % and a +390 ppm cell; mirroring the
converged `.EXP` gave 9.73 % against GSAS's 10.05 % on an identical 5750
channels.

---

## 5. Read numbers, not pixels

This is the design premise of the package and the first thing that changes when
the operator is an agent.

A human judges a fit by looking at it, especially at peak-shape misfit. A
vision model cannot do that reliably: frontier VLMs fail precise value
extraction from dense plots, and one PNG costs ~1000–1600 tokens — about the
same as 50 regions of exact numbers. All three prior agentic Rietveld systems
fed plot images to a VLM and all three report the same failure: *locally bad,
globally fine* fits that the image hides.

So:

```python
report = ref.report(plan="lab_bragg_brentano")   # the plan supplies the Layer-2 veto
```

- **Layer 0** — model-free, always trustworthy: regions, per-region χ² share,
  cumulative-χ² breakpoints, unmatched peaks. Use this when the fit is bad.
- **Layer 1** — gated linear attribution: per region, how much of the misfit is
  a position error, a width error, an intensity error, a mixing error, an
  asymmetry error, with esds and each term's *share* of the explained misfit.
- **Layer 2** — typed suggested actions from a closed enum, each with a
  confidence, a rationale, `alternatives`, and `vetoed_by`.

Images are secondary evidence. `plot_for_vlm()` exists and renders what VLMs
*can* read (annotated multi-panel montage, worst regions auto-zoomed, Δ/σ panel,
high contrast, never JPEG) — use it to sanity-check a conclusion you already
reached from numbers, not to reach one.

---

## 6. Abstention is a result. Do not convert it into a number

The package's hardest rule is **never return a confident wrong singleton**.
Several places will decline to answer. When they do, that *is* the answer —
propagate it, do not paper over it.

| Signal | Meaning | Correct agent response |
|---|---|---|
| `report.abstained_reason` is set | The global maturity gate refused Layer 1: the model is too far from converged for linearisation to mean anything | Fix the fit using Layer 0; do not read `attribution` |
| `region.gates_passed is False` | This region's coefficients failed resolvability / validity-radius / significance | Read `region.gate_failures`; the coefficients are present for transparency only and must **not** be read as causes |
| A trend is reported non-separable | Two angular templates (e.g. size vs strain) are collinear over this range | Do not pick one. Extend the range or report both |
| `PAWLEY_OVERLAP_UNRESOLVED` | A group's summed intensity is determined; the split is not | Treat the group sum as the datum |
| `STEPHENS_STRAIN_NOT_POSITIVE` | σ²(M) went negative on some reflection — outside the physical cone | The S_HKL are **not quotable**. This fires on isotropic and anisotropic specimens alike, so it is never evidence *of* anisotropy |
| `ADP_NOT_POSITIVE_DEFINITE` | The tensor is not an ellipsoid; its Debye-Waller factor diverges at high Q | Revert the site to isotropic `biso` |
| `ROUGHNESS_UNCONSTRAINED` | The refined correction depresses no modelled reflection by >1 % | Drop the block. The value it refined to is arbitrary |
| `SEQUENTIAL_PATH_DEPENDENT` | A parameter's trajectory differs between the forward and backward chains by more than their esds allow | That trajectory is an artefact of the refinement order, not a measurement. Hold the parameter, restrain it, or quote the forward/backward spread as its uncertainty |

`Layer 1`'s gates, for reference, are: resolvability on the **scale-normalised**
Gram matrix, a 0.4·FWHM validity radius (a peak 5 FWHM off must trigger
"re-detect", never a confident small-offset reading), local χ²_red
significance, and share-based global maturity. Confidence weights *importance*
(share of χ²), not only statistical significance — at high counting statistics
the second-order leakage of a peak shift into the width column is significant
but carries a per-cent-level share.

---

## 7. The diagnostics are the channel for "your answer is wrong although Rwp is fine"

Every code below is a structured `Diagnostic` on `result.diagnostics` with a
`level`, a `where` list of parameter paths, a `message` and a `suggestion`.
**Branch on the code, not on the message text.**

| Code | What it means you must not do |
|---|---|
| `HIGH_CORRELATION` | Quote both members of the pair as independently measured |
| `BOUND_HIT` | Quote a parameter sitting on its bound as a measurement |
| `BACKGROUND_ABSORPTION` | Quote ADPs, scales or QPA fractions from this fit — the background can imitate them, and Rwp *improved* while they biased |
| `ROUGHNESS_ABSORPTION` | Quote roughness and the displacement parameters as two separate results |
| `ROUGHNESS_UNCONSTRAINED` / `ROUGHNESS_OUTSIDE_REGIME` | Interpret the roughness parameters physically |
| `ADP_NOT_POSITIVE_DEFINITE` | Report the tensor as measured |
| `STEPHENS_STRAIN_NOT_POSITIVE` | Report any S_HKL |
| `DISPERSION_NEGLECTED` | Quote QPA weight fractions — unequal f′ across phases biases them directly (measured: RMS 2.26 → 0.69 wt % once applied) |
| `ABSORPTION_ESTIMATE_UNAVAILABLE` | Assume the capillary correction ran. It did not; the fit has **no** absorption correction |
| `ABSORPTION_MU_R_OUT_OF_RANGE` | Trust the magnitude of the correction — µR > 1 extrapolates the Rouse fit |
| `BRINDLEY_OUTSIDE_REGIME` | Prefer the corrected fractions; past µR ≈ 0.05 the "correction" can be further from truth than none |
| `MICROABSORPTION_SKIPPED` | Assume microabsorption was handled |
| `PAWLEY_OVERLAP_UNRESOLVED` | Use an individual reflection intensity from the group |
| `RESTRAINT_TENSION` | Silently accept the averaged compromise — the data and your prior disagree by >3σ |
| `SEQUENTIAL_RESEED` | Read this point of a series as evidence that the trajectory is continuous — its starting values did not come from its neighbour |
| `SEQUENTIAL_DISCONTINUITY` | Report the jump as physics without opening that pattern's own fit; it is equally the signature of a chain failure |
| `SEQUENTIAL_PATH_DEPENDENT` | Quote that parameter's per-pattern esd as its uncertainty — the between-chain spread is larger and is the honest one |

```python
codes = {d.code for d in result.diagnostics}
if "BACKGROUND_ABSORPTION" in codes:
    # stiffen the background BEFORE reporting anything intensity-derived
    ...
```

---

## 8. Ten things that will surprise you, all measured

These are the findings from building the package that change how an agent
should behave. Each one cost a debugging pass.

**8.1 A correction that provably cannot improve Rwp can still be essential.**
The capillary absorption factor factors *exactly* into a constant × exp(c·sin²θ)
— a Debye-Waller shape — so applying it to a model with a free scale and free
Biso leaves the residual unchanged to machine precision. Its entire content is
that a Biso refined without it comes back **low by 0.49 Å² at µR = 1** (Cu Kα),
which is comparable to Biso itself and 19σ against its own esd. `result.absorption`
reports the bias because no fit statistic can. **Corollary for the agent: never
judge a correction by Δ Rwp. Ask which physical quantity it unbiases.**

**8.2 The opposite also happens: an improvement that passes every statistical
test and is still rejected.** On round-robin brucite, adding anisotropic strain
improves Rwp 18.55 → 17.90 % with ΔBIC +488 — and drives σ²(M) negative on 12
of 43 reflections, so the coefficients are unphysical and unquotable. A
statistical test cannot see a violated positivity cone.

**8.3 Judge a correction at the reflections, not on the fitted grid.** The IUCr
round-robin patterns start at 5° 2θ but their first reflections are at 25–32°.
A grid-based fence cheerfully reported a 27 % low-angle intensity depression
that no modelled peak ever experienced. If you are reasoning about where a
correction has leverage, the relevant coordinate is *where the reflections are*.

**8.4 A multiplicative correction is trivially ~0.96 "scale-like".** Any
correction that rescales intensity projects almost entirely onto the scale
column, so a raw R² against a block containing the scale is a constant that
says nothing. Use the **partial** R² with the scale and background projected
out first — `optimize.statistics.block_projection_r2(..., nuisance=...)`. With
that fix the statistic tracks real identifiability (R² 0.06 → 0.95 as the
low-angle reflections leave the fitted range); without it, it saturates and the
guard is blind.

**8.5 Pairwise correlation is the wrong statistic for a block.** With ~100
spline coefficients, each individual |ρ| against a structural parameter stays
around 0.2 while the block collectively absorbs ~46 % of it. Ask "can this
*group*, acting together, imitate that one?" — that is what
`background_absorption` measures.

**8.6 Some parameters are dead at zero and some explode there.** A
softplus-transformed coefficient (extinction, roughness strength) has
dp/du → 0 at the floor, so it will never move: it needs `Stage.seed`. A
Stephens block has Λ ∝ √Σ with *unbounded* slope at Σ = 0, so it needs
`Stage.strain_seed` to start on the isotropic ray instead. These are opposite
pathologies with opposite fixes; the plans already carry both.

**8.7 Off-by-default is a decision, not an oversight.** Anomalous dispersion,
anisotropic ADPs, Stephens strain, surface roughness and preferred orientation
are all opt-in per source/atom/phase. Turning one on changes every number
downstream, including published acceptance values. If you enable one, re-measure
— do not carry a comparison across the change.

**8.8 Never transfer a literature constant without a numerical check across
*all* its arguments.** A published cylinder-absorption coefficient printed as
"−0·0375" is really −0·3750; the error is invisible against a constant-θ slice
of the paper's own table (which constrains only the other two coefficients) and
is 0.082 wrong at µR = 1. What caught it was a quadrature of the exact integral
the fit approximates — which shares no constant with any published fit. The
general rule: **the strongest anchor is the integral a fit approximates, not
another code's transcription of the same fit.** The same applies to Stephens
S_HKL, where codes fold symmetry multiplicities into their templates and print
values differing by small integer factors.

**8.9 An absurd statistic is more often the linear algebra than the physics.**
JᵀJ here is routinely conditioned at ~10²⁰ — that is what the degeneracy table
in §3 *means* numerically. Until 2026-07-28 the covariance was taken with
`np.linalg.pinv`'s general SVD path, which does not know the matrix is
symmetric and returned correlations as large as |ρ| ≈ 1.6 × 10³ (and +2.75 for
`scale ~ axial_sl` on a real fluorite fit). If a reported correlation, esd or
weight-fraction uncertainty is impossible rather than merely surprising, check
the conditioning before you invent a physical story for it — and remember that
the fix is to compute the covariance properly, not to clip the output, because
clipping 2.75 to 1.0 reports a degeneracy the arithmetic invented rather than
the one the data has.

**8.10 Conventions are documented by physics, never by letter.** GSAS and
FullProf swap the X/Y size/strain labels. Most tabulations print the absorption
*correction* A\* = 1/A where this package multiplies by the *transmission*
A ≤ 1 — and both equal 1 at µR = 0, so an identity test cannot tell them apart;
only the direction of the θ-dependence can. The March coefficient r means
opposite habits in reflection and transmission geometry. **Read the docstring,
not the symbol.**

---

## 9. Using the history DAG as a search structure

This is the part of the API that exists because the operator might be a search
process rather than a person. Every stage auto-commits an immutable, restorable
node (~10 kB — state, not curves), so branching is cheap and a rejected
experiment leaves no trace in the working state.

The canonical agent loop:

```python
ref = pr.Refinement(structure, instrument, history="session.jsonl")
ref.fit(data, plan="lab_bragg_brentano")
ref.history.tag(ref.history.head, "baseline")

# try a hypothesis on a branch — rollback is structural, not manual
rival = ref.branch("baseline")
rival.run_stage(data, pr.Stage("aniso_strain", ["phases.*.microstrain.dof.*"],
                               strain_seed=1000.0))

ref.history.compare([n.id for n in ref.history.leaves()])
ref.checkout(ref.history.best("rwp").id)
```

and the machine-checked version of "should I take this suggestion?":

```python
outcome = pr.report.predict_then_verify(ref, data, report.suggested_actions[0])
# runs the action on a branch, keeps it only if χ² actually improves by ≥1 %
print(outcome.accepted, outcome.reason, outcome.predicted_delta_chi2,
      outcome.observed_delta_chi2)
```

Note `expected_delta_chi2` on a suggested action is the *linear model's*
prediction — an optimistic upper bound, not a promise. The gap between
predicted and observed is itself information: a large predicted improvement
that does not materialise means the linearisation was invalid there, which is
usually a peak far enough off that it should have been re-detected rather than
shifted.

Two properties worth relying on:

- **Node metrics are as-optimised**, measured on a model frozen at the values
  each stage *started* from. `pr.replay(tree, node_id, data)` recompiles at the
  values the stage *ended* on, so the two can differ marginally. That gap is a
  staleness signal, not a bug.
- **Each node carries the API call that produced it**, so a session doubles as
  a reproducible script, and `cherry_pick` replays another node's stage *action*
  (not its values) on top of the current state.

---

## 9b. Series: refine a ramp as a chain, and check it both ways

An in-situ ramp, a parametric sweep or a tray of related specimens is
`pr.SequentialRefinement` / `pr.refine_sequential`: N separate refinements,
each warm-started from its predecessor.  (One *joint* residual over patterns
that share structural parameters is the different verb `pr.refine_multi`.)
What comes back is a `SeriesResult` — per-pattern summaries plus
`trajectory(path)`, `qpa_trajectory(phase)`, `to_table()`, `write_csv()`.

```python
series = pr.refine_sequential(patterns, structure, instrument,
                              x=temperatures, x_label="T (K)",
                              plan="lab_sample_refine")
a_of_T = series.trajectory("phases.0.cell.a")     # x, value, stderr
```

Three things an operator must know, all measured:

- **Chaining is worth ~3x in iterations, not in accuracy.**  On the eight
  round-robin sample-1 mixtures: 2863 iterations unchained, 904 chained, at
  identical Rwp and identical weight fractions.  Use it to make a long series
  affordable, never to make an individual fit better.
- **The default `refit="single"` collapses the plan into one stage** for every
  pattern after the first.  The staged turn-on order exists to keep early
  stages conditioned from a *poor* starting model; a converged neighbour is not
  one.  A pattern where that turns out to be wrong is caught by the reseed
  fence, which refits it cold with the full staged plan.
- **A sequential trajectory is path-dependent by construction**, so a smooth
  curve is exactly what a poisoned chain produces.  `direction="both"` runs the
  series each way and reports `SEQUENTIAL_PATH_DEPENDENT` per parameter.  For
  any trajectory you intend to publish, run it — it is the only check that
  separates a measurement from an ordering artefact.

`carry` (dot-path globs) restricts what crosses a pattern boundary.  Reach for
it when a parameter must provably not be chained; do **not** reach for it
because a parameter jumps.  That hypothesis was tested on a series whose
composition swings 1 → 94 wt % and it is false: carrying everything is cheaper
there than excluding the scales.

---

## 10. A worked default

If you have a lab pattern, a CIF and no other information, this is the sequence
to run and the checks to make. Adapt, do not skip the checks.

```python
import pxrdref as pr

data       = pr.read_pattern("sample.xy")
structure  = pr.Structure.from_cif("phase.cif")
instrument = pr.Instrument.bragg_brentano(radiation="CuKa",
                                          monochromator_two_theta=26.6)
instrument.background = pr.background.auto_background(data)

ref = pr.Refinement(structure, instrument, history="session.jsonl")

# 1. structure-free first: cell + profile without any structural assumption
ref.fit(data, mode="lebail", plan="profile_only")

# 2. Rietveld from the converged cell/profile
result = ref.fit(data, plan="lab_bragg_brentano")

# 3. guards outrank statistics
for d in result.diagnostics:
    print(d.level, d.code, d.where, d.message)

# 4. numbers, not pixels
report = ref.report(plan="lab_bragg_brentano")
if report.abstained_reason:
    print("Layer 1 abstained:", report.abstained_reason)   # fix the fit first
else:
    for r in report.attribution:
        if r.gates_passed:
            print(r.two_theta_lo, r.two_theta_hi,
                  [(c.kind, c.value, c.stderr, c.share) for c in r.coefficients])

# 5. impurities / missing phases
print([u for u in report.unmatched if u.kind == "unmatched_obs"])

# 6. only now, the statistics
print(result.statistics.rwp, result.statistics.gof,
      result.statistics.durbin_watson, result.statistics.esd_inflation)
```

**Stop conditions.** Stop refining when (a) every diagnostic is understood and
either resolved or reported as a caveat, (b) Layer 1 attributes no remaining
region above the significance gate, and (c) adding the next parameter group
fails a ΔBIC test or trips a guard. Do **not** stop merely because Rwp stopped
falling, and do not continue merely because it is still falling.

**What to report.** The refined values with their (inflated) esds, the
diagnostics you could not resolve named as systematics, the protocol you
actually ran (plan, held parameters, excluded ranges, channel count), and the
package version from `result.provenance`. A number without its protocol is not
a measurement.

---

## See also

- [`README.md`](../README.md) — capability table and worked examples
- [`DESIGN.md`](DESIGN.md) — why the FitReport is shaped this way (the
  "Outputs & fit assessment" section is the agent-native design record)
- [`ROADMAP.md`](ROADMAP.md) — what is implemented, what is fenced
- `tests/data/README.md` — provenance and reference values for every dataset
- `pxrdref compare` — browser UI comparing refinement settings side by side on
  the bundled standards (`src/pxrdref/viz/compare.py` is its registry, and a
  usable API on its own: `compare.run("zincite", "dispersion")`). Its
  cumulative-Δχ² panel is the machine-readable form of §8.1's rule — it shows
  *where* a correction acted, not just whether Rwp moved
