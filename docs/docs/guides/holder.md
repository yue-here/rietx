(guide-holder)=
# How to fit a peak from the sample holder

Append a `PeakComponent` to `Instrument.extra_components` with bounds around the line, and free `instrument.extra_components.*` in a stage after the scale and background.

A sharp peak that no phase in the model explains can come from the sample holder, a mount, a window or an unidentified impurity.
If it sits on empty background, leave its region out of the fit, as [How to limit the fit range or leave out a region](range.md) shows.
Declare it when it overlaps a reflection of the sample, so the channels under it stay in the fit.
GSAS-II calls this a background peak, and TOPAS an `xo_Is` peaks phase.

## Declare the peak

Give the line's position, a starting area and width, and a range for each:

```python
import rietx as rx

instrument = rx.Instrument.bragg_brentano(radiation="CuKa")
instrument.extra_components = [rx.PeakComponent(
    label="steel holder 110",
    center=rx.Parameter(value=44.6, min=44.4, max=44.9, unit="deg"),
    area=rx.Parameter(value=10.0, min=0.0, unit="counts*deg"),
    fwhm=rx.Parameter(value=0.1, min=0.02, max=0.4, unit="deg"))]
assert instrument.extra_components[0].center.vary is False
```

`center` is the line's 2θ for Kα1, and `area` its integrated intensity in counts·degrees.
`center` and `fwhm` need a finite `min` and `max`, because rietx evaluates the peak only over a window those bounds set.
A wide bound makes a wide window, so give the range you believe.
`eta`, the Lorentzian fraction of the pseudo-Voigt, defaults to 0.5 and refines between 0 and 1.
`label` is free text, shown in the fit's messages and never part of a parameter's name.

The parameters are named `instrument.extra_components.0.center`, `.area`, `.fwhm` and `.eta`, numbered by the peak's place in the list.
All four start fixed, and a declared peak with zero area changes nothing.

The holder diffracts the same Kα2 the sample does, so rietx places an image of the line at each emission line by default.
Set `all_lines=False` for a line that is not diffraction, such as fluorescence or a detector artefact.

`center` is the 2θ where the line appears in the pattern.
No zero shift, specimen displacement or transparency is applied to it, because the holder sits at its own height and has its own errors.
Do not read a d-spacing from it.

## Free it after the scale and background

`mccusker_structural` frees declared peaks in its `extra_components` stage, after the zero shift, cell and peak widths.
No other preset frees them, so with another plan add a stage for `instrument.extra_components.*` after the scale and background, as [How to add a stage to a refinement plan](plan.md) shows.
A free peak turned on before the general level is set takes intensity from whatever lies nearest.

No plan or suggestion ever adds a peak.
A free area lowers Rwp on any pattern, so a peak in a fit is one somebody declared.
If an agent's fit carries one, ask what evidence it had for the line.

Under Le Bail and Pawley a declared peak stays free.
Its curve is subtracted before the reflection intensities are shared out, so the phases are not handed the holder's counts.

## Compare ignoring, excluding and declaring

No pattern that rietx ships has a holder line, so this guide adds one to the fluorapatite scan.
`examples/guides/_holder_line.py` makes the 110 line of a ferritic steel at 44.65° 2θ, with area 60 counts·degrees, FWHM 0.12° and its Kα2 image, and adds Poisson noise to the counts.
The line overlaps fluorapatite's (400) reflection at 44.57°.

The script fits the pattern three ways and compares each with the fit to the pattern before the line was added:

```{literalinclude} ../../../examples/guides/holder.py
:language: python
:start-after: "# guide: start"
:end-before: "# guide: end"
```

<!-- output of examples/guides/holder.py -->
```text
ignored   largest move 1.88 esd, phases.0.atoms.6.x
excluded  largest move 0.28 esd, phases.0.atoms.6.x
declared  largest move 0.25 esd, phases.0.atoms.6.x
```

`phases.0.atoms.6.x` is the x coordinate of O7.
Ignored, the line pulls it 1.9 esd.
Excluding 44.3-45.1° removes the line and fluorapatite's (400) with it, and every esd grows by at most 4 %.
This pattern has hundreds of other reflections, so losing one changes little.
Declare the line when the reflection under it matters more, such as the strongest line of a minor phase.

The declared line comes back close to the one that was made:

```{literalinclude} ../../../examples/guides/holder.py
:language: python
:start-after: "# guide: line start"
:end-before: "# guide: line end"
```

<!-- output of examples/guides/holder.py -->
```text
center 44.6506(77)
area   68.8(61)
fwhm   0.122(26)
```

Each lies within 1.5 esd of the value it was made with.

## Read what the fit reports

The fit reports [`EXTRA_PEAK_ON_REFLECTION`](../reference/diagnostics-refinement.md#extra_peak_on_reflection) when a declared peak ends within {{ LAYER0_MATCH_TOL_DEG }}° of a reflection the model predicts:

```{literalinclude} ../../../examples/guides/holder.py
:language: python
:start-after: "# guide: diagnostic start"
:end-before: "# guide: diagnostic end"
```

<!-- output of examples/guides/holder.py -->
```text
warning[EXTRA_PEAK_ON_REFLECTION]: Declared peak 'steel holder 110' sits 0.041 deg from a position this model already predicts.
  at: instrument.extra_components.0.center, instrument.extra_components.0.area
  help: If the component stands in for a misfitting reflection, fix the phase's scale, profile and preferred orientation instead.
```

Here the reflection is the Kα2 image of (400) at 44.69°.
The two peaks share the counts between them, and nothing in the data says how.
That is expected for a holder line on a sample peak.
If you declared the peak to cover a reflection the model misfits, fix the model instead.

A declared peak's positions also join the reflection ticks, under the key `"(extra)"` of `result.ticks`.
The report then stops listing the line among the peaks that match no reflection:

```{literalinclude} ../../../examples/guides/holder.py
:language: python
:start-after: "# guide: unmatched start"
:end-before: "# guide: unmatched end"
```

<!-- output of examples/guides/holder.py -->
```text
ignored   unmatched peaks between 44.3 and 45.1°: [44.78]
declared  unmatched peaks between 44.3 and 45.1°: []
```

With the line ignored, the report finds its Kα2 image at 44.78°.
The report matches an observed peak to a tick within the same {{ LAYER0_MATCH_TOL_DEG }}°, so the Kα1 image, beside the Kα2 tick of (400), is not listed.

## Check a peak the data may not have

Declare the same peak on the pattern without the steel line:

```{literalinclude} ../../../examples/guides/holder.py
:language: python
:start-after: "# guide: absent start"
:end-before: "# guide: absent end"
```

<!-- output of examples/guides/holder.py -->
```text
area 8.4(97)
warning[BOUND_HIT]: instrument.extra_components.0.center refined to its bound (ρ=-0.013).
  at: instrument.extra_components.0.center
  help: Widen the bound or fix the parameter.
warning[BOUND_HIT]: instrument.extra_components.0.fwhm refined to its bound (ρ=-0.034).
  at: instrument.extra_components.0.fwhm
  help: Widen the bound or fix the parameter.
warning[BOUND_HIT]: instrument.extra_components.0.eta refined to its bound (ρ=-0.033).
  at: instrument.extra_components.0.eta
  help: Widen the bound or fix the parameter.
```

The area is less than one esd from zero, and the centre, width and Lorentzian fraction end on their bounds.
The steel line on the other pattern refined inside its bounds, with an area eleven esds from zero.
`BOUND_HIT` advises widening the bounds, but here there is no line to find, so remove the peak.
`EXTRA_PEAK_NO_INTENSITY` stays silent, because the area did not reach zero.

A peak declared over empty background refines to zero area.
Declared at 60° on this pattern, it reports [`EXTRA_PEAK_NO_INTENSITY`](../reference/diagnostics-refinement.md#extra_peak_no_intensity).
At zero area nothing fixes the centre, so the centre and its esd are not measurements.

`result.identifiability.extra_peak_absorption` gives, for each structural parameter, the fraction of its effect on the pattern that the declared peaks could reproduce.
No threshold is applied to it.

The full script is `examples/guides/holder.py`.

## See also

- [How to add a hump to the background](hump.md) declares a broad feature, such as a container's amorphous halo, on the same list.
- `save_instrument_profile` leaves declared peaks out, holder lines included, so declare the line again on each sample's instrument. [How to calibrate an instrument on a standard and reuse it](calibrate.md) covers the profile.
- In a series, `carry=["*"]` passes the peak's refined values from each pattern to the next, and its area and centre come back as trajectories. [How to fit a temperature series](series.md) has the details.
