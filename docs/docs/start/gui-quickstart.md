# The GUI: a first fit

This tutorial takes you in the GUI from an empty screen to a fit you have read.

`rietx gui` is a browser front end to the package.
It runs a small HTTP server on your own machine, serves one page to a browser,
and calls the same `Refinement` methods a script would. Nothing about a project
is private to it: a project the GUI made opens in Python, and a fit run from a
script shows up in the GUI's history.

[](../reference/gui-guide.md) then goes panel by panel, and
[](../reference/gui-power.md) is the text document, the keyboard and the wire.

## Install and start

The GUI needs nothing beyond rietx itself. Its front end is committed inside
the package, so installing it never needs node.

```console
$ pip install rietx
$ rietx gui
rietx gui — http://127.0.0.1:8731/
  no project — open or create one in the app
  Ctrl-C to stop
```

A browser opens on that address. `--no-open` suppresses that, `--port` moves it,
and `rietx gui my_sample.rex` starts with a project already open.
`rietx gui --help` lists every option.

Everything you do writes to the project as you do it. There is no unsaved state
and no "are you sure?" on close, because each verb persists as it runs. That
also means there is no read-only way to look at a project: opening one appends a
line to its log before you have done anything. To look without changing, use
`rietx gui my_sample.rex --scratch`, which works on a byte-for-byte copy in a
temporary directory.

## Start with an example

`rietx gui` with no project named reopens the project you had open last, unless
you closed it from the File menu. Otherwise it shows the start screen. On the left are `New project…`, `Open…`, and
links to this manual and its tutorials. On the right are the projects you opened
recently and the example projects shipped inside the package. A first run has no
recent list, so it shows the examples alone. Start from an example if you have
no data of your own.

Each row opens with one click. Its `⋯` button, or a right-click, offers the
rest: `Remove from list` on a recent project, and `Open a fresh copy` on an
example you have opened before. A project that has moved since you last opened
it stays on the list as `Not found`, with `Locate…` to find it again.

The package ships {{ N_EXAMPLES }} of them. Each is a real specimen with a
published reference value, and each carries the refinement protocol its
acceptance suite measures, so a fit of one is comparable with a number somebody
else recorded. Opening one makes your own copy, so anything you change stays
yours. `Open a fresh copy` throws that copy away and builds it again.

Open the fluorapatite example. It is an ordinary laboratory pattern from an
ordinary diffractometer, with seven atomic sites. That is the point at which a
refinement starts to need a plan rather than a button.

```{image} ../screenshots/empty-state-light.png
:class: only-light
:alt: The start screen: the wordmark, New project, Open and the two links on the left, and the shipped example projects with their descriptions on the right
```

```{image} ../screenshots/empty-state-dark.png
:class: only-dark
:alt: The start screen: the wordmark, New project, Open and the two links on the left, and the shipped example projects with their descriptions on the right
```

## What is on the screen

The window is two columns. On the left is the pattern; on the right is a column
of ten tabs, all mounted at once:

| Tab | Is |
|---|---|
| `Parameters` | every parameter, with the one control that frees it |
| `Interactive` | sliders that move a parameter and show the pattern before you apply it |
| `Plan` | the stages the fit will run, and what each one frees |
| `Peaks` | picked lines, and indexing a pattern that has no structure yet |
| `Model` | the structure and the instrument, and a 3D view of the cell |
| `Text` | the whole project as one editable text document |
| `Series` | many patterns refined as a chain |
| `Report` | what the package will say about the last fit |
| `History` | every state the refinement has passed through |
| `Build` | what this build of the package can do |

On a project's first open a `Getting started` strip sits above the tabs. It is
four steps, and it is neither a wizard nor modal. You can ignore it, work around
it, and dismiss it whenever you like. Every step except the last is derived from
the project rather than remembered, so it cannot disagree with what you have
actually done: undo a fit and `Run the fit` un-ticks itself.

```{image} ../screenshots/first-run-light.png
:class: only-light
:alt: A Getting started strip above the tab strip with four steps, two ticked, and a Dismiss button
```

```{image} ../screenshots/first-run-dark.png
:class: only-dark
:alt: A Getting started strip above the tab strip with four steps, two ticked, and a Dismiss button
```

Dismissing it is remembered for that project, and nothing else about it is
written.

```{image} ../screenshots/first-fit-light.png
:class: only-light
:alt: The whole window after a run: the fitted pattern with its difference curve on the left, the parameter table on the right, the console below
```

```{image} ../screenshots/first-fit-dark.png
:class: only-dark
:alt: The whole window after a run: the fitted pattern with its difference curve on the left, the parameter table on the right, the console below
```

Each side has a collapse button at its own end of the header. The left one
hides the graphs and the right one hides the panel column. One side always
stays, and the buttons never move. In a window narrower than 760 px the two
sides stack, graphs above and panels below.

The header also carries the project's name and pattern, `Simple | Advanced` and
a three-way theme control (`◐` follow the system, `☀` light, `☾` dark). Over the
pattern, the `Pattern` tab and a title line say what the graph shows. Once a fit
has run, `Rwp` and `GoF` sit on that line.

## Run the fit

Under the panel column is the action bar. Press its `Refine` button, or `⌘⏎`
(`Ctrl+Enter` off a Mac), or the `r` key. With `Staged plan` chosen beside it,
a refine runs the project's plan.

The run pill in the header names the stage and counts them off. Underneath the
tab column, the console prints each stage as it starts and finishes, and beside
each one the Python call that would have done the same thing. That echo is the
on-ramp described in [](../reference/gui-power.md). You can always find out what a button you
pressed actually did.

When it stops, `Rwp` appears on the title line over the pattern. Lower is better. What counts as good
depends on the data, and [Agreement statistics](../theory/estimation.md#agreement-statistics)
defines Rwp beside the expected value it is judged against.

:::{admonition} A hopeless fit says so
:class: note
Past an Rwp of {{ MATURITY_MAX_RWP }} the header shows `⚠ not a fit yet` beside
the number, and the run's own status pill may still read `converged`. Both are true: the
optimiser stopped moving, and the model is not yet describing the data. Believe
the warning, and go to the Report.
:::

## Read what happened

Look at the plot first. Three curves are drawn over the measured points: the
calculated pattern, the background, and underneath them the difference.
Structure in the difference curve is the model failing to explain something, and
where it sits is the diagnosis. A difference that swings under one peak is a
shape or a position problem; one that follows the whole pattern is a scale or a
background problem.

Two knobs under the plot change what you can see:

- The `residual` selector switches the lower panel between `Δ/σ`, `Δ` and `Σχ²`.
  `Σχ²` accumulates the misfit from left to right, so a flat stretch contributed
  nothing and a step is exactly where the fit is bad. It locates the worst misfit
  better than any single number does.
- The intensity scale (`lin`, `√`, `log`) redraws the same numbers. `√` makes
  weak peaks visible without pretending they are strong.

Then open the `Report` tab. It states what the package is prepared to say about
this fit, and it is built to refuse a confident wrong answer: where two
explanations fit the misfit equally well it says so and names both, instead of
picking one. [](../concepts/report.md) is the full account of what those
statements mean.

```{image} ../screenshots/report-light.png
:class: only-light
:alt: The report panel: Rwp and GoF, a paragraph naming an exchangeable pair of parameters, and suggested actions with one carrying a could-not-rule-out line
```

```{image} ../screenshots/report-dark.png
:class: only-dark
:alt: The report panel: Rwp and GoF, a paragraph naming an exchangeable pair of parameters, and suggested actions with one carrying a could-not-rule-out line
```

The screenshot above is the fluorapatite example after the run this page
describes. The report has found a real degeneracy in it: a specimen displacement
that "stands 39σ from 0 but is exchangeable with the held zero shift". It says
the fit cannot tell which is physical. That is the package declining to give you
a confident wrong number.

## Then your own data

`New project…` on the start screen opens one dialog of four rows:

1. `Pattern`. Choose a data file. The row names the reader that claimed it, the
   point count, the 2θ range and step, and where the esds come from, and draws
   the pattern small. A multi-scan vendor file grows a scan picker here and a
   two-column text file does not. `How the file was read` holds the reader's
   options and its diagnostics: this is where you find out that a scan was
   stored backwards, or that an attenuator factor has been applied to the
   counts.
2. `Phases`. `Add phase` takes a CIF or a typed space group and cell, as many as
   the specimen holds. The typed form offers only the cell parameters the
   symmetry leaves free, so a `b` under a tetragonal symbol is not a value you
   can get wrong. With no phase the project starts from the pattern alone,
   which is the right start when the cell is what you are looking for. See
   [Peaks](../reference/gui-guide.md#peaks) in the panel guide.
3. `Instrument`. One line says the geometry and the source, and a tag says where
   that came from: the data file's header, a saved instrument profile, or
   `assumed`. `Change…` opens the form.
4. `Project`. The name and the folder the `.rex` directory goes in. Both follow
   the data file until you type in them.

The dialog asks for no intensity mode and no plan. A typed cell has no atoms,
so a project with one is Le Bail and every other project is Rietveld. The plan
is the default until you open the Plan tab. Nothing is written until you press
`Create project`, and the sentence beside the button says what is still missing.

:::{admonition} Check an assumed anode
:class: warning
Where the file's header names no anode, the dialog assumes Bragg-Brentano with a
Cu Kα1/Kα2 anode and tags the line `assumed`. A wrong wavelength ends up in
every cell parameter you go on to refine, and it is invisible in Rwp. The fit is
as good as ever and the numbers are wrong.
[The wavelength–cell degeneracy](../theory/peak-positions.md#the-wavelengthcell-degeneracy)
has it in full.
:::

## Where to go next

- [](../reference/gui-guide.md): the ten panels, and when to branch the history.
- [](../reference/gui-power.md): the `.rxt` text document, the keyboard, and the routes.
- [](tutorials.md): the same fluorapatite pattern fitted in Python, one step a notebook cell.
- [](../guides/index.md): one task a page, each done from a Python script.
- [](../concepts/fit.md): what the stages of a plan are actually doing.
