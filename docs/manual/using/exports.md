# Exports and derived tables

A finished fit holds more than its refined parameters. The calculated pattern,
the reflection list behind it and the tick positions drawn under it are all
functions of the converged state, and the package will compute any of them on
request. This chapter is those derived quantities and the files they become.
Where each file lands, and the rest of the on-disk map, is [](files.md).

## The calculated pattern

`RefinementResult` carries the curves of the fit itself: `RefinementResult.y_obs`,
`RefinementResult.y_calc` and `RefinementResult.y_background` on
`RefinementResult.two_theta`. Two more belong with them.

`RefinementResult.sigma` is the per-point σ the fit divided by, copied verbatim
from the pattern at stage compile. `RefinementResult.sig` is the method to call
rather than the field to read: it is the one authority for σ, and every weighted
residual in the package goes through it, the static plot, the interactive page,
the report's Layer 0 and the GUI's own window alike. Two conditioning steps
are the reason it is a method. A result recorded before v0.2 carries no σ at all
and gets the Poisson √max(y,1) fallback the fit itself would have used, and
non-positive entries are floored, so a zero esd becomes a small σ instead of an
infinity that would lose the whole trace.

`RefinementResult.sig` says nothing about where σ came from. By the time a
result exists, a file's esd column and a Poisson estimate are the same array of
floats. `DataRef.has_sigma` is the fact that survives, and it is what a plot
axis and the text document are labelled from ([](files.md)).

`RefinementResult.ticks` maps a phase name to its reflection positions in
degrees 2θ. It covers every emission line, not only the primary one. The
calculated pattern really does have a peak at each Kα₂ position, and a tick list
that omitted them would make the report flag every Kα₂ peak as an unindexed
impurity, which it once did.

`RefinementResult.tick_hkl` says which reflection each of those ticks is, as
`[h, k, l]`, paired with `ticks` by index. One reflection appears once per
emission line, so a peak and its Kα₂ image carry the same Miller index. The
three browser pages hover it over a tick. A phase is absent from the mapping
rather than empty when there is nothing to say, which is the case for the
reserved key declared peaks go under: a peak given by centre has no Miller
index, and an empty list there would claim it had none of its own. A satellite
of a phase with a propagation vector is `[h, k, l, m]`, its parent H and its
order m, because H alone does not identify it: the satellite of (0 0 0) is not
the origin, and a nuclear row and a satellite can share a parent. The browser
pages spell three-index rows only, so they show a satellite tick unlabelled
rather than as its parent.

Two reflections can land at the same 2θ to every decimal, so a position is not
a key into this mapping. Pair them by index or not at all.

`Refinement.predict` evaluates y_calc at the parameters as they stand. Given a
grid (a `PatternData`, or an array of 2θ values) it compiles a fresh model on it,
so it will extrapolate beyond the fitted range or resample inside it. With
no argument it uses the grid the last fit ran on.

<!-- api-doc: no-exec — needs a structure and an instrument -->
```python
import numpy as np

fine = np.arange(10.0, 90.0, 0.001)
y = refinement.predict(fine)

y_here = refinement.predict(data)   # the pattern's own grid
```

It does not need a fit. Evaluating a model is not refining it. The values come
off the structure and instrument, whether a fit put them there, `set_value` did,
or you typed them. So drawing the curve a set of parameters implies costs no
solver time, and a zero-stage plan, which refines nothing and is refused, is not
the way to ask for it. Le Bail and Pawley are the exception, and say so. Their
per-hkl intensities are extracted by a fit, so there is nothing to carry over
before one has run.

The two forms are not bit-identical on the same grid, and the difference is the
frozen-per-stage invariant rather than a defect. `predict()` reuses the model
compiled for the last stage, whose per-reflection evaluation windows were sized
at the values that stage started from, while a grid argument sizes them at the
values it ended on. On the synthetic five-stage fit that is 36 of 4200 channels,
by at most 8e-6 of the peak height, all of them in peak tails at a window edge.
`RefinementResult.y_calc` is the first of the two: the curve the fit minimised.

(plotting-the-fit)=
## Plotting the fit

`RefinementResult.plot` draws the standard panel [](first-refinement.md) opens with:
observed points, the calculated line, the `obs − calc` difference on the same
axis at the same scale, and one row of reflection ticks per phase. It draws
with matplotlib and returns the figure, so passing `path=` is optional.

`two_theta_range=` is a window and not a crop. The intensity scale and the rows
below it are built from what the window contains, so a zoom into a weak region
is a figure of its own data.

`weighted=True` draws Δ/σ instead, in its own panel with a ±3σ band. A raw
difference shares the intensity axis, so the eye reads a small deviation on a
strong peak as a large error, while Δ/σ has expectation 1 under a correct model
and the band is an absolute scale rather than a relative one. It is not the
default because it costs the one thing the classic layout gives away free, which
is the residual and the peak that caused it in a single glance.

`wavelength=` puts λ on the 2θ axis, which is meaningless without it. The result
does not carry the emission line, so it has to be passed. It is also what
`x_axis="q"` and `x_axis="d"` are derived through, and those two carry no λ of
their own, which is the point of them.

`y_scale=` takes `"sqrt"` (equal display distance for equal counting σ), `"log"`
or `"asinh"`. Any of them moves the difference into its own panel, since an
offset raw difference is negative by construction and a nonlinear intensity axis
cannot draw it.

`style="dark"` is for a figure going onto a dark page, and `figsize=`/
`font_size=` are the exposure surface: build the figure at the width it will be
read at, and do not scale it in the document afterwards.

## A figure of the structure

`rietx.viz.render_structure` draws one phase as the GUI's structure viewer
draws it, to an RGBA array or a PNG.
It needs no browser, no display and nothing beyond the base install.
The geometry, the scene rules and the lighting are the viewer's own, so a
picture drawn from a script matches one exported from the GUI.

```{literalinclude} ../../../examples/structure_figure.py
:language: python
:start-at: structure = rx.Structure
```

```text
wrote nac_structure.png: 1000 x 963 px, 173 atoms, 46.7 px/Å
wrote nac_ellipsoids.png: rotation drawn [[-0.707, 0.707, 0.0], [-0.408, -0.408, 0.816], [0.577, 0.577, 0.577]]
a round trip through the rotation draws the same picture: True
  letter a at (1745, 1619) px
  letter b at (389, 263) px
  letter c at (389, 1619) px
wrote nac_print.png
```

The call returns a `StructureFigure`.
`image` is the picture, height × width × 4 bytes with straight alpha.
`np.asarray(fig)` and `plt.imshow(fig)` both take the figure itself.
`atoms` and `letters` give each atom's and each axis letter's position in
pixels from the top-left corner, so a caller can annotate in matplotlib
without projecting anything.
`rotation` is the view drawn, and passing it back as `view=` draws the same
picture.
`StructureFigure.to_px` takes Cartesian points in Å, one or an `(N, 3)` array,
and returns where they land in the image, x right and y down.
It is the map that placed `atoms`.
`rotation`, `pixels_per_angstrom` and `StructureFigure.origin` make it.
`origin` is the view-plane position of pixel (0, 0), in Å.

`view=` takes `"opening"` (the GUI's first picture), `"a"`, `"b"` or `"c"`
(its buttons), a lattice direction `[u, v, w]`, a plane normal
`{"hkl": (h, k, l)}`, a rotation, or `"auto"`, which {ref}`picks the view that
hides least <figure-report>`.
The named direction points at you.
`up=` takes the same forms.
By default c is up, or b when you look down c, as in VESTA's standard
orientation.
`turn=` is ASE's rotation string (`"30y,-15x"`), turning about the screen's
axes in the order written.
Every view is fitted to the frame, and the projection is parallel.

`size=` is the long side in pixels, or `(width, height)`.
Line widths and letters grow with it, as they do in the GUI's export, so a
larger picture is the same figure at a higher resolution.
`dpi=` goes only into the PNG's `pHYs` chunk.
A 17 cm figure at 300 dpi is `size=2008, dpi=300`.
`supersample=` sets the antialiasing, 2 × 2 samples a pixel by default and up
to 4 × 4.

`mode=` is `"ball"` or `"ellipsoid"`, with `probability=` (50 % by default)
and `exaggeration=` meaning what they mean in the GUI.
`hidden=` takes elements or species, and a name the phase does not have
raises.
One site is left out by a mask, as {ref}`below <figure-cut-and-keep>`.
`boundary=False` drops the images outside the cell.
`polyhedra=` follows the mode (on for balls, off for ellipsoids) unless you
pass `True`, `False` or a formula switch such as `{"AlF₆": False}`.
`background=None` is transparent.
`cell=False` leaves out the cell's frame and the a, b and c on its edges, so
the view is fitted to the atoms alone.
A 22 Å sphere cut from HKUST-1's 26 Å cell draws at 8.5 px/Å with the frame
and at 16.4 px/Å without it, at `size=400`.
`stick=` multiplies the radius of the bond sticks, in either mode.
In ellipsoid mode a stick's radius is half the smallest drawn semi-axis, at
most 0.08 Å.
For paracetamol at 100 K (COD 2104364) that is 0.072 Å, and `stick=0.5`
draws 0.036 Å.
Above 1, a stick may show through the side of a small ellipsoid.
`outline=True` inks the silhouettes, off by default because the GUI draws
none.
From a structure, the cell is drawn whole or the call raises.
`max_atoms=` bounds the cell's own atoms with their copies on its faces, at
the GUI's 400 by default.
A cell past it raises and names its count.
HKUST-1's cell holds 648, so it needs `max_atoms=648` or more.
The bonded neighbours and polyhedron vertices drawn outside the cell do not
count against the cap.
For a site's colour or radius, edit the dict `rietx.gui.structure3d.build`
returns and pass the dict in place of the structure.
`build` trims the one cell to its own `max_atoms` instead, because that
default serves the GUI's viewer.
The dict's `cut` counts what the trim left out, and so does the figure's
report.
A site's `color` is `#rrggbb`, `"white"` or `"black"`, and `render_structure`
raises on any other spelling, because the scene would draw it grey without a
message.
`StructureFigure.palette` gives each site label drawn and its colour, for a
legend beside the figure.

On an Apple M4 in October 2026, a render of this NAC cell took
271-290 ms at 1000 px and 1.74-1.82 s at 3000 px.

There is no SVG or PDF output.
A ray-caster has no shapes to write.
Perspective, shadows and ambient occlusion are not drawn either.
The function follows the GUI's viewer, and the viewer is still changing.
Its look and keywords are {ref}`provisional <provisional-by-declaration>`.
For a picture in another program's style, `Structure.to_cif` writes each
phase with its anisotropic displacement loop.
VESTA and Jmol both read it.

### A legend, an axis triad and a scale bar

`render_structure` draws none of the three.
An agent wrote twelve figure scripts for rietx's promotional video, and ten of
them drew all three in matplotlib.
Strip height, fonts and extra marks differed in every script, so a drawing
helper would fix a style each caller then works against.
The scripts lacked data instead.
Four fitted the map from Å to pixels by least squares from `atoms`.
The rest typed the triad's directions in by hand from `view=`.
Those directions are wrong for any view that is not down an axis.
`to_px` is that map, so a direction is
`fig.to_px(v) - fig.to_px([0, 0, 0])`.

The example draws a legend from `palette`, a triad from `to_px` of each lattice
vector and a 5 Å bar from `pixels_per_angstrom`.
Each arm of the triad is 1 Å of its axis carried into pixels, so an axis
tilted out of the page draws short.
An axis within about 17° of the line of sight is drawn as a dot when it points
toward the viewer and a cross when it points away.
The third row of `rotation` is the direction toward the viewer.

```{literalinclude} ../../../examples/structure_furniture.py
:language: python
:start-at: geometry = build
```

```text
wrote ybco_furniture.png: legend ['Y', 'Ba', 'Cu', 'O'], bar 202 px for 5 Å
```

(figure-cut-and-keep)=
### Drawing part of the structure

The dict `build` returns holds its bonds and polyhedra by index into its
`atoms`.
Deleting an atom from it renumbers nothing and raises at the first later index.
`rietx.viz.keep` is the one function that renumbers.
It takes the dict and a boolean mask over `atoms` and returns a new dict with
only the atoms the mask keeps.
A bond survives when both its ends do, and a polyhedron when its centre and
every vertex do.
What it cut from a surviving atom is counted in the dict's `note` and added
to its `cut`.
Four functions build the mask, and masks combine with `&`, `|` and `~`.
Each example below is from `examples/structure_cut.py`.

```{literalinclude} ../../../examples/structure_cut.py
:language: python
:start-at: geometry = build(structure)
:end-before: a block of cells
```

```text
built: 185 atoms, 255 bonds, 34 polyhedra
without F2: 113 atoms drawn; 26 polyhedra cut · 108 bonds cut
completed: 173 atoms drawn; note ''
(110) slab: 112 atoms kept
4 Å round atom 18: 15 atoms kept
corner-sharing piece of atom 18: 168 atoms
palette: {'Ca1': '#00c4b8', 'Al1': '#bc5c70', 'Na1': '#8040e0', 'F1': '#48d860', 'F2': '#48d860', 'F3': '#48d860', 'Al1 (recoloured)': '#ff0000'}
```

- `select(g, species=, element=, label=, site=, boundary=)` picks the atoms of
  named sites.
  `F1` and `F2` share the species `F1-`, so a label or a site index tells them
  apart.
  A name the phase lacks raises and lists what it has.
- `plane(g, hkl, distance, width=None, inverse=False, units="d")` keeps the
  origin side of the plane (hkl) at `distance` d-spacings, so `distance=1` is
  the first plane beyond the origin.
  `units="angstrom"` reads Å along the plane's normal.
  `width` keeps the slab from `distance` to `distance + width` instead.
- `sphere(g, centre, radius)` keeps the atoms within `radius` Å of an atom
  index or a Cartesian point.
- `component(g, atom, via="bonds")` keeps the connected piece holding `atom`.
  `via="corners"`, `"edges"` or `"faces"` joins polyhedra sharing at least one,
  two or three vertices.
  `"edges"` and `"faces"` start from a polyhedron's centre, since the polyhedra
  round a shared vertex need not touch each other.
  Use them when bonds reach everything: by bonds every atom of NAC's cell is
  one piece.
- `recolour(g, mask, colour)` returns a dict in which the masked atoms, and the
  polyhedra centred on them, are in a new colour.
  The rest of the site keeps its own.
- `keep(g, mask, complete=True)` first re-adds the far ends of the bonds cut
  from a kept atom, and the vertices of polyhedra whose centre is kept.
  That is VESTA's boundary search.
  `complete="polyhedra"` re-adds the vertices alone, so a window of whole
  polyhedra has nothing hanging off its edge.
  On a window of YBa₂Cu₃O₇ holding 44 atoms, `complete=True` adds 80 and
  `complete="polyhedra"` adds 30.
  `complete="bonds"` re-adds the far ends alone.
  It completes only within the atoms `build` produced, which are the extent
  it was asked for and the images its bonds and polyhedra reach.
  A bond's `j` is an image of its far end and not always the atom at that end,
  so `keep` and `component` find the far end by image.
- `periodicity(g, mask)` says how many lattice directions the masked atoms
  repeat in, from 0 to 3.
  A molecule is 0, a chain 1, a layer 2 and a framework 3 (Larsen et al. 2019).
  It needs the image the piece reaches to be drawn, so it reads a mask of a
  motif and its bond neighbours, as `component` returns one.

`hidden=` does not take a site label, and its error says to use
`keep(g, ~select(g, label=...))`.
`sites` is untouched by `keep`, so `atoms[k]["site"]` keeps its meaning.
None of the functions modifies its input.

`render_structure(structure)` draws `ref.structure` and the structure is the
live model.
To change the chemistry a figure shows, edit a `model_copy(deep=True)`: an
in-place edit changes the next fit, and no history node records it.
A cut changes only the picture.

### A block of cells

`build(structure, extent=((0, 2), (0, 2), (0, 1)))` draws a block of whole
cells as a half-open box in cell units.
`extent=None` is the one cell.
The cell is built once and the block is that result translated, so the cost
grows with the atoms drawn.
Each atom is drawn once, the atoms on the block's lower faces are drawn again
on the opposite ones as the cell's own rule does, every bond of a drawn atom is
kept, and every polyhedron whose centre is drawn is kept whole.
A block that draws more than `max_atoms` raises, and the GUI's 400 is that
default, so pass a larger one.
`note` gives the atom count and the build time.

Every atom carries `image`, `[orbit index, [n1, n2, n3]]`: which atom of the
cell it is, and the whole cells it has been moved by.
Two images of one atom are told apart from two atoms by it, and
`periodicity` reads it.
`n_cell` is how many of the first `atoms` are the block's own atoms and their
face copies, the only ones a polyhedron is centred on.
`corners` and `edges` frame the block.

```{literalinclude} ../../../examples/structure_cut.py
:language: python
:start-at: a block of cells
```

```text
2x2x1 block: 599 atoms, 919 bonds, 128 polyhedra
atom 0 is [0, [0, 0, 0]], atom 351 is [11, [2, 1, 0]]
periodicity: framework 3, one octahedron 0
```

(figure-report)=
### What the figure says about itself

An image costs a reader about width × height / 750 tokens, 213 at 400 px and
1333 at 1000 px, and each look is a turn.
`StructureFigure.report` holds the numbers a look would give.
`hidden` is the share of the atoms inside the cell that are covered over more
than 80 % by an atom or a bond in front.
`hidden_atoms` lists them by their index in the dict's `atoms`, which is the
`index` each entry of the figure's `atoms` carries.
It is read from a 256 px pass that records which atom or bond is in front at
each pixel, so a stick that hides an atom counts and a translucent face does
not.
`stacked` is the part of `hidden` behind an atom of the same site, within a
quarter of the hidden atom's drawn radius.
A view down a symmetry or lattice direction stacks a site's copies by
construction, and the one in front draws what the ones behind hold.
`hidden - stacked` is what the view occludes.
One cell down a cell axis reads:

| Structure | View | `hidden` | `stacked` |
|---|---|---|---|
| HKUST-1 | a | 0.53 | 0.53 |
| ZSM-5 | b | 0.52 | 0.50 |
| YBa₂Cu₃O₇ | b | 1.00 | 1.00 |

NAC's opening view hides 0.18 and stacks none of it.
`dangling_bonds` counts bond halves whose far atom is not drawn.
The stubs a `hidden=` species leaves on its neighbours count too.
So do the bonds of a cell `build` trimmed, where the far atom was left out
of the dict.
HKUST-1 trimmed to 400 atoms has 96.
A mask on `element=` through `keep` removes the species with its bonds whole.
On NAC it is 0 for the cell, for a block of cells and after a `keep`, since
`keep` drops a bond it cuts and counts it in `cut`.
It is 158 with `boundary=False`, which leaves out the images at the cell faces
that the bonds there reach.
`label_overlaps` counts pairs of strings whose boxes intersect.
A box is the string's width and the font's height.
`label_atom_overlaps` counts pairs of a string and an atom that meet.
An atom is the ellipse it projects to, and a site label is not counted against
its own atom.
`label_bond_overlaps` counts pairs of a string and a bond that meet.
A bond is its drawn halves, widened by the stick radius.
All three count a, b and c too.
`atom_labels=True` tries eight places around each atom, up and to the right
first.
Each label keeps the first place this test finds clear of atoms, bonds and the
labels placed before it, or else the place that meets fewest.
On a paracetamol molecule at 800 px the three counts read 0, 0 and 0 with
balls and 0, 0 and 1 with ellipsoids.
The one left is C9's label, since each place around C9 meets one of its four
bonds.
With every label up and to the right, the counts read 1, 2 and 15, and 0, 3
and 14.
`empty` is the share of pixels with nothing drawn.
`cut` counts what the figure lost before it was drawn.
Its `atoms` is the cell's atoms `build`'s atom cap left out, 248 on HKUST-1.
Its `neighbours` is the bonded neighbours outside the cell that the cap left
out, and `segments` the bond segments past the bond cap of 4000.
Its `bonds` and `polyhedra` are what `keep` dropped from an atom it kept,
running over successive cuts.
`polyhedra` also counts the polyhedra the atom cap left out.
`note` is the dict's own note, and it gives the same losses in words.
`warnings` are sentences.
One says when the atom cap trimmed the cell.
Another says when an ellipsoid is drawn flat because its tensor is not
positive definite.
There is no quality score: the report is evidence and the judgement is the
reader's.

`view="auto"` tries every primitive direction `[u, v, w]` with indices up to 2,
each with the default up, and the opening view.
It ranks them by `hidden`, then `empty`, then the smaller indices and the fewer
minus signs, so the search is deterministic, and it never draws a view that
hides more than the opening view does.
`candidates` holds the best five as dicts of `view`, `hidden` and `empty`, the
first being the picture drawn, so the second choice is a lookup.
Pass a candidate's `view` back with the same `up=` and `turn=`, since the search
applied both.
Their numbers are the search's, from atoms and bonds alone at 256 px, and can
differ slightly from the report's `empty`, which reads the image.
An axis view of a cubic cell stacks atoms, and the report's `stacked` says how
many.
The ranking reads `hidden`, stacking included, so `auto` prefers an oblique
view to a projection that stacks every site behind itself.
`turn=` works on what stays hidden.

`recipe` is the call that draws the picture again.
`render_structure(structure, **fig.recipe)` with the same first argument, a
structure or a dict, gives `image` bit for bit, through JSON.
It holds every other argument as passed except `path`, with `view` the rotation
drawn and `up` and `turn` folded into it.
`phase`, `probability` and `bond_tolerance` are among them, because they choose
and build the geometry from a structure.
The first argument is the caller's to keep.
A geometry of 5000 atoms is megabytes of JSON, so save it with `json.dump`.
To look small and keep large, draw at `size=400` while working and once at the
size to keep: `render_structure(geometry, **{**fig.recipe, "size": 1000})`.

```{literalinclude} ../../../examples/structure_figure.py
:language: python
:start-at: what the figure says about itself
```

```text
opening view: 18% of atoms hidden, 0 bonds dangling, 70% of the frame empty
auto view: 7% hidden, chose [0, 1, 2], then [[1, 2, 0], [2, 0, 1]]
redrawn from the recipe with a long side of 1000 px, same view: True
```

On an Apple M4 in October 2026, at `size=400`, the report's id pass added
12 ms to a render of this cell, and `view="auto"` took 1.29-1.42 s against a
render of 97-113 ms.
At 3143 atoms the search took 22.6 s against a render of 1.02-1.06 s.

## The reflection list

`Refinement.reflection_table` returns one row per (emission line, reflection) of
every phase, and not one row per reflection. `reflection_table` is the same
table as a function, taking the compiled model, the decoded parameter values and
the structure, for a caller that holds those instead of a `Refinement`.

`ReflectionRow` is one row.

| Field | Holds |
|---|---|
| `ReflectionRow.phase` | the phase name |
| `ReflectionRow.line` | which emission line, indexed from 0 |
| `ReflectionRow.wavelength` | that line's λ in Å |
| `ReflectionRow.h`, `ReflectionRow.k`, `ReflectionRow.l` | the Miller indices |
| `ReflectionRow.d` | the d-spacing in Å |
| `ReflectionRow.two_theta` | the apparent position, in degrees |
| `ReflectionRow.multiplicity` | the Laue-group multiplicity of the orbit |
| `ReflectionRow.f_squared` | the nuclear \|F\|² (on a magnetic phase too, unless the row is a `"magnetic"` component), or `None` in Le Bail and Pawley mode |
| `ReflectionRow.intensity` | the modelled integrated intensity of this row |
| `ReflectionRow.satellite_order` | the m of Q = H + m·k, 0 on every nuclear reflection |
| `ReflectionRow.component` | `"total"`, or `"nuclear"`/`"magnetic"` where a magnetic width is active |
| `ReflectionRow.phase_index` | the phase's index in the structure, which holds where two phases share a name |

Four of those need care.

`ReflectionRow.two_theta` is where the model places the peak: the Bragg angle
plus the zero shift plus the geometry's own position correction, so it matches
`RefinementResult.ticks` rather than the ideal Bragg angle. A reflection
whose 2θ is non-physical at a given line's wavelength (sin θ > 1) is dropped for
that line only, so a row missing from one line may be present in another.

`ReflectionRow.intensity` is the whole modelled contribution and not \|F\|². In
Rietveld mode it is scale × multiplicity × \|F\|² × preferred orientation ×
line weight × Lp × extinction × absorption × roughness. It is what the peak
under the tick is made of.

`ReflectionRow.satellite_order` is 0 for every row of a phase that declares no
`Phase.propagation_vector`, which is every phase unless you asked for one. Where
it is not, `ReflectionRow.h`, `ReflectionRow.k` and `ReflectionRow.l` stay the
parent reciprocal-lattice vector H and the row is read as H and m together,
the (3+1)-index spelling; `ReflectionRow.d` is the satellite's own d-spacing,
not the parent's, and `ReflectionRow.f_squared` on such a row is exactly 0 in
Rietveld mode because this rung computes no magnetic structure factor.

`ReflectionRow.component` is `"total"` on every row unless a phase's magnetic
component is drawn with its own width (`Phase.magnetic_lor_size` or
`Phase.magnetic_lor_strain` non-zero, or free in the stage that compiled the
model; {ref}`sec-magnetic-width`). Such a phase exports two rows per (line,
reflection), one `"nuclear"` and one `"magnetic"`, because the two are drawn on
different profiles; their `ReflectionRow.intensity` values add up to the
reflection's total, and `ReflectionRow.f_squared` is each component's own
structure factor. A table read as one row per reflection would otherwise carry
the nuclear share alone and put every magnetic-only reflection at zero.

On a `"total"` row of a phase carrying moments, which is every row of it
until a magnetic width is active, `ReflectionRow.f_squared` is the nuclear
⟨|F_N|²⟩ alone, while `ReflectionRow.intensity` is built from
⟨|F_N|²⟩ + p²⟨|F_⊥|²⟩. A magnetic-only reflection, such as MnF₂'s (1 0 0) under
136.499, which is a nuclear absence, therefore has `f_squared` 0 beside one of
the largest intensities in the pattern. Read the magnetic share from
`ReflectionRow.intensity`, not from `ReflectionRow.f_squared`.

`ReflectionRow.f_squared` is `None` in Le Bail and Pawley mode, where the
per-reflection intensity is extracted or refined rather than computed from the
structure. With anomalous scattering on, which is the default, it is the
Friedel-averaged ⟨|F|²⟩ and not the representative reflection's own \|F(h)\|².
The two differ in a non-centrosymmetric group, both land in the same
powder peak, and only the average is observable in a powder.

## Writing them out

[](files.md) has the three writers that turn a result into a file, what each
file contains, and why the CIF carries a symmetry-operation loop of its own, and,
for a phase carrying a moment, the magCIF block the same writer adds:
the operator and centring loops, the BNS metadata, and the refined moments with
the modulus esd in `_atom_site_moment.magnitude_su`. A phase with no
`Phase.magnetic_symmetry` gets none of it. A phase that `magnetic_supercell` built is written by
`Structure.to_cif` in its own child cell, with no
`_space_group_magn.transform_BNS_Pp_abc`: its `MagneticSymmetry.setting` is
`None`, because the builder derives no transform to the BNS setting, and the
parent-to-child transform it does know stays in the phase name. The writer
puts `setting` into that tag only when it is a (P,p) transform in the
dictionary's form, so a `setting` holding anything else (prose saved by an
older version, or written by hand) is left out of the file.
`MagneticSymmetry.propagation_vector_parent` is not written, so the file reads
as k = 0 in the child cell.
`Refinement` carries the same three as methods on the refinement that produced
the result, which saves passing the pieces back in: `Refinement.write_cif`,
`Refinement.write_reflection_table` and `Refinement.write_qpa_table`. Each takes
a path and passes any other keyword through, so
`refinement.write_reflection_table("refl.tsv")` picks a tab delimiter from the
suffix.

## Numbers with uncertainties

`format_su` writes a value and its esd in the crystallographic `value(su)`
notation {cite}`schwarzenbach1989`: the su carries two significant figures and
the value is quoted to exactly that precision.

```python
from rietx.io.exporters import format_su

assert format_su(4.593700, 2.5e-4) == "4.59370(25)"
assert format_su(123.4, 2.5) == "123.4(25)"
assert format_su(12345.0, 250.0) == "12340(250)"
```

`4.59370(25)`, not `4.593700(250)`. An esd of 2.5 × 10⁻⁴ says the sixth decimal
is not knowledge, so the esd sets the number of decimals and the `decimals`
argument governs only the case where there is none. The CIF writers do not use
that argument. A value with no esd goes into a CIF as the shortest text that
reads back as the same number, because a fixed number of decimals loses what it
does not print.

Three cases the function handles that a format string does not. An esd like
0.0999 rounds up to two figures as 100, which is renormalised to 0.10 and one
fewer decimal rather than written as a spurious three-figure `(100)`. An esd of
1 or more takes decimals off the value and keeps its own trailing magnitude, so
12345 ± 250 is `12340(250)`. And no esd at all (`None`, non-positive, or not
finite, which is a fixed parameter or one the fit could not estimate) writes the
plain number, never an implied uncertainty.

```python
from rietx.io.exporters import format_su

assert format_su(1.234567, 0.0999) == "1.23(10)"
assert format_su(4.5937, None) == "4.593700"
```
