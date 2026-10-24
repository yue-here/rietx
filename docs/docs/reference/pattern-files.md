# Pattern files

This page gives the pattern formats `read_pattern` opens, how it recognises each one, where each format's esds come from, and what a reader repairs, reports or refuses.

`read_pattern` returns a `PatternData`, whose fields are on [Patterns and structures](data.md#pattern).
[Reader options](settings.md#reader-options) gives the meaning of each keyword a reader takes.
[Diagnostics: reading files](diagnostics-files.md) gives every code this page names.

## Reading a pattern

`read_pattern` identifies the format from the file's contents and passes the file to that format's reader.
Pass a list as `diagnostics=` and every repair or assumption the reader made comes back in it.

```python
import rietx as rx
from rietx.examples import examples_dir

notes = []
data = rx.read_pattern(examples_dir() / "FAP.XRA", diagnostics=notes)
print(data.axis, len(data.intensity), data.sigma is None)
print(data.metadata)
print([note.code for note in notes])
```

```text
two_theta 5753 True
{'source_file': 'FAP.XRA', 'format': 'gsas-std'}
[]
```

`FAP.XRA` is a GSAS file, recognised by its `BANK` record whatever its suffix.
Its records carry counts only, so `PatternData.sigma` is `None` and the fit uses the Poisson fallback.

Without the list, the read is silent and returns the same pattern.
Two checks still run on every call: a reader that cannot read the file raises `ValueError` or `OSError` naming the file, and a 2θ axis past 180° is refused.

`rietx.io.readers.identify_format` returns the format that claims a file without reading it.
`rietx.io.readers.list_scans` returns one `ScanInfo` per measurement in a file that holds several, with its label, point count, stepped range and, where the file records one, its temperature.
It refuses a format that holds one measurement per file.

## Formats

The readers are tried in a fixed order, and the first whose test matches reads the file.
Magic bytes and archive manifests come first, then a required first line or XML root, then a suffix, then a looser text test.
The two peak-list refusals come next, then the ASCII reader, and the refusal of an unrecognised `.raw` comes last, so it can shadow no reader.
`ReaderCapability.sniff` gives each format's test in words, `ReaderCapability.sigma` says where its esds come from, and `ReaderCapability.refuses` says why a refused format is declined.

| Format | `name` | Suffixes | Option | Esds |
|---|---|---|---|---|
| Bruker/Siemens DIFFRAC binary, versions 3 and 4 | `bruker_raw` | `.raw` | `scan` | measured per file: whole numbers are counts, a rate whose product with the step time is whole gets √(y·t)/t, anything else withholds σ |
| Philips PC-APD binary scan | `philips_rd` | `.rd`, `.sd` | none | Poisson on the decoded counts |
| Rigaku SmartLab Studio II measurement | `rasx` | `.rasx` | `scan` | measured per file, as for `.ras` |
| Bruker DIFFRAC.MEASUREMENT experiment | `brml` | `.brml` | `scan` | through the automatic absorber factor a, σ = √(y/a)·a |
| Rigaku SmartLab or MiniFlex scan | `ras` | `.ras` | `scan` | measured per file: Poisson for whole counts, √(y·t)/t for a rate, withheld otherwise |
| Bruker/Siemens DIFFRAC-AT export | `uxd` | `.uxd` | `scan` | Poisson for a `_COUNTS` block, √(y·t)/t from `_STEPTIME` for a `_CPS` block |
| PANalytical/Malvern XRDML | `xrdml` | `.xrdml` | `scan` | through the attenuation factor and counting time the file names |
| PANalytical scan | `udf` | `.udf` | none | Poisson |
| Powder CIF | `pdcif` | `.cif` | `block` | an `_su` or `_esd` loop, then an uncertainty in parentheses on every intensity, then `_pd_proc_ls_weight` read as 1/σ², else Poisson |
| GSAS raw powder data | `gsas` | `.fxye`, `.gsas`, `.gda`, `.xra`, `.raw` | `bank` | the third column of an `FXYE` record or the second of an `ESD` record; Poisson for `STD` |
| FIT2D or pyFAI integrated pattern | `chi` | `.chi` | none | the third column where written, else Poisson |
| Two- or three-column ASCII | `xy` | `.xy`, `.xye`, `.dat`, `.prn`, `.txt` | none | the third column where present and positive, else Poisson |

| Refused format | `name` | Suffix | Why |
|---|---|---|---|
| Peak list from DIFFRAC-AT or RRUFF | `dif_peaklist` | `.dif` | a table of reflections, recognised by its hkl columns |
| Peak list from Stoe or PANalytical | `peak_list` | `.pks`, `.udi` | a table of reflections, recognised by the suffix alone because no sample file was available |
| Unrecognised binary `.raw` | `raw_unclaimed` | `.raw` | six vendors write `.raw`, and this file matched none of the readers |

A file misnamed `.dif`, `.pks` or `.udi` that reads as a plain profile still reaches the ASCII reader.
`capabilities()` lists the formats in the order they are tried:

```python
from rietx import capabilities

caps = capabilities()
assert [fmt.name for fmt in caps.reader_formats] == [
    "bruker_raw", "philips_rd", "rasx", "brml", "ras", "uxd", "xrdml", "udf",
    "pdcif", "gsas", "chi", "dif_peaklist", "peak_list", "xy", "raw_unclaimed"]
assert [opt.name for opt in caps.reader_options] == ["bank", "block", "scan"]
```

### Format notes

- `bruker_raw` reads versions 3 (`RAW1.01`) and 4 (`RAW4.00`). Versions 1 and 2 are refused by name, because no corroborated description of either exists. A version 3 file whose declared ranges leave non-zero bytes over is refused, naming the offset. A trailing run of zeros is accepted.
- `philips_rd` stores each intensity √-compressed, and the reader decodes it as counts = v²//100. The header states the file's length twice and its maximum intensity once, and a disagreement is refused.
- `rasx` and `ras` read an attenuator column and never apply it. [`RAS_ATTENUATOR_PRESENT`](diagnostics-files.md#ras_attenuator_present) names the 2θ range it covers.
- `brml` locates every column from the file's own data views. A detector frame (a recorded view longer than one point) is refused.
- `xrdml` applies the beam attenuation factor and reports [`XRDML_ATTENUATOR_APPLIED`](diagnostics-files.md#xrdml_attenuator_applied).
- `udf` states no scanned axis, so 2θ is assumed without a diagnostic. Its 2θ values are rebuilt from the stated range and step, and a point count that disagrees with them is refused.
- `gsas` reads `STD`, `ESD` and `FXYE` records and refuses `ALT` and `FXY` by name. A file whose only bank record is behind a `#` is read from that record, with [`GSAS_BANK_COMMENTED`](diagnostics-files.md#gsas_bank_commented).
- `chi` requires the point count in its four-line header to match the rows.
- `xy` keeps the rows at the file's most common column count and drops the rest with [`PATTERN_ROWS_DROPPED`](diagnostics-files.md#pattern_rows_dropped). A file with NUL bytes in its first 4 kB is refused unless a byte-order mark says it is UTF-16.

## Reader options

`read_pattern` takes three keyword options, and the Option column under [Formats](#formats) says which format honours which.

`scan`
: Which measurement to read, counting from 0, in a vendor file that holds several. The ranges are selected and never concatenated, because two ranges are usually two counting regimes. A file holding several, read without `scan`, returns scan 0 and reports [`PATTERN_MULTISCAN_DEFAULTED`](diagnostics-files.md#pattern_multiscan_defaulted).

`block`
: The pdCIF data block to read, matched against any part of the block's name. Without it, the first block holding a 2θ and an intensity loop is read. A file with a `_meas` and a `_calc` block is a different pattern depending on which one you ask for. `read_pdcif` reads a pdCIF directly with the same option.

`bank`
: The GSAS bank to read, by the number its `BANK` record declares. A file holding more than one bank is refused until `bank` names one, because each bank is a different detector. `rietx.io.formats.gsas.gsas_banks` lists each bank's bintype, record layout, channel count and range, or the reason it cannot be read.

An option no format takes is a typo and raises.
An option this file's format does not take is dropped, and reported as [`READER_OPTION_IGNORED`](diagnostics-files.md#reader_option_ignored).
`None` means not given.

## Repairs and reports

A reader repairs a file only where it can say that it did.
A deviation that is the same measurement stored differently is repaired and reported.
A deviation that makes the measurement ambiguous is refused.

| What the file holds | What the reader does |
|---|---|
| a 2θ column stored high to low | reverses it, [`PATTERN_SCAN_REVERSED`](diagnostics-files.md#pattern_scan_reversed) |
| a repeated 2θ with the same intensity | drops the repeat, [`PATTERN_DUPLICATE_POINTS`](diagnostics-files.md#pattern_duplicate_points) |
| a repeated 2θ with a different intensity | refuses, naming the 2θ |
| a 2θ column that is not monotonic | refuses, and names `scan=` where the format has it |
| a step that changes along the scan | reads it unchanged |
| an axis at or below 0° | reads it, [`PATTERN_X_AXIS_IMPLAUSIBLE`](diagnostics-files.md#pattern_x_axis_implausible) |
| an axis past 180° | refuses, naming the file, the reader and the range |
| the same σ on every point | keeps it, [`PATTERN_SIGMA_CONSTANT`](diagnostics-files.md#pattern_sigma_constant) |
| dead detector channels | keeps them, [`PATTERN_DEAD_CHANNELS`](diagnostics-files.md#pattern_dead_channels) |

A constant σ makes the fit unweighted.
If the column is a placeholder, set `PatternData.sigma` to `None` to use the Poisson weights.

## Intensities and esds

The fit weights each point by the file's esd where the file has one, and by Poisson σ = √max(y, 1) otherwise.
The Poisson fallback is right for raw counts and wrong by a factor √t for a rate already divided by a counting time t.
So a reader decides which of the two a file holds:

- A unit the format states structurally is trusted. `.uxd` names it in the token that opens the data block, and `.xrdml` in an attribute of the data element.
- A unit stated as free text is checked by arithmetic. Counts are whole numbers, and so is a rate multiplied by its counting time. A real `.ras` file declares counts and stores 84.3047.
- Where neither settles it, σ is withheld and the reader reports [`PATTERN_INTENSITY_SCALED`](diagnostics-files.md#pattern_intensity_scaled).

The intensities need not be the file's numbers.
Vendors disagree about whether an attenuator factor is already applied: four formats have one, and they give three answers.
`.xrdml` applies the factor, `.brml` leaves the values alone and carries the factor into σ alone ([`BRML_ABSORBER_ENGAGED`](diagnostics-files.md#brml_absorber_engaged)), and `.ras` and `.rasx` report the attenuator without applying it.
The `.xrdml` and `.brml` answers were measured on files where the factor varies, by asking which series runs continuously through the change.
No obtainable `.ras` or `.rasx` file has a varying attenuator, so those two readers report it and leave the choice to you.
Whichever way it goes, σ goes through the same factor.

The package never subtracts an estimated background from the intensities.
Hold a measured background additively with `BackgroundFixedPlusChebyshev`, or refine it under a smoothness penalty with `BackgroundPSpline` ([Background](instrument.md#background)).

## The scanned axis

Most vendor files are not powder scans: four of the five real `.uxd` files obtained were pole figures or rocking curves.
A non-2θ scan parses cleanly and refines to a wrong cell, so a format that states its axis is read by that statement:

- a 2θ axis is read;
- a neutron flight time in microseconds is read as a time-of-flight pattern;
- any other recognisable axis, such as a q or d axis, a rocking curve or a pole-figure ring, is refused, naming what the file holds;
- an axis the reader cannot identify is read as 2θ, with [`PATTERN_X_AXIS_ASSUMED`](diagnostics-files.md#pattern_x_axis_assumed) quoting what the file says.

A format that states no axis at all, `.udf` and an `.xy` file with no unit comment, is read as 2θ without a diagnostic.
A flight-time axis is taken only from a statement of the unit, never from the size of the numbers.
A range of 1000 to 10000 µs passes every check a 10-100° scan passes.

The file's own wavelength goes into `PatternData.metadata` and is never used.
The instrument sets the wavelength.

## Time-of-flight patterns

Two readers produce a time-of-flight pattern, with `PatternData.tof` in microseconds in place of `PatternData.two_theta`.
Both do it because the file states the unit.

| File | What makes it a flight time |
|---|---|
| GSAS bank, `TIME_MAP` bintype | the bintype. The steps are tabulated in a separate `TIME_MAP` record as (first channel, flight time, step) triples in clock ticks, so the axis is exact and all three record layouts (`STD`, `ESD`, `FXYE`) are read. |
| GSAS bank, `RALF` or `SLOG` bintype | the bintype and an `FXYE` record layout, which writes its own x column. Mantid's `SaveGSS` writes this, `RALF` by default. Under `ESD` or `STD` the axis would have to be rebuilt from the bank's four coefficients, and the bank is refused by name. |
| `.xy` or `.xye` with a Mantid header | the line `' The X-axis unit is: Time-of-flight`. |

The GSAS manual says a `RALF` step varies irregularly about a constant Δt/t.
Rebuilding a real ISIS GEM bank's axis from its own coefficients reproduces the file's explicit column only to about 9 × 10⁻³ µs.
Nothing downstream could see an error that small, so the reader refuses rather than rebuild it.

An `.xy` file whose comments mention a flight time without stating the unit is read as 2θ, with `PATTERN_X_AXIS_ASSUMED`.
The word `tof` also turns up in file names and provenance comments.
A stated unit of d-spacing, momentum transfer Q, Q², wavelength, energy or neutron momentum is refused by name.

GSAS bintypes other than `CONS`, `TIME_MAP`, `RALF` and `SLOG` are refused, each naming what its axis holds: `COND` a d-spacing, `CONQ` a Q, `LPSD` a detector position, `EDS` a photon energy, and `LOG6` a flight time on a clock whose step table is not in the data file.
A GSAS file holding banks on both a 2θ and a flight-time axis is refused, naming both, and `bank=` does not lift that refusal.

The calibration that converts a flight time to a d-spacing is not in the data file.
[Instrument files](instrument-files.md#time-of-flight-instrument-files) gives the readers for it, and [Time-of-flight bank](instrument.md#time-of-flight-bank) gives the fields they fill.
This version reads a time-of-flight pattern and refines none ([Time-of-flight patterns](data.md#time-of-flight-patterns)).

## Metadata

`PatternData.metadata` holds what a reader found in the file, under a fixed set of keys.
A reader refuses to write any other key, because the GUI's import wizard and a preview's scan count match on these names.

| Key | Meaning |
|---|---|
| `source_file` | the file's own name, as opened |
| `format` | the record layout or format that claimed the file |
| `block` | the pdCIF data block read, when the file held more than one |
| `title` | the file's own title line, verbatim |
| `sample` | the sample name the file records |
| `x_label` | the x-axis label the file states, verbatim |
| `scan_axis` | the goniometer axis scanned, as the file names it |
| `scan` | which scan was read, counting from 0 |
| `scan_count` | how many scans the file holds |
| `anode` | the X-ray target element the file names |
| `wavelength` | the primary wavelength in Å the file states; recorded and never used |
| `wavelength_alpha2` | the Kα2 wavelength in Å the file states; a stated zero says no doublet was used |
| `intensity_item` | the pdCIF intensity item read, where its definition says more than a count (`_pd_proc_intensity_net`, defined as background-subtracted); a label, not a measurement |
| `intensity_unit` | the intensity unit the file declares, a claim the reader checks before trusting |
| `count_time_s` | seconds per step, where the file gives enough to derive it |
| `temperature_k` | the specimen temperature the scan records; the series coordinate of an in-situ run |
| `goniometer_radius_mm` | the goniometer radius the file records, in mm |
| `beam_optics` | the optic elements the file lists in its beam paths, named only |
| `diffracted_beam_optics` | the part of `beam_optics` after the sample, which sets `Source.kbeta` in the GUI's import wizard |

```python
from rietx.io.formats.base import METADATA_KEYS

assert list(METADATA_KEYS) == [
    "source_file", "format", "block", "title", "sample", "x_label",
    "scan_axis", "scan", "scan_count", "anode", "wavelength",
    "wavelength_alpha2", "intensity_item", "intensity_unit", "count_time_s",
    "temperature_k", "goniometer_radius_mm", "beam_optics",
    "diffracted_beam_optics"]
```
