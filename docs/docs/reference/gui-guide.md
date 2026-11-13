# The GUI panel by panel

This page covers the GUI's whole window, panel by panel: what each panel is for, and the handful of things about it that the screen cannot say about itself.

The [GUI tutorial](../start/gui-quickstart.md) runs one fit and reads it.
Read this page beside the app rather than instead of it. Most controls carry their own
explanation: a dotted underline means a definition is one click away, and the
popover it opens is generated from the same help corpus as the
[parameter map](parameters.md) and the [diagnostic codes](diagnostics.md).
What is written here is the part no tooltip can hold: why a
control behaves as it does, and when you should reach for it.

## The shape of the window

Two sides. The graphs are on the left, under their own tab strip. It holds
three tabs, `Pattern`, `Single peaks` and `Background`. A title line under it says what the
graph shows. On the pattern it reads `Observed pattern` before any fit, `Last fit` after one, and
`Refining` while a run is in flight. While the Interactive tab has values
waiting, it says `Preview, not refined`. The panel column is on the right, with
ten tabs, the action bar and the console. Every panel is mounted at once, so a filter you typed, an
edit you have not applied and a text buffer you are half way through all survive
a look at another tab.

Each side has a collapse button at its own end of the header. One side always
stays, so the button of the last side showing is disabled. The buttons never
move: the middle of the header wraps within itself. Collapsing is a view choice
and is not persisted. The width you drag on the sash between the sides is
persisted, per project, and a double-click on the sash resets it. Two panels
want the room, and collapsing the graphs is for them: the Text document's
editable columns need about 550 px and the atom table about 470.

Below 760 px of window the two sides cannot both meet their floors, 420 px of
graph and 340 px of panel, so they stack. The graphs go on top and the panels
below, and the sash then drags up and down.

## The header

| Control | Does |
|---|---|
| the project's name | opens the File menu, below; `No project` when none is open |
| the project line | the data file, the point count, the intensity mode, and whether σ came from the file or from counting statistics |
| the two collapse buttons | hide the graphs (left end) or the panel column (right end) |
| `Simple \| Advanced` | whether the Plan, Model, Series and Report panels show their advanced controls |
| `◐ ☀ ☾` | theme: follow the system, light, dark |
| the run pill | the stage and its number while busy; the last status otherwise |
| `Cancel` | stop the run between iterations |
| `⌘K` | every command, with the Python call it makes |

`Rwp` and `GoF` are on the title line over the pattern. `⚠ not a fit yet`
appears beside them past an Rwp of {{ MATURITY_MAX_RWP }}.

### The File menu

Click the project's name to open the File menu. Work saves itself as you go, so
the menu has no Save. `⌘S` answers `Saved` and does nothing else.

| Item | Does |
|---|---|
| `New project…` | the New project dialog |
| `Open…` | the folder browser, to open another `.rex`; `⌘O` |
| `Open recent` | the other projects on the recent list, and `Clear the list` |
| `Save a copy…` | copies the whole `.rex` folder with its history, under a name and into a folder you choose; the window stays on the original; `⇧⌘S` |
| `Rename…` | turns the name into a text box; `Enter` renames the folder, and `Esc` keeps the old name |
| `Move to…` | moves the folder into another folder you choose |
| `Export` | writes one of the six exports into a folder you choose, starting beside the project |
| `Close project` | returns to the start screen |

The folders come from the folder browser, which lists only your home directory
and the working directory. A page in a browser cannot open the system's own save
dialog. None of these items replaces a folder that already exists. An export
refuses a file of the same name once, and the dialog's button then reads
`Replace`. Every item that changes the folder is refused while a run is in
flight.

An export that needs a fit stays disabled until there is one. The instrument
profile is the exception, because it is read from the project. Phase fractions
also needs a Rietveld fit with two phases or more.

After `Close project`, the next `rietx gui` with no project named shows the start
screen. The `Open or create a project` palette command shows the start screen
over an open project, with `Back to the project` to return.

## The action bar

One row under the panel column, on every tab.

| Control | Does |
|---|---|
| `One cycle \| Staged plan` | what a refine runs: one stage on exactly the ticked parameters, or the project's plan |
| the pending count | how many Parameters and Interactive edits wait, plus one for an edited plan, and the first refusal if one is invalid |
| `Revert` / `Apply` | drop or apply the pending edits: the Parameters edits first, then the Interactive values, then the plan |
| `Refine` | run the choice; it reads `Apply and refine` while edits wait, and applies them first |

`⌘⏎` (`Ctrl+Enter` off a Mac) presses `Refine`, except inside the Text
document, where it applies the document. A refused edit runs nothing. A plan
replaces the vary flags, so a parameter you ticked by hand stays free under
`One cycle` and may be held again under `Staged plan`. The Plan tab's ladder
shows which.

There is no Save command, and that is not an omission. Settings
persist on the verb. The moment you tick a box or drag a region it is written to
the project, so there is nothing to save on close.
`Save the project` exists as a palette command for the one case that is not
covered, which is writing out the settings file after an edit made from
elsewhere.

### Edits not yet applied

An edit in the action bar's count stays pending until `Apply`. The window keeps
the pending edits in a recovery copy, in the application's own state directory
beside the recent list and apart from the project, as editors such as VS Code
keep theirs. The copy is written half a second after each change, and again
before the project closes. So closing the project, opening another, closing the
browser tab or stopping the server keeps them.

Opening the project again shows `Unapplied edits`, with how many and when they
were made. `Restore` puts them back as pending edits, and `Discard` deletes
them. `Escape` closes the dialog and keeps the copy without restoring it. The
dialog comes back the next time the project opens. Edits you make before then
are not kept. If the project has been refined or edited since, for example by a
fit run from Python, the dialog adds "The project has been refined or edited
since. Restored values will replace the current ones." Restored edits still
wait in the action bar until you apply them.

The copy is deleted once the edits are applied, reverted or discarded. It
follows the project through `Rename…` and `Move to…`. `Save a copy…`, and a
folder moved outside the app, leave it behind. The Model panel's forms and the
Text document apply through their own buttons, so they are not kept.

The theme belongs to you and not to the project. It lives beside the recent list
in the application's own settings, so it follows you across projects, ports and
browser profiles. It is also the one control that still works while a run is in
flight, because it is not about the project.

## The pattern

The left column is the measured points, the calculated pattern, the background,
a band of reflection ticks, and the difference curve underneath.

```{image} ../screenshots/plot-readout-light.png
:class: only-light
:alt: The pattern with observed and calculated curves, a tick band, the difference below, then the readout strip, the knob strip and the fitted-range strip
```

```{image} ../screenshots/plot-readout-dark.png
:class: only-dark
:alt: The pattern with observed and calculated curves, a tick band, the difference below, then the readout strip, the knob strip and the fitted-range strip
```

### Reading under the pointer

There is no hover tooltip; a box that covered the data was worse than no box.
What you get instead is the readout strip under the plot: a fixed set of slots
that always shows 2θ and d, then one row per drawn curve, each label in that
curve's own colour, plus the nearest reflection of each phase as a signed offset.
A slot empties to `—` when there is nothing under the pointer, so the plot above
never resizes as you move. A solid vertical line marks where you are.

The strip follows what is drawn. Hide a curve and its row goes; press
`data only` and the strip empties down to the measured points. That is correct
behaviour.

### The two kinds of knob

Only one kind changes the answer, and both sit under the same plot and look
alike.

Drawing choices change the picture and nothing else. They are not persisted, so
they reset with the session:

- the residual selector: `Δ/σ`, `Δ`, `Σχ²`;
- the intensity scale: `lin`, `√`, `log`;
- the per-curve visibility toggles, and `data only`.

`Σχ²` accumulates the weighted misfit from left to right, so a flat stretch is a
region that cost nothing and a step is a region that cost a lot. A curve that is
a staircase with one tall step tells you where to look in a way that no
whole-pattern number can.

Protocol controls change what is fitted, move Rwp, and persist the moment you
set them:

- the fitted range: two typed boxes, or the `⇥ range` gesture;
- the excluded regions: a list of pills, or the `✂ exclude` gesture;
- and beside them the count, `N of M channels fitted`, which puts a number on
  the shaded band on the plot.

Because settings persist immediately and curves only move on a run, the two can
disagree, and the panel says so:
`the curves shown were fitted over a different set of channels — re-run`.

### The armed gestures

`⇥ range` and `✂ exclude` are modes, not modifiers. Press one and the next drag
on the plot sets a range or excludes a region instead of zooming; the cursor
changes to say so, the peak gestures are suspended while it is armed, one
selection disarms it, and `Esc` cancels.

They have to be modes because a region drag and a zoom drag are the same gesture
at every distance. There is no radius at which the app could tell them apart.
The peak gestures below are the opposite case, where the ambiguity is local and
can be resolved by aim.

The plot holds every channel of the pattern, sent once, so a zoom fetches
nothing and zooming in shows every point the file has. Drag to zoom, scroll to
zoom about the pointer, and shift-scroll or alt-drag to pan. Double-click
returns the whole pattern. The view stays where you put it across a peak edit, a
knob change and a fit that lands on the same channels. A pattern past 150 000
channels arrives as a min/max sample, and the line under the plot says so.

### Saving the picture

Four buttons at the end of the knob strip save or copy what the plot shows
now, at your zoom. The two pictures leave your hidden curves out.

| Button | Gives |
|---|---|
| `PNG` | the plot as a PNG file, at your screen's pixel density |
| `SVG` | the plot redrawn as vectors, for a figure you will edit |
| `copy image` | the PNG, on the clipboard |
| `copy data` | every channel in view as tab-separated columns, which a spreadsheet pastes |

The columns are `two_theta`, `y_obs`, `excluded` (1 for an excluded channel),
`y_calc`, `y_background`, and the residual the selector shows, and a hidden
curve keeps its column. The legend is in neither picture, so name the curves
in your caption. The line beside the buttons says what each press did, and
says so when a browser refuses the clipboard.

## Single peaks

The second graph tab frames three reflections, one window each. The pattern is
cut into twelve equal ranges of 2θ. Each range offers its strongest reflection,
ranked by the last fit's height above its background. The windows open on one
low, one middle and one high reflection, and `‹` and `›` step a window to the
next one. A window spans five peak widths either side of its reflection.

Each window draws the observed points, the last fit and the normalised residual
in a strip below. While the Interactive tab has values waiting, the preview is
drawn solid and the last fit dashed in the same colour. The residual strip then
shows the preview's residual. The y range stays the last fit's, so a peak the
preview grows runs off the top of its window. A comparison that rescaled with
each drag would hide the change you are trying to see.

Before any fit there is nothing to frame, and the tab says so.

```{image} ../screenshots/single-peaks-light.png
:class: only-light
:alt: Three windows on single reflections, each with observed crosses, the fitted curve and a residual strip, and arrows beside each caption to step to the next reflection
```

```{image} ../screenshots/single-peaks-dark.png
:class: only-dark
:alt: Three windows on single reflections, each with observed crosses, the fitted curve and a residual strip, and arrows beside each caption to step to the next reflection
```

## The background

The `Background` graph tab draws the background on its own. The observed
pattern is greyed behind it, and the frame is set by the curve, so the peaks
run off the top. The curve is drawn at the working values, the ones the next
run starts from, and the title line says so.

The shaded band is where the curve may move when the free parameters refine.
It is the curve's esd at each channel, taken through the whole covariance of
every free parameter: equation {eq}`est-derived` of
[Esds of derived quantities](../theory/estimation.md#esds-of-derived-quantities),
with the background curve as the derived quantity. `rietx.gui.background`
computes it. A free scale or Biso that trades against the background
therefore widens it. The band is drawn at ±3 esd, and `×5` and `×20` draw it
wider still. A multiplier exaggerates the picture and is not a probability. The
band is linearised at the current values, so before a fit converges it
describes the curvature there and nothing more. With no background term free
there is no band, and the `Band ±3 esd` label opens a note saying why. The route
behind it is `GET /api/background`.

```{image} ../screenshots/background-tab-light.png
:class: only-light
:alt: The Background tab after one fit, the greyed pattern behind a falling background curve with a narrow band, and six hold boxes c0 to c5 under it beside the band's multiplier
```

```{image} ../screenshots/background-tab-dark.png
:class: only-dark
:alt: The Background tab after one fit, the greyed pattern behind a falling background curve with a narrow band, and six hold boxes c0 to c5 under it beside the band's multiplier
```

The controls under the plot follow the background family.

| family | control | what it does |
|---|---|---|
| Chebyshev | a `Hold` box per term, `c0` upwards | holds the term at its value from the previous cycle; no plan stage frees it until it is released |
| P-spline | `Smoothness λ` | the penalty's weight, applied on Enter or when the box loses focus; larger is stiffer |

A hold is `Refinement.hold`, and a release `Refinement.unhold`. Each records a
history node, and the console echoes the call. The Parameters panel offers no
switch per coefficient, since one coefficient alone means little. The family and
the number of Chebyshev terms are set in Model.

## Parameters

Every parameter the model has, grouped the way a refinement is read. The panel
shows each phase in a band headed by its name, its space group and its crystal
system. The instrument follows in a band of its own.

Inside a phase, single parameters such as `Scale` come first. The groups follow
in the order a refinement frees them: `Cell`, then `Size and strain`. The atoms
come last, in a table with one row per atom. Each atom row shows the label, the
species, the Wyckoff letter, x, y and z, the occupancy, Biso and the site
multiplicity. The instrument band lists the zero shift and the displacement
first, then `Background`, `Peak shape`, `Axial divergence` and `Source and
geometry`.

The `Cell` group shows only the edges and angles the space group leaves free.
The rest fold into one line, such as `a = b, α = β = 90°, γ = 120°` for a
hexagonal cell. Press that line to see the held rows behind it.

A checkbox stands beside each parameter it frees, and nowhere else. A group's
heading has a box that frees or fixes every member at once; it shows a dash when
only some are free. The atom table's column headings carry the same kind of box
for every position, every occupancy and every Biso. An atom's position has one
box per direction its site allows, beside the coordinate that direction moves.

A row that cannot be freed has no checkbox. It carries a mark naming the reason
it is held: it is locked by symmetry, tied to another parameter, fixed by the
intensity mode, or needs a held cell. Press the mark for the reason in the
package's own words.

The padlock is `hold`. A held parameter stays fixed even when a plan stage's
glob names it, which `vary=False` alone does not do. An atom with a free site
has a padlock beside its Wyckoff letter, which holds its whole position. A
plain row shows its padlock in the checkbox's place while it is held.

Numbers keep their columns. Values from 0.01 up to 10 000 are written plainly,
and others with a power of ten. Atom coordinates, occupancies and Biso are
always plain. The decimal points in a group line up, and the unit follows the
value. A number you can edit is tinted; a number you cannot is not.

Press a number to edit it. The editor opens over the number, so nothing else
moves. Enter keeps the value, and Escape drops it. A value typed back as it was
shown is no edit, so pressing into `4.1568(2)` and out again cannot truncate
the parameter. Below the editor, the value's limits can be set, and
`Restrain` adds a restraint toward a target with a σ. Press the word to tick
its box.

To edit several values at once, press them with `⌘` held (`Ctrl` off a Mac), or
press one and then another with Shift held to take every value between them in
the same column. Press any of the picked values and type: the value goes to all
of them.

The filter box narrows the panel. Type a word, or a glob such as
`phases.*.cell.*`. The `Free` and `Fix` buttons beside it act on that glob in
one `set_vary` call, which is one history node. The count beside the box says
how many rows the glob reaches.

Edits wait until `Apply`, or until a refine applies them first. The action bar
counts them.

```{image} ../screenshots/parameters-light.png
:class: only-light
:alt: The Parameters panel: a band for fluorapatite with its space group, the Scale row, the Cell group with its folded symmetry line, Size and strain, and the atom table with one row per atom
```

```{image} ../screenshots/parameters-dark.png
:class: only-dark
:alt: The Parameters panel: a band for fluorapatite with its space group, the Scale row, the Cell group with its folded symmetry line, Size and strain, and the atom table with one row per atom
```

## Interactive

Sliders for the values you would adjust by hand before a fit: the scale and
cell lengths of each phase, the zero shift and sample displacement, the axial
apertures, and the peak-width terms. Each parameter the table could free gets
one. A tied, locked or force-fixed parameter gets none, so under a hexagonal
cell `b` follows `a` and has no slider. Atom positions, occupancies, Biso, cell
angles and the background are left to the Parameters table.

Moving a slider changes nothing in the project. The graphs redraw at the new
values through `POST /api/preview`, and the title line says `Preview, not
refined` with the preview's Rwp beside the last fit's. The values wait in the
action bar like a Parameters edit. `Apply` writes them as one `set_values`
history node, `Apply and refine` writes them and runs, and `Revert` drops them.
When both tabs have edits waiting, the Parameters edits are applied first and
the sliders second, so a slider wins on a parameter both tabs touched. The
sliders also start from the head's values, so a typed Parameters edit is not
drawn in the preview until it is applied.

A drag asks the server for one preview at a time. While one is out, only the
newest position waits, so a fast drag never queues behind itself. On a pattern
past 150 000 channels the preview is drawn on the same thinned channels as the
pattern.

Each slider opens on a range set by the last fit:

| Parameter | Range | Track |
|---|---|---|
| a phase scale | half to double | logarithmic |
| a cell length | the change that moves the highest-angle peak by two peak widths | linear |
| the zero shift | two peak widths either way | linear |
| the sample displacement | 0.1 mm either way | linear |
| the axial apertures | 0 to three times the value, or to 0.05 | linear |
| a Gaussian width term (U, V, W, size, strain) | a quarter to four times | logarithmic |
| a Lorentzian width term (X, Y, size, strain) | half to double | logarithmic |

A Gaussian term is in squared degrees, so a quarter to four times its value is
half to double the peak width. A term at zero opens on a linear track one peak
width wide. Every range stops at the parameter's own bounds. Click the
parameter's name to set the range and the track yourself. A range you set is
kept when a fit moves the values, and `Default` gives the measured one back.

Click the number to type a value. `Enter` takes it and `Esc` leaves it. A value
outside the parameter's bounds is refused with the bound it crossed. Each number
keeps one format for its whole range, so the digits stay put while you drag. `↺`
puts one slider back at the last fit, and the tick on the track marks where that
is.

```{image} ../screenshots/interactive-light.png
:class: only-light
:alt: The Interactive tab, with sliders grouped under Instrument and the phase name, each showing its parameter name, its value and a track with the last fit marked
```

```{image} ../screenshots/interactive-dark.png
:class: only-dark
:alt: The Interactive tab, with sliders grouped under Instrument and the phase name, each showing its parameter name, its value and a track with the last fit marked
```

## Plan

The stage list, and what each stage will actually do.

The panel resolves the plan against the real parameter table and shows, per
stage, the paths its globs reach, which of them are newly freed, which are held
and why, and the running count of free parameters. That resolution is the real
verb and not a preview. It is the same call the fit makes, so the ties, the
locks and the mode's force-fixes shown are the ones you will get.

Under the last stage the panel names the closing stage every plan ends with.
It frees every stage's globs once more, on peak windows that drop 0.10% of
each peak, and its Rwp is the answer's. When a stage fixes a parameter that no
later stage frees again, the closing stage keeps it fixed and says how many it
keeps. The plan's `closing` line in the text document sets the fraction, and
`none` removes the stage.

The plan reads top to bottom, one stage to a row. Each row holds:

- a three-line handle. Drag it to move the stage, or focus it and press the up
  and down arrow keys.
- the stage's name, which you can type over.
- `Run this stage`, which runs that one stage from where you are and keeps what
  you freed by hand. It applies the pending edits first, as `Refine` does.
- `×`, which removes the stage. The last stage has none.
- the globs the stage frees, each with a `×` beside it, and a field where you
  type another glob and press Enter.
- the globs the stage fixes, in a `Fixes` row of the same shape. `+ Fix` at
  the end of the frees opens the row when the stage fixes nothing yet. The stage
  fixes them after it frees its own globs, so a stage that frees `phases.*`
  and fixes `phases.*.atoms.*.biso` frees all of the phase but its
  displacements. A parameter stays fixed until a later stage frees it again.
- the stage's line of the ladder: how many parameters it frees on top of the
  stages above, how many it fixes (`−N`), the running count of free ones, how
  many stay held, and the stage's Rwp from the last run. Open it for the paths.

The `Preset` menu replaces the stages with a preset's. `+ Stage` adds an empty
stage at the end and puts the cursor in its name.

An edit to the plan waits in the action bar as one pending edit. `Apply` stores
it, `Revert` drops it, and `Refine` stores it before running. To run the whole
plan, choose `Staged plan` in the action bar and press `Refine`. A plan
replaces the vary flags rather than continuing them, so a row you freed by hand
that no stage names is dropped. The panel lists those rows under the closing
stage.

The ladder describes the plan the server holds. After an edit, the stages
above the first change keep their lines, and every stage from that change down
reads `not applied` until you apply. `⌘Z` and `⇧⌘Z` undo and redo plan edits,
the preset menu included, while the cursor is outside a text field.

```{image} ../screenshots/plan-ladder-light.png
:class: only-light
:alt: The plan panel: a preset menu, then one row per stage with a drag handle, its name, the globs it frees and a line counting the parameters it frees and holds
```

```{image} ../screenshots/plan-ladder-dark.png
:class: only-dark
:alt: The plan panel: a preset menu, then one row per stage with a drag handle, its name, the globs it frees and a line counting the parameters it frees and holds
```

## Peaks

Two jobs: fitting individual lines, and finding a cell when you have no
structure.

### Picking lines

The plot becomes an editing surface while this tab is up, and prints its four
gestures across the top whenever it is:

| Gesture | Does | Typed route |
|---|---|---|
| click empty space | add a line | the panel's 2θ box |
| drag a marker | move it | the Text pane's `2theta` column |
| shift-click | exclude a line from indexing | the row's checkbox |
| right-click | remove it | the row's `×` |

Every pointer verb has a typed twin. A pointer is not available to everyone, and
a position typed to four decimals is not a position aimed at with a mouse.

A drag only moves a line when you are zoomed in far enough for the line to be
visible. The grab radius is the smaller of 10 px and 1.5 fitted peak widths, so
at a whole-pattern view a drag is always a zoom. Zoom first, then
correct. Before that radius existed, a drag starting near a marker could move a
line by degrees.

A line the fitter could not resolve is drawn differently rather than hidden, and
the flag on its row says why. That is the fitter explaining the shape of a
strong peak. A pasted position list carries the badge `σ assumed`, and its σ is a stated
assumption rather than a property of your data.

### Indexing

The `Search controls` disclosure is `ProjectDoc.indexing` as a form: which
engines and crystal systems to search, centrings, a preset, bounds and budgets,
and two editors for what you already know. Its vocabularies come from the
build's own capabilities, so a fourth engine would appear here with no new
control written.

Three things to understand before reading an answer:

- The default is a bounded search. `quick` puts a ceiling on the whole run and
  streams a graded shortlist per crystal system as each finishes, so the first
  click gives an answer in bounded time. A `low` grade from a run that hit its
  ceiling means unconfirmed rather than bad, and the full search is one rerun
  away.
- A list with no high-confidence entry is a result. The whole module is built so
  that "the data cannot distinguish these" is an answer it can give, and there is
  no setting that forces an answer.
- State what you already know. A prior cell or space group narrows the search
  honestly, where widening the tolerances does not.

Beside the volume limits, `formula` takes the specimen's chemical formula and
`temperature (K)` the temperature the pattern was measured at, and the project
stores both. The temperature box waits for a formula, since a temperature only
scales the formula's volumes. Emptying the formula box clears the temperature with it. A run with a formula adds a `Z` column to the
candidate table: the formula units each cell's volume holds by Hofmann's average
atomic volumes. Z moves no search and no rank. A correct inorganic cell reads
0.4 to 0.9 of its true Z, so read it as a guide rather than a test.

`Screen extinctions` lives in a candidate's expanded row: one row per extinction
class, every space group in the class listed, and the reflections that refute it
named. The teaching point is the package's own. The extinction symbol is what a
powder measures, and a single space group out of a class is a convention you
choose rather than a measurement the table made.

Above the candidate table the panel says what the search covered: the crystal
systems searched, the ones whose search did not finish, and every run-level
diagnostic with the systems it names. A run that stopped at its ceiling says
which systems it never reached, so a short list there is not evidence that no
cell exists in them.

`Adopt` turns a candidate into a Le Bail scaffold and flips the mode. Every row
has it. The candidate `best_or_none()` picks wears that name as a badge. Every
other row prints, under its grade, the sentence its adoption writes into the
history node's label: that it is not the gate's pick, its grade and its caveats.

## Model

The structure and the instrument, and a 3D view of the cell.

The split explains why some edits feel different. If the parameter table has the
path, the parameter table owns it: a lattice parameter, an occupancy, a Biso, a profile
term go through the parameter routes, where the tie and lock rules already live.
A species, a label, an atom added or removed, a geometry or a background family
go as a whole validated model, because each changes what the table contains.

Two consequences you will meet:

- Coordinates are not typed as x, y, z. A site refines along the directions its
  symmetry allows, so the editor offers those; a fully fixed special position
  gets no coordinate control at all. Typing a whole position is possible, and
  the site answers. An unreachable one is refused, naming the directions it does
  allow and the nearest position they reach. It is never snapped, because
  snapping would move the atom to a different site than the one you asked for.
- An edit empties the plot until the next run. The curves described values the
  model no longer holds, so they are discarded rather than left to mislead. The
  workflow is edit, run, compare, and an empty plot there is the design.

The instrument form is three groups, `Source`, `Geometry` and `Profile`, and
which group a field is in is a decision rather than its dot-path. The axial
apertures are drawn with the profile they shape, and the zero shift beside the
displacement it is refined against. U, V and W stand above X and Y. There is no
Z; GSAS and FullProf spell these letters differently, so match the physics
(size varies as 1/cos θ, strain as tan θ) and never the letter.

Changing a phase's space group shows a preview of what the change would
invalidate before it commits: incompatible values with their nearest allowed
ones, coordinates that would be dropped, and the consequences a table diff
cannot see, which are a setting change, an orbit collision, or the cell's atom
count doubling under a symbol with the same number of free parameters.

### The 3D view

A third column of this panel, on by default. The server computes the geometry,
and the browser draws it with rietx's own WebGL2 renderer, so every sphere,
ellipsoid and stick is exact at any zoom. Two modes: balls, and displacement
ellipsoids.
The projection is parallel and there is no axis box, so the cell's own a, b, c
edges are the frame of reference. Drag to rotate (a free trackball), shift-drag
or right-drag to pan, and scroll to zoom. The buttons view down a, b or c.
The line under the picture names the atom or bond under the pointer.

In ellipsoid mode each anisotropic site also shows its three principal
ellipses, the rings of an ORTEP drawing. An isotropic site shows none, because
its axes point nowhere in particular. Where a site displaces equally in two
directions, as on a threefold or higher axis, two of its rings could sit at any
angle round the third. One of them is drawn through the lattice vector nearest
their plane, and each symmetry copy of the site shows the copy of those rings.
Every machine draws the same picture.

Ball mode also draws coordination polyhedra: the shape the nearest anions make
around a cation, such as SiO₄ or AlF₆. Shells of four to six ligands are drawn
by default, which are the tetrahedra and octahedra of a framework. Larger
shells, such as NAC's CaF₈, start switched off. The row under the species
legend holds a `polyhedra` switch and one button per formula. A species with
two shapes, such as a CaO₆ site beside a CaO₈ one, has two buttons. A formula
whose ligands would take the picture past the 400 atoms the viewer draws keeps
its button, greyed out, and the note under the picture counts it. The switch
is held per mode, so polyhedra start on in ball mode and off in ellipsoid mode,
where the faces would cover the ellipsoids. A drawn polyhedron takes the place
of its centre's sticks. It also brings the ligands it needs outside the cell,
and they go when it is switched off. A centre outside the cell carries no
polyhedron, so it is drawn only while its site's polyhedra are off, as in
VESTA. Pointing at a face names the polyhedron,
its ligand count, its mean distance and its gap. When a second gap is nearly as
large and would close a shell of its own, the line names it too, as `next gap
×1.15 after 4`. Brunner and Schwarzenbach (1971) call two such gaps
approximately equal, and the shell drawn is then a choice the data barely
makes. The caption lists what is drawn and what is off.

A centre is a metal, or a non-metal bonded to a more electronegative one, as P
is in PO₄. A ligand is any other non-metal except hydrogen. A non-metal bonded
to a metal and to one more electronegative atom is a ligand too, as the C of a
cyanide or a carbonyl is. The ligands are searched out to three times the
nearest one's distance. An atom bonded to one of the centre's own ligands, and
lying behind it, is part of that ligand and is left out, as a cyanide's N is.
The shell ends at the largest jump in the sorted distances. It is drawn only
when that jump is at least 1.15 times, every ligand is a corner, and the centre
is inside. On 21 test phases, from spinel to gypsum, this draws the picture a
chemist would, and Prussian blue's C-bonded iron draws FeC₆. It does not cover
three cases:

- An intermetallic has no anions, so it draws no polyhedra.
- A split site draws none. That is a shell holding two partly occupied ligands
  closer to each other than to the centre.
- A split pair can still get a stick. Two non-metals closer than 0.7 times
  their radius sum are read as one atom over two positions: no stick joins
  them, and neither makes the other a cation. With a metal in the pair, the
  bound is 0.5, since uranyl's U=O sits at 0.67. Two partly occupied non-metals
  further apart lose their stick when they sit closer to each other than to an
  atom both are bonded to, as a disordered nitrate's O do round Na. A pair that
  meets no test keeps its stick, as Prussian blue's C and a vacancy's water O
  do, and Ag β-alumina's Ag and O4 do at 0.6 to 0.7 of their radius sum. A
  file's disorder groups settle those, where it has them.

A CIF that states disorder groups is drawn with every alternative, and the
viewer reads the groups. It draws no stick between two sites the file says are
never occupied together, and no polyhedron holding both.
`major alternative only`, under `drawing`, draws each assembly's most occupied
group alone, and the caption says how many sites it left out. A group with a
minus prefix is a site disordered about a special position: its symmetry
copies are its alternatives, and that button leaves them all drawn.

The rule can be overridden, as Mercury's central and ligand element lists
override its own. Under `drawing`, the `round` row holds one button per element
for the atoms a polyhedron is drawn round, and the `corners` row one per element
for the atoms at its corners. Both start as the rule picks them. Any element
may go in either row, so F round with Ca at the corners draws fluorite's
anion-centred FCa₄. Cs round with Cs and Cl at the corners finds CsCl's
14-atom environment, and its legend button starts off, as every shell of more
than six does. An intermetallic's environments are asked for the same way.
Double-clicking an atom draws that atom's environment alone: its shell
among every element, as Daams and Villars (1993) draw an atomic environment.
Double-clicking empty space ends it. `chemistry` goes back to the rule, and so does a change of phase. The
caption says when the lists are your own.

`PNG` renders the picture again, 3000 pixels on its long side, with the a, b, c
letters drawn in. That is a 17 cm figure at 300 dpi with room to crop.
`transparent PNG`, under `drawing`, leaves the background out.

`depth cue`, under `drawing`, fades each surface toward the background with
its distance, so the near layer stands out from the far one in a still
picture. A transparent PNG has no background to fade toward, so it is
exported without the cue, and the line under the plot says so.
`fill planar rings` fills each ring of five or six bonded atoms lying within
0.1 Å of one plane as a translucent grey face. Flat is all the fill says:
coordinates cannot tell an aromatic ring from any other flat one. The viewer
draws one cell, so a ring that a cell edge cuts stays open; a block drawn by
`render_structure` closes it. Both start off.

Two things here will mislead you if nobody says them:

- The bond threshold is a drawing threshold rather than chemistry. Bonds are
  drawn at a fraction of the sum of covalent radii, and no single value is right
  for both an ionic solid and an organic. LaB₆ at the default draws every La–B
  contact and looks like a cage; one turn of the slider down and the B₆
  octahedron appears. It sits behind the `drawing` disclosure, and a first-time
  user needs it. No stick joins a metal to a cation at any threshold, so
  forsterite's Mg is never joined to the Si of its SiO₄ neighbours.
- The ellipsoids are a diagnostic. Their axes are refined quantities, so a
  background flexible enough to imitate the peaks arrives here as balloons,
  while improving Rwp. A non-positive-definite tensor arrives as a flat disc,
  and the line under the picture gives the reason when you point at it. Six ordinary-looking numbers in the parameter
  table are obvious in the picture.

The probability selector scales the ellipsoids. The `× size` factor beside it is
a drawing multiplier and no ellipsoid stands above 100 %. A figure exported at a
multiplier other than 1 is not an ORTEP-quotable surface, and the caption prints
both numbers so it cannot be quoted as one by accident.

Element colours are chosen per phase rather than per element, so the same
element can be drawn in two colours in two phases. The familiar assignments
never move; the rest are separated against whatever else is in that phase.

## Text

The whole project as one text document: settings, plan, and every parameter row,
where `@` frees a parameter and a bare value holds it. It is the fastest way to
free thirty things at once, and the only panel where a rectangular selection
(`⌥`-drag) makes sense. The format aligns its columns for that reason.

The normative description of the format is in [](gui-power.md). Two facts about
using it belong here:

- There is no merge and no force-apply. If the project moved under your buffer,
  you re-read and re-apply. The reason is sharper than "merging is hard": your
  stale document also carries the old value of every row you did not touch, so
  applying it anyway would silently revert them.
- Comments do not survive a re-render, because a document regenerated from the
  project has one authority and storing your comments would make two.

## Series

The one panel whose subject is a method rather than a model. A series is N
separate refinements chained by a warm start, and its trajectory is N answers in
order. Reading it as one joint fit with a time axis through it is the mistake to
avoid.

It runs under this project's protocol: mode, plan, 2θ limits, excluded regions.
The panel states those rather than offering them, because one protocol over N
specimens is what makes their trajectories comparable.

Run it both ways once. `direction="both"` refines the chain forwards and
backwards and records how far the two passes differ. It is the only check that
separates a measured trajectory from an ordering artefact, and a smooth curve is
exactly what a poisoned chain produces. The panel opens with one line giving the
largest gap in esds (the two chains' esds combined) and the parameter and
pattern it sits at; click the parameter to plot it. Every trajectory is listed
with its own largest gap, in the series' own order, and the panel opens on the
first. The "largest gap first" control reorders the list. On a series whose two chains
agree, the gaps are noise and that order means nothing. The backward chain is
drawn beside the forward one. No parameter is
called path-dependent, because no gap size separates a real dependence from
chance across many parameters and patterns. You decide which size matters for
your specimen. Where the two chains kept different attempts at that pattern (one
warm, the other cold), the caption says so, and the gap then measures the
escalation ladder as well as the order. Then decide whether you need to keep
paying for the second pass.

The status column carries four chips, best learnt as two pairs. `restaged` and
`reseeded` are both recoveries, the first still from the neighbour's answer so
the chain is unbroken, the second only from a cold start. `hard` means nothing
rescued it but a warm attempt was still the best available, and `unrecovered`
means the chain kept a fit it rejected after its last attempt: the solver
diverged, or the fit carries an error-level diagnostic. A fit can converge and
still be rejected, so the chip can sit beside `converged`, and its tooltip names
the reason. A rejected pattern seeded no successor and joined no median.
On the trajectory plot a ring marks a reseed and a cross marks an `unrecovered`
point. They say opposite things: a ring is a good fit from a different starting
model, a cross is not a measurement.

The trajectory is drawn in the order the chain ran. A heat-then-cool series
therefore comes back along its own axis. Pointing at a point names its pattern,
its coordinate and its value, with the esd where the fit gave one. Clicking a
pattern's row plots that pattern's own fit instead. The chart has the pattern
plot's four export buttons, between its legend and the plot. On the trajectory,
`copy data` gives each pattern in view with its x, its value and its esd, and
the backward chain's value when there is one.

Under the plot, Steps lists the change in each parameter between neighbouring
patterns, later minus earlier, with its size in the later pattern's esds. It is
the series' `steps` field, largest first. It shows the selected parameter, or
every parameter with the switch beside it, capped at the largest 60 rows. No
step is called a jump, because what a jump is (a transition, a sample shift, a
beam dump, a wrong model) depends on the sample's history, which no pattern
records. When the series ran with `verify_steps`, a column gives the cold ratio
of the largest steps: the same two patterns refitted cold and independently,
over the step. Near 1 the step is in the data, and near 0 the chain made it.

### The trace

Above the plot, a strip draws the series on the experiment's own axis: the
series coordinate against the pattern index, one point per pattern, a failed
one included. Every mark is read from the series answer:

| mark | label | what it says |
|---|---|---|
| `SERIES_PATTERN_FAILED` | failed | every attempt raised: no fit, no point on any trajectory |
| `SEQUENTIAL_UNRECOVERED` | unrecovered | the fit diverged on every attempt |
| `SEQUENTIAL_RESEED` | reseeded | a good fit from the initial model, not from its neighbour |
| `findings` | findings | a bar as tall as the number of codes that pattern's fit raised |
| `largest_step` | largest step | where the parameter on show moved most, in its esds: a rank, never a verdict |

A series diagnostic marks a pattern when it names that pattern. One that names a
parameter or nothing, such as `SEQUENTIAL_PERSISTENT_FINDING`, stays in the banner
and the Fences list.

Drag along the strip to scrub. The plot below follows as that pattern's own fit
and keeps your zoom. The arrow keys step one pattern when the strip has focus.

A series does not persist. Its patterns are staged uploads and its answer lives
in the session, so closing the window loses the staged list. Say what you need
from it before you close it.

## Report

The `FitReport` rendered. [](../concepts/report.md) is what the statements mean; five things
about this panel will otherwise be misread.

Above the suggestions sits a "Fit diagnostics" section. It lists every diagnostic
the fit's result carries, errors first, then warnings, then notes, each under its
code and the parameters it names; an error opens in full, and every other row stays
folded to the purposes it is a warning under until you open it for its message and
suggestion. These are the package's own
findings about the answer (`BOUND_HIT`, `LEBAIL_ALTERNATION_STOPPED` and the rest),
and no other panel shows them.

- A suggestion with no Apply button is still a suggestion. Four of the action
  kinds are advice, and the note beside them is the deliverable. The
  background-flexibility pair is the case to watch: a more flexible background
  lowers Rwp while biasing displacement parameters up and scales down, so there
  is no honest one-click version.
- A greyed suggestion reading `vetoed:` is the engine agreeing with you and
  having already handled it. It looks like a refusal and is the opposite.
- "Could not rule out" is the headline. Where two explanations fit the misfit
  equally well, the report names both and caps its confidence rather than
  choosing. On the package's own test case, applying a zero-shift correction to
  a fit whose cell was wrong improved Rwp from 21.6 % to 9.3 % by putting the
  error in the wrong parameter, and the report had said so in advance.
- The predicted Δχ² is one number for the whole report and it is not a bound.
  The panel prints it once, and it cannot be used to rank the suggestions.
- Applying a suggestion runs one stage, so it takes the same path the Plan
  panel's per-stage Run takes and records one history node. Undo is a checkout,
  which throws the fitted curves away for the same reason an edit does.

## History

Every state the refinement has passed through, drawn as a graph. What this panel
changes is what you are free to try.

After a Le Bail run that alternated, each node carries a `pass k` chip. The chip
is green on the pass the fit kept, and the head stands in it. It is orange on the
other passes, whose nodes are drawn faint and stay in the tree. Select a node to
read the verdict in words.

The rail is lanes, and a lane is where the tree divided. There are no named
branches here and no moving refs. An edge runs down its lane and steps sideways
in one row. Only a second parent is dashed, so a dashed line means "this rival
strategy was folded in" and never "this is a merge". With more lanes than the
palette has hues a colour repeats, and that repeat is a collision you can see.

Select two nodes and the compare table reads `path · a · b · Δ · Δ %`, each side
at its own family's number of decimal places and the percentage taken against
`|a|`. Only the Rwp badge is coloured for direction: a parameter difference has
no good direction, and colouring one would be a claim.

```{image} ../screenshots/history-graph-light.png
:class: only-light
:alt: The history panel reading 13 nodes and 2 lanes, with a second coloured lane branching from the cell node, and a compare table of two nodes below it
```

```{image} ../screenshots/history-graph-dark.png
:class: only-dark
:alt: The history panel reading 13 nodes and 2 lanes, with a second coloured lane branching from the cell node, and a compare table of two nodes below it
```

The picture above is the state this section is about: the plan was run, then run
again from the `cell` node with a different strategy, and the two lineages sit
side by side with a comparison of one node against the other underneath.

### When to branch

A Rietveld refinement is a sequence of decisions that are hard to unmake. Free
the wrong thing early and the fit slides into a minimum that looks fine and is
wrong, and by the time the difference curve says so you have made ten more
decisions on top of it.

Branching turns that into an experiment you can run twice:

- Before a decision you are not sure of, branch, try it, and compare against the
  state you left. Freeing anisotropic displacement parameters, adopting a
  candidate cell and turning on preferred orientation are all that kind of
  decision. The comparison is the point: a correction that improves Rwp while
  moving a cell by 1000 ppm has told you something, and you can only see it
  beside the other answer.
- When two explanations both fit, run both. The report will already have told
  you it could not separate them; a branch each is how you find out whether they
  disagree about anything you care about.
- Before anything irreversible in the model, such as a space-group change or a
  replaced structure, because a checkout restores the parameter count and not
  only the values.

Checkout, tag and annotate are all here, and every one of them is a node. The
history is append-only, so exploring it cannot lose anything.

## Build

What this build of the package can do, rendered from its own capabilities:
backends and whether each optional dependency actually imports here, solvers,
plans, modes, anodes and the pattern formats that can be opened. It is derived,
so it cannot claim a feature the installed package does not have.

It also lists the panels the GUI plan still owes, which is currently none.
