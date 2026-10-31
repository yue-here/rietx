# The parameter table

This page gives the table of parameters a refinement builds from its models: the fields of a row, why a row cannot be freed, ties and restraints, the bounds a fit runs in, what the editing calls return and refuse, the rows a result reports, and the profile interval for a row on its bound.

A fit does not refine the `Structure` and `Instrument` objects directly.
It refines a flat vector, and the parameter table stands between the two.
The table walks both models, gives every `Parameter` it finds a name, and records which may be varied and which follow another.
{eq}`par-affine` is the mapping, p<sub>phys</sub> = C·p<sub>free</sub> + d.
The table is rebuilt from the models at every stage boundary, so a row is never stale against the objects it came from.

[Parameter map](parameters.md) lists every name with its unit, default and typical range.
[About parameters](../concepts/parameters.md) groups them by what they belong to.

## Names

A name is a dot-path that starts at `phases`, `instrument` or `vars`, the last for a variable you declared with `Refinement.add_variable`.
A number in the middle is a list index, counted from 0 in the order the model stores the list.
The same names, with `*` and `?` as wildcards, are what `Refinement.set_vary`, `Refinement.hold`, `Refinement.untie` and a stage's `turn_on` list take.

A name never contains square brackets.
The matching reads `[0]` as a set of characters, so `phases[0].cell.a` matches nothing and raises no error.

Some names exist only when the model declares the block they belong to.
`phases.0.microstrain.dof.*` appears once the phase carries a `StephensStrain`, `phases.0.atoms.2.adp.*` once that atom carries an `AnisoU`, and `instrument.geometry.capillary_offset_along_beam` only on a capillary geometry.
A wildcard over an absent block matches nothing, so the shipped plans' broad names are safe on any model.

## Rows

`Refinement.parameters` returns the whole table as a list of `ParameterRow`, in the order the free vector uses.
It needs no fit.

```python
import rietx as rx

lab6 = rx.Structure(phases=[rx.Phase(
    name="LaB6",
    space_group="P m -3 m",
    cell=rx.Cell.cubic(4.15689, vary=True),
    atoms=[
        rx.Atom(label="La", species="La", x=rx.Parameter(value=0.0),
                y=rx.Parameter(value=0.0), z=rx.Parameter(value=0.0)),
        rx.Atom(label="B", species="B", x=rx.Parameter(value=0.19964),
                y=rx.Parameter(value=0.5), z=rx.Parameter(value=0.5)),
    ],
)])
ref = rx.Refinement(lab6, rx.Instrument.debye_scherrer(wavelength=0.4139),
                    history=False)

rows = ref.parameters()
assert len(rows) == 42                                  # every scalar, held ones included
assert sum(row.refinable for row in rows) == 25         # what set_vary could free

held = {row.path: row.held_because for row in rows if not row.refinable}
assert held["phases.0.cell.b"] == "tied: = 1·phases.0.cell.a"
assert held["phases.0.cell.alpha"] == "structurally fixed by symmetry or by the model"
```

Two atoms and a default instrument make 42 rows, of which 25 could be freed.

| Field | Type | Holds |
|---|---|---|
| `ParameterRow.path` | `str` | the name |
| `ParameterRow.value` | `float` | the current value, in the parameter's own unit |
| `ParameterRow.vary` | `bool` | whether it is free in the next fit |
| `ParameterRow.lo`, `ParameterRow.hi` | `float` | the stored bounds, inclusive, ±inf where unbounded; a stage can add one the row does not show ([Bounds a stage adds](#bounds-a-stage-adds)) |
| `ParameterRow.tie` | `TieSpec` or `None` | what this value follows ([Ties](#ties)) |
| `ParameterRow.locked` | `bool` | fixed by the structure; no call can free it |
| `ParameterRow.held` | `bool` | held by `Refinement.hold`, or by a floating-origin declaration |
| `ParameterRow.esd` | `float` or `None` | the esd from the most recent fit, where the row was free or tied in it |
| `ParameterRow.mode_fixed` | `bool` | fixed by the Le Bail or Pawley mode |
| `ParameterRow.needs_held_cell` | `bool` | a wavelength that cannot be freed while this pattern's cell is free |
| `ParameterRow.origin_axis` | `(int, int, int)` or `None` | the direction along which this row holds a polar group's floating origin |
| `ParameterRow.help_key` | `str` or `None` | the [parameter map](parameters.md) entry that describes this row's family |

The first eight fields mirror the solver's own row type field for field, and a test holds the two equal.
The rest are deliberate additions.
`esd` is a property of a completed fit, and merging it in lets one listing say both what a parameter is worth and how well it is known.
A tied row's esd is its sources' propagated through C, as σ² = diag(C·Cov·Cᵀ), so an identity tie reports its source's esd.
A row gets an esd only when at least one of its sources was free, and `None` means the esd is unavailable rather than zero.

`ParameterRow.refinable` and `ParameterRow.held_because` are derived.
`refinable` is the one test a program should grey a row by, and `held_because` is the sentence to show beside it.

## Held rows

A row cannot be freed for one of five reasons, and the remedy differs.

| Reason | Means | Lifted by |
|---|---|---|
| `locked` | fixed by the structure: a cell angle the space group fixes, a coordinate on a fully fixed special position, the first emission line's weight, a non-primary line's wavelength, `biso` on a site with an anisotropic tensor, an atom a rigid body places, a position correction the geometry does not have | nothing |
| `tie` | an affine function of other rows, so the freedom lives in its sources | `Refinement.untie`, if the tie is your own |
| `mode_fixed` | refinable in principle, but the Le Bail or Pawley mode fixes it: every atom parameter, each phase's scale and a texture coefficient | switching back to `rietveld` |
| `held` | you declared it does not move, whatever a plan frees; a coordinate held to fix a polar group's origin reads `held` too, and `ParameterRow.origin_axis` names the direction | `Refinement.unhold` |
| `ParameterRow.needs_held_cell` | a wavelength, while this pattern's cell is free, since d = λ/(2 sin θ) fixes only their product | holding the cell; the one reason another parameter decides |

`ParameterRow.refinable` is false if any of the five holds.
`ParameterRow.held_because` reports the first that applies, in an order set by what you can do about it.
A row a rigid body places names the body first and says to refine the body's origin and rotation.
The structural reasons come next, then the mode, then a hold, then the wavelength.
A Le Bail phase's held atom therefore names the mode, which is the reason that would still hold if the hold went.

The counts of the five do not add up to the number of held rows.
On the LaB6 table above, the Le Bail listing marks 12 rows `mode_fixed`, while the refinable count falls only from 26 to 20, because 6 of the 12 were already locked or tied.
Read `refinable` for the decision, and the five flags only to explain it.

```python
import rietx as rx

lab6 = rx.Structure(phases=[rx.Phase(
    name="LaB6", space_group="P m -3 m", cell=rx.Cell.cubic(4.15689),
    atoms=[rx.Atom(label="La", species="La", x=rx.Parameter(value=0.0),
                   y=rx.Parameter(value=0.0), z=rx.Parameter(value=0.0)),
           rx.Atom(label="B", species="B", x=rx.Parameter(value=0.19964),
                   y=rx.Parameter(value=0.5), z=rx.Parameter(value=0.5))],
)])
ref = rx.Refinement(lab6, rx.Instrument.debye_scherrer(wavelength=0.4139),
                    history=False)

lebail = ref.parameters(mode="lebail")
assert sum(row.mode_fixed for row in lebail) == 12
assert sum(row.refinable for row in lebail) == 20
```

`Refinement.parameters` takes `mode` because the mode the object carries is the one its last stage ran in, which before the first run is the `rietveld` default.
A program that knows the mode of the next run passes it.
Without it, a Le Bail project's atom rows come back looking editable.
A Le Bail phase must carry a dummy atom to exist at all, and that atom's `biso` is not a parameter to offer anyone.

## Ties

`TieSpec` is the stored form of value = Σ c·source + k.

| Field | Holds |
|---|---|
| `TieSpec.terms` | the (path, coefficient) pairs |
| `TieSpec.const` | the additive constant k |
| `TieSpec.user` | `True` for a tie you declared, `False` for one the symmetry created |
| `TieSpec.sources` | the paths this value follows, which are the ones to edit instead |
| `TieSpec.describe` | the right-hand side as text, such as `1·phases.0.cell.a` |

A symmetry tie and a tie you declared hold a row the same way, and `held_because` reads the same for both.
`TieSpec.user` tells them apart.
A symmetry tie is derived again from the space group every time the table is built, and nothing removes it.
A tie you declared lives in the history, and `Refinement.untie` removes it.
Symmetry outranks a tie of your own, so a coordinate refuses one.
[How to tie parameters together](../guides/tie.md) gives the calls, what they refuse and how a dependent's bounds carry onto its source.

A cell tie is an identity, `1·phases.0.cell.a`.
A coordinate tie carries the starting position in its constant: on the LaB6 table above, `phases.0.atoms.1.x` describes itself as `0.19964 + 1·phases.0.atoms.1.dof.0`.
A coordinate's degree of freedom is a displacement from the stored coordinate {eq}`par-coord`.
Anisotropic displacement and Stephens degrees of freedom are absolute instead, which holds their site symmetry exactly.

Tying a coordinate's degree of freedom to another is how two atoms are made to move together.
The anchor is the coordinate as it stood when the tie was declared.
`phases.0.atoms.1.dof.0` then reads the displacement its tie implies, and `phases.0.atoms.1.x` reads the sum of the two.
That holds at every rebuild for as long as the tie is declared, so a second `Refinement.fit` reports the amplitude the first one did.

A dependent's bounds carry onto its source exactly where the tie has one source, which is every tie rietx derives and most that anyone writes.
With several sources the allowed region is a slanted boundary, and the solver can only be given a range.
It is given the smallest range containing every allowed point, which rules out no answer you asked for and can leave a corner where two sources together push the dependent outside its bounds.
If a fit lands in that corner, writing the values back to the models refuses, naming the parameter, its bounds and the tie that drove it.

## A child refined on its mode amplitudes

A superstructure of a known parent can refine as that parent plus a displacement field, one absolute amplitude per symmetry-adapted mode, rather than as free coordinates.
`rietx.crystallography.representation.distortion.displacive_statement` takes the parent `Phase`, the stated child `Phase` and the transform (P, p) with `r_parent` = P·`r_child` + p, and returns a `DisplaciveStatement`: the child, with its `Phase.distortion_modes` record set and its coordinates rewritten from it, plus the per-parent-site Biso ties (`DisplaciveStatement.biso_ties`, for `Refinement.tie`) and the seed it applied (`DisplaciveStatement.seed`).

The record is a `DistortionModes`.
`DistortionModes.parent_space_group` and `DistortionModes.transform` say what the modes were built from, `DistortionModes.reference_cell` the metric of the parent cell before any strain they were normalised in, and `DistortionModes.base` the parent-derived position of each atom.
Each entry of `DistortionModes.modes` is a `DistortionMode`: `DistortionMode.irrep`, `DistortionMode.k`, `DistortionMode.isotropy_group`, `DistortionMode.index` and `DistortionMode.site` say which mode it is, `DistortionMode.parent_invariant` whether it is the identity irrep's, `DistortionMode.vectors` its displacement of each atom per Å, and `DistortionMode.amplitude` the refined amplitude in Å.
Compare a published table on `isotropy_group`, never on `irrep`, which is rietx's own label.

Every atom a mode moves sits at its base plus the sum of amplitude times vector, and its x, y and z are derived rows of the parameter table: free the amplitudes, `phases.*.distortion_modes.modes.*.amplitude`, which the `mccusker_structural` plan does in its coordinates stage.
The amplitudes are absolute, so a second fit, a `set_values` of something else, or a replayed node leaves the coordinates where the amplitudes put them.
A coordinate edited by hand is refused when the table is built, as is a mode vector the atom's site symmetry forbids; to move the atoms, set the amplitudes.

A child stated at its parent's positions is seeded, because every amplitude outside the identity irrep has an exactly zero gradient there and a fit started there cannot move.
A block freed with all those amplitudes exactly zero is refused for the same reason.
The seed's first mode is positive, which picks one domain: the sign of a driving amplitude is a domain label, and only the relative signs inside a basis are measured.
The equations are in {ref}`the theory chapter <ch-parameterisation>`.

### What the fit reports about the blocks

The unit the result reports on is the irrep block: every mode sharing one `DistortionMode.irrep`, `DistortionMode.k` and `DistortionMode.isotropy_group`, over all parent sites, fixed by symmetry before the fit.
`rietx.report.distortion_blocks` lists a phase's blocks with their mode indices.
A fit of a phase carrying `Phase.distortion_modes` returns one `DistortionTotal` per block in `RefinementResult.distortion_totals`, which is `None` when no phase carries modes.

| field | what it is |
|---|---|
| `DistortionTotal.phase`, `DistortionTotal.irrep`, `DistortionTotal.k`, `DistortionTotal.isotropy_group` | which block |
| `DistortionTotal.modes`, `DistortionTotal.n_modes` | its indices in `DistortionModes.modes`, and their count m |
| `DistortionTotal.a_tau` | the block's amplitude, the norm of its mode amplitudes in Å, the same in any basis inside the block |
| `DistortionTotal.esd` | the esd of `a_tau` from the block's own covariance, the covariance every reported esd comes from |
| `DistortionTotal.esd_label` | "linearised; undefined at A_τ = 0 and Rice-biased below about 2 esd", on every block |
| `DistortionTotal.t2` | Hotelling's T² = Aᵀ·Cov⁻¹·A over the block's amplitudes, with m beside it and no p |
| `DistortionTotal.driving` | whether a displacement inside this block alone has the child's own group; `None` where the record's parent operations do not map its reference structure onto itself |
| `DistortionTotal.sign_convention` | which sign the amplitudes carry: the fitted domain, as the fit left it |
| `DistortionTotal.largest_displacement` | the largest atomic displacement the block puts on the child, Å |

`esd` and `t2` are `None` where the fit measured no covariance for the block: an amplitude not freed, a column the data cannot see, or, for `esd`, `a_tau` exactly 0.
T² carries no p because χ² is even in an amplitude that breaks the parent's symmetry: where a block's truth may be zero, T² is about four times the likelihood ratio, so a p against χ²<sub>m</sub> is wrong exactly where the question is asked.
A correlation inside one block is an artefact of the basis chosen inside it; `a_tau`, its esd, `t2` and the block comparison below are the same in any basis.

### Comparing blocks by a refit

`Refinement.distortion_block_tests(data, hold=..., detectability_bar=..., detectability_probe=...)` holds blocks at 0 and refits, after a fit that freed them.
`hold` is a list whose items are a block or a set of blocks held together, each named by its `(irrep, k, isotropy_group)` key or by its `DistortionTotal`; `None` holds every block that is not the identity irrep's and that the fit freed throughout, each alone; a block the fit freed only in part is skipped, and a named one raises.
Each item gets one restricted refit: its amplitudes at 0, everything else the fit freed free again, starting from the fit's optimum.
It runs on a private copy, so the refinement, its history and its result are unchanged, and it costs one refit per item (0.5 to 1.4 s each on the five blocks of the BT-1 LaMnO₃ `Pnma` fit, macOS arm64).

It returns a `DistortionBlockTests`, with one `DistortionBlockTest` per item in `DistortionBlockTests.tests`:

| field | what it is |
|---|---|
| `DistortionBlockTest.phase`, `DistortionBlockTest.held` | the held blocks |
| `DistortionBlockTest.m` | the number of free amplitudes held |
| `DistortionBlockTest.delta_bic` | ΔBIC at N/f², f the restricted fit's, as `compare_freed` charges it; positive favours the blocks |
| `DistortionBlockTest.lambda_`, `DistortionBlockTest.lambda_p` | Λ = Δχ²/(χ²<sub>red</sub>·f²) with the full fit's χ²<sub>red</sub> and f, and its upper-tail p against χ²<sub>m</sub> |
| `DistortionBlockTest.chi2_restricted`, `DistortionBlockTest.chi2_full` | the χ² of each fit, not reduced |
| `DistortionBlockTest.esd_inflation_restricted`, `DistortionBlockTest.esd_inflation_full`, `DistortionBlockTest.chi2_red_full`, `DistortionBlockTest.n_points` | the numbers the two statistics were computed from |
| `DistortionBlockTest.a_det` | the predicted smallest amplitude of the held set whose ΔBIC reaches the bar, Å, when a bar was passed |
| `DistortionBlockTest.wall_s` | the restricted refit's wall time |

`rietx.report.block_comparison` computes `delta_bic`, `lambda_` and `lambda_p` from stated numbers.
Λ is Hamilton's F form on rietx's esd scale: it holds its size on white-noise nulls, but under model misfit it can call a block that absorbs the misfit, so it is not a test of zero.
No row carries a verdict.

A restricted refit that lands below the full fit by more than the solver's own stopping tolerance (a relative `rietx.optimize.lm.FTOL`) proves the full fit stopped short of its optimum; one within it is round-off, as a held true zero gives, and starts nothing.
The call then refits the full model from that restricted optimum, with the held blocks re-seeded as `displacive_statement` seeds them, and tests every item again.
`DistortionBlockTests.restarts` records each restart as a `DistortionRestart`: `DistortionRestart.held` names the set that triggered it, `DistortionRestart.chi2_full_before`, `DistortionRestart.chi2_restricted` and `DistortionRestart.chi2_full_after` the three χ², and `DistortionRestart.lowered` whether the refit lowered the full χ².
The full χ² falls by more than that tolerance at every restart, so the loop ends without a cap; a restart that does not lower it is recorded and ends the loop.
After a restart the rows compare against the restarted fit, which is `DistortionBlockTests.restarted_result`; otherwise that field is `None`.

`detectability_bar` and `detectability_probe` have no default: without a bar `a_det` is not computed, and a bar without a probe raises (`DistortionBlockTests.detectability_bar` and `DistortionBlockTests.detectability_probe` record the ones used).
The smallest detectable amplitude is the minimum over the held modes j of A<sub>0</sub>·[χ²<sub>red</sub>·f²·(m·ln(N/f²) + bar)/λ<sub>j</sub>(A<sub>0</sub>)]<sup>1/p<sub>j</sub></sup>, with χ²<sub>red</sub> the full fit's and f the restricted fit's.
λ<sub>j</sub> is one predict per mode at the caller's probe amplitude A<sub>0</sub> (`detectability_probe`, Å) from the restricted optimum, on the file's σ.
The scaling λ ∝ A<sup>p</sup> holds to leading order only, so no probe is built in: at 0.1 Å on two blocks of LaMnO₃ at one noise seed the test holds `a_det` within 2.1 % (p = 4) and 3.7 % (p = 2) of the bisected crossing, and that is all that has been shown.
p<sub>j</sub> is 4 for a mode the pattern has no first-order term along at that structure, which `AmplitudeAction.even` reads from the structure's symmetry, and 2 otherwise.
`rietx.report.detectability_target` and `rietx.report.detectability_amplitude` are the two steps.
Measured against the strength at which half of the planted seeds gave ΔBIC above a bar of 6, on LaMnO₃ synthetic white noise, `a_det` was off by +2 % on a five-mode Γ block, +9 to +12 % on a ten-mode zone-boundary block, and +48 % on a one-mode block of a 57-mode P1 child, whose signal the other free modes absorb; it is uncalibrated on misfit.

`rietx.crystallography.representation.distortion.amplitude_action` returns the `AmplitudeAction` of a phase on mode amplitudes: the parent group acting on its mode fields over the child cell.
`AmplitudeAction.stabiliser` gives the operations that leave a set of amplitudes unchanged, the structure's own symmetry, and `AmplitudeAction.even` the modes along which the pattern has no first-order term there.

## Restraints

A restraint adds a row to the residual and leaves the table as it is.
It is an observation with an uncertainty, a distance, an angle or a value known from chemistry, and the parameters it touches stay free.
Restraints are declared on `Phase.restraints`, and [How to restrain a bond length or an angle](../guides/restrain.md) gives the procedure.

| Field | `BondRestraint` | `AngleRestraint` | `ValueRestraint` |
|---|---|---|---|
| the quantity | `BondRestraint.atom_i`, `BondRestraint.atom_j` | `AngleRestraint.atom_i`, `AngleRestraint.atom_j` (the vertex), `AngleRestraint.atom_k` | `ValueRestraint.path`, any name in the model |
| the target | `BondRestraint.target`, in Å | `AngleRestraint.target_deg`, in degrees | `ValueRestraint.target`, in the parameter's own unit |
| the uncertainty you claim | `BondRestraint.sigma`, in Å | `AngleRestraint.sigma`, in degrees | `ValueRestraint.sigma` |
| a multiplier on the row | `BondRestraint.weight`, 1 by default | `AngleRestraint.weight`, 1 by default | `ValueRestraint.weight`, 1 by default |
| the symmetry image | `BondRestraint.op_index`, `BondRestraint.translation` | `AngleRestraint.op_index_i`, `AngleRestraint.translation_i`, `AngleRestraint.op_index_k`, `AngleRestraint.translation_k` | none |

An atom field is a position in `Phase.atoms`, counted from 0, as in the names.
Each restraint adds one row, √weight·(computed − target)/σ, after the data rows {eq}`par-restraint`.
`sigma` sets how hard the restraint pulls, and `weight` multiplies the row on top of it.
`Stage.restraint_weight_scale` multiplies every row for one stage {eq}`par-restraint-weight`.

The rows enter the covariance, so they tighten the esds of the parameters they touch.
They are left out of Rwp, the Durbin-Watson statistic and the Bérar-Lelann inflation, because they are not measurements of the pattern.
`RefinementResult.restraints` reports each one's computed value and deviation ([Restraint report](result.md#restraint-report)).

A distance obeys periodic boundary conditions, so the second atom is taken at a symmetry image.
Leave the image unnamed and the nearest one is found once, at the coordinates a stage starts from, and kept for that stage.
Name it whenever an atom may move far enough to change which image is nearest.

Two one-sided kinds, a tether and an anti-bump, hold a distance within a range.
They belong to the rigid-body technique, which is provisional by declaration ({ref}`provisional-by-declaration`), and are documented with it.

## Bounds

`ParameterRow.value`, `ParameterRow.lo` and `ParameterRow.hi` are what the solver sees.
Every parameter refines in its own unit, and the bounds go to the solver as a box.
The default solver solves each step inside that box, so a parameter the data push against a bound lands exactly on it ([Solvers](../theory/estimation.md#solvers)).
A width or a scale can therefore end on its off state at 0.
A field whose physics divides by the value carries a floor above 0 instead ([Parameter](data.md#parameter)).

A `Parameter` you pass to a field inherits the `min`, `max` and `unit` you left unset from the field's own default, and a bound you state yourself wins ([Parameter](data.md#parameter)).
A value outside the inherited range is refused when the model is built, naming the field and the range.
State the range you mean on the `Parameter`, or, for a coarse instrument's widths, build them with `ProfileTCHZ.coarse`.

A file written before schema 0.46 stored a `transform` word instead of bounds, and it is read as the box it enforced.

| Stored `transform` | Bounds it becomes |
|---|---|
| `identity` | unchanged |
| `softplus` or `exp` | `min` raised to 0 |
| `logit` | `min` raised to 0 and `max` lowered to 1 |

So `Parameter(value=0.5, min=-1.0, transform="softplus")` builds with `min=0.0`, and a project saved by an earlier release opens with the bounds its fits ran in.

### Bounds a stage adds

A stage adds three default bounds of its own, each only on a side you left at ±inf.
A bound you set wins, so setting any finite bound on that side turns the default off.
None of them is written to the stored parameter, so `ParameterRow.hi` can read `inf` on a row that stopped on one.

A phase whose summed contribution sits below {{ PHASE_SUPPORT_SIGMA }}σ of the counting noise when the stage begins contributes nothing the fit can see.
Every structural parameter of a phase reaches the pattern only through scale × \|F\|² × profile, so its cell could then move without changing Rwp at all, out of the physical range.
The stage bounds that phase's cell: each length to ±5 % of the value the stage starts from, plus 0.05 Å, with a floor of 1.5 Å, and each angle to ±2°.
The bounds follow TOPAS's default cell limits, re-centred at each stage rather than at each iteration.
Only that phase's cell is bounded.
Under the default solver, a bound the step never reaches leaves each step unchanged.
Under `solver="trf"` a bound changes how a parameter moves even when it is never reached, because TRF scales its step by the distance to the bounds, so the window is kept off every phase the data can see.
Such a cell can report [`BOUND_HIT`](diagnostics-refinement.md#bound_hit) while its `ParameterRow.hi` still reads `inf`.

In a staged plan the window is rarely reached, because the stage holds that phase's structural parameters instead (`StageResult.held`, [Held parameters](refinement.md#held-parameters)).
[`PHASE_UNCONSTRAINED`](diagnostics-refinement.md#phase_unconstrained) names a phase the data cannot tell from absent and says what the run did with its parameters.

A free cell that moves more than ±15 % in length or ±6° in angle within one stage has run away.
The stage puts that phase's free cell parameters back at the values the stage started from, holds them, and solves the stage again.
Before 1.10 the check clamped the value to the 15 % edge, which left a number that was no measurement.
`StageResult.cell_reset` lists the parameters put back, and [`CELL_RUNAWAY`](diagnostics-refinement.md#cell_runaway) reports it.
That check reads the answer and is never a bound the solver sees.
A runaway in the final stage leaves the cell at its start values and withholds its esd, and the esd of every parameter tied to it.

The sample strain and size widths get the other two default bounds, armed only on a term that has already reached them.
A strain width is held to the width the fitted 2θ range can express, and a size width to the same width read through 1/cos θ ({ref}`the strain bound <sec-strain-cap>`, {ref}`the size bound <sec-size-cap>`).
No default bound limits the crystallite size itself.
`SIZE_UNUSUALLY_SMALL` speaks below its threshold and bounds nothing.

## Editing the table

`Refinement.set_vary` and `Refinement.set_values` edit the table, and each records a history node, because freeing a parameter and setting one are refinement moves.
The tree is created on the first `Refinement.fit` or `Refinement.run_stage`, since it is pinned to its pattern by a fingerprint.
Both calls change the working state before then, but a call before the first fit is not in the log ([The refinement history](history.md)).

`Refinement.set_vary` takes a name or a list of names, with wildcards, and returns the paths it changed.
Read the return rather than the list you offered it.
A locked or tied row never matches, however broad the name, so the hits are the account of what the call did.

```python
import rietx as rx

lab6 = rx.Structure(phases=[rx.Phase(
    name="LaB6", space_group="P m -3 m", cell=rx.Cell.cubic(4.15689),
    atoms=[rx.Atom(label="La", species="La", x=rx.Parameter(value=0.0),
                   y=rx.Parameter(value=0.0), z=rx.Parameter(value=0.0)),
           rx.Atom(label="B", species="B", x=rx.Parameter(value=0.19964),
                   y=rx.Parameter(value=0.5), z=rx.Parameter(value=0.5))],
)])
ref = rx.Refinement(lab6, rx.Instrument.debye_scherrer(wavelength=0.4139),
                    history=False)

assert ref.set_vary("phases.*.cell.*") == ["phases.0.cell.a"]   # five of six are held
assert ref.set_vary("phases.*.cell.alpha") == []                # locked by symmetry
assert ref.set_vary("phases.*.atoms.*.x") == []                 # tied to a site-symmetry direction
assert ref.set_vary("instrument.profile.u", vary=False) == ["instrument.profile.u"]
```

A cubic cell returns one path from a name that matches six, and that one hit is the whole of the cell's freedom.
A held row is skipped by a wildcard name, as a locked one is.
A literal path to a row you held raises `ValueError`, saying to `Refinement.unhold` it first.
A row the current mode fixes is the exception to the matching rule: `set_vary` frees it, and the next stage drops it again and reports it as `mode_fixed`.

The `vary` flags on the models you passed in are the starting declaration only.
Once `set_vary`, a hold, a tie or a stage has declared a free set, the table reads that set, even when it is empty.
A plan replaces the flags at every stage, so `vary=False` alone does not keep a parameter fixed, and `Refinement.hold` does ([How to keep a parameter fixed whatever the plan frees](../guides/hold.md)).

`Refinement.set_values` takes a dict of paths to values.
It is plural because a table is edited several cells at a time, and one node per value would bury the log.
It raises `ValueError` on four refusals, each with its own remedy.

| Refusal | Message | Remedy |
|---|---|---|
| unknown path | `unknown parameter path(s): [...]` | correct the name |
| locked | `... is structurally fixed (symmetry, or a representation that owns this channel) and cannot be set` | none; the structure owns the value |
| tied | `... follows 'phases.0.cell.a' as an affine tie; set that instead` | set the source |
| out of bounds | `... lies outside its bounds [0.0, inf]` | a value inside them, since the bounded solver cannot start outside |

A tied parameter follows its sources.
Setting `phases.0.cell.a` on a cubic phase moves `b` and `c` with it, and the change reaches the objects.
`Refinement.structure` and `Refinement.instrument` are the refinement's own deep copies of what you passed in, and they are what the table writes back to.
`Refinement.fitted_structure` and `Refinement.fitted_instrument` return the same two objects, under names that say when you are reading them.
Setting a value also clears the fitted curve and its statistics, which described the previous values.

## Refined rows

A result carries its own view of the table.
`RefinementResult.parameters` is a list of `RefinedParameter`, and a row appears if its parameter varied or was tied.
A fixed parameter is absent rather than present with `vary=False`.
`RefinementResult.parameter` returns the row for one path.

| Field | Holds |
|---|---|
| `RefinedParameter.path` | the name |
| `RefinedParameter.value` | the value the fit ended at |
| `RefinedParameter.stderr` | the esd, or `None` where it could not be estimated |
| `RefinedParameter.stderr_uncorrected` | the same esd without the Bérar-Lelann factor, as GSAS-II and TOPAS print it ([Estimation](../theory/estimation.md)); `None` where `stderr` is `None`, and on a result from before 1.10 |
| `RefinedParameter.vary` | `False` on the tied rows, which is how to spot them |
| `RefinedParameter.at_bound` | `True`, `False`, or `None` where the row was not tested |
| `RefinedParameter.equations` | the parametric declarations that set the row ([Parametric refinement](parametric.md)), empty where none did, and `None` on a row from before 1.10 |
| `RefinedParameter.interval` | the profile interval ([Profile interval](#profile-interval)) of a moment angle the fit left out of its covariance at a direction the symmetry fixes ([Magnetic refinement](magnetic.md#an-angle-at-a-symmetry-direction)), and `None` on every other row |

A parameter the data said nothing about reports no esd rather than a small one.
A free parameter can end in a direction the residual does not move at all, such as the centre of a declared peak whose area refined to zero, and there is no variance to report for it.
Its `stderr` is `None`, and so is the esd of every tied row that draws on it.
Read a `None` esd on a row you meant to refine as a sign to take that parameter out of the plan.
A scale or a peak area that refined to zero is not such a direction: its column is still the pattern it would add, so it keeps its esd, and `at_bound` says whether the floor held it.

### On a bound

A value resting on a bound the data push against is not a measurement, so do not quote it with its esd.

| `at_bound` | Means |
|---|---|
| `True` | the fit stopped against a bound with the data still pushing outward; the same rows [`BOUND_HIT`](diagnostics-refinement.md#bound_hit) and [`FLOOR_HIT`](diagnostics-refinement.md#floor_hit) name |
| `False` | tested, and the bound carried no load |
| `None` | not tested, so no answer either way |

`None` covers two cases.
A tied row is never tested, because it is not in the free vector the fit solves, and it can sit on its own declared bound while every source is interior.
A result built without a fit behind it has nothing to report, so every row of a [`replay`](history.md) is `None`.
A free scale or width on its floor of 0 is tested like any other bound, and an absent phase's scale reads `True` when the data push it onto that floor.
It keeps its value and its esd, and so does every other row: no esd is computed as if the floored row were fixed.
A floor reports as `FLOOR_HIT` (a lower bound of 0, or W's floor) and any other bound as `BOUND_HIT`, because only the second can be widened.

What counts as on a bound depends on the solver.
Under the default `solver="lm"` a row is on its bound when it is in the solver's exact active set: it sits on the limit and the gradient there points out of the allowed range.
Under `solver="trf"` a value only comes close, so a row is on its bound when it sits within a hundredth of its own esd of the limit and the residual still pushes it outward.
The default solver takes that second test too when a stage frees more than 128 columns.
Neither test reads the distance alone, so a wide `min=1e-14, max=1e14` written to mean "leave this alone" does not make a value read as pinned.

The flag and the two diagnostics come from one bound test, so they cannot disagree.
Read the diagnostic for the list, and the flag when you are already iterating rows.

### The table against the result

The two views differ in size.
A Le Bail fit of the 11-BM NAC pattern over 2-24° gives 73 rows from `Refinement.parameters` and 31 from `RefinementResult.parameters`: 13 free, 18 tied and 42 fixed rows that the result leaves out.
All 13 free rows come back `False`, and all 18 tied rows `None`: `cell.b`, `cell.c` and 16 symmetry-tied coordinates.
Capping `cell.a` at 10.2500 Å against a free optimum of 10.2512 Å turns that one row `True` and takes Rwp from 0.1435 to 0.2163.
The other parameters cover for a cell the fit is not allowed to reach.

`Refinement.parameters` merges the most recent fit's esds onto `ParameterRow.esd`.
In that fit `phases.0.cell.b` and `phases.0.cell.c` both carry 5.42×10⁻⁵ Å, `a`'s esd.
The tied coordinate rows carry none, because the fit freed no coordinate degree of freedom.
Use the result to report a fit, and the table to decide what to do next.

## Profile interval

An esd read as value ± esd is symmetric.
On a bound that interval reaches into values the bound forbids, and the estimate there has no symmetric sampling distribution to give it meaning.
`Refinement.profile_interval` gives such a row a range to quote, as a `ParameterInterval` ([How to quote a parameter that ended on its bound](../guides/interval.md)).
It pins the parameter at a value, refits everything the last fit freed, reads the data's χ² there, and finds where that χ² has risen by a threshold on each open side.

<!-- api-doc: no-exec — needs a fitted refinement; tests/test_parameter_interval.py runs this call -->
```python
interval = ref.profile_interval(data, "instrument.profile.y")
print(interval.lower, interval.upper, interval.one_sided)
```

A row whose `RefinedParameter.at_bound` is `True` gets a one-sided interval.
The bound is one end, and the other is where χ² has risen by 2.71 × χ²<sub>red</sub> × f², with f the fit's `Statistics.esd_inflation`.
Any other row gets a two-sided interval, at 3.84 × χ²<sub>red</sub> × f² on each side.
Both are 95 % points, and `level` moves them.
The two factors put the threshold on the scale of the esds, so on a quadratic profile a two-sided interval is the value ± 1.96 esd.

Each side steps out by 1, 2, 4, … esd until χ² passes the threshold, then solves for the end to a thousandth of an esd.
A side that reaches the parameter's own limit first reports the limit as its end.
Each pinned value is refitted until its χ² stops falling, up to four times, because a stage keeps the peak windows it sized when it started.
`max_refits` caps each side at {{ PARAMETER_INTERVAL_MAX_REFITS }} refits by default.
Every refit runs on a branch, so the working state, `Refinement.result_` and the history's head are left as they were.
A fit must have run, and the path must have been free in it; a tied, locked or fixed path is refused with the reason.

| Field | Holds |
|---|---|
| `ParameterInterval.path` | the parameter profiled |
| `ParameterInterval.value` | the fit's value, copied from its result row |
| `ParameterInterval.stderr` | the fit's esd for it |
| `ParameterInterval.at_bound` | the row's `at_bound`, copied |
| `ParameterInterval.level` | the confidence level |
| `ParameterInterval.one_sided` | whether the bound is one end |
| `ParameterInterval.quantile` | the χ²₁ point the threshold is built from, 3.84 or 2.71 at 95 % |
| `ParameterInterval.delta_chi2_cut` | the threshold in χ², the quantile × χ²<sub>red</sub> × f² |
| `ParameterInterval.lower`, `ParameterInterval.upper` | the two ends, or `None` where a side found none |
| `ParameterInterval.lower_stop`, `ParameterInterval.upper_stop` | why each side stopped |
| `ParameterInterval.chi2_fit` | the fit's own data χ², not reduced |
| `ParameterInterval.chi2_lowest` | the lowest data χ² found, the fit's included |
| `ParameterInterval.fit_is_minimum` | whether every refit stayed at or above the fit's χ² |
| `ParameterInterval.points` | one `ParameterIntervalPoint` per pinned value, in the order they ran |
| `ParameterInterval.n_refits` | the refits those points took |

| Field | Holds |
|---|---|
| `ParameterIntervalPoint.value` | the pinned value |
| `ParameterIntervalPoint.runs` | how many refits it took to settle |
| `ParameterIntervalPoint.chi2` | the lowest data χ² those refits reached |
| `ParameterIntervalPoint.delta_chi2` | its distance above `ParameterInterval.chi2_fit`, negative below it |
| `ParameterIntervalPoint.status` | how the refit's stage ended |
| `ParameterIntervalPoint.error` | why a refit raised |
| `ParameterIntervalPoint.node_id` | the history node the refit recorded, and `None` where it recorded none: history disabled, or an interval the fit computed itself |

| Stop | Means |
|---|---|
| `"threshold"` | χ² rose by the threshold, and the end is that point |
| `"bound"` | the side reached the parameter's own limit first, and the end is the limit; a one-sided interval's bounded end reads this |
| `"refits"` | the side ran out of refits, and has no end |
| `"error"` | a refit raised, and the side has no end |

`ParameterInterval.fit_is_minimum` is `False` when a refit found χ² below the fit's by more than 1 % of the threshold.
The fit then did not reach the minimum along this parameter, and the ends, measured from the fit, are too wide.
Refit before quoting them.
