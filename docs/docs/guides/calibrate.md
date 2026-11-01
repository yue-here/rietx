(guide-calibrate)=
# How to calibrate an instrument on a standard and reuse it

Refine a line-profile standard under `lab_calibrate` with its certified cell held, save the instrument with `rietx.save_instrument_profile`, and load it with `rietx.load_instrument_profile` for each sample measured on the same setup.

A sample's peak width is the instrument's width combined with the sample's own.
Over angle, each sample term follows the same shape as an instrument term, so a fit to the sample alone cannot tell them apart.
A standard with no size or strain broadening of its own, such as NIST SRM 660c LaB₆, measures the instrument's half.
[The instrument ⊕ sample width split](../theory/profiles.md#the-instrument--sample-width-split) gives the equations.
Tutorial 04 walks through the same steps one cell at a time.

## Calibrate on the standard

No pattern that rietx ships pairs a standard with a sample from the same diffractometer, so this guide uses synthetic patterns.
`examples/guides/_calibration_pair.py` computes a LaB₆ standard and a CeO₂ sample on two Cu Kα setups and adds Poisson noise.
The sample has a crystallite size of 300 Å and a microstrain of 1.0 × 10⁻³, both Lorentzian.

```{literalinclude} ../../../examples/guides/calibrate.py
:language: python
:start-after: "# guide: start"
:end-before: "# guide: end"
```

<!-- output of examples/guides/calibrate.py -->
```text
u 0.00399(17)
v -0.00293(25)
w 0.002957(83)
x 0.01483(37)
y 0.02018(88)
```

Each width term lies within one esd of the instrument that made the data.

Hold the cell at the certificate's value.
With the cell fixed, the peak positions measure the zero shift and the specimen displacement, which a free cell would absorb.
`lab_calibrate` frees one group a stage: the scale and background, the zero shift and displacement, the width term W, the other four width terms, the emission-line weights and the two axial-divergence ratios, and the Biso.
[Plan presets](../reference/plans.md#lab_calibrate) draws its stages.

Refine one of the two axial-divergence ratios, S/L, and hold the other, H/L.
In rietx's profile the two are interchangeable: swapping their values gives the same pattern to the last bit.
Refined together on this standard, they came back as S/L 0.02476(78) and H/L 0.01542(87), against 0.025 and 0.015.
The exchanged pair gives the same pattern, so nothing in the data chose this order, and no finding names the pair.
H/L is the receiving slit's height over the goniometer radius, 3 mm over 200 mm here, so take it from the instrument's dimensions.

## Check the calibration before saving it

Read the calibration's diagnostics:

```{literalinclude} ../../../examples/guides/calibrate.py
:language: python
:start-after: "# guide: check start"
:end-before: "# guide: check end"
```

<!-- output of examples/guides/calibrate.py -->
```text
warning[HIGH_CORRELATION]: Correlated pair: instrument.zero_shift ~ instrument.geometry.sample_displacement (ρ=+0.993). Flagged in stages: zero_disp, profile_w, profile, lines_axial, biso, closing.
  at: instrument.zero_shift, instrument.geometry.sample_displacement
  help: Fix one of the two at a known value, or free them in separate stages.
info[HOLD_BLOCKED_PLAN]: 1 held parameter was matched by the turn_on glob of stages 'closing', 'lines_axial' and stayed fixed: instrument.geometry.axial_hl.
  at: instrument.geometry.axial_hl
  help: Call unhold() on them first if you meant the plan to refine them.
```

`HOLD_BLOCKED_PLAN` confirms that H/L stayed at the value you set.

The zero shift and the specimen displacement still correlate with the cell held.
The zero shift refined to 0.01976(61)° against 0.02° in the instrument that made the data, and the displacement to −0.0006(14) mm against zero.
The profile keeps the zero shift and drops the displacement, and the sample fit refines a displacement of its own.

Do not save a calibration that reports [`RESOLUTION_NOT_POSITIVE`](../reference/diagnostics-refinement.md#resolution_not_positive).
It says U, V and W give a negative Gaussian width somewhere in the fitted range.
The model then clamps the width to a floor finer than any diffractometer, so a size or strain read against it is wrong.

## Save it and reuse it on a sample

```{literalinclude} ../../../examples/guides/calibrate.py
:language: python
:start-after: "# guide: reuse start"
:end-before: "# guide: reuse end"
```

<!-- output of examples/guides/calibrate.py -->
```text
first profile, first sample  size 300.7(23) Å  strain 0.001016(44)  Rwp 0.0460
```

The size and strain each lie within one esd of the values the sample was made with.

`save_instrument_profile` writes the instrument as JSON and leaves out what belongs to one specimen: the background, the specimen displacement and transparency, surface roughness, absorption, and any declared humps or peaks.
Give the loaded instrument a background of its own, and declare a holder line again if the sample needs one, as [How to fit a peak from the sample holder](holder.md) shows.

`load_instrument_profile` returns every parameter fixed.
`lab_sample_refine` frees the sample's scale, background, displacement, cell, the four sample-broadening terms and Biso, and leaves the zero shift and instrument widths alone.
Where the model declares them, it also frees anisotropic strain and surface roughness ([Plan presets](../reference/plans.md) draws each stage).
Do not free the instrument widths on the sample, because the sample's own terms would then trade against them again.

`result.microstructure` reads the broadening terms as a crystallite size and a microstrain.
The size is a coherent domain size, read with the Scherrer constant `scherrer_k` the result carries.
[Reading a width as a size](../theory/microstructure.md#reading-a-width-as-a-size) gives the conversion.

## Use a profile only on the setup that measured it

The widths belong to the slits, optics and wavelength the standard was measured with.
The second setup in `_calibration_pair.py` has twice the first's W and X.
Calibrate on its standard, then use each profile on the other setup's sample:

```{literalinclude} ../../../examples/guides/calibrate.py
:language: python
:start-after: "# guide: mismatch start"
:end-before: "# guide: mismatch end"
```

<!-- output of examples/guides/calibrate.py -->
```text
second profile, first sample size 325.3(27) Å  strain 0.001053(44)  Rwp 0.0461
first profile, second sample size 281.8(21) Å  strain 0.000928(46)  Rwp 0.0465
```

Each crossed profile moves the size by eight to ten esd, and Rwp stays within 0.001 of the matched fit.
With the wider profile, the fit reports the same two `FLOOR_HIT` findings as the matched one, on the Gaussian size and strain the sample does not have.
With the narrower profile, the instrument width it misses appears as a Gaussian size of 1440(200) Å and a Gaussian strain, which the sample does not have.
Nothing in either fit says the profile is wrong.

Measure the standard again whenever the slits, optics, wavelength or detector change, and keep each profile with the setup it describes.

The full script is `examples/guides/calibrate.py`.

## See also

- Tutorial 04, `examples/tutorials/04_peak_shape_and_microstructure.py`, compares the calibrated sample fit with one on a default instrument.
- A profile saved by an earlier release can carry a parameter whose range that release dropped. `load_instrument_profile(path, diagnostics=[])` restores it and reports the repair on that list.
- In the GUI, the Model panel's `Save profile…` and `Load profile…` write and read the same file.
