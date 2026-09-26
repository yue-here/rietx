# Files and projects

This chapter is the map of what the package reads off disk and what it writes
back. [](data.md) is what the objects it hands you contain.

```{mermaid}
graph LR
  P["pattern file<br/><i>.xye .fxye .raw .cif …</i>"] --> RP["read_pattern"]
  C["structure<br/><i>.cif</i>"] --> SC["Structure.from_cif"]
  I["instrument profile<br/><i>.json</i>"] --> LP["load_instrument_profile"]
  G["GSAS-I instrument file<br/><i>.prm</i>"] --> GP["read_gsas_prm"]
  M["another program's refinement<br/><i>.inp .pcr .EXP</i>"] --> PM["read_project_model"]
  RP --> REF(["refinement"])
  SC --> REF
  LP --> REF
  GP --> REF
  PM --> REF
  subgraph rex ["my_sample.rex/"]
    PJ["project.json<br/><i>settings</i>"]
    PC["the pattern file<br/><i>copied byte for byte</i>"]
    H["history.jsonl<br/><i>model state</i>"]
    LV["live/<br/><i>one directory per run</i>"]
    EX["exports/<br/><i>CIF, tables</i>"]
  end
  REF --> PJ
  REF --> PC
  REF --> H
  REF --> LV
  REF --> EX
  REF -.-> RUNS[".rietx/runs/<br/><i>one directory per fit,<br/>with no project</i>"]
```

Every fit writes the dotted arrow whether you asked for it or not. A refinement
that came from a project records into that project's `live/` instead, and
`.rietx/` is what a fit outside a project leaves in the working directory. Both
are below.

## Pattern files

`read_pattern` opens a pattern and returns a `PatternData`, whose fields are in
[](data.md). It identifies the format from the file itself rather than from the
extension:

```python
from rietx import capabilities

caps = capabilities()
[(fmt.name, fmt.sigma) for fmt in caps.reader_formats]
[(opt.name, opt.help) for opt in caps.reader_options]
```

Ask `capabilities()` rather than trusting a list in prose. The format list went
from five to ten in two days once. `ReaderCapability.sniff` says how each format
is recognised, `ReaderCapability.sigma` says where the uncertainties come from,
and `ReaderCapability.refuses` says what the reader declines and why.

Four properties of the readers reach a caller, and each of them can change a
number you quote.

A multi-range file holds scans, and the reader selects one. Pass `scan=` to
choose. The ranges are never concatenated, because two ranges are usually two
weighting regimes, and joining them silently mixes them.

A pdCIF holds blocks instead of scans, and takes `block=`. A file with
a `_meas` block and a `_calc` block is a different pattern depending on which
you ask for. `read_pdcif` reads one directly.

A reader may repair a file only where it can say that it did. Pass a list as
`diagnostics=` and the repairs come back in it:

<!-- api-doc: no-exec — it reads a pattern file the reader supplies -->
```python
import rietx as rx

notes = []
data = rx.read_pattern("my_sample.raw", diagnostics=notes)
for note in notes:
    print(note.code, note.message)
```

The intensities and σ need not be the file's numbers. Vendors disagree about
whether an attenuator factor is already applied (four formats, three answers),
so the reader applies it or not by measured convention, and σ goes through the
same transformation either way. Where the scale cannot be established the reader
withholds σ and says so with `PATTERN_INTENSITY_SCALED`, because the Poisson
fallback is wrong by √t on a rate.

The scanned axis is never assumed. Most vendor files are not powder scans at
all, so a file whose axis is something other than 2θ is refused by name, and an
axis the reader cannot identify says so.

Weights follow from all this. The package uses the file's esd column when the
file has one, and Poisson σ = √max(y, 1) only as the fallback. It never
subtracts an estimated background: hold the background additively
(`BackgroundFixedPlusChebyshev`) or co-refine it under a smoothness penalty
(`BackgroundPSpline`).

## Structures from CIF

`Structure.from_cif` reads a crystal structure. It takes `phase_name=` to pick
one block from a multi-phase file, `aniso=True` to read an anisotropic
displacement loop, and the same `diagnostics=` channel:

<!-- api-doc: no-exec — it reads a CIF the reader supplies -->
```python
notes = []
structure = rx.Structure.from_cif("my_phase.cif", aniso=True, diagnostics=notes)
```

`aniso` is opt-in on purpose. Several CIFs carry an anisotropic loop, and
reading a file must not silently change which parameters a plan will free.

Two repairs happen at read, and both are recorded rather than assumed. A species
label that is not a recognised scatterer is normalised
(`CIF_SPECIES_NORMALISED`), and a cell angle that disagrees with its space group
by a small amount is snapped to the symmetry value
(`CIF_CELL_ANGLE_CORRECTED`): a β of 90.002(3) under `P m m m` is an
experimenter quoting a refined number. Past that threshold the symbol and the
angle contradict each other, one of the two is wrong, and choosing between them
is yours: the value is left byte for byte and the read raises.

A third note is a report rather than a repair. A site can sit within 1e-4 of a
special position without being on it, as a file quoting five decimals often
leaves one. Such a site has its orbit expanded at that position, so its
multiplicity is the special one, and `SITE_SNAPPED_TO_SPECIAL_POSITION` names
the site, the shift and the multiplicity. The stored coordinates are unchanged
and the fit is unaffected. What the multiplicity decides is how many atoms the
site puts in the cell, and so ZMV and every weight fraction; compare it against
the file's own `_atom_site_symmetry_multiplicity`.

Building a phase by hand, with no file behind it, has one more way to go quiet.
A bare Hermann-Mauguin symbol resolves to the first setting the tables hold, and
40 symbols hold more than one: the `:1`/`:2` origin choices and the rhombohedral
`:H`/`:R` axes. Site multiplicities differ between settings, so
spinel's origin-2 coordinates under a bare `F d -3 m` build Mg₂AlO₄ where
MgAl₂O₄ was meant, with Rwp unmoved. `SPACE_GROUP_SETTING_ASSUMED` quotes the
cell contents each setting implies, which is the part you can recognise:

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

Naming the setting silences it. Files carry theirs, so a CIF or a TOPAS `.inp`
never raises it.

### A magnetic structure: reading and writing a magCIF

A magnetic structure reaches you as a magCIF, and `Structure.from_cif` reads
one. MAGNDATA, ISODISTORT, k-SUBGROUPSMAG and Bilbao's own tools all emit that
form, and what it carries is exactly what the model stores: the operator list
with its time-reversal signs, the moments in crystal-axis components and the
BNS symbol.

<!-- api-doc: no-exec — it reads a magCIF the reader supplies -->
```python
notes = []
structure = rx.Structure.from_cif("0.642.mcif", moment_ions={"Mn1": "Mn3+"},
                                  diagnostics=notes)
phase = structure.phases[0]
print(phase.space_group, phase.magnetic_symmetry.bns_number)
print(phase.atoms[1].moment.values(), phase.atoms[1].moment.ion)
```

Four things about that read are worth knowing before you trust the answer.

The nuclear space group's label comes from `_parent_space_group.name_H-M_alt`
(a magCIF states no ordinary `_space_group_name_H-M_alt` at all, since the
magnetic block replaces it). The IUCr underscore screw-axis spelling
(`P 2_1/c`) is normalised to the plain one gemmi's lookup table accepts (`P
21/c`) before the symbol is resolved, and the file's own spelling stays
unchanged in every diagnostic. The symbol names the type, and the setting is
checked against the file's own magnetic operators with time reversal dropped,
because gemmi's tabulated operator table for a Hermann-Mauguin symbol can sit
at a different origin or axis choice than a non-standard setting's own
(measured on Ima2, space group 46), and a symbol lookup on its own would attach
the wrong coordinate frame to a right-looking name. The atom positions refine under
the highest tabulated group the file's atoms satisfy, and the moments always
under the file's magnetic group. The parent is kept when it contains those
operators and gives every listed site the same number of images as they do:
that is a nuclear phase under the parent carrying moments under a magnetic
group that may be a subgroup of it, Cr₂WO₆'s `Pn'nm` in `P4₂/mnm`, and
`CIF_MAGNETIC_NUCLEAR_GROUP` says so ("positions refine under 'P 42/m n m',
index 2 over the file's own 'P n n m'; moments under the file's magnetic
group"). Otherwise the phase is built under the tabulated setting whose
operations are exactly the file's own, and `CIF_MAGNETIC_NUCLEAR_SETTING` says
which and why. `Structure.from_cif(..., nuclear_group="file")` always takes the
file's own group, and `nuclear_group="parent"` always takes the parent and is
refused by name where the parent cannot carry the file's atoms; the default,
`"auto"`, is the rule above.
That covers a symbol tabulated at another origin, and a symmetry-lowering
magnetic group whose asymmetric unit lists one parent orbit as two sites,
which under the parent would be one orbit counted twice. A file whose own
group is in a setting no tabulated symbol names, an origin or axis choice
gemmi's table does not hold, is read with that group as its operation list:
`Phase.symmetry_operations` holds the file's operations with time reversal
dropped, in the file's order, `Phase.space_group` holds a bracketed label
naming the closest type (`'P -1 [unnamed in this cell]'`), and
`CIF_MAGNETIC_NUCLEAR_SETTING` says so. Every symmetry consumer reads the list,
never the label, and `Structure.to_cif` writes the list back. A writer whose
format states a group only as a symbol refuses such a phase by name. A group
whose rotations are in no tabulated orientation at all, a two-fold along a face
diagonal for instance, is refused by name: an operation list takes its crystal
system and cell ties from the tabulated group with the same rotations, and
there is none.
A `_parent_space_group.transform_Pp_abc`
that is not the identity is a record of which setting the symbol was
tabulated in, one every non-standard-setting MAGNDATA entry carries, and is
not by itself a reason to refuse the file. What is refused is a genuine
supercell, judged by the child transform's determinant and by k, never by the
parent transform. A file with no space group this reader can resolve at all,
neither an ordinary tag nor a magCIF parent symbol, is refused by name.

The operators are stored verbatim, and `transform_BNS_Pp_abc` is not applied.
A published structure is usually written in its own setting rather than the BNS
standard one (Cr₂WO₆'s record carries `'b,-a,c;0,0,0'`), and that setting is
the one its cell and coordinates are in. So the list is kept as written, the
transform goes into `MagneticSymmetry.setting` as the record it is, and applying
it would move the group away from the atoms beside it.
`MagneticSymmetry.uni_number` is *derived* from the operators through spglib, so
it is the same on both sides of a round trip.

The magnetic ion is not in the file. The magnetic dictionary has no item for
it, and MAGNDATA writes a bare `Mn` for a site that is chemically Mn³⁺, so
without `moment_ions=` the *neutral atom's* ⟨j₀⟩ is used and
`CIF_MAGNETIC_ION_UNCHARGED` says so. The two curves differ, and a moment
refined under the wrong one absorbs the difference into its magnitude. A bare
lanthanide or actinide symbol has no neutral-atom row at all, so there the
fallback goes one step further, to the element's majority oxidation state
that is *magnetic* (Ln³⁺, except Eu²⁺; U⁴⁺, Np⁴⁺, Pu³⁺), reporting
`MAGNETIC_ION_ASSUMED` instead. `moment_g=` is the same shape for the Landé g
a 4f moment needs. Where the ion itself was assumed this way, its free-ion
Hund's-rule g_J is assumed too (magCIF has no item for g any more than it has
one for the ion, so refusing on a quantity the file could never have carried
either way would be the wrong-shaped fix), reporting `LANDE_G_ASSUMED`. An ion
*stated* explicitly (`moment_ions=`) still needs `moment_g=` stated alongside
it, unchanged: that gap is the caller's, unrelated to this default. Both
arguments are keyed by `_atom_site_moment.label`, and a key that names no row
of that loop is refused with the labels the file does carry, since a
misspelled label would leave its site on the default with nothing said.

All three moment forms are read. The dictionary defines the moment in
crystal axes, in spherical coordinates and in Cartesian ones; a reader taking
only the first would silently drop the other two. The spherical and Cartesian
frames are the one where x ∥ a and z ∥ c*, which is the frame the ADP
code already uses, so no second convention enters. Where a file states more than
one form they must agree, and a file stating `_atom_site_moment.magnitude` has
it cross-checked against the components under the cosine metric the
dictionary defines: |m| = √(mᵀ·G·m) and not √(Σmᵢ²), which on hexagonal axes is
29 % out and is the commonest way that line goes wrong. The check compares
`|magnitude|` against the (always non-negative) derived norm, since a
negative stated magnitude is a sign convention rather than a mismatch, at a
tolerance drawn from the file's own stated precision (`magnitude_su`, an
inline `value(su)`, or half the last printed digit when neither is given)
rather than a fixed band, widened by each component's own imprecision
propagated through the metric, since the derived norm is itself only as
precise as the components it came from. A magnitude rounded to fewer
figures than the components is read, not refused.

Standard uncertainties follow the form the moment is taken from. A
crystal-axis row keeps its own. A Cartesian row's go through the conversion,
which is linear, so each crystal-axis esd is the Cartesian ones propagated
through it, assuming no correlation between components, since a CIF row
states none. A spherical row's are not propagated, because that conversion
is nonlinear and singular on the pole, and `CIF_MAGNETIC_SPHERICAL_ESD_NOT_STORED`
names each su that was dropped, so a component's `stderr=None` there is not
read as "not refined".

Two constructs are refused by name rather than half-read. A modulated
structure (any `_atom_site_moment_Fourier` loop, special function, cell wave
vector or superspace group), because reading its k = 0 amplitude alone would
return a collinear structure for a modulated one. And a structure stated in a
supercell of its parent, which is the generic commensurate k ≠ 0 record: the
asymmetric unit of the magnetic group in that cell splits one *nuclear* orbit
into several sites carrying different moments, and the model stores one moment
per nuclear site. Both refusals name what would be needed. The k ≠ 0 test
reduces every component modulo 1 first, because a propagation vector is only
ever meaningful modulo the reciprocal lattice: an all-integer k such as
(1, 1, 1) is Γ identically and reads exactly like k = 0, never as a
supercell. The parent k is read for that test and nothing else, so it is not
stored and not written back.

`Structure.to_cif` and `Refinement.write_cif` write the same form back. The
operator and centring loops go out verbatim, the BNS/OG metadata with them,
and the moments in crystal-axis components with the dictionary's own
`_su` items beside them, *not* in the `value(su)` notation every other number
in the file uses, and for a measured reason: a refined moment's esd is routinely
0.05-0.9 μ_B, so two significant figures of su would quote the value to one
decimal and the number you refined would not come back. Two items have no
magnetic-dictionary tag at all, the form-factor ion and the Landé g, so they go
out under a namespaced `_rietx_atom_site_moment.` category; without them a round
trip would lose which form factor the refinement used. A refinement CIF also
carries `_atom_site_moment.magnitude_su`, the esd of the modulus, which is
where a moment's uncertainty lives.

### A magnetic phase from a TOPAS `.inp`

A TOPAS `.inp` states a magnetic phase as `mag_space_group` on a `str`, with
`mlx mly mlz` (and optionally `mg`) on each magnetic `site`. Its magnetic
examples, and ISODISTORT's TOPAS export, often state no nuclear `space_group`
at all. `rx.read_topas_inp` reads such a `str` as a phase. The build then takes
the nuclear group from the magnetic one: its operators with time reversal
dropped, under the magCIF reader's tier-2 rule above. TOPAS itself generates
the atoms from those operators.

A `mag_space_group` written as a BNS number (`62.448`, `1.1`) or an OG number
is used as the group directly. It resolves to the operators of that number's
standard setting, and `TOPAS_MAGNETIC_GROUP_READ` says so. A Shubnikov
*symbol* is only kept as metadata, because nothing here parses one. The build
refuses a phase that states moments under a symbol until you pass
`to_structure(magnetic_symmetry=...)`.

`mlx mly mlz` are components in the fractional basis,
m = mlx·a + mly·b + mlz·c with the edges in Å. The stored
crystal-axis moment is therefore (mlx·|a|, mly·|b|, mlz·|c|). This is a
per-axis scale, never a rotation. It is the TOPAS Technical Reference's own
reading, § 13: Fmagc = L·Fmag, and its `MM_CrystalAxis_Display` macro gives
mxc = mlx·a. A file's `MM_CrystalAxis_Display` line is the number to compare
with. On the Durham LaMnO₃ tutorial it agrees to the printed digits. It is
also measured against TOPAS's own calculated intensities. On a monoclinic
cell with β = 115° and a moment on all three axes, TOPAS 6's magnetic
intensity ratios between reflections of equal d match this reading on every
pair to four digits, and its absolute magnetic intensity gives the same |m|.
A crystal-axis reading misses the median pair by about 58 %, and a Cartesian
one by about 80 %. With the moment along b alone, where the three readings
coincide, all three match, which shows the comparison can tell them apart.

`mag_only` and `mag_only_for_mag_sites` switch a site's nuclear scattering off.
The file that uses them typically restates the magnetic sites in a second
`str`. Building that without the switch would count those sites' nuclear
scattering twice, so it is refused by name rather than dropped.

## Instrument profiles

A calibrated instrument is a file. `save_instrument_profile` writes one and
`load_instrument_profile` reads it back with every parameter `vary=False`, which
is the second half of the two-step lab workflow:

<!-- api-doc: no-exec — it refines a standard and writes a file -->
```python
result = rx.refine(standard_data, standard, instrument, plan="lab_calibrate")
rx.save_instrument_profile(ref.fitted_instrument, "cu_ka_10mm.json")

instrument = rx.load_instrument_profile("cu_ka_10mm.json")
result = rx.refine(data, structure, instrument, plan="lab_sample_refine")
```

Calibrate on a standard with its certified cell held fixed. That is what
decorrelates the zero shift from the sample displacement from the cell, and it
is why `lab_sample_refine` is the only plan whose size and strain numbers mean
what they say.

The GUI writes and reads the same file from the Model panel, with `Save
profile…` and `Load profile…`. Saving lands it in the project's `exports/`
directory. It needs a model and not a fit, unlike everything else written
there: the other exports describe a refinement result, while a profile
describes the instrument as it stands.

### Reading a GSAS-I `.prm` instrument file

`read_gsas_prm` reads a GSAS-I instrument-parameter file (Larson & Von Dreele,
*GSAS*, LAUR 86-748) straight into an `Instrument`, with the same `vary=False`
contract as `load_instrument_profile`. It is the text file an APS 11-BM mail-in
ships beside its pattern:

<!-- api-doc: no-exec — needs a real .prm file on disk -->
```python
instrument = rx.read_gsas_prm("beamline.prm")
```

It reads the dominant case the format ships: one bank, `HTYPE PXCR`
(constant-wavelength X-ray), GSAS profile function 3. Its neutron twin, `HTYPE
PNCR` with profile function 3, reads too, onto
`Instrument.constant_wavelength_neutron` at the file's `LAM1`: the profile
record is defined by profile function rather than by radiation, so the same
coefficients land in the same places. A neutron source has one wavelength and
no polarization, so such a file's `POLA` and `KRATIO` are read and not applied,
and a non-zero `LAM2` is refused. It converts `GU`/`GV`/`GW`
from centidegrees² and `LX`/`LY` from centidegrees into the degrees² and degrees
`ProfileTCHZ` uses. A file stating a Kα1/Kα2 doublet comes back with two
emission lines, the second weighted by the `KRATIO` field, which is the Kα2/Kα1
intensity ratio and so is what `EmissionLine.weight` means. A doublet with no
`KRATIO` is refused: the conventional 0.5 would be the reader's number rather
than the file's, and the polarization two fields earlier is conventionally 0.5
as well. A neutron time-of-flight file (`HTYPE PNTR`) and every other
GSAS profile function are refused by name rather than approximated, and the
refusal says which reason applies to which. A time-of-flight file puts something
onto the axis that `ProfileTCHZ`'s constant-wavelength Caglioti/TCH law cannot
express. A profile function other than 3 is refused under `PXCR` and `PNCR`
alike, naming the type the file carries, because each function has its own
coefficient layout and no verified one exists here for the others. A GSAS `.LST` refinement output has no reader and is transcribed
by hand. A GSAS `.EXP`, a TOPAS `.inp` and a FullProf `.pcr` are whole
refinements rather than instrument files, and have their own readers in the
next section.

Two things this reader chooses rather than reads, both on the `diagnostics=`
channel the sections above use. A `.prm` states no geometry at all, and
`HTYPE PXCR` spans Bragg-Brentano and Debye-Scherrer, so the `Instrument` comes
back `debye_scherrer`, which is the 11-BM capillary the corpus this reader was
built against. A flat-plate calibration must have its geometry set by the
caller, and doing that takes one care, because the geometry is not the only
thing assumed. `S/L` and `H/L` (`PRCF` positions 7-8) are read from the file,
and they land on `geometry.axial_sl`/`geometry.axial_hl` rather than on the
profile. A replacement `Geometry` built from scratch starts at 0 for both, which
is an instrument with no axial divergence at all, so copy those two across. That
matters beyond bookkeeping: `Geometry.kind` selects the position correction and
its suggested action, and the two geometries' absorption corrections have
different off states. The file's fields that the `Instrument` cannot carry are
dropped at their identity value and reported the same way, one per record that
carried them:

<!-- api-doc: no-exec — needs a real .prm file on disk -->
```python
notes = []
instrument = rx.read_gsas_prm("beamline.prm", diagnostics=notes)
[(d.code, d.message) for d in notes]
# GSAS_PRM_FIELD_DROPPED:    ICONS's IPOLA and refine controls, PRCF's GP …
# GSAS_PRM_GEOMETRY_ASSUMED: the geometry was not read from the file
```

### Writing a GSAS-I `.prm` back

`write_gsas_prm` is that reader's inverse, and the fourth of the
foreign-format writers. It takes a calibrated `Instrument` and states it as
GSAS states one: the wavelengths, the polarization, `profile.u/v/w` as
`GU`/`GV`/`GW` and `profile.x/y` as `LX`/`LY` multiplied back into
centidegrees, and `geometry.axial_sl`/`axial_hl` as `S/L` and `H/L`:

<!-- api-doc: no-exec — it writes a file -->
```python
notes = []
rx.write_gsas_prm(instrument, "beamline.prm", header="LaB6, March",
                  diagnostics=notes)
```

Unlike the three structure writers, the refine flags are deliberately not the
payload. An instrument-parameter file is a beamline calibration rather than a
starting guess, which is why both readers here hand one back frozen, so the
`PRCF` header's flag columns are left blank as a real calibration file leaves
them. `GSAS_PRM_FIELD_NOT_WRITTEN` names what this instrument carries that the
format cannot state, the geometry always among it. `GSAS_PRM_VALUE_NARROWED`
names what did not fit: a `.prm` is read by column and a column is the budget,
so a converged calibration's full-precision numbers are written to what the
field holds.

One value is refused rather than reported. `ICONS`' `ZERO` field is the one
number here whose unit this package has not established, and `read_gsas_prm`
refuses a non-zero one on the way in for that reason, so writing a guess would
make a file this package will not read back and a `ZERO` wrong by 100× puts
every peak in the wrong place. Set `zero_shift` to 0 and let the receiving
program refine it; a zero shift belongs to the mount rather than to the
goniometer. A third emission line and a second line whose weight is not a
`KRATIO` are refused for the same reason: each would make a file this
package's own reader declines. A neutron source is refused for a different
one. The reader takes a type-3 `HTYPE PNCR` file, but what such a file's `POLA`
and `KRATIO` should hold, for a source that has neither, is spelled by one real
file only, and that is a reading rather than a convention to write by.

Pass no list and the read is silent and identical, so the channel is opt-in
rather than a behaviour change.

### Reading a GSAS-II `.instprm` file

GSAS-II keeps a project in the binary `.gpx` the next section opens, and ships
a calibration as a small text file instead. `read_gsas2_instprm` reads one into
a frozen `Instrument`, on the same contract as the two readers above:

<!-- api-doc: no-exec — needs a real .instprm file on disk -->
```python
notes = []
instrument = rx.read_gsas2_instprm("beamline.instprm", diagnostics=notes)
```

It reads the constant-wavelength types, `PXC` (X-ray) and `PNC` (neutron), and
a neutron file comes back with a `NeutronSource`. `U`, `V` and `W` are
centidegrees squared and `X` and `Y` centidegrees, converted through the same
factors the `.gpx` reader uses. `Zero` is already in degrees, and it means what
`instrument.zero_shift` means: a constant added to the calculated 2θ. `SH/L` is
GSAS-II's combined (S+H)/L, so it is split evenly into `axial_sl` and
`axial_hl`, which is the symmetric Finger-Cox-Jephcoat reading and the only one
a single number admits.

Several banks in one file are a selection rather than a default: pass
`bank=`, as `#Bank n:` states it, or the read refuses and names the numbers it
found. Refused by name as well: a time-of-flight or energy-dispersive `Type`,
a non-zero `Z` (this package's profile is `u, v, w, x, y` exactly, and `Z` is
zero in all 95 constant-wavelength histograms of GSAS-II's own tutorial
corpus), a non-zero `Azimuth`, which changes what `Polariz.` means, and a
negative `U`, `W`, `X` or `Y`. That last one is the ordinary case rather than a
corner. GSAS-II bounds none of its width coefficients, this package's are
bounded at zero through a softplus, and two of the four constant-wavelength
files in that corpus converged to a negative `X`.

The geometry comes from `Diff-type` where the file states one. Where it does
not, the reader falls back the way GSAS-II's own does (a stated doublet is
Bragg-Brentano and anything else Debye-Scherrer) and says so with
`GSAS2_INSTPRM_GEOMETRY_ASSUMED`, because the choice was not read from the
file.

### Writing a GSAS-II `.instprm` back

`write_gsas2_instprm` is that reader's inverse and the machine half of what
GSAS-II imports. The structure half is a CIF, below.

<!-- api-doc: no-exec — it writes a file -->
```python
notes = []
rx.write_gsas2_instprm(instrument, "beamline.instprm", diagnostics=notes)
```

The refine flags are dropped here as they are from a `.prm`, an `.instprm`
stating none at all. Two values are worth knowing about before you hand the
file to GSAS-II. `axial_sl` and `axial_hl` are written as their sum, GSAS-II
modelling one number where this package holds two, and an uneven pair is named
`GSAS2_INSTPRM_VALUE_MERGED` rather than quietly halved on the way back. And
GSAS-II floors `SH/L` at 0.002 when it evaluates a profile, so a smaller sum is
written faithfully and still modelled as the floor by the program the file is
for; that is `GSAS2_INSTPRM_VALUE_FLOORED`, and no round trip through this
package can show it.

## Refinement files another program wrote

A TOPAS `.inp`, a FullProf `.pcr` and their kind are neither patterns nor
structures. They state someone's whole refinement: the phases, the instrument,
and which parameters were free. That last part is the one nobody can reconstruct
from a CIF plus a pattern. Transcribing one by hand is the failure mode this
reader exists to remove, because a mistyped coordinate stays symmetry-valid and
fails silently, so what comes out is a plausible wrong answer rather than an
error.

:::{admonition} Provisional
:class: warning
The foreign-refinement readers are under active development, so the names in
this section are documented and not frozen. `read_project_model`,
`identify_project_format`, `read_topas_inp`, `read_fullprof_pcr`,
`read_gsas_exp`, `read_gsas2_gpx`, `write_topas_inp`, `write_fullprof_pcr`,
`write_gsas_exp`, `write_gsas2_phase_cif` and
the per-format models they answer with (`rietx.io.projects`) may change in a
1.x release: the registry has four formats and one more queued, each of which
is evidence about its shape, and all four can now be written. A format's own
model mirrors that format, so its fields move when the reader's coverage does.
{ref}`provisional-by-declaration` has the promise in full.
:::

### Opening one

`read_project_model` takes a file and works out which program wrote it:

<!-- api-doc: no-exec — needs a real .inp or .pcr on disk -->
```python
model = rx.read_project_model("refined.inp")
model.format.name          # 'topas_inp'
model.stated.r_wp          # the run's own figure, as the file states it
structure = model.to_structure()
```

Dispatch is on content, never on the extension. `.inp` is written by several
unrelated programs, and claiming one by name is how a reader returns a plausible
wrong model for a finite-element deck. A file nothing here reads is refused by a
message naming what this build does open, and pointing at the three neighbouring
readers: `rx.read_pattern` for a pattern, `rx.read_gsas_prm` for a GSAS-I
instrument file, `rx.read_recipe` for a PowderLine recipe. Those are what such a
file usually turns out to be.

Call `rx.read_topas_inp`, `rx.read_fullprof_pcr`, `rx.read_gsas_exp` or
`rx.read_gsas2_gpx` directly when you already know what you have; `rx.identify_project_format` answers which format claims a
file without parsing it, reading only enough of the head to decide.

### Writing one back

`rx.write_topas_inp(structure, path)`, `rx.write_fullprof_pcr(structure,
path)` and `rx.write_gsas_exp(structure, path)` are each format's inverse of
its own reader +
`ProjectModel.to_structure`. All three write a file that states the same
phases, the same cell and the same atoms, plus the part a CIF cannot carry:
the same refine flags, each `Parameter.vary` written in the target format's
own grammar (TOPAS's `@`/`!`; FullProf's codeword, one free parameter to one
codeword number, never a shared tie; GSAS's `Y` on the cell record and its
`X`/`U`/`F` letters on a site's).

<!-- api-doc: no-exec — needs a real Structure and writes a file -->
```python
rx.write_topas_inp(structure, "exported.inp")
back = rx.read_topas_inp("exported.inp").to_structure()

rx.write_fullprof_pcr(structure, "exported.pcr")
back = rx.read_fullprof_pcr("exported.pcr").to_structure()

rx.write_gsas_exp(structure, "exported.EXP", title="my experiment")
back = rx.read_gsas_exp("exported.EXP")
```

All three write space groups from `get_spacegroup(...).xhm()`, never a
phase's own stored spelling, so a setting this build already resolved is not
laundered back into an ambiguous symbol. FullProf's grammar has no origin or
axis suffix at all, though, so it can only *state* a setting its own
bare-symbol convention already prefers (root CLAUDE.md's "an R lattice on
rhombohedral axes" and "choice 2 wherever the bare symbol lands on choice
1"). A phase whose resolved setting disagrees, most commonly origin choice 1,
is refused by name instead of being silently written as the other setting.
TOPAS and GSAS can both spell every setting, so neither owes that refusal. An
anisotropic site is refused by the FullProf and GSAS writers, because
`to_structure` refuses to assume a displacement-tensor convention on the way
in and writing one out would assume the very thing the reader declines to
read back.

A `.EXP` is the one target read by column rather than by token, and two
things follow from that. A number is worth as many characters as its field
has, so a value whose shortest exact decimal fits ten columns crosses
untouched and one that does not is written to the precision the field holds
and named, `GSAS_EXP_VALUE_NARROWED`, once for the file. The displacement is
always in that second class: GSAS stores `Uiso` and rietx stores `Biso`, so
the 8π² between them turns a two-character `Biso` into a `Uiso` no ten-column
field can hold exactly. Ten columns keep it to about seven significant
figures, five orders below the esd a refinement reports, and two figures
better than the six decimals GSAS itself writes. The other thing is that GSAS
states one refine flag for a whole cell and one for a site's three
coordinates, both meaning "refine as symmetry permits". A structure whose six
or three disagree is written free and the group is named,
`GSAS_EXP_REFINE_FLAG_MERGED`, so the file still says the cell refined and
you learn which held parameter it frees. Pass `diagnostics=[]` to collect
both.

Some things do not travel, because no `to_structure` builds them from its
file. Common to all three: the emission profile and instrument geometry
(`Instrument` is not part of what any of these readers returns), and cell and
site bound windows. FullProf-specific: the fitted 2θ range, the resolution
function and every control/output switch on a `.pcr` are protocol
`to_structure` never reads into a `Structure`. `write_fullprof_pcr` fills them
with safe, inert placeholders purely to keep the file complete, since a
`.pcr` is positional and every line the reader expects has to exist even
where a `Structure` carries nothing for it. A written `.EXP` states no
histograms at all, which is what a GSAS experiment file looks like before any
data is loaded rather than an omission.

GSAS-II is the fourth target and the one with no project file to write.
It imports a phase from a CIF and a machine from an `.instprm`, so the pair is
what `rx.write_gsas2_phase_cif(structure, path)` and `rx.write_gsas2_instprm`
produce:

<!-- api-doc: no-exec — needs a real Structure and writes a file -->
```python
rx.write_gsas2_phase_cif(structure, "exported.cif")
back = rx.Structure.from_cif("exported.cif")
```

Its atom tags are the ones GSAS-II's own importer reads, so the file is the
package's ordinary structure block with the symmetry stated three times. That
is not belt and braces. GSAS-II resolves a bare two-origin symbol such as
`F d -3 m` to origin choice 2, and calls choice 1 a setting not compatible with
it; gemmi, and so this package, resolves the same string to choice 1. No single
symbol satisfies both, so each tag carries the spelling its own reader takes:
`_symmetry_space_group_name_H-M` the bare symbol, which is the tag GSAS-II
reads first and the only grammar it accepts, `_space_group_name_H-M_alt` the
resolved `xhm()`, which gemmi prefers when both are present, and
`_space_group_symop_operation_xyz` the operations themselves, which need no
convention at all. GSAS-II checks its own reading of the symbol against those
operations and offers to transform a structure that disagrees. A phase whose
symbol is ambiguous is named `GSAS2_CIF_SETTING_IN_OPERATORS`. What a CIF
cannot state (the refine flags, the phase scale, the sample broadening) is
named `GSAS2_CIF_FIELD_NOT_WRITTEN`.

### What comes back

The answer is a `ProjectModel`. It names the format and hands on that format's
own model untouched. It is deliberately not one shape with blanks where a file
was silent, because a blank reads as an answer and a caller cannot tell "this
file carried none" from "the reader found none".

| Field | What it holds |
|---|---|
| `ProjectModel.format` | the `ProjectFormat` that claimed the file |
| `ProjectModel.path` | the file that was read |
| `ProjectModel.stated` | what the file stated, in that format's own model |
| `ProjectModel.diagnostics` | what the read repaired or assumed, kept whether or not you asked |
| `ProjectModel.to_structure` | build a `Structure` from it, with the file's refine flags |

`ProjectModel.to_structure` passes its keywords through to the format's own
conversion, so `dataset=` reaches a multi-dataset `.inp` and `nuclear_only=`
reaches a `.pcr` with a magnetic phase. They are not flattened into one
vocabulary: two formats' options that happened to share a name would not share
a meaning.

### What each format states

A model is what the file said, seeded with nothing. A value the file omitted
arrives as `None` and never as a default. The two differ because the formats
do.

`read_topas_inp` returns a `TopasModel`:

| Field | What it holds |
|---|---|
| `TopasModel.path` | the file it was read from |
| `TopasModel.phases` | the phases the file states, with their sites and refine flags |
| `TopasModel.r_wp`, `TopasModel.gof` | the run's own figures, where the grammar settles which is the file's |
| `TopasModel.r_wp_all`, `TopasModel.gof_all` | every such value in file order, since a multi-dataset file states one per dataset |
| `TopasModel.n_datasets` | how many `xdd`-family blocks the file opens |
| `TopasModel.data_files` | the pattern files it points at |
| `TopasModel.emission_lines`, `TopasModel.emission_macro`, `TopasModel.anode`, `TopasModel.wavelength` | the emission profile, as stated or as a macro named it |
| `TopasModel.geometry`, `TopasModel.goniometer_radius_mm` | the diffractometer, where the file says |
| `TopasModel.background_terms` | how many background coefficients were refined |
| `TopasModel.skipped_blocks` | phase blocks that stated no name, or neither a `space_group` nor a `mag_space_group`, recorded whether or not a diagnostics list was passed |
| `TopasModel.coverage` | what the reader met and did not carry; see below |

`read_fullprof_pcr` returns a `FullProfModel`:

| Field | What it holds |
|---|---|
| `FullProfModel.path`, `FullProfModel.title`, `FullProfModel.pcr_name` | the file, and the names it gives itself |
| `FullProfModel.phases` | every phase, nuclear and magnetic |
| `FullProfModel.nuclear_phases`, `FullProfModel.magnetic_phases` | the same, split; a magnetic phase reads but cannot build |
| `FullProfModel.chi2` | the converged figure, from the comments FullProf rewrites each cycle |
| `FullProfModel.control` | the Job/Npr/Nph control line, field by field |
| `FullProfModel.job` | which diffraction experiment the file declares |
| `FullProfModel.lambda1`, `FullProfModel.lambda2`, `FullProfModel.lambda_slot` | the wavelengths, and which slot stated them |
| `FullProfModel.zero_shift` | the zero correction, with its refine codeword decoded |
| `FullProfModel.background` | the background the file declares |
| `FullProfModel.excluded_regions`, `FullProfModel.fitted_range` | what the run fitted and what it left out |
| `FullProfModel.data_file`, `FullProfModel.pattern` | the pattern it points at |
| `FullProfModel.cycles`, `FullProfModel.refined_parameter_count`, `FullProfModel.parameter_numbers` | how the run was driven, and which codeword numbered which parameter |
| `FullProfModel.output` | the output options the file sets |

`read_gsas_exp` returns a `GsasModel`. A GSAS experiment file holds the whole
experiment rather than one phase, so the model is a tree: phases, histograms,
and one entry per phase-and-histogram pair, which is where GSAS keeps the
profile coefficients.

| Field | What it holds |
|---|---|
| `GsasModel.path`, `GsasModel.title`, `GsasModel.version` | the file, its `DESCR` title and the GSAS version that wrote it |
| `GsasModel.phases` | every phase the file states |
| `GsasModel.histograms` | every histogram, with its machine and the pattern it points at |
| `GsasModel.hap` | the phase-and-histogram entries, keyed `(phase number, histogram number)` |
| `GsasModel.rwp`, `GsasModel.rp` | the run's own agreement indices |
| `GsasModel.reduced_chi2` | GSAS's `GDNFT` figure, which is reduced χ² rather than its root |
| `GsasModel.n_variables`, `GsasModel.n_observations` | how many parameters the run refined, and over how many channels |
| `GsasModel.unsupported` | one line per thing the read could not carry, kept whether or not you asked |
| `GsasModel.histogram`, `GsasModel.profile` | pick one histogram, or one pair's refined profile; both refuse to choose when the file carries several and you named none |

A phase is `GsasPhase`:

| Field | What it holds |
|---|---|
| `GsasPhase.number`, `GsasPhase.name` | its `CRS` ordinal and the name the file gives it |
| `GsasPhase.space_group` | the symbol, as written |
| `GsasPhase.cell` | the lattice, its esds and its one refine flag |
| `GsasPhase.atoms` | the sites |
| `GsasPhase.kind`, `GsasPhase.magnetic` | GSAS's phase type, and whether it is one of the two magnetic ones |
| `GsasPhase.formula` | the `CHMF` unit-cell contents, per species |

Its lattice is a `GsasCell`:

| Field | What it holds |
|---|---|
| `GsasCell.a`, `GsasCell.b`, `GsasCell.c`, `GsasCell.alpha`, `GsasCell.beta`, `GsasCell.gamma` | the lattice |
| `GsasCell.esd_a`, `GsasCell.esd_b`, `GsasCell.esd_c`, `GsasCell.esd_alpha`, `GsasCell.esd_beta`, `GsasCell.esd_gamma` | their esds, where the run produced them |
| `GsasCell.volume`, `GsasCell.volume_esd` | the cell volume |
| `GsasCell.refined`, `GsasCell.damping` | GSAS refines the cell as metric tensor elements under one flag, so there is one here rather than six |

Each of its sites is a `GsasAtom`:

| Field | What it holds |
|---|---|
| `GsasAtom.label`, `GsasAtom.species` | the name you chose and the scattering species, in the file's own upper case |
| `GsasAtom.x`, `GsasAtom.y`, `GsasAtom.z`, `GsasAtom.occupancy`, `GsasAtom.multiplicity` | the site |
| `GsasAtom.uiso` | the isotropic displacement in Å², or `None` for an anisotropic site |
| `GsasAtom.uij`, `GsasAtom.anisotropic` | the six anisotropic values, or `None` |
| `GsasAtom.refine_xyz`, `GsasAtom.refine_u`, `GsasAtom.refine_occupancy` | the `X`, `U` and `F` letters from the file's own refine codes |
| `GsasAtom.damping` | the per-group damping codes |

A histogram is `GsasHistogram`:

| Field | What it holds |
|---|---|
| `GsasHistogram.number`, `GsasHistogram.kind` | its ordinal and GSAS's `HTYP`, such as `PXC` for powder X-ray at constant wavelength |
| `GsasHistogram.is_powder`, `GsasHistogram.is_constant_wavelength` | that type, read for you |
| `GsasHistogram.data_file`, `GsasHistogram.instrument_file` | the pattern and `.prm` it points at, as the file spells them |
| `GsasHistogram.bank`, `GsasHistogram.anode` | the detector bank, and the anode `IRAD` names |
| `GsasHistogram.wavelengths` | the emission lines, Kα1 first |
| `GsasHistogram.zero`, `GsasHistogram.refine_zero` | the zero correction and its flag |
| `GsasHistogram.polarization`, `GsasHistogram.polarization_type` | the polarization fraction and its type code |
| `GsasHistogram.ka2_ratio` | the Kα2/Kα1 ratio, or `None` where the field is blank |
| `GsasHistogram.excluded_regions` | what the run left out, GSAS's spacer pair dropped |
| `GsasHistogram.two_theta_range` | the range the data covers |
| `GsasHistogram.n_channels_used`, `GsasHistogram.n_channels_total` | how many points were fitted, of how many recorded |
| `GsasHistogram.scale`, `GsasHistogram.refine_scale` | the histogram scale and its flag |
| `GsasHistogram.background` | the background function and its coefficients |
| `GsasHistogram.default_profiles` | the profile sets the instrument file supplied, which is where the histogram *started* |
| `GsasHistogram.rwp`, `GsasHistogram.rp` | this histogram's own indices |

A phase-and-histogram pair is a `GsasHap`:

| Field | What it holds |
|---|---|
| `GsasHap.phase`, `GsasHap.histogram` | which pair this is |
| `GsasHap.phase_fraction`, `GsasHap.refine_phase_fraction` | the phase fraction and its flag |
| `GsasHap.profile` | the refined profile for this pair |
| `GsasHap.preferred_orientation` | the March-Dollase rows, each with its axis and flag |
| `GsasHap.extinction`, `GsasHap.refine_extinction` | the powder extinction coefficient |

Its profile is a `GsasProfile` of `GsasProfileTerm` rows:

| Field | What it holds |
|---|---|
| `GsasProfile.function`, `GsasProfile.n_coefficients`, `GsasProfile.cutoff`, `GsasProfile.damping` | which GSAS profile function, over how many coefficients |
| `GsasProfile.terms` | the coefficients, named |
| `GsasProfile.by_name` | the same, keyed by GSAS's name for each |
| `GsasProfile.refined_names` | the ones the run was free to move, which is the protocol |
| `GsasProfileTerm.name`, `GsasProfileTerm.index` | GSAS's name for the coefficient and its 1-based position |
| `GsasProfileTerm.value`, `GsasProfileTerm.refined` | the file's own number, and its flag |
| `GsasProfileTerm.degrees` | the same quantity in degrees, or `None` where the unit is compound |

The background is a `GsasBackground`:

| Field | What it holds |
|---|---|
| `GsasBackground.function`, `GsasBackground.n_coefficients` | which of GSAS's background functions, over how many terms |
| `GsasBackground.coefficients` | the terms themselves |
| `GsasBackground.refined`, `GsasBackground.damping` | whether the run refined them |

Three things about a `.EXP` decide how you read one.

#### Coefficient names depend on the profile function

GSAS's constant-wavelength
function 2 has `LX` fourth and function 3 has `GP` fourth, so the names come from
the function the file declares. A function this build cannot name is refused
rather than read positionally, because a mis-assigned width is a plausible wrong
answer rather than an error.

#### The coefficients are in centidegrees

`GsasProfileTerm.degrees` is the
conversion, and it is `None` for the `L11`…`L23` anisotropic terms, whose unit
also involves `d²`. `None` there means no conversion was made, not that the
value is zero.

#### A blank field is not a zero

`GsasHistogram.ka2_ratio` is the case that
catches people: both a polarization fraction and a Kα2/Kα1 ratio are
conventionally 0.5, and they sit in adjacent fields on the same record. Where
the file leaves the ratio blank this reads `None`, and choosing a ratio is then
yours to do explicitly.

The converse holds too. A field that is written but is not a number is not
blank, and the read is refused rather than returning `None`. The message names
the file, the record key, the card columns and the text. A record like that is
misaligned or corrupt, so nothing on it can be trusted by column. The `.prm`
reader shares the record grammar and refuses the same way. A field of nothing
but asterisks is the exception with a known cause: it is Fortran's output for a
value too wide for its field, so the writer had the number and ran out of
columns. In a required field, such as a cell edge or a `.prm`'s `LAM1`, the
read is refused and the message says overflow. In an optional one, such as an
esd or the history Rwp, the field reads as `None` and the reader reports
`GSAS_FIELD_OVERFLOW` on its `diagnostics=` list, naming the record and the
columns. One case no
per-field rule can catch: a number that spills across a field boundary and
leaves two readable halves, such as a left-aligned `46.60` read as `46` and
`.60`.

`read_gsas2_gpx` returns a `Gsas2Model`. A GSAS-II project is the same shape of
tree as a `.EXP`: phases, histograms, and one entry per phase-and-histogram
pair. It carries two things the older format has no room for. One is the set of
constraints the refinement ran under. The other is the list of variables it
actually refined.

| Field | What it holds |
|---|---|
| `Gsas2Model.path`, `Gsas2Model.saved_as`, `Gsas2Model.version` | the file you opened, where GSAS-II last saved it, and the revision that wrote it |
| `Gsas2Model.phases`, `Gsas2Model.histograms` | every phase, and every powder histogram |
| `Gsas2Model.hap` | the phase-and-histogram entries, keyed `(phase name, histogram name)`. Those are GSAS-II's own keys, which are names rather than numbers |
| `Gsas2Model.vary_list`, `Gsas2Model.esds` | the variables the last refinement refined, in GSAS-II's `p:h:name` spelling, and their standard uncertainties in the same order. This is the protocol, stated by the file itself |
| `Gsas2Model.constraints` | the equivalences, holds and constraint equations, with their variables resolved into names |
| `Gsas2Model.rwp`, `Gsas2Model.gof`, `Gsas2Model.chi2` | the run's own agreement indices. `gof` is the square root of reduced χ². `chi2` is GSAS-II's `chisq`, which is Σw(Io−Ic)² and not reduced at all |
| `Gsas2Model.n_observations`, `Gsas2Model.n_variables`, `Gsas2Model.converged` | how many channels, how many parameters, and whether GSAS-II called it converged. `n_variables` is `None` where the file's `Rvals` does not state it, which happens |
| `Gsas2Model.unsupported` | one line per thing the read could not carry, kept whether or not you asked |
| `Gsas2Model.histogram`, `Gsas2Model.phase` | pick one by name or by number; both refuse to choose when the file carries several and you named none |

A phase is a `Gsas2Phase`:

| Field | What it holds |
|---|---|
| `Gsas2Phase.name`, `Gsas2Phase.number` | the name GSAS-II gives it, and its `pId`, which is the `p` of a `p:h:name` variable |
| `Gsas2Phase.space_group` | the symbol, as written |
| `Gsas2Phase.space_group_from_operators`, `Gsas2Phase.resolved_space_group` | the setting the project's own operators describe, and the symbol to build under. The second is the first where the file settled one, and `space_group` otherwise. GSAS-II writes the operations themselves, so a symbol like `F d d d` that the tables hold in two settings is read rather than assumed. `to_structure` builds under `resolved_space_group`, and `GSAS2_GPX_SETTING_FROM_OPERATORS` says when the two differ |
| `Gsas2Phase.cell`, `Gsas2Phase.volume` | the six lattice parameters and the cell volume |
| `Gsas2Phase.refine_cell` | GSAS-II refines a cell under one flag, so there is one here rather than six |
| `Gsas2Phase.atoms` | the sites |
| `Gsas2Phase.kind`, `Gsas2Phase.magnetic` | GSAS-II's phase type, and whether it is a magnetic one |
| `Gsas2Phase.magnetic_partner` | set where a *nuclear* phase is half of a magnetic model. The sites import correctly. The magnetic scattering in the file's own Rwp does not, so a fit of this structure is not comparable with the file's figures |
| `Gsas2Phase.pawley` | whether the phase was fitted by Pawley extraction, in which case its refined quantities are intensities rather than sites |

Each of its sites is a `Gsas2Atom`:

| Field | What it holds |
|---|---|
| `Gsas2Atom.label`, `Gsas2Atom.species` | the name you chose and the scattering species, in the file's own spelling. GSAS-II writes an ionic charge sign first, as `Mn+3` |
| `Gsas2Atom.x`, `Gsas2Atom.y`, `Gsas2Atom.z`, `Gsas2Atom.occupancy` | the site |
| `Gsas2Atom.site_symmetry`, `Gsas2Atom.multiplicity` | what GSAS-II worked out about the position |
| `Gsas2Atom.adp`, `Gsas2Atom.anisotropic` | `I` or `A`, and that flag read for you |
| `Gsas2Atom.uiso`, `Gsas2Atom.uij` | the isotropic displacement in Å², and the six anisotropic values |
| `Gsas2Atom.refine_flags` | the letters the file carries, such as `XU`. An empty string is the file saying *held* |
| `Gsas2Atom.refine_xyz`, `Gsas2Atom.refine_u`, `Gsas2Atom.refine_occupancy`, `Gsas2Atom.refine_moment` | those letters read one at a time |

A histogram is a `Gsas2Histogram`:

| Field | What it holds |
|---|---|
| `Gsas2Histogram.number`, `Gsas2Histogram.name` | its `hId` and the tree label, which is the key `Gsas2Model.hap` uses |
| `Gsas2Histogram.kind`, `Gsas2Histogram.constant_wavelength` | GSAS-II's type code, such as `PXC`, and whether this build names its coefficients |
| `Gsas2Histogram.terms`, `Gsas2Histogram.by_name` | the instrument coefficients, and the same keyed by GSAS-II's name for each |
| `Gsas2Histogram.wavelengths` | the emission lines, primary first |
| `Gsas2Histogram.limits`, `Gsas2Histogram.measured_limits` | the range the refinement used, and the range the file was loaded with. Two numbers rather than one, because that pair is what makes a narrowed range visible |
| `Gsas2Histogram.excluded_regions` | ranges masked out of the fit |
| `Gsas2Histogram.background` | the background function and its coefficients |
| `Gsas2Histogram.sample` | the refinable sample parameters with their flags, keyed by GSAS-II's own names (`Scale`, `DisplaceX`, `Shift`, `Absorption` and their kind) |
| `Gsas2Histogram.geometry`, `Gsas2Histogram.gonio_radius`, `Gsas2Histogram.temperature` | `Debye-Scherrer` or `Bragg-Brentano`, the radius in mm, and the temperature |
| `Gsas2Histogram.n_points` | how many channels the file carries |

An instrument coefficient is a `Gsas2Term`:

| Field | What it holds |
|---|---|
| `Gsas2Term.name` | GSAS-II's own name, such as `U` or `SH/L` |
| `Gsas2Term.value`, `Gsas2Term.initial` | the refined number and the one it started from, which the format keeps side by side |
| `Gsas2Term.refined` | whether the run was free to move it |
| `Gsas2Term.degrees` | the same quantity in degrees for the six centidegree coefficients, and `None` for everything else. `Zero` is `None` because it is already degrees. GSAS-I writes that field in centidegrees and GSAS-II does not |

The background is a `Gsas2Background`:

| Field | What it holds |
|---|---|
| `Gsas2Background.function` | GSAS-II's own name for it, such as `chebyschev-1` |
| `Gsas2Background.coefficients`, `Gsas2Background.refined` | the terms, and whether the run refined them |
| `Gsas2Background.n_debye`, `Gsas2Background.n_peaks` | how many diffuse terms and fitted background peaks sat beside them |

A phase-and-histogram pair is a `Gsas2Hap`:

| Field | What it holds |
|---|---|
| `Gsas2Hap.phase`, `Gsas2Hap.histogram` | which pair this is |
| `Gsas2Hap.scale`, `Gsas2Hap.used` | the phase's scale in this histogram, and whether the pair was in the fit at all |
| `Gsas2Hap.size`, `Gsas2Hap.mustrain` | the sample broadening, which GSAS-II refines per pair |
| `Gsas2Hap.hstrain` | the hydrostatic-strain terms |
| `Gsas2Hap.preferred_orientation` | the model, its value, its flag and its axis |
| `Gsas2Hap.extinction` | the extinction coefficient |
| `Gsas2Hap.lebail` | whether this pair's intensities were extracted rather than calculated |

Size and microstrain are each a `Gsas2Broadening`:

| Field | What it holds |
|---|---|
| `Gsas2Broadening.kind` | `isotropic`, `uniaxial` or `generalized`. Read this first |
| `Gsas2Broadening.values` | the direct numbers with their flags: a size in µm, a microstrain in units of 1e-6 |
| `Gsas2Broadening.axis` | the unique axis a uniaxial model uses |
| `Gsas2Broadening.terms` | the hkl-dependent coefficients. The format writes this row whatever the model, so on an isotropic one it is the unused default rather than a second opinion |

A constraint is a `Gsas2Constraint`:

| Field | What it holds |
|---|---|
| `Gsas2Constraint.kind` | the format's own letter: `e` equivalent variables, `c` a constraint equation, `h` a variable held, `f` a new variable |
| `Gsas2Constraint.group` | which variables it constrains: `Phase`, `Hist`, `HAP` or `Global` |
| `Gsas2Constraint.terms` | `(multiplier, name)` pairs, the names resolved out of the random-number ids the file stores |
| `Gsas2Constraint.value`, `Gsas2Constraint.vary` | the right-hand side of a constraint equation, and whether a new variable is refined |
| `Gsas2Constraint.is_equivalence` | the one shape `Refinement.tie_equal` reproduces in one call |

Anything with a flag beside it is a `Gsas2Value`, which is `Gsas2Value.value`
and `Gsas2Value.refined` and nothing else.

Three things about a `.gpx` decide how you read one.

#### It is a pickle, so the reader refuses names rather than running them

A `.gpx` is a sequence of python pickles, and loading a pickle runs whatever it
names. So this reader resolves an allow-list and refuses every other name,
naming it, without reading the file at all. That covers GSAS-II's own two
classes too. They are admitted as inert stand-ins that can hold data and do
nothing, which is why a project with constraints reads at all. If you are handed
a `.gpx` from somewhere you do not trust, this is the property to know about:
the refusal message names the global, and a file that opens has named nothing
outside the list.

#### The profile coefficients are centidegrees and the zero correction is not

`Gsas2Term.degrees` is the conversion, and it exists for `U`, `V`, `W`, `X`, `Y`
and `Z` only. `Zero` is already in degrees, which is where the two GSAS
generations differ from each other, so a `None` there means "no conversion was
needed" rather than "no conversion was made".

#### What `to_structure` refuses, it refuses by name

A magnetic phase, a macromolecular one, a Pawley phase, a phase with
anisotropic sites, a phase with no sites at all, and a phase whose stored `Uiso`
is negative. The last two are what a corpus of real projects contains and a
specification never mentions: GSAS-II fits a phase with no sites by extracting
its intensities, and a refinement really can end with a negative displacement
parameter. Each refusal names the phase and leaves the numbers on the model,
because deciding what a negative `Uiso` should have been is yours.

### Which formats this build reads

`rx.capabilities()` publishes the registry, so a client asks rather than
guesses:

```python
import rietx as rx

caps = rx.capabilities()
[(f.name, f.extensions, f.reports_at) for f in caps.project_formats]
```

| Field | What it holds |
|---|---|
| `Capabilities.project_formats` | one `ProjectFormatCapability` per format, in dispatch order |
| `ProjectFormatCapability.name`, `ProjectFormatCapability.title` | the registry key, and what a person calls it |
| `ProjectFormatCapability.extensions` | the conventional suffixes, which are informational and never the dispatch |
| `ProjectFormatCapability.sniff` | how the format is recognised, in words |
| `ProjectFormatCapability.carries` | what the file holds beyond a structure; read this before reading a model you have no common shape for |
| `ProjectFormatCapability.reports_at` | `"read"`, `"build"` or `"both"`: which call takes your `diagnostics=` list |
| `ProjectFormatCapability.writes` | the top-level verb that writes this format, or `None` where this build has no writer for it |
| `ProjectFormatCapability.refuses` | set when the build recognises a format in order to decline it, carrying why |

`reports_at` is a real difference and not bookkeeping. A `.inp`'s repairs, such
as a rewritten species spelling or a translated origin suffix, happen while
parsing, so its channel is `read_project_model(..., diagnostics=notes)`. A
`.pcr`'s all happen while codewords become a `Structure`, so its channel is
`ProjectModel.to_structure(diagnostics=notes)`. A `.EXP` repairs at both ends
and declares `"both"`. It reports the histograms it could not carry while
parsing, and the species it normalises while building. Passing a list to both
calls collects any of the three without your having to know which.

Passing your list to the wrong call still does not lose the read's half.
Whatever the read reported is on `ProjectModel.diagnostics` as well, filled list
or no list. That matters more than it sounds. An empty list reads as "this file
needed no repairs", and a caller who had passed it to the other call would
believe it.

`writes` is a name rather than a flag, so a client learns what to call and not
only that something is possible. It is `None` where this build has no writer,
which is `.gpx` today, and `None` rather than `False` on purpose: a `False`
would be an answer about a format nobody had wired.

The same facts are in the registry the arm is built from. `ProjectFormat.name`,
`ProjectFormat.title`, `ProjectFormat.extensions`, `ProjectFormat.sniff`,
`ProjectFormat.carries`, `ProjectFormat.reports_at` and `ProjectFormat.refuses`
carry the declarations, while `ProjectFormat.matches`, `ProjectFormat.read`,
`ProjectFormat.to_structure` and `ProjectFormat.write` are the callables the
dispatch and the writers use.

### What a reader will not guess

These formats hold constructs this package has no model for, and dropping one
changes the model rather than its presentation. So every construct the TOPAS
reader knows about is a `Feature` carrying a declared `Stance`, a keyword with
no stance fails a test instead of vanishing, and what a particular file turned
out to contain comes back as a `Coverage` of `Hit` rows:

```python
from rietx.io.projects import coverage
```

| Name | What it is |
|---|---|
| `Stance.READ` | carried into the model |
| `Stance.IGNORED` | deliberately not carried, and harmless |
| `Stance.REPORTED` | met, not carried, and named in the diagnostics |
| `Stance.REFUSED` | met, and the file is refused rather than returned half-built |
| `Feature.name`, `Feature.what`, `Feature.why` | one construct, what it is and the argument for its stance |
| `Feature.stance`, `Feature.keywords` | the stance, and the format keywords it governs |
| `Hit.feature`, `Hit.keywords`, `Hit.phases` | one construct actually met in a file, and where |
| `Coverage.reported`, `Coverage.refused`, `Coverage.partial` | the hits of each kind |
| `Coverage.summary`, `Coverage.summary_of` | those hits in a sentence |

A refused construct raises, naming the file and the line. A reported one
arrives on the diagnostics channel, and without a list the read is silent and
identical, on the same opt-in terms as every other reader here.

## The `.rex` project directory

A project is the one durable thing a session can point at. It is a directory
rather than an archive:

```text
my_sample.rex/
    project.json        settings and the data reference
    11BM_NAC.fxye       the pattern file, byte for byte as measured
    history.jsonl       the refinement DAG, append-only
    live/               one directory per run, for `rietx watch`
        20260915-092640-80245/
        20260915-101302-80245/
    exports/            CIFs, reflection tables, QPA tables
```

`live/` holds one directory per run. Two writers on one project, a GUI session
and an agent fitting the same directory, would otherwise interleave their events
into a single file.

A directory because the history log's crash safety is append-only writes by one
writer. Zipping would force a rewrite on every save and lose exactly the
property that makes a JSONL log recoverable and tailable while a fit runs.

<!-- api-doc: no-exec — it creates a directory from the reader's own files -->
```python
project = rx.Project.create("my_sample.rex", pattern="my_sample.xye",
                            structure=structure, instrument=instrument)
project.fit()
project.save()

project = rx.Project.open("my_sample.rex")
```

`Project.create` builds the directory around a pattern file and a model.
`Project.open` reads one back and resumes at the history head. It re-checks
every binding on the way rather than assuming it: the pattern file is still
there, its bytes still hash to the recorded digest, this build still parses those
bytes to the recorded numbers, and the history was recorded against that same
pattern. Each of the four raises with its own message, because each has a
different cause and a different fix.

### A project with no structure

`structure=` may be left out. What you get is a pattern-only project: zero
phases, for a pattern whose phase you do not know yet.

<!-- api-doc: no-exec — it creates a directory from the reader's own files -->
```python
project = rx.Project.create("unknown.rex", pattern="unknown.xye",
                            instrument=instrument)
```

Peak picking and indexing work over it, the parameter table holds the instrument
and the background, and the routes out of it both end in a phase: index the
peaks and adopt a candidate cell ([](indexing.md)), or build a Le Bail scaffold
from a space-group symbol and the cell parameters that setting leaves free
(`rietx.schemas.structure.lebail_scaffold`). In the GUI it is the third answer
to the wizard's structure step.

What it cannot do is refine. A phase reaches the pattern only through
`scale × |F|² × profile`, so with no phase there is nothing but the background
to fit, and a plan run over one converges on the background and reports
success. `fit`, `run_stage`, `refine_multi` and `refine_sequential` therefore
raise `NoPhasesError` before they start. `NoPhasesError.code` is the string
`NO_PHASES` on every surface: the agent envelope's fourth error code, and the
GUI's reason for a disabled Run button.

```python
import rietx as rx

print(rx.NoPhasesError.code)
```

```text
NO_PHASES
```

`Refinement.predict` still works, because evaluating the background as it stands
is not a refinement.

An open project holds the session as six attributes.

| Attribute | Holds |
|---|---|
| `Project.path` | the project directory |
| `Project.doc` | the `ProjectDoc`, which is `project.json` in memory |
| `Project.data` | the `PatternData` read back from the copied file |
| `Project.refinement` | the `Refinement`, positioned at the history head |
| `Project.history` | that refinement's `RefinementTree` |
| `Project.data_diagnostics` | what the reader repaired or assumed on the last read |

`Project.data_diagnostics` is held in memory and is not a `project.json` field.
The repairs are a function of the bytes, the reader and its options, and the
data reference below already records all three.

Every verb that changes a project writes into its directory as it runs, and
`Project.open` appends a line to the log before any verb is called. There is
no read-only way to open one. To look at a project without changing it, open a
copy: `rietx gui PROJECT.rex --scratch` copies the directory to a temporary
one and opens that, printing where it went ([](cli.md)). The copy is
byte-for-byte, so it opens exactly as the original does.

Each fact has one authority. `project.json` holds the settings: the selected
plan and mode, the 2θ limits, the excluded regions, and the GUI's own `ui` keys.
`history.jsonl` holds the model state, and its head is the working state. No
parameter value is written in both places.

Saving persists settings, and is not what makes the work durable. Every verb
that changes the model commits a history node the moment it runs, so the work is
on disk whether or not anyone calls `Project.save`. What `save` persists is the
half of a session that nothing else owns.

`ProjectDoc` is that half, field by field.

| Field | Holds |
|---|---|
| `ProjectDoc.patterns` | the data references, one per pattern |
| `ProjectDoc.plan` | the plan the next run will use, as a `PlanSpec` |
| `ProjectDoc.mode` | the intensity mode the next run will use |
| `ProjectDoc.two_theta_limits` | the range the next run will fit |
| `ProjectDoc.excluded_regions` | 2θ regions masked out of the residual |
| `ProjectDoc.indexing` | the next indexing run's controls |
| `ProjectDoc.history_file` | the log's filename inside the directory |
| `ProjectDoc.format_version` | the version of the `.rex` format |
| `ProjectDoc.package_version` | the version of rietx that wrote it |
| `ProjectDoc.created_utc`, `ProjectDoc.updated_utc` | when it was created, and last saved |
| `ProjectDoc.ui` | keys a front end persists, untyped |

The three settings after the plan are what `fit` and `run_stage` will be called
with. A history node records a mode and limits too, and that is a different
fact: the node says what a past run used, the document says what the next one
will use. Before the first run there is no node to ask.

`ProjectDoc.patterns` is a list because stacking several patterns into one joint
residual is a later milestone's work. A project holds one today, and
`Project.open` refuses a document carrying more rather than opening the first
and looking like it worked.

`ProjectDoc.ui` is untyped deliberately. A front end owns those keys, and the
container only stores them, so a layout change is not a schema change.

The pattern is copied verbatim rather than re-serialised, because the bytes are
the contract: the reader takes σ from the file's own column and never overrides
it. `Project.data_ref` returns the `DataRef` that makes those bytes trustworthy
on re-open. It carries `DataRef.sha256` of the file, `DataRef.fingerprint` of
the parsed arrays, and `DataRef.reader` with `DataRef.options`. The reader
call itself is part of the reference, because a pdCIF is a different pattern
depending on the block. Agreeing bytes with a disagreeing fingerprint mean the
reader changed, not that the project is corrupt.

Four more fields say what the pattern is: `DataRef.filename` names it inside the
directory, `DataRef.n_points` and `DataRef.two_theta_range` describe it, and
`DataRef.has_sigma` records whether σ was measured or fell back to Poisson. That
last one is a correctness property of every fit in the project and is invisible
once the data are read, so it is written down.

`Project.set_excluded_regions` records regions to leave out of the fit. They
live in the document rather than in a history node because they are protocol
that is in neither the file nor the model: a node cannot say what was excluded
when it ran. `Project.fitted_mask` is the one authority for which channels the
next run fits. An inverted or empty interval is refused rather than reordered.

The two settings compose. On the 11-BM pattern of [](quickstart.md), limits of
2–24° leave 22 003 of 59 498 channels in the residual, and excluding 7.4–7.6°
as well leaves 21 803.

`Project.exports_dir` and `Project.live_dir` are where the last two directories
live, and `Project.parameters`, `Project.fit` and `Project.run_stage` are the
session verbs, with the same meaning they have on `Refinement`.

## Run directories

A fit that did not come from a project records under `.rietx/runs/` in the
working directory, one directory per fit, named for the date, the time and the
process id:

```text
.rietx/runs/
    .gitignore                      contains `*`, so runs stay out of `git status`
    20260915-092640-80245/
        events.jsonl                one line per event
        snapshot.json               the stage's curves, ticks and statistics
        summary.txt                 the termination view
        meta.json                   label, start time, version, cwd, command
        status.json                 state, pid, host, heartbeat, stage, Rwp, gof
        run.lock                    held by the writing process for its life
```

Two directories are spelled `.rietx` and they have nothing to do with each
other. `$HOME/.rietx` is the GUI's per-user state, the recent list and the theme,
and `--state-dir` or `RIETX_STATE_DIR` moves it. The one above is the runs root,
it is relative to wherever the process is running, and no environment variable
moves it. To put runs elsewhere, name a root per call with `telemetry=`
([](refining.md)).

A fit you run inside somebody else's package leaves `.rietx/` in their working
directory. That is the working directory doing its job rather than a bug, and
`RIETX_TELEMETRY=0` is how a process declines.

### What a run directory contains

Every free parameter's value at every recorded evaluation, in `events.jsonl`,
alongside the stage boundaries and the statistics at each one. `snapshot.json`
holds the observed, calculated and difference curves for the stage, decimated
for drawing.

No pattern bytes are ever copied into a run. The curves in a snapshot are
decimated to a drawing budget of 4000 points, the same budget the GUI and the
comparison UI use, so a long pattern reaches a run as a picture of itself. A
short one arrives nearly whole: a 4200-point pattern kept 4143.

The parameter trajectory is the part to weigh before writing runs to a shared
filesystem, and `RIETX_TELEMETRY=0` is how you decline ([](refining.md)).

## The history log

`history.jsonl` is an append-only record of the refinement DAG, one JSON object
per line. `RefinementTree.save` and `RefinementTree.load` are the file
interface, `RefinementTree.records` is what gets written, and
`RefinementTree.summary` prints the tree. [](history.md) is the DAG itself: what
a node holds, and the verbs that restore, fork and merge one.

Each line is a `HistoryRecord`, a tagged union of the three things the log
carries. The tag is what keeps the file append-only: a reader branches on it
rather than on the file's shape, so a new line never invalidates the ones before
it.

| Field | Is | Reads as |
|---|---|---|
| `HistoryRecord.record` | `"header"`, `"node"` or `"annotation"` | the tag. Branch on this and read the matching field |
| `HistoryRecord.header` | a `TreeHeader`, on the first line only | the tree's identity and the fingerprint pinning it to one pattern |
| `HistoryRecord.node` | a `HistoryNode` | one state, appended when a stage or an edit commits |
| `HistoryRecord.annotation` | an `Annotation` | a tag or a note attached to a node afterwards, so it is a separate line rather than a field on the node |

The other three fields are null on any given line. A tag applied to a node that
was written an hour ago appends an annotation line; it never rewrites the node.

A node stores state and not curves. A node is about 10 kB; embedding the
calculated pattern would make it 1.24 MB. Le Bail extracted intensities are the
exception, because they live outside the parameter vector and are
path-dependent, so they are serialized per node.

The tree branches. A stage adds a node under the head, a model edit adds one
too, and `Refinement.checkout` moves the head back so the next fit forks
instead of continuing:

```{mermaid}
graph TD
  root["root<br/>initial model"] --> n1["fit: lebail<br/>Rwp 0.113"]
  n1 --> n2["edit: add CaF₂ phase"]
  n2 --> n3["fit: rietveld<br/>Rwp 0.093"]
  n1 --> n4["fit: rietveld<br/>no impurity<br/>Rwp 0.141"]
```

`RefinementTree.to_mermaid` prints that diagram for a real tree, in the same
syntax, so you can paste it into any markdown that renders mermaid:

<!-- api-doc: no-exec — it needs a refinement that has run -->
```python
print(ref.history.to_mermaid())
```

## Exports

Three writers turn a result into a file someone else can read:

| Call | Writes |
|---|---|
| `write_refinement_cif` | the refined structure and fit as a CIF |
| `write_reflection_table` | one row per (emission line, reflection): hkl, d, 2θ, \|F\|², intensity |
| `write_qpa_table` | the quantitative phase analysis |

[](exports.md) has the rows those last two are made of, and the same three
writers as methods on `Refinement`.

The CIF is the one a journal asks for, so it carries more than the coordinates.
Per phase it writes the agreement indices of
[](results.md) as `_refine_ls_R_I_factor` (R_B), `_refine_ls_R_factor_all` (R_F)
and `_refine_ls_number_reflns`, and the geometry as `_geom_bond_`,
`_geom_contact_` and `_geom_angle` loops with esds in su notation. Each
`_geom_*_site_symmetry_*` code indexes a `_space_group_symop_` loop written
into the same block, because a code that pointed at whatever order the reader's
own library generated would name a different atom. The loops list each bond
once, unlike `GeometryTable`, whose audience is a chemist counting neighbours
rather than a parser. Take `structure` from `Refinement.fitted_structure`, which
is where the refined values and their esds are.

`viz.html.write_html` writes the interactive page, and `RefinementResult.plot`
writes the static figure. The page needs nothing beyond a base install. The
figure needs the `viz` extra.

:::{admonition} For agents
:class: agent
`Capabilities.project_format_version` versions the `.rex` directory, and
`Capabilities.textdoc_format_version` versions `.rxt`, the line-oriented text
rendering of a project that the GUI edits. Both move independently of the
package version. See [](agents.md).
:::
