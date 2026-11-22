(guide-holder-cell)=
# How to fit a sample holder's lines from its cell

Declare one `PeakComponent` for each of the holder's reflections, and tie each line's centre to a formula of the holder's lattice parameter and its height.

Use this when the holder is a known crystal and its line intensities cannot be trusted, for example an aluminium holder with texture.
The positions then follow the holder's cell, as for a Pawley phase, while each line's area and width refine on their own.
Stinton and Evans fit an aluminium holder this way beside two Rietveld phases {cite}`stinton2007`.
TOPAS writes such a holder as an `hkl_Is` phase.

## Write each centre from the cell and the height

The example pattern is synthetic, made by `examples/guides/holder_cell.py` on the 2θ grid of the fluorapatite scan that ships with rietx.
The specimen is fluorapatite with its surface 0.040 mm above the goniometer axis.
The aluminium holder sits 0.120 mm lower, and was drawn with a March-Dollase texture along [111], so its intensities are not those of its structure.

```{literalinclude} ../../../examples/guides/holder_cell.py
:language: python
:start-after: "# guide: start"
:end-before: "# guide: end"
```

<!-- output of examples/guides/holder_cell.py -->
```text
a_holder 4.04948(17)  made with 4.0495
offset   -0.1231(21)  made with -0.12
height   0.018(22)    made with 0.04
```

Each centre is Bragg's law for Kα1 at the holder's lattice parameter, plus the zero shift, plus the specimen-displacement shift −(2s/R)·cosθ.
Here s is the holder's height, `height + offset`, and R is the goniometer radius.
This is the shift rietx applies to a phase's reflections, so the formula gives the holder the position an aluminium phase at that height would have.
[How to tie parameters together](tie.md#tie-to-a-formula) describes the formula language.

A formula reads only variables declared with `add_variable`.
So the zero shift and the specimen's displacement are tied to the variables `zero` and `height`, and the formula names those.

`mccusker_structural` frees neither variables nor the specimen displacement.
The plan above replaces its `zero` stage with one freeing `vars.zero` and `vars.height`.
It also renames the `extra_components` stage `holder`, adds the holder's two variables to it, and moves it to second place, after the scale and background.
The holder's lines then carry their counts before the zero shift and the cell refine.
[How to add a stage to a refinement plan](plan.md) shows these list edits.

The holder's lattice parameter and the offset come back within 1.5 esd of the values the pattern was made with.
The offset is measured to 0.002 mm, and the height only to 0.022 mm.
Over 15-90° 2θ a zero shift and a change of height move the peaks in similar shapes, and the fit reports this pair as `FLAT_DIRECTION`.
The offset is a difference between two heights, and the zero shift moves both alike.

## Compare with the holder fitted as a phase

The same pattern, with the holder added as a Rietveld phase of aluminium and the specimen displacement freed in place of the variables:

```{literalinclude} ../../../examples/guides/holder_cell.py
:language: python
:start-after: "# guide: phase start"
:end-before: "# guide: phase end"
```

<!-- output of examples/guides/holder_cell.py -->
```text
a_holder 4.04336(20)  made with 4.0495
```

The lattice parameter misses by about 30 esd.
A phase shares the specimen's displacement, so its cell takes up the holder's 0.120 mm offset.
The texture is not modelled either, and the goodness of fit rises from 1.02 to 1.18.

## Hold a known holder cell

If the holder's lattice parameter is known, set it and hold it:

```{literalinclude} ../../../examples/guides/holder_cell.py
:language: python
:start-after: "# guide: known start"
:end-before: "# guide: known end"
```

<!-- output of examples/guides/holder_cell.py -->
```text
offset   -0.1232(17)
height   0.020(12)
```

The height's esd falls from 0.022 mm to 0.012 mm.
The holder's lines then fix the holder's height, and the offset carries that to the specimen.
This is where Stinton and Evans's gain in precision comes from.
[How to keep a parameter fixed whatever the plan frees](hold.md) explains `hold`.

## Share the holder across a series

A series of patterns of one holder can share the holder's lattice parameter and its offset, while each pattern keeps its own specimen height.
This is the setting of Stinton and Evans's first example, where the holder fixes each data set's height {cite}`stinton2007`.
The script makes five patterns of the same fluorapatite over the same aluminium holder, with the specimen surface at five heights between −0.060 mm and 0.090 mm.
The holder sits 0.120 mm below the specimen in each.

A joint fit has no `tie`, so each formula becomes a `ParametricEquation` with `basis="expression"`.
The four variables are passed to `MultiHistogramRefinement` as `variables`:

```{literalinclude} ../../../examples/guides/holder_cell.py
:language: python
:start-after: "# guide: series start"
:end-before: "# guide: series end"
```

<!-- output of examples/guides/holder_cell.py -->
```text
vars.a_holder        4.049470(77) made with 4.0495
vars.offset          -0.11943(96) made with -0.12
vars.zero            0.0120(54)   made with 0.012
hist.0.vars.height   0.0401(97)   made with 0.04
hist.1.vars.height   -0.0299(97)  made with -0.03
hist.2.vars.height   0.0900(97)   made with 0.09
hist.3.vars.height   0.0100(97)   made with 0.01
hist.4.vars.height   -0.0600(97)  made with -0.06
```

Each variable is one number across the five patterns, unless `SharingMap.per_histogram` names it.
Here only `height` is named, so it comes back as one row per pattern, `hist.<k>.vars.height`.
The zero shift is one number too, because the five patterns come from one instrument.
Every parameter under `instrument.` is otherwise one per pattern, so each line's area and width refine separately in each pattern.
`shared=["instrument.profile.*"]` gives the five patterns one instrument profile.

The variables are declared with `vary=False`, so only the stages that name them free them.
A stage reaching an equation's target would otherwise free every variable its formula names.
The plan is the single-pattern plan from the first section, reused unchanged.

Every recovered value lies within 1.5 esd of the value the patterns were made with.
The offset's esd is 0.00096 mm, against 0.0021 mm from one pattern, close to the factor 1/√5 that five patterns give.
The zero shift still trades against each height, and the fit reports each pair as `FLAT_DIRECTION`.
The five heights and the zero shift move together.
Here each height misses the value it was made with by nearly the same amount, under a tenth of its esd from the others.
So the differences between the heights are measured better than the esd of each height says.

[Parametric refinement](../reference/parametric.md#formula-equations) describes formula equations in a joint fit.

## Limitations

- Each line's width and Lorentzian fraction refine on their own, not from the instrument's Caglioti terms.
- A declared line's Kα2 image sits at the Bragg image of its Kα1 centre, as [How to fit a peak from the sample holder](holder.md) describes, while a phase applies the zero and displacement shifts at each wavelength. On this pattern the two placements differ by 0.00025° or less, about a tenth of the esd of a line centre.
- rietx gives the holder no phase fraction, since it is no phase.

The full script is `examples/guides/holder_cell.py`.

## See also

- [How to fit a peak from the sample holder](holder.md) declares a single line with a free centre.
- [The Einstein-function guide](formula.md) writes a formula for each lattice parameter across a temperature series.
