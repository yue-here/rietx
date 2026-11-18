(guide-blank)=
# How to use a measured blank as the background

Read the blank scan with `rietx.read_pattern`, build the background with `BackgroundFixedPlusChebyshev.from_pattern`, and assign it to `Instrument.background`.

A blank is a scan of everything the specimen is not: an empty capillary or can, a matrix-only scan, an empty furnace.
rietx holds it under the pattern, scaled, with a low-order polynomial on top, and never subtracts it.
Subtracting a curve would change the counting statistics while leaving the pattern's σ as it was.

In TOPAS this is `bkg_file("blank.xy")`, and with a refined scale `bkg_file("blank.xy", @, s)`.

## Fit the pattern over its blank

This uses APS 11-BM's scan of NIST SRM 640c silicon in a Kapton capillary and the same capillary scanned empty, from the same beamtime in February 2010.
`rietx.examples.fetch` downloads each file, about 1.5 MB, the first time it is asked for, checks it, and keeps it under `~/.rietx/data`.
Without a network it raises `OSError` naming the path to save the file at by hand.

```{literalinclude} ../../../examples/guides/blank.py
:language: python
:start-after: "# guide: start"
:end-before: "# guide: end"
```

<!-- output of examples/guides/blank.py -->
```text
blank scale 0.84 ± 0.02
```

`from_pattern` takes any pattern `read_pattern` opens.
`n_terms` sets the Chebyshev polynomial refined on top of the blank, `vary_scale` frees the blank's scale, and `source` records where the curve came from.
The lattice parameter is held at the certificate's value, because this is a standard.

The blank's own σ comes with it, as `BackgroundFixedPlusChebyshev.fixed_sigma`.
Each channel's weight then includes the blank's counting noise, so a short blank scan weighs less than a long one.

## Free the scale against a low-order polynomial

A blank is not on the specimen's scale.
The two scans differ in counting time and monitor, and in the sample scan the specimen attenuates the container's scattering.
The polynomial cannot correct that, because it adds to the level and never rescales the shape.

The refined scale is a measurement only against a low-order polynomial.
With more terms the polynomial imitates part of the blank, and the scale walks away:

```{literalinclude} ../../../examples/guides/blank.py
:language: python
:start-after: "# guide: order start"
:end-before: "# guide: order end"
```

<!-- output of examples/guides/blank.py -->
```text
with 6 terms: blank scale 0.69 ± 0.03
```

On this pair a scan of fixed scales, scored under one σ, puts the best scale near 0.85, which the three-term fit agrees with.
A lower Rwp with more terms does not make the scale a better measurement.

`rietx.background.select_chebyshev_order(data, fixed=background)` chooses the polynomial order for the part of the background the blank does not describe.

## Keep the scale at 1.0

Every plan preset except `magnetic_width` frees `instrument.background.*` in its first stage, and that includes the scale.
So a blank built with `vary_scale=False` is refined anyway, by the first stage.
Hold it to keep it fixed:

```{literalinclude} ../../../examples/guides/blank.py
:language: python
:start-after: "# guide: hold start"
:end-before: "# guide: hold end"
```

<!-- output of examples/guides/blank.py -->
```text
held scale 1.0
```

[How to keep a parameter fixed whatever the plan frees](hold.md) explains why a cleared refine flag is not enough.

## Hold a curve another program computed

The same slot holds a curve computed by another program for one phase.
An example is a stacking-fault diffuse term from DIFFaX, the faulted pattern minus the ideal one.
Such a curve scales with its phase, so its scale is tied to the phase scale instead of refined.
A curve whose amount is independent of the phase, such as an amorphous fraction, keeps a free scale.

Store the curve as c*·D.
D is the other program's curve in its own units.
c* converts those units to counts at phase scale 1.
To find c*, compute the ideal pattern in the other program too.
Then take the least-squares ratio of `Refinement.predict` at phase scale 1 to that pattern, over the whole fitted range.
Check that the ratio is flat across 2θ: the two programs may treat Lorentz-polarisation or absorption differently.
`predict` returns the whole model, so make that comparison before the curve is stored, with every background coefficient at zero.
Then tie the curve's scale to the phase scale:

```python
import numpy as np
import rietx as rx
from rietx.examples import examples_dir

two_theta = np.arange(10.0, 120.0, 0.01)
diffuse = 1.0 / (1.0 + ((two_theta - 31.9) / 0.15) ** 2)  # stands in for D
c_star = 5e5

instrument = rx.Instrument.bragg_brentano(radiation="CuKa")
instrument.background = rx.BackgroundFixedPlusChebyshev(
    fixed_two_theta=two_theta.tolist(),
    fixed_intensity=(c_star * diffuse).tolist(),
    fixed_source="DIFFaX, faulted minus ideal, c* = 5e5")
structure = rx.Structure.from_cif(examples_dir() / "fluorapatite.cif")
ref = rx.Refinement(structure, instrument)
ref.tie("instrument.background.scale", "phases.0.scale")

rows = {row.path: row for row in ref.parameters()}
assert rows["instrument.background.scale"].tie.terms == [("phases.0.scale", 1.0)]
```

The curve then adds S·c*·D to the model, with S the phase scale.
A plan that frees `instrument.background.*` frees the Chebyshev terms and leaves the tied scale alone.
One fit reaches the least-squares minimum in S, with the curve's dependence on S included.
A loop of refits that rebuilds the curve from each new scale stops elsewhere, because it holds the curve fixed while it refits S.
In two synthetic cases the loop's scale differed from the fit's by 0.09 % and 0.5 %.

In a series, a tie is not carried from one pattern to the next.
Declare it in the `constrain=` hook, which runs before each pattern's fit.

The curve is fixed on the 2θ axis.
Every peak-position correction moves only the Bragg peaks: the zero shift, the specimen displacement and transparency on a flat plate, and the offsets on a capillary.
With a zero shift of 0.05° and curve features 0.15° wide, the phase scale came out 0.16 % low and GoF rose from 1.02 to 1.04.
With features 2.5° wide the bias was 0.009 %.
If the fit finds a peak shift Δ(2θ), the sum of those corrections at each angle, store the curve at `two_theta + Δ(two_theta)` and fit again.
For a zero shift alone, Δ is the constant Z.

## Know the limits

- The blank must cover every fitted channel.
  A fit whose range runs past the blank is refused, naming both ranges.
  Narrow the fit range, or measure the blank over the whole scan.
- Interpolating a noisy blank onto the pattern's 2θ steps makes neighbouring channels' errors correlated, so the propagated σ is a lower limit.
  Smooth the blank first if that matters, and record that you did.
- One blank reused across a temperature or atmosphere series carries the same error into every pattern.
  A refined scale that trends along the series is partly that error.
  Refine the scale in each pattern.
- A single scale is the leading-order correction.
  In the sample scan the container's scattering also passes through the specimen, so the true factor depends on angle.

The full script is `examples/guides/blank.py`.

## See also

- [How to check a pattern before fitting](check.md) builds a background from the pattern alone, when no blank exists.
