# 7. The diagnostics are the channel for "your answer is wrong although Rwp is fine"

Load it when a `Diagnostic` fires and you need the row: what it means, what to do, and what you must not do.

*A reference file of the `rietx` skill. The body it belongs to is [`SKILL.md`](../SKILL.md); section numbers are the ones the body cites.*

Every code below is a structured `Diagnostic` on `result.diagnostics` with a
`level`, a `where` list of parameter paths, a `message` and a `suggestion`.
**Branch on the code, not on the message text.**
`d.explanation` (or `rietx.help.explain(code)`) says what a code means and why it fires. The rows below add only what you must not conclude and where to look next.

One namespace note, because two vocabularies share the same UPPER_SNAKE shape:
every code in this document is the **engine's**, a `Diagnostic.code`. The GUI
server's session codes (`NOT_FOUND`, `RUN_IN_FLIGHT`, `STALE_REVISION`, …) are
a separate vocabulary with no rows here, so a code met outside
`result.diagnostics` is the server's, not the engine's.

| Code | What it means you must not do |
|---|---|
| `HIGH_CORRELATION` | Quote both members of the pair as independently measured. Deduplicated across a plan's stages (worst \|ρ\| kept) and capped at 10 per fit, worst first; a `HIGH_CORRELATION_OMITTED` row past the cap gives the omitted count |
| `FLAT_DIRECTION` | Quote **either** member as measured, and do not read the esds. It fires when \|ρ\| prints as 1.000, a statement about the **rank** of the data. It rides *beside* the pair's §`HIGH_CORRELATION` row. Tighter convergence does not help: say which member you held |
| `FLAT_DIRECTION_OMITTED` | (info) Read it as "only these pairs are degenerate". Capped at the same ten as §`HIGH_CORRELATION_OMITTED`, on its own budget. `result.identifiability` carries the full matrix |
| `COVARIANCE_DIRECTION_DISCARDED` | Quote none of the esds in `where` as measured. A set already inside a reported §`FLAT_DIRECTION` pair adds no row here, and there is no minimum group size. (Measured: 183 of 1 899 slow-acceptance solves, WP-1535) |
| `HIGH_CORRELATION_OMITTED` | (info) Nothing was dropped from the fit, only from this message. `result.identifiability` carries the full correlation matrix and `top_correlations` |
| `BOUND_HIT` | Quote a parameter whose bound **carried load** as a measurement. `Diagnostic.value` is a signed cosine of the push, so a value near a limit with **no** row here is one the limit is not holding, and widening it buys nothing. `RefinedParameter.at_bound` is the same finding on the row, three-valued: test `is True`, since `None` means untested (a tied row, or `replay`). **Check the ties before you widen a bound**: a tie hands its dependent's limits back to its source, so a `BOUND_HIT` on a parameter whose own `min`/`max` are nowhere near the value is a dependent's ceiling arriving through the tie, and the parameter to widen is that dependent (§ 8.22). A floor of 0 is §`FLOOR_HIT` |
| `FLOOR_HIT` | Report the parameter as absent, or as exactly zero. Its value and esd stay. Quote an upper limit: `ref.profile_interval(data, path).upper`. Held at 0 and refitted, the others' esds become conditional on it, smaller by √(1−ρ²) each. (Measured: BT-1 `profile.x` 0.0098 marginal, 0.0032 held, WP-1929) |
| `BACKGROUND_ABSORPTION` | Quote ADPs, scales or QPA fractions from this fit. Read the number, not the bit: `report.background.absorption` is the same measurement for **every** screened parameter, fired or not, and `result.identifiability.background_absorption` carries it on the result. **The R² names the victim, not the cause**: a phase broadened past the instrument stops being a set of peaks and becomes a second background, so read `SIZE_UNUSUALLY_SMALL` / `STRAIN_UNUSUALLY_LARGE` and `result.microstructure` on every phase before concluding the background function is the thing to change (measured on a four-phase in-situ scan, WP-1130 § Finding 2; along a series, `SEQUENTIAL_WIDTH_GROWTH`). Le Bail and Pawley screen nothing, so there `report.background.worst_absorption` is `None`: not measured, never clean (WP-1465) |
| `HUMP_TOO_NARROW` | Quote **anything** from this fit: the peak parameters, the displacement parameters the hump was meant to protect, or the Rwp. `value` is the fitted width as a multiple of the instrumental FWHM at its own position (the case it was built for is ~20×). For a real unindexed line, use a second phase or Layer 0's unmatched-peak report, never a hump |
| `EXTRA_PEAK_ON_REFLECTION` | Quote the intensity split between the phase and the declared peak as measured: it is the §3 degeneracy. Not wrong by itself, since a holder line over a sample peak is what the member is *for*. Before declaring a component to remove one misfitting reflection, check the phase's scale, profile and preferred orientation. If the overlap is real, quote the phase quantities and say they overlap |
| `EXTRA_PEAK_NO_INTENSITY` | Quote the declared peak's **centre**, or its esd. The centre is a walk, the zero-scale phase's flat direction one rank down (§`PHASE_UNCONSTRAINED`), and the area's esd comes back absent rather than small |
| `ROUGHNESS_ABSORPTION` | Quote roughness and the displacement parameters as two separate results |
| `RESOLUTION_UNCONSTRAINED` | Quote the profile widths, or anything read off them: the crystallite size, the microstrain, `result.microstructure`. McCusker § Synchrotron's named failure, with its remedy: **measure the instrument instead of refining it here.** `lab_calibrate` on a standard with its certified cell held fixed, `save_instrument_profile`, then `load_instrument_profile` before this fit, which holds all five profile terms. There is no threshold on how wide the widths are, because U, V and W are "easily determined" on constant-wavelength neutron data and one threshold would be wrong for one technique. `value` is the Gaussian's share of the width at the median fitted point |
| `ROUGHNESS_UNCONSTRAINED` / `ROUGHNESS_OUTSIDE_REGIME` | Interpret the roughness parameters physically |
| `PHASE_UNCONSTRAINED` | Quote **anything** about this phase (cell, coordinates, ADPs, weight fraction), held or refined alike, and do not read a held value as "it did not move, so it is right". `HIGH_CORRELATION` on the same fit reports ρ≈1 between the phase's cell and its scale: the symptom, where this is the cause |
| `ADP_NOT_POSITIVE_DEFINITE` | Report the tensor as measured |
| `BISO_UNUSUALLY_LARGE` | Read this B as a displacement. Check in this order: a wrong species or occupancy on the site, a missing or wrong absorption correction, a background flexible enough to have eaten the high-angle intensity. The bound is computed from the phase's own cell (Gilvarry 1956); `value` is the refined B. Unlike most rows here it does not withhold the number: a genuinely mobile site (a cavity cation, a superionic sublattice) can sit above the bound honestly, and saying *that* is part of quoting it. `Atom.biso` has no default ceiling, so this row is what speaks on a large B |
| `BISO_NEGATIVE` | Do not quote this B as a displacement. `Atom.biso` has no default floor, so a B below zero lands here rather than as `BOUND_HIT` |
| `OCCUPANCY_ABOVE_ONE` | Quote the value as more atoms of the declared species than the site holds. On a mixed site declared as its lighter species it is site scattering (Mg declared on an Fe-Mg site reads ≈ 2.2 at full Fe); otherwise check the species, the multiplicity and the site's B. The message gives the distance above 1 in esds, and a full site refined freely lands just above 1 about half the time (Measured: synthetic LaB6, a true 1.0 refined to 1.032 ± 0.025, WP-2002). `Atom.occ` has no default ceiling, so this row is what speaks on a large occupancy |
| `STEPHENS_STRAIN_NOT_POSITIVE` | Report any S_HKL |
| `RESOLUTION_NOT_POSITIVE` | Quote the profile widths or anything read off them, and do not trust this fit's own width judgements. A negative V or Y alone is ordinary; this fires only where the **sum** Γ_G², or Γ_L = X/cosθ + Y·tanθ, goes below zero in the fitted range. Nothing raises: `gaussian_fwhm` clamps Γ_G to a 1e-4° floor and the fit goes on converging, and §`HUMP_TOO_NARROW` abstains rather than judge a peak against a resolution that is not there. `value` is the worst Γ_G² or Γ_L; the message names which, the 2θ where it sits and how many fitted points are affected, often every one |
| `STRAIN_UNUSUALLY_LARGE` | Quote the strain, the crystallite size derived from the same profile, or that phase's weight fraction **without saying the width is this large**. This is not an instruction to withhold the number, only to adjudicate it; the threshold is in [`abstention.md`](abstention.md) |
| `SIZE_UNUSUALLY_SMALL` | Quote the crystallite size, the strain, or that phase's weight fraction **without saying the crystallite is this small**. Like `STRAIN_UNUSUALLY_LARGE`, this is not an instruction to withhold the number, only to adjudicate it |
| `SIZE_NORMALISED_ACROSS_WAVELENGTHS` | (info) Read a shared `phases.N.lor_size` / `gauss_size` from a joint fit as the coefficient **your** histogram shows. It is the coefficient at histogram 0's wavelength; each histogram's own copy is `MultiHistogramRefinement.fitted_structures[h]`. Read the crystallite size with `rietx.model.profiles.caglioti.apparent_size_from_size_coefficient` and that histogram's own λ, and the answers agree by construction. Nothing needs doing; a joint fit that shared the degrees instead would land the implied sizes a factor λ_max/λ_min apart while reporting `converged` |
| `DISPERSION_NEGLECTED` | Quote QPA weight fractions. X-ray sources only. (Measured: RMS 2.19 → 0.62 wt % once the correction was applied) |
| `NEUTRON_RESONANT_ABSORBER` | Quote an occupancy or a displacement parameter on that site **without first checking this wavelength is away from the resonance**. The neutron twin of `DISPERSION_NEGLECTED`; it fires for any non-X-ray source, TOF included, and reports where it cannot refuse. `warning` where the element itself absorbs ≥ 1000 barn (Cd 2520, Eu 4530, Sm 5922, Gd 49700), `info` otherwise (Yb 35, whose resonance lives in the minority ¹⁶⁸Yb at 2230). A wavelength-resolved fit may not use one thermal value at all |
| `SPECIES_FALLBACK_NEUTRAL` | Assume the model scatters like the ion its species label names. `value` is the fractional error on \|f\| at s = sinθ/λ = 0; every substitution fires one unless `refine.SPECIES_FALLBACK_MIN_DELTA_FRAC` raises the floor. A phase *ratio* can survive it when every absolute wt % is wrong. Silent only under a constant-wavelength neutron source (`neutron_cw`); a TOF source gets it |
| `HARMONIC_FRACTION` | Transfer the fitted per cent to another histogram, or read it as a property of the specimen. At `warning` level (past 15 %) do not read it as a measurement of the beam at all; the tick marks against the unfitted peaks are what to check |
| `HARMONIC_ABSENT` | Read it as a failure of the correction. It is a *result* |
| `HARMONIC_HELD` | Quote the harmonic fraction at all. Free `instrument.source.lines.*.weight` in a stage **after** the profile and the scale have settled |
| `ABSORPTION_ESTIMATE_UNAVAILABLE` | Assume the absorption correction ran. The fit has **no** specimen absorption correction |
| `ABSORPTION_MU_R_OUT_OF_RANGE` | Trust the magnitude of the correction: µR > 1 extrapolates the Rouse fit |
| `ABSORPTION_THICKNESS_MATTERS` | Quote displacement parameters without checking the flat specimen's thickness |
| `ABSORPTION_PLATE_THICKNESS` | (info) Read it as a fit problem. A transmission plate far from µt = 1 costs counts, not accuracy |
| `WAVELENGTH_CALIBRATION` | (info) Quote the cell without saying what pinned the scale the wavelength was measured against: the **held cell** in a single-histogram fit, or which histogram's wavelength was **held** in a joint one. It fires whenever a wavelength was refined. The reference is the wavelength **declared when the refinement was constructed**, so the ppm is *cumulative* across successive λ-freeing stages (a `branch` inherits that reference, a `checkout` never resets it, only an instrument `edit` re-declares it). It is the only evidence the refinement offers for the move, deliberately not an Rwp comparison. Read a move inside its own esd as "this measured nothing", and one far past the beamline's known drift as a modelling error in *that* histogram (an unmodelled harmonic, a zero shift traded against λ), not a calibration result |
| `CAPILLARY_OFFSET_UNAVAILABLE` | (info) Read a cell from this fit as free of position systematics. It fires on any capillary geometry with no radius, calibrated synchrotrons included (11-BM among them): there the 2θ scale is pinned and a certified cell reproduces to spec, so note it and move on. On a laboratory capillary the held offset is a real accuracy gap. (Measured: 143 ppm on both axes of a BT-1 refinement, c/a agreeing to 3.4 ppm) |
| `BRINDLEY_OUTSIDE_REGIME` | Prefer the corrected fractions: past µR ≈ 0.05 the "correction" can be further from truth than none, the QPA round robin's community-wide finding (Madsen et al. 2001; Scarlett et al. 2002) |
| `MICROABSORPTION_SKIPPED` | Assume microabsorption was handled |
| `PAWLEY_OVERLAP_UNRESOLVED` | Use an individual reflection intensity from the group |
| `PAWLEY_OFF_DATA_RIDGED` | (info) Export or use a named intensity. One row per phase |
| `DATA_SUPPORT_LOW` | Read the esds as the whole story. `warning` below three effective observations per structural parameter, `info` between three and five; the counts are on `result.data_support`. Start cutting parameters from `result.identifiability`. More points across the same peaks raise N and nothing else |
| `PATTERN_UNDERSAMPLED` | Quote integrated intensities, ADPs or QPA fractions and expect the step size not to be the limit. **No choice made after the fact repairs it.** The number is `PatternDiagnostics.steps_per_fwhm`, from `diagnose(data)` before any refinement. It fires under five steps across the median resolved peak's FWHM; above ten there is no code at all, since oversampling costs beam time, not validity |
| `LOW_ANGLE_UNMODELLED` | (warning) Trust the background below the first reflection because `air_scatter_gain` did not fire: it tests the envelope over the *whole* range, which a narrow tail barely moves (Ba₂FeSbSe₅ 1.5 K: 0.019 vs 0.3). This code reads the fit's own residual over `[two_theta_min, first_tick − 2·FWHM)`, with `first_tick` the lowest image (any line) of a reflection whose window norm ‖y/σ‖ reaches 3σ, and fires when its mean weighted-squared residual exceeds 3× the whole-pattern reduced χ² (`value`). Silent under ten channels in the region. The message names both remedies and picks neither: only someone looking can tell a beam edge from a wrong background |
| `AIR_SCATTER_UNDECLARED` | (warning) Read a P-spline fit's χ² as the background's best without the 1/(2θ) term `auto_background`'s envelope test declines on humped, line-dense data. `value` = share of χ² a background refit with the column removes, Bragg held (fires ≥ 0.5 %, ≥ 25× χ²_red). Fires where `LOW_ANGLE_UNMODELLED` can be silent |
| `RESTRAINT_TENSION` | Silently accept the averaged compromise: the data and your prior disagree by >3σ |
| `RESTRAINT_PAIRS_STALE` | (warning, plan end) Read the anti-bump list as complete. The list (`anti_bump_restraints`) is built once; `where` names atoms that came inside the minimum your rows give their species pair during the run, unlisted. Rebuild it at the answer, refit |
| `SEQUENTIAL_*`, `SERIES_PATTERN_FAILED` | Look for them here: they arrive on a `SeriesResult`. All but one are in §9b, [`references/series.md`](series.md); `SEQUENTIAL_PERSISTENT_FINDING` is in §6, [`references/abstention.md`](abstention.md) |
| `CONSTRAINT_ACTIVE` | (info, the default `lm` driver only; never `trf` or a joint fit) Read the constrained coefficients as free-fit measurements. The message names the constraint (the Stephens cone or the Γ_G² floor). Vary the start before quoting. It is the *only* signal a declared constraint was active |
| `CELL_DEGENERATE_PROBE` | (info) Read this as anything about the reported values. `value` counts the refused trials over every completed stage, and the message names the stages. Nonzero is ordinary on a poorly-constrained cell |
| `COVARIANCE_UNAVAILABLE` | (warning) Read an absent esd on this result as "that parameter was not refined", or refit to make the warning go away and quote the first fit's values with the second fit's esds. Quote values and esds from one fit. `where` names the stage: on an intermediate one, a `HIGH_CORRELATION` its correlation guard would have raised is unknown rather than absent |
| `CELL_RUNAWAY` | (warning) A free cell parameter left ±15% (`a`/`b`/`c`, so any length ≤ 0) or ±6° (angles) of its stage-start value. Its phase's free cell went back to that start and was held while the stage solved again (`StageResult.cell_reset`), never a bound the solver saw. Fired in the answer stage: that cell is not a measurement, it and every path tied to it carry no esd, and a held one leaves `parameters`. One driven only by a free `vars.X` is named, never reset. Fired earlier: later stages refined it again from its start |
| `HOLD_BLOCKED_PLAN` | (info) Read it as a fault, or the paths it names as measurements. They carry no esd and belong in a report as a constraint (§`PHASE_UNCONSTRAINED`'s rule for a held phase). `StageResult.blocked_by_hold` names them per stage. Read it closely when you did not declare the hold: a reopened `.rex` restores the register |
| `STAGE_PATH_UNKNOWN`, `STAGE_PATH_NOT_FREE` | Read the stage it names as having refined what you asked for. `StageResult.unknown_paths` lists the UNKNOWN ones. Warnings, never raised. Fix the plan and refit |
| `PARAMETRIC_OUT_OF_RANGE`, `PARAMETRIC_FORM_REJECTED`, `PARAMETRIC_TARGET_UNSEEN` | (joint fits) Quote what `where` names: the target there (out of range, or unseen by its pattern) or the coefficients (an equation the data refuses). Narrow the subset or change the order |
| `STAGE_FREED_NOTHING` | (info, joint fits) Read histogram `value`'s instrument parameters as refined by the stages named. Nothing is wrong when that histogram declares no such component (§ 8.28); otherwise list its `hist.<h>.*` rows and add a glob that reaches them. `StageResult.unreached_histograms` has the globs per stage |
| `QPA_UNAVAILABLE` | Read `result.qpa is None` as "this specimen is single-phase" or as any statement about composition. `where` names the scales that died. It is reported rather than raised on purpose: raising took a whole 157-pattern sequential run down with one bad pattern |
| `QPA_FRACTION_RANGE` | (info, on every `FractionProfile.diagnostics` whose fit has an esd; `ref.profile_fraction(data, phase)` returns it and no fit emits it) Quote the phase's `weight_fraction` ± its esd when `value` is well above 1. `value` is the farthest admissible fraction's distance from the fit's, in the esd's 95 % half-widths; then quote the range and the widths, never the point. The test is Δχ² = 3.84·χ²_red·f² against the lowest χ². A `value` under 1 confirms the esd; it does not establish that the phase is present, and a range reaching 0 % says it is not (`judging.md` § "a trace phase's esd describes one basin") |
| `MODEL_FAR_FROM_DATA` | (error) Read `status`, the parameter values or their esds at all. `status` may say `converged` and `result.usable` reads False. The message quotes the share of above-background intensity the model accounts for (0.2 % on the reproduction). Check the cell (~1 % precondition, §1), wavelength, zero shift and 2θ range, then re-index |
| `STAGE_MAX_ITER` | Read the result's `status` as covering every stage: it is the *last* stage's. Raising `max_iter` buys solver evaluations, not a different minimum; the stages that stall are the degenerate groups in §3 (measured: three identical mixtures, same models and parameter counts, 39 s / 858 s / 2838 s with no difference in the answer) |
| `FROZEN_COMPILE_STALE` | (info) Read it as a fit defect, or quote the history node's Rwp as the result's. It fires when the two χ² differ by more than 1 % (`value` is that fraction, both figures in the message). The minimum is not biased by it. A large value says the last stage travelled far enough to re-size its windows, so split that stage if the curve it drew matters. It never aggregates into `SEQUENTIAL_PERSISTENT_FINDING`: it is about how a pattern was measured, not about the model. A Pawley result and a joint fit get no fresh compile and never carry this row |
| `SPACE_GROUP_SETTING_ASSUMED` | (warning) Read the composition, ZMV or any weight fraction as the one you meant. It covers 40 symbols (the `:1`/`:2` origin choices and the rhombohedral `:H`/`:R` axes); spinel's origin-2 coordinates under a bare `F d -3 m` give Mg2AlO4 where MgAl2O4 was meant. The message quotes the **cell contents each setting implies**: recognise yours and write it into the symbol (`"F d -3 m:2"`). Where the sites that swap carry one species the contents agree, so it quotes the **site multiplicities** instead: Mn3O4 under `I 41/a m d` is Mn12O16 either way and the wrong choice still moves half the intensity. A `:H`/`:R` pair gets alternatives and no composition. A symbol carrying its setting is silent; what each foreign format can say is in §7g and §7h |
| `SITE_SNAPPED_TO_SPECIAL_POSITION` | (warning, on `result.diagnostics` and on the reader's channel from `Structure.from_cif(..., diagnostics=[])`) Read the site's multiplicity as the general-position one. The message says which of two things happened. "Expanded there" leaves the coordinates as stored. "Moved onto" means the CIF reader rewrote them, because the file states the multiplicity (that column, or `_atom_site_Wyckoff_symbol`) and the site was within 1e-3 of the position it names. If the multiplicities match the source's own, nothing is wrong and the coordinates are merely rounded; if they disagree, the coordinates and the space group are telling you different things |

The `TOPAS_*` and `FULLPROF_*` families are **not here**: they belong to
`rietx.io.projects`, they fire at *import* rather than on a fit, and none of
them ever reaches `result.diagnostics`. They have their own file —
§7g, [`references/diagnostics-projects.md`](diagnostics-projects.md) — because
the question they answer comes before a fit exists: *is the model I just
imported the model that file describes?* Load that one if a TOPAS `.inp` or a
FullProf `.pcr` import handed you a diagnostic.

The reader's own family — the `PATTERN_*`, `CIF_*` and vendor-attenuator
rows — is in §7i, [`references/diagnostics-reading.md`](diagnostics-reading.md).
Each fires on a quirk of one file, so load it when a reader handed you a
diagnostic.

The `RECIPE_*` family belongs to the PowderLine
recipe reader (`read_recipe`, `Recipe.diagnostics`) rather than
`result.diagnostics`, and it answers a question the others do not: *how does
the fit I am about to run differ from the one the recipe describes?* It has
its own file too — §7g, [`references/diagnostics-projects.md`](diagnostics-projects.md)
— since a PowderLine recipe is another program's file just as a TOPAS `.inp`
or a FullProf `.pcr` is. Load that one if a PowderLine recipe handed you a
diagnostic.

```python
codes = {d.code for d in result.diagnostics}
if "BACKGROUND_ABSORPTION" in codes:
    # stiffen the background BEFORE reporting anything intensity-derived
    ...

# the same measurement as evidence rather than as a bit — and the two
# background hypotheses, which are advice: they change what the background can
# *absorb*, not which parameters move, so there is no stage to run
bg = report.background                      # None only if no background curve
bg.worst_absorption, bg.worst_absorption_path    # 0.46, "…atoms.0.biso"; None = not measured
bg.absorption                                    # every screened path → R²
bg.off_region_chi2_reduced, bg.off_region_durbin_watson   # 12.6, 0.19
report.action("decrease_background_flexibility")  # fewer terms, larger λ
report.action("increase_background_flexibility")  # capped at 0.6 — see below
```

`increase_background_flexibility` is capped however strong its evidence,
because an amorphous hump and an un-modelled broad crystalline phase produce
the same between-peak signature as a too-stiff background, and bending the
background over either of the last two **hides** it while improving every
statistic. `add_impurity_phase` rides in its `alternatives` for that reason,
and each names the other. If you add the flexibility anyway, read any QPA
afterwards as fractions of the crystalline content you did model.
