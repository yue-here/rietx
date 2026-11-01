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
