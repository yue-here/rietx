# How a refinement works

A Rietveld refinement is one non-linear least-squares problem. The package
computes a pattern from the model, compares it with the measurement point by
point, and moves the free parameters to reduce the weighted sum of squares.

Almost everything that goes wrong is a correlation. Two parameters change the
calculated pattern in nearly the same way, so the data cannot tell them apart,
and the solver splits the difference between them however the starting point
happened to lean. This chapter is about which parameters those are and what the
package does about it: how they are grouped, why the groups fight, and the three
things you can do. You can order the refinement, tie two parameters together, or
restrain a quantity you know. [](results.md) is the numbers that come back.

## The parameter groups

Every refinable quantity has a dot-path, and the paths group by what the
parameter does to the pattern. [](data.md) is the objects the paths address,
field by field, and [](model.md) is the path grammar and the table itself. This
section is what each group does and why the groups fight.

| Group | Paths | Changes | Angular signature |
|---|---|---|---|
| scale | `phases.*.scale` | total intensity of each phase | flat in Q |
| background | `instrument.background.*` | the pedestal under the peaks | smooth in 2θ |
| position corrections | `instrument.zero_shift`, `instrument.geometry.sample_displacement`, `instrument.geometry.capillary_offset_along_beam`, `instrument.geometry.capillary_offset_across_beam` | where every peak sits | constant, cos θ, sin 2θ, cos 2θ |
| cell | `phases.*.cell.*` | where each peak sits, through its d-spacing | tan θ |
| instrument profile | `instrument.profile.u`, `.v`, `.w`, `.x`, `.y` | peak widths and shape | Gaussian: `w` constant, `v` tan θ, `u` tan²θ. Lorentzian: `x` 1/cos θ, `y` tan θ |
| sample broadening | `phases.*.gauss_size`, `phases.*.lor_size`, `phases.*.gauss_strain`, `phases.*.lor_strain` | the specimen's own width contribution | size 1/cos θ, strain tan θ |
| anisotropic strain | `phases.*.microstrain.dof.*` | width, per hkl rather than per θ | tan θ, scaled by direction |
| coordinates | `phases.*.atoms.*.dof.*` | relative peak intensities | none; it is an hkl effect |
| displacement | `phases.*.atoms.*.biso`, `phases.*.atoms.*.adp.*` | intensity falling off with Q | exp(−2B sin²θ/λ²) |
| occupancy | `phases.*.atoms.*.occ` | relative peak intensities | none |
| intensity corrections | `phases.*.preferred_orientation.r`, `phases.*.extinction`, `instrument.geometry.surface_roughness.*` | intensity, as a smooth or hkl-selective rescaling | various, all smooth in Q |

Coordinates and occupancies refine differently from the rest, and it matters
when you read a plan. A coordinate is free along the directions its site
symmetry allows rather than in x, y and z. `ParameterTable` wires one
`phases.*.atoms.*.dof.*` entry per allowed direction and ties x, y and z to
them. A fully fixed special position contributes no entries at all, so the glob
is always safe to use, and setting `vary=True` on such a coordinate raises
(`ref.fix_special_positions()` clears the flag on every such coordinate, and says which).

Anisotropic displacement parameters work the same way, through
`phases.*.atoms.*.adp.*`, and so do the fifteen Stephens strain coefficients
through `phases.*.microstrain.dof.*`. In each case the symmetry-allowed subspace
is derived from the space-group operators, and a value outside it raises rather
than being quietly symmetrised.

## Why the groups correlate

Two parameters are hard to separate when their effects on the pattern have the
same shape in 2θ. Over the whole range of a good dataset the shapes differ. Over
a short range they do not, and that is where the trouble is.

```{image} figures/angular-signatures-light.png
:class: only-light
:alt: Four angular signatures over 110 degrees, where they separate, and over 20 degrees, where they nearly coincide
```

```{image} figures/angular-signatures-dark.png
:class: only-dark
:alt: Four angular signatures over 110 degrees, where they separate, and over 20 degrees, where they nearly coincide
```

Each curve is normalised to 1 at the middle of its range, because separability
is a question about shape and not about scale. Two effects that differ only by a
constant factor are one parameter, whatever their sizes. On the left, over
110° of data, the four are plainly different functions. On the right, over 20°,
every one of them is a straight line to within 0.8 %, so the four shapes have
little more than a constant and a slope between them. A refinement over that
range reports four numbers and measures rather fewer.

| Correlated group | Signatures | What goes wrong |
|---|---|---|
| zero shift · sample displacement · cell | constant · cos θ · tan θ | over a narrow 2θ range these three are collinear. A cell refined against a free zero shift on 20° of data is not measured. |
| zero shift · the two capillary offsets (Debye-Scherrer only) | constant · sin 2θ · cos 2θ | the same problem in the transmission geometry's own shapes. Over 5-160° the three are separable; over 5-25° they are not, by a factor of about 4600 in the conditioning. |
| crystallite size · microstrain | 1/cos θ · tan θ | the Williamson-Hall separation. Over a short range they are one parameter rather than two. |
| scale · displacement · background · absorption · surface roughness · extinction | all smooth in Q | the big one. Every member lifts or depresses intensity smoothly with angle, so any of them can absorb any other. |
| preferred orientation · occupancy | both rescale specific hkl | an occupancy refined against uncorrected texture is a texture measurement. |
| overlapped intensities (Le Bail, Pawley) | identical | the data determine the sum and not the split. |

Two of those groups are worse than correlated. Capillary absorption is exactly a
reparameterisation of the scale and the displacement parameters, the fit being
identical with and without it, so `Geometry.mu_r` is computed from the specimen
and never refined. Flat-plate absorption is 60 to 99 % absorbable, so
`Geometry.mu_t` is also computed rather than refined. The part that is not
absorbable does move Rwp, and a wrong thickness lands partly in the fit and
partly in the displacement parameters.

Which position correction exists depends on the geometry. `cos θ` is the
flat-plate specimen-displacement shape, so `Geometry.sample_displacement` and
`Geometry.sample_transparency` are held fixed on anything that is not
`bragg_brentano`. A capillary off the centre of the 2θ circle has its own pair,
McCusker eq (4): `Geometry.capillary_offset_along_beam` carries the sin 2θ half
and `Geometry.capillary_offset_across_beam` the cos 2θ half, they exist only on
`debye_scherrer`, and both need `Geometry.goniometer_radius_mm`, which eq (4)
divides by. Both default to 0 and fixed. At a synchrotron with a crystal
analyser the paper says the displacement error is eliminated, so freeing them
there measures nothing; a laboratory capillary or Guinier camera is where they
belong.

The report knows this. Its position templates and the actions they map to are
chosen by geometry, so a capillary fit is never told to refine a flat-plate
aberration it cannot free.

Two rules follow, and they are the reason plans exist:

1. Do not free the second member of a group until the first is pinned by
   something outside the fit. This is what the `lab_calibrate` workflow is for:
   refining a certified standard with its cell held fixed decorrelates zero
   shift from displacement from cell, because the cell is supplied rather than
   fitted.
2. A correlation above 0.98 means you refined one parameter and reported two.
   The package raises `HIGH_CORRELATION` when that happens. The answer is almost
   never to widen the bounds. Fix one of the pair, extend the data range until
   the signatures separate, or constrain them to each other where chemistry says
   the two quantities are the same quantity.

(constraining-parameters)=
## Constraining parameters to each other

A constraint makes two parameters one. The dependent leaves the free vector and
follows its source exactly, so the parameter count drops by one and the
observation-to-parameter ratio rises. A restraint is the other thing: it adds an
observation, a bond length say, with a weight, and leaves the parameter count
alone.

Use one where the data cannot separate two quantities and chemistry says they
need not be separated. Two of the cases the guidelines {cite}`mccusker1999`
recommend are available here: equal displacement parameters across atoms in the
same environment, and occupancies that must sum to a known total. The third,
rigid bodies, arrived in 1.7.0 as a provisional first piece
(`RigidBody`; [](compatibility.md)).

<!-- api-doc: no-exec — it needs the reader's own structure and instrument -->
```python
ref = rx.Refinement(structure, instrument)

# the three oxygens of one phosphate group refine as one B
ref.tie_equal(["phases.0.atoms.4.biso",
               "phases.0.atoms.5.biso",
               "phases.0.atoms.6.biso"])

# a mixed site: occupancies that sum to 1
ref.tie("phases.0.atoms.1.occ", "phases.0.atoms.0.occ", scale=-1.0, offset=1.0)

ref.untie("phases.0.atoms.*.biso")     # release them again
```

`Refinement.tie_equal` takes the same fnmatch globs as `set_vary`, and the
first match in table order carries the freedom while the rest follow it; pass
`source` to choose a different one. `Refinement.tie` is the general affine
form, `value = scale·source + offset`, of which `tie_equal` is the
`scale=1, offset=0` case, and `Refinement.untie` releases them. Each verb
records a history node, so a constrained refinement replays as one, and a
project reopens with the constraint still in force.

A tie shows up in the parameter listing as a held row: `refinable` is false,
`held_because` names the sources, and `TieSpec.user` is true for the ones you
declared. The ties the space group creates (`b` following `a` in a tetragonal
cell, a coordinate following its site-symmetry direction) read the same way with
that flag false, and they cannot be released: symmetry outranks a user tie
everywhere the two meet. [](model.md) reads a held row field by field.

The verbs refuse rather than approximate. A locked parameter, an already-tied
one, a source that is itself tied and is a model parameter (which would make a
chain), a target the current intensity mode force-fixes, and an implied value
outside the target's own bounds are all refused with the reason and the
parameter holding it. The exception in that list is the subject of the next
section: a named variable may follow other named variables.

A tie carries the dependent's bounds back onto its source, and you do not have
to do that arithmetic. The dependent leaves the free vector, so the optimiser
never sees its `min`/`max` directly. What it is given instead is the range on the
source that keeps the dependent inside them. The mixed-site example above is the
clearest case. `occ` is declared `[0, 1.5]`, and `occ₁ = 1 − occ₀` means `occ₀`
must stay in `[0, 1]` for `occ₁` to be non-negative, so `[0, 1]` is the box that
stage runs against, without anyone writing it. Every dependent a source drives
contributes, and the tightest wins, along with whatever the source declares
itself. A fit that stops at such a limit reports it like any other bound
(`BOUND_HIT`, naming the source), and the parameter to widen is then the
dependent rather than the one the diagnostic names. Ties with several sources
are the one case this cannot close exactly, and {ref}`named-variables` has that
detail, since they are where several sources arise.

:::{admonition} Worked example: tying three displacement parameters
:class: tip

Fluorapatite on a laboratory diffractometer, refined twice under one protocol,
the second time with the three phosphate oxygens' `biso` tied together:

| | free | tied |
|---|---|---|
| free parameters | 20 | 18 |
| points per parameter | 287.5 | 319.4 |
| Rwp | 0.092498 | 0.092546 |
| B(O5) / Å² | 0.3647(1513) | 0.5150(754) |
| B(O6) / Å² | 0.6016(1590) | 0.5150(754) |
| B(O7) / Å² | 0.5377(1078) | 0.5150(754) |

The return is precision. The constrained esd is smaller than the best of the
three free ones. Rwp is not the evidence and cannot be. It moved by 0.05 % of
itself, the shape "the constraint costs no fit quality" takes.

Points per parameter counts the 5 750 measured channels. The independent
observations are the reflections, far fewer (McCusker et al. 1999, §9).

The check to run first is in the free column. Compare each pair of free values
with their combined esd, the square root of the sum of the two squared esds. The
three pairs differ by 1.08, 0.93 and 0.33 of it, all under about two, so the free
refinement does not contradict the claim that these are one parameter. Where a
pair differs by more, the atoms are telling you they are not in the same
environment, and tying them replaces a measurement with an assumption.
:::

(named-variables)=
## Naming a variable of your own

Every constraint above names a model parameter as its master: one of the three
oxygens carries the freedom and the other two follow it. That reads oddly when
the quantity is not any one of them. Three oxygens do not have atom 4's
displacement parameter; they have one displacement parameter that all three
share. A named variable is that quantity, declared in its own right.

<!-- api-doc: no-exec — it needs the reader's own structure and instrument -->
```python
ref = rx.Refinement(structure, instrument)

ref.add_variable("B_phosphate", 0.5, min=0.0, max=25.0)     # -> "vars.B_phosphate"
for j in (4, 5, 6):
    ref.tie(f"phases.0.atoms.{j}.biso", "vars.B_phosphate")

ref.set_vary("vars.*", True)          # it refines like anything else
```

The path is `"vars."` plus the name, and it is an ordinary dot-path from there:
`Refinement.parameters` lists it, `set_vary` globs it, `set_values` moves it,
a fit refines it and reports an esd for it. `Refinement.remove_variable` deletes
one, and refuses while anything still follows it, naming the dependents.

`min` and `max` are the part worth thinking about, because a variable is a
`Parameter` and those are the fields the fit reads. Declared with the same
bounds as the model parameter it replaces, it produces the identical column and
the identical answer. Declared with different ones it is a different problem.

A dependent's own bounds reach the solver too, and you do not have to do the
arithmetic. A tie says `dependent = coefficient · source + offset`, so a
dependent bounded at 25 and followed at coefficient 2 puts its source's ceiling
at 12.5. That is what the stage is given, intersected over every dependent the
source drives and with whatever the source declares itself. The tighter of the
two wins, so declaring `max=12.5` by hand changes nothing and declaring `max=25`
costs nothing. A source stopped at a limit it never wrote is reported like any
other: `BOUND_HIT`, naming the source.

This is a property of ties generally rather than of variables, and
`tie(..., scale=2.0)` between two model parameters behaves the same way. It is
exact for a tie with one source, which is every tie rietx derives and most that
anyone writes. With several sources the constraint is a slanted boundary rather
than a range, and the optimiser can only be given a range, so what it gets is
the smallest range containing every allowed point. It never rules out an answer
you asked for, and it can leave a corner where two sources conspire. If a fit
lands in that corner the write-back refuses, naming the parameter, its bounds
and the tie that drove it.

A variable may follow other variables, and that is what makes composing them
worth the trouble:

<!-- api-doc: no-exec — it needs the reader's own structure and instrument -->
```python
ref.add_variable("B_base", 0.4)
ref.add_variable("B_extra", 0.1)
ref.add_variable("B_total", 0.5)      # declared before it can be tied
ref.tie("vars.B_total", {"vars.B_base": 1.0, "vars.B_extra": 1.0})
```

That second argument is the other half. `Refinement.tie` takes several sources
as a `{path: coefficient}` mapping or a list of pairs, not only one, and `scale`
multiplies every term. A model parameter still may not follow a tied model
parameter, and there the refusal's advice is right, since naming what it follows
says the same thing without inheriting a constant nobody wrote.

A variable is no expression language. The relation is affine,
`Σ coefficient · source + constant`, because that is what the constraint block
computes exactly. There is no string form: `"2*A + 0.5"` parses nowhere, and the
method calls above are the whole surface.

(holding-a-parameter)=
## Holding a parameter against the plan

Setting `vary=False` does not keep a parameter still. A plan replaces the vary
flags rather than continuing them, so a stage whose `turn_on` glob matches your
pinned parameter frees it and refines it. The value moves, the model you handed
in goes on reading `vary=False`, and nothing says which of the two declarations
won.

`Refinement.hold` is how you say it and have it stick.

<!-- api-doc: no-exec — it needs the reader's own structure and instrument -->
```python
ref = rx.Refinement(standard, instrument)
ref.hold("phases.0.cell.*")            # the certificate's cell, not a guess
result = ref.fit(data, plan="lab_calibrate")
```

The verb takes the same fnmatch globs as `set_vary` and returns the paths it
held, sorted. `Refinement.unhold` takes it back, and takes the same globs; a
literal path that is not held is refused rather than passing silently. An
unheld parameter comes back fixed at its current value, since withdrawing a
refusal to move something is not a decision to move it.

Calibration is the case it exists for. Refining a certified standard with its
cell held fixed is what decorrelates zero shift from displacement from cell,
and it works because the cell is supplied rather than fitted. A plan that
frees that cell leaves a calibration that is worthless and reports nothing
unusual. On the 11-BM LaB6 SRM 660a pattern over 2-30° 2θ, `mccusker_default`
moves a cell declared at 4.157597 Å to 4.156826 Å, which is 185 ppm. With the
hold in place it comes back at 4.157597 Å exactly.

A hold outranks a plan's glob and loses to the space group. Holding
`phases.0.cell.*` on a cubic phase marks all six rows and frees none of them,
and the listing still reports `b` as tied and `alpha` as locked, because those
are the reasons `unhold` cannot lift. The parameter listing reads a held row
through `ParameterRow.held`, and [](model.md) has the field beside the other
four held-reasons.

A polar space group (P 6₃ m c, P 4 m m, Pna2₁, C c, P 1) needs one more hold. Every
atom has a free coordinate along the polar axis, and the whole structure can slide
along it without changing any intensity. A plan that frees them all walks the
atoms along that axis and quotes an esd for a position the data does not fix. On a
synthetic zincite pattern under `mccusker_structural`, the TRF driver moved Zn
and O from z = 0 and 0.40 to z ≈ 150, each quoted at ±0.00029.

`Phase.floating_origin = "hold"` makes the parameter table hold, for each
direction the origin floats in, the first atom's displacement DOF that a shift
along it moves. On a hexagonal or tetragonal axis that is the DOF running along
the axis; on rhombohedral axes (R 3 m:R) a general site's x serves, since a
shift along [1, 1, 1] moves it too. `Refinement.hold_floating_origin()` sets
the field on every phase where the table would hold something. The held row
reads `held`, and `ParameterRow.origin_axis` names the direction. The same
zincite fit then keeps Zn at 0 and refines O to 0.38231(57), the esd of the Zn-O
difference. The fit, a joint fit included, reports `ORIGIN_FIXED_ON_POLAR_AXIS`
naming the phase, the direction and the atom. Where every DOF such a shift moves
is tied or held, so none can be held, and a stage still frees what walks the
direction (a variable they all follow), it reports `ORIGIN_NOT_FIXED` instead.
A tie or hold of your own that already fixes the origin gets no second hold.
`unhold` on the held DOF sets the field back to `None`. The field is `None` by
default, so nothing is held unless you ask. The directions themselves come from
`rietx.crystallography.wyckoff.floating_origin_basis(space_group)`.

`Phase.floating_origin = "centroid"` holds nothing. Instead each stage that
can slide the phase restrains a weighted centroid of its sites to where the
stage found it, as Flack & Schwarzenbach (1988) do. The weights come from the
data, so every coordinate along the axis is refined and keeps an esd you can
quote on its own. The same zincite fit gives z(O) − z(Zn) = 0.38231, the held
fit's answer at the same Rwp, with each z quoted at ±0.00039: two sites share
the difference's esd equally and uncorrelated. `ORIGIN_FIXED_ON_POLAR_AXIS`
then names the sites with their weights. A joint fit refuses `"centroid"` by
name and accepts `"hold"`. The restraint is the theory part's
{eq}`par-origin-centroid`.

The stage that wanted the parameter says so. `StageResult.blocked_by_hold`
names what its glob matched and could not free, and the fit raises
`HOLD_BLOCKED_PLAN` at `info` naming the paths and the stages. Nothing is
wrong when it fires: it is the record of which declaration won, which is the
half you could not otherwise see.

:::{note}
The diagnostic is keyed on holds rather than on `vary=False` for a measured
reason. `vary=False` is the default rather than a decision, so on the LaB6
above 38 of 46 parameters carry it and a plan frees 8 to 12 of them. A
diagnostic on that would print ten useless lines beside the one that matters.
A hold is only ever deliberate.
:::

A hold lives on one `Refinement`, and a series builds a fresh one per pattern.
Declare it in `SequentialRefinement.fit`'s `constrain` hook to hold across a
chain, the way you declare a tie there ([](series.md)).

(restraining-a-distance)=
## Restraining a distance or an angle

A restraint is the other half of the bargain. Where a constraint removes a
parameter, a restraint adds an observation: a distance, an angle or a parameter
value you know from chemistry, with an uncertainty attached, competing with the
data on the same least-squares footing. Powder data lose information to
overlap, and this is the standard way of putting some back
{cite}`mccusker1999,waser1963`.

Three kinds, declared on `Phase.restraints`:

```python
from rietx.schemas.structure import AngleRestraint, BondRestraint, ValueRestraint

bond = BondRestraint(atom_i=0, atom_j=1, target=1.87, sigma=0.02)
angle = AngleRestraint(atom_i=1, atom_j=0, atom_k=2, target_deg=109.47, sigma=1.5)
occupancy = ValueRestraint(path="phases.0.atoms.1.occ", target=1.0, sigma=0.01)
```

<!-- api-doc: no-exec — it needs the reader's own structure -->
```python
structure.phases[0].restraints = [bond, angle, occupancy]
```

| Restraint | Names the quantity with | Target |
|---|---|---|
| `BondRestraint` | `BondRestraint.atom_i` and `BondRestraint.atom_j` | `BondRestraint.target`, in ångströms |
| `AngleRestraint` | `AngleRestraint.atom_i`, `AngleRestraint.atom_j` (the vertex) and `AngleRestraint.atom_k` | `AngleRestraint.target_deg`, in degrees |
| `ValueRestraint` | `ValueRestraint.path`, any dot-path in the model tree | `ValueRestraint.target`, in that parameter's own unit |

The atom fields are positional indices into `Phase.atoms`, the same convention
the dot-paths use. All three kinds carry the same two numbers beside the
target. `BondRestraint.sigma`, `AngleRestraint.sigma` and `ValueRestraint.sigma`
are the uncertainty you are claiming, and that is what decides how hard the
restraint pulls. `BondRestraint.weight`, `AngleRestraint.weight` and
`ValueRestraint.weight` multiply the row on top of it and default to 1.

Each restraint contributes one residual row, √weight·(computed − target)/σ,
appended after the data rows {eq}`par-restraint`. The rows land in the
covariance, so they tighten the esds of the parameters they touch, and they are
excluded from Rwp, the Durbin-Watson statistic and the Bérar-Lelann inflation,
because they are not measurements of this pattern. `RefinementResult.restraints`
is what they report back, and [](results.md) reads it.

A fourth kind, `PlanarityRestraint`, holds four or more atoms to their
least-squares plane. `PlanarityRestraint.atoms` lists their positional indices,
`PlanarityRestraint.sigma` is the uncertainty in ångströms and
`PlanarityRestraint.weight` multiplies the rows. It contributes one row per
atom, √weight·d/σ, where d is that atom's signed distance from the plane, so
it is order-free and has no target {eq}`par-planarity`.
`PlanarityRestraint.op_indices` and `PlanarityRestraint.translations` give each
listed atom's symmetry image, one entry per atom or none, for a ring that
crosses a symmetry element. Leave them out and each atom takes the minimum
image relative to the first.

A distance obeys periodic boundary conditions, so the second atom is taken at a
symmetry image. `BondRestraint.op_index` selects the symmetry operation and
`BondRestraint.translation` the lattice shift; `AngleRestraint.op_index_i`,
`AngleRestraint.translation_i`, `AngleRestraint.op_index_k` and
`AngleRestraint.translation_k` do the same for each arm of an angle. Leave them
out and the minimum image is resolved once, at the stage's starting
coordinates, and frozen for that stage, under the same discreteness rule the
reflection list follows. Name the image explicitly whenever a coordinate is
expected to move far enough to change which image is nearest.

## Refinement plans

Because the groups correlate, freeing everything at once from a poor starting
point walks into a local minimum that a staged release avoids. A fit here is
therefore a plan: a list of stages, each freeing one group and running to
convergence before the next group joins. Parameters stay free once freed, so
each stage refines everything released so far.

`RefinementPlan` carries the presets, named for the job each does:

```python
from rietx import RefinementPlan

RefinementPlan.mccusker_default()      # scale+bkg -> zero -> cell -> W -> U,V,X,Y
RefinementPlan.mccusker_structural()   # ... then coordinates, displacement, PO
RefinementPlan.lab_bragg_brentano()    # ... with sample displacement, Ka2, FCJ axial
RefinementPlan.lab_calibrate()         # instrument calibration, certified cell HELD
RefinementPlan.lab_sample_refine()     # sample against a frozen calibrated instrument
RefinementPlan.profile_only()          # Le Bail
RefinementPlan.pawley_default()        # Pawley
RefinementPlan.magnetic_width()        # moment -> magnetic width -> both
```

The two standard presets are one chain. `mccusker_default` stops after the
widths, and `mccusker_structural` continues into the structure:

```{mermaid}
flowchart LR
  subgraph a ["mccusker_default"]
    direction TB
    A["scale + background"] --> B["zero shift"] --> C["cell"]
    C --> D["W, the constant width"] --> E["U, V, X, Y"]
  end
  subgraph b ["mccusker_structural adds"]
    direction TB
    X["extra components"] --> F["coordinates"] --> G["displacement"] --> H["preferred orientation"]
    H --> I["extinction"] --> J["surface roughness"]
  end
  a --> b
```

Each box is a `Stage`. Every stage runs to convergence with everything above it
still free.

`Refinement.fit` also takes a plan by name (`plan="mccusker_default"`).
`PLAN_INFO` reports each preset's title, description, modes and when to use it,
so a program can offer the choice without hard-coding a list.

A plan is an ordinary object: `RefinementPlan.stages` is a plain list of `Stage`,
so you can edit it.

<!-- api-doc: no-exec — it needs the reader's own structure and instrument -->
```python
plan = rx.RefinementPlan.mccusker_default()
plan.stages.append(rx.Stage("biso", ["phases.*.atoms.*.biso"]))
result = ref.fit(data, plan=plan)
```

`Stage` takes fnmatch globs over the dot-paths, so paths carry no brackets:
fnmatch reads `[..]` as a character class rather than an index.

[](refining.md) is the rest of the machinery: the plan registry a program reads
instead of hard-coding this list, the other settings a `Stage` carries, and how
to run, watch or stop a fit.

### Relaxing the restraints as the model improves

Each restraint carries its own `weight`. A stage can scale all of them at once,
which is how the guidelines {cite}`mccusker1999` ask restraints to be used: the
refinement minimises S = S_y + c_w·S_G {eq}`par-restraint-weight`, and c_w "is
set high at the beginning of a refinement when the structure is incomplete or
only approximately correct" and is reduced "as the structural model improves".
`Stage.restraint_weight_scale` is that c_w, one number per stage.

```python
import rietx as rx

coords = ["phases.*.atoms.*.dof.*"]
plan = rx.RefinementPlan(stages=[
    rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
    rx.Stage("coords_stiff", coords, restraint_weight_scale=300.0),
    rx.Stage("coords_free", coords),          # back to 1.0, the default
])
```

The default is 1.0, which leaves the restraints exactly as they were declared.
`0.0` silences them for a stage without removing their rows, so the row count
the fit statistics exclude does not change part-way through a plan.

What this buys is a path. On a synthetic case whose data under-determines two
oxygen sites, starting from a Zr–O distance of 3.73 Å for a 1.87 Å bond, the
plan above lands the bond at 1.87 Å with the coordinates 1e-3 rms from truth.
The same three stages left at c_w = 1 throughout converge with that distance at
4.84 Å, the restraint 149σ in tension, Rwp 0.0393 against 0.0327.

```{image} figures/restraint-schedule-light.png
:class: only-light
:alt: Two difference curves that look alike, one from a fit with a 1.87 angstrom bond and one from a fit with a 4.83 angstrom bond
```

```{image} figures/restraint-schedule-dark.png
:class: only-dark
:alt: Two difference curves that look alike, one from a fit with a 1.87 angstrom bond and one from a fit with a 4.83 angstrom bond
```

Both fits converged, on the same data, from the same start. The difference
curves are the evidence a reader would normally reach for, and they are nearly
the same curve. Read the restraint deviations instead. The failed fit is a
slightly worse fit, and no announcement that a bond is 4.8 Å.

A stiff c_w makes a restraint more authoritative rather than more correct. Where
the chemistry assumed is wrong (the guidelines' example is a tetrahedral site
that is really octahedral), "the refinement will not progress satisfactorily",
and a higher weight makes that worse.

`RestraintReport.weight_scale` records the c_w a result was measured under, so a
report always says which weight was insisting on its deviations. The deviations
themselves are reported unscaled, and [](results.md) reads the rest of that
object.

### The order the presets encode

The backbone is the order McCusker et al. {cite}`mccusker1999` set out in the
IUCr Rietveld refinement guidelines:

1. Background and scale first. The guidelines want good starting values for the
   background before the structure is touched, and the calculated pattern scaled
   to the observed one before anything is read off a difference plot.
2. Peak positions before everything else. The cell and the 2θ correction (the
   zero shift, plus sample displacement where the geometry has one) refine
   before the widths and before the structure. The guidelines put it flatly:
   unless the observed and calculated peak positions match, a Rietveld
   refinement cannot and will not work.
3. Then the widths, then the asymmetry. `mccusker_default` stops after the
   widths. `lab_bragg_brentano` and `lab_calibrate` continue in the guidelines'
   order with a `lines_axial` stage after them, carrying the FCJ
   axial-divergence ratios and the Kα2 weight.
4. Then the structure, coordinates before displacement parameters. The
   guidelines note that the scale, the occupancies and the displacement
   parameters are correlated with each other and are the parameters most
   sensitive to a background error, so they follow the positions rather than
   accompany them.
5. Everything free together at the end. Stages are cumulative for a reason the
   guidelines state explicitly: the esds are only correct when all parameters,
   profile and structural, are refined simultaneously. The last stage of every
   preset does that.

One departure: the guidelines suggest refining the heavier atoms' positions
before the lighter ones, and `mccusker_structural` frees every coordinate in one
`coordinates` stage. Nothing here measures what the split would buy. If your
structure has a large scattering contrast and a poor starting model, split that
stage yourself; a plan is an ordinary object.

Three further ordering rules are this package's own rather than the guidelines':

- Widths last among the profile terms, and `w` before `u`, `v`, `x`, `y`. `w` is
  the constant term of the Gaussian width. Free the tan θ and 1/cos θ terms
  first and they absorb a constant offset, then fight it when `w` joins.
- Intensity-scaling corrections go last, after the structure has settled.
  Preferred orientation, extinction and surface roughness all rescale
  intensities as a function of Q, and so do the scale, the occupancies and the
  displacement parameters. Free a correction early and it eats intensity that
  belongs to the structure.
- Anisotropic strain is freed inside the sample-broadening stage rather than
  after it. A Stephens block locks `phases.*.lor_strain`, because the isotropic
  direction of the block is identically that column. Deferring the block would
  leave the isotropic width unrefined until fifteen correlated coefficients turn
  on at once.

:::{admonition} For agents
:class: agent
{doc}`the agent skill <skill>`
§2 and §3 give the same order as an operating discipline, with the measured
findings behind each rule, including what a Le Bail pass does that one `fit`
call cannot.
:::
