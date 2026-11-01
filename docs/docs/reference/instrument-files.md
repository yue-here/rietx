# Instrument files

This page gives the instrument files rietx reads and writes: its own JSON instrument profile, the GSAS-I `.prm` and GSAS-II `.instprm` of a constant-wavelength instrument, and the GSAS-I `.iparm` and GSAS-II `.instprm` of a time-of-flight bank.

Every reader on this page returns an `Instrument` with every parameter `vary=False`.
An instrument-parameter file is a calibration refined against a standard, so it is data rather than a starting guess.
Freeing the zero shift or a bank's DIFC beside a free cell reopens the correlation the calibration was made to remove.
[The instrument](instrument.md) gives the fields each reader fills.
[How to calibrate an instrument on a standard and reuse it](../guides/calibrate.md) gives the procedure the profile file serves.

Each reader and writer takes `diagnostics=`.
Pass a list and the reader's assumptions and dropped fields come back in it.
Pass none and the read is silent and returns the same instrument.
[Diagnostics: reading files](diagnostics-files.md) gives every code this page names.

## Instrument profile

`save_instrument_profile` writes an instrument as a JSON file, and `load_instrument_profile` reads it back with every parameter `vary=False`.

```python
import json
import tempfile
from pathlib import Path

import rietx as rx

folder = Path(tempfile.mkdtemp())
rx.save_instrument_profile(rx.Instrument.bragg_brentano(radiation="CuKa"),
                           folder / "cu_ka.json")
print(sorted(json.loads((folder / "cu_ka.json").read_text())))
instrument = rx.load_instrument_profile(folder / "cu_ka.json")
print(instrument.geometry.kind, instrument.profile.w.vary)
```

```text
['created_utc', 'instrument', 'instrument_profile', 'schema_version']
bragg_brentano False
```

`instrument_profile` is the format tag, and a file without it is refused.
`schema_version` is the package schema the file was written under.

The file leaves out what belongs to one specimen rather than to the diffractometer:

- the background, which comes back as a fresh default `BackgroundChebyshev`;
- the extra components, including a holder peak;
- the specimen displacement and transparency, which come back at 0;
- surface roughness, µR with the capillary radius, and µt with the thickness, which come back absent.

`load_instrument_profile` takes `diagnostics=`.
A profile saved by an earlier release can store a parameter with no range, where that release's field had none.
Reading it restores the field's range and reports [`DECLARED_RANGE_RESTORED`](diagnostics-refinement.md#declared_range_restored).
A stored value outside the restored range is left as stored and reported as [`DECLARED_RANGE_NOT_RESTORED`](diagnostics-refinement.md#declared_range_not_restored).
A profile with no `schema_version` predates the stamp and is read as the oldest.

A time-of-flight bank is refused by both functions, because its parameters would not come back held.

The GUI writes and reads the same file from the Model panel, with `Save profile…` and `Load profile…`.
Saving puts the file in the project's `exports/` directory.
It needs a model and no fit, since the profile describes the instrument as it stands.

## GSAS-I .prm

`read_gsas_prm` reads a GSAS-I instrument-parameter file (Larson & Von Dreele, *GSAS*, LAUR 86-748) and `write_gsas_prm` writes one.
It is the text file an APS 11-BM mail-in measurement ships beside its pattern.

```python
import tempfile
from pathlib import Path

import rietx as rx

folder = Path(tempfile.mkdtemp())
rx.write_gsas_prm(rx.Instrument.debye_scherrer(wavelength=0.4139090),
                  folder / "beamline.prm", header="LaB6")
notes = []
instrument = rx.read_gsas_prm(folder / "beamline.prm", diagnostics=notes)
print(instrument.geometry.kind, instrument.source.lines[0].wavelength.value)
for note in notes:
    print(note.code)
```

```text
debye_scherrer 0.413909
GSAS_PRM_FIELD_DROPPED
GSAS_PRM_FIELD_DROPPED
GSAS_PRM_GEOMETRY_ASSUMED
```

### Reading a .prm

The reader takes one bank of two histogram types, each with GSAS profile function 3:

- `HTYPE PXCR`, constant-wavelength X-ray, read onto `Instrument.debye_scherrer`;
- `HTYPE PNCR`, constant-wavelength neutron, read onto `Instrument.constant_wavelength_neutron` at the file's `LAM1`.

Every record is read by column, in the columns the GSAS manual gives.
The coefficients convert as follows.

| File field | rietx field | Conversion |
|---|---|---|
| `LAM1` | `Source.lines` entry 0 | none, Å |
| `LAM2` with `KRATIO` | `Source.lines` entry 1, its `EmissionLine.weight` | none; `KRATIO` is the Kα2/Kα1 intensity ratio |
| `POLA` | `Source.polarization` | none |
| `GU`, `GV`, `GW` | `ProfileTCHZ.u`, `ProfileTCHZ.v`, `ProfileTCHZ.w` | × 8 ln 2 × 10⁻⁴: a Gaussian variance in centidegrees² to a Gaussian FWHM² in degrees² |
| `LX`, `LY` | `ProfileTCHZ.x`, `ProfileTCHZ.y` | × 10⁻², centidegrees to degrees |
| `S/L`, `H/L` (`PRCF` positions 7 and 8) | `Geometry.axial_sl`, `Geometry.axial_hl` | none, ratios |

A neutron source has one wavelength and no polarisation.
So a `PNCR` file's `POLA` and `KRATIO` are read and not applied, and a non-zero `LAM2` is refused.

A bank may offer several profile functions as numbered sets `PRCF1`, `PRCF2` and further, and `profile_set=` names the one to read.
Without it the reader reads set 1, as GSAS-II's importer does, and reports [`GSAS_PRM_PROFILE_SET_DEFAULTED`](diagnostics-files.md#gsas_prm_profile_set_defaulted) when the file offers more than one.

Refused by name, each with its reason:

- a file declaring more than one bank;
- `HTYPE PNTR`, a time-of-flight file, whose message points to `read_gsas_tof_iparm`, and any other histogram type;
- a profile function other than 3, under either type, because each function has its own coefficient layout; the refusal names a type-3 set when the file offers one;
- a file with no set 1;
- a `LAM2` with no `KRATIO`, since the conventional 0.5 would be the reader's number and not the file's;
- a non-zero `ZERO`, whose unit no file available here settles, and a non-zero `IPOLA`, the polarisation type;
- a non-zero `GP` (position 4) or a non-zero coefficient past position 8;
- a value outside the range `Instrument` holds, such as a negative `GW` or a `POLA` on a 0-100 scale, refused naming the file.

[`GSAS_PRM_FIELD_DROPPED`](diagnostics-files.md#gsas_prm_field_dropped) names, once per record, the fields dropped at their identity value: `IPOLA`, the refine flags and `IDAMP` on `ICONS`, `GP` and the coefficients past position 8 on `PRCF`, and the ignored `IRAD` and `ITYP` records.

A `.prm` states no geometry, and `HTYPE PXCR` covers both Bragg-Brentano and Debye-Scherrer.
The reader returns `debye_scherrer`, the 11-BM capillary its source files came from, and always reports [`GSAS_PRM_GEOMETRY_ASSUMED`](diagnostics-files.md#gsas_prm_geometry_assumed).
For a flat-plate calibration, set the geometry yourself and copy `axial_sl` and `axial_hl` across first.
A new `Geometry` starts both at 0, an instrument with no axial divergence.
The geometry matters beyond bookkeeping: `Geometry.kind` selects the position correction, and the two geometries' absorption corrections have different off states.

A GSAS `.LST` refinement output has no reader.
A GSAS `.EXP`, a TOPAS `.inp` and a FullProf `.pcr` are whole refinements, read by `read_project_model` ([How to read another program's files](../guides/foreign.md)).

### Writing a .prm

`write_gsas_prm(instrument, path, header=, diagnostics=)` writes what the reader reads back: the wavelengths with `KRATIO`, the polarisation, `GU`, `GV`, `GW`, `LX` and `LY` converted back into centidegrees, and `S/L` and `H/L`.
`GP` and the coefficients past position 8 are written at 0.
The file is written in latin-1, the encoding the reader decodes.

The refine flags are not written, and the `PRCF` header's flag columns are left blank, as a real calibration file leaves them.
[`GSAS_PRM_FIELD_NOT_WRITTEN`](diagnostics-files.md#gsas_prm_field_not_written) names what the instrument carries that the format cannot state.
The geometry is always among it, and a true-Voigt peak shape is named there too.
[`GSAS_PRM_VALUE_NARROWED`](diagnostics-files.md#gsas_prm_value_narrowed) names values cut to fit their column, since a `.prm` is read by column.

Refused by name:

- a non-zero `zero_shift`, because `ZERO`'s unit is not established and a `ZERO` wrong by 100× puts every peak in the wrong place; set it to 0 and refine it in the receiving program;
- a neutron source, because what a `PNCR` file's `POLA` and `KRATIO` should hold is spelled by one real file only;
- a third emission line, since `ICONS` holds `LAM1` and `LAM2`;
- a second line whose weight is outside 0 < w ≤ 2, the range a `KRATIO` means;
- a time-of-flight bank, and any non-finite value.

## GSAS-II .instprm

GSAS-II keeps a project in a binary `.gpx` and ships a calibration as a small text file of `key:value` lines.
`read_gsas2_instprm` reads one and `write_gsas2_instprm` writes one.

```python
import tempfile
from pathlib import Path

import rietx as rx

folder = Path(tempfile.mkdtemp())
notes = []
rx.write_gsas2_instprm(rx.Instrument.bragg_brentano(radiation="CuKa"),
                       folder / "lab.instprm", diagnostics=notes)
print([note.code for note in notes])
notes = []
instrument = rx.read_gsas2_instprm(folder / "lab.instprm", diagnostics=notes)
print(instrument.geometry.kind, len(instrument.source.lines))
print([note.code for note in notes])
```

```text
['GSAS2_INSTPRM_VALUE_FLOORED', 'GSAS2_INSTPRM_FIELD_NOT_WRITTEN']
bragg_brentano 2
['GSAS2_INSTPRM_FIELD_NOT_READ']
```

### Reading an .instprm

The reader dispatches on the file's `Type` line.
`PXC` (X-ray) and `PNC` (neutron) are constant-wavelength types, read onto `Source` and `NeutronSource`.
`PNT` is a time-of-flight bank, read as [Time-of-flight instrument files](#time-of-flight-instrument-files) describes.

| File item | rietx field | Conversion |
|---|---|---|
| `Lam`, or `Lam1` and `Lam2` | the emission lines | none, Å |
| `I(L2)/I(L1)` | the second line's `EmissionLine.weight` | none |
| `Polariz.` | `Source.polarization` | none; read for an X-ray bank, inert on a neutron bank |
| `U`, `V`, `W` | `ProfileTCHZ.u`, `ProfileTCHZ.v`, `ProfileTCHZ.w` | × 8 ln 2 × 10⁻⁴: a Gaussian variance in centidegrees² to a Gaussian FWHM² in degrees² |
| `X`, `Y` | `ProfileTCHZ.x`, `ProfileTCHZ.y` | × 10⁻², centidegrees to degrees |
| `Zero` | `Instrument.zero_shift` | none; degrees, a constant added to the calculated 2θ |
| `SH/L` | `Geometry.axial_sl` and `Geometry.axial_hl` | split evenly |
| `Diff-type` | `Geometry.kind` | `Bragg-Brentano` or `Debye-Scherrer` |
| `Gonio. radius` | `Geometry.goniometer_radius_mm` | none, mm |

`SH/L` is GSAS-II's combined (S+H)/L.
An even split is the only reading one number admits, and [`GSAS2_INSTPRM_CONVENTION_ASSUMED`](diagnostics-files.md#gsas2_instprm_convention_assumed) reports it.
A file stating no `Diff-type` takes GSAS-II's own fallback: Bragg-Brentano for a stated doublet, Debye-Scherrer otherwise, reported as [`GSAS2_INSTPRM_GEOMETRY_ASSUMED`](diagnostics-files.md#gsas2_instprm_geometry_assumed).
A value outside the default range of a width widens that range rather than being clipped.
A `W` below the floor the Gaussian width is clamped at is read onto the floor ([Peak width](instrument.md#peak-width)).

Several banks in one file are a selection: pass `bank=`, the number `#Bank n:` states, or the read refuses and names the numbers it found.
A bank number stated twice is refused, and three of the twelve files in GSAS-II's own tutorial corpus do that.

Refused by name as well:

- an energy-dispersive or unknown `Type`;
- a non-zero `Z`, because `ProfileTCHZ` has no constant Lorentzian term; `Z` is zero in all 95 constant-wavelength histograms of GSAS-II's tutorial corpus;
- a non-zero `Azimuth`, which changes what `Polariz.` means;
- a negative `W`, `X` or `Y`, because those widths are bounded at zero here; GSAS-II bounds none of its width coefficients, and two of the four constant-wavelength files in that corpus converged to a negative `X`;
- a `PNC` bank stating the `Lam1`/`Lam2` pair, and a `Lam2` with no `I(L2)/I(L1)`;
- a file stating neither `Lam` nor `Lam1`;
- a `Diff-type` other than the two GSAS-II names.

A negative `U` or `V` is read, since those coefficients may be negative.
[`GSAS2_INSTPRM_VALUE_DEFAULTED`](diagnostics-files.md#gsas2_instprm_value_defaulted) names a declared item the file omits.
Such an item comes back at this package's default.
[`GSAS2_INSTPRM_FIELD_NOT_READ`](diagnostics-files.md#gsas2_instprm_field_not_read) names items the `Instrument` has no place for, such as `Bank`.

### Writing an .instprm

`write_gsas2_instprm(instrument, path, diagnostics=)` writes what the reader reads back: the wavelengths and the doublet ratio, the polarisation, `U`, `V`, `W`, `X` and `Y` converted back, `SH/L`, `Zero` in degrees and the geometry as `Diff-type`.
`Z` is written at 0.
Each value is written as its Python `repr`, so it reads back exactly.
The refine flags are not written, because an `.instprm` states none.

`axial_sl` and `axial_hl` are written as their sum, since GSAS-II models one number where this package holds two.
An uneven pair is reported as [`GSAS2_INSTPRM_VALUE_MERGED`](diagnostics-files.md#gsas2_instprm_value_merged), and reads back as two equal halves.
GSAS-II floors `SH/L` at 0.002 when it evaluates a profile.
A smaller sum is written as it stands, still modelled as 0.002 by GSAS-II, and reported as [`GSAS2_INSTPRM_VALUE_FLOORED`](diagnostics-files.md#gsas2_instprm_value_floored).
No round trip through this package can show that floor.
[`GSAS2_INSTPRM_FIELD_NOT_WRITTEN`](diagnostics-files.md#gsas2_instprm_field_not_written) names what the format has no items for: the background, the absorption, the displacement and the transparency.
It also names a peak shape or extra components the format cannot state.

Refused by name: a `flat_plate_transmission` geometry, which `Diff-type` cannot name; more than two emission lines; a harmonic on a neutron source; a time-of-flight bank; and a non-finite value.

The structure half of what GSAS-II imports is a phase CIF from `write_gsas2_phase_cif`.

## Time-of-flight instrument files

A GSAS data file's `BANK` record carries binning constants and no calibration.
A time-of-flight pattern without its instrument-parameter file is an axis in microseconds with no way back to a d-spacing.
Two readers fill a [Time-of-flight bank](instrument.md#time-of-flight-bank), and neither format has a writer.

<!-- api-doc: no-exec — it reads instrument files the user supplies -->
```python
import rietx as rx

banks = rx.read_gsas_tof_iparm("bank_calibration.iparm")   # {1: Instrument, ...}
bank = rx.read_gsas2_instprm("Bank 2.instprm")              # source.kind "neutron_tof"
d = bank.source.d_from_tof(pattern.tof_us())
```

This version reads a bank and refines none.
`Refinement` and every other entry point that computes a pattern refuse a `neutron_tof` instrument by name.

### GSAS-I .iparm

`read_gsas_tof_iparm` reads a GSAS-I `.iparm`, `.prm` or `.inst` whose `HTYPE` begins `PNT`, and returns one `Instrument` per bank, keyed by the bank number.
Several banks are what a time-of-flight instrument is, so none is picked.

| Record | Read onto |
|---|---|
| `ICONS`: DIFC, DIFA, ZERO | `TOFSource.difc`, `TOFSource.difa`, `TOFSource.tzero`; `TOFSource.difb` is 0, GSAS-I having no such field |
| `BNKPAR`: DIST, TTHETA | `TOFSource.l2_m` and `TOFSource.two_theta_bank_deg`; TTHETA is required |
| `FPATH1`, one number for the file | `TOFSource.l1_m` on every bank. The manual does not list this record; SNS files write it, so it is read as one number and anything else on it is refused |
| `I ITYP`: ITYP, TMIN, TMAX | `IncidentSpectrum.itype` and its window, converted from ms to µs |
| `ICOFF` and `IECOF` | `IncidentSpectrum.coefficients`, with the esds on `stderr` |
| `PRCF` set 1 | `ProfileTOF` |

The reader holds to the layout the GSAS manual documents and refuses anything else by name:

- The first `PRCF` set is the default whatever its profile function, and it is the only set read. A later set of any type is skipped with [`GSAS_IPARM_PROFILE_DECLINED`](diagnostics-files.md#gsas_iparm_profile_declined).
- A type-1 default set must carry the documented 12 coefficients and a type-3 set 21. A block of another length is refused, never padded or truncated.
- The coefficients are read in the order the manual lists their names. The manual never states the record order, so [`GSAS_IPARM_PROFILE_READ`](diagnostics-files.md#gsas_iparm_profile_read) says the order is an assumption. The cut-off `CTOF` is read and not used.
- A default set of profile function 2, 4 or 5, which this package does not evaluate, is refused.
- A non-zero anisotropic or peak-shift coefficient is refused rather than dropped, and so is a negative `sig` variance.
- A non-zero fifth coefficient pair of an `ITYP` 1 or 2 incident spectrum is refused, since the documented layout stops short of it. `ITYP` 10, whose spectrum is in another file, is refused too.
- A non-zero `POLA`, `IPOLA` or `KRATIO` on `ICONS` is refused, naming its columns, since the manual says they are absent for neutron data.
  Each field may be blank or zero, which the record's Fortran format reads identically.
- A bank with no `PRCF` set keeps its calibration and gets an all-zero `ProfileTOF`, reported as `GSAS_IPARM_PROFILE_DECLINED`.

Fields with no place in the schema, such as the incident spectrum's `CHKSUM` and `IECOR`, are reported as [`GSAS_IPARM_FIELD_DROPPED`](diagnostics-files.md#gsas_iparm_field_dropped).

### Column overrun

The file is read by column, so a value written one field too wide would be cut short.
`61.20` placed in columns 30-34 leaves `61.` in TTHETA's columns 23-32.
Every record the reader parses is therefore checked at each field boundary.
Where the last column of one field and the first column of the next are both filled, and the next field still holds a blank, a number has run across the boundary.
No right-aligned file produces that, so the record is refused with its key, both fields' columns and the raw text.
A blank field still reads as zero.

Two kinds of misplaced value cannot be seen this way.
One is an overrun that ends exactly on a field boundary: `       61.` then `6000000000` is the same text as two full-width fields.
The other is a value moved wholly into the wrong field, which reads as a well-formed number in the wrong slot.
The check also refuses a full field followed directly by a left-aligned one (`      2.5061.20`), although Fortran would read it.
Right-align the second value.
An `.instprm` is `key:value` lines, so none of this applies to it.

### Legacy LANSCE layout

A legacy layout departs from a published format in a way its documentation does not describe, in files a facility wrote.
The strict reader refuses one.
`rietx.io.legacy.read_lansce_iparm` accepts the three departures of `.iparm` files written at LANSCE, each reported as [`GSAS_IPARM_LEGACY_LAYOUT`](diagnostics-files.md#gsas_iparm_legacy_layout):

1. A type-1 `PRCF` set with 8 coefficients in place of the documented 12, read as the first eight of the twelve and named in the manual's order.
2. A non-zero fifth pair in an `ITYP` 1 or 2 incident spectrum, carried as written.
3. A `BNKPAR` value written one field too wide. That one record, and no other, is re-read by whitespace tokens, and the report quotes its raw text and the value taken.

The slot order was checked against GSAS-II v5.8.2 run as a black box, one sentinel value at a time, and no GSAS-II source was read.
A file carrying none of the three departures is passed to `read_gsas_tof_iparm` and comes back unchanged.
The two readers do not dispatch to each other, so you opt in by calling the legacy reader.

### GSAS-II time-of-flight .instprm

`read_gsas2_instprm` reads a file whose `Type` line states `PNT` as one time-of-flight bank.
It reads one bank per file, so `bank=` is refused for such a file.

| File item | rietx field |
|---|---|
| `difC`, `difA`, `difB` | `TOFSource.difc`, `TOFSource.difa`, `TOFSource.difb` |
| `Zero` | `TOFSource.tzero` |
| `2-theta` | `TOFSource.two_theta_bank_deg` |
| `alpha` | `ProfileTOF.alpha1` |
| `beta-0`, `beta-1` | `ProfileTOF.beta0`, `ProfileTOF.beta1` |
| `sig-0`, `sig-1`, `sig-2` | `ProfileTOF.sig0`, `ProfileTOF.sig1`, `ProfileTOF.sig2` |

`Type`, `2-theta` and `difC` are required.
`difB` is read because dropping it would move every peak of a project that sets it, with nothing said.
A key with no published time-of-flight law (`beta-q`, `sig-q`, `Z`, `X`, `Y`) or a constant-wavelength key (`SH/L`, `Polariz.`, `Lam`) is accepted only at exactly zero, reported as dropped, and refused otherwise.
`Bank`, `fltPath` and `Azimuth` are reported as [`GSAS2_INSTPRM_FIELD_DROPPED`](diagnostics-files.md#gsas2_instprm_field_dropped).
Any other key is refused, spelled out, and so is a repeated key.
