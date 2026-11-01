# Magnetic refinement

This page gives the magnetic side of a refinement: the satellite test for intensity the nuclear model leaves unexplained, how a moment and its magnetic space group are stated, what the fit reports about a moment, the magnetic peak width, and `solve_magnetic` with the answer it returns.

The magnetic term is a neutron term.
It enters a constant-wavelength neutron pattern and nothing else.
[Patterns and structures](data.md#propagation-vector) gives the phase fields that declare a propagation vector, a magnetic space group and a moment, and [Structure files](structure-files.md) gives what a magnetic CIF reads and writes.
The magnetic structure factor and the dipole approximation are in [Intensities](../theory/intensities.md#the-magnetic-structure-factor).

## Satellite evidence

`FitReport.satellites` tests whether the intensity a fit leaves unexplained indexes as magnetic satellites.
It needs a cell, a space group and a wavelength.
A satellite is a position, so no moment, no magnetic form factor and no magnetic symmetry enters, and the test can run before you decide whether a magnetic model is worth building.

For each phase it sorts the positive residual peaks into three places, and scores only the third.

1. On a calculated line: a nuclear misfit, or a k = 0 magnetic structure whose intensity falls on the nuclear reflections. The test cannot tell those apart.
2. On a reciprocal-lattice point that a glide or screw absence of the assumed space group forbids. These peaks need no propagation vector.
3. Neither: the only peaks a satellite is needed to explain.

For those it generates the satellite positions Q = H ± k for an enumerated set of candidate propagation vectors k, and counts how many peaks fall within {{ VALIDITY_RADIUS_FWHM }}·FWHM of a satellite, the report's own validity radius.
It publishes the whole ranked list, because the k at the top is a hypothesis to test and not an answer.

<!-- api-doc: no-exec — it needs a refinement that has run -->
```python
report = ref.report()
arm = report.satellites[0]
print(arm.note)
for c in arm.candidates[:3]:
    print(c.vector, c.matched, "of", arm.n_unexplained)
```

| Field | Is | Reads as |
|---|---|---|
| `SatelliteEvidence.phase_index` | which phase | its position in `Structure.phases` |
| `SatelliteEvidence.radiation` | `"neutron"` or `"xray"` | read off the phase's own scattering amplitude |
| `SatelliteEvidence.n_residual_peaks` | positive residual peaks before the sort | |
| `SatelliteEvidence.excess_on_nuclear_lines` | residual peaks on a calculated reflection | a nuclear misfit or a k = 0 structure; not scored |
| `SatelliteEvidence.excess_on_absent_lattice_lines` | residual peaks on a reciprocal-lattice point the assumed group's glide or screw forbids | four causes the test cannot separate ([Forbidden lattice points](#forbidden-lattice-points)); not scored |
| `SatelliteEvidence.n_unexplained` | peaks at neither, the ones the ranking was scored against | zero means nothing needed a satellite, which is not a result about the specimen |
| `SatelliteEvidence.declared_k` | the k the phase already declares, or `None` | the test still scores, since a declared k does not say whether another explains the rest |
| `SatelliteEvidence.generator` | the candidate set used | `zone_boundary_candidates` in a report |
| `SatelliteEvidence.candidates` | the ranked list, one `SatelliteCandidate` each | empty when there was nothing to score |
| `SatelliteEvidence.note` | the findings, as sentences | never empty |
| `SatelliteCandidate.vector` | the plain spelling, `(0, 0, 1/2)` | what to type into `Phase.propagation_vector` |
| `SatelliteCandidate.k` | the three exact rationals | |
| `SatelliteCandidate.name` | a positional label, `k1`, `k2`, … | stable within one candidate set, and nothing else |
| `SatelliteCandidate.cdml` | the CDML k-label | always `None` in this version: the tables are not in the package, and a made-up label would look like CDML and disagree with it |
| `SatelliteCandidate.matched`, `SatelliteCandidate.matched_fraction` | how many unexplained peaks this k accounts for, and that count over `n_unexplained` | the ranking key |
| `SatelliteCandidate.worst_offset_deg` | the largest Δ2θ among the matched peaks | `None` when none matched |
| `SatelliteCandidate.n_satellites` | satellite positions this k puts in the fitted range | a k with many positions matches peaks by being everywhere |
| `SatelliteCandidate.star_size` | arms of the star of k | |
| `SatelliteCandidate.minus_k_distinct` | whether −k is a second vector | false when 2k is a reciprocal-lattice vector; the test respects centring. in the default candidate set only (⅓ ⅓ 0) and (⅓ ⅓ ½) on a hexagonal lattice are true, since 2k is not a lattice vector there |

The candidate set is enumerated, not searched: the zone-boundary vectors where k ≡ −k on the phase's own lattice (2k a reciprocal-lattice vector), plus (⅓ ⅓ 0) and (⅓ ⅓ ½) on a hexagonal or trigonal lattice, one per star.
On a primitive lattice those are {0, ½}³ without the origin; on a centred one they are not, and F, for one, adds the X points (1 0 0), (0 1 0) and (0 0 1).
An incommensurate k is outside it, and so is any commensurate k it does not list, so a good pattern can score nothing.
`solve_magnetic` takes another candidate set through `generator=`.

A match count has no chance baseline.
On the Cr<sub>2</sub>WO<sub>6</sub> pattern at 4 K from the GSAS-II *Magnetic-II* tutorial (HB-2A, λ = 2.4067 Å), against a nuclear model refined from the 150 K pattern, the two best candidates each index 2 of the 5 unexplained peaks, from 50 and 56 satellite positions.
At 150 K, above the ordering temperature, the best candidate also indexes 2 of 5.
Read `SatelliteCandidate.n_satellites` beside `SatelliteCandidate.matched`.
The note quotes both for the best candidate and the runner-up, and says when the two tie, since the ranking then breaks only on the offset and the name.

The ranking means nothing in two cases, and the note says so.
With k = 0 the satellites coincide with the nuclear reflections, so a Le Bail extraction absorbs the magnetic intensity into the nuclear intensities.
A k = 0 structure and a nuclear misfit then look alike, and a pattern of the same specimen above its ordering temperature is what separates them.
On an X-ray pattern, intensity at G ± k is a superstructure reflection, at the same positions and with a different meaning.

To test a candidate, declare it as `Phase.propagation_vector` and refine in Le Bail or Pawley mode.
The satellites become reflections the extraction can put intensity on, and whether it does is the measurement.

### Forbidden lattice points

A peak on a forbidden lattice point is forbidden under the space group the fit assumed, and four causes can put one there:

- a true nuclear group that lacks the glide or screw, so the assumed group is too high;
- λ/2 contamination from the monochromator;
- an impurity line that lands on the point;
- on neutrons only, a k = 0 magnetic structure, whose structure factor is an axial vector and can obey the complementary absence rule {cite}`gallego2012`.

The note names all four, or the first three on an X-ray pattern, and `excess_on_absent_lattice_lines` says only that these peaks need no k.
On the Cr<sub>2</sub>WO<sub>6</sub> 4 K pattern four residual peaks sit on forbidden lattice points, among them the (0 0 1) and (1 0 2) regions, and on the 150 K pattern none do.

### Centring-forbidden positions

An integer (h k l) that the lattice's centring forbids, such as (1 0 0) on an F lattice, is not a reciprocal-lattice point, so a peak there is counted in neither of the two lists above.
It stays among the unexplained peaks and is scored like any other.
The note then says how many unexplained peaks sit on such positions, out of how many such positions lie in range, and names the strongest by its height in σ, with its (h k l).
It also lists the causes it cannot separate: a lattice less centred than the one assumed, λ/2 contamination when the group allows (2h 2k 2l) (centring, glides and screws all count), an impurity line, and on neutrons a magnetic structure whose propagation vector is such an integer vector.
A lattice with no centring has no such positions, so the sentence never appears for one.
On the GSAS-II *Magnetic-IV* (Pr,Sr)MnO<sub>3</sub> pattern (space group `F m m m`) the strongest residual peak sits on (1 0 0).

## Moments

A moment is a site attribute, `Atom.moment`, holding a `Moment`.
It needs a magnetic space group on its phase, `Phase.magnetic_symmetry`, holding a `MagneticSymmetry`.
The nuclear and magnetic contributions share the phase's one `Phase.scale`, and phase quantification reads species, occupancy and multiplicity and never sees a moment.
A separate magnetic phase would double the specimen's mass in a phase fraction, and a second magnetic scale would let a wrong moment fit well, so neither is offered.

<!-- api-doc: no-exec — it needs the reader's cell and other sites -->
```python
from rietx import Atom, Moment, Parameter, Phase

mn = Atom(label="Mn", species="Mn",
          x=Parameter(value=0.0), y=Parameter(value=0.0), z=Parameter(value=0.0),
          moment=Moment.from_values((0.0, 0.0, 4.6), "Mn2+", vary=True))
phase = Phase(name="MnF2", space_group="P 42/m n m", cell=cell,
              atoms=[mn, f_site], magnetic_symmetry="136.499")
```

### Magnetic space group

| Field | Holds |
|---|---|
| `MagneticSymmetry.operations` | the magCIF `_space_group_symop_magn_operation.xyz` loop: operations in `x,y,z` form, each ending in a time-reversal sign, as in `"-x,-y,z,-1"` |
| `MagneticSymmetry.centerings` | the `_space_group_symop_magn_centering.xyz` loop, the identity included |
| `MagneticSymmetry.bns_number`, `MagneticSymmetry.og_number`, `MagneticSymmetry.uni_number` | the group's numbers, filled when the group was given as a number |
| `MagneticSymmetry.symbol` | a record you may set; nothing reads it |
| `MagneticSymmetry.setting` | the magCIF `transform_BNS_Pp_abc` to the BNS standard setting, a record |
| `MagneticSymmetry.propagation_vector_parent` | the parent cell's k a supercell was built from, a record |

The operator list is the model.
A UNI, BNS or OG number in its place, as `"136.499"` above, is resolved through spglib's database into that list, and fills the three numbers with `setting` `"a,b,c;0,0,0"`.
A Shubnikov symbol is refused, because no dependency here parses one.
A list that is empty, lacks the identity or is not closed under composition is refused.
`MagneticSymmetry.group` returns the operator algebra.

A magnetic space group has to be a symmetry of the structure it decorates, mapping the cell and every atom, with its moment, onto itself.
A number resolves to the group's default setting, which can disagree with the nuclear phase beside it: a type-IV group next to the symbol of its unprimed operations, a BNS default origin that is not the nuclear group's, or a b-unique number on a c-unique cell.
Each would build a different structure from the one the group describes, so the readers and `Refinement(...)` refuse it by name.
State the nuclear operations with the translation in `Phase.symmetry_operations`, give the operator list in the nuclear setting, or pick the matching setting with `rietx.crystallography.magnetic.operators.database_settings` and `rietx.crystallography.magnetic.operators.magnetic_group`'s `hall_number=`.

### Moment components

| Field | Holds |
|---|---|
| `Moment.crystalaxis_x`, `Moment.crystalaxis_y`, `Moment.crystalaxis_z` | the components in μ<sub>B</sub>, as `Parameter`s |
| `Moment.ion` | the magnetic form-factor key, such as `"Cr3+"` |
| `Moment.g` | the Landé g factor, or `None` |

`Moment.values` returns the three components, `Moment.vary` says whether any of them asks to refine, and `Moment.from_values` builds a block from three numbers.

The components follow the magCIF `_atom_site_moment.crystalaxis_*` convention: components along unit vectors parallel to the a, b and c axes.
That basis is oblique whenever the cell is, so on hexagonal axes the moment (1, 1, 0) is 1 μ<sub>B</sub> and not √2.
The components are not what refines.
The least-squares problem sees `phases.*.atoms.*.moment.dof*`: a modulus in μ<sub>B</sub>, then one or two angles inside the subspace the site symmetry allows ({ref}`sec-moment-dofs`).
The components are written back from those at the end of each stage and carry no esd.

`Moment.ion` is not `Atom.species`.
The neutron scattering length is keyed by nuclide and the form factor by oxidation state.
An ion the table does not carry is refused by name rather than mapped to a neighbour.
Leave `Moment.g` as `None` for a 3d or 4d ion, where the spin-only g = 2 makes the ⟨j<sub>2</sub>⟩ term of the dipole approximation vanish.
Set it for a 4f or 5f ion, where that term does not vanish: an absent g there is refused, because a default would drop a term worth tens of per cent at high angle.

### Refused declarations

Each of these is refused where it is made, because nothing later can rescue it:

- a moment on a phase with no `Phase.magnetic_symmetry`, which leaves no allowed subspace to refine in;
- a moment outside the subspace its site allows, which means the structure and the group disagree;
- a moment on a site that also carries `Atom.aniso`;
- a free moment that is exactly zero, because the magnetic intensity goes as m² and its derivative vanishes there; seed a physical estimate, such as 1-5 μ<sub>B</sub> for a 3d ion;
- a phase that declares both `Phase.propagation_vector` and `Phase.magnetic_symmetry`, which state one magnetic structure two ways.

A moment refines against a `neutron_cw` pattern only.
On an X-ray pattern in a joint fit the magnetic term is not built, so the moment has no gradient there and the report has no moment row for that pattern.
Any other source kind is refused by name.

## Moment evidence

`FitReport.magnetic` holds one `MomentEvidence` per magnetic site.

<!-- api-doc: no-exec — it needs a refinement that has run -->
```python
report = ref.report()
row = report.magnetic[0]
print(row.magnitude, row.magnitude_esd, row.supported, row.unmeasured_directions)
```

| Field | Is | Reads as |
|---|---|---|
| `MomentEvidence.phase`, `MomentEvidence.atom` | which site | the labels you gave, which may repeat across phases |
| `MomentEvidence.path` | the name of the site's modulus, a `phases.*.atoms.*.moment.dof0` parameter | the key to the same number in `RefinementResult.parameters` |
| `MomentEvidence.ion` | the form-factor key in force | |
| `MomentEvidence.magnitude`, `MomentEvidence.magnitude_esd` | the refined modulus and its esd, μ<sub>B</sub> | the esd is copied from `RefinementResult.parameters`, Bérar-Lelann inflated like every esd; `None` when the block did not refine |
| `MomentEvidence.magnitude_from_components` | \|m\| recomputed from the components with the oblique metric | equal to the modulus unless the last stage moved a lattice parameter α, β or γ; a 41 % disagreement on a hexagonal cell is what a Euclidean norm gives |
| `MomentEvidence.crystalaxis` | the three components the modulus and angles imply | derived, so no esd |
| `MomentEvidence.approximation` | the form factor used, named | ⟨j<sub>0</sub>⟩ alone, or ⟨j<sub>0</sub>⟩ + (2/g − 1)⟨j<sub>2</sub>⟩ with g |
| `MomentEvidence.free_directions` | every direction the site symmetry leaves free | `"polar"`, `"azimuth"` |
| `MomentEvidence.unmeasured_directions` | those the powder average did not determine | held, so they carry no esd |
| `MomentEvidence.paired_with` | the paths of other sites this modulus is powder-degenerate with | empty for an ordinary site; [`MOMENT_PAIR_DEGENERATE`](diagnostics-structures.md#moment_pair_degenerate) names the pair |
| `MomentEvidence.paired_magnitude`, `MomentEvidence.paired_magnitude_esd` | the quadrature sum √(Σm²) over the pair, with its esd from the fit's covariance | the number the powder measures for a degenerate pair; `None` otherwise |
| `MomentEvidence.supported` | whether the modulus is above 0.001 μ<sub>B</sub> and above three of its own esds | false means the data do not support a moment here; `None` means the modulus has no esd, so nothing was tested |
| `MomentEvidence.note` | a sentence for whichever case applies | empty when there is nothing to add |

The support test is a ratio.
Refine a moment against a pattern above the ordering temperature and the modulus has nowhere to go, because |F<sub>m</sub>|² ∝ m² and the only way to lower χ² is to remove the magnetic intensity.
Where it stops depends on the rest of the model, so a small value is not a measurement.
On the Cr<sub>2</sub>WO<sub>6</sub> tutorial pattern at 150 K, refined from the ideal trirutile positions with the protocol in `tests/test_acceptance_magnetic.py`, the modulus stops at 0.059 μ<sub>B</sub> with an esd of 0.39, so `supported` is false.
At 4 K the same model gives 2.125 ± 0.045 μ<sub>B</sub>, a ratio of 47, and `supported` is true.

### Directions a powder cannot see

A direction the powder average cannot determine is held, not fitted.
After the orbit average, a cubic collinear structure's intensity does not depend on the moment direction at all, and a uniaxial one measures only the angle to its unique axis.
Those are flat directions of the least-squares problem, so the stage holds them, names them in `StageResult.held`, and reports them in `MomentEvidence.unmeasured_directions`.

The flat rotation is one angle's column only when the frame's polar axis lies along the unique axis.
On tetragonal and hexagonal axes it does, and the azimuth is held.
On rhombohedral axes the unique axis is [111], so the flat rotation mixes the polar angle and the azimuth.
The fit finds that axis from the two angles' response, and before holding it turns the moment about the axis onto the meridian through it.
The data cannot see that turn, and the fit checks this before it writes it.
The azimuth is then the flat rotation and is held, and the polar angle measures the angle to the axis.
The turn changes the direction the fit reports.
`StageResult.moment_flat_axes` gives the axis per site, `StageResult.moment_turned` lists the sites turned, and the moment's note says the reported direction is one of a cone of equally good ones.
Quote the angle to the axis, not the direction.

### An angle at a symmetry direction

A free angle can end at a direction the site symmetry fixes, such as a moment along a in an orthorhombic group.
The data determine the angle there and the fit does not hold it.
But the angle's Jacobian column vanishes at that direction, so an esd read from it would depend on where the solver stopped, and so would the esds of everything correlated with it.
After each solve the fit tests for this with {eq}`est-stationary-angle` ([A moment angle at a direction the symmetry fixes](../theory/estimation.md#a-moment-angle-at-a-direction-the-symmetry-fixes)).
An angle that passes keeps its value, has no esd, and is named by [`MOMENT_ANGLE_STATIONARY`](diagnostics-structures.md#moment_angle_stationary).
`StageResult.moment_angle_tests` holds each round of the test:

| Field | Holds |
|---|---|
| `MomentAngleTest.paths` | the free columns tested together: angles, or a variable of yours that drives only angles |
| `MomentAngleTest.reached` | whether moving them, everything else fixed, drove every column below the floor |
| `MomentAngleTest.statistic` | Δχ² from where the fit stopped to that direction, the other parameters refitted, over χ²<sub>red</sub>·f²; `None` where the direction was not reached |
| `MomentAngleTest.cut` | the 95 % point the statistic is held against: 2.71 for one angle, 4.23 for two, 5.43 for three, 6.50 for four |
| `MomentAngleTest.zeroed` | whether these angles left the covariance |
| `MomentAngleTest.stationary_at` | each angle's value at the direction where its column vanishes, the image nearest the fitted value; empty where the direction was not reached |
| `MomentAngleTest.half_widths` | on a passing round, each angle's distance either side of that direction at which χ², everything else held, rises by χ²<sub>red</sub>·f² |

Such an angle carries its profile interval in place of an esd ([How to quote a parameter that ended on its bound](../guides/interval.md)).
After the last stage, a single-pattern fit runs `Refinement.profile_interval` for each angle the test left out, stepping from its half-width, and stores the answer on the row as `RefinedParameter.interval`.
`MOMENT_ANGLE_STATIONARY` then gives each angle's distance from the direction and says whether the interval includes it.
Where it does, the data cannot tell the moment from one along that direction.
The refits run on a copy of the models, so the history gains no node.
They are the only cost, and only a fit whose test passed pays it: 20-32 refits an angle, 2.6-16.7 s on the two-site test fits of 0.2-1.2 s.
A joint fit computes no interval, and its rows read `None`.

(sec-magnetic-width)=
## Magnetic peak width

A phase's nuclear and magnetic contributions share one scale and one peak shape.
If the observed magnetic reflections are broader than the calculated ones, the fit has one way to lower the residual under them: shrink the moment until the narrow calculated peak's height matches the broad observed peak's.
Since |F<sub>m</sub>|² ∝ m², the moment comes back low by roughly the ratio of the two widths, the fit converges, and no number in the result says what happened.

`Phase.magnetic_lor_size` and `Phase.magnetic_lor_strain` remove that route.
Both are extra Lorentzian FWHM terms applied to the magnetic component alone, following the 1/cos θ and tan θ laws of `Phase.lor_size` and `Phase.lor_strain`.
The magnetic peak is then drawn broader than its nuclear neighbour at the same position, with the same scale and every other correction unchanged, {eq}`int-two-component`.
The size term is Scherrer's with the magnetic coherence length in place of the crystallite size.
Antiphase and domain boundaries, an order parameter not fully grown near T<sub>N</sub>, and disorder that couples to the exchange all cut that length below the structural one.
Both terms default to 0, which is off, and exist only on a phase with `Phase.magnetic_symmetry`.

The moment and the width both lower the calculated magnetic peak's height, so freed together from a cold start they trade against each other.
The `magnetic_width` preset, `RefinementPlan.magnetic_width`, frees them in order: the moment with the widths at zero, then the widths beside the converged moment, then both together as the last stage.
Staging is cumulative, so the moment keeps refining in the middle stage, and enters it at its own converged value.
The preset continues from a converged nuclear fit and frees no cell, coordinate or instrument width.

<!-- api-doc: no-exec — it needs a converged magnetic structure -->
```python
result = ref.fit(data, plan="magnetic_width")
```

A plan that frees a magnetic width in the stage that first frees the moment is reported as [`STAGE_FREES_MAGNETIC_WIDTH_WITH_MOMENT`](diagnostics-refinement.md#stage_frees_magnetic_width_with_moment) before the first stage runs, by `Refinement.fit` and `Refinement.run_stage` alike.

While the terms are held at zero, [`MAGNETIC_WIDTH_UNMODELLED`](diagnostics-structures.md#magnetic_width_unmodelled) says whether they are needed.
It reads the shape of the converged residual, since the package measures no observed width.
A calculated peak too narrow for a broad observed one leaves a residual that is negative at the centre and positive in both tails.
The diagnostic compares that centre-against-tails split at the magnetic-only reflections with the same statistic at the nuclear-only ones.
A wrong instrument profile, a wrong `Phase.lor_size` or a wrong background moves both sets together and cancels, so only a width belonging to the magnetic component survives.

On a synthetic MnF<sub>2</sub> pattern (λ = 2.4 Å) with a planted magnetic size width of 0.22° and a 4.60 μ<sub>B</sub> moment, three noise draws gave these results with the `magnetic_width` preset: widths of 0.211° to 0.224° with esds near 0.011°, and moments of 4.600 to 4.615 μ<sub>B</sub> with esds near 0.033 μ<sub>B</sub>.
With the widths held at zero, the same patterns gave moments of 3.34 to 3.41 μ<sub>B</sub> with esds near 0.13 μ<sub>B</sub>, about nine esds low, and `MAGNETIC_WIDTH_UNMODELLED` fired on all three.
The fixture is `tests/test_magnetic_width.py`.

The terms are identifiable only where the ratio of magnetic to nuclear intensity changes from one reflection to the next.
A k ≠ 0 structure with magnetic-only reflections measures them.
A k = 0 collinear structure, whose magnetic and nuclear intensities track each other, generally cannot, and a paramagnetic pattern has no magnetic component to broaden.
The preset frees both terms, because which one carries an excess is a property of the data, so expect one of them back unmeasured.
[`MAGNETIC_WIDTH_UNMEASURED`](diagnostics-structures.md#magnetic_width_unmeasured) names a freed width below three of its own esds, or one with no esd.

An unmeasured width is not necessarily one you can drop.
The preset fits the moment twice, with the widths at zero in the first stage and with them free in the last.
[`MAGNETIC_WIDTH_MOVED_MOMENT`](diagnostics-refinement.md#magnetic_width_moved_moment) fires when releasing the widths moved the moment by more than the tighter of the two esds.
Beside `MAGNETIC_WIDTH_UNMEASURED` on the same term, it means the width is correlated with the moment rather than absent, and holding it at zero puts the moment back where the first stage had it.
Quote the released moment, and give the width as an upper bound, value plus esd, not as a coherence length.

On the Cr<sub>2</sub>WO<sub>6</sub> tutorial pattern at 4 K, which has magnetic-only intensity on the parent's absences, the preset returned a size term of 0.034 ± 0.024°, 1.4 esds and so unmeasured, and a strain term on its floor at 0 ± 0.059°.
The moment moved from 2.125 ± 0.031 μ<sub>B</sub> with the widths at zero to 2.171 ± 0.035 μ<sub>B</sub> with them free, and `MAGNETIC_WIDTH_MOVED_MOMENT` fired.
On the 150 K pattern, which has no magnetic order, the size term stopped at 0.19° with an esd of 15° and the strain term at 0 with an esd of 45°.

There is no Gaussian partner, because magnetic coherence broadening is Lorentzian in shape.
There is no magnetic position offset either: magnetic peaks in the wrong place need two nuclear phases.

## `solve_magnetic`

`solve_magnetic` starts from a converged nuclear fit, enumerates the magnetic models, refines one per class the powder cannot separate, ranks them by a criterion that is not Rwp, and abstains when the top classes tie.
It is {ref}`provisional by declaration <provisional-by-declaration>`: the chain of steps is settled and the ranking criterion is expected to change.

<!-- api-doc: no-exec — it needs a converged neutron refinement -->
```python
import rietx as rx

ref = rx.Refinement(nuclear, instrument)
ref.fit(data, plan="mccusker_structural")

solution = rx.solve_magnetic(ref, data, sites=["Mn1"], ion="Mn3+")
print(solution)
if solution.verdict == "solved":
    print(solution.best.bns_number, solution.best.moments[0].magnitude)
solution.write_magcifs("candidates/")
```

`print(solution)` prints the ranked table.

| Argument | Default | Sets |
|---|---|---|
| `phase` | 0 | the phase to solve |
| `sites`, `species` | every site whose species is a magnetic form-factor key | the sites that carry a moment, by label or by species |
| `ion`, `g` | the site's species where the form-factor table carries it, else its usual magnetic ion; g = 2 for a 3d or 4d ion and the free-ion g for an assumed 4f or 5f ion | the form-factor key and Landé g, one value or a mapping from label or species; an ion or g it had to assume is reported as [`MAGNETIC_ION_ASSUMED`](diagnostics-structures.md#magnetic_ion_assumed) or [`LANDE_G_ASSUMED`](diagnostics-structures.md#lande_g_assumed) |
| `k` | chosen from the satellite evidence | the propagation vector, when a single crystal has given it |
| `top_k`, `k_trials`, `k_tie_width` | 3, 2, 10.0 | how many ranked k to carry, how many to refine in full, and the ΔBIC gap below which two k are not separated |
| `d_min` | 1.5 Å | the d limit the equivalence classes are a statement about |
| `magnitude` | 2.0 μ<sub>B</sub> | the seed modulus |
| `plan` | three stages, `moduli`, `moment` and `all` (`rietx.strategy.magnetic.SOLVE_STAGE_NAMES`) | the stages for every trial and the nuclear reference; they must differ only by the moment paths |
| `tie_width` | 6.0 | the ΔBIC gap below which two classes are tied |
| `generator` | `zone_boundary_candidates` | the candidate k set |
| `nuclear_group` | `"parent"` | the group a k ≠ 0 supercell's atom positions refine under |
| `tie_to_parent` | `False` | hold a k ≠ 0 trial's cell at the parent's and tie together the child Biso of one parent atom, in the trial and its reference, reported as [`SOLVE_B_TIED_PER_PARENT_SITE`](diagnostics-structures.md#solve_b_tied_per_parent_site) |
| `cif_dir` | `None` | a directory to write one magCIF per refined class into |

### Steps

1. The propagation vector. The satellite evidence sorts the positive residual peaks of the nuclear fit. Peaks on a lattice point the nuclear structure factor forbids are the k = 0 signature and are never scored against a candidate. Otherwise the unexplained peaks are scored against the candidate set, the top vectors are taken, and the rest are kept in `MagneticSolution.k_candidates`. `MagneticSolution.k_route` records the route.
2. The candidates. For each named site, every order-parameter direction of every small irreducible representation with a non-zero multiplicity, each as a magnetic space group in its own cell. A k ≠ 0 candidate is stated in its magnetic supercell, with the anti-centring applied as a constraint on the moment parameters. `MagneticTrial.anti_translation_drift` measures how far the refined structure left its group, and should read zero.
3. One trial refinement per powder-equivalence class. The members of a class are models this pattern cannot tell apart to `MagneticSolution.d_min`. Refining each would give N copies of one answer, so they are named in `MagneticTrial.members` instead, and that they cannot be separated is the finding.
4. The ranking, given in `MagneticSolution.criterion`.

A candidate with more free amplitudes always reaches a lower Rwp, so ordering by Rwp orders by freedom.
The ranking is `MagneticTrial.delta_bic` against a nuclear reference refined under the same stages minus the moment paths, so the two models differ only by the moment block and the added parameters are exactly `MagneticTrial.n_moment_parameters`.
The −n<sub>added</sub>·ln N term of ΔBIC charges every extra amplitude {cite}`schwarz1978`, so a nested set of groups reaching one profile ranks smallest group first.
ΔBIC charges N/f² observations in place of the N fitted channels, as `compare_freed` does, with f the Bérar-Lelann factor of the nuclear reference's fit.
Neighbouring channels of one peak share the sign of their misfit, so at the raw count any χ² gain outvotes the parameter penalty.
Before 1.10 the count was N.
On the Cr<sub>2</sub>WO<sub>6</sub> 4 K tutorial pattern f is 3.38, so ΔBIC charges 153 of the 1749 channels, and the winner's lead over the next class falls from 1682 to 143, still far past the tie width.
`MagneticTrial.r_magnetic` is a profile R over the channels the nuclear model puts nothing on, where 1 means it explains none of the intensity there and 0 all of it.
It is reported and ranks nothing.
A supported moment is a condition for winning.
A trial whose every moment fails the support test cannot win whatever its ΔBIC, and neither can one whose ΔBIC is not positive.
When no trial passes both, the verdict is `"nothing to solve"`.

Classes whose ΔBIC lies within `MagneticSolution.tie_width` of the leader's are tied on ΔBIC.
A tie is an abstention: `MagneticSolution.tied` names the classes, the verdict is `"abstained"`, and the reason gives each tied class's moment-parameter count and magnetic-only R.
The tied classes come first in `MagneticSolution.trials`, fewest moment parameters first, the order of the convention that reports the highest symmetry the data allow.
Neither the count nor the R ranks them, because ΔBIC already charges each parameter.
Before 1.10 a gap in the magnetic-only R of more than 2 %, and then a smaller parameter count, broke a tie and gave `"solved"`.
The 2 % margin was never measured.
The default width, 6.0, is "strong" on the scale of Kass and Raftery (1995).
A cubic collinear structure gives another abstention: one class, a well-measured modulus and a direction the powder cannot determine, reported in `MomentRow.unmeasured_directions`.

A moment stage over several sites is not convex, and an equal-magnitude start can land in a minimum that is provably not the best, a three-amplitude fit with a worse Rwp than the one-amplitude model it contains.
Compared at such points, the ranking would measure the start.
So every class with more than one magnetic site is refined from each one-site start, the other sites' moments absent, then released, and the best converged minimum is reported.
`MagneticTrial.n_starts`, `MagneticTrial.n_minima` and `MagneticTrial.start` show that sweep, and a multimodal class says so in `MagneticSolution.caveats`.
Every start frees the moduli before the directions.
A small moment's direction barely moves the pattern, and the default driver scales every column to the same size, so with both free it took its largest steps along the direction and stopped far from the minimum.

A stage pattern that frees nothing makes the compared models differ from the ones the plan describes, so `solve_magnetic` puts any such pattern in the caveats.
A trial fit or nuclear reference that stops on its iteration budget is continued up to ten times, and one still short is listed and not ranked.

Without a `plan`, the trials and the nuclear reference run no closing stage, so the ranking compares every χ² at the declared stages' windows.
The winner then runs one closing stage from its own fit.
Its moments and their esds, Rwp, GoF and magnetic-only R come from that stage, and a caveat says so.
Its ΔBIC stays the ranking's.
On a synthetic two-site orthorhombic pattern the larger modulus's esd falls from 0.00242 to 0.00151 μ<sub>B</sub>, because the declared windows drop the peak tails.
A `plan` you pass keeps its own `closing_window_tol` for every fit, the winner's included.

`solve_magnetic` refuses a pattern that is not constant-wavelength neutron, a refinement that has not fitted, a phase that already declares a magnetic space group, and a phase that declares a propagation vector.
Everything else, such as no unexplained intensity or a tie at the top, is reported.

The nuclear model it starts from is the one in the refinement you hand it, fitted without a moment.
[How to refit the nuclear model with the moment present](../guides/moment.md) gives two ways to start from a better one.

### The solution

`solve_magnetic` returns a `MagneticSolution`, whose fields are these.

| Field | Is | Reads as |
|---|---|---|
| `MagneticSolution.verdict` | `"solved"`, `"abstained"` or `"nothing to solve"` | the third is an answer about the specimen |
| `MagneticSolution.reason` | why, in a sentence | never empty |
| `MagneticSolution.criterion` | the ranking rule, stated | the same string every run |
| `MagneticSolution.best` | the winning `MagneticTrial`, or `None` | `None` for every verdict but `"solved"` |
| `MagneticSolution.margin` | the winner's ΔBIC over the best other eligible class | `None` with no winner or no second eligible class; above the tie width otherwise |
| `MagneticSolution.phase`, `MagneticSolution.space_group` | the phase solved | |
| `MagneticSolution.sites` | the sites given a moment | |
| `MagneticSolution.k` | the propagation vector used, as three rationals | `None` when the run stopped before choosing one |
| `MagneticSolution.k_route` | how it was chosen | `"forbidden lattice points"`, `"satellite ranking"` or `"given by the caller"`; `"nothing to solve"`, `"no candidate k"` or `"no satellite arm"` when none was |
| `MagneticSolution.k_reason` | why that k, in a sentence | separate from `reason`, which is the verdict's |
| `MagneticSolution.k_candidates` | the ranked vectors, as (spelling, matched, satellites in range) | empty when the satellite step did not run |
| `MagneticSolution.k_trials` | one `KTrialSummary` per vector refined in full | one row unless a runner-up indexed as many peaks within 0.5° of the winner's worst offset |
| `MagneticSolution.n_residual_peaks` | positive residual peaks of the nuclear fit | before the sort |
| `MagneticSolution.n_on_nuclear_lines` | those on a calculated reflection | not scored |
| `MagneticSolution.n_on_forbidden_lattice_points` | those at a systematic absence | the k = 0 signature |
| `MagneticSolution.n_unexplained` | those at neither | the only ones a k is needed for |
| `MagneticSolution.trials` | one `MagneticTrial` per class: the eligible ones best first, then the rest | refusals and unsupported models included |
| `MagneticSolution.tied` | the class indices inside the tie width | one entry when the verdict is `"solved"` |
| `MagneticSolution.tie_width` | the ΔBIC below which two classes are tied | |
| `MagneticSolution.d_min` | the d limit the classes are a statement about | |
| `MagneticSolution.nuclear_rwp`, `MagneticSolution.nuclear_gof` | the reference fit's agreement | |
| `MagneticSolution.nuclear_r_magnetic` | the reference's own magnetic-only R | near 1 on a nuclear model that explains none of it; the scale every `MagneticTrial.r_magnetic` is read against |
| `MagneticSolution.n_magnetic_channels` | channels in that region | zero makes `r_magnetic` `None` |
| `MagneticSolution.caveats` | what the run wants you to know, as sentences | includes the N/f² count ΔBIC charged, with N and f |
| `MagneticSolution.diagnostics` | structured diagnostics | [`K_VECTOR_UNSEPARATED`](diagnostics-structures.md#k_vector_unseparated), [`MAGNETIC_SUBGROUP_PREFERRED`](diagnostics-structures.md#magnetic_subgroup_preferred) and the assumed ion and g among them |
| `MagneticSolution.subgroup_audit` | the winner's maximal magnetic subgroups at its k, each refitted from the winner's solution, one `SubgroupAudit` each | empty when k ≠ 0, or when no class already enumerated is a subgroup |
| `MagneticSolution.subgroup_note` | which subgroup beat the winner and by how much, that none did, or why the audit was not run | set on every solved verdict |
| `MagneticSolution.write_magcifs` | writes one magCIF per refined class and returns the paths | nothing is written unless you call it or pass `cif_dir=` |

| Field | Is |
|---|---|
| `KTrialSummary.k` | the propagation vector, as three rationals |
| `KTrialSummary.matched`, `KTrialSummary.worst_offset_deg` | the satellite step's score for this k; `None` on a route with no scoring |
| `KTrialSummary.best_delta_bic` | the best eligible class's ΔBIC for this k, or `None` |
| `KTrialSummary.n_refined` | how many of this k's classes refined |
| `SubgroupAudit.bns_number`, `SubgroupAudit.label` | which subgroup |
| `SubgroupAudit.n_moment_parameters` | its moment parameter count, more than the winner's |
| `SubgroupAudit.delta_bic_over_winner` | ΔBIC with the winner as the restricted model; positive favours the subgroup, `None` when it refused |
| `SubgroupAudit.status`, `SubgroupAudit.refusal` | `"refined"` or `"refused"`, and why |

### Trials

| Field | Is | Reads as |
|---|---|---|
| `MagneticTrial.class_index` | the powder-equivalence class | stable within one run |
| `MagneticTrial.label` | what the table prints | the BNS number with the irreducible representation and direction |
| `MagneticTrial.representative` | the representation and direction refined | the smallest family of the class |
| `MagneticTrial.members` | every candidate in the class | more than one is the finding |
| `MagneticTrial.site` | the site whose representation produced it | |
| `MagneticTrial.irrep`, `MagneticTrial.direction` | the labels, such as `S2` and `(a)` | |
| `MagneticTrial.bns_number`, `MagneticTrial.uni_number`, `MagneticTrial.msg_type` | what spglib recognised the operator list as | `"unidentified"` and `None` are answers, not errors |
| `MagneticTrial.free_amplitudes` | the representative site's amplitudes before any data | per site; `n_moment_parameters` counts them |
| `MagneticTrial.determinable_amplitudes` | how many of them a powder to `d_min` can determine | the deficit is the flat directions; `None` on a refused trial |
| `MagneticTrial.status`, `MagneticTrial.refusal` | `"refined"` or `"refused"`, and why | a refusal such as a magnetic orbit that cannot cover the nuclear one |
| `MagneticTrial.fit_status`, `MagneticTrial.reference_status` | the trial fit's status and its nuclear reference's, after the continuations | anything but `"converged"` lists the trial and leaves it out of the ranking |
| `MagneticTrial.stopped_short` | which of the two stopped short, in words | `None` when both converged |
| `MagneticTrial.rwp`, `MagneticTrial.gof` | the trial's own agreement | context, never the ranking key |
| `MagneticTrial.delta_bic` | the ranking quantity | positive favours the magnetic model |
| `MagneticTrial.r_magnetic` | the magnetic-only R | read against `MagneticSolution.nuclear_r_magnetic` |
| `MagneticTrial.n_moment_parameters`, `MagneticTrial.n_free_parameters` | the moment parameters left free, and the whole free count | `None` on a refused trial |
| `MagneticTrial.moments` | one `MomentRow` per site with a moment | |
| `MagneticTrial.held` | the parameters the stage held | a direction here was not measured |
| `MagneticTrial.supported` | whether any site's moment, or any degenerate pair's quadrature sum, passed the support test | false disqualifies the trial |
| `MagneticTrial.anti_translation_drift` | how far a supercell refinement left its own group, μ<sub>B</sub> | zero is the pass; `None` for k = 0 |
| `MagneticTrial.n_starts` | the starts the moment stage ran from | one per magnetic site plus the equal-magnitude one; 1 for a single site |
| `MagneticTrial.n_minima` | distinct minima those starts found | more than one means one start would have reported another answer |
| `MagneticTrial.start` | which start won | `"flat"` or `"<site> only, then released"` |
| `MomentRow.label`, `MomentRow.ion` | the site and its form-factor key | |
| `MomentRow.magnitude`, `MomentRow.esd` | \|m\| in μ<sub>B</sub> and the modulus's esd | the components carry none |
| `MomentRow.sigma` | \|m\| over its own esd | `None` without an esd |
| `MomentRow.crystalaxis` | the three components | |
| `MomentRow.supported` | the support test for this site | |
| `MomentRow.unmeasured_directions` | directions the powder average did not determine | a result about the measurement |
| `MomentRow.paired_with` | the other site this modulus is powder-degenerate with | |
| `MomentRow.paired_magnitude`, `MomentRow.paired_magnitude_esd` | the pair's quadrature sum and its esd | the number the powder measures for the pair; `None` without a pair |
| `MomentRow.pair_supported` | the support test on the quadrature sum | each modulus of a degenerate pair fails alone, its esd being the length of the flat direction, so the gate reads this; false for an ordinary row |
