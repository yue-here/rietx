# Derived quantities

This page gives the quantities a fit computes from its refined parameters: interatomic distances, angles and torsion angles, each phase's cell volume, and each phase's crystallite size and microstrain in physical units, each with its esd.

All three are fields of the `RefinementResult` a fit returns.
[The refinement result](result.md) gives the rest of the result.
Each esd is propagated through the parameter covariance, as [Esds of derived quantities](../theory/estimation.md#esds-of-derived-quantities) derives in equation {eq}`est-derived`.
[About correlations and esds](../concepts/correlations.md#derived-quantities) explains why the whole covariance matters.

## Bonding geometry

The IUCr guidelines rank the distances and angles above every R value.
The two most important criteria for judging a refinement are the profile fit and the chemical sense of the structure {cite}`mccusker1999`.
`RefinementResult.geometry` is a `GeometryTable` that carries the distances, angles and torsion angles.

| Field | Is | Reads as |
|---|---|---|
| `GeometryTable.distances` | one `GeometryDistance` per neighbour | every asymmetric-unit atom's whole environment, so the rows naming an atom count its coordination number and a bond between two sites is listed twice, once from each end |
| `GeometryTable.bonds`, `GeometryTable.contacts` | the two halves of that list | split by `GeometryDistance.bonded` |
| `GeometryTable.angles` | one `GeometryAngle` per pair of bonded neighbours | at every vertex, over that vertex's complete bonded environment; a contact is never an arm |
| `GeometryTable.torsions` | one `GeometryTorsion` per chain A–B–C–D of three bonds | each torsion once, never again read from its other end |
| `GeometryTable.bond_slack` | the slack added to the covalent-radius sum, in Å | 0.4 Å |
| `GeometryTable.contact_max` | the listing radius for non-bonded contacts, in Å; bonds are found past it | 3.5 Å |
| `GeometryTable.notes` | where coverage stopped | empty means nothing was bounded |

A pair is bonded when its distance is at most the sum of the two covalent radii plus `GeometryTable.bond_slack`.
A pair of two metals is always a contact, because a radius criterion is no evidence of a metal-metal bond.
Past the slack a pair is still listed, as a contact, out to `GeometryTable.contact_max`.
The guidelines ask for both kinds: "interatomic distances (both bonding and nonbonding) should be reasonable" {cite}`mccusker1999`.
The slack and the search radius are conventions rather than physical constants, and the table records the values it used.

Four limits write a note.
Each atom keeps its 24 nearest contacts, and a note counts the contacts the cap dropped.
Each atom keeps 36 torsions about the bonds it starts, and a note counts the torsions that cap dropped.
A chain with a straight bond angle has no torsion, and a note counts those chains.
A phase with more than 200 asymmetric-unit atoms is not searched, and a note names it.

A row's value is `GeometryDistance.distance` in ångströms, or `GeometryAngle.angle` in degrees.
Each row names its atoms twice.
The first naming uses the labels the structure carries: `GeometryDistance.atom_1` and `GeometryDistance.atom_2`, or `GeometryAngle.atom_1`, `GeometryAngle.atom_2` and `GeometryAngle.atom_3` with the vertex in the middle.
The second uses indices into `Phase.atoms`: `GeometryDistance.atom_index_1`, `GeometryDistance.atom_index_2`, `GeometryAngle.atom_index_1`, `GeometryAngle.atom_index_2` and `GeometryAngle.atom_index_3`.
`GeometryDistance.phase_index` and `GeometryAngle.phase_index` say which phase, in a multi-phase fit.

`GeometryDistance.symmetry_2` is the CIF `n_klm` code of the image the second atom sits at.
It resolves against the operation list the exported CIF writes beside it.
The code holds a lattice shift of −4 to +4 along each axis, and an image that needs a larger one carries `None`.
The distance and its esd are unaffected.
`GeometryDistance.symmetry_1` is always `.`, the published position.
So is `GeometryAngle.symmetry_2`, the vertex, while `GeometryAngle.symmetry_1` and `GeometryAngle.symmetry_3` code the two arms.

### Torsion angles

A `GeometryTorsion` is the torsion angle of a chain A–B–C–D whose three links are bonds of the table.
`GeometryTorsion.angle` is in degrees, in the range (−180°, 180°], so an anti chain reads 180 and never −180.
Its sign is Klyne and Prelog's, the one the CIF dictionary states for `_geom_torsion`: looking along B → C, the angle is positive when the bond B–A turns clockwise, by less than 180°, to eclipse C–D {cite}`klyne1960`.
Equation {eq}`par-torsion-restraint` gives the angle.
`GeometryTorsion.atom_1`, `GeometryTorsion.atom_2`, `GeometryTorsion.atom_3` and `GeometryTorsion.atom_4` are the labels in chain order.
`GeometryTorsion.atom_index_1`, `GeometryTorsion.atom_index_2`, `GeometryTorsion.atom_index_3` and `GeometryTorsion.atom_index_4` are the indices into `Phase.atoms`.
`GeometryTorsion.phase_index` says which phase.
`GeometryTorsion.symmetry_1`, `GeometryTorsion.symmetry_3` and `GeometryTorsion.symmetry_4` code the images of A, C and D as a distance's codes do.
B sits at its published position in the table, so its `GeometryTorsion.symmetry_2` is `.`.
The esds, `GeometryTorsion.stderr` and `GeometryTorsion.stderr_diagonal`, follow the distances' conventions.
Their partials are analytic, so a torsion at exactly 180° has a finite esd.

Torsions are listed about each asymmetric-unit atom B in turn, over its bonds B–C nearest first, then A and D nearest first.
The 36 kept about one atom are every chain a molecule of atoms with at most four bonds has, so a molecular structure is listed whole.
A densely bonded inorganic phase reaches the cap: in LaB₆ the La has 24 bonded B and 4 374 chains.
The cap changes which rows are listed, never an esd.

### Asking for particular rows

`Refinement.geometry()` returns the same table.
`Refinement.geometry(request)` returns only the rows a `GeometryRequest` names, so a torsion past the cap, a contact past the listing radius, or a torsion over atoms that are not bonded can be measured too.
A plain dictionary with the same fields is accepted in place of the object.

| Field | Is |
|---|---|
| `GeometryRequest.distances` | pairs of atoms |
| `GeometryRequest.angles` | triples of atoms, the vertex in the middle |
| `GeometryRequest.torsions` | chains of four atoms |
| `GeometryRequest.phase_index` | which phase the labels name; 0 by default |

Each atom is its label, such as `"C1"`, or its label and a CIF symmetry code, such as `("C1", "2_655")`.
An atom given by its label alone sits at the image nearest the atom it is measured from.
That is the previous atom of a distance or a torsion, and the vertex for an angle's two arms.
The first atom of a distance or a torsion, and an angle's vertex, sit at their published positions unless a code says otherwise.
Each row in the answer names the image it used, so the codes it prints reproduce it.
A torsion whose chain has a straight bond angle has none, and the answer's notes say so.
An unknown label, or a code that is not of the form `n_klm`, raises.

<!-- api-doc: no-exec — it needs a refinement of a structure with these labels that has run -->
```python
got = ref.geometry({"torsions": [["C2", "C3", "C4", "C5"]],
                    "distances": [["O1", ("N2", "2_555")]]})
got.torsions[0].angle, got.torsions[0].stderr
```

The answer has esds while the last fit's covariance is still live, which is from the end of `Refinement.fit` or `Refinement.run_stage` to the next edit.
The esds come from the covariance the fit's parameter esds were read off, with the Bérar-Lelann factor already in it, so a row the table lists carries the same numbers in both.
With no live fit, before one, after an edit or a checkout, the values are the current model's and every esd is `None`.
The verb returns `None` in Le Bail and Pawley mode, as the result does.

A distance prints on one line, such as `Ca1–O5  2.3898(50) Å  5_565` from the fluorapatite tutorial fit.

Geometry is computed for a Rietveld fit only.
In Le Bail and Pawley mode `RefinementResult.geometry` is `None`, because the dummy atom those modes require is not a structure to measure.
The table is computed when the fit closes.
The covariance it needs comes from the final Jacobian, and the Jacobian is not stored.

### Esds of distances and angles

`GeometryDistance.stderr` is propagated through the whole parameter covariance.
The guidelines require the whole correlation matrix, and not only its diagonal, in the esd of any derived quantity {cite}`mccusker1999`.
`GeometryDistance.stderr_diagonal` is the same propagation with the correlations between refined parameters set to zero.
It is the number a reader combining the printed parameter esds in quadrature would get.
It is reported so the difference can be seen, and it is never the answer.
`GeometryAngle.stderr` and `GeometryAngle.stderr_diagonal` are the same pair for an angle, in degrees.

```{image} ../figures/geometry-esd-light.png
:class: only-light
:alt: Diagonal-only esd divided by the full-covariance esd for each NAC distance, scattered from 0.86 to 1.41 on both sides of a dotted line at one
```

```{image} ../figures/geometry-esd-dark.png
:class: only-dark
:alt: Diagonal-only esd divided by the full-covariance esd for each NAC distance, scattered from 0.86 to 1.41 on both sides of a dotted line at one
```

Dropping the correlations is not a conservative approximation.
The figure shows the 88 distances of an 11-BM NAC refinement under `mccusker_structural` (Rwp 0.0819), each as its diagonal-only esd over its full one.
The ratio runs from 0.86 to 1.41, on both sides of one.
So the diagonal-only number is sometimes too small and sometimes 40 % too large, and nothing in the row says which.

The spread appears only once the coordinates refine.
Under a plan that frees the cell and nothing structural, a cubic phase's distances depend on one free parameter.
The quadratic form then has one term, and the two esds agree to the last digit.
The guideline is about correlation between coordinates, so a table quoted from a profile-only refinement shows no difference.

### Absent esds

An esd is `None` when it cannot be measured.
That is an absence, and it never means σ = 0.
Four routes lead there, for a torsion as for a distance:

- The result has no covariance behind it.
  Any evaluate-only pass, a replay of a history node included, has distances and no esds at all.
- Nothing free reaches the row.
- Symmetry fixes the value, as for a fluorite Ca–F distance with the cell held, or a rutile O–Ti–O angle, which stays at exactly 90° however the one free coordinate moves.
  The variance then reaches zero by cancelling terms, and a variance below {{ VARIANCE_CANCELLATION_FLOOR }} of the sum of those terms counts as zero.
  A rigid body's template fixes a distance or a torsion inside it the same way, and so does an inversion centre for a torsion A–B–B′–A′ across it.
- The angle is within {{ ANGLE_LINEARISATION_LIMIT_DEG }}° of 0° or 180°.
  Such an angle is a stationary point, where the linear propagation of {eq}`est-derived` does not hold.

The distance or angle itself is exact in all four cases.
Only its uncertainty is withheld.

## Cell volume

`RefinementResult.cell_volumes` holds one `CellVolume` per phase, in every mode, because a Le Bail cell is refined as surely as a Rietveld one.
`CellVolume.phase_index` names the phase and `CellVolume.volume` is in Å³.
`CellVolume.stderr` goes through the covariance of the six cell entries, so a tie such as b = a and a correlation between a and c both reach it.
On a cubic cell it is exactly 3a²σ(a).
`CellVolume.stderr_diagonal` is the diagonal-only number, as for a distance.
The four absences of a distance's esd apply unchanged.
The refinement CIF writes the volume with this esd.
`RefinementResult.cell_volumes` is `None` on a result that did not come from a fit.

## Size and strain

A refined profile width is a number of degrees, and a number of degrees does not transfer between instruments.
The same 0.09° of 1/cosθ broadening is a coherent domain of about 410 Å on Mo Kα and about 880 Å on Cu Kα.
`RefinementResult.microstructure` holds one `PhaseMicrostructure` per phase, in phase order.
Each reads the four sample-broadening coefficients as the two quantities behind them.
[Reading a width as a size](../theory/microstructure.md#reading-a-width-as-a-size) and [Reading a width as a strain](../theory/microstructure.md#reading-a-width-as-a-strain) state the two conversions as equations {eq}`ms-size-coefficient` and {eq}`ms-strain-coefficient`.

| Field | Is | Reads as |
|---|---|---|
| `PhaseMicrostructure.phase_index`, `PhaseMicrostructure.phase_name` | which phase the block is about | the index into `Structure.phases` and that phase's `Phase.name`, so a block reads on its own in a multi-phase fit |
| `PhaseMicrostructure.terms` | one `MicrostructureTerm` per sample coefficient | four rows (`lor_size`, `gauss_size`, `lor_strain`, `gauss_strain`), whether or not any of them refined; `PhaseMicrostructure.term` fetches one by coefficient name, such as `term("lor_size")` |
| `MicrostructureTerm.kind` | `"size"` or `"strain"` | which conversion produced `MicrostructureTerm.value`: a coherent domain size in ångströms, or a dimensionless Δd/d |
| `MicrostructureTerm.coefficient` | the refined coefficient | in its stored units, deg 2θ for the Lorentzian pair and deg² for the Gaussian variances, so a row can be checked against `RefinementResult.parameters` without converting anything |
| `MicrostructureTerm.value`, `MicrostructureTerm.esd` | the reading and its esd | `None` for a cause that `MicrostructureTerm.unavailable` names |
| `MicrostructureTerm.path` | the parameter it came from | such as `phases.0.lor_size`, so the row joins `RefinementResult.parameters` and any diagnostic's `where` |
| `PhaseMicrostructure.wavelength`, `PhaseMicrostructure.scherrer_k` | the two constants the size reading used | the source's longest declared line, and the Scherrer K, so a size can be rescaled to another convention |
| `PhaseMicrostructure.size_agreement`, `PhaseMicrostructure.strain_agreement` | the Gaussian reading divided by the Lorentzian one | 1 means the two independent columns describe one specimen; `None` when either reading is absent |
| `PhaseMicrostructure.separable`, `PhaseMicrostructure.size_strain_collinearity` | whether size and strain are distinguishable over the range measured | read [Separating size from strain](#separating-size-from-strain) before quoting either number |

`FitReport.microstructure` is a copy of the same list on the report, so a reader working from `Refinement.report()` need not go back to the result.
The report adds one thing to its copy, the separability verdict.

A coherent domain size is the length over which the lattice diffracts in phase.
It is not a particle size and must not be reported as one.
`Phase.particle_radius_um` is a different quantity for a different correction, the absorption path through a grain, and a particle is an aggregate of domains.
A domain size is also not a two-figure number.
K moves 10-20 % with crystallite shape, so `SCHERRER_K` = 0.9 is one convention among several.
GSAS-II reads its size off the same FWHM with K = 1.
FullProf reads it off the integral breadth, which for a pure Lorentzian is π/2 = 1.571 times the FWHM rietx uses.
Quote the size as an order of magnitude, with the K the row carries.

### Separating size from strain

Over a short 2θ range 1/cosθ and tanθ are nearly the same curve, so a fit can trade a size against a strain with no change in Rwp.
That is the Williamson-Hall problem, and it is why a size is reported with `PhaseMicrostructure.separable` beside it.
The verdict is the width trend's own: `TrendAnalysis.separable` on the `"width"` observable, with `PhaseMicrostructure.size_strain_collinearity` carrying the correlation it was decided on.
So the report holds one opinion about it.

The report writes the verdict on its own copy, `FitReport.microstructure`.
On `RefinementResult.microstructure` both fields stay `None`.
On the report they are `None`, meaning no claim made, when Layer 1 abstained or no width trend was fitted.

Where it says `False`, quote neither number alone.
Refining one of the pair and holding the other does not help, because the answer then depends on which one was held.
Measuring over a wider range does.

### Esds and absent readings

Each reading is a function of exactly one refined coefficient, so its esd is that coefficient's scaled by the derivative and nothing is dropped.
For the Lorentzian pair the reading's relative esd equals its coefficient's.
The Gaussian pair store a variance, whose square root is the width, so the reading's relative esd is half its coefficient's.
A combined Gaussian-plus-Lorentzian size would be a function of two correlated columns, and is not reported.
The two are read separately and compared through `PhaseMicrostructure.size_agreement` instead.

`MicrostructureTerm.unavailable` names why a number is missing:

| `unavailable` | What happened |
|---|---|
| `"at_zero"` | the coefficient is at its off state, where a size is infinite and a strain is a perfect lattice; true, and not a number to report. A phase whose widths were never refined says this in all four rows |
| `"no_wavelength"` | the source declares no emission line, so no size can be read; a strain has no wavelength in it and never says this |
| `"not_measured"` | the coefficient has no esd, so `MicrostructureTerm.value` stands and `MicrostructureTerm.esd` does not: the parameter was never freed, its column measured nothing, or the result came from `rietx.replay` |
| `None` | nothing is missing |

### Size in a joint fit

A joint fit shares the crystallite size and not the degrees it is read in.
In a multi-histogram fit `MultiHistogramRefinement` normalises the size coefficients by wavelength.
A Lorentzian size coefficient goes as λ and a Gaussian one as λ², while a strain coefficient does not depend on λ.
The shared column is the coefficient at the first histogram's wavelength, and each histogram's own structure copy carries the value it needs.
So the crystallite behind them is a single number, and the [`SIZE_NORMALISED_ACROSS_WAVELENGTHS`](diagnostics-series.md#size_normalised_across_wavelengths) diagnostic says so.
Read a shared `phases.*.lor_size` as histogram 0's coefficient, never as the number your second pattern shows.
