(guide-restrain)=
# How to restrain a bond length or an angle

Put a `BondRestraint`, `AngleRestraint` or `ValueRestraint` in the phase's `Phase.restraints` list before the fit, and each one adds a weighted observation of that quantity.

A restraint keeps every parameter free and adds information from chemistry, which powder data lose to peak overlap {cite}`mccusker1999,waser1963`.
To link two parameters exactly instead, see [How to tie parameters together](tie.md).

## Declare the restraints

Each kind names its quantity, a target and an uncertainty `sigma`:

```python
import rietx as rx
from rietx.examples import examples_dir
from rietx.schemas.structure import AngleRestraint, BondRestraint, ValueRestraint

structure = rx.Structure.from_cif(examples_dir() / "fluorapatite.cif")
structure.phases[0].restraints = [
    BondRestraint(atom_i=2, atom_j=4, target=1.54, sigma=0.01),
    AngleRestraint(atom_i=4, atom_j=2, atom_k=5, target_deg=109.47, sigma=1.0),
    ValueRestraint(path="phases.0.atoms.3.biso", target=1.0, sigma=0.2),
]
```

| Restraint | Names the quantity with | Target and its unit |
|---|---|---|
| `BondRestraint` | `atom_i` and `atom_j` | `target`, in Å |
| `AngleRestraint` | `atom_i`, `atom_j` (the vertex) and `atom_k` | `target_deg`, in degrees |
| `ValueRestraint` | `path`, a parameter's name | `target`, in that parameter's unit |

The atom fields are positions in `Phase.atoms`, counted from 0, as in parameter names.
In fluorapatite atom 2 is P3 and atoms 4 to 6 are the oxygens O5, O6 and O7.

## Choose sigma

`sigma` is the uncertainty you claim for the target, and it sets how hard the restraint pulls.
Each restraint adds one residual, √weight × (computed − target) / sigma, beside the residuals of the pattern {eq}`par-restraint`.
The optional `weight` multiplies that residual and defaults to 1.

The restraint residuals enter the covariance, so they shrink the esds of the parameters they touch.
They are left out of Rwp, the Durbin-Watson statistic and the Bérar-Lelann esd correction, because they are not measurements of the pattern.

## Run the fit and read the restraints

This fit restrains the three P–O bonds of fluorapatite's phosphate group to 1.54 Å, and one O–P–O angle to the tetrahedral 109.47°.
It refines the GSAS-II tutorial pattern that ships with rietx.

```{literalinclude} ../../../examples/guides/restrain.py
:language: python
:start-after: "# guide: start"
:end-before: "# guide: end"
```

<!-- output of examples/guides/restrain.py -->
```text
bond [2, 4] 1.552 +1.2
bond [2, 5] 1.574 +3.4
bond [2, 6] 1.526 -1.4
angle [4, 2, 5] 110.796 +1.3
['fluorapatite P3', 'fluorapatite O6'] The bond restraint deviates +3.4σ from its target (1.574 vs 1.54).
```

`RefinementResult.restraints` holds one row per restraint, with the computed value and its deviation from the target in units of sigma.
The P3–O6 bond ends 3.4 sigma from its target, and the fit reports [`RESTRAINT_TENSION`](../reference/diagnostics-refinement.md#restraint_tension).
The diagnostic's `where` names the two atoms.

Here the pattern's 5 751 points outweigh four restraints.
The script refits with every sigma a thousand times larger, so the restraints pull on nothing, and each bond moves by at most 0.0011 Å:

<!-- output of examples/guides/restrain.py -->
```text
bond shifts: 0.0004, 0.0011, 0.0004
```

So the data place the bonds, and the restraints add little.
When a restraint is in tension, either correct its target, loosen its sigma, or accept that the data overrule it.
The full script is `examples/guides/restrain.py`.

## Hold a ring or a group planar

A fourth kind, `PlanarityRestraint`, holds four or more atoms to their least-squares plane.
`PlanarityRestraint.atoms` lists their positional indices, `PlanarityRestraint.sigma` is the uncertainty in ångströms and `PlanarityRestraint.weight` multiplies the rows.
It adds one row per atom, √weight × d / σ, where d is that atom's signed distance from the plane, so it is order-free and has no target {eq}`par-planarity`.
`PlanarityRestraint.op_indices` and `PlanarityRestraint.translations` give each listed atom's symmetry image, one entry per atom or none, for a ring that crosses a symmetry element.
Leave them out and each atom takes the minimum image relative to the first.

## Choose the symmetry image

A bond or an angle may reach an atom in a neighbouring unit cell, or a symmetry copy of it.
If you name no image, rietx takes the nearest one at the start of each stage and keeps it for that stage.
Name the image yourself when an atom may move far enough to change which copy is nearest:

- `BondRestraint.op_index` selects the symmetry operation applied to `atom_j`, and `BondRestraint.translation` the lattice translation;
- `AngleRestraint.op_index_i` and `AngleRestraint.translation_i` do the same for `atom_i`, and `AngleRestraint.op_index_k` and `AngleRestraint.translation_k` for `atom_k`.

## Make the restraints stiff early and relax them later

The IUCr guidelines {cite}`mccusker1999` give restraints a large weight while a model is approximate, and a smaller one as it improves.
`Stage.restraint_weight_scale` multiplies every restraint's weight for one stage, as c<sub>w</sub> in {eq}`par-restraint-weight`:

```python
import rietx as rx

coords = ["phases.*.atoms.*.dof.*"]
plan = rx.RefinementPlan(stages=[
    rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
    rx.Stage("coords_stiff", coords, restraint_weight_scale=300.0),
    rx.Stage("coords_free", coords),
])
assert [s.restraint_weight_scale for s in plan.stages] == [1.0, 300.0, 1.0]
```

The default, 1.0, leaves each restraint as declared.
A scale of 0.0 switches the restraints off for that stage while keeping their rows, so the fit statistics count the same rows throughout the plan.
`RefinementResult.restraints` records the scale it was measured under as `RestraintReport.weight_scale`.

On a synthetic structure in rietx's test suite, with a Zr–O bond started at 3.73 Å for a true 1.87 Å, this plan recovers the bond and both oxygen positions.
The same plan with every scale at 1.0 also converges, with the bond at 4.84 Å and its restraint 149 sigma in tension.
Rwp is 0.0393 against 0.0327, and the two difference curves look much alike.
Read the restraint deviations, because Rwp barely separates the two fits.

:::{warning}
A stiff weight makes a restraint more authoritative, not more correct.
If the assumed chemistry is wrong, such as a tetrahedral target on a site that is octahedral, a larger weight makes the fit worse.
:::

## See also

- [About the report](../concepts/report.md) lists the report's restraint and geometry sections.
- The theory of restraints is in [Parameterisation](../theory/parameterisation.md).
