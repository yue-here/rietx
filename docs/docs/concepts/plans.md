# About refinement plans

A refinement plan frees the parameters in stages, and this page says why rietx stages a fit, what each preset is for, the order its presets free the parameter groups in, and where that order comes from.

## Why a fit runs in stages

Most of what goes wrong in a refinement is a correlation.
Two parameters change the calculated pattern in nearly the same way, so the data cannot tell them apart ([About correlations and esds](correlations.md)).
Freed together from a poor starting point, such parameters walk into a local minimum that a staged release avoids.

A plan is a list of stages, and each stage frees one group of parameters and runs before the next group joins.
Staging is cumulative: a parameter stays free once freed, so each stage refines everything released so far, and the last stage refines everything together.
The IUCr guidelines {cite}`mccusker1999` ask for that last joint stage, because an esd is correct only when every parameter, profile and structural, is refined at once.

A plan is an ordinary Python object.
`RefinementPlan.stages` is a list of `Stage`, and [How to add a stage to a refinement plan](../guides/plan.md) edits one.
[Plan presets](../reference/plans.md) draws every stage of every preset, and [The refinement](../reference/refinement.md#plans) gives the plan and stage fields.

## The presets

Each preset is a constructor on `RefinementPlan`, and `Refinement.fit` also takes its name, as `plan="lab_calibrate"`.
`PLAN_INFO` gives each preset's title, description, modes and when to use it, so a program can offer the choice without a list of its own.

| Constructor | Frees, in order |
|---|---|
| `RefinementPlan.mccusker_default` | scale and background, zero shift, cell, the constant width W, then U, V, X and Y; no structure |
| `RefinementPlan.mccusker_structural` | the same, then declared extra components, coordinates, displacement parameters, preferred orientation, extinction and surface roughness |
| `RefinementPlan.magnetic_structural` | scale and background, the magnetic moment moduli, every moment degree of freedom, then the `mccusker_structural` order with the moments still free |
| `RefinementPlan.lab_bragg_brentano` | the `mccusker_default` order with the specimen displacement beside the zero shift, then the emission-line weights and axial divergence, then surface roughness |
| `RefinementPlan.lab_calibrate` | the instrument on a standard: scale and background, zero shift and specimen displacement, the widths, line weights and axial divergence, then displacement parameters; never the cell, which stays at the standard's certified value |
| `RefinementPlan.lab_sample_refine` | a specimen against a calibrated instrument: scale and background, specimen displacement, cell, the specimen's size and strain widths, displacement parameters and surface roughness |
| `RefinementPlan.profile_only` | background, zero shift, cell and widths, for a Le Bail fit or a Rietveld fit that leaves the structure alone |
| `RefinementPlan.pawley_default` | the same groups for a Pawley fit |
| `RefinementPlan.magnetic_width` | the magnetic moment with the scale and background, then the magnetic peak widths, then both ([Magnetic peak width](../reference/magnetic.md#magnetic-peak-width)) |

`fit` runs `mccusker_default` unless you pass another.
`lab_calibrate` and `lab_sample_refine` are the two halves of separating the instrument's peak width from the specimen's ([Instrument and specimen](parameters.md#instrument-and-specimen)).

## The order the presets follow

The presets follow the order the IUCr Rietveld refinement guidelines set out {cite}`mccusker1999`.

1. Background and scale first. The guidelines want good starting values for the background before the structure is touched, and the calculated pattern scaled to the observed one before anything is read off a difference plot.
2. Peak positions next. The cell and the 2θ corrections refine before the widths and before the structure: the zero shift, and in `lab_bragg_brentano` and `lab_sample_refine` the specimen displacement. The guidelines say a refinement cannot work until the calculated peak positions match the observed ones.
3. Then the widths, then the asymmetry. `mccusker_default` stops after the widths, and `lab_bragg_brentano` and `lab_calibrate` continue with a stage for the line weights and axial divergence.
4. Then the structure, coordinates before displacement parameters. The scale, the occupancies and the displacement parameters correlate with each other and are the parameters most sensitive to a background error, so they come after the positions.
5. Everything free together at the end, which staging gives every preset.

`mccusker_structural` departs from the guidelines in one place.
The guidelines suggest refining the heavier atoms' positions before the lighter ones, and `mccusker_structural` frees every coordinate in one `coordinates` stage.
Nothing in rietx measures what the split would gain.
If your structure has a large scattering contrast and a poor starting model, split that stage yourself.

## Ordering rules of rietx's own

Three rules in the presets are rietx's own.

The constant width term `w` comes before `u`, `v`, `x` and `y`.
Freed first, the tan θ and 1/cos θ terms take up a constant offset, and then fight `w` for it when it joins.

The intensity corrections come last, after the structure has settled.
Preferred orientation, extinction and surface roughness rescale intensities as a function of angle, and so do the scale, the occupancies and the displacement parameters.
Freed early, a correction takes intensity that belongs to the structure.

Anisotropic strain is freed in the same stage as the isotropic size and strain widths, never after it.
A Stephens block locks `Phase.lor_strain`, because the block's isotropic direction is that same column ([Anisotropic strain](../reference/data.md#anisotropic-strain)).
`lab_sample_refine` frees `phases.*.microstrain.dof.*` beside the size and strain widths for that reason.
A stage after it would leave the isotropic width unrefined until the block's correlated coefficients, up to fifteen of them, turned on at once.
