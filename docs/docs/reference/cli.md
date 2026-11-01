# The command line

The `rietx` command has seven subcommands: one finds the unit cell of a pattern, one starts the GUI, one installs the agent skill, and four show runs and results the Python API produced.

```console
$ rietx --help
usage: rietx <command> [...]

commands:
  gui [PROJECT.rex] [--scratch] [--port N] [--no-open]
                                    the refinement GUI (localhost)
  watch [dir] [--port N] [--open] [--read-only]
                                    list and watch the runs under a directory
  events <events.jsonl | run dir> [--json]
                                    summarise an event log, run by run
  html <result.json> <out.html>     render a saved RefinementResult to HTML
  index <pattern> --wavelength A [...]
                                    determine the unit cell of an unknown
                                    phase (rietx index --help)
  compare [--data DIR] [--port N] [--open]
                                    browser UI comparing refinement
                                    settings on the bundled standards
  skill [--path | --print [SECTION] | --install [DIR]]
                                    the agent skill: where it is, its
                                    text, or install it into a repo
                                    (rietx skill --help)
```

An unknown command exits 2.
No subcommand refines a structure.
A refinement is a sequence of decisions about a model, and it runs from the Python API ([a first fit in Python](../start/first-fit.md)) or the GUI.

## `rietx index`

`rietx index` finds candidate unit cells for an unknown phase.
It is the only subcommand that computes an answer.

```console
$ rietx index corundum.prn --wavelength 1.540596 --systems trigonal --total-budget 45
```

It prints the candidate list and never one cell, because `IndexingResult` has no `.cell`.
Each candidate carries a confidence grade and the caveats holding that grade down.
The last block is the run's diagnostics, where a truncated search says so.
[Diagnostic codes: indexing](diagnostics-indexing.md) explains each code.

| Option | Meaning |
|---|---|
| `pattern` | the pattern file; any format `read_pattern` opens |
| `--wavelength` | required, in Å, and a single line. For a lab Kα doublet, build the instrument in Python and call `index_pattern`. Peak picking recognises each line's Kα2 alias, and a one-line source cannot |
| `--geometry`, `--radius` | `debye_scherrer` (default), `bragg_brentano` (which needs the goniometer radius in mm) or `flat_plate_transmission` |
| `--systems` | comma-separated crystal systems; the default is all seven. A restricted search reports what it did not cover and concludes nothing about it |
| `--engines` | comma-separated engines; the default is all of them. `high` confidence means every engine that ran agreed |
| `--max-d`, `--min-d` | the longest and shortest principal d-spacing of the search domain, in Å (defaults 25 and 2). The domain size sets the cost of an exhaustive search |
| `--budget` | wall-clock seconds per (engine × crystal system) slice of the search (default 30) |
| `--total-budget` | wall-clock ceiling for the whole run, search, probe and validation together. It overrides the preset's ceiling, and `INDEX_BUDGET_EXHAUSTED` names the systems it cut short |
| `--preset` | `quick` (the default: every engine and system under a whole-run ceiling, truncation reported) or `full` (no ceiling) |
| `--ceiling` | print the cost arithmetic for these options and exit without searching |
| `--shift-allowance` | a measured systematic 2θ shift in degrees. Without one the engines assume 0.05° and cap every candidate's confidence, because a cell found inside a widened window absorbs the shift |
| `--formula` | the specimen's chemical formula, with `·` before a hydrate. Each candidate records the formula units its volume holds (`formula_units`); the search is not narrowed and nothing is judged |
| `--temperature` | the pattern's temperature in K for `--formula`'s volumes, 298 by default. Given without `--formula` it is refused, since it would change nothing |
| `--no-validate` | skip the whole-profile validation fit, which caps every candidate at `medium` |
| `--json FILE` | also write the whole `IndexingResult` as JSON |

A formula the parser cannot read, or a temperature that is not a positive finite number of kelvin, is refused before the pattern is read, as a usage error with exit code 2.
Anything the pattern reader repaired or assumed goes to stderr before the answer.
A reversed scan or a dropped duplicate changes every number under it.

### The cost ceiling

`--ceiling` prints what a run may cost, from the options alone, and exits 0:

```console
$ rietx index corundum.prn --wavelength 1.540596 --ceiling
worst case: 1518 s   (search 630 + probe 360, arithmetic on the per-system budgets; + validation 12 fits x 0.6-44 s, a measured range — the fit's cost is data-dependent)
measured typical: 4-440 s per real dataset (searches finish their systems early far more often than not)
a --total-budget binds within ~10 s (the longest uninterruptible stretch)
```

The worst case is what the budgets permit, and a real dataset usually costs far less.
Restricting `--systems` to where the answer can be shortens a run more than raising a budget does.

### Exit status

`rietx index` exits 0 when one candidate reached `high` confidence with no ambiguity partner.
It exits 1 when the result abstains.
The diagnostics say the same thing, and the exit status is the form a shell script can branch on.

This run on the SRM 676a corundum scan took the 45 s it was given (2026-10-20, an Apple-silicon Mac):

```console
$ rietx index corundum.prn --wavelength 1.540596 --systems trigonal --total-budget 45
engines: dichotomy, svd, trial_error   systems: trigonal   lines: 63   validated: yes

 1. [ low  ] trigonal R   4.75966 4.75966 12.99261 Å  90.000 90.000 120.000°   V = 254.91 Å³
      found by dichotomy, svd;  indexed 43/63 lines;  chi2_red 0.94;  Le Bail Rwp 0.3561, 15 of 85 reflections absent
      not higher because: engines_disagree, fom_panel_disagrees, predicted_but_absent, indexed_fraction_low, shift_allowance_assumed
...
NO CELL: the result abstains — see the diagnostics below.
...
  warning[INDEX_ABSTAINED]: No cell reached the confidence gate. The best candidate (trigonal R, V = 254.9 Å³) has low confidence because of: engines_disagree, fom_panel_disagrees, predicted_but_absent, ...
...
$ echo $?
1
```

The corundum cell is candidate 1, and the command still exits 1, because five caveats stand between it and the gate.
Exit 0 claims that one candidate reached `high`.
It does not mean that something was printed.
The list and the ranking depend on the wall clock a run is given, so a second run can differ.

## `rietx watch`

`rietx watch` serves a page listing the recorded refinement runs under a directory, with the selected run's plot and event log.
[How to watch or stop a running fit](../guides/watch.md) is the task; this section is what the page shows.

| Option | Meaning |
|---|---|
| `directory` | the directory to scan; default the working directory. A directory that is itself a run opens straight onto it |
| `--port N` | the port to serve on (default 8899) |
| `--open` | open a browser |
| `--read-only` | serve the page with no stop button and no GUI launch; both routes refuse with 403 |

```console
$ rietx watch --read-only
rietx watch: 2 run(s) under /Users/yue/work/demo
             http://127.0.0.1:8899/  (Ctrl-C to stop)
             read-only: no stop button, no GUI launch
```

### Where the runs come from

Every fit records a run directory unless recording is switched off.
A fit that came from a project records into that project's `live/` directory.
Every other fit records under `.rietx/runs/` in its working directory.
A run is any directory holding an `events.jsonl`, so a project's `live/` and a directory passed to a `LiveSession` count too.

```console
$ rietx watch ./my_sample.rex/live
```

### The run list

The list is one panel and the selected run is the other.
With no run in the URL the page follows the newest run, so opening it beside an agent's job shows what is happening now.
Selecting a run pins it.

The list has seven columns:

| Column | Shows |
|---|---|
| `state` | the run's state (the next table) |
| `run` | for a series member the pattern it fitted, otherwise the label |
| `stage` | the stage the run last recorded |
| `Rwp`, `GoF` | the fit at that stage, Rwp as a percentage |
| `started` | a clock time to the second for a run started today, a date before that |
| (button) | `open`, for a run inside a `.rex` project |

The label is the `label=` the fit was given.
Without one it is the project's name or the directory the fit was launched from.
An unnamed batch launched from one directory gives every run the same label, so the start time tells its rows apart.
Hovering a row shows the label, the run directory, the command line that launched it, and where that was run.

| State | Means |
|---|---|
| `running` | a process holds the run's lock |
| `done`, `failed`, `cancelled` | the writer recorded its own last state |
| `abandoned` | the status says `running` and the lock is free |
| `unknown` | this machine cannot answer |

The lock is held by the writing process for its whole life, and the kernel releases it however that process dies, `kill -9` included.
`abandoned` is what a killed process leaves behind.
It is drawn in the same neutral colour as `unknown`, because in both states nothing recorded how the run ended.

`unknown` arises three ways.
The run was written on another host, so its process id means nothing on this machine.
The lock is free and no state was recorded, as in every run written before the recorder existed.
Or there is no lock file to probe.
A heartbeat age is reported beside the state and never decides it.

### The run panel

The run panel carries a status line, the plot and the event console.

The plot redraws in place as the fit writes each stage.
Its 2θ and intensity axes follow the pattern, so a zoom survives a stage.
The Δ/σ axis is symmetric and steps between fixed limits (±3, ±5, ±10, ±20 and wider) as the residual tightens.
The shaded band on the Δ/σ panel runs from −3 to +3.

The plot takes the GUI's gestures.
Drag to zoom, or scroll to zoom about the pointer.
Shift-scroll or Alt-drag pans, and a double-click shows the whole pattern again.
Clicking a legend entry hides that curve until you click it again, and it stays hidden when a stage lands.
Pointing at a tick names the reflection, as `2 1 1` with its angle; a run recorded before 1.5 has positions only.
The `export` menu holds the four exports of [the GUI's plot](gui-guide.md): a PNG, an SVG, the picture on the clipboard, and the channels in view as tab-separated columns.

Opening a run puts you at the newest line of its log.
The console reads the end of the file and says that earlier lines are above, without counting them.
It keeps the newest 2 000 lines, and it follows the log only while you are at the end.
For a series the status line names the pattern being fitted, its pass and its stage.

The status line drops whole slots when the panel is narrow.
The GUI command and the free-parameter count go first, then the label, then the series.
The state, Rwp and GoF always stay, and the stage shortens.

### Layout

Two seams divide the page, one between the list and the run panel and one between the plot and the console.
Drag a seam to size the panel beside it.
Double-click it, or focus it and press Enter, to collapse that panel, and repeat to bring it back.
A focused seam takes the arrow keys, 16 px a press and ten times that with Shift, with Home and End for its two stops.
The browser remembers both sizes and re-fits them to the window you next open in.

A seam stops where the panel stops being readable.
The list keeps 71 characters, the width its six fixed columns need plus room for the run column's heading.
The run panel keeps 340 px, where the plot's legend already takes three rows.
`full list`, beside the title, hides the run panel and gives the list the window.

Below 859 px the list and the run panel stack, and the seam between them turns horizontal.
That is the width at which the list's floor and the plot's floor stop fitting side by side.
The seam remembers a width and a height separately.
Narrower still, the list drops the stage and the start time.

The page draws in the GUI's colours, from the same tokens, so a fit open in both looks the same.
The theme is one setting for the whole of rietx, `ui.theme` in `~/.rietx/settings.json` (`$RIETX_STATE_DIR` moves the directory).
The three buttons in the title bar write it: follow the system, light, or dark.
An open watch page picks up a change on its next poll, every 1.2 s, and an open GUI when it is reloaded.

### Stopping a fit

A `running` run has a stop button, which takes two clicks and has no keyboard shortcut.
The fit stops at its next residual evaluation, and its process raises `RefinementCancelled`.
The latency is one poll plus the evaluation in flight: on a 150-stage synthetic fit the process exited 0.12 s after the request was written.

The finished stages are kept, and the working state stands at the last of them.
The stage in flight records no history node, commits no parameters, and puts the structure and instrument back where that stage found them.
A cancelled run gets no `summary.txt`.

Only a run being written on this machine can be stopped.
A finished run, a run on another host, and a run whose writer holds no lock each refuse with 409.

Afterwards the run reads `cancelled`, and its `status.json` carries `cancelled_by`.
A fit its own code stopped through a `CancelToken` records the same state with no `cancelled_by`.
That field is the only place the two differ.

### Opening a copy in the GUI

Every run inside a `.rex` project has an `open` button.
It starts `rietx gui --scratch` on a copy of the project and opens it in a new tab.

The copy holds the model, the parameters and the history as they stood at the click, and never gains the next stage.
It gives you what the watcher has no room for: the parameter table, the report, the 3D structure, and branching a strategy from the fit's head.
The watcher stays the live view.

A project cannot be opened read-only, because `Project.open` appends an annotation before you click anything.
Opening the live project would put a second writer on the `history.jsonl` the fit is growing.
So the button copies the project first, and everything you then do lands in the copy.
The copy is a temporary directory, and nothing removes it.

The status strip of a run with a project carries the same command, for typing:

```console
rietx gui --scratch campaign/sample.rex
```

A run recorded by a bare `fit()` has no project to copy.
Its row offers no button, and the route answers 409.

### Routes

These routes carry everything the page shows, and any of them can be read directly:

| Route | Returns |
|---|---|
| `/api/runs` | every run under the scanned root, with its state |
| `/api/run/<id>` | one run's row |
| `/api/run/<id>/events?offset=&limit=&end=` | events from a byte offset, with the next offset. `limit` keeps the newest that many and counts the rest in `skipped`; `end=1` starts from the end of the file |
| `/api/run/<id>/snapshot` | the stage's curves, ticks and statistics as JSON |
| `/api/run/<id>/legacy` | a `fit.html` written before 1.4, as it stands |
| `POST /api/run/<id>/cancel` | asks that run to stop; 403 under `--read-only` |
| `POST /api/run/<id>/gui` | opens a copy of that run's project in the GUI; 403 under `--read-only` |
| `POST /api/theme` | stores the theme; allowed under `--read-only` |
| `/tokens.css` | the colour tokens the GUI is drawn from |
| `/rxplot.mjs`, `/uPlot.iife.min.js`, `/uPlot.min.css` | the chart library, served from the installed package so the page works offline |

They are provisional by declaration, like the GUI's ({ref}`provisional-by-declaration`).
A route may be added, renamed or split in any release.

The three `POST` routes check `Origin` and `Referer`, as the GUI's writing routes do.
Without that check any page open in another tab could stop a refinement.
`curl` sends neither header, so `curl -X POST` against `127.0.0.1` works.

The watcher never opens a project and never builds a refinement, so starting or stopping it does not touch a running fit.
The stop writes a request file into the run directory, and the fit's own cancel token acts on it.

## `rietx events`

`rietx events` summarises an event log in a terminal, one block per run.
It takes an `events.jsonl`, or a run directory holding one.
For each run it prints fits and stages started and ended, residual evaluations, the first and last Rwp, wall clock per stage, how often each termination criterion ended a solve, and the paths held because the data could not see them.

```console
$ rietx events run/events.jsonl
run/events.jsonl: 2 runs
run 1  header 4744861730ca  opened 2026-10-20 00:27:58   wall 0.12 s
  fits 1 (1 ended, 0.12 s fit_start→fit_end)   stages 5 ended (5 started)   evals 35
  Rwp first 0.9517   last 0.0414
  stage            n    seconds   evals
  scale_bkg        1       0.01       1
  zero             1       0.01      12
  cell             1       0.01      10
  profile_w        1       0.01       9
  profile          1       0.01       3
  termination: exhausted_fp64 3, ftol_runs 2
  most held: phases.1.cell.a (3)
run 2  header e1df7262acfc  opened 2026-10-20 00:27:58   wall 0.12 s
  ...
```

That log holds two runs of one synthetic two-phase fit given the same `events=` path, with the second phase absent from the data.
`phases.1.cell.a` was held in three stages because the data cannot see that phase.

`--json` prints the same summary as JSON.
`rietx.history.aggregate.summarize_events` returns it in Python.
A log that does not exist exits 2.

A log is opened for appending, so a second fit with the same `events=` path adds a second run to the file.
Since version 3 of the event schema each stream writes one header line when it opens the file, and `rietx events` splits the runs there.
The id after `header` is that header's own, fresh for each stream.
It is not the id `rietx watch` lists a run under, which comes from the run directory's path.
A log written before version 3 has no header and reads as one run, printed as `header: none`.
The split assumes one writer at a time: if two processes append to one path at once, every line after the second header counts in the second run.

A stage's seconds run from its first `stage_start` to its `stage_end`, so a stage that releases a held phase and solves again is one span.
A fit's cost is `fit_start` to `fit_end`.
The stage spans do not add up to it, because a stage report or a recompile between stages is outside every span.

A line that is not JSON is counted and skipped.
The half line a running writer has not finished is left alone, so a running job can be summarised.

## `rietx html`

`rietx html` writes a saved `RefinementResult` as a standalone HTML page.
It takes exactly two arguments, and anything else exits 2.

```console
$ rietx html result.json fit.html
wrote fit.html
```

A `RefinementResult` round-trips through JSON, so this renders a fit that ran elsewhere: on a cluster, in CI, or in a closed notebook.
The page is the GUI's pattern plot, with the chart library and the curves inside the file, so it opens from disk with no network.
The NAC example's page is 1.36 MB.
It takes the GUI's gestures, and its header holds the four exports of [the GUI's plot](gui-guide.md).
Past 150 000 channels the file carries a min/max sample of the curves, as the GUI does.

`rietx.viz.html.write_html` writes the same page from Python.
Its `weighted=True` draws Δ/σ with its ±3σ band in place of the raw difference.

## `rietx compare`

`rietx compare` serves a page that refines a bundled standard under several settings and draws where along 2θ each setting changed the fit.

| Option | Meaning |
|---|---|
| `--data DIR` | the directory holding the standards; default a checkout's `tests/data` |
| `--port N` | the port to serve on (default 8730) |
| `--open` | open a browser |

```console
$ rietx compare --open
rietx compare — http://127.0.0.1:8730
  data: /path/to/checkout/tests/data
  standards available: srm660c, corundum, zincite, fluorite, brucite, fap, nac, lab6_capillary
```

The standards are test data, not package data, so the page needs a checkout.
Started without them it says so and lists nothing:

```console
  standards available: (none found)
  hint: pass --data <dir> pointing at a checkout's tests/data
```

Pick a standard, tick the variants, and read the cumulative Δχ² against the reference variant.
A change in Rwp cannot settle whether a correction helped.
Some corrections cannot move Rwp at all: capillary absorption is an exact reparameterisation of the scale and the displacement parameters.
Others improve Rwp by absorbing an error that belongs to another parameter.
The cumulative Δχ² shows where along 2θ the change acted, which tells those cases apart.

The three panes share one 2θ axis and take the GUI's gestures.
The variant list is the legend, and clearing a variant's box hides it in every pane.
The line above the panes reads each variant's value at the pointer, and names the reflection over the tick band.
The Export section saves or copies the panes as the GUI's plot does.
Its `copy data` gives `two_theta` and `y_obs`, then each shown variant's `y_calc`, Δ/σ and Δχ² over the channels in view.

The chrome takes the GUI's colours through `/tokens.css`, and the theme is read when the page is served, so a change reaches it on a reload.
The variant curves keep ten colours of their own, since the GUI has no categorical set that large.

The same computation runs without the page:

<!-- api-doc: no-exec — each call runs a full refinement of a bundled standard -->
```python
from rietx.viz import compare

record = compare.run("srm660c", "roughness_suortti")
```

`compare.STANDARDS` and `compare.VARIANTS` are the registries, each entry with a title and a description of what it shows.

## `rietx gui`

`rietx gui` serves the refinement GUI on `127.0.0.1:8731` and opens a browser.
[The GUI: a first fit](../start/gui-quickstart.md) is a tutorial, [the GUI panel by panel](gui-guide.md) covers the panels, and [the GUI as a text document and a wire](gui-power.md) covers the document, the keyboard and the routes.

```console
$ rietx gui my_sample.rex
```

The project argument is optional.
Without one the GUI starts empty, and you open or create a project from inside it.
A project that will not open exits 2 and prints the reason.

| Option | Meaning |
|---|---|
| `project` | a `.rex` project directory to open |
| `--port N` | the port to serve on (default 8731) |
| `--no-open` | do not open a browser |
| `--scratch` | open a copy of the project in a temporary directory; the project you named is never written to |
| `--state-dir PATH` | keep the recent list and the theme here; default `$RIETX_STATE_DIR`, else `~/.rietx` |
| `--machine` | print one JSON boot line (`url`, `port`, `project`, `pid`, `scratch_of`) and nothing else, for a supervising process |
| `--backend`, `--solver` | the Jacobian backend and the least-squares driver, by the names `capabilities()` reports |

Every GUI action writes to the project as you click it, and opening a project appends a line to its log.
`--scratch` opens a project without changing it:

```console
$ rietx gui my_sample.rex --scratch
rietx gui — http://127.0.0.1:8731/
  project: /var/folders/8r/qnc8y_5j.../T/rietx-scratch-xe9arpn1/my_sample.rex
  scratch copy — my_sample.rex is not written to
  Ctrl-C to stop
```

The copy is byte for byte, so it opens exactly as the original does, and nothing deletes it.
`rietx watch`'s `open` button runs this with `--no-open` and `--machine`, and reads the port from the boot line.
A project under a running fit is safe to open only this way.

The GUI needs nothing beyond a base install, because its built front end ships inside the package.
The `gui` extra is empty and kept for old install lines.

## `rietx skill`

`rietx skill` finds, prints or installs the agent skill.
`--path` prints where it is, `--print` prints it as text, and `--install` puts it in `.agents/skills/` with a link from each harness that reads somewhere else.
[For agents](agents.md) covers the options and the harnesses.

There is no `rietx[claude]` or `rietx[codex]` extra.
A pip extra can only add a dependency, and installing a skill means writing files into your project.
