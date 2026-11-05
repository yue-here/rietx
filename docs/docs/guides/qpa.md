(guide-qpa)=
# How to find the weight fraction of each phase in a mixture

Refine every phase in Rietveld mode, read `result.qpa.phases`, and check the minor phase's esd and correlations before you quote its fraction.

A Rietveld fit with more than one phase converts the phase scales into weight fractions by the Hill-Howard relation, W<sub>p</sub> ∝ S<sub>p</sub>·(ZMV)<sub>p</sub>, renormalised to sum to 1.
Nothing has to be switched on.

## Read the fractions

The NAC pattern that ships with rietx, measured at APS 11-BM, carries a CaF₂ impurity.
This refines both phases with `mccusker_structural`:

```{literalinclude} ../../../examples/guides/qpa.py
:language: python
:start-after: "# guide: start"
:end-before: "# guide: end"
```

<!-- output of examples/guides/qpa.py -->
```text
NAC    98.66 ± 0.11 wt%
CaF2    1.34 ± 0.11 wt%
```

Each row is a `PhaseQuantity`, with the fraction, its esd, the refined scale and the Z·M and V it was computed from.
The esd is propagated through the covariance of all the scales.
With two phases the fractions sum to 1, so their esds are equal.

The fractions are of the crystalline phases in the model, and `result.qpa.crystalline_only` says so.
An amorphous component or a crystalline phase you did not model is shared out among the phases you did, so the fractions still sum to 1.
Report them as "wt % of the crystalline content".
A phase with no reflection in the fitted range has no fraction (`None`), and the others are relative to the phases seen in range ([QPA reference](../reference/qpa.md#a-phase-with-no-reflection-in-the-fitted-range)).

## Check the minor phase

A minor phase has few strong peaks, so read its diagnostics before you quote its fraction:

```{literalinclude} ../../../examples/guides/qpa.py
:language: python
:start-after: "# guide: why start"
:end-before: "# guide: why end"
```

<!-- output of examples/guides/qpa.py -->
```text
FLOOR_HIT | phases.1.atoms.0.biso refined to its floor (ρ=+0.198).
```

The Ca Biso of CaF₂ went to 0, which no real crystal has.
The data cannot fix the displacement parameters of a phase this weak, so hold them:

```{literalinclude} ../../../examples/guides/qpa.py
:language: python
:start-after: "# guide: hold start"
:end-before: "# guide: hold end"
```

<!-- output of examples/guides/qpa.py -->
```text
NAC    98.59 ± 0.07 wt%
CaF2    1.41 ± 0.07 wt%
```

The esd falls from 0.11 to 0.07 wt %, and `mccusker_default`, which frees no structural parameter, gives 1.38 wt % for CaF₂.
Rwp rose from 0.088 to 0.090 when the two Biso values were held.
A Biso on its floor lowered Rwp, so Rwp cannot choose between the two fits.
The fit reports the holds as `HOLD_BLOCKED_PLAN`, because the plan tried to free paths you held.
[How to keep a parameter fixed whatever the plan frees](hold.md) explains holds.

## Declare extinction only where the data can measure it

Extinction is opt-in, so the plan freed none here.
A phase declares it with `phase.extinction = 0.0`, and then the plan's extinction stage frees it.
Declared on the minor phase, it trades against the scale:

```{literalinclude} ../../../examples/guides/qpa.py
:language: python
:start-after: "# guide: extinction start"
:end-before: "# guide: extinction end"
```

<!-- output of examples/guides/qpa.py -->
```text
NAC    96.31 ± 3.63 wt%
CaF2    3.69 ± 3.63 wt%
HIGH_CORRELATION | Correlated pair: phases.1.scale ~ phases.1.extinction (ρ=+0.998). Flagged in stages: extinction, roughness, closing.
```

With a few weak peaks, the extinction and the scale can scale the same intensities.
The fraction moves from 1.34 to 3.69 wt %, and its esd from 0.11 to 3.63 wt %.
Rwp falls from 0.088 to 0.083, so Rwp would choose the fit with the meaningless fraction.
When a fit would gain from extinction, `EXTINCTION_UNDECLARED` names the phase.
Here it does not fire.

## Check that the fraction has one answer

A weak phase's scale can also trade against its peak width: broadened far enough, its peaks become a hump the background can share.
`Refinement.profile_fraction` pins a width term at a series of values, refits everything else at each, and reports every fraction the data cannot tell from the best one:

```{literalinclude} ../../../examples/guides/qpa.py
:language: python
:start-after: "# guide: profile start"
:end-before: "# guide: profile end"
```

<!-- output of examples/guides/qpa.py -->
```text
admissible 1.41 to 1.41 wt%, 12 refits
```

Here only the fit's own fraction is admissible, so the fraction is determined.
A point is admissible when its χ² is within {{ FRACTION_PROFILE_DCHI2 }} × χ²<sub>red</sub> × f² of the lowest χ² found, f being the Bérar-Lelann factor.
Every profile of a fit with an esd carries a `QPA_FRACTION_RANGE` info record, whose value is the farthest admissible fraction's distance from the fit's, in the esd's 95 % half-widths.
Below 1 the profile confirms the esd.
Well above 1 the esd describes only the basin the fit stopped in, and you should quote the range rather than the value.
Without `axes=`, it uses the phase's width terms that were free in the last fit, and refuses if none was.

## Correct for microabsorption

A strongly absorbing coarse phase hides the inside of its own particles, so its fraction comes out low.
The Brindley correction needs a particle radius for every phase, which the pattern cannot give: measure it, for example from a micrograph.
Set `Phase.particle_radius_um` on every phase before the fit:

```{literalinclude} ../../../examples/guides/qpa.py
:language: python
:start-after: "# guide: brindley start"
:end-before: "# guide: brindley end"
```

<!-- output of examples/guides/qpa.py -->
```text
NAC   µR 0.0021  98.59 -> 98.59 wt%
CaF2  µR 0.0014  1.41 -> 1.41 wt%
```

The radii here are assumed, to show the call.
At 0.414 Å both phases absorb so little that the correction changes nothing.
With Cu Kα and a heavy phase it can move a fraction by several wt %.

The corrected fraction is reported beside the uncorrected one, and the esd belongs to the uncorrected one: the radii's uncertainty is not statistical.
Above µR = {{ BRINDLEY_MU_R_FENCE }} the correction is outside the regime Brindley derived it for, and `BRINDLEY_OUTSIDE_REGIME` names the phases.

## Write the table

`Refinement.write_qpa_table` writes the fractions to a CSV with the crystalline-only caveat in it.
A joint fit reports the fractions per histogram on `HistogramResult.qpa`, and a series per pattern on `SeriesEntry.qpa`.

## See also

- [How to quote a parameter that ended on its bound](interval.md) gives an interval for a Biso on its floor.
- [Intensity corrections](../theory/corrections.md) gives the Hill-Howard and Brindley equations.
