# Structure files

This page gives what `Structure.from_cif` reads from a CIF or a magnetic CIF, what it repairs, reports and refuses, what `Structure.to_cif` writes back for a magnetic phase, and how a magnetic phase crosses to and from a TOPAS `.inp` and a FullProf `.pcr`.

[Patterns and structures](data.md#structure) gives the fields of the `Structure` a reader returns.
[Diagnostics: structures and magnetism](diagnostics-structures.md) gives every structure code this page names, and [Diagnostics: other programs' files](diagnostics-projects.md) the TOPAS and FullProf ones.
[How to read another program's files](../guides/foreign.md) covers the rest of a TOPAS or FullProf file.

## Reading a CIF

`Structure.from_cif` reads a CIF into a `Structure` with one phase.

```python
import rietx as rx
from rietx.examples import examples_dir

notes = []
structure = rx.Structure.from_cif(examples_dir() / "fluorapatite.cif",
                                  diagnostics=notes)
phase = structure.phases[0]
print(phase.name, phase.space_group, len(phase.atoms))
print([note.code for note in notes])
```

```text
fluorapatite P 63/m 7
['SITE_SNAPPED_TO_SPECIAL_POSITION']
```

The bundled file writes Ca1 at (0.3333333333, 0.6666666667, z), 3.3 × 10⁻¹¹ from the special position (1/3, 2/3, z), so the reader reports that it expanded the site there.

| Argument | Default | Meaning |
|---|---|---|
| `phase_name` | `None` | the `Phase.name`; without it, the CIF block's name, else `phase_1` |
| `aniso` | `False` | keep an `_atom_site_aniso_U_ij` loop as `Atom.aniso` |
| `moment_ions` | `None` | per moment label, the ion whose form factor the moment scatters with |
| `moment_g` | `None` | per moment label, the Landé g |
| `nuclear_group` | `"auto"` | which group a magnetic CIF's atom positions refine under: `"auto"`, `"file"` or `"parent"` |
| `diagnostics` | `None` | a list that collects each repair and report |

The reader takes a file with one data block.
A file holding several is refused, so split a multi-phase CIF into one file per phase.

It reads the cell, the space group, and each site's label, species, coordinates, occupancy and displacement parameter.
The space group comes back as the extended Hermann-Mauguin symbol gemmi resolves, which names its setting (`F d -3 m:1`).
A U is converted to B = 8π²U.
A site with no isotropic column takes the equivalent isotropic U of its anisotropic tensor, else 0.5 Å².
A missing occupancy is 1.
A stated B or occupancy of 0 is read as 0, and a null `.` or `?` is not a statement.

`aniso=True` keeps the anisotropic tensor, and without it the tensor gives the isotropic value.
It is off by default because several CIFs carry an anisotropic loop, and reading a file must not change which parameters a plan frees.
The disorder assembly and group columns are read into `Atom.disorder_assembly` and `Atom.disorder_group`.
A bracketed space-group label beside an operation loop is read back as `Phase.symmetry_operations` ([Symmetry operations](data.md#symmetry-operations)).

## Repairs and reports

A reader repairs a stranger's file only where it can say that it did, and each repair below comes back on the `diagnostics=` list.

A species label that is not a recognised scatterer is rewritten, such as `O1` in the type-symbol field or a charge written before its digit (`O-2`), and reported as [`CIF_SPECIES_NORMALISED`](diagnostics-structures.md#cif_species_normalised).

A cell angle that differs from its space group's fixed value by a small amount is set to that value, and reported as [`CIF_CELL_ANGLE_CORRECTED`](diagnostics-structures.md#cif_cell_angle_corrected).
A β of 90.002(3) under `P m m m` is an experimenter quoting a refined number.
Past `rietx.crystallography.cif.CIF_ANGLE_CORRECT_MAX_DEG` the symbol and the angle contradict each other, and one of the two is wrong.
Choosing between them is yours, so the value is left byte for byte and the read raises.

A Biso of any value is kept as the file states it, because `Atom.biso` has no default bound.
Published structures carry values a range would refuse.
The methylammonium C in COD 4335638 sits at 26.8 Å², and a light atom is sometimes refined slightly negative.
Refine such a value, or set a physical start before a stage holds it.
A fit that keeps a negative B reports [`BISO_NEGATIVE`](diagnostics-refinement.md#biso_negative).

A site within 1e-4 of a special position, as a file quoting five decimals often leaves one, has its orbit expanded at that position.
The 1e-4 bounds each operation's displacement R·x + t − x, so on a mirror, which moves the site by twice its offset, the reach is 5e-5.
Its multiplicity is the special one, and [`SITE_SNAPPED_TO_SPECIAL_POSITION`](diagnostics-structures.md#site_snapped_to_special_position) names the site, the shift and the multiplicity.
The stored coordinates are unchanged and the fit is unaffected, with one exception.
Where the file states the multiplicity (`_atom_site_symmetry_multiplicity`, or the number in `_atom_site_Wyckoff_symbol`) and the site is within 1e-3 of the position that multiplicity names, the reader moves the site onto it.
The forward model would otherwise put twice the atoms in the cell, and the same code names the move.
A stated multiplicity the site cannot reach, or one larger than the coordinates give, moves nothing and reports [`CIF_SITE_MULTIPLICITY_DISAGREES`](diagnostics-structures.md#cif_site_multiplicity_disagrees).

The multiplicity decides how many atoms a site puts in the cell, so it sets the ZMV and every weight fraction.
Compare it against the file's own `_atom_site_symmetry_multiplicity`.

Two more repairs guard the same count.
A site within 5e-4 (fractional, per coordinate) of a special position, further off than a snap reaches, may be one atom counted twice, so it is moved onto the special position they collapse to, at every boundary that can say so, where the site as stored would put more than one atom at one place.
The gate is the same at every boundary, readers included: the occupancy at the position, summed over the atoms sharing it and each × (images before / images after), must be above 1.
A CIF read says a merge with [`CIF_SITE_TWINS_MERGED`](diagnostics-structures.md#cif_site_twins_merged); the project readers' `to_structure` say `SITE_TWINS_MERGED` on their own `diagnostics=`; `RefinementTree.load` and `Refinement` construction, `edit`, `set_values` and `checkout` say it on `RefinementTree.load`'s `diagnostics=` or on the next `fit` or `run_stage` result.
Where the product is 1 or below, the stated numbers read both as one atom off its position and as a split pair of part-atoms, so the site is left as stored and `SITE_TWINS_KEPT` gives both readings and the occupancy each implies.
A hold, user tie or free path on a coordinate degree of freedom follows its direction when a site gains symmetry, on every route that moves the site (a fit's write-back, `set_values`, `edit`, a branch, a stored history); one on a direction the position fixes or couples is dropped, and `SITE_TWINS_MERGED` or `SITE_DOFS_RENUMBERED` names it.
A merged site's coordinates that the position fixes lose `vary`, and an anisotropic tensor is projected onto the tensors the position allows, so the merged model still builds its table.
`Phase` itself stays strict: a phase built in code with a twin site is held as stated until it enters one of those.
The merge keeps the occupancy, so the site's atoms per cell change with its multiplicity, and each message gives both counts (multiplicity × occupancy).
For one atom stated off its position that is the repair.
A part-occupied split pair that a fit left within 5e-4 of the position loses content instead (issue #1088), so on such a site the message says so and the suggestion gives the occupancy that keeps it.
A split site, further than that from every special position, is left as stated.
The occupancy test sums over every atom sharing the position, so Fe 0.5 and Mn 0.5 on one site merge together.
A hold or user tie on a coordinate degree of freedom (`…dof.k`) follows its direction when the site gains symmetry, or is dropped and named in the message where the position fixes that direction.
Two sites of one species on one orbit with identical properties are one site listed twice, and the second is dropped, [`CIF_SITE_LISTED_TWICE`](diagnostics-structures.md#cif_site_listed_twice).
A pair that differs in any property is refused.

## Space-group settings

A bare Hermann-Mauguin symbol resolves to the first setting the tables hold, and 40 symbols hold more than one: the `:1`/`:2` origin choices and the rhombohedral `:H`/`:R` axes.
Site multiplicities differ between settings.
Spinel's origin-2 coordinates under a bare `F d -3 m` build Mg₂AlO₄ where MgAl₂O₄ was meant, with Rwp unmoved.
[`SPACE_GROUP_SETTING_ASSUMED`](diagnostics-structures.md#space_group_setting_assumed) quotes the cell contents each setting implies, so you can recognise the one you meant.
Naming the setting silences it:

```python
import rietx as rx

P = rx.Parameter
spinel = rx.Phase(
    name="spinel",
    space_group="F d -3 m:2",          # the setting, and not the bare symbol
    cell=rx.Cell.cubic(8.0806),
    atoms=[
        rx.Atom(label="Mg", species="Mg", x=P(value=0.125),
                y=P(value=0.125), z=P(value=0.125)),
        rx.Atom(label="Al", species="Al", x=P(value=0.5),
                y=P(value=0.5), z=P(value=0.5)),
        rx.Atom(label="O", species="O", x=P(value=0.2624),
                y=P(value=0.2624), z=P(value=0.2624)),
    ],
)
```

A fit raises it for a phase built by hand.
A phase read from a CIF carries the extended symbol gemmi resolved, so a fit does not raise it.
A TOPAS `.inp` and a GSAS `.EXP` state a symbol and nothing else, so their readers raise it when they read the file.
A GSAS-II `.gpx` states its operators, and its reader takes the setting they match.
A phase carrying its own operation list never raises it.

## Magnetic CIF

A magnetic structure usually arrives as a magCIF, which MAGNDATA, ISODISTORT, k-SUBGROUPSMAG and the Bilbao tools emit.
`Structure.from_cif` reads one into the model rietx stores:

- the operator list with its time-reversal signs, on `Phase.magnetic_symmetry`;
- the moments in crystal-axis components, in μ<sub>B</sub>, on `Atom.moment` of the sites they name;
- the BNS and OG numbers and the BNS symbol, as metadata.

<!-- api-doc: no-exec — it reads a magCIF the reader supplies -->
```python
notes = []
structure = rx.Structure.from_cif("0.642.mcif", moment_ions={"Mn1": "Mn3+"},
                                  diagnostics=notes)
phase = structure.phases[0]
print(phase.space_group, phase.magnetic_symmetry.bns_number)
print(phase.atoms[1].moment.values(), phase.atoms[1].moment.ion)
```

### Nuclear group

A magCIF usually states no ordinary space group, since the magnetic block replaces it.
The nuclear group's type then comes from `_parent_space_group.name_H-M_alt`.
The IUCr underscore spelling of a screw axis (`P 2_1/c`) is normalised to the one gemmi's tables accept (`P 21/c`), and every message keeps the file's own spelling.
A file that also states an ordinary `_space_group_name_H-M_alt`, as an ISODISTORT export can, takes that group as stated, and `nuclear_group=` has no effect.

The symbol names the type, and its setting is checked against the file's own magnetic operators with time reversal dropped.
gemmi's tabulated operators for a symbol can sit at another origin or axis choice than a non-standard setting's own, as measured on Ima2 (space group 46).
A symbol lookup alone would attach the wrong coordinate frame to a right-looking name.
The moments always refine under the file's magnetic group, and `nuclear_group=` chooses the group the atom positions refine under:

`"auto"`
: The highest tabulated group the file's atoms satisfy. That is the parent where it contains the file's operators and gives every listed site the same number of images, reported as [`CIF_MAGNETIC_NUCLEAR_GROUP`](diagnostics-structures.md#cif_magnetic_nuclear_group). Cr₂WO₆ reads this way, with `Pn'nm` moments in `P4₂/mnm` positions. Otherwise it is the tabulated setting whose operations are exactly the file's own, reported as [`CIF_MAGNETIC_NUCLEAR_SETTING`](diagnostics-structures.md#cif_magnetic_nuclear_setting) with the reason.

`"file"`
: The file's own group, the operators with time reversal dropped. Where those equal the parent's, the result is the parent.

`"parent"`
: The parent, refused by name where it cannot carry the file's atoms.

`"auto"` covers a symbol tabulated at another origin, and a symmetry-lowering magnetic group whose asymmetric unit lists one parent orbit as two sites.
Under the parent those two sites would be one orbit counted twice.

A file whose own group is in a setting no tabulated symbol names is read with that group as its operation list.
`Phase.symmetry_operations` holds the operations with time reversal dropped, in the file's order.
`Phase.space_group` holds a bracketed label naming the closest type, such as `'P -1 [unnamed in this cell]'`, and `CIF_MAGNETIC_NUCLEAR_SETTING` says so.
Every symmetry consumer reads the list and never the label, and `Structure.to_cif` writes the list back.
A writer whose format states a group only as a symbol refuses such a phase by name.

A group whose rotations are in no tabulated orientation, such as a two-fold axis along a face diagonal, is refused by name.
An operation list takes its crystal system and cell ties from the tabulated group with the same rotations, and there is none.
A file whose space group cannot be resolved at all, from an ordinary tag or a parent symbol, is refused by name.

### What a magCIF read refuses

A modulated structure is refused by name, because reading only its amplitude at k = 0 would return a collinear structure for a modulated one.
That covers a moment, displacement, occupancy or rotation stated as Fourier amplitudes or a special function, a cell or site wave vector, a superspace group, and a moment row flagged as modulated.

A structure stated in a supercell of its parent is refused by name.
This is the generic commensurate k ≠ 0 record.
The asymmetric unit of the magnetic group in that cell splits one nuclear orbit into several sites with different moments, and the model stores one moment per nuclear site.
The test is the child transform's determinant and the parent k.
Every component of k is reduced modulo 1 first, so an all-integer k such as (1, 1, 1) is Γ and reads as k = 0.
The parent k is read for this test alone, and is not stored or written back.
A `_parent_space_group.transform_Pp_abc` that is not the identity records which setting the symbol was tabulated in, as every non-standard-setting MAGNDATA entry does, and is not a reason to refuse.
Two moment rows for one site label are refused too, since that is a supercell stated in the parent cell.

Both refusals name what would be needed.
`rietx.crystallography.magnetic.supercell.magnetic_supercell` builds a supercell phase from its parent instead.

Also refused: moments with no magnetic operator loop, a moment row whose label is not an `_atom_site_label`, and a moment row that states no form.

### Magnetic symmetry

The operator and centring loops are stored as written.
A file with no centring loop is read as having none, and [`CIF_MAGNETIC_CENTERING_ASSUMED`](diagnostics-structures.md#cif_magnetic_centering_assumed) says so, because a forgotten anti-centring makes the operators a smaller group.

`transform_BNS_Pp_abc` is not applied.
A published structure is usually written in its own setting rather than the BNS standard one, and that setting is the one its cell and coordinates are in.
Cr₂WO₆'s record carries `'b,-a,c;0,0,0'`.
So the list is kept as written, and the transform goes into `MagneticSymmetry.setting` as a record.
Applying it would move the group away from the atoms beside it.

`MagneticSymmetry.uni_number` is derived from the operators through spglib, so it is the same on both sides of a round trip.
Where no tabulated magnetic group matches, it is `None`, with [`CIF_MAGNETIC_UNIDENTIFIED`](diagnostics-structures.md#cif_magnetic_unidentified).
A stated `number_BNS` or `number_OG` is checked against the same identification.
A number labels the group's type in every setting, so one the operators are not is a contradiction.
The operators are what is refined, so their numbers are stored, the stated `name_BNS` is dropped, and [`CIF_MAGNETIC_NUMBER_MISMATCH`](diagnostics-structures.md#cif_magnetic_number_mismatch) names both.
The reader cannot tell which side is wrong: a forgotten anti-centring makes the operators a smaller group while the number stays right.

A file's `_atom_site_moment.symmform`, the constraint its producer applied to each moment, is kept for reference and compared with the allowed directions the operators give, [`CIF_MAGNETIC_SYMMFORM`](diagnostics-structures.md#cif_magnetic_symmform).
Four tags are read and deliberately not used: `_space_group_magn.name_OG`, `_parent_space_group.IT_number`, `_parent_space_group.transform_Pp_abc` and `_atom_site_moment.refinement_flags_magnetic`.
The last is the producer's plan, and what a rietx fit frees is set by its stages.

### Magnetic ion and Landé g

The magnetic ion is not in the file.
The magnetic dictionary has no item for it, and MAGNDATA writes a bare `Mn` for a site that is chemically Mn³⁺.
Without `moment_ions=`, the neutral atom's ⟨j<sub>0</sub>⟩ is used and [`CIF_MAGNETIC_ION_UNCHARGED`](diagnostics-structures.md#cif_magnetic_ion_uncharged) says so.
The two curves differ, and a moment refined under the wrong one absorbs the difference into its size.

A bare lanthanide or actinide symbol has no neutral-atom row.
There the reader takes the element's majority oxidation state that is magnetic, and reports [`MAGNETIC_ION_ASSUMED`](diagnostics-structures.md#magnetic_ion_assumed):

| Element | Ion assumed |
|---|---|
| Ce, Pr, Nd, Sm, Gd, Tb, Dy, Ho, Er, Tm, Yb | the 3+ ion |
| Eu | Eu²⁺ |
| U, Np | the 4+ ion |
| Pu | Pu³⁺ |

A bare symbol of any other lanthanide or actinide is refused.

`moment_g=` states the Landé g a 4f or 5f moment needs.
Where the ion was assumed, its free-ion Hund's-rule g<sub>J</sub> is assumed too, and [`LANDE_G_ASSUMED`](diagnostics-structures.md#lande_g_assumed) reports it.
A magCIF has no item for g any more than for the ion.
An ion you state with `moment_ions=` still needs its `moment_g=`, and a 4f or 5f ion without one is refused when the phase is built.

Both arguments are keyed by `_atom_site_moment.label`.
A key that names no row of that loop is refused with the labels the file carries, since a misspelled label would leave its site on the default with nothing said.
A file rietx wrote carries the ion and g in its own `_rietx_atom_site_moment` loop, and the reader takes them from there.
`moment_ions=` and `moment_g=` override that loop.

### Moment forms and esds

The dictionary defines the moment in crystal axes, in spherical coordinates and in Cartesian ones, and all three forms are read.
Both the dotted and the flat spellings of the tags are read.
Where a row states more than one form, the moment is taken from the crystal-axis form first, then the spherical, then the Cartesian, and the forms must agree within 0.02 μ<sub>B</sub> per component.
The spherical and Cartesian frames have x ∥ a and z ∥ c\*, the frame the ADP code uses.

A stated `_atom_site_moment.magnitude` is checked against the components under the metric the dictionary defines: |m| = √(mᵀ·G·m).
The plain √(Σmᵢ²) is 29 % out on hexagonal axes and is the commonest way that line goes wrong.
The check compares the magnitude's absolute value, since a negative stated magnitude is a sign convention.
Its tolerance comes from the file's own precision: an inline uncertainty, then `magnitude_su`, then half the last printed digit.
For a crystal-axis row the tolerance is widened by each component's own imprecision, propagated through the metric.
A magnitude rounded to fewer figures than the components is read.

A component written `?` or `.` beside numbers in the same form is refused, naming the site and the item.
In CIF, `?` means unknown and `.` inapplicable, the dictionary gives a moment component no default, and reading either as 0 μ<sub>B</sub> would state a moment the file did not.
A form whose cells in a row are all `?` or `.` is one that row does not use, and the next form is read.

A moment printed with fewer decimals than its symmetry relation needs can sit slightly off the form the site allows.
Within half a unit of the last printed digit, capped at 0.02 μ<sub>B</sub>, it is moved onto the allowed form, [`CIF_MAGNETIC_MOMENT_ON_ALLOWED`](diagnostics-structures.md#cif_magnetic_moment_on_allowed).
A larger disagreement is refused.

Standard uncertainties follow the form the moment is taken from.
A crystal-axis row keeps its own.
A Cartesian row's go through the conversion, which is linear, assuming no correlation between components since a CIF row states none.
A spherical row's are not propagated, because that conversion is nonlinear and singular on the pole.
[`CIF_MAGNETIC_SPHERICAL_ESD_NOT_STORED`](diagnostics-structures.md#cif_magnetic_spherical_esd_not_stored) names each uncertainty dropped, so a component's `stderr=None` there does not mean "not refined".
A stated `magnitude_su` has no field on the structure and is reported as [`CIF_MAGNETIC_MAGNITUDE_ESD_NOT_STORED`](diagnostics-structures.md#cif_magnetic_magnitude_esd_not_stored).

### Writing a magCIF

`Structure.to_cif` and `Refinement.write_cif` write the same form back.
The operator and centring loops go out as stored, with the BNS and OG metadata.
A `MagneticSymmetry` whose BNS, OG or UNI number is not its operators' is refused by name.
The nuclear group goes out as an ordinary `_space_group_name_H-M_alt` with its operation loop, so a rietx-written magCIF reads back through the ordinary path.

The moments go out in crystal-axis components with the dictionary's own `_su` items beside them, and `.` where there is no esd.
Every other number in the file uses the `value(su)` notation.
A refined moment's esd is routinely 0.05-0.9 μ<sub>B</sub>, and an uncertainty given to two significant figures would quote the value to one decimal, so the number you refined would not come back.

The form-factor ion and the Landé g have no magnetic-dictionary tag.
They go out in a `_rietx_atom_site_moment` loop with `label`, `ion` and `g` items, and without it a round trip would lose which form factor the refinement used.
The `magnitude_su` column is written on every row.
A refinement CIF fills it with the esd of the moment's modulus, where a moment's uncertainty lives.
`Structure.to_cif` writes `.` there.

`_space_group_magn.transform_BNS_Pp_abc` is written only when `MagneticSymmetry.setting` is a transform in the dictionary's form, the (P,p) from the current setting to the BNS one, and is left out otherwise.
A group built from its number is in the BNS standard setting, so its `setting` is `'a,b,c;0,0,0'`.
A `magnetic_supercell` phase has none: the parent-to-child transform it knows is a different map, and it stays on the statement and in the phase name.
The parent k is not written, so a supercell phase goes out as k = 0 in its own cell.

## Magnetic phases in a TOPAS input file

A TOPAS `.inp` states a magnetic phase as `mag_space_group` on a `str`, with `mlx mly mlz` and optionally `mg` on each magnetic `site`.
`rx.read_topas_inp` parses the file, and `rietx.io.projects.topas.to_structure` builds the phases.

### Reading a magnetic phase

TOPAS's magnetic examples, and ISODISTORT's TOPAS export, often state no nuclear `space_group`.
The build then takes the nuclear group from the magnetic one: its operators with time reversal dropped, by the `"auto"` rule a magCIF read uses.
TOPAS itself generates the atoms from those operators.

A `mag_space_group` written as a BNS number (`62.448`, `1.1`) or an OG number (three integers) is used as the group.
It resolves to the operators of that number's standard setting, reported as [`TOPAS_MAGNETIC_GROUP_READ`](diagnostics-projects.md#topas_magnetic_group_read).
A Shubnikov symbol is kept as metadata alone, because nothing here parses one.
The build refuses a phase that states moments under a symbol until you pass `to_structure(model, magnetic_symmetry=...)`.
That argument takes a number as a string, a `MagneticSymmetry`, an operator mapping, or a mapping from phase name to any of those.
A bare value is accepted only where one phase states moments, and a value you pass outranks the file's number.

`mlx mly mlz` are components in the fractional basis, `m = mlx·a + mly·b + mlz·c`, with the edges in Å.
The stored crystal-axis moment is therefore (mlx·|a|, mly·|b|, mlz·|c|), a scale per axis and never a rotation.
An unstated component is 0, and the moment is free if any of the three is refined.
[`TOPAS_MOMENT_CONVENTION`](diagnostics-projects.md#topas_moment_convention) reports the reading on every magnetic phase.
It is the TOPAS 6 Technical Reference's own reading, § 9, p. 65: `Fmagc = L·Fmag`, with `m = {mlx, mly, mlz}` and `L` the Cartesian lattice matrix.
The values TOPAS reports on a file's `MM_CrystalAxis_Display` line are the numbers to compare with, and on the Durham LaMnO₃ tutorial they agree to the printed digits.
It is also measured against TOPAS's own calculated intensities.
On a monoclinic cell with β = 115° and a moment on all three axes, TOPAS 6's magnetic intensity ratios between reflections of equal d match this reading on every pair to four digits, and its absolute magnetic intensity gives the same |m|.
A crystal-axis reading misses the median pair by about 58 %, and a Cartesian one by about 80 %.
With the moment along b alone, where the three readings coincide, all three match.
So the comparison can tell the readings apart.

A moment-bearing site whose species has no charge (`occ Cr` rather than `Cr+3`) takes the neutral atom's form factor, reported as [`TOPAS_MOMENT_ION_UNCHARGED`](diagnostics-projects.md#topas_moment_ion_uncharged).

`mg` is the site's Landé g, which enters only the ⟨j<sub>2</sub>⟩ weight of the magnetic form factor.
TOPAS can refine it (Technical Reference § 9, p. 66), and `Moment.g` is a fixed number.
So an `mg` the file refines (`mg @ 1.9`, or a named parameter) is held at the file's value, and [`TOPAS_MOMENT_G_HELD`](diagnostics-projects.md#topas_moment_g_held) names each such site.
A site with no `mg` takes the spin-only value.

`mag_only` and `mag_only_for_mag_sites` switch a site's nuclear scattering off.
A file that uses them typically restates the magnetic sites in a second `str`, and building that without the switch would count those sites' nuclear scattering twice, so it is refused by name.
One form is read: a separate magnetic-only width, written the way a writer has to state it, since TOPAS has one peak shape per `str`.
A `"<name> magnetic part"` `str` whose every site is `mag_only` and carries a moment is merged back into `<name>`, its moments onto the sites of the same label.
The part's scale, cell, space group and each site's position, element and occupancy must equal `<name>`'s, and every part site needs a site of that label in `<name>`.
The merge takes the part's `mag_space_group`, its ion and its moments' refine flags, and [`TOPAS_MAGNETIC_PART_MERGED`](diagnostics-projects.md#topas_magnetic_part_merged) reports it.
Every other refusal the part states stays in force, and a `mag_only_for_mag_sites` `str` is still refused.
The two widths come back from parameters named as rietx writes them, reported as [`TOPAS_PHASE_TERM_READ`](diagnostics-projects.md#topas_phase_term_read).

### Writing a magnetic phase

`rx.write_topas_inp` writes a magnetic phase back in the same form.
The `str` states `mag_space_group` with the BNS number and no `space_group`.
Each moment-bearing site states `mlx mly mlz`, the stored μ<sub>B</sub> divided by the edge, plus `mg` where a Landé g is set.
Each component is flagged `@` where the site symmetry lets it move and the moment is free, and `!` otherwise.
Read back, each component is within one ulp of the one written: over 180 random moments on an orthorhombic, a monoclinic and an oblique triclinic cell, most come back bit for bit.
The group's symbol rides as a comment and is not read back.

Whatever the `str` cannot state is refused by name:

- a group in a setting other than its number's standard one, since TOPAS generates the standard operators;
- a group with no tabulated number;
- a nuclear group larger than the magnetic group's own family group, since TOPAS would generate only part of each parent orbit;
- a magnetic group on a phase with no moment;
- a moment ion that differs from the site's species, since TOPAS takes both from the one `occ`;
- a propagation vector, either the parent k of a supercell or a phase's own.

A magCIF drops the parent k as well, since a supercell is written as k = 0 in its own cell, so the `Structure`'s own JSON is the export that keeps it.
The ion refusal applies to the plain form.
With `instrument=`, `pattern=`, `free=` or `scale=`, a moment-bearing site is written with its ion unless the instrument is X-ray, and on that X-ray route a differing ion is still refused.

A magnetic phase the `str` cannot state goes through P1.
`write_topas_inp(structure, path, p1_expand=True)` writes every phase as the explicit list of the atoms of its cell, in `P 1`, each with its own moment, and a magnetic phase as `mag_space_group 1.1`.
A k ≠ 0 supercell, a family group TOPAS has no number for and a non-standard setting all go through this way, because the restatement needs neither the parent k nor a group name.
The list comes from `rietx.crystallography.magnetic.p1.restate_phase_in_p1`, the forward model's own expansion.
Each position is R·x + t, each moment is ε·det(R)·R·m in crystal-axis μ<sub>B</sub> (an axial vector, with ε = −1 for a primed operation or an anti-translation), and each displacement tensor is rotated with its image.
`predict()` on the restatement equals `predict()` on the original to about 1e-12, so the list also checks the moments of every atom of the cell.
Atom labels become `<label>_<k>`.
The species of a moment-bearing atom is written as its ion.
A neutron pattern does not notice the difference.
A phase with restraints, a Stephens anisotropic-strain block or a spherical-harmonics texture cannot be restated and is refused.

With `p1_expand=True` alone, every flag in the file is `!`: the ties that made the copies one parameter are not stated in P1, so free what you mean to refine in TOPAS yourself.
With `free=`, `scale=`, `instrument=` or `pattern=`, the copies are tied instead.
Each copy is an equation over the parameter it copies (`mly = -0.1099*Fe1_moment_dof0;`, the moment a `prm` in μ<sub>B</sub>), so the file refines as the model does.
The anti-translation partners of a supercell, and a `tie_equal` across copies, come out as one name.

`p1_expand="auto"` restates only a phase TOPAS cannot name as it stands (a k ≠ 0 supercell, a family group with no tabulated number, a non-standard setting, a larger nuclear parent) and writes every other phase in its own group.
When it restates a phase it writes the tied form, and names each phase it restated with [`TOPAS_PHASE_RESTATED_IN_P1`](diagnostics-projects.md#topas_phase_restated_in_p1).
When nothing needs restating it writes the plain form.
It does not lift the refusal of a magnetic group with no moment or of a phase's own k.

A magnetic-only width (`magnetic_lor_size`, `magnetic_lor_strain`) has no keyword in a TOPAS `str`, which has one peak shape.
With `instrument=`, a phase that carries one is written as two `str` sharing every parameter: the nuclear part, and `"<name> magnetic part"`, which lists only the moment-bearing sites, each `mag_only`, under the magnetic group, with the two widths added to its Lorentzian terms.
That is rietx's model term for term, since nuclear and magnetic scattering do not interfere for unpolarised neutrons.
A magnetic-only width beside a non-zero or free extinction is refused.
Without `instrument=` the file has no profile to add the widths to, and [`TOPAS_FIELD_NOT_WRITTEN`](diagnostics-projects.md#topas_field_not_written) names them.
For such a file, TOPAS 6's zero-cycle pattern agrees with rietx's to 3.6 × 10⁻³ of the peak, measured, against 5 × 10⁻² without the width.
`tests/test_topas_p1_ties.py` holds the comparison to 10⁻².

## Magnetic phases in a FullProf input file

FullProf states a magnetic structure as a separate pure magnetic phase: `Jbt = 1`, or `Jbt = -1` with the moment as (M, φ, θ).
The phase lists only the magnetic atoms and has its own `Scale`.
FullProf's manual requires that phase's scale and structural parameters to be constrained to those of its crystallographic counterpart.
So `rietx.io.projects.fullprof.to_structure` reads it as the moments of that counterpart, one `Jbt = 0` phase of the same file, and only when all of the following hold:

- the magnetic phase is stated in the counterpart's own cell, with k = 0 (the magnetic cell, where the manual says the Fourier term is the moment);
- its symmetry is `Isy = -1` SYMM/MSYM pairs, each moment matrix ±det(R)·R with phase 0, so each pair is a Shubnikov operation;
- each magnetic atom sits on one of the counterpart's sites, with the same Biso and the same number of images;
- the two phases' `Scale × f²` agree, f being the `Occ` factor, because one scale is all the built phase has.

The moments are μ<sub>B</sub> on unit vectors along the cell axes.
That is magCIF's basis, so the numbers carry over as written.
[`FULLPROF_MAGNETIC_PHASE_READ`](diagnostics-projects.md#fullprof_magnetic_phase_read) reports the merge.
A moment carries one refine flag, so a site whose file frees only some of its three moment columns (`Jbt = -1` with only M coded, say) comes in with the whole moment free, and the message names the site.

Every other magnetic phase is refused by name, naming the phase and the reason:

- the Fourier-component form, meaning a k other than 0, an imaginary part, or a `MagPh` or MSYM phase;
- basis functions of an irreducible representation (`Isy = -2`);
- a moment matrix that is not an axial action;
- a counterpart stated in a different cell, as when the nuclear phase is in the chemical cell and the magnetic one in the supercell, or one whose space group does not build;
- no counterpart sharing the cell, or more than one, and two magnetic phases on one counterpart, since one phase carries one magnetic group;
- a magnetic phase with no sites;
- a magnetic species label not of the form `M` + element + charge (`MCR3`), a soft moment constraint, or moment columns tied to one refinement parameter;
- `Jbt = -1` on a cell that is not orthogonal, where the manual leaves the in-plane frame of φ open.

`rietx.io.projects.fullprof.magnetic_reading(model, phase)` asks before building.
It returns the reading (the counterpart, the operations and the moments) for a phase that maps, and the refusal's reason as a string for one that does not.
`to_structure(model, nuclear_only=True)` omits every magnetic phase, and reports each as [`FULLPROF_MAGNETIC_PHASE_OMITTED`](diagnostics-projects.md#fullprof_magnetic_phase_omitted) on the `diagnostics=` list.
`write_fullprof_pcr` refuses a magnetic phase.
