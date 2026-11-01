# Figures and structure pictures

This page gives the options of the fit figure `RefinementResult.plot`, and `render_structure`, which draws one phase of a structure to a PNG with the functions that cut part of it out and the numbers the picture reports about itself.

[Exports and derived tables](exports.md) gives the curves and tick positions a figure is drawn from.
[Objects in a notebook or a terminal](result.md#objects-in-a-notebook-or-a-terminal) says how a figure displays in a notebook, and `PatternData.plot` draws a pattern before any model exists ([Plotting a pattern](data.md#plotting-a-pattern)).

## The fit figure

`RefinementResult.plot` draws the standard panel: the observed points, the calculated line, the `obs − calc` difference on the same axis at the same scale, and one row of reflection ticks per phase.
It draws with matplotlib and returns the figure, so `path=` is optional.
It forwards to `rietx.viz.plots.plot_result`.

| Keyword | Default | Effect |
|---|---|---|
| `path` | `None` | writes the figure to that file as well |
| `two_theta_range` | the whole pattern | a window in degrees 2θ, whatever the x axis |
| `show_background` | `True` | draws the background curve |
| `weighted` | `False` | draws Δ/σ in a panel of its own, with a ±3σ band |
| `x_axis` | `"two_theta"` | `"q"` or `"d"` redraws against Q or d-spacing |
| `wavelength` | `None` | the λ in Å written on the 2θ axis in place of the recorded one, and the one Q and d are derived through |
| `y_scale` | `"linear"` | `"sqrt"`, `"log"` or `"asinh"` |
| `label_align` | `"bottom"` | `"curve"` puts each curve's name level with the end of its curve |
| `style` | `"light"` | `"dark"` for a figure going onto a dark page |
| `figsize`, `font_size` | 7.6 in wide, 11 pt | the size the figure is built at |
| `dpi` | 300 | the raster resolution of a PNG |
| `title` | `None` | words drawn above the data panel ([Printing a result](result.md#printing-a-result)) |

`two_theta_range` selects channels rather than cropping a whole-range figure.
The intensity scale, the difference offset and the tick rows are built from what the window contains, so a zoom into a weak region is a figure of its own data.
A window holding no points raises `ValueError`.

`weighted=True` puts the residual on an absolute statistical scale.
A raw difference shares the intensity axis, so the eye reads a small deviation on a strong peak as a large error.
Δ/σ has expectation 1 under a correct model, and the ±3σ band is a fixed scale.
It is not the default because its panel separates the residual from the peak that caused it, which the classic layout shows in one glance.

The 2θ axis label names the radiation the fit used, which `RefinementResult.radiation` records as a `Radiation`.
`Radiation.kind` is the source's `kind`, `"xray_cw"` or `"neutron_cw"`.
`Radiation.wavelengths` holds each emission line's λ in Å at the answer, primary first, so a refined wavelength is recorded as refined.
The label reads `2θ (degrees), Cu Kα, λ = 1.54059 Å`, by the rule `PatternData.plot` uses ([Plotting a pattern](data.md#plotting-a-pattern)).
A refined wavelength, a synchrotron or a neutron source shows λ alone.
A joint fit records each histogram's own in `HistogramResult.radiation`, so `result.for_histogram(h).plot()` names histogram `h`'s.
A result saved by a version without the record has `radiation=None` and shows `2θ (degrees)`.
`wavelength=` replaces the recorded λ.
`x_axis="q"` and `x_axis="d"` raise without it, because the label converts nothing.
A d axis is drawn ascending, so the pattern is mirrored rather than the axis reversed.

`y_scale="sqrt"` gives equal display distance to equal counting σ.
`"log"` compresses hardest, and `"asinh"` keeps channels at or below zero.
Each of the three moves the difference into a linear panel of its own, because an offset raw difference is negative by construction and a nonlinear intensity axis cannot draw it.

Build the figure at the width it will be read at with `figsize=` and `font_size=`, and do not scale it in the document afterwards.
The default is 7.6 by 4.4 in, or 7.6 by 5.6 in when the difference has its own panel.
A `.svg` or `.pdf` `path` is vector output, where `dpi` does not apply.

### Figures in a dark notebook

A notebook needs no `style="dark"`.
A pattern, fit, series or indexing figure drawn light carries a dark copy in its output, and a frontend in a dark theme shows that copy.
JupyterLab 4, Notebook 7 and JupyterLite switch it live, and this manual switches it with its own theme.
VS Code and Colab carry the same switch, read from their source and not yet seen running.
A frontend that strips the switch shows the light figure: GitHub's notebook viewer, and JupyterLab on a notebook opened with its outputs until the cell runs again.
What you add to the returned figure, such as an annotation, appears in both copies.
A structure figure on the default white ground works the same way.

## Structure pictures

`rietx.viz.render_structure` draws one phase as the GUI's structure viewer draws it, to an RGBA array or a PNG.
It needs no browser, no display and nothing beyond the base install.
The geometry, the scene rules and the lighting are the viewer's own, so a picture drawn from a script matches one exported from the GUI.
This example draws the NAC cell (COD 1000236) four ways:

```{literalinclude} ../../../examples/structure_figure.py
:language: python
:start-at: structure = rx.Structure
:end-before: what the figure says about itself
```

<!-- output of examples/structure_figure.py -->
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
`np.asarray(fig)` and `plt.imshow(fig)` both take the figure itself, and a notebook cell holding one shows the picture.

| Field | Holds |
|---|---|
| `image` | the picture, height × width × 4 bytes, straight alpha |
| `rotation` | the view drawn, as three rows: the screen's right, up and the direction toward the viewer, in the structure's Cartesian frame |
| `pixels_per_angstrom` | the scale of the picture |
| `origin` | the view-plane position of pixel (0, 0), the top-left corner, in Å |
| `atoms` | one entry per atom drawn: its index into the geometry, its site, label and species, whether it is an image outside the cell, its x and y in pixels from the top-left corner, and its depth |
| `letters` | the a, b and c on the cell's edges, each with its x and y in pixels |
| `path` | the PNG written, or `None` |
| `palette` | each site label drawn and its colour as `#rrggbb`, for a legend beside the figure |
| `report` | the numbers a look at the picture would give ([What the figure reports](#what-the-figure-reports)) |
| `candidates` | with `view="auto"`, the best five views the search ranked |
| `recipe` | the arguments that draw the picture again |

`StructureFigure.to_px` takes Cartesian points in Å, one or an `(N, 3)` array, and returns where they land in the image, x right and y down.
It is the map that placed `atoms`, and `rotation`, `pixels_per_angstrom` and `StructureFigure.origin` make it.
Depth is dropped, because the projection is parallel.
A site recoloured in part appears in `StructureFigure.palette` a second time, as `"<label> (recoloured)"`.

### Views

`view=` takes these forms:

- `"opening"`, the GUI's first picture, and the default;
- `"a"`, `"b"` or `"c"`, the GUI's buttons;
- a lattice direction `[u, v, w]`;
- a plane normal `{"hkl": (h, k, l)}`;
- a rotation, such as a figure's own `rotation`;
- `"auto"`, which picks the view that hides the fewest atoms ([What the figure reports](#what-the-figure-reports)).

The named direction points toward you.
`up=` takes the same forms.
By default c is up, or b when you look down c, as in VESTA's standard orientation.
`turn=` is ASE's rotation string (`"30y,-15x"`), turning about the screen's axes in the order written.
Every view is fitted to the frame, and the projection is parallel.

### Size and resolution

`size=` is the long side in pixels, 1000 by default, or a `(width, height)` pair.
Line widths and letters grow with it, as they do in the GUI's export, so a larger picture is the same figure at a higher resolution.
`dpi=` goes only into the PNG's `pHYs` chunk.
A 17 cm figure at 300 dpi is `size=2008, dpi=300`.
`supersample=` sets how many samples are taken along each side of a pixel, from 1 to 4, and 2 by default.
More samples draw smoother edges.
`path=` writes a PNG and refuses any other suffix.

### Drawing options

| Keyword | Default | Effect |
|---|---|---|
| `phase` | 0 | which phase of the structure to draw |
| `mode` | `"ball"` | `"ball"` or `"ellipsoid"` |
| `probability` | 50 % | the ellipsoids' probability level |
| `exaggeration` | 1.0 | a drawing scale on the ellipsoids, on top of `probability` |
| `stick` | 1.0 | a multiple of the bond sticks' radius |
| `hidden` | none | species or elements to leave out, with their bond halves |
| `boundary` | `True` | `False` leaves out the images outside the cell |
| `cell` | `True` | `False` leaves out the cell's frame and its a, b and c |
| `polyhedra` | on for balls, off for ellipsoids | `True`, `False`, or a switch per formula such as `{"AlF₆": False}` |
| `axis_labels` | `True` | the a, b and c on the cell's edges |
| `atom_labels` | `False` | each site's label beside its atom |
| `outline` | `False` | inks the silhouettes, which the GUI does not |
| `background` | `"white"` | `"white"`, `"black"`, `"#rrggbb"`, three channels from 0 to 1, or `None` for transparent |
| `bond_tolerance` | 1.15 | the bond threshold, as a multiple of the sum of the two atoms' radii |
| `max_atoms` | 400 | the most atoms the cell may draw, its face copies included |

A stick's radius is 0.08 Å in ball mode.
In ellipsoid mode it is half the smallest drawn semi-axis, from 0.02 Å to 0.08 Å, and the 0.02 Å floor does not scale with `stick`.
For paracetamol at 100 K (COD 2104364) that radius is 0.072 Å, and `stick=0.5` draws 0.036 Å.
Up to `stick=1` a stick stays inside every ellipsoid it ends in, and above it a stick may show through the side of a small ellipsoid.

A name in `hidden` the phase does not have raises and lists the species it has.
The other half of each bond to a hidden atom stays, as a stub.
One site is left out by a mask instead ([Drawing part of the structure](#drawing-part-of-the-structure)).
`hidden` does not take a site label, and its error says to use `keep(g, ~select(g, label=...))`.

`cell=False` fits the view to the atoms alone.
A 22 Å sphere cut from HKUST-1's 26 Å cell draws at 8.5 px/Å with the frame and at 16.4 px/Å without it, at `size=400`.

From a structure, the cell is drawn whole or the call raises.
`max_atoms` bounds the cell's own atoms with their copies on its faces, and a cell past it raises and names its count.
HKUST-1's cell holds 648, so it needs `max_atoms=648` or more.
The bonded neighbours and polyhedron vertices drawn outside the cell do not count against the cap.

For a site's colour or radius, edit the dict `rietx.gui.structure3d.build` returns and pass the dict in place of the structure.
`build` trims the cell to its own `max_atoms` instead of raising, because that default serves the GUI's viewer.
The dict's `cut` counts what the trim left out, and so does the figure's report.
A dict says what was built, so `probability`, `bond_tolerance` and `max_atoms` are refused beside one.
A site's `color` is `#rrggbb`, `"white"` or `"black"`.
`render_structure` raises on any other spelling, because the scene would draw it grey without a message.

On an Apple M4 in October 2026, a render of the NAC cell took 35-41 ms at 1000 px and 89-117 ms at 3000 px.

### Limits

There is no SVG or PDF output, because a ray-caster has no shapes to write.
Perspective, shadows and ambient occlusion are not drawn either.
The function follows the GUI's viewer, and the viewer is still changing, so its look and its keywords are {ref}`provisional <provisional-by-declaration>`.
For a picture in another program's style, `Structure.to_cif` writes each phase with its anisotropic displacement loop, which VESTA and Jmol both read.

## Legend, axis triad and scale bar

`render_structure` draws none of the three.
Their size, type and placement differ from figure to figure, so a drawing helper would fix a style each caller then works against.
The figure carries the data each needs instead:

- `palette` gives each site's colour, for a legend;
- `to_px` maps a direction into the picture, for an axis triad;
- `pixels_per_angstrom` gives the scale, for a scale bar.

A direction in the picture is `fig.to_px(v) - fig.to_px([0, 0, 0])`.
A direction typed in by hand from `view=` is wrong for any view that is not down an axis.

The example below draws all three under a picture of YBa₂Cu₃O₇ (COD 9007744).
Each arm of the triad is 1 Å of its axis carried into pixels, so an axis tilted out of the page draws short.
An axis within about 17° of the line of sight is drawn as a dot when it points toward the viewer and as a cross when it points away.
The third row of `rotation` is the direction toward the viewer.

```{literalinclude} ../../../examples/structure_furniture.py
:language: python
:start-at: geometry = build
```

<!-- output of examples/structure_furniture.py -->
```text
wrote ybco_furniture.png: legend ['Y', 'Ba', 'Cu', 'O'], bar 202 px for 5 Å
```

## Drawing part of the structure

The dict `build` returns holds its bonds and polyhedra by index into its `atoms`.
Deleting an atom from it renumbers nothing, and the draw raises at the first later index.
`rietx.viz.keep` renumbers.
It takes the dict and a boolean mask over `atoms`, and returns a new dict with only the atoms the mask keeps.
A bond survives when both its ends do, and a polyhedron when its centre and every vertex do.
What it cut from a surviving atom is counted in the dict's `note` and added to its `cut`.
Four functions build a mask, and masks combine with `&`, `|` and `~`.
These examples are from `examples/structure_cut.py`, on the NAC cell:

```{literalinclude} ../../../examples/structure_cut.py
:language: python
:start-at: geometry = build(structure)
:end-before: a block of cells
```

<!-- output of examples/structure_cut.py -->
```text
built: 185 atoms, 255 bonds, 34 polyhedra
without F2: 113 atoms drawn; 26 polyhedra cut · 108 bonds cut
completed: 173 atoms drawn; note ''
(110) slab: 104 atoms kept
4 Å round atom 18: 15 atoms kept
corner-sharing piece of atom 18: 168 atoms
palette: {'Ca1': '#00c4b8', 'Al1': '#bc5c70', 'Na1': '#8040e0', 'F1': '#48d860', 'F2': '#48d860', 'F3': '#48d860', 'Al1 (recoloured)': '#ff0000'}
```

- `select(g, species=, element=, label=, site=, boundary=)` picks the atoms of the named sites. `F1` and `F2` share the species `F1-`, so a label or a site index tells them apart. `boundary=True` keeps only the images outside the cell, and `False` only those inside. A name the phase lacks raises and lists what it has.
- `plane(g, hkl, distance, width=None, inverse=False, units="d")` keeps the origin side of the plane (hkl) at `distance` d-spacings, so `distance=1` is the first plane beyond the origin. `units="angstrom"` reads Å along the plane's normal. `width` keeps the slab from `distance` to `distance + width` instead, and `inverse=True` keeps what the plane would have cut.
- `sphere(g, centre, radius)` keeps the atoms within `radius` Å of an atom index or a Cartesian point.
- `component(g, atom, via="bonds")` keeps the connected piece holding `atom`. `via="corners"`, `"edges"` or `"faces"` joins polyhedra sharing at least one, two or three vertices. `"edges"` and `"faces"` start from a polyhedron's centre, since the polyhedra round a shared vertex need not touch each other. Use them where bonds reach everything: by bonds every atom of NAC's cell is one piece.
- `recolour(g, mask, colour)` returns a dict in which the masked atoms, and the polyhedra centred on them, are in a new colour. The rest of the site keeps its own.
- `keep(g, mask, complete=True)` first adds back the far ends of the bonds cut from a kept atom, and the vertices of the polyhedra whose centre is kept, as VESTA's boundary search does. `complete="polyhedra"` adds back the vertices alone, so a window of whole polyhedra has nothing hanging off its edge, and `complete="bonds"` the far ends alone. On a window of YBa₂Cu₃O₇ holding 44 atoms, `complete=True` adds 80 and `complete="polyhedra"` adds 30. It completes only within the atoms `build` produced: the extent it was asked for and the images its bonds and polyhedra reach. The default is `complete=False`.
- `periodicity(g, mask)` says in how many lattice directions the masked atoms repeat, from 0 to 3. A molecule is 0, a chain 1, a layer 2 and a framework 3 (Larsen et al. 2019). It needs the image a piece reaches to be drawn, so it reads a mask of a motif and its bonded neighbours, as `component` returns one.

A bond's `j` is an image of its far end and not always the atom at that end, so `keep` and `component` find the far end by image.
`sites` is untouched by `keep`, so `atoms[k]["site"]` keeps its meaning.
None of the functions modifies its input.

`render_structure(ref.structure)` draws the live model.
To change the chemistry a figure shows, edit a `model_copy(deep=True)` of it: an edit in place changes the next fit, and no history node records it.
A cut changes only the picture.

### A block of cells

`build(structure, extent=((0, 2), (0, 2), (0, 1)))` draws a block of whole cells as a half-open box in cell units.
`extent=None` is the one cell.
The cell is built once and the block is that result translated, so the cost grows with the atoms drawn.
Each atom is drawn once, and the atoms on the block's lower faces are drawn again on the opposite faces, as the cell's own rule does.
Every bond of a drawn atom is kept, and every polyhedron whose centre is drawn is kept whole.
A block that draws more than `max_atoms` raises, and the GUI's 400 is that default, so pass a larger one.
`note` gives the atom count and the build time.

Every atom carries `image`, `[orbit index, [n1, n2, n3]]`: which atom of the cell it is, and the whole cells it has been moved by.
It tells two images of one atom from two atoms, and `periodicity` reads it.
`n_cell` is how many of the first `atoms` are the block's own atoms and their face copies, the only atoms a polyhedron is centred on.
`corners` and `edges` frame the block.

```{literalinclude} ../../../examples/structure_cut.py
:language: python
:start-at: a block of cells
```

<!-- output of examples/structure_cut.py -->
```text
2x2x1 block: 599 atoms, 919 bonds, 128 polyhedra
atom 0 is [0, [0, 0, 0]], atom 351 is [11, [2, 1, 0]]
periodicity: framework 3, one octahedron 0
```

## What the figure reports

An image costs a model reading it about width × height / 750 tokens: 213 at 400 px and 1333 at 1000 px.
`StructureFigure.report` holds the numbers a look would give, so a program can judge a picture without looking at it.
There is no quality score: the report is evidence, and the judgement is the reader's.

| Field | Holds |
|---|---|
| `hidden` | the share of the atoms inside the cell covered over more than 80 % by an atom or a bond in front |
| `hidden_atoms` | those atoms, by their index in the dict's `atoms`, which is the `index` each entry of the figure's `atoms` carries |
| `stacked` | the part of `hidden` behind an atom of the same site, within a quarter of the hidden atom's drawn radius |
| `dangling_bonds` | the bond halves whose far atom is not drawn |
| `label_overlaps` | the pairs of strings whose boxes intersect |
| `label_atom_overlaps` | the pairs of a string and an atom that meet |
| `label_bond_overlaps` | the pairs of a string and a bond that meet |
| `empty` | the share of the picture's pixels with nothing drawn |
| `cut` | what the figure lost before it was drawn |
| `note` | the dict's own note, the same losses in words |
| `warnings` | sentences about the drawing |

`hidden` is read from a 256 px pass that records which atom or bond is in front at each pixel, so a stick that hides an atom counts and a translucent face does not.
An atom smaller than one sample at that size is left out of the count, and a warning says how many were.
A view down a symmetry or lattice direction stacks a site's copies by construction, and the one in front draws what the ones behind hold, so `hidden - stacked` is what the view occludes.
One cell down a cell axis reads:

| Structure | View | `hidden` | `stacked` |
|---|---|---|---|
| HKUST-1 | a | 0.53 | 0.53 |
| ZSM-5 | b | 0.52 | 0.50 |
| YBa₂Cu₃O₇ | b | 1.00 | 1.00 |

NAC's opening view hides 0.18 and stacks none of it.

`dangling_bonds` counts the stubs a `hidden=` species leaves on its neighbours, and the bonds of a cell `build` trimmed, where the far atom was left out of the dict.
HKUST-1 trimmed to 400 atoms has 96.
A mask on `element=` through `keep` removes the species with its bonds whole.
On NAC it is 0 for the cell, for a block of cells and after a `keep`, since `keep` drops a bond it cuts and counts it in `cut`.
It is 158 with `boundary=False`, which leaves out the images at the cell faces that the bonds there reach.

A string's box is its width and the font's height.
An atom is the ellipse it projects to, and a site label is not counted against its own atom.
A bond is its drawn halves, widened by the stick radius.
All three label counts include a, b and c.
`atom_labels=True` tries eight places around each atom, up and to the right first.
Each label takes the first place clear of atoms, bonds and the labels placed before it, or else the place that meets fewest.
On a paracetamol molecule at 800 px the three counts read 0, 0 and 0 with balls, and 0, 0 and 1 with ellipsoids.
The one left is C9's label, since each place around C9 meets one of its four bonds.
With every label up and to the right, the counts read 1, 2 and 15, and 0, 3 and 14.

`cut` has five counts.
Its `atoms` is the cell's atoms that `build`'s atom cap left out, 248 on HKUST-1.
Its `neighbours` is the bonded neighbours outside the cell that the cap left out, and `segments` the bond segments past the bond cap of 4000.
Its `bonds` and `polyhedra` are what `keep` dropped from an atom it kept, summed over successive cuts, and `polyhedra` also counts the polyhedra the atom cap left out.
One warning says when a cap trimmed the cell, and another when an ellipsoid is drawn flat because its tensor is not positive definite.

### The automatic view

`view="auto"` tries every primitive direction `[u, v, w]` with indices up to 2, and the opening view, each with your `up=` and `turn=`.
It ranks them by `hidden`, then `empty`, then by smaller indices and fewer minus signs, so the search is deterministic.
It never draws a view that hides more than the opening view does.
`StructureFigure.candidates` holds the best five as dictionaries of `view`, `hidden` and `empty`, the first being the picture drawn, so the second choice is a lookup.
Pass a candidate's `view` back with the same `up=` and `turn=`, since the search applied both.
Its numbers are the search's, from atoms and bonds alone at 256 px, and can differ slightly from the report's `empty`, which reads the image.
The ranking reads `hidden` with stacking included, so `auto` prefers an oblique view to an axis projection that stacks every site behind itself.
`turn=` works on what stays hidden.

### The recipe

`StructureFigure.recipe` is the call that draws the picture again.
`render_structure(structure, **fig.recipe)` with the same first argument, a structure or a dict, gives `image` bit for bit, through JSON.
It holds every other argument as passed except `path`, with `view` the rotation drawn and `up` and `turn` folded into it.
`phase`, `probability` and `bond_tolerance` are among them, because they choose and build the geometry from a structure.
The first argument is yours to keep, and a geometry of 5000 atoms is megabytes of JSON, so save it with `json.dump`.
To look small and keep large, draw at `size=400` while working and once at the size to keep: `render_structure(geometry, **{**fig.recipe, "size": 1000})`.

```{literalinclude} ../../../examples/structure_figure.py
:language: python
:start-at: what the figure says about itself
```

<!-- output of examples/structure_figure.py -->
```text
opening view: 18% of atoms hidden, 0 bonds dangling, 70% of the frame empty
auto view: 7% hidden, chose [0, 1, 2], then [[1, 2, 0], [2, 0, 1]]
redrawn from the recipe with a long side of 1000 px, same view: True
```

On an Apple M4 in October 2026, at `size=400`, the report's 256 px pass added 0.65-0.76 ms to a render of the NAC cell, and `view="auto"` took 90-107 ms against a render of 27-34 ms.
At 3143 atoms the search took 530-548 ms against a render of 175-209 ms.
