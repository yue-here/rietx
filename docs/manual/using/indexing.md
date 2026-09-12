# Indexing an unknown cell

Every other chapter assumes you know the cell. This one is for when you do not:
the specimen is unidentified, or a database hit is a guess, and the lattice has
to come out of the pattern itself. Indexing is that step: from the line
positions alone, find a lattice whose calculated reflections land where the
observed lines are.

:::{admonition} Provisional
:class: warning
Indexing is under active development, so this chapter's names are documented
but **not frozen**. `pick_peaks`, `fit_peaks`, `index_pattern`,
`determine_extinction_symbol`, the answer types in `rietx.schemas.indexing` and
the helpers under `rietx.indexing` may change in a 1.x release, because the
engines, the gates and the figures of merit are still being measured against
real data.
Every change is announced in the release notes, and the data contracts a
consumer parses do not move with them.
{ref}`provisional-by-declaration` has the promise in full.
:::

Three calls do it, and each answers a smaller question than a reader usually
wants answered.

| Call | Takes | Returns |
|---|---|---|
| `pick_peaks` | a pattern and an instrument | `PeakList`: every resolvable line, with a fitted position and its own esd |
| `index_pattern` | that list, and the pattern | `IndexingResult`: candidate lattices, ranked and graded |
| `determine_extinction_symbol` | a candidate, and the pattern | `ExtinctionScreen`: the extinction classes that lattice admits |

A fourth call in this chapter indexes nothing. `fit_peaks` fits the peaks
*you* name, which is the same machinery serving a question that is not about a
cell at all: [](#fitting-peaks-you-name).

None of the three returns a single answer, by design.
`IndexingResult` has no `.cell` and no `.best`; `ExtinctionScreen` has no
`.symbol` and no `.space_group`. The only route to one answer is
`IndexingResult.best_or_none` or `ExtinctionScreen.best_or_none`, each of which
returns `None` unless a gate is fully satisfied. On a first run against real
laboratory data, `None` is the ordinary outcome rather than a failure, and the
reasons are on the answer. The gate is
{ref}`described below <the-confidence-gate>`, and what to do about each reason is the
{doc}`agent skill <skill>`'s
§7c rather than this chapter's.

The physics is Part 2. {ref}`ch-indexing` carries the quadratic form the search
is over, what a peak list can support, the figures of merit in both directions,
and the ambiguity that cannot be resolved from positions; {ref}`ch-engines`
carries the three search algorithms. This chapter is the objects and the calls.

## Picking the peaks

`pick_peaks` fits every resolvable line in a pattern and returns a `PeakList`.
Detection proposes maxima and shoulders, neighbouring lines are fitted together
as a group, and every reported position comes out of a profile fit with its own
esd rather than from a maximum.

<!-- api-doc: no-exec — it needs a pattern file on disk -->
```python
import rietx as rx

data = rx.read_pattern("corundum.prn")
ins = rx.Instrument.bragg_brentano(radiation="CuKa")
peaks = rx.pick_peaks(data, ins)
```

The instrument is used for four things and **none of them is refined here**:
the primary wavelength and the emission-line set (the peak positions and the
doublet constraint), the U, V, W, X, Y width law (the separation floor and the
width seeds), `ProfileTCHZ.shape` (so the peak list and the refinement that
follows share one peak shape), and the axial apertures, which are applied and
held.

| Argument | Default | Does |
|---|---|---|
| `two_theta_range` | the whole pattern | restricts detection and fitting to a range |
| `shoulders` | `True` | proposes shoulder seeds from curvature, not only maxima |
| `flag_contamination` | `True` | flags Kβ and tungsten ghosts, which are excluded rather than subtracted |

Abstention is a result here too: a pattern with too few lines comes back as a
list carrying `PEAK_LIST_TOO_SHORT`, never as an exception.

(what-a-list-holds)=
### What a list holds

| Field | Holds |
|---|---|
| `PeakList.peaks` | every fitted component, in 2θ order |
| `PeakList.wavelength` | the primary emission line, Å |
| `PeakList.two_theta_min`, `PeakList.two_theta_max` | the range the lines were picked over |
| `PeakList.source` | `fitted` when this package measured them, `positions` when they were supplied |
| `PeakList.thresholds_version` | which set of thresholds produced the list |
| `PeakList.diagnostics` | what the picker noticed, as `Diagnostic` entries |

`PeakList.usable` is the list every screen and every engine actually runs on:
the lines left after ghosts, failed fits, caller exclusions and inseparable
components are dropped. The dropped lines stay in `PeakList.peaks` so a report
can say why a line went, which a filtered-at-source list cannot.

Five accessors return the usable lines as arrays, which is the form the engines
and the figures of merit want: `PeakList.two_theta`, `PeakList.two_theta_esd`,
`PeakList.q`, `PeakList.q_esd` and `PeakList.intensity`.

On the bundled corundum pattern (7251 points, 5–150° 2θ, Cu Kα) picking takes
about 0.2 s and returns 62 components, 54 of them usable.

### What one line holds

Each entry in `PeakList.peaks` is an `ObservedPeak`: one fitted component, with
the group it was fitted in.

| Field | Holds |
|---|---|
| `ObservedPeak.two_theta` | fitted position of the Kα1 component, ° |
| `ObservedPeak.two_theta_esd` | its esd, carrying the √max(χ²_red, 1) inflation |
| `ObservedPeak.q` | 1/d², Å⁻², derived from the position and the list's wavelength |
| `ObservedPeak.q_esd` | σ(Q), by the exact derivative of that relation |
| `ObservedPeak.intensity` | integrated area of the primary line |
| `ObservedPeak.intensity_esd` | its esd |
| `ObservedPeak.fwhm` | the **group's** combined Γ, ° |
| `ObservedPeak.eta` | the group's pseudo-Voigt mixing, 0 = Gaussian |
| `ObservedPeak.group` | which fitted group this component came from |
| `ObservedPeak.n_in_group` | how many components were fitted simultaneously with it |
| `ObservedPeak.chi2_red` | reduced χ² of that group's fit |
| `ObservedPeak.flags` | what the fit or the screens noticed about this line |
| `ObservedPeak.origin` | `fitted`, `manual` or `edited`: who decided a line is here |

`ObservedPeak.d` is the d-spacing, and `ObservedPeak.usable` is this line's half
of `PeakList.usable`.

Two of those fields are the group's rather than the line's. Within a group, a
fraction of a degree wide, the widths are not separately identifiable, so `fwhm`
and `eta` are shared, and pretending otherwise is what lets a doublet fit
absorb an unresolved neighbour.

Q rather than d or 2θ is the working coordinate throughout, because Q is linear
in the reciprocal metric ({eq}`idx-qform`), which is what makes a cell fit a
linear problem. The list validates that every `ObservedPeak.q` agrees with its
own 2θ, so a peak built by hand with a stale Q raises here rather than
mis-indexing a pattern later.

### The flags

`ObservedPeak.flags` is a closed vocabulary. Five of the twelve take a line out
of `PeakList.usable`; the rest are evidence a consumer weighs.

| Flag | Means | Usable? |
|---|---|---|
| `ghost_kbeta` | a Kβ contamination line | no |
| `ghost_tungsten` | a tungsten L contamination line | no |
| `excluded` | the caller removed it | no |
| `fit_failed` | the group solve did not converge, so the position is the seed | no |
| `not_separable` | a component the fitter believes as a shape and disbelieves as a line | no |
| `no_intensity` | it refined onto its zero intensity bound, so it locates nothing | no |
| `sigma_assumed` | σ was supplied rather than fitted | yes |
| `unresolved_shoulder` | it never separated from its neighbour by half a FWHM | yes |
| `position_at_bound` | the fit pushed to its position bound: detection seeded it in the wrong place | yes |
| `asymmetry_unmodelled` | one-sided asymmetry beyond what the model absorbs | yes |
| `background_extrapolated` | it stands where the background was extrapolated, not measured | yes |
| `axial_tail` | it sits on a much stronger group-mate's axial-divergence tail side | yes |
| `kalpha2_residual` | it sits at a stronger group-mate's predicted Kα2 maximum | yes |

A contamination line is **flagged and excluded, never subtracted**: Rachinger
stripping redistributes the noise and biases what is left. The last three flags
report evidence rather than refusing a line, because a real reflection can
coincide with an extrapolated background, with a stronger line's axial tail or
with a predicted Kα2 position, and one pattern cannot tell which it is. §7b of
the protocol says which ones are usually excluded before a search, and
what that has been measured to cost.

### A peak list from somewhere else

`PeakList.from_positions` builds a list from bare positions: a publication, a
database entry, another program's output.

```python
import numpy as np
import rietx as rx

# LaB6, the first six lines at Cu Kα1, as they would be quoted in a paper
peaks = rx.PeakList.from_positions(
    np.array([21.358, 30.385, 37.442, 43.507, 48.964, 53.996]),
    wavelength=1.540596)

assert peaks.source == "positions"
assert len(peaks.usable()) == 6
assert all("sigma_assumed" in p.flags for p in peaks.peaks)
assert abs(peaks.peaks[0].d - 4.1566) < 1e-3
```

Every line is flagged `sigma_assumed` and `PeakList.source` reads `positions`,
because an assumed σ is *unmeasured*: it must never be quoted as a precision,
and a gate that weights lines by 1/σ² is being handed a constant rather than
information. Intensities default to equal weight, which is what a
position-only list actually says. Pass `two_theta_esd=` if you know better,
and `intensity=` when the source quotes relative intensities, because the search
is driven by the strongest lines and intensities change which lines it uses.


(fitting-peaks-you-name)=
## Fitting peaks you name

`pick_peaks` decides what the lines are. `fit_peaks` does not: you give it
positions, and it fits exactly those. No structure, no space group, no
refinement. It is the call for a width analysis over a chosen set of lines, a
d-spacing lookup, or a check on one reflection.

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

The answer is a `PeakList`, the same object [](#what-a-list-holds) describes, so
everything in it reads the same way. Two things differ, and both are about
provenance: every line carries `origin="manual"`, because these positions are
yours rather than detection's proposals, and the components fitted in each
window are exactly the ones you named.

| | `pick_peaks` | `fit_peaks` |
|---|---|---|
| what is fitted | every line detection resolves | the positions you pass |
| a weak shoulder | proposed, then kept or refused on ΔBIC | fitted only if you name it |
| `ObservedPeak.origin` | `fitted` | `manual` |
| a position with no peak | never arises | returned, flagged `no_intensity` |

Detection still runs. The background envelope, the seed widths and the window
each group is fitted over all come from it, and a position inside a detected
window reuses that window rather than re-sizing one around a subset of its
components. Positions that share a window are fitted **together**, in one
simultaneous solve, because overlapping components fitted separately each bias
the other. A position where detection found nothing gets a fresh window sized
exactly as detection sizes its own, and a position off the end of the pattern
or in a gap is refused by name:

```text
ValueError: only 0 channel(s) around 2θ = 40.0000°; that is a gap or an
excluded region, not a place a peak can be fitted
```

### Naming a position where there is no peak

This is a correct request, not a mistake. A width analysis over a published
line list, or a d-spacing lookup, will name positions that turn out to be
empty, and the answer has to say so.

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
intensity 8e-16   esd(2θ) 3e+15°
flags ['position_at_bound', 'no_intensity']
usable 0 of 1
```

The line comes back **flagged and unusable**, never dropped: a component you
placed is yours to see and remove, and a call that silently returns fewer peaks
than you asked for is a call you cannot check. It is also not a measurement.
A peak reaches the data only through intensity × profile, so a component at
zero intensity has no gradient on its own position: what comes back is wherever
the solve left it, and the esd of 3e+15° is the honest statement of that.
`PeakList.usable` drops it for you; `PeakList.peaks` keeps the reason.

### The neighbour you did not name

If the window holds a component your list left out, its intensity has nowhere
to go but into the components that were fitted. The named positions are then
biased towards it, and χ²_red is the only other sign. Those lines are flagged
`unnamed_neighbour`.

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

Naming the weak neighbour moves the line you actually wanted by 2.7 m°, which
is 2.7 times its own esd, and takes χ²_red from 4.94 to 1.50. The flag is
**reported, not refused**: naming a subset is legitimate, and the esd inflation
by √max(χ²_red, 1) already carries part of the cost. Whether 2.7 esds matters
is yours to judge.

The question is asked of your own fit rather than of detection's seed list: the
residual proposes a position and ΔBIC decides whether it earns its two
parameters, which is how `pick_peaks` decides the same thing. So the flag also
catches a component detection never seeded.

### Widths: a Williamson-Hall analysis

The package fits the peaks; the analysis is four lines of numpy, and writing it
out is better than hiding it behind a helper whose conventions you would have
to look up anyway. Williamson and Hall (1953) separate size from strain by
their different angular dependence: size broadening goes as 1/cosθ, strain as
tanθ, so

$$\beta \cos\theta = \frac{K\lambda}{L} + 4\varepsilon \sin\theta$$

is a straight line in sinθ whose intercept gives the size L and whose slope
gives the strain ε.

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
beta = np.radians(np.array([p.fwhm for p in peaks.peaks]))
slope, intercept = np.polyfit(np.sin(theta), beta * np.cos(theta), 1)

print(f"intercept Kλ/L = {intercept:.3e}  →  L = {0.9 * peaks.wavelength / intercept:.0f} Å")
print(f"slope       4ε = {slope:.3e}  →  ε = {100 * slope / 4:.3f} %")
```

```text
intercept Kλ/L = 1.023e-03  →  L = 1355 Å
slope       4ε = 4.269e-04  →  ε = 0.011 %
```

**Those two numbers are the broadening of the pattern, not of the specimen.**
`ObservedPeak.fwhm` is the width that was measured, and a measured width is the
instrument's own width convolved with whatever the sample adds. On this
fluorapatite the instrument dominates, so 1355 Å is a floor set by the
diffractometer rather than a crystallite size. To get the sample's half, remove
the instrument's first: measure the width law on a standard with
`lab_calibrate`, save it with `save_instrument_profile`, and subtract it — in
the widths for a Williamson-Hall plot, or, better, by refining the sample
broadening terms against it, which is what [](model.md) covers and what
`rietx.model.microstructure` reports with esds. The split itself is Part 2's
{ref}`ch-profiles`.

Two smaller conventions in the four lines above. The plot is in FWHM, not
integral breadth, so K = 0.9 rather than 1: quote which you used, because the
two differ by about 10 % on the same data. And the fit is unweighted, while
`two_theta_esd` and the fitted widths give you everything a weighted fit
needs — a weighted `np.polyfit` is one more argument, and on a list mixing
strong and weak lines it is the right one.

## Whether the list can be indexed

`rietx.indexing.assess_peak_list` answers that, and `index_pattern` calls it
before spending any budget. The answer is a `DataQualityReport`.

| Field | Holds |
|---|---|
| `DataQualityReport.supports_indexing` | can this list be **searched** at all |
| `DataQualityReport.abstained_reason` | why not, when it cannot |
| `DataQualityReport.n_usable`, `DataQualityReport.n_total` | lines that count, of lines picked |
| `DataQualityReport.source` | inherited from the list: `fitted` or `positions` |
| `DataQualityReport.two_theta_min`, `DataQualityReport.two_theta_max` | the range the lines span |
| `DataQualityReport.sigma_two_theta_median`, `DataQualityReport.sigma_two_theta_worst` | position precision, ° |
| `DataQualityReport.relative_sigma_q_median` | median σ(Q)/Q, a resolving power ({eq}`idx-sigma-q`) |
| `DataQualityReport.sigma_over_spacing` | median σ(Q) over the mean spacing between neighbouring Q |
| `DataQualityReport.lines_per_dof` | usable lines ÷ metric degrees of freedom, per system |
| `DataQualityReport.systems_supported` | the systems this list can support a search in |
| `DataQualityReport.fom_undefined` | figures of merit undefined on this list, name → reason |
| `DataQualityReport.volume_envelope` | Smith's volume bound, Å³, **per system** |
| `DataQualityReport.shift` | the systematic-shift screen, or `None` |
| `DataQualityReport.thresholds_version` | which thresholds produced the verdict |
| `DataQualityReport.diagnostics` | what the assessment noticed |

**"Enough lines" is a per-system question, not a number.** The metric has one
free parameter in cubic and six in triclinic ({eq}`idx-subspace`), so the same
list is enormously over-determined for one system and barely determined for
another. `DataQualityReport.lines_per_dof` carries the ratio and
`DataQualityReport.systems_supported` carries the verdict. On the corundum list
above, 54 usable lines read 54.0 per degree of freedom for cubic and 9.0 for
triclinic, and every system is supported.

Whether a list can be searched and whether it can be scored are different
questions, and conflating them once refused a pattern this package indexes
perfectly. Below twenty usable lines the
classical figures are undefined, since de Wolff's M₂₀ and Smith & Snyder's F₂₀
are *defined* on twenty lines ({eq}`idx-m20`, {eq}`idx-fn`), so the search still
runs over the supported systems, ranks on the reduced panel, and names each
missing figure with its reason in `DataQualityReport.fom_undefined`. What that
costs is the grade: a short list can never reach `high`.

`DataQualityReport.volume_envelope` is Smith's (1977) bound on the cell volume
from the d-spacing of the N-th line ({eq}`idx-volume`), and it is per system
because the bound differs by up to 96× across them: a cubic F lattice shows far
fewer distinct lines than a primitive triclinic one of the same volume. It is
the default `max_volume` for a search.

### The systematic shift, and the window it opens

A 2θ shift is measurable before the cell is, and it has to be, because a
candidate's calculated positions are matched against **uncorrected** observed
lines. `DataQualityReport.shift` is a `ShiftScreen`.

| Field | Holds |
|---|---|
| `ShiftScreen.n_lines` | lines the screen used |
| `ShiftScreen.templates` | each template fitted alone, as a `ShiftTemplateFit` |
| `ShiftScreen.best` | the template that fits best, or `None` |
| `ShiftScreen.separable` | whether that name means anything |
| `ShiftScreen.separability_ratio`, `ShiftScreen.max_collinearity` | how far apart the templates are over the angles sampled |
| `ShiftScreen.prediction_spread_deg` | largest disagreement between the **competitive** templates' corrections, ° |
| `ShiftScreen.sigma_sys_deg` | residual scatter the winning template leaves, ° |
| `ShiftScreen.allowance_deg` | what a search window must **span**, ° |
| `ShiftScreen.source` | `measured`, `reflection_pairs` or `unavailable` |
| `ShiftScreen.pairs` | the harmonic-pair evidence, when that is where the number came from |

**`allowance_deg` and `sigma_sys_deg` are not the same number and the
difference decides whether a search finds anything.** The scatter is what the
winning template *leaves*; the allowance has to span the shift's own
*amplitude*, because nothing has corrected the observed positions yet. On
certified SRM 660c the two read 0.0078° and 0.037°, a factor 4.3, and declaring
the smaller one makes the search find **nothing**. Declare
`SearchSpecSpec.shift_allowance_deg` from the allowance, never from the
scatter.

The other direction is worse. A window wider than the shift manufactures a
confident wrong answer: at 0.060° on the same certified pattern the search
returns a cell 293 000 ppm from the certificate, graded `high`. This is why the
allowance is derived rather than guessed, and why an *assumed* one caps the
grade.

`ShiftScreen.best` names a cause (a zero-point error, a specimen displacement,
transparency) and `ShiftScreen.separable` says whether the data can tell them
apart, which over a limited angular range it frequently cannot.
The magnitude survives that; the cause does not. Each `ShiftTemplateFit` carries
`ShiftTemplateFit.name`, `ShiftTemplateFit.coefficient` (the template's
amplitude in ° 2θ), `ShiftTemplateFit.stderr`, `ShiftTemplateFit.r2` and
`ShiftTemplateFit.residual_ss`. The ratio is computed on the residual sum of
squares rather than on R², because every template scores R² ≈ 0.99 against a
clean trend.

With no reference positions the shift is still recoverable, from harmonic
reflection pairs ({eq}`idx-pair`, {eq}`idx-pair-shift`), pairs of lines whose
sines are in an integer ratio, which for any lattice is one equation in the
shift and none in the cell. `index_pattern` runs that screen by default
(`shift_from_pairs=True`); `assess_peak_list` does not, so a report you build
yourself carries `ShiftScreen.source == "unavailable"` unless you ask. Its
evidence is a `ReflectionPairScreen`, reported in full because the method's
failure mode is accidental agreement and the only way to judge that is to see
how much agreement a structureless list of the same size produces.

| Field | Holds |
|---|---|
| `ReflectionPairScreen.n_candidate_triples` | line pairs whose sine ratio rounded to an integer |
| `ReflectionPairScreen.n_pairs` | of those, the ones admitted inside the window |
| `ReflectionPairScreen.n_clustered` | pairs inside the densest window, the statistic itself |
| `ReflectionPairScreen.null_k_mean`, `ReflectionPairScreen.null_k_std` | the same statistic on structureless replicates |
| `ReflectionPairScreen.z`, `ReflectionPairScreen.p_value` | the standardised gap, and the empirical p |
| `ReflectionPairScreen.null_replicates`, `ReflectionPairScreen.seed` | how many replicates, and the seed that drew them |
| `ReflectionPairScreen.scatter_deg` | scatter of the clustered pairs about the reported amplitude |
| `ReflectionPairScreen.refuted_templates` | templates the pair evidence rules out |
| `ReflectionPairScreen.declined_reason` | why no shift was reported, when none was |

The method may refute a cause and may not choose between the two that stay
collinear. Read `ReflectionPairScreen.refuted_templates` as "not this one",
never as "therefore that one".

## Running the search

<!-- api-doc: no-exec — a real search costs seconds to minutes -->
```python
result = rx.index_pattern(peaks, data=data, instrument=ins)
```

| Argument | Default | Does |
|---|---|---|
| `peaks` | required | the `PeakList` to index; omit it and pass `data` + `instrument` to have one picked |
| `data` | `None` | the pattern. **Supplying it is what turns whole-profile validation on** |
| `instrument` | `None` | needed with `data`, and by the validation fits |
| `spec` | `None` | the search bounds, as the frozen `SearchSpec` dataclass that `SearchSpecSpec` mirrors field for field |
| `preset` | `quick` | the whole-run ceiling; `full` removes it |
| `engines` | every registered engine | which searches to run |
| `quality` | `None` | a `DataQualityReport` you already computed |
| `shift_from_pairs` | `True` | recover the shift allowance from harmonic pairs |
| `validate` | `True` | run the Le Bail validation when a pattern is available |
| `check_top` | `None` | how many candidates get the expensive per-candidate checks |
| `two_theta_limits` | `None` | restrict the range the validation fits use |
| `events` | `None` | the streaming event ladder, as everywhere else |
| `cancel` | `None` | a `CancelToken`; a cancelled search **returns what it has** |

Two of those defaults should be kept rather than tuned. Passing `data` is
what makes validation possible, and without it every candidate caps at
`medium`. Leaving `engines` alone is what lets `high` mean anything at all, for
the reason in the next section.

### Three engines, and why the default is all of them

Confidence in this package is engines **agreeing**, not any statistic. The ones
registered today fail in different ways, which is the whole point: a wide search
domain defeats one, a poisoned base line defeats another, a bad starting basin
defeats the third. Restricting `engines` narrows what the answer is able to say,
and adding an engine raises the bar rather than diluting it, because `high`
means every engine that ran found the same lattice.

Ask which are here rather than assuming, since the set is a registry:

```python
import rietx as rx

caps = rx.capabilities()
engines = {engine.name: engine.description for engine in caps.indexing_engines}
assert engines and all(engines.values())
```

Each row is an `EngineCapability`, and both of its fields,
`EngineCapability.name` and `EngineCapability.description`, are quoted from
that live registry, so a client's engine checkboxes and the agent schema cannot
name different sets. [](agents.md) has the rest of `capabilities()`.

Only one of the three carries an exhaustiveness claim: when the branch-and-bound
engine finishes a system, "no cell here" is evidence. That claim survives only
where `IndexingResult.search_complete` is true for the system, which is what
makes that field one to read before concluding anything from a silence.

### Presets, budgets, and the three states of a system

An exhaustive search over seven crystal systems has no natural stopping point,
so runs are bounded, and the bound is reported rather than hidden. The presets
come from `Capabilities.search_presets`, one `SearchPresetCapability` each.

| Field | Holds |
|---|---|
| `SearchPresetCapability.name` | the preset's key: `quick` or `full` |
| `SearchPresetCapability.title` | its display name |
| `SearchPresetCapability.description` | what it bounds, and what the worst case is |
| `SearchPresetCapability.when_to_use` | the chooser's sentence |
| `SearchPresetCapability.default` | whether `index_pattern` resolves it when the caller names none |

`quick` is the default: every engine, every requested system, and a whole-run
ceiling covering search, probe and validation. **Nothing is narrowed**: no
engine dropped, no system dropped, no search box shrunk. What a binding ceiling
cuts is the trailing low-symmetry systems, which is the documented cost of
running cheapest-first, and it says so with `INDEX_BUDGET_EXHAUSTED`. `full`
removes the whole-run ceiling and leaves only the per-slice budget, which is
the pre-1.0 behaviour and the right choice for a rerun when a `quick` run
reported that the answer might live in a system it never reached.

There are two budgets and they are per different things.
`SearchSpecSpec.budget_seconds` is per **(engine × crystal system)** slice;
`SearchSpecSpec.total_budget_seconds` is the whole run. Units run system-major,
every engine finishing one system before any engine starts the next, so a
binding deadline sacrifices trailing systems for every engine
equally, and a completed system holds every engine's answer, which is what the
agreement gate needs. `rietx.indexing.engines.estimate_ceiling` is the
arithmetic for choosing a value before starting.

After a run, three states are distinguishable, and the distinction is the
answer's honesty:

- the system is in `IndexingResult.systems_searched` with
  `IndexingResult.search_complete` **true**, searched to exhaustion;
- in `systems_searched` with `search_complete` **false**, truncated, so a
  negative result there means nothing;
- **absent** from `systems_searched`, never reached at all.

Measured on the bundled corundum pattern with everything left at its defaults:
120.2 s wall clock, all three engines, five of the seven systems entered, of
which cubic and hexagonal completed, and monoclinic and triclinic never
started. The answer says all of that.

### The search specification

`SearchSpecSpec` is the full control surface. It is flat and complete rather
than a handful of convenience knobs, because the engines' agreement only means
something if they were given identical bounds.

| Field | Default | Does |
|---|---|---|
| `SearchSpecSpec.systems` | all seven | which crystal systems to search, in decreasing symmetry |
| `SearchSpecSpec.centrings` | every centring a system admits | per-system Bravais centrings; an empty list is refused |
| `SearchSpecSpec.min_d_axis`, `SearchSpecSpec.max_d_axis` | 2 Å, 25 Å | the principal d-spacing range; raising the top costs exponentially |
| `SearchSpecSpec.min_volume` | 15 Å³ | volume floor |
| `SearchSpecSpec.max_volume` | Smith's envelope | volume ceiling, taken verbatim when declared |
| `SearchSpecSpec.n_unindexed` | 2 | search lines a cell may leave unexplained and still be accepted |
| `SearchSpecSpec.n_search_lines` | 20 | observed lines the search is **driven** by, the strongest N |
| `SearchSpecSpec.k_sigma` | 3 | matching window in units of each line's own σ |
| `SearchSpecSpec.shift_allowance_deg` | 0 | a systematic allowance **you measured** |
| `SearchSpecSpec.shift_template` | `None` | re-fit a surviving candidate with this shift column |
| `SearchSpecSpec.budget_seconds` | 30 s | per (engine × system) |
| `SearchSpecSpec.total_budget_seconds` | the preset's | the whole run |
| `SearchSpecSpec.preset` | `None`, resolving to `quick` | which preset governs the ceiling |
| `SearchSpecSpec.max_candidates` | 12 | how many candidates the answer reports |
| `SearchSpecSpec.seed` | 0 | the stochastic engine's seed, and part of its answer |
| `SearchSpecSpec.prior_cells` | `None` | cells from a structural analogue, to try first |
| `SearchSpecSpec.prior_spacegroups` | `None` | space-group symbols from that analogue |

`SearchSpecSpec.to_spec` converts it to the `SearchSpec` dataclass
`index_pattern` takes. The two mirror each other field for field, held by a
test, because the same controls are the agent request's, the project
document's and the GUI form's:

```python
import rietx as rx
from rietx.schemas.indexing import SearchSpecSpec

controls = SearchSpecSpec(systems=["trigonal", "hexagonal"],
                          centrings={"trigonal": ["R"]},
                          max_volume=600.0, budget_seconds=60.0)
spec = controls.to_spec()
assert spec.systems == ("trigonal", "hexagonal")
assert spec.max_volume == 600.0
```

Several of those fields refuse rather than narrow in silence. An unknown
crystal system, centring, shift template or preset raises with the live
vocabulary in the message; an empty centring list raises rather than skipping
the system, because omitting the key is how a system keeps its full set; and a
prior cell with a non-positive axis or an angle outside (0, 180)° raises too.

`SearchSpecSpec.n_search_lines` is the one to leave alone. Raising it is
neither free nor safe: a cell must index all but `n_unindexed` of *those*
lines, an absolute budget, so every extra foreign line admitted can refute the
true cell rather than merely rank it lower.

A prior steers the search rather than gating it. A declared `prior_cells` entry
puts its crystal system at the front of the queue, seeds the stochastic engine's
starting basin with its metric, and is checked against the lines the engines'
own way. No
system is dropped and no range is changed, so a wrong prior costs time rather
than truth, and `INDEX_PRIOR_USED` records what was assumed. Declare one
whenever you have a database hit or an isostructural analogue; §7d of the
protocol has the worked example.

`IndexingControls` is the same thing one level up: the settings an indexing
*run* carries that are not the data.

| Field | Holds |
|---|---|
| `IndexingControls.search` | the `SearchSpecSpec` |
| `IndexingControls.engines` | which engines to run |
| `IndexingControls.validate_candidates` | whether to run whole-profile validation |
| `IndexingControls.check_top` | how many candidates get the expensive checks |

It is what a project document persists ([](files.md)), so a run can be repeated
from a stored setting rather than from a call site.

## The result object

`IndexingResult` is a ranked list of hypotheses with the evidence behind each,
plus what the search covered.

| Field | Holds |
|---|---|
| `IndexingResult.candidates` | the ranked `CellCandidate` list |
| `IndexingResult.engines_run` | engines that actually ran, the denominator of the agreement gate |
| `IndexingResult.systems_searched` | systems any engine covered |
| `IndexingResult.search_complete` | per system: did every engine that searched it exhaust its domain |
| `IndexingResult.engine_stats` | per-engine counters, prefixed with the engine's name |
| `IndexingResult.fom_panel_disagrees` | do the panel's members put different candidates first |
| `IndexingResult.quality` | the `DataQualityReport` the run used |
| `IndexingResult.validated` | was a pattern supplied, so validation could run at all |
| `IndexingResult.n_usable_lines` | usable lines the answer is about |
| `IndexingResult.wavelength` | the primary wavelength, Å |
| `IndexingResult.preset` | which preset governed the ceiling, or `custom` |
| `IndexingResult.provenance` | version, timestamp and the spec, as everywhere else |
| `IndexingResult.thresholds_version` | which gates and vocabularies produced the grades |
| `IndexingResult.diagnostics` | run-level findings |

Result-level and candidate-level statements are kept apart on purpose.
`IndexingResult.diagnostics` says things about the run (a truncated budget,
systems not covered, an assumed allowance) while a statement about one cell
lives in that candidate's own `CellCandidate.diagnostics` and
`CellCandidate.confidence_caveats`.

### One candidate

| Field | Holds |
|---|---|
| `CellCandidate.cell`, `CellCandidate.cell_esd` | a, b, c (Å) and α, β, γ (°), with esds |
| `CellCandidate.system`, `CellCandidate.centring` | crystal system, and Bravais centring letter |
| `CellCandidate.lattice_group` | the **absence-free** group of the lattice: holohedry plus centring |
| `CellCandidate.volume`, `CellCandidate.volume_esd` | cell volume, Å³ |
| `CellCandidate.af` | the six quadratic-form parameters actually fitted ({eq}`idx-af`) |
| `CellCandidate.n_indexed`, `CellCandidate.n_lines` | lines this cell explains, of lines offered |
| `CellCandidate.chi2_red` | reduced χ² of the metric fit |
| `CellCandidate.shift_template`, `CellCandidate.shift_coefficient`, `CellCandidate.shift_esd` | the shift column re-fitted with the cell, if one was |
| `CellCandidate.fom` | the figure-of-merit panel, as `FigureOfMerit` entries |
| `CellCandidate.found_by` | which engines produced this lattice |
| `CellCandidate.ambiguity` | geometrically indistinguishable partners |
| `CellCandidate.bravais` | the two independent opinions on the lattice symmetry |
| `CellCandidate.lebail` | the whole-profile test, or `None` if it never ran |
| `CellCandidate.confidence` | `high`, `medium` or `low` |
| `CellCandidate.confidence_caveats` | every reason it is not `high` |
| `CellCandidate.diagnostics` | findings about this candidate |

`CellCandidate.fom_value` reads one panel member by name and returns `None`
rather than raising, because which members exist depends on what the list
could support.

`CellCandidate.lattice_group` is the absence-free group, never a plausible
space group, and the distinction is load-bearing: a group carrying reflection
conditions would hide exactly the reflections whose absence is not yet
established, and hiding them is how an oversized cell passes.

### The figure-of-merit panel

The panel ranks candidates rather than scoring them. A margin is comparable
within one member and not across them, so the members vote rather than being
summed, and each carries what it is blind to.

| Field | Holds |
|---|---|
| `FigureOfMerit.name` | which member this is; `IndexingEvidence.fom_ranked` lists the ones a given run had |
| `FigureOfMerit.value` | its value |
| `FigureOfMerit.n_lines`, `FigureOfMerit.n_possible` | lines it used, and lines the lattice allows |
| `FigureOfMerit.k_sigma` | the matching window it was computed at, in units of each line's σ |
| `FigureOfMerit.mean_discrepancy` | mean \|Δ\| of the matched lines, in the member's own units; −1 when nothing matched, which is not zero |
| `FigureOfMerit.blind_spot` | what this member cannot see |

`FigureOfMerit.blind_spot` is a field rather than documentation because every
published figure of merit has a failure mode, and a consumer that reads a value
without it is one step from a confident wrong answer. M₂₀'s own text says that
it counts lattice-possible lines, so it is blind to space-group extinctions,
and that its mean discrepancy is trimmed to match what the search was allowed
to leave unindexed.

On a full-length list the panel runs to seven members: de Wolff's M₂₀ and Smith
& Snyder's F_N ({eq}`idx-m20`, {eq}`idx-fn`), three coverage fractions, and
Oishi-Tomiyasu's two reversed figures. Coverage is scored in **both**
directions, and that is what the reversed members are for: share-of-observed
alone puts a supercell above the truth, since a supercell indexes every
observed line, while the reversed direction asks how much of what the cell
predicts was actually seen.

### The lattice symmetry, and its ambiguities

`CellCandidate.bravais` is a `BravaisOpinion`: two independent readings of the
same reduced cell, kept apart on purpose, because gemmi's tolerance is an
obliquity in degrees and spglib's is a distance in Å, so a disagreement between
them is information about the cell rather than a bug in either.

| Field | Holds |
|---|---|
| `BravaisOpinion.system` | the symmetry that survives the whole tolerance sweep |
| `BravaisOpinion.system_loosest` | the highest symmetry any tolerance reported |
| `BravaisOpinion.system_gemmi`, `BravaisOpinion.system_spglib` | each method's own answer |
| `BravaisOpinion.ambiguous` | the symmetry appears only at a loose tolerance |
| `BravaisOpinion.methods_disagree` | the two methods do not agree |
| `BravaisOpinion.reduced_cell` | the Niggli-reduced cell the symbols refer to |

A powder pattern carries only the *length* of a reciprocal vector, so distinct
lattices can produce the same line positions ({eq}`idx-hnf`). Those are
reported, never resolved, as `AmbiguityPartner` entries.

| Field | Holds |
|---|---|
| `AmbiguityPartner.cell`, `AmbiguityPartner.system`, `AmbiguityPartner.volume` | the partner lattice |
| `AmbiguityPartner.transformation` | the integer basis transformation to it |
| `AmbiguityPartner.index` | \|det\| of that transformation |
| `AmbiguityPartner.discriminating_reflections` | the hkl that would break the tie |
| `AmbiguityPartner.discriminating_two_theta` | where a line would have to appear, or be absent, to do so |

The discriminating reflections are what make an ambiguity actionable rather
than merely honest: they say which part of the pattern to measure again, or
further.

### The whole-profile test

The figure-of-merit panel sees at most twenty lines. A Le Bail fit against the
whole pattern sees three things the panel cannot: lines beyond the panel,
reflections *predicted where there is no intensity*, and impurity content. The
middle one is the classic doubled-cell false positive, and it is why
validation is mandatory rather than optional. `CellCandidate.lebail` is that
test, as a `LeBailValidation`.

| Field | Holds |
|---|---|
| `LeBailValidation.rwp`, `LeBailValidation.gof` | the fit's agreement |
| `LeBailValidation.space_group` | the absence-free lattice group it used |
| `LeBailValidation.n_reflections` | reflections in the fitted range |
| `LeBailValidation.predicted_but_absent` | reflections the lattice predicts where the pattern has none |
| `LeBailValidation.unmatched_observed` | observed lines with no calculated reflection nearby |
| `LeBailValidation.predicted_but_absent_two_theta`, `LeBailValidation.unmatched_observed_two_theta` | where each of those is, ° |
| `LeBailValidation.status` | the underlying refinement's status; `failed` is evidence, not a crash |
| `LeBailValidation.n_stages` | stages the validation plan ran |
| `LeBailValidation.diagnostics` | findings from the fit |

The fit **holds the cell**: the candidate is the hypothesis under test, and
letting it walk would validate a different cell from the one reported. What it
frees is the background, exactly one peak-position parameter chosen from the
candidate's own shift template, and then the widths. It is single-phase, which
is a measured constraint rather than a simplification: Le Bail partitioning has
nothing to arbitrate two phases claiming the same channel.

`LeBailValidation.rwp` is deliberately **not** a panel member. It costs a
refinement, so it is computed for a shortlist rather than for every candidate,
and reading it as a rank would reintroduce the blind spot it exists to close,
since a bigger cell fits better. Read `predicted_but_absent` as "this cell
predicts lines the pattern lacks", never as "this cell is too big": it counts
against the *lattice* group, so a space-group extinction (a glide plane, a
screw axis) refutes a perfectly correct cell, and only the extinction screen
below separates the two.

(the-confidence-gate)=
### The confidence gate

`CellCandidate.confidence` is `high`, `medium` or `low`. The top level is
**agreement between independent engines**, not a threshold on any statistic,
and every reason a candidate falls short is a member of a closed vocabulary in
`CellCandidate.confidence_caveats`. Six of the twelve *refute* the candidate and
drop it to `low`: each is positive evidence against the cell, or evidence that
the data cannot choose. The other six *cap* it at `medium`.

| Caveat | Means | Effect |
|---|---|---|
| `geometric_ambiguity` | a distinct lattice fits the positions as well | refutes |
| `fom_panel_disagrees` | the panel's members put different candidates first | refutes |
| `predicted_but_absent` | the Le Bail fit found reflections where the pattern has no intensity | refutes |
| `indexed_fraction_low` | the cell explains less than 90 % of the usable lines | refutes |
| `volume_unphysical` | the volume is outside what the data can support | refutes |
| `validation_failed` | the Le Bail fit raised or diverged | refutes |
| `engines_disagree` | fewer than every engine that ran found this lattice | caps |
| `not_validated` | this candidate has no Le Bail fit behind it | caps |
| `search_incomplete` | a budget expired, so a negative result elsewhere means nothing | caps |
| `shift_allowance_assumed` | the matching window was widened by an assumed systematic | caps |
| `fom_panel_reduced` | the list is too short for the classical figures | caps |
| `bravais_ambiguous` | the lattice symmetry appears only at a loose tolerance, or the methods disagree | caps |

`not_validated` and `validation_failed` are separate on purpose: the absence of
a test and a failed test are different statements, and only the second is
evidence about the cell.

**`not_validated` has two causes, and they are not the same news.** No pattern
was supplied, so no candidate could be validated, which is what
`IndexingResult.validated` reports at run level. Or a pattern *was* supplied and
this candidate's fit did not run, because the shortlist is validated top-down and
`SearchSpec.total_budget_seconds` expired partway. `INDEX_BUDGET_EXHAUSTED` names
the second, counting the candidates it cost. Measured on the round-robin
corundum pattern under a 45 s ceiling: `IndexingResult.validated` is `True` and
all twelve candidates carry `not_validated`, so reading the run-level flag as the
per-candidate one inverts the answer.

`IndexingResult.best_or_none` returns a candidate only when exactly one is
`high` and it has no ambiguity partners. Everything else returns `None`: nothing
found, two cells that both explain the pattern, an unvalidated search, or an
assumed tolerance.

**Never take `candidates[0]` because it is ranked first.** The ranking orders
the hypotheses and the gate judges them; they are different questions. The
order leads with corroboration, the candidates at least two engines found, and
ranks the panel within that, which is closer to the gate's reading than a
panel ranking alone, and still not it.

On the corundum run above, the certified trigonal *R* lattice comes back at
rank 1, found by two of the three engines, with a Le Bail fit that converged,
and grades `low` on five caveats, so `best_or_none` returns `None`. Two of the
five carry the reading. `predicted_but_absent` counts 12 reflections, which is
what a space-group extinction looks like from a lattice group that does not
know about it, and the extinction screen below is what separates that from an
oversized cell. `search_incomplete` is there because the ceiling cut the
trailing systems. Neither says the cell is wrong; they say what has not been
established, which is the whole difference between this answer and a confident
one.

## The evidence view

The gate exists for unattended use, where a machine that cannot weigh evidence
must never be handed one cell. A consumer that *can* weigh evidence wants the
inputs to that judgement instead, and `IndexingResult.evidence` is those inputs
in one place, as an `IndexingEvidence`. Everything in it is a projection of
fields the result already carries, computed on each call, so the two can never
disagree.

| Field | Holds |
|---|---|
| `IndexingEvidence.candidates` | one `CandidateEvidence` per candidate, in rank order |
| `IndexingEvidence.systems_searched`, `IndexingEvidence.search_complete` | what the search covered |
| `IndexingEvidence.systems_supported` | what the peak list supports at all |
| `IndexingEvidence.n_usable_lines` | lines the answer is about |
| `IndexingEvidence.fom_ranked` | the panel members that ranked every candidate |
| `IndexingEvidence.fom_undefined` | members that could not be computed, each with its reason |
| `IndexingEvidence.validated` | whether a pattern was supplied at all |

| Field | Holds |
|---|---|
| `CandidateEvidence.index` | position in `IndexingResult.candidates`, the address other calls take |
| `CandidateEvidence.cell`, `CandidateEvidence.cell_esd`, `CandidateEvidence.system`, `CandidateEvidence.centring`, `CandidateEvidence.volume` | the lattice |
| `CandidateEvidence.confidence` | the grade |
| `CandidateEvidence.caveats` | every caveat **with its kind** |
| `CandidateEvidence.found_by` | which engines found it |
| `CandidateEvidence.n_indexed`, `CandidateEvidence.n_lines` | its coverage |
| `CandidateEvidence.fom` | the panel members that ranked it, name → value |
| `CandidateEvidence.validated` | whether a Le Bail fit ran on **this** candidate |
| `CandidateEvidence.lebail_status`, `CandidateEvidence.lebail_rwp` | that fit's outcome |
| `CandidateEvidence.predicted_but_absent`, `CandidateEvidence.unmatched_observed` | its two detector counts |
| `CandidateEvidence.ambiguity_partners` | how many partners it has |

`CaveatEvidence` is the piece `confidence_caveats` withholds:
`CaveatEvidence.name` is the caveat and `CaveatEvidence.kind` is `refuting` or
`capping`. That split lives in a package constant a JSON consumer cannot see,
and an agent told `predicted_but_absent` and `not_validated` in the same breath
needs to know the first argues against the cell while the second only says a
question was never asked.

:::{admonition} For agents
:class: agent
Read `IndexingResult.evidence` rather than the gate alone, and read
`CandidateEvidence.lebail_rwp` **beside** the two detector counts rather than
scoring on it. The three together are what let a reader notice that a detector
has failed: on one measured pair, the correct cell reads
`predicted_but_absent` 2 and its wrong rival reads 0, which is backwards, while
Rwp reads 0.25 against 0.79. A reasoner given both can see that; the gate, reading
one number, cannot. This is an argument for surfacing Rwp, never for ranking on
it.

The same shape survives serialisation: `IndexingResult.model_dump` carries no
`cell` key either, and `IndexingResult.evidence` is the companion projection to
dump beside it. [](agents.md) has the rest of the programmatic surface.
:::

`rietx.viz.plot_indexing` draws the ranked candidates as tick rows against the
pattern, with the Le Bail panel, from the result alone. The visual check is
part of the answer rather than documentation of it: a wrong cell that scores
well usually looks wrong immediately.

## From a candidate to a phase

A candidate is a lattice, and a refinement needs a `Structure`.
`rietx.indexing.structure_from_candidate` builds the single-phase model that
the Le Bail validation itself uses:

<!-- api-doc: no-exec — it needs a candidate from a real search -->
```python
from rietx.indexing import structure_from_candidate

candidate = result.best_or_none()       # or one you chose after reading the evidence
phase = structure_from_candidate(candidate)
lebail = rx.refine(data, phase, ins, mode="lebail", plan="profile_only")
```

Two things about it are load-bearing. The dummy atom is mandatory, because a
phase cannot have an empty atom list and a candidate cell has no structure yet,
which is the entire point. And in Le Bail mode every atom path is force-fixed, so it
contributes nothing and shows as `mode_fixed` rather than editable in
[](model.md)'s listing. And `space_group` defaults to the **absence-free
lattice group**, for the reason `CellCandidate.lattice_group` exists: a
plausible-looking space group would hide the very reflections whose absence has
not been established.

The reverse direction closes too. When a refinement's Layer 2 emits
`reindex_or_recheck_cell`, on peak offsets beyond the linearisation radius
across most of the misfitting regions, that action has something to call: pick peaks
and index the same pattern. [](report.md) has the action, and §7d of the
protocol has the loop.

## The extinction symbol

Once a lattice is established, the next question is which reflections are
systematically absent. `determine_extinction_symbol` answers it, and answers it
as a **class**, never as a space group.

<!-- api-doc: no-exec — one Le Bail fit per surviving class -->
```python
screen = rx.determine_extinction_symbol(data, candidate, ins,
                                        two_theta_limits=(15.0, 90.0))
klass = screen.best_or_none()
if klass is not None:
    print(klass.symbol, klass.space_groups)
```

| Argument | Default | Does |
|---|---|---|
| `data`, `candidate`, `instrument` | required | the pattern, the lattice under test, and the instrument |
| `peaks` | `None` | a peak list, used to seed the shared profile fit |
| `two_theta_limits` | the whole pattern | the range classes are enumerated and judged over |
| `k_sigma` | 3 | the matching window, in units of each line's σ |
| `max_classes` | `None` | cap the number of classes fitted |
| `cancel` | `None` | cooperative cancellation |

The pipeline is one shared profile fit of the absence-free lattice group, a
reference fit of the absence-free class under the same protocol, then one Le
Bail fit per class scored by ΔBIC and by Hamilton's ratio test against that
reference, and finally a direct absence test: intensity at a position the class
forbids refutes it, with the hkl named. Every class is fitted with the shared
instrument **frozen**, so no class can compensate a missing reflection with a
wider peak.

The candidate's `CellCandidate.system` is taken as given rather than
re-screened, because when the Bravais screen reported an ambiguity that field
is the conservative reading, and enumerating classes in a higher symmetry would
offer classes the lattice may not have.

| Field | Holds |
|---|---|
| `ExtinctionScreen.candidates` | the ranked `ExtinctionCandidate` list |
| `ExtinctionScreen.lattice_group` | the absence-free group every class is compared against |
| `ExtinctionScreen.cell`, `ExtinctionScreen.system`, `ExtinctionScreen.centring` | the lattice screened |
| `ExtinctionScreen.wavelength` | the primary wavelength, Å |
| `ExtinctionScreen.two_theta_range` | the range judged over, which is part of the answer |
| `ExtinctionScreen.n_classes`, `ExtinctionScreen.n_screened` | classes enumerated, classes actually fitted |
| `ExtinctionScreen.reference_rwp`, `ExtinctionScreen.reference_chi2`, `ExtinctionScreen.reference_lines` | the absence-free reference fit |
| `ExtinctionScreen.profile_rwp` | the shared profile fit every class inherits |
| `ExtinctionScreen.n_points` | channels in the fitted range |
| `ExtinctionScreen.status` | the screen's own status |
| `ExtinctionScreen.thresholds_version` | which thresholds produced the ranking |
| `ExtinctionScreen.diagnostics` | findings, including the one that names the groups a class cannot separate |

Two classes differing only outside `ExtinctionScreen.two_theta_range` are one
class here, which is why the range is reported as part of the answer rather
than as a setting.

| Field | Holds |
|---|---|
| `ExtinctionCandidate.symbol` | the IT-style extinction symbol, derived from the members |
| `ExtinctionCandidate.representative` | the H-M symbol whose reflections were generated |
| `ExtinctionCandidate.space_groups` | **every** space group in the class, in IT number order |
| `ExtinctionCandidate.conditions` | the derived reflection conditions, for a human to check |
| `ExtinctionCandidate.conditions_complete` | whether the derivation named every absence |
| `ExtinctionCandidate.n_lines` | distinct lines this class predicts in range |
| `ExtinctionCandidate.n_absent` | lattice lines it forbids |
| `ExtinctionCandidate.n_testable` | of those, the ones the data can actually check; `None` until `screened` |
| `ExtinctionCandidate.n_present` | testable forbidden positions carrying intensity, the refutation |
| `ExtinctionCandidate.forbidden_hkl`, `ExtinctionCandidate.forbidden_two_theta` | which reflections those are, and where |
| `ExtinctionCandidate.rwp`, `ExtinctionCandidate.gof`, `ExtinctionCandidate.chi2` | its own Le Bail fit |
| `ExtinctionCandidate.delta_bic` | BIC against the absence-free reference; **negative favours this class** |
| `ExtinctionCandidate.absences_rejected` | Hamilton's test in the same direction |
| `ExtinctionCandidate.screened` | was this class actually fitted |
| `ExtinctionCandidate.refuted`, `ExtinctionCandidate.refuted_reason` | refuted, and why |
| `ExtinctionCandidate.diagnostics` | findings about this class |

`n_absent` and `n_testable` answer different questions and the gap between them
is usually large. Three kinds of forbidden position are not observations: one
outside the fitted range, one coinciding with a line the class still allows, and
one whose window this class's own fit already fills with a neighbour's **tail**.
An absence hiding under a neighbour is not an absence you saw, and a window
already carrying a tail measures how well that tail is modelled rather than
whether the absence holds. The third test is why `n_testable` is `None` until
`ExtinctionCandidate.screened`: it is a question about the class's own fit, so
before that fit the count is unknown rather than zero.

Refutation is one-sided by construction. A class asserts absences, so
intensity where it forbids one contradicts it; a class claiming too *few*
absences asserts nothing the data can falsify, and is outranked rather than
refuted. `ExtinctionScreen.best_or_none` therefore returns a class only when it
was fitted, is not refuted, rests on at least one absence the data could test
(or is the absence-free class itself, whose claim is that there is nothing to
see), is separated from the next surviving class by a decisive ΔBIC margin, and
**no unrefuted class was left unfitted**, because a `max_classes` cap or a
cancelled run leaves an unasked question, which must not read as a clean
answer.

On the GSAS-II fluorapatite tutorial pattern the screen enumerates seven
classes over 15–90° in about two seconds and returns `P 63 - -`, whose members
are `P 63`, `P 63/m` and `P 63 2 2`, with one condition, `00l: l = 2n`, and
ΔBIC −21.8 against the absence-free class. That is a complete answer rather
than a hedge: the mirror and the two-folds that separate those three produce no
absences at all, so no counting time distinguishes them, and
`EXTINCTION_GROUPS_NOT_SEPARABLE` says so. Choosing inside a class is chemistry
rather than diffraction, and any member can be handed to
`structure_from_candidate` for the fit that follows, because they predict the
same reflections at the same positions.

**A forbidden position is evidence only where the class's own fit is quiet
there.** The absence test integrates the residual over ±½ FWHM and asks whether
it clears 3σ, so where the window already holds a neighbour's tail, what it
measures is the accuracy of that tail. Measured on the corundum pattern above,
over 20–90°: at **sham** positions 1–3 FWHM from an allowed line, carrying no
reflection of any kind, the same test clears 3σ on 40–50 % of probes and reaches
24.7σ, and it does so on the low-angle flank only, which is the unmodelled
axial tail.
So `n_testable` keeps a position only when the class's own model predicts less
intensity in that window than the test's own threshold, which means no error in
a neighbour's tail, not even a total one, can manufacture a refutation.

That is what returns the right answer here. α-Al₂O₃ is certified `R -3 c`, and
over 20–90° with the widths seeded from the peak list the screen returns
`R - c -` = {`R 3 c`, `R -3 c`} at ΔBIC −218, with five testable positions all
absent: the certified group listed, never chosen, beside the
non-centrosymmetric partner no counting time separates from it.

**Read `ExtinctionScreen.profile_rwp` before believing a refutation anyway.**
Every class is fitted with the shared instrument frozen, so a poor shared fit is
a poor screen, and the gate above bounds what a *neighbour* can do, not what a
wrong profile can. Same specimen, same certified cell, over the whole 5–150°
range with the round-robin instrument's declared widths: the shared fit reaches
Rwp 0.270 against 0.149, its fitted peaks come out a third too wide, four
forbidden positions read as occupied, and the certified class is refuted. So
give the screen a range and a width law its profile fit can actually match, and
read `ExtinctionScreen.profile_rwp` to check that it did.

Refutation still outranks ΔBIC wherever a testable position does carry
intensity: a class asserts absences, and no amount of evidence *for*
it buys back a position that contradicts it. It makes the named reflections
ones to check either way, since a single flagged position can be an impurity
line rather than a violated absence, and this specimen's own indexing run reported 49
observed lines its top candidate did not explain. §7e of the protocol says how
to make that check.

## Further reading

- **What to do about each answer**: the [agent
  skill <skill>`,
  §7b (peak-picking diagnostics), §7c (the answer's own diagnostics), §7d (the
  closed loop from an unknown pattern to a refinement), §7e (extinction) and
  §7f (the gate against the evidence). This chapter is the surface; that is the
  judgement, and neither restates the other.
- **The physics**: {ref}`ch-indexing` and {ref}`ch-engines`.
- **What comes next**: [](refining.md) for the fit the cell feeds, and
  [](report.md) for the report that says whether it holds up.
