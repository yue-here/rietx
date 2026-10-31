# Peak lists for indexing

This page gives the peak list an indexing search runs on: what `pick_peaks` and `fit_peaks` return and refuse, the fields of a `PeakList` and of each `ObservedPeak`, the flags that take a line out of the list, and the verdict `assess_peak_list` gives on whether a list can be indexed, with its systematic-shift screen.

Indexing finds a lattice from line positions alone, for a specimen whose cell is unknown or only guessed.
The search itself is `index_pattern` ([The indexing search and its result](indexing.md)) and the extinction screen after it is `determine_extinction_symbol` ([The extinction symbol](extinction.md)); this page covers what both take in.
The quadratic form the search runs over, what a peak list can support and the shift measured before the cell are in [Indexing](../theory/indexing.md).

:::{admonition} Provisional
:class: warning
Indexing is still being measured against real data, so every name on this page may change in a 1.x release: `pick_peaks`, `fit_peaks`, the types in `rietx.schemas.indexing` and the helpers under `rietx.indexing`.
A change is announced in the release notes, and the data contracts a consumer parses do not move with it.
{ref}`provisional-by-declaration` gives the promise in full.
:::

## Picking the peaks

`pick_peaks` fits every resolvable line in a pattern and returns a `PeakList`.
Detection proposes maxima and shoulders, neighbouring lines are fitted together as one group, and every position comes out of a profile fit with its own esd rather than from a maximum.

<!-- api-doc: no-exec — it needs a pattern file on disk -->
```python
import rietx as rx

data = rx.read_pattern("corundum.xy")
ins = rx.Instrument.bragg_brentano(radiation="CuKa")
peaks = rx.pick_peaks(data, ins)
print(peaks)
```

| Argument | Default | Does |
|---|---|---|
| `data` | | the pattern; its excluded regions are removed from detection, not masked |
| `instrument` | | read, never refined (below) |
| `two_theta_range` | `None` | crops detection and fitting to a (low, high) range in degrees, on top of the excluded regions |
| `shoulders` | `True` | also proposes shoulder seeds from the curvature, not only maxima |
| `flag_contamination` | `True` | flags Kβ and tungsten Lα lines; they stay in the list and leave the usable set, and nothing is subtracted |

The instrument is read for four things: the primary wavelength and the emission lines (the positions and the doublet constraint), the U, V, W, X, Y width law (the separation floor and the width seeds), `ProfileTCHZ.shape` (so the list and the refinement after it share one peak shape), and the axial apertures, applied and held.
Its declared beam also decides the contamination search: a neutron source, or an X-ray source with `kbeta="monochromator"`, skips both ghost searches, because neither line reaches the detector.

`pick_peaks` raises `ValueError` for a time-of-flight pattern or a time-of-flight source, and when fewer than 16 points survive the excluded regions and `two_theta_range`.
A list that is too short to index is not an error.
It comes back carrying [`PEAK_LIST_TOO_SHORT`](diagnostics-indexing.md#peak_list_too_short), a warning that fires under 20 usable lines.
`PeakList.diagnostics` holds that and the other picker codes; [Diagnostics: peaks and indexing](diagnostics-indexing.md) explains each one.

On the bundled fluorapatite pattern (`rietx.examples`, 5753 points over 15-130° 2θ, Cu Kα), the pick takes several seconds and returns 186 components, 135 of them usable.
Most of the 51 left out are `duplicate_line` copies (40), the rest `no_intensity`, `width_capped`, `position_unmeasured`, `unresolved_split` and `fit_failed` components.

(peak-list-fields)=
### What a list holds

| Field | Holds |
|---|---|
| `PeakList.peaks` | every fitted component, usable or not, in 2θ order |
| `PeakList.wavelength` | the primary emission line, Å |
| `PeakList.two_theta_min`, `PeakList.two_theta_max` | the range the lines were picked over: the first and last channel detection kept, or the lowest and highest position of a list built from positions |
| `PeakList.source` | `"fitted"` when this package measured the lines, `"positions"` when they were handed in |
| `PeakList.instrument_undeclared` | the instrument blocks the picker found at their defaults on a laboratory source, keyed by block; empty when the source is a lab tube and nothing was; `None` when nothing was checked: a source that is not a lab tube, or a list no picker made |
| `PeakList.thresholds_version` | which set of indexing thresholds produced the list, `rietx.schemas.indexing.INDEXING_THRESHOLDS_VERSION` at the time |
| `PeakList.diagnostics` | what the picker noticed, as `Diagnostic` entries |

`PeakList.usable` is a method, and every screen and every engine runs on the list it returns: the components whose flags include none of the ten that refuse a line ([The flags](#the-flags)).
The refused lines stay in `PeakList.peaks`, so a report can say why each went.

Five more methods return the usable lines as arrays, the form the engines and the figures of merit take: `PeakList.two_theta`, `PeakList.two_theta_esd`, `PeakList.q`, `PeakList.q_esd` and `PeakList.intensity`.

Printing a list gives one row per component, with its position, esd, intensity, width, origin and flags, under a count line and above the diagnostics.

The list checks on construction that every `ObservedPeak.q` agrees with its own 2θ at the list's wavelength, to a relative 1e-9.
A peak built by hand with a stale Q raises `ValueError` there, rather than mis-indexing a pattern later.

### What one line holds

Each entry in `PeakList.peaks` is an `ObservedPeak`: one fitted component, with the group it was fitted in.

| Field | Holds |
|---|---|
| `ObservedPeak.two_theta` | fitted position of the primary-line (Kα1) component, ° |
| `ObservedPeak.two_theta_esd` | its esd, ° 2θ, inflated by √max(χ²_red, 1); on a line that unresolved splits were merged into, widened to reach them |
| `ObservedPeak.two_theta_esd_fit` | the fit's own esd before that widening, on a merged line only; `None` elsewhere, where the two are one number |
| `ObservedPeak.intensity` | integrated area of the primary line |
| `ObservedPeak.intensity_esd` | its esd; infinite on a list built from positions |
| `ObservedPeak.q` | Q = 1/d², Å⁻², from the position and the list's wavelength |
| `ObservedPeak.q_esd` | σ(Q), by the exact derivative of that relation |
| `ObservedPeak.fwhm` | the group's combined FWHM, ° 2θ |
| `ObservedPeak.eta` | the group's pseudo-Voigt mixing, 0 Gaussian and 1 Lorentzian |
| `ObservedPeak.group` | index of the fitted group this component came from |
| `ObservedPeak.n_in_group` | how many components were fitted together with it, itself included |
| `ObservedPeak.chi2_red` | reduced χ² of that group's fit; NaN on a list built from positions |
| `ObservedPeak.flags` | what the fit or the screens noticed about this line ([The flags](#the-flags)) |
| `ObservedPeak.origin` | `"fitted"` (detection proposed it), `"manual"` (a person placed it) or `"edited"` (a person moved a fitted line and its group was refitted) |

Two properties derive from these: `ObservedPeak.d` is the d-spacing in Å, and `ObservedPeak.usable` is true when no flag refuses the line.

`ObservedPeak.fwhm` and `ObservedPeak.eta` belong to the group rather than the line.
Within a group, a fraction of a degree wide, the widths of its lines cannot be told apart, and fitting one per line is what lets a doublet absorb an unresolved neighbour.

`ObservedPeak.origin` records provenance and is no judgement: no gate in the package branches on it.
[Peak origins](settings.md#peak-origins) gives each value's entry.

Q rather than d or 2θ is the working coordinate, because Q is linear in the reciprocal metric {eq}`idx-qform`, and that linearity makes fitting a cell a linear problem.

### The flags

`ObservedPeak.flags` holds members of a closed vocabulary of twenty.
Ten take a line out of `PeakList.usable`; the other ten report evidence and leave it in.
[Peak flags](settings.md#peak-flags) gives each flag's meaning as the GUI shows it.

| Flag | Written when | Usable? |
|---|---|---|
| `ghost_kbeta` | the line matches a stronger line's Kβ position and intensity | no |
| `ghost_tungsten` | the line matches a stronger line's tungsten Lα position and intensity | no |
| `excluded` | a person took the line out in the GUI's peak editor | no |
| `fit_failed` | the group's solve did not converge | no |
| `not_separable` | a component a re-seed pass added, inside a stronger group-mate's profile at under a quarter of its area, in a group whose fit is still refuted with it in | no |
| `no_intensity` | the fitted intensity sits on its zero bound, or is under one esd of itself | no |
| `position_unmeasured` | the position esd reached 180°, the whole span a 2θ axis has | no |
| `duplicate_line` | a better-measured component of another group already fitted this line | no |
| `unresolved_split` | the component sits closer than Sparrow's limit to a comparable group-mate, which reports the pair as one line with an esd reaching both | no |
| `width_capped` | the group's width ran into its bound: a hump, not a line | no |
| `sigma_assumed` | σ was supplied rather than fitted (every line of a list built from positions) | yes |
| `unresolved_shoulder` | the fit never pulled the component more than half a FWHM from a group-mate | yes |
| `position_at_bound` | the position ran into its bound, half a seed FWHM from where detection put it | yes |
| `asymmetry_unmodelled` | the residual carries an odd, one-sided shape at 4σ or more that the model does not absorb | yes |
| `background_extrapolated` | the line stands where the background was extrapolated rather than measured, at either end of the pattern | yes |
| `axial_tail` | the line is under a quarter of a stronger group-mate's area, within 3.5 FWHM on its axial-divergence tail side | yes |
| `kalpha2_residual` | the line is under a quarter of a stronger group-mate's area, within its FWHM of that line's predicted Kα2 position | yes |
| `weak_line` | the line's $I/\sigma_I$ fails the pattern's false-discovery threshold (Benjamini-Hochberg at q = 0.01) | yes; scored, and drives a search only to make up six lines |
| `residue_misfit` | `index_residue` only: the pick stands on more of the subtracted first phase's profile than its own height | yes, but it never drives a search, whatever the floor |
| `unnamed_neighbour` | `fit_peaks` only: the window holds a component you did not name | yes |

A contamination line is flagged and left out, never subtracted, because stripping redistributes the noise and biases what is left.

To index the residue a cell leaves, pass the result to `rietx.indexing.index_residue` with the pattern and instrument.
It fits the first cell (or the one you name with `candidate=`) with the validation's Pawley fit, subtracts its peaks, picks what remains with the widths that fit refined, and indexes the picks as a second result.
A pick standing on more of the subtracted profile than its own height is flagged `residue_misfit`: it counts as an unexplained line and lowers the grade, but never drives the search.
On a single-phase pattern the residue holds no pick (synthetic Si) or only such lines (SRM 660c), so the second result abstains.
A cell whose fit needs widths more than three times the list's own does not describe the pattern: nothing is picked from its residue and the result says why (skipped for a list passed in as positions, whose widths are assumed).
On synthetic Si with MgO at 0.05 to 0.3 of its scale, the second result holds MgO's cell first.
Each cell was validated alone: refine both phases together before quoting either.

The evidence flags leave a line in because one pattern cannot say what the line is.
A real reflection can stand on an extrapolated background, on a stronger line's axial tail or at a predicted Kα2 position, and on the certified laboratory patterns a component under the false-discovery bar is often a real weak line the certified cell indexes.

`weak_line` sits between the two groups.
A search is driven by the strongest usable lines and scores a candidate against every usable line, and every line a search is driven by is one an accepted cell must index.
So a `weak_line` component is scored like any usable line but does not drive a search.
The one exception is a list with fewer than six other usable lines: the strongest `weak_line` components then drive it too, up to six, so a list of weak lines can still be searched.
[Which lines drive the search](../theory/indexing.md#which-lines-drive-the-search) gives the rule.

### A peak list from somewhere else

`PeakList.from_positions` builds a list from bare positions: a publication, a database entry, another program's output.

```python
import numpy as np
import rietx as rx

# LaB6, the first six lines at Cu Kα1, as a paper would quote them
peaks = rx.PeakList.from_positions(
    np.array([21.358, 30.385, 37.442, 43.507, 48.964, 53.996]),
    wavelength=1.540596)

assert peaks.source == "positions"
assert len(peaks.usable()) == 6
assert all(p.flags == ["sigma_assumed"] for p in peaks.peaks)
assert abs(peaks.peaks[0].d - 4.1569) < 1e-3
```

| Argument | Default | Does |
|---|---|---|
| `two_theta` | | positions in degrees, a non-empty one-dimensional array; sorted on the way in |
| `wavelength` | | the primary wavelength, Å |
| `intensity` | `None` | relative intensities; `None` gives every line the same weight |
| `two_theta_esd` | `0.02` | the assumed σ(2θ), one number or one per line |
| `fwhm` | `0.1` | the width every line is given, ° 2θ |

Every line is flagged `sigma_assumed` and `PeakList.source` reads `"positions"`, because an assumed σ is not a measurement: it must not be quoted as a precision, and a gate weighting lines by 1/σ² is handed a constant.
Each line also carries `eta` 0.5, an infinite `intensity_esd` and a NaN `chi2_red`.
The list carries no diagnostics: `rietx.indexing.diagnostics.peak_diagnostics` translates such a list into the picker's codes, [`PEAK_SIGMA_ASSUMED`](diagnostics-indexing.md#peak_sigma_assumed) among them.

Pass `intensity=` when the source quotes relative intensities, because a search is driven by the strongest lines and the intensities decide which those are.
A list of equal intensities drives the search with its lowest-angle lines.
The assumed widths size no search window either: unless a shift was declared or measured, a search over such a list matches within 0.05°.

`from_positions` raises `ValueError` for an empty or multi-dimensional `two_theta`.

(fitting-peaks-you-name)=
## Fitting peaks you name

`fit_peaks` fits the positions you give it and nothing else, with no structure, no space group and no refinement.
It serves a width analysis over chosen lines, a d-spacing lookup or a check on one reflection.

```python
import tempfile

import rietx as rx
from rietx.examples import build_example

with tempfile.TemporaryDirectory() as parent:
    project = build_example("fap", parent)
    data, ins = project.data, project.refinement.instrument

# seven isolated fluorapatite lines, as you would read them off a plot
peaks = rx.fit_peaks(data, ins, [28.094, 34.087, 39.985, 48.226,
                                 49.521, 50.711, 51.522])

for p in peaks.peaks[:3]:
    print(f"{p.two_theta:7.3f} ± {p.two_theta_esd:.4f}°   "
          f"d = {p.d:.4f} Å   FWHM = {p.fwhm:.4f}°   {p.origin}")
```

```text
 28.094 ± 0.0010°   d = 3.1735 Å   FWHM = 0.0665°   manual
 34.087 ± 0.0007°   d = 2.6279 Å   FWHM = 0.0693°   manual
 39.985 ± 0.0007°   d = 2.2529 Å   FWHM = 0.0707°   manual
```

It takes `data`, `instrument`, `positions` (a list or an array of 2θ in degrees) and `two_theta_range`, and returns a `PeakList` read the same way as a picked one ([What a list holds](#peak-list-fields)).

| | `pick_peaks` | `fit_peaks` |
|---|---|---|
| what is fitted | every line detection resolves | the positions you pass, and only those |
| a weak shoulder | proposed, then kept or refused on ΔBIC | fitted only if you name it |
| `ObservedPeak.origin` | `"fitted"` | `"manual"` |
| a position with no peak | does not arise | returned, flagged `no_intensity` |
| `unresolved_split`, `width_capped` | judged | not judged: a named pair closer than Sparrow's limit comes back as two lines |
| `duplicate_line`, `weak_line` | judged | not judged |
| ghost search | `flag_contamination=True` by default | always, subject to the declared beam |
| `PEAK_LIST_TOO_SHORT`, `PEAK_EXPECTED_FALSE_LINES` | reported | never: the count and the positions are yours |

Detection still runs.
The background envelope, the seed widths and the window each group is fitted over come from it.
A position inside a detected window reuses that window, rather than re-sizing one around a subset of its components.
Positions sharing a window are fitted together in one solve, because overlapping components fitted one at a time each bias the other.
A position where detection found nothing gets a fresh window, sized as detection sizes its own.

`fit_peaks` raises `ValueError` for:

- what `pick_peaks` refuses: a time-of-flight pattern or source, or fewer than 16 points in range;
- an empty list of positions;
- a position named twice, since two components at one 2θ cannot be told apart;
- a position outside the picked range: `2θ = 5.0000° is outside the picked range 15.0000–129.9800°`;
- a window holding too few channels, in a gap or an excluded region, with a message that names the position or the span of a cluster of positions.

### A position with no peak

Naming a position that turns out to be empty is a correct request: a width analysis over a published line list, or a d-spacing lookup, will do it.
The answer has to say so.

```python
import tempfile

import rietx as rx
from rietx.examples import build_example

with tempfile.TemporaryDirectory() as parent:
    project = build_example("fap", parent)
    data, ins = project.data, project.refinement.instrument

empty = rx.fit_peaks(data, ins, [37.43])       # flat background, no line
line = empty.peaks[0]
print(f"intensity {line.intensity:.0e}   esd(2θ) {line.two_theta_esd:.0e}°")
print(f"flags {line.flags}")
print(f"usable {len(empty.usable())} of {len(empty.peaks)}")
```

```text
intensity 3e-18   esd(2θ) 7e+17°
flags ['position_at_bound', 'no_intensity', 'position_unmeasured']
usable 0 of 1
```

The line comes back flagged and unusable, never dropped: a component you placed is yours to see and remove, and a call returning fewer peaks than you asked for is one you cannot check.
It is not a measurement either.
A peak reaches the data only through intensity × profile, so at zero intensity its position has no gradient, and the position is wherever the solve left it.
The esd of 7e+17° says that.
`PeakList.usable` drops the line and `PeakList.peaks` keeps the reason.

### The neighbour you did not name

When the window holds a component your positions left out, its intensity has nowhere to go but into the components that were fitted.
The named positions are then pulled towards it, and χ²_red is the only other sign.
Those lines are flagged `unnamed_neighbour`.

```python
import tempfile

import rietx as rx
from rietx.examples import build_example

with tempfile.TemporaryDirectory() as parent:
    project = build_example("fap", parent)
    data, ins = project.data, project.refinement.instrument

for named in ([52.253], [52.170, 52.253]):
    for p in rx.fit_peaks(data, ins, named).peaks:
        print(f"named {len(named)}: {p.two_theta:8.4f} ± {p.two_theta_esd:.4f}°"
              f"   χ²_red {p.chi2_red:5.2f}   {p.flags}")
```

```text
named 1:  52.2502 ± 0.0010°   χ²_red  4.94   ['unnamed_neighbour']
named 2:  52.1701 ± 0.0067°   χ²_red  1.50   ['axial_tail']
named 2:  52.2529 ± 0.0008°   χ²_red  1.50   []
```

Naming the weak neighbour moves the line you wanted by 2.7 m°, 2.7 times its own esd, and takes χ²_red from 4.94 to 1.50.
The flag reports and refuses nothing: naming a subset is legitimate, and the esd inflation by √max(χ²_red, 1) already carries part of the cost.

The question is asked of your fit, not of detection's seeds.
The residual proposes a position and ΔBIC decides whether it earns its two parameters, as `pick_peaks` decides for its own groups, so the flag also catches a component detection never seeded.

### Widths: a Williamson-Hall analysis

The package fits the peaks, and the Williamson-Hall analysis is four lines of numpy.
Williamson and Hall (1953) separate size from strain by their angular dependence, size broadening going as 1/cos θ and strain as tan θ, so $2w\cos\theta = K\lambda/L + 4\varepsilon\sin\theta$ is a straight line in sin θ.
Its intercept gives the size L and its slope the strain ε.
Here $2w$ is a FWHM, so K has to be a FWHM constant, and the lines below use 0.9.

```python
import tempfile

import numpy as np
import rietx as rx
from rietx.examples import build_example

with tempfile.TemporaryDirectory() as parent:
    project = build_example("fap", parent)
    data, ins = project.data, project.refinement.instrument

peaks = rx.fit_peaks(data, ins, [28.094, 34.087, 39.985, 48.226,
                                 49.521, 50.711, 51.522])

theta = np.radians(np.array([p.two_theta for p in peaks.peaks]) / 2.0)
fwhm = np.radians(np.array([p.fwhm for p in peaks.peaks]))
slope, intercept = np.polyfit(np.sin(theta), fwhm * np.cos(theta), 1)

print(f"intercept Kλ/L = {intercept:.3e}  →  L = {0.9 * peaks.wavelength / intercept:.0f} Å")
print(f"slope       4ε = {slope:.3e}  →  ε = {100 * slope / 4:.3f} %")
```

```text
intercept Kλ/L = 1.023e-03  →  L = 1355 Å
slope       4ε = 4.269e-04  →  ε = 0.011 %
```

Those two numbers describe the broadening of the pattern, not of the specimen.
`ObservedPeak.fwhm` is the measured width, the instrument's own width convolved with what the sample adds, and on this fluorapatite the instrument dominates, so 1355 Å is a floor the diffractometer sets rather than a crystallite size.
To get the sample's part, measure the width law on a standard, as [How to calibrate an instrument on a standard](../guides/calibrate.md) does, and either subtract it from the widths or, better, refine the sample-broadening parameters against it.
[Size and strain](derived.md#size-and-strain) gives what such a fit reports, with esds.
[Profiles](../theory/profiles.md) has the instrument and sample convolution, and [Microstructure](../theory/microstructure.md#reading-a-width-as-a-size) the size and strain relations this plot combines.

Two conventions in the lines above.
The plot is in FWHM, so K = 0.9 where an integral breadth would take 1; the two differ by about 10 % on the same data, so quote which you used.
And the fit is unweighted, while `ObservedPeak.two_theta_esd` and the fitted widths give what a weighted fit needs: on a list mixing strong and weak lines, a weighted `np.polyfit` is the right call.

## Whether the list can be indexed

`assess_peak_list`, in `rietx.indexing`, says whether a list can be searched, and `index_pattern` calls it before spending any budget.
It answers with a `DataQualityReport`, and an abstention is a field, never an exception.

```python
import numpy as np
import rietx as rx
from rietx.indexing import assess_peak_list

peaks = rx.PeakList.from_positions(
    np.array([21.358, 30.385, 37.442, 43.507, 48.964, 53.996]),
    wavelength=1.540596)
report = assess_peak_list(peaks)

assert report.supports_indexing
assert report.systems_supported == ["cubic"]
assert report.lines_per_dof["cubic"] == 6.0
assert sorted(report.fom_undefined) == ["f_n", "m20"]
assert report.shift.source == "unavailable"
```

| Argument | Default | Does |
|---|---|---|
| `peaks` | | the `PeakList`; only its usable lines count |
| `reference_two_theta` | `None` | one reference position per usable line, in the same 2θ order, which turns on the shift fit against references; another length raises `ValueError` |
| `sigma_sys_deg` | `None` | a systematic floor declared from outside, recorded in `ShiftScreen.sigma_sys_deg` with the source still `"unavailable"` |
| `shift_from_pairs` | `False` | measure the shift from harmonic reflection pairs, with no reference; `index_pattern` passes `True` |
| `pair_seed` | `0` | the seed the pair screen's structureless replicates are drawn with |
| `envelope_n` | `20` | which line Smith's volume estimate is taken at |
| `instrument` | `None` | the instrument the list was picked with; it changes no verdict, and an abstention's suggestion names what it leaves at default |

When more than one shift road is given, references win over pairs, and pairs over a declared floor.

| Field | Holds |
|---|---|
| `DataQualityReport.supports_indexing` | whether this list can be searched in any system |
| `DataQualityReport.abstained_reason` | why not, as a sentence; `None` when it can |
| `DataQualityReport.n_usable`, `DataQualityReport.n_total` | usable lines, of all the components in the list |
| `DataQualityReport.source` | the list's own `"fitted"` or `"positions"` |
| `DataQualityReport.two_theta_min`, `DataQualityReport.two_theta_max` | the list's picked range, copied from `PeakList.two_theta_min` and `PeakList.two_theta_max` |
| `DataQualityReport.sigma_two_theta_median`, `DataQualityReport.sigma_two_theta_worst` | median and largest σ(2θ) over the usable lines, ° |
| `DataQualityReport.relative_sigma_q_median` | median σ(Q)/Q, a resolving power {eq}`idx-sigma-q` |
| `DataQualityReport.sigma_over_spacing` | median σ(Q) over the mean spacing between neighbouring Q; above about 1 the lines are not resolved in Q |
| `DataQualityReport.lines_per_dof` | usable lines over the metric's degrees of freedom, per crystal system |
| `DataQualityReport.systems_supported` | the systems with at least 5 usable lines per degree of freedom |
| `DataQualityReport.fom_undefined` | figures of merit this list is too short for, name to reason |
| `DataQualityReport.volume_envelope` | Smith's volume estimate, Å³, per system |
| `DataQualityReport.shift` | the systematic-shift screen, a `ShiftScreen` |
| `DataQualityReport.thresholds_version` | which set of thresholds produced the verdict |
| `DataQualityReport.diagnostics` | what the assessment noticed |

A list with fewer than two usable lines comes back at once: `supports_indexing` false, every σ figure NaN, and `DataQualityReport.shift` `None`, the one case where it is.

### Enough lines, and precise enough

"Enough lines" is a question per crystal system.
The metric has one free parameter in cubic, two in tetragonal, hexagonal and trigonal, three in orthorhombic, four in monoclinic and six in triclinic {eq}`idx-subspace`, so one list can be over-determined for one system and short for another.
A system is supported at 5 usable lines per degree of freedom: 5 lines for cubic, 30 for triclinic.

The list abstains for one of three reasons, each written into `DataQualityReport.abstained_reason` and reported as [`INDEX_DATA_INSUFFICIENT`](diagnostics-indexing.md#index_data_insufficient):

- fewer than two usable lines;
- no system supported;
- a fitted list whose median σ(Q)/Q is above 1e-3, where cells differing by 0.1 % in a lattice parameter cannot be told apart.

On a fitted list picked with a laboratory source, a tube's Kα doublet or one line at an anode's Kα1, Kα2 or weighted-mean wavelength (to 5e-4 Å, so `1.5405929`, `1.5406` and a vendor header's `1.5418` all read as Cu), whose axial apertures or profile were left at their defaults, the suggestion names declaring them first, since a re-pick is the cheapest remedy.
The list records those blocks at its pick, in `PeakList.instrument_undeclared`, so `index_pattern(peaks)` with no instrument still names them.
On a synchrotron or neutron source the defaults are what a correct declaration looks like, so nothing is named.

The precision test runs only on a list whose σ was measured.
On a list built from positions every σ is the assumed 0.02°, and refusing on it would quote an assumed precision as a measured one.
All ten sets of a published indexing benchmark {cite}`bergmann2004` arrive as bare positions, and every one of them would fail the test.
`relative_sigma_q_median` is still reported, and [`PEAK_POSITION_PRECISION`](diagnostics-indexing.md#peak_position_precision) still states it.

Whether a list can be searched and whether its candidates can be scored are separate questions.
Below 20 usable lines the classical figures are not computed: de Wolff's M₂₀ is defined on twenty lines {eq}`idx-m20`, and $F_N$ is scored at twenty as this package's own choice, since Smith and Snyder define it for any N and recommend thirty {eq}`idx-fn`.
The search still runs, over the supported systems only, and ranks on the reduced panel.
`DataQualityReport.fom_undefined` names each missing figure with its reason, [`INDEX_PANEL_REDUCED`](diagnostics-indexing.md#index_panel_reduced) says so, and the candidates' confidence is capped below `high` ([The confidence gate](indexing.md#the-confidence-gate)).

`DataQualityReport.volume_envelope` is Smith's (1977) estimate of the cell volume from the d-spacing of the N-th line {eq}`idx-volume`, with N the smaller of `envelope_n` and the usable count.
It is per system because the estimate differs by up to 96× across them: a cubic F lattice shows far fewer distinct lines than a primitive triclinic one of the same volume.
The estimate is a mean line, not a bound, so a search that declares no `max_volume` prunes at 1.5 times it.
On the fluorapatite list of 135 usable lines it runs from 118 Å³ for triclinic to 11 287 Å³ for cubic, and reads 1411 Å³ for hexagonal, the true system.

### The systematic shift, and the window it opens

A 2θ shift has to be measured before the cell, because a candidate's calculated positions are matched against observed lines nothing has corrected.
`DataQualityReport.shift` is a `ShiftScreen`, and `ShiftScreen.source` says which road measured it.

| `ShiftScreen.source` | When |
|---|---|
| `"measured"` | `reference_two_theta` was given and the three templates were fitted against it |
| `"reflection_pairs"` | `shift_from_pairs=True` and the pair screen detected a shift |
| `"unavailable"` | neither, or the pair screen declined; never a zero shift reported as measured |

| Field | Holds |
|---|---|
| `ShiftScreen.n_lines` | lines the screen used |
| `ShiftScreen.templates` | each template fitted alone, as a `ShiftTemplateFit`; empty when nothing was measured |
| `ShiftScreen.best` | the template that fits best, or `None` |
| `ShiftScreen.separable` | whether the data can tell `best` from the others |
| `ShiftScreen.separability_ratio` | the runner-up's residual sum of squares over the best one's, against references; 0 on the pair road |
| `ShiftScreen.max_collinearity` | largest cosine between two templates over the angles sampled, known before any shift is measured |
| `ShiftScreen.prediction_spread_deg` | largest disagreement between the corrections the competitive templates predict, ° 2θ |
| `ShiftScreen.sigma_sys_deg` | scatter the best template leaves, ° 2θ, or the declared floor |
| `ShiftScreen.allowance_deg` | what a search window must span, ° 2θ: the best amplitude plus three of its standard errors |
| `ShiftScreen.source` | the road, from the table above |
| `ShiftScreen.pairs` | the pair screen's evidence, a `ReflectionPairScreen`, whenever the pair road ran |

The templates are the three causes of a shift: `constant` (a zero-point shift), `cos_theta` (a specimen displacement) and `sin_2theta` (transparency).
Each `ShiftTemplateFit` carries:

| Field | Holds |
|---|---|
| `ShiftTemplateFit.name` | the template |
| `ShiftTemplateFit.coefficient` | its amplitude in ° 2θ: z, s in s·cos θ, or t in t·sin 2θ |
| `ShiftTemplateFit.stderr` | the amplitude's standard error |
| `ShiftTemplateFit.r2` | R² of the template alone; 0 on the pair road, where it has no meaning |
| `ShiftTemplateFit.residual_ss` | weighted residual sum of squares against references; on the pair road, 1 over the template's clustered pair count, so smaller is better on both |

Against references, `separable` holds when the runner-up leaves more than twice the best template's residual sum of squares.
The ratio is taken on the residual sum of squares rather than on R², because every template scores R² near 0.99 against a clean trend.
On the pair road, `separable` holds only when one template alone stays competitive, which is rare: `constant` and `cos_theta` tie on every dataset measured.

`ShiftScreen.allowance_deg` and `ShiftScreen.sigma_sys_deg` are different numbers, and the difference decides whether a search finds anything.
The scatter is what the best template leaves; the window has to span the shift's own amplitude, because the observed positions are uncorrected.
On certified SRM 660c they read 0.0078° and 0.037°, a factor of 4.3, and a search declared with the smaller one finds nothing.
So `SearchSpecSpec.shift_allowance_deg` takes the allowance, never the scatter.
A window wider than the shift fails the other way: at 0.060° the same certified pattern returns a cell 293 000 ppm from its certificate, graded `high`.

`index_pattern` sizes its window in this order: a declared `SearchSpecSpec.shift_allowance_deg`; a screen allowance from either measured road; a picked list's own lower-quartile FWHM, capped at 0.05°; and 0.05° otherwise.
The last two are assumed, which [`INDEX_SHIFT_ALLOWANCE`](diagnostics-indexing.md#index_shift_allowance) reports and which caps the grade ([The confidence gate](indexing.md#the-confidence-gate)).

`ShiftScreen.best` names a cause, and `ShiftScreen.separable` says whether the name means anything; over a limited angular range it often does not.
The magnitude survives that and the cause does not.
`ShiftScreen.prediction_spread_deg` gives the cost of picking the wrong cause, counting only the templates that fit comparably: a template the data reject is no candidate cause.
`index_pattern` corrects a cell with a template only when the screen is separable, or when that spread is within the list's median σ(2θ); a template you declare is never overridden ([The search specification](indexing.md#the-search-specification)).
Against references, [`INDEX_SHIFT_DETECTED`](diagnostics-indexing.md#index_shift_detected) or [`INDEX_SHIFT_MODEL_AMBIGUOUS`](diagnostics-indexing.md#index_shift_model_ambiguous) on the report states the screen; when the pairs measured a shift, `index_pattern` reports [`INDEX_SHIFT_FROM_PAIRS`](diagnostics-indexing.md#index_shift_from_pairs).

### Reflection pairs

With no reference positions the shift is still recoverable, from harmonic reflection pairs {eq}`idx-pair`: two lines whose sines stand in an integer ratio, which for any lattice is one equation in the shift and none in the cell {eq}`idx-pair-shift`.
The method's failure mode is accidental agreement, so the evidence is reported in full as a `ReflectionPairScreen`, beside the agreement a structureless list of the same size produces.

| Field | Holds |
|---|---|
| `ReflectionPairScreen.n_candidate_triples` | line pairs whose sine ratio rounds to an integer from 2 to 8, examined |
| `ReflectionPairScreen.n_pairs` | of those, the pairs whose implied shift is within 0.20° |
| `ReflectionPairScreen.n_clustered` | pairs inside the densest window 0.010° either side, the statistic and the members the amplitude is averaged over |
| `ReflectionPairScreen.null_k_mean`, `ReflectionPairScreen.null_k_std` | the same statistic on structureless line lists drawn uniformly in sin²θ over the same range |
| `ReflectionPairScreen.z`, `ReflectionPairScreen.p_value` | the standardised gap from that null, and the empirical p |
| `ReflectionPairScreen.null_replicates`, `ReflectionPairScreen.seed` | how many replicates (200), and the seed that drew them |
| `ReflectionPairScreen.scatter_deg` | scatter of the clustered pairs about the reported amplitude, ° 2θ |
| `ReflectionPairScreen.refuted_templates` | templates the data reject: their concentration is not significant (p above 0.01) and under 60 % of the best template's count |
| `ReflectionPairScreen.declined_reason` | why no shift was reported, when none was |

A shift is reported only when the concentration clears z ≥ 4 and p ≤ 0.01 with at least three pairs in agreement.
When the screen declines, `ShiftScreen.source` reads `"unavailable"` and `ShiftScreen.pairs` still carries the evidence and the reason.
On the published benchmark's bare twenty-line position lists the pairs number one to seven, and the screen declines.

On the fluorapatite list of 135 usable lines the pair screen took about two seconds.
It examined 3721 candidate triples, admitted 100 pairs and clustered 31, against a null of 8.8 ± 1.9 (z = 11.5, and p = 0.005, the smallest 200 replicates can give).
`constant` and `cos_theta` tied at 31 clustered pairs each with amplitudes of −0.038° and −0.036°, `cos_theta` named best on the tighter cluster, `separable` false, and the allowance 0.038°.

The pair method may refute a cause and may not choose between the two that stay collinear.
Read `ReflectionPairScreen.refuted_templates` as "not this one", never as "so that one".
