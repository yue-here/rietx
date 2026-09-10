# 4/4b. The evidence behind the judging rules

Load it when a rule in §4 (judging a fit) or §4b (declaring the deliverable)
needs its measurement — before overriding one, and before quoting a number whose
trustworthiness the rule decides.

*A reference file of the `rietx` skill. The body it belongs to is
[`SKILL.md`](../SKILL.md); section numbers are the ones the body cites.*

## Step 9 — what `max_shift_over_esd` separates

McCusker et al. (1999) §7 calls a refinement converged when max|Δθ|/esd ≤ 0.1.
The band is quoted from the paper and gates nothing here. A converged solve
satisfies it a fortiori, so the number earns its keep on the other branch: where
a stage stopped on `STAGE_MAX_ITER`, its magnitude says *how far* the solve was
still moving in esd units, which separates "nearly there" (just over the band)
from a fit that stopped mid-flight — measured ≈14 on one starved iteration.

## Step 12 — the geometry table's esds

`stderr` is propagated through the *whole* covariance, which McCusker §10
requires of any derived quantity, and `stderr_diagonal` beside it is what
ignoring the correlations would have given. Quote the first; use the pair when
you need to say how much the correlations mattered (measured on 11-BM NAC,
dropping them moves an esd by ×0.71 to ×1.15, in *both* directions, so a
diagonal esd is not the conservative choice).

`None` covers all four ways a number is unavailable: no covariance behind the
row (an evaluate-only pass), no free source, a quadratic form that reaches zero
by cancelling, and a straight angle where linear propagation does not hold. An
esd of 0 on a symmetry-fixed 90° angle would be a claim about precision rather
than a statement about constraint.

`write_refinement_cif` writes the whole table as `_geom_bond_*`,
`_geom_contact_*` and `_geom_angle_*` loops, with the symmetry codes resolvable
against the `_space_group_symop_operation_xyz` loop it writes beside them.

## §2 rules 4-5 — the two Le Bail measurements

**Iterate to a fixed point, and keep the best pass.** On PbSO4 pass 1 stops at
Rwp 20.756 % with an unphysical Caglioti **V = +0.0615**; passes 2-4 reach
10.247 % with the curve sane. Re-run the plan until Rwp stops moving. Because
the alternation is not a descent on one objective, a later pass can come back
worse — seen on Tb2BaCoO5, 17.3 % → 18.7 %.

**Seed the background first.** `auto_background` chooses the knot spacing or the
Chebyshev *order* but starts every coefficient at **0.0**, so the modelled
background is identically zero and the first `lebail_update` runs *before* the
background has ever been fitted. The partition is then handed
`max(y_obs − 0, 0)` — the whole pedestal — and gives it to the Bragg
reflections. Measured on a synthetic pattern whose background is 5× its
strongest peak: cycle one claims **571×** the true Bragg intensity.

**Multi-phase Le Bail** was broken until v1.0 and is now supported: the shares
sum to 1 across all phases at every channel (measured Σ calculated / Σ observed
excess **1.79 → 1.0000** on LaB₆ + CaF₂, single-phase path bit-identical). One
caveat survives the fix and is about the method: the intensities of two phases
whose reflections *coincide* are not separately determined by the data, since
the partition splits them by the current model, which is a starting value and
not a measurement. Treat a high multi-phase Le Bail Rwp as a reason to check the
seeding above.

## §3 rule 8 — what tying three oxygens actually bought

Fluorapatite's three phosphate oxygens, tied as one displacement parameter: 20 →
18 free parameters, 287.5 → 319.4 observations per parameter, and B(O)
0.2763(1810) / 0.5279(1911) / 0.4149(1282) Å² free against 0.4138(899) Å² tied —
tighter than the best of the three. Rwp moved by 0.05 % of itself, which is why
it can tell you neither that the constraint helped nor that it hurt.

Every tie is recorded as a `set_tie` history node and restored by a checkout, so
a constrained protocol replays as one. Symmetry always outranks a user tie: a
cell axis the space group already ties, a coordinate behind its site-symmetry
direction, and a `lebail`/`pawley` mode-fixed path are refused by name rather
than silently ignored.

## Step 13 — why the inflation is an upper bound, and why the trio travels

The Bérar-Lelann factor has an expected value of ≈1.51 even for perfectly white
residuals. That is a house derivation rather than the paper's: chance same-sign
runs give E[χ²′]/χ² = 1 + 4/π (`optimize.statistics.berar_lelann_factor`,
simulation-verified). So it is an upper bound on the damage, not a measurement
of it.

`report.identifiability` quotes the qualifying trio side by side — raw χ²_red,
the inflation (already in every quoted esd, dividable back out), Durbin-Watson —
plus the δR line (`delta_r_slope` / `delta_r_intercept`: sorted Δ/σ against
normal quantiles; slope ≈ 1 and intercept ≈ 0 on honest σ, slope > 1 when σ is
underestimated).

The round robins measured why the ingredients matter: the same data refined
under different protocols spread by up to ×17–25 of the quoted esds on cell
dimensions (Hill, 1992; Hill & Cranswick, 1994, *J. Appl. Cryst.* **27**, 802),
whose explanation is §3's first degeneracy row — the cell compensating 2θ-scale
errors. Durbin-Watson is in the trio because serial correlation is precisely
what makes the raw esds untrustworthy, and d stays discriminating where Rwp and
GoF do not (Hill & Flack, 1987, *J. Appl. Cryst.* **20**, 356).

## Step 14 — the exchange row, the swap, and the ridge

**The row and its verdict.** An `exchangeable=True` row says a **held**
parameter's signature is reproducible inside the fitted span (`r2` → 1) *and*
that a fitted partner stands many σ from its null. An E2-shaped answer reads
"converged, but the fitted zero_shift is exchangeable with the held
sample_displacement — **this fit** cannot tell you which is physical". Measured,
the fit carrying a planted displacement inside a compensating zero and its clean
reference differ in *nothing* but this row: χ²_red 1.012 against 1.010, R²
identical to six decimals, and only the partner's 128σ against 1.6σ separates
them.

**Why R² cannot decide it.** R² is a *geometric* statement about column overlap
and cannot say whether the counts in hand separate the pair. On real SRM 660c an
R² of 0.9977 pair comes apart decisively: χ² 4.0752 (zero only) against 3.4890
(displacement only) on 5332 points, with the zero-only model biasing *a* by
+100 ppm.

**The decision band, and hedging a won swap.** `RIVAL_DECISIVE_MIN_CHI2_RATIO`
is 1.10, read on the losing rival's χ² over the winning rival's. On the round-3
eval's solvable control (rivals decisive at 1.1679, the SRM 660c pair above) the
agents that ran the swap recovered the true displacement and still declined or
hedged the answer: the control went 0/7 valid. Below the band the pair is
genuinely unresolved — the two real tie states measure 1.0075 and 1.0001.

**Why the clause is on the statistics block as well as in the summary.**
Measured consumers pipe the answer to a file and grep the statistics back, and
the summary string is what those greps drop: the licence reached agent context
in 2 of 12 cells from the summary, and 4 of 4 from the statistics block once
placed there. `None` there means no report was built or nothing crossed a
comment threshold, never a verdict.

**The ridge.** Freeing the held parameter alongside its partner and refitting
lands on §3's degenerate ridge and reports the unconstrained combination at a
*better* Rwp. Measured over 30 agent runs, seven of twenty position cells took
it. The swap runs each rival **alone**; the ridge runs them **together**.

## Step 16 — what background-subtracted Rwp separates

A sharp LaB₆ fit and one under 0.6° of broadening both report Rwp **0.0137**,
and background-subtracted they read 0.0490 and 0.0766. Raw Rwp is flattered by
whatever the background carries — 89 % of the observed intensity in both — so
the number that separates two fits is the subtracted one. The literature says
the same twice: Toby (2006, Fig. 1) shows identical model discrepancies reading
Rwp 23 % with no background and 3.5 % with one, and Hill's 1992 round robin
recommends quoting the background-subtracted forms for exactly this comparison.
It is published on every report and deliberately never mentioned in `summary`,
because every background-dominated pattern would trigger it, converged ones
included.

## Step 17 — a trace phase's R_B

Neither index is weighted, so a reflection the fit barely constrains weighs as
much as one that dominates it — the weighted R_WI of Cox & Papoular (1996,
*Mater. Sci. Forum* **228–231**, 233) exists to answer exactly this and is not
computed here — and a minor phase's windows sit under the major phase's peaks,
where the counts the major phase failed to describe are handed out too. Measured
on 11-BM NAC with 1.35 wt % CaF₂: 0.052 for the major phase against 0.385 for
the impurity, all of the latter in four reflections at I(obs)/I(calc) ≈ 2.2,
each under a strong NAC peak. Read it beside `qpa.phases[].weight_fraction`, and
treat a trace phase's value as a question rather than a measurement.

`write_refinement_cif` writes them as `_refine_ls_R_I_factor` and
`_refine_ls_R_factor_all` on each phase's own block, beside a
`_pd_proc_ls_special_details` that states the esd method in full — the base
estimator √diag(χ²_red·(JᵀJ)⁻¹), then the Bérar-Lelann factor it was multiplied
by, which §10 of the guidelines requires any publication to state.

## §4b — Phase ID: the unmatched list and the Le Bail-gap read

`report.unmatched`'s `kind="unmatched_obs"` entries are the strong lines your
phase set does not produce — an unmodelled phase's signature, distinct from
resolution-limited noise. `report.lebail_gap` is the structural-against-profile
triage: it re-partitions the per-hkl intensities at the frozen converged state
and reports both Rwp. A `ratio` ≫ 1 means positions and profile alone account
for the pattern, so every line is indexed and phase identification is safe
**at any absolute Rwp** — the structural model does not have to fit well for
the phase list to be right.

## §4b — the QPA background measurement in full

Fractions ride on scales, so the rows that decide a QPA are the ones that bias
scales silently. `report.background.absorption`, keyed by parameter path, is
the detector: the block projection R² of each structural parameter's Jacobian
column onto the background column span sees §3's scale↔Biso↔background
degeneracy that a pairwise ρ cannot. A negative Biso is that same error
laundered through a scale. The Le Bail gap reads the *other* way here than for
phase ID: a large ratio means the intensity model is wrong, and wrong
intensities **are** wrong fractions.

LaB₆, broad peaks, same data both times. Fitted with a 1°-knot unpenalized
spline the refinement reports Rwp **0.08852** and GoF 1.022, against **0.08969**
and 1.025 with a correct Chebyshev-6 — the wrong background wins on every
agreement index — and its displacement parameters come back 0.958 and 0.000 Å²
against a truth of 0.5, one of them on its bound, where the correct background
gives 0.691 and 0.327. `worst_absorption` reads 0.46 against 0.08. **Nothing
else in the report distinguishes these two fits, and the plot does not either**:
the over-flexible residual is white noise inside ±3σ.

The whole `report.background.absorption` table is published rather than only the
entries over `BACKGROUND_ABSORPTION_NOTABLE`, because a fired/not-fired bit is a
verdict and the diagnostic already carries the verdict. A pairwise ρ misses the
effect entirely: ~0.2 per coefficient while the block absorbed 46 %.

## §4b — the two QPA rules the round robins own

Madsen et al., 2001, *J. Appl. Cryst.* **34**, 409; Scarlett et al., 2002, *J.
Appl. Cryst.* **35**, 383.

- A Rietveld σ(W) reflects only the fit's mathematical precision and is "not
  necessarily related to the accuracy". Judge a fraction against the published
  participant spread, never against its own esd. (This is the policy the
  repository's `tests/data/README.md` applies to the bundled `qarr/` patterns,
  which are the round robin's own samples.)
- Microabsorption is the largest physical obstacle to X-ray QPA — "may prove to
  be insurmountable in some circumstances" — and a Brindley correction applied
  where none is needed *reduces* accuracy (their sample 1 and synthetic bauxite;
  `BRINDLEY_OUTSIDE_REGIME`).

## §4b — the worked example that stops at GoF 2.97

LaB₆ pore proxy: a guest scatterer at the 1b site in the data only, host model
refined to convergence. Rietveld Rwp 0.0405, GoF 2.97 — a "bad fit" by GoF. The
report gives zero suggested actions; intensity carries 83 % of the misfit in
per-region errors of 9–18 % with **alternating sign** ((100) low, (110) high,
(111) low — structure-factor interference, which scale, ADP and texture cannot
produce, and the summary names it as un-modelled scattering contents); and
`lebail_gap.rwp_lebail` reads 0.0170 against 0.0405, a ratio of ×2.4.

Read by deliverable: phase ID is **done** — stop, at GoF 2.97. A structure
determination is **not**, and its next move is chemistry (what occupies the
pores), never finer profile corrections, which this evidence says cannot help.

## §4b — why no bar moves for non-ideal data

The gates auto-scale to information content. Measured: a zero error read at
confidence 0.997 on sharp data produces silence, GoF 1.02, on the same error
under 0.6° of broadening. Pushing finer corrections into a fit whose attribution
is resolution-limited changes numbers it cannot justify.

## §4b — the trajectory deliverable, and where its rows come from

Four codes on `SeriesResult.summary(deliverable="series")` carry the chain's
own rows. `SEQUENTIAL_PATH_DEPENDENT` is an ordering artefact — only a
`direction="both"` chain can produce one, so a one-way chain has not looked.
`SEQUENTIAL_PERSISTENT_FINDING` states a persistent count no per-pattern code
can, measured at **42 of 68** patterns on this ramp. `SEQUENTIAL_DISCONTINUITY`
flags either the science or a chain failure, and `verify_discontinuities=True`
tells them apart (below). `PHASE_UNCONSTRAINED` says the value is held, not
measured, so its trajectory is the one you handed in — then the QPA
deliverable's own background check, applied **at every point** along the
chain: an absent phase took **40–96 wt %** at equal Rwp.

The row exists because an agent needed it and wrote it itself. Given 68 patterns
of a variable-temperature ramp, `rietx`, and "tell me what the cell does, and
flag anything you would not quote", a run recorded in full built its own
stopping rules and they were the right ones: model selection by ΔBIC and the
rival χ² ratio rather than by Rwp; the step at 430 → 440 °C verified by an
**independent cold refit** of both patterns; tan θ against cos θ to tell a cell
change from a specimen-height jump; a CaF₂ impurity used as an internal standard
to bound 2θ drift to ±27 ppm over 280 K; and the explicit split — precision on
the shape of a(T) at ±0.00015 Å, no accuracy claim on the absolute beyond
~100 ppm, *because nothing pinned the 2θ scale*. About 34 of its 90 calls went
into those checks. None of them is a fit statistic, and §4b named none of them.

Two are now the package's:

- **The cold-refit check is `verify_discontinuities=True`.** Each flagged step's
  two patterns are refitted cold and independently, and the diagnostic's `value`
  becomes the cold step over the chain's — 1.0 in the data, 0 the chain's own.
  Measured on that ramp, reproducing the run's own protocol: the chain takes
  11.6–12.0 s and the check adds 5 % (12.1–12.2 s) for four flagged steps over
  four patterns, and the real transition reproduces at **1.00**. The cost scales
  with the patterns flagged, not with the series length.
- **The rows are `SeriesResult.summary(deliverable="series")`.** In the same
  re-run, `PHASE_UNCONSTRAINED` fires on the impurity's cell in **40 of 68**
  patterns and the trajectory of a *held* value is not a measurement — which is
  exactly the "would not quote" list the agent arrived at by hand.

The two the package cannot supply stay the caller's, and the row says so rather
than leaving them blank: nothing in a pattern file records what pinned the 2θ
scale, and no esd can tell you it is a precision on the shape rather than an
accuracy on the absolute.

## Microstructure: what a domain size is, and what it is not

`result.microstructure` reads each of a phase's four sample-broadening
coefficients as the quantity behind it — a **coherent domain size** in Å from
the two 1/cosθ terms, a dimensionless Δd/d from the two tanθ terms — with an
esd, or a named reason there is none (`MicrostructureTerm.unavailable`:
`at_zero`, `no_wavelength`, `not_measured`).

**A domain size is not a particle size.** `Phase.particle_radius_um` is a
different quantity for a different correction, the absorption path through a
grain; profile broadening measures the coherent domain inside it, which is
smaller and unrelated. Reporting one as the other is the commonest way to
misread this block.

**It is not a two-figure number either.** The Scherrer constant moves 10-20 %
with crystallite shape, and the codes disagree about which constant and which
measure of breadth: rietx reads the FWHM with K = 0.9, GSAS-II the FWHM with
K = 1, FullProf the integral breadth — which for a pure Lorentzian is 1.571×
rietx's answer. Quote the size as an order of magnitude with the `scherrer_k`
the block carries, and quote a Δd/d with its convention (rietx's is the FWHM of
the d-spacing distribution; GSAS-II's `mustrain` is twice it, FullProf's
apparent strain half of it before the breadth factor).

**Read `separable` before either number.** Over a short 2θ range 1/cosθ and
tanθ are one curve, so the fit trades a size against a strain at no cost in
Rwp. `PhaseMicrostructure.separable` is the width trend's own verdict and
`size_strain_collinearity` the correlation it was decided on. `False` is not a
smaller number to quote — it is a wider range to collect. Refining one of the
pair and holding the other is not a workaround: the answer then depends on
which was held.

**Then read `size_agreement`.** rietx registers the Gaussian and Lorentzian
halves of each mechanism as independent columns, where GSAS-II refines one
magnitude and a mixing coefficient. Nothing makes them agree, so the ratio is a
measurement: far from 1 means the two describe different specimens and neither
is quotable alone.

**In a joint fit, read the size and never the degrees.** A size coefficient is
proportional to λ, so `MultiHistogramRefinement` normalises the shared column
and reports it at histogram 0's wavelength, saying so through
`SIZE_NORMALISED_ACROSS_WAVELENGTHS`. Each histogram's own structure copy
carries the coefficient it needs; the crystallite behind them is one number.

**`SIZE_UNUSUALLY_SMALL` and `STRAIN_UNUSUALLY_LARGE` flag a coefficient
outside its usual range, and `BOUND_HIT` on the same path says why it stopped
there:** a width term pinned to a bound is a held value, not a measurement,
and reads no differently in the table until you check for it.

## §4b — Structure: why the intensity-model rows are not optional

Structure determination needs everything Phase ID, QPA, Trajectory and
Microstructure check, plus the rows that speak to the intensity model
directly: per-region intensity coefficients and their angular trends,
`report.texture` and `report.strain` with their caveats, restraint tension,
ADP positive-definiteness, and `report.identifiability.exchanges` with
`.soft_modes` (step 14, above). Here a notable Le Bail gap is a **blocker**,
not a comfort the way it can be for phase ID: the intensity model *is* the
structural claim, and a large gap says that model does not carry the pattern,
whatever the profile-only fit's Rwp says.
