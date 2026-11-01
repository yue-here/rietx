# Phase fractions

This page gives the weight fractions a Rietveld fit reports for its phases: the fields of the answer, what an esd on a fraction does and does not cover, the width profile that tests whether a fraction is determined, the Brindley microabsorption correction, and the limits of the method.

A Rietveld fit refines one scale per phase, and the scales are proportional to how much of each phase is present.
The Hill-Howard relation {cite}`hill1987` turns them into weight fractions, W<sub>p</sub> ∝ S<sub>p</sub>·(ZMV)<sub>p</sub>, renormalised to sum to 1 across the phases {eq}`corr-qpa`.
Every Rietveld fit reports them on `RefinementResult.qpa`, and a single phase reads 100 % (unless it has no reflection in range, which leaves it none).
A Le Bail or Pawley fit reports none, because its scales are degenerate with the extracted intensities.
[How to find the weight fraction of each phase in a mixture](../guides/qpa.md) gives the procedure on a shipped pattern.

<!-- api-doc: no-exec — it refines a three-phase mixture -->
```python
result = rx.refine(pattern, structure, instrument)
for row in result.qpa.phases:
    print(row.name, 100 * row.weight_fraction)
```

## The answer

`QuantitativePhaseAnalysis` is the mixture's answer.

| Field | Holds |
|---|---|
| `QuantitativePhaseAnalysis.phases` | one `PhaseQuantity` per phase |
| `QuantitativePhaseAnalysis.method` | `"zmv"`, the Hill-Howard route, and the only one |
| `QuantitativePhaseAnalysis.crystalline_only` | `True`: the fractions are of the modelled crystalline content alone |
| `QuantitativePhaseAnalysis.unmeasured_phases` | the phases with no fraction: no reflection in range, or a scale a stage held |
| `QuantitativePhaseAnalysis.unmeasured_held` | the part of that list a stage held while a reflection is in range at the answer |
| `QuantitativePhaseAnalysis.microabsorption` | the `MicroabsorptionCorrection` record, when the correction ran |
| `QuantitativePhaseAnalysis.microabsorption_skipped` | why it did not run, when a phase asked for it |

`PhaseQuantity` is one phase's row.

| Field | Holds |
|---|---|
| `PhaseQuantity.name` | the phase name |
| `PhaseQuantity.weight_fraction` | its mass fraction, from 0 to 1, or `None` for an unmeasured phase |
| `PhaseQuantity.weight_fraction_stderr` | that fraction's esd, or `None` |
| `PhaseQuantity.scale` | the refined scale it came from |
| `PhaseQuantity.cell_mass` | Z·M, the mass in one unit cell, in g/mol |
| `PhaseQuantity.cell_volume` | V, in Å³ |
| `PhaseQuantity.zmv` | their product, the quantity the fractions are proportional to |
| `PhaseQuantity.z` | formula units per cell |
| `PhaseQuantity.molar_mass` | one formula unit's mass, in g/mol |
| `PhaseQuantity.particle_radius_um` | the particle radius you supplied, in µm, when the correction ran |
| `PhaseQuantity.mu_cm` | the phase's linear attenuation coefficient µ, in cm⁻¹ |
| `PhaseQuantity.mu_r` | its µ·R, with R the particle radius |
| `PhaseQuantity.brindley_tau` | its Brindley particle-absorption factor τ |
| `PhaseQuantity.weight_fraction_corrected` | the fraction after that correction |

The last five fields are `None` unless the microabsorption correction ran.

`PhaseQuantity.cell_mass` and `PhaseQuantity.cell_volume` are the unambiguous quantities.
`PhaseQuantity.z` and `PhaseQuantity.molar_mass` split the cell mass into an integer count and a formula-unit mass, and fall back to `z = 1` with `molar_mass` equal to `cell_mass` when the composition does not reduce to integers under refined occupancies.
The weight fraction never depends on that split, so a surprising `z` changes nothing else.
The site multiplicities are the ones the model compiled, so a coordinate that drifted near a special position cannot change the count.

`PhaseQuantity.weight_fraction_stderr` is propagated through the covariance of all the scales together, rather than from each scale's esd alone, so it carries the same conditioning as every other esd rietx reports.
W<sub>p</sub> divides by a sum over every phase, so one scale the data carry no gradient in makes every fraction's esd unknown.
The whole block of esds is then `None`, and [`QPA_ESD_UNAVAILABLE`](diagnostics-refinement.md#qpa_esd_unavailable) names the phase that withheld it.
Where the refined scales give a non-positive Σ S·ZMV, there are no fractions to form: `RefinementResult.qpa` is `None`, and [`QPA_UNAVAILABLE`](diagnostics-refinement.md#qpa_unavailable) names the scales at or below zero.

### A mixture of three phases

Sample 1e of the IUCr round robin on quantitative phase analysis {cite}`madsen2001` is corundum, zincite and fluorite, weighed at 55.12, 15.25 and 29.62 wt %.
Under the protocol of `tests/test_acceptance_qpa_roundrobin.py`, with anomalous scattering off, the fit reaches Rwp 0.126 and gives:

| Phase | W (%) | esd | Z | Z·M (g/mol) | V (Å³) | Weighed (%) | Error |
|---|---|---|---|---|---|---|---|
| corundum | 57.25 | 0.43 | 6 | 611.77 | 254.68 | 55.12 | +2.13 |
| zincite | 12.96 | 0.22 | 2 | 162.76 | 47.59 | 15.25 | −2.29 |
| fluorite | 29.79 | 0.37 | 4 | 312.30 | 163.04 | 29.62 | +0.17 |

The errors are inside the published participant spread for this sample.
Corundum's error is 5 times its esd and zincite's 10 times, which is the usual case.
An esd measures how well this model fixes the scales against this pattern, and it says nothing about how close the answer is to the weighed composition.

## One basin

`PhaseQuantity.weight_fraction_stderr` comes from the curvature of χ² where the fit converged.
It describes the basin the fit stopped in, and it cannot see any other.
For most fractions that is the whole story, and for a trace phase it may not be.

A phase's scale and its peak width trade against each other.
Broadened far enough, a weak phase's peaks become a hump the background can share, and its scale can then grow with almost no change in χ².
Along that ridge χ² can hold separate basins at nearly the same value.
Each basin has ordinary curvature, so each gives a tight esd, and the fit reports whichever it reached.
The case was first measured on a laboratory in-situ series, where one pattern admitted three basins at almost the same Rwp and the fit flagged nothing.

No quantity measured at one point sees this, because every basin looks healthy from inside.
The check is a scan along the width, and `Refinement.profile_fraction` runs it.

1. It pins one of the phase's width terms at a series of values, from no sample broadening up to a peak width of half the fitted range.
2. At each value it refits everything else, starting from where the previous value finished.
3. It reads the phase's weight fraction and the data's χ² at every point.

<!-- api-doc: no-exec — needs a fitted multi-phase refinement; tests/test_qpa_multimodal.py runs this call -->
```python
profile = ref.profile_fraction(data, "CaF2")
print(profile.range_low, profile.range_high, profile.excess)
for d in profile.diagnostics:
    print(d.code, d.message)
```

The axes are the phase's own `lor_strain`, `lor_size`, `gauss_strain` and `gauss_size`, each one that was free in the last fit, and never its scale.
`axes=` names them instead, and `fwhm=` sets the grid as the phase's own FWHM in degrees 2θ at the middle of the fitted range.
The default grid is 0 and then 11 values evenly spaced on a log scale from 0.01° to half the fitted span, so the scan costs 12 refits for each width term.
Every refit runs on a branch, so the working state and `Refinement.result_` are left as they were.
The call runs in Rietveld mode only, after a fit.
It refuses a phase name it does not know, a path that is not one of the phase's width terms, a tied width, an empty or non-finite grid, and a phase none of whose width terms was free.

A refit at a pinned scale could reach the hump basin only by broadening the phase until the data cannot see it.
At that point the stage holds the phase's structure ([Held parameters](refinement.md#held-parameters)), so a scan along the scale would stop short of the basin it is looking for.

A point is admissible when its χ² is within {{ FRACTION_PROFILE_DCHI2 }} × χ²<sub>red</sub> × f² of the lowest χ² the profile found, with f the fit's `Statistics.esd_inflation`.
That is the 95 % Δχ² for one parameter, scaled by the two factors every esd already carries.
On a single well-behaved minimum it reproduces W ± 1.96 esd.
On the test suite's control pattern every admissible fraction stayed within 0.79 of that interval's half-width.

`FractionProfile` is the answer.

| Field | Holds |
|---|---|
| `FractionProfile.phase` | the phase's name |
| `FractionProfile.phase_index` | its position in the structure |
| `FractionProfile.axes` | the width paths that were pinned |
| `FractionProfile.weight_fraction` | the fit's fraction, copied from its row |
| `FractionProfile.weight_fraction_stderr` | the fit's esd, or `None` |
| `FractionProfile.points` | one `FractionProfilePoint` per pinned value |
| `FractionProfile.chi2_fit` | the fit's own data χ², not reduced |
| `FractionProfile.chi2_best` | the lowest data χ² found, the fit's included |
| `FractionProfile.delta_chi2_cut` | the admissibility cut, in χ² |
| `FractionProfile.fit_admissible` | whether the fit's own point is within the cut |
| `FractionProfile.range_low`, `FractionProfile.range_high` | the smallest and largest admissible fractions |
| `FractionProfile.excess` | the farthest admissible fraction from the fit's, in units of 1.96 esd, or `None` without an esd |
| `FractionProfile.diagnostics` | the `QPA_FRACTION_RANGE` record, wherever `FractionProfile.excess` is defined |

| Field | Holds |
|---|---|
| `FractionProfilePoint.axis` | the width path pinned |
| `FractionProfilePoint.value` | its value, in its own unit |
| `FractionProfilePoint.fwhm` | that value as the phase's FWHM at mid-range, in degrees 2θ |
| `FractionProfilePoint.admissible` | whether the point is within the cut |
| `FractionProfilePoint.weight_fraction` | the fraction the refit reached |
| `FractionProfilePoint.chi2` | its data χ² |
| `FractionProfilePoint.delta_chi2` | its distance above `FractionProfile.chi2_best` |
| `FractionProfilePoint.rwp` | its Rwp |
| `FractionProfilePoint.status` | how the refit's stage ended |
| `FractionProfilePoint.error` | why a refit raised, with the numbers left `None` |
| `FractionProfilePoint.node_id` | the history node the refit recorded |

The range is an inner bound.
Each admissible point's fraction is inside the 95 % profile interval for W, so a finer grid can only widen it.
When `FractionProfile.fit_admissible` is `False`, a pinned refit found χ² lower than the fit's by more than the cut, so the fit did not reach the lowest basin along this ridge.

Every profile of a fit with an esd carries a [`QPA_FRACTION_RANGE`](diagnostics-refinement.md#qpa_fraction_range) info record.
It names the range and the widths that produced it, and its value is `FractionProfile.excess`, the farthest admissible fraction's distance from the fit's in the esd's 95 % half-widths.
Below 1, the profile confirms the esd: the controls reached at most 0.79.
Well above 1, the fraction is not determined by this pattern, whatever its esd says, so quote the range rather than the point: the synthetic trace below reached about 99.
Before 1.10 the record was the warning `QPA_FRACTION_UNDETERMINED`, which fired only past an excess of 2, a number chosen rather than measured.
The basins separate only on information the fit does not have: a width held at a value the specimen justifies, a background that can take the hump itself, or more counts on the phase's strongest lines.

The synthetic trace is LaB₆ with 1 wt % CaF₂ and a small amorphous hump under a six-term Chebyshev background, in `tests/test_qpa_multimodal.py`.
The fit reports CaF₂ at 0.93 ± 0.33 wt %, and the profile admits everything from 0.93 % to 77.1 %, in two basins separated by a barrier the data can see.

A wrong Z·M·V is a different failure.
A wrong site multiplicity or a wrong space-group setting ([`SITE_SNAPPED_TO_SPECIAL_POSITION`](diagnostics-structures.md#site_snapped_to_special_position), [`SPACE_GROUP_SETTING_ASSUMED`](diagnostics-structures.md#space_group_setting_assumed)) moves the Z·M·V factor of one phase by a fixed multiple, at unchanged Rwp.
A width profile cannot see that, and it finds only the case where the pattern admits several fractions at once.

## Scope

`QuantitativePhaseAnalysis.crystalline_only` is `True` on every result.
The fractions are of the modelled crystalline content, renormalised across the phases in the model, so they sum to 1 whatever is missing.
In the three-phase mixture above they sum to 1 to nine decimal places.

Two things therefore do not show as a shortfall:

- an amorphous fraction, such as glass, a poorly crystalline binder or an X-ray amorphous gel, which the crystalline phases absorb in proportion;
- a crystalline phase you did not put in the model, whose intensity is shared out among the phases you did.

Neither is visible in the fractions, because both leave a set that sums to 1.
The fit shows them.
An amorphous fraction is a broad hump the background has to absorb, and a missing phase is a set of peaks with no tick under them, which the report's Layer 0 names ([The fit report](report.md)).
`PatternDiagnostics.amorphous_hump_score` is the pattern-level reading of the first, measured before any fit ([Pattern diagnostics](pattern-diagnostics.md)).
It is the RMS of what remains in the background envelope after a cubic and a 1/(2θ) term, over the median level, so it measures broad structure no ordinary background shape accounts for.

Quote a fraction as a share of the crystalline content: 57.3 % corundum is wrong if the specimen is 20 % glass, while 57.3 % of the crystalline content is right either way.

### A phase with no reflection in the fitted range

A phase none of whose reflections lies in the fitted range has no fraction: its `weight_fraction` and esd are `None`, and `QuantitativePhaseAnalysis.unmeasured_phases` names it.
Its scale's column is zero at every value, so the stage holds the scale at the value you handed in, under every solver, and a fraction read off it would be that start value.
The other fractions are normalised over the phases seen in range, so they sum to 1 without it.
They are relative to those phases, not to the crystalline content: a specimen known to hold the unmeasured phase has no absolute fractions from this range.
[`PHASE_UNCONSTRAINED`](diagnostics-refinement.md#phase_unconstrained) says so, and so do the QPA table's caveats.
The Brindley correction is skipped while a phase is unmeasured, with that reason in `microabsorption_skipped`, because its mixture-average µ needs every phase's fraction.
A phase with no line wants a wider range; one whose scale a stage held (a refined zero shift moved a line into range afterwards) wants a start where a reflection is already in range, so its scale refines. Either may be taken out of the model.
Internal-standard and amorphous quantification, spiking a known weight of a known phase and solving for the rest, is not implemented.

## Microabsorption

A strongly absorbing coarse phase hides the inside of its own particles, so its intensity is suppressed against a weakly absorbing phase and its weight fraction comes back low.
This is the Brindley microabsorption effect {cite}`brindley1945`, {eq}`corr-brindley`.

The correction needs a particle radius for every phase, and the pattern cannot give one.
Set `Phase.particle_radius_um` on every phase from a micrograph or a particle-size measurement.
Profile broadening measures a coherent domain size, which is not a particle size ([Size and strain](derived.md#size-and-strain)).
With no radius on any phase the correction is not attempted.
With a radius on some phases but not all, it is skipped, `QuantitativePhaseAnalysis.microabsorption_skipped` says why, and [`MICROABSORPTION_SKIPPED`](diagnostics-refinement.md#microabsorption_skipped) is reported.

µ comes from the pattern's own radiation.
An X-ray pattern reads the McMaster photoabsorption table by element, and a constant-wavelength neutron one reads the Sears (1992) cross-sections by nuclide, the same two tables the capillary µR estimate uses.
A source with neither skips the correction and says why.
A nuclide in the structure (`D`, `2H`, `7Li`) enters the cell mass at its own mass: 2.0141 for ²H, and the mass number otherwise, within 0.26 % of the nuclide's mass above A = 4.

When the correction runs, `QuantitativePhaseAnalysis.microabsorption` records what it assumed.

| Field | Holds |
|---|---|
| `MicroabsorptionCorrection.method` | `"brindley_sphere"` |
| `MicroabsorptionCorrection.wavelength` | the primary emission line µ was evaluated at, in Å |
| `MicroabsorptionCorrection.mu_mean_cm` | the volume-weighted mean attenuation of the solid mixture, in cm⁻¹ |

The corrected fraction is reported beside the uncorrected one and never replaces it.
`PhaseQuantity.weight_fraction` stays the uncorrected Hill-Howard number, and `PhaseQuantity.weight_fraction_corrected` sits beside it.
The esd belongs to the uncorrected fraction.
The corrected one inherits the uncertainty of the radii you supplied, which dominates and is not statistical, so the statistical esd does not apply to it.

### The Brindley regime

Brindley's treatment is derived for fine to medium powders, µ·D ≤ 0.1 with D the particle diameter, so µ·R ≤ {{ BRINDLEY_MU_R_FENCE }}.
Past that the expression is used outside what it was derived for, and [`BRINDLEY_OUTSIDE_REGIME`](diagnostics-refinement.md#brindley_outside_regime) names the phases.
`PhaseQuantity.mu_r` travels with the answer for that reason.

Sample 4 of the round robin was designed to fail on microabsorption: corundum, magnetite and zircon, weighed at 50.46, 19.64 and 29.90 wt %.
With order-of-magnitude radii of 0.5, 5.0 and 1.5 µm and the same protocol, the fit reaches Rwp 0.279 and gives:

| Phase | µ (cm⁻¹) | µR | τ | W (%) | Error | Corrected (%) | Error |
|---|---|---|---|---|---|---|---|
| corundum | 125.8 | 0.006 | 1.009 | 74.60 | +24.14 | 70.96 | +20.50 |
| magnetite | 1134.8 | 0.567 | 0.520 | 4.56 | −15.08 | 8.42 | −11.22 |
| zircon | 379.8 | 0.057 | 0.969 | 20.84 | −9.06 | 20.63 | −9.27 |

The table makes three separate statements.
The uncorrected errors have the microabsorption shape: the two absorbing phases suppressed and the weakly absorbing one inflated.
The correction moves the two extremes toward the weighed values and leaves zircon slightly worse, which is the shape of a correction applied outside its regime.
`BRINDLEY_OUTSIDE_REGIME` fires on magnetite (µR = 0.567) and zircon (µR = 0.057), so the corrected numbers arrive labelled as not quotable.
A corrected fraction still 11 wt % from the weighed value is evidence that this specimen needs a different preparation.

## Writing the table

`Refinement.write_qpa_table` writes the table to a CSV file, or a tab-separated one for a `.tsv` or `.tab` suffix ([Exports and derived tables](exports.md)).
The file opens with `#` comment lines stating the crystalline-only scope and, where it applies, the microabsorption correction or why it was skipped.
A joint fit reports a `QuantitativePhaseAnalysis` per pattern on `HistogramResult.qpa`, and a series reports one per pattern on `SeriesEntry.qpa`.
`SeriesResult.qpa_trajectory` turns one phase's fraction into a trajectory across the series ([Sequential refinement](series.md)).
