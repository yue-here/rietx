(guide-hump)=
# How to add a hump to the background

Append a `HumpComponent` to `Instrument.extra_components`, and free `instrument.extra_components.*` in a stage after the peak widths have refined.

A hump is one broad Gaussian added on top of whichever background model you use.
Use it for scattering with no Bragg peaks behind it: an amorphous phase, a glass or polymer capillary, a cryostat window or a sample holder.
Other programs call it a background peak.

## Declare the hump

Give it a starting position, height and width.
Seed the position where the feature is, from a blank scan or from the pattern itself:

```python
import rietx as rx
from rietx.schemas.instrument import HUMP_FWHM_MIN

capillary = rx.Instrument.debye_scherrer(wavelength=0.412359)
capillary.extra_components = [rx.HumpComponent(
    label="Kapton halo",
    position=rx.Parameter(value=5.0, unit="deg"),
    height=rx.Parameter(value=50.0, min=0.0, unit="counts"),
    fwhm=rx.Parameter(value=2.0, min=HUMP_FWHM_MIN, unit="deg"))]
assert capillary.extra_components[0].height.vary is False
```

`position` and `fwhm` are in degrees 2θ, and `height` is the peak value in counts.
Keep the `min` bounds: a height of zero switches the hump off, and the width is floored at `HUMP_FWHM_MIN` because the Gaussian divides by it.
`label` is free text and never part of a parameter's name.

The parameters are named `instrument.extra_components.0.position`, `.height` and `.fwhm`, numbered by the hump's place in the list.
All three start fixed, and a declared hump at zero height changes nothing.

## Free it after the peak widths

`mccusker_structural` frees declared humps in its `extra_components` stage, after the zero shift, cell and peak widths.
No other preset frees them, so with another plan add a stage for `instrument.extra_components.*`, as [How to add a stage to a refinement plan](plan.md) shows.
Freeing the hump earlier lets its free position chase misfit from a wrong zero shift or cell.
For the same reason `instrument.background.*`, which most presets free in their first stage, does not reach the humps.

No plan ever adds a hump.
A plan frees only the humps you declared.

## Compare it with more polynomial terms

A free position, height and width will lower Rwp on any pattern, so compare the hump with the same number of extra polynomial terms.
This runs APS 11-BM's scan of NIST SRM 640c silicon in a Kapton capillary, which shows the capillary's halo near 5° 2θ.
`rietx.examples.fetch` downloads the file, about 1.5 MB, the first time it is asked for.

```{literalinclude} ../../../examples/guides/hump.py
:language: python
:start-after: "# guide: start"
:end-before: "# guide: end"
```

<!-- output of examples/guides/hump.py -->
```text
3 terms         Biso 0.443 ± 0.100 Å²
3 terms + hump  Biso 0.446 ± 0.018 Å²
6 terms         Biso 0.448 ± 0.039 Å²
```

Silicon's Biso is the only structural parameter in this fit.
Its value barely moves, and its esd falls by a factor of 5.6 with the hump, against 2.5 with three more polynomial terms.
A background that cannot describe the halo trades against the Bragg intensities, and the hump ends that trade.

## Check what the hump is

Rwp cannot tell a container halo from a missed reflection, so look for evidence outside the fit.
For this pattern, 11-BM's scan of the same capillary empty peaks near 5.0° 2θ, d ≈ 4.7 Å, the amorphous halo of the polyimide the capillary is made of.
A scan of the beam path with no capillary shows no feature at all.
Without such a check, a hump is three parameters that lower Rwp.

A hump narrower than {{ HUMP_MIN_WIDTH_MULT }} times the instrumental peak width at its position is reported as [`HUMP_TOO_NARROW`](../reference/diagnostics-refinement.md#hump_too_narrow).
That width belongs to a reflection, so model it as a second phase instead.

## Read the fitted position with care

The refined position and width describe the background model, not the halo on its own:

```{literalinclude} ../../../examples/guides/hump.py
:language: python
:start-after: "# guide: hump start"
:end-before: "# guide: hump end"
```

<!-- output of examples/guides/hump.py -->
```text
3 terms: hump at 4.16 ± 0.10°, FWHM 5.59 ± 0.25°
6 terms: hump at 5.24 ± 0.04°, FWHM 1.91 ± 0.11°
```

Against three polynomial terms, the hump also absorbs the rise of the direct beam below 3°, which pulls its centre low and widens it.
Against six, the polynomial takes the rise, and the hump moves onto the halo and narrows to a third of the width.
Its esds cover neither shift.
Quote the blank's envelope for where the halo is, and keep the background low-order if you mean to quote the hump's parameters.

The full script is `examples/guides/hump.py`.

## See also

- [How to use a measured blank as the background](blank.md) holds the empty capillary's whole scan under the pattern, which describes the halo without three free parameters.
- `save_instrument_profile` leaves humps out, because a hump belongs to the specimen and its holder, not to the diffractometer.
