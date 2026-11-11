# WP-2214 — the GUI rebuild: its plan, and a home for every feature of today's GUI

Milestone: gui-overhaul · Status: ✅ 2026-11-11 — the inventory and the plan written, the five questions ruled, R1 filed as WP-2215
Depends on: —

## Goal

The GUI's front end is rebuilt from the prototype, beside today's, and replaces it once the two
reach parity. This WP writes the two things the rebuild starts from. The first is an inventory
of every feature a person can see or use in today's GUI, each given a home in the new design.
The second is the plan: the pieces in order, how the two front ends are served side by side,
when the new one replaces the old, which tests and manual chapters are rewritten when, and how
the maintainer reviews the work. It writes no code.

## Context

### The ruling

On 2026-11-11 the maintainer ruled, on a brief, to rebuild the front end from the prototype
instead of porting it piece by piece. In his words: "What I want is the new gui to look and feel
like the prototype. I'd like you to find elegant ways to include the extra features of the
current gui into the new one in a visually uncluttered way. For example, the many buttons above
and below the main panels should be hidden and accessible according to UI design best practice.
At the moment, I feel that we're litigating every small change to the old gui."

Two rulings of the evening before bear on it. "A large part of the redesign is concealing a lot
of these cluttered buttons." And "drop the wordmark and other random infoslop (this comment could
be generalised to more of the gui)". The second asked for a list of what goes before anything is
deleted; that list is flagged row 4 below.

What the rebuild keeps: the Python server and its routes, the logic layer in `gui/src/lib`, the
chart module (`src/rietx/viz/static/rxplot.mjs`) and the colour tokens in
`src/rietx/viz/theme.py`. What it replaces: the shell and the panels. The new front end is served
beside the old, may be incomplete until parity, and then replaces it. The milestone's rule that
every merge leaves every panel reachable moves from each merge to the swap.

### What the prototype is

The design was worked out in twelve rounds of prototypes the maintainer reviewed on screen,
6 to 8 November 2026. The prototypes are a private mockup, so this file restates each design it
relies on. `gui/STYLE.md` holds the rules distilled from those rounds, each with its motive, and
is the authority a screen is judged against. Where the prototype and a rule disagree, the rule
wins (STYLE principle 9).

The prototype draws the main window, the Parameters, Interactive, Plan and Text tabs, the
Pattern, Peaks, Background and Structure graphs, the start screen and New project, the File,
workflow and plan menus, a Settings dialog, a bottom panel with Console and History, and the
peaks-and-indexing and series workflows. It draws no command palette, no view menu, no context
menu on a plot, no excluded region, no hover readout on the pattern, no fit report and no Model
tab. Today's GUI has all of these. The inventory gives each a home.

### How a person reaches what is not on screen

The prototype hides secondary controls in twelve ways, and the inventory uses only these, plus
the command palette today's GUI already has:

- a menu on a bar button (File on the project name, the workflow menu, the plan menu);
- a context menu on an object (interaction rule 12);
- a disclosure, which stays open until its own chevron closes it;
- a popover on a value (limits, restraint, formula);
- a legend label that is also the curve's switch;
- a selection bar over a selected plot object (interaction rule 3);
- a panel that collapses from a fixed toggle;
- the Settings dialog;
- a `?` box per panel, and help on a term;
- a control that exists only while it can act (Free and Fix only while filtering, Show all only
  while zoomed);
- a step navigation inside a workflow;
- a keyboard key.

### Practice

Recall, labelled as such, plus the window-layout survey already in `docs/practice.md`. This WP
adds a short section there, "Where a GUI keeps its secondary controls".

- **VS Code**: an activity bar and side bars that collapse, a bottom panel (Problems, Output,
  Terminal), a status bar whose right half shows facts about the file (language mode, encoding,
  line endings) and whose items open a menu when clicked, and a command palette (⇧⌘P) holding
  every command, each with its key. The Problems count sits in the status bar and opens the
  Problems panel (recall).
- **Figma**: a canvas with almost no chrome, a toolbar of a few tools, a properties panel that
  shows only what applies to the selection, right-click menus on every object, and a quick-actions
  search on ⌘/ (recall).
- **Origin and Igor Pro**: a plot's export, copy and axis options live on the plot's right-click
  menu and in a plot-details dialog. Origin reads the cursor's coordinates in its status bar
  (recall).
- **ImageJ, QGIS and GIMP**: the pointer's coordinates and the value under it are read in the
  status bar (recall).
- **GraphPad Prism**: a graph's format options open in a dialog from the graph, and the graph
  window shows only the graph (recall).
- **GSAS-II**: a data tree on the left, each node's notebook on the right, menus on the window's
  menu bar, and right-click menus on plots for a few actions (recall, 5.8.4).
- **Gmail and GitHub**: single-letter keys for frequent verbs, and `?` opens the list of keys
  (recall).
- **macOS**: ⌘. cancels the operation in progress (recall, Apple Human Interface Guidelines).

The practice these add up to: the window shows the work and few controls. Everything else is one
gesture away on the object it acts on (a context menu, a selection, a popover). A command palette
holds every command with its key. The status bar carries facts about the document and live state.
That is the shape every row below takes.

## The inventory

Every feature a person can see or use in today's GUI, on `origin/main` at 68fd06973, walked over
`gui/src/App.svelte`, every file in `gui/src/panels`, the keys and the palette. Rows are grouped
by where the feature lives today. The open pull requests add a few features (#1521's status bar,
#1523's recovery dialog); they are rows too, marked with their PR.

Columns: **Today** is where the feature sits now. **Home** is where it lives in the new design.
**Rests on** names the prototype, a `gui/STYLE.md` rule, a ruling or the practice above. **F**
marks a row that waited on the maintainer, numbered as in § Questions, where each ruling of
2026-11-11 is recorded; every other row is settled on its grounds. "Kept" means the prototype draws it in the same place. A "one-line empty state"
is a short sentence and the action that fills the view, as VS Code's empty views have.

### Top bar

| # | Feature | Today | Home | Rests on | F |
|---|---|---|---|---|---|
| 1 | Hide or show the graphs | header, far left | top bar, far left; ⌘1 | prototype; STYLE § Layout | |
| 2 | Hide or show the model panel | header, far right | top bar, far right; ⌘2 | prototype; STYLE § Layout | |
| 3 | The `rietx` wordmark | header | removed | the maintainer, 2026-11-10 ("drop the wordmark") | 4 |
| 4 | The version | header | Settings, as an About line | VS Code's About | 4 |
| 5 | The project name, which opens the File menu | header | top bar, after the workflow menu | prototype; macOS document title | |
| 6 | The data file's name and point count | header | removed from the bar; the project name's tooltip | "infoslop" ruling | 4 |
| 7 | The refinement mode (Rietveld, Le Bail, Pawley) | header | removed | the maintainer, 2026-11-10 (dropped from the header as clutter) and 2026-11-11 (not in the status bar) | 3 |
| 8 | Where σ comes from ("σ from file", "σ Poisson") | header | removed | the maintainer, 2026-11-10 (dropped from the header as clutter) and 2026-11-11 (not in the status bar) | 3 |
| 9 | Simple or Advanced | header | removed; each advanced field sits behind its own disclosure or popover | the maintainer, 2026-11-08 (an advanced mode "probably not needed if we're judicious"); prototype | |
| 10 | Theme | header | Settings: Match system, Light, Dark | the maintainer, 2026-11-09 | |
| 11 | Run state (idle, stage i of n, Le Bail pass) | header; status bar in #1521 | status bar, left, in words, only while a run is in flight | prototype; #1521 | |
| 12 | Cancel the run | header; status bar in #1521 | Stop beside the run state, in a slot kept for it; ⌘.; the palette | prototype (Stop in the indexing step); macOS ⌘. | |
| 13 | The palette's button | header | removed from the bar; ⌘K, named at the foot of every `?` box | VS Code (no button) | |
| 14 | The Le Bail alternation verdict | a row under the header | a finding in the report, counted in the status bar | rows 161-171 | 2 |
| 15 | The workflow menu | #1524 | top bar, after the graphs toggle | prototype; the maintainer, 2026-11-07 | |
| 16 | Settings | none | top bar, right, before the model toggle; ⌘, | prototype | |
| 17 | The console toggle | #1521 | status bar, far left; ⌘J | prototype | |

### Action bar

| # | Feature | Today | Home | Rests on | F |
|---|---|---|---|---|---|
| 18 | One cycle or a staged plan | action bar | kept | prototype | |
| 19 | The pending-edit count, or "invalid edit" | action bar | kept, in a slot that never resizes | prototype; STYLE principle 4 | |
| 20 | Revert | action bar | kept | prototype | |
| 21 | Apply | action bar | kept; it also applies the Text tab's edits and the structural edits of rows 118-131, so a window has one Apply | prototype; the milestone's owed list (two Apply buttons in one view) | |
| 22 | Refine, or Apply and refine, ⌘Enter | action bar | kept, the one filled button | prototype; STYLE § Components | |
| 23 | Rwp and GoF beside Refine while the graphs are hidden | #1518 | kept | the maintainer, 2026-11-09 ("try B") | |
| 24 | The Model tab's own Apply and Revert | Model header | removed; its edits join the action bar | the owed list | |

### Pattern graph

| # | Feature | Today | Home | Rests on | F |
|---|---|---|---|---|---|
| 25 | Graph tabs (Pattern, Single peaks, Background) | graph column | Pattern, Peaks, Background, Structure | prototype; STYLE § Layout | |
| 26 | The title saying what the graph shows | title line | kept; it shrinks with an ellipsis before any control wraps | prototype; B1, 2026-11-09 | |
| 27 | Rwp and GoF | title line | kept | prototype | |
| 28 | "Not a fit yet" | a chip on the title line | words in the danger colour, no box | STYLE § Components (Fact); #1518 | |
| 29 | A refused preview | title line | the title's state | STYLE: the title says what the graph shows | |
| 30 | The chart (crosses, calculated, background, difference, ticks) | Plot | kept on the chart module | the rebuild ruling | |
| 31 | The difference as Δ/σ, Δ or cumulative χ² | a row under the plot | the view menu (⋯ at the right of the title line) › Difference | Origin and Igor plot menus; the prototype draws Δ/σ alone | |
| 32 | Intensity: linear, √, log | a row under the plot | title line: Linear, Square root, Log on one segmented track | prototype (linear and √); STYLE § Components | |
| 33 | One button per curve | a row under the plot | the legend gutter at the plot's right; each label is its curve's switch | prototype; STYLE § Plots | |
| 34 | A curve that cannot be drawn, with its reason | that row | its legend label greyed, the reason in its tooltip | WP-1210 | |
| 35 | Data only | that row | view menu › Show only the data | Prism and Origin keep show-all and hide-all in a menu | |
| 36 | PNG, SVG, copy image, copy data | that row | the plot's context menu (Copy image, Copy data, Save image…) and File › Export › Pattern plot | Origin, Igor and Excel chart menus; prototype's File › Export | |
| 37 | "N channels, lo–hi°" and the decimation note | under the plot | removed; the counts go to the fitted range's selection bar; the decimation note stays where it applies | "infoslop" ruling | 4 |
| 38 | "N predicted lines · label" for a candidate | under the plot | the candidate's legend entry, "#n" | prototype (indexing legend) | |
| 39 | The fitted range's typed bounds, Set and All | the protocol row | the range is an object on the plot: a click on its edge band selects it, and its selection bar holds the typed bounds and the channel count; view menu › Fit the whole pattern | interaction rules 1, 3 and 4 | |
| 40 | Arm a drag that sets the fitted range | protocol row | view menu › Set the fitted range…, and the plot's context menu | interaction rule 12 | |
| 41 | Arm a drag that excludes a region | protocol row | view menu › Exclude a region…, and the plot's context menu | interaction rule 12 | |
| 42 | One pill per excluded region, with × | protocol row | shading on the plot; a click selects it, its bar holds the bounds and Delete; Delete or Option-click removes it | interaction rules 1 and 4 | |
| 43 | "N of M channels fitted" | protocol row | the selection bar of the range or a region | WP-1033 | |
| 44 | "Fitted over a different set of channels" | protocol row | the title's state until the next run | STYLE: the title says what the graph shows | |
| 45 | A refused range or region | protocol row | a toast beside the selection bar | prototype's toast | |
| 46 | The hover readout (2θ, d, observed, calculated, background, difference, hkl) | a strip under the plot | the status bar's right half while the pointer is over a plot | ImageJ, QGIS and Origin; the maintainer, 2026-11-11 (looked at once built) | 5 |
| 47 | A crosshair shared by every pane | chart | kept | WP-1213 | |
| 48 | Drag to zoom | chart | kept | interaction rule 6 | |
| 49 | Wheel zoom, Shift-wheel and Alt-drag pan | chart | kept; sideways scroll pans, and ‹ › appear while zoomed | prototype | |
| 50 | Double-click shows everything | chart | kept, and Show all on the title line while zoomed | prototype; interaction rule 6 | |
| 51 | Peak gestures on the pattern (click adds, drag moves, Shift-click excludes, right-click removes) | Plot, Peaks tab up | the peaks-and-indexing workflow, under the object grammar: click adds, drag moves, Option-click removes, a selected peak's bar holds Used, Not used and Delete, right-click opens its menu | interaction rules 1 to 12 | |
| 52 | The line naming the peak gestures | under the plot | removed; the `?` box says it, and hover shows where a click lands | STYLE principle 5; interaction rule 9 | |
| 53 | "Drag on the plot to …, Esc cancels" while armed | under the plot | a note floating over the plot while armed, and the `col-resize` cursor | STYLE principle 4 (no new line) | |
| 54 | "No fitted curves yet", "Raw pattern, no fit yet" | in the plot | a one-line empty state with Refine | VS Code's empty views; "infoslop" ruling | 4 |
| 55 | A hovered peak's ring, lit in its table row and back | Plot, Peaks | kept | the maintainer, 2026-11-07 (hkl highlighting comes over) | |
| 56 | A candidate's lines on hover and on selection | Plot | the indexing workflow's Pattern | prototype | |
| 57 | The preview curve | Plot | the legend's Preview slot, kept empty until a preview exists | prototype | |
| 58 | A failed or loading fetch | above the chart | the title's state | STYLE: the title says what the graph shows | |

### Peaks graph (today's Single peaks)

| # | Feature | Today | Home | Rests on | F |
|---|---|---|---|---|---|
| 59 | Three peak windows at the last fit's scale | PeakWindows | the Peaks graph, up to three windows | prototype | |
| 60 | Each window's 2θ, hkl and phase | caption | the window's title | prototype | |
| 61 | ‹ › to the next strong reflection | caption | kept | prototype | |
| 62 | "No fitted peaks to frame yet" | window | a one-line empty state | VS Code's empty views | |

### Background graph

| # | Feature | Today | Home | Rests on | F |
|---|---|---|---|---|---|
| 63 | The curve over greyed data, with its band | Background | kept | prototype | |
| 64 | One hold box per Chebyshev term | a row under the plot | "Hold at last fit" term chips under the plot | prototype | |
| 65 | The P-spline's λ | that row | a stiffness slider under the plot | prototype | |
| 66 | The band at ×1, ×5, ×20 | that row | title line, "Band drawn" | prototype | |
| 67 | The background family and Chebyshev term count | Model tab | title line: Chebyshev or P-spline; a terms slider under the plot | prototype | |
| 68 | A refused band, "waiting for the run" | Background | the title's state | STYLE: the title says what the graph shows | |

### Structure graph

| # | Feature | Today | Home | Rests on | F |
|---|---|---|---|---|---|
| 69 | The 3D view | Model's third column; a graph tab in #1519 | the Structure graph tab | the maintainer, 2026-11-07; prototype | |
| 70 | Balls or ellipsoids | over the canvas | title line, segmented | prototype; STYLE § Components | |
| 71 | Which phase | over the canvas | a menu on the title line, drawn only with two or more phases | STYLE: a control exists only while it can act | |
| 72 | Drag rotates, Shift-drag or right-drag pans, wheel zooms | canvas | kept | WP-1015 | |
| 73 | Double-click an atom to show its coordination | canvas | click selects the atom; its selection bar holds Show coordination; double-click resets the view | interaction rules 3 and 6 | |
| 74 | The atom or bond under the pointer | a line under the canvas | the status bar's right half, as row 46 | ImageJ, QGIS and Origin; the maintainer, 2026-11-11 | 5 |
| 75 | The cell's a, b, c letters | canvas | kept | WP-1015 | |
| 76 | One button per species | under the canvas | the colour key on the title line, each entry a switch | prototype; STYLE § Plots (legend as switch) | |
| 77 | Polyhedra on or off, and per formula | under the canvas | entries in that key | prototype (Atoms and Polyhedra) | |
| 78 | Look down a, b, c, and reset | under the canvas | title line, "Look down a b c" | prototype | |
| 79 | PNG | under the canvas | the canvas's context menu (Save image…, Copy image) and File › Export | Origin, Igor and Excel | |
| 80 | The drawing drawer (probability, size, bond tolerance, centres and corners, disorder, images outside the cell, transparent PNG) | under the canvas | view menu › Drawing…, a popover; the transparent choice goes to Save image… | Origin's plot details; VESTA's Properties dialog | |
| 81 | The caption (draw mode, probability, exaggeration) and "space group · V" | under the canvas | the probability and any exaggeration in the title while ellipsoids show; the rest removed | WP-1029 (an exaggeration is not a probability); "infoslop" ruling | 4 |
| 82 | No WebGL2, loading, a load error | canvas | a one-line empty state | VS Code's empty views | |

### Parameters tab

| # | Feature | Today | Home | Rests on | F |
|---|---|---|---|---|---|
| 83 | The filter box, `/` | top of the tab | kept | prototype | |
| 84 | "N free of M" | top of the tab | kept | prototype | |
| 85 | Free N and Fix N on the filter | top of the tab | drawn only while a filter is typed; `f` and `x` | prototype | |
| 86 | One section per phase | list | a phase band with its chevron | prototype | |
| 87 | Groups with a three-state box | list | groups by effect, in refinement order | the maintainer, 2026-11-07 (grouping B) | |
| 88 | Label with help, box, value, unit | row | kept | prototype; STYLE § Spacing | |
| 89 | A held row's mark and reason | row | a row that cannot be freed folds into the crystallographer's line (`a = b = c, α = β = γ = 90°`); others keep their mark, the reason in its tooltip | the maintainer, 2026-11-06 | |
| 90 | The padlock (`hold`) | row | kept, in a checkbox cell's geometry | the maintainer, 2026-11-07 | |
| 91 | The atom table | phase section | kept, one row per atom | the maintainer, 2026-11-06 | |
| 92 | Click a value to edit it | row | the floating editor, wide enough for the whole number | prototype; STYLE § Components | |
| 93 | Shift-click ranges, ⌘-click selections, one number into all | row | kept | the maintainer, 2026-11-07 | |
| 94 | The value popover (limits, restraint) | row | kept, with the `=` formula button | the maintainer, 2026-11-08 | |
| 95 | A value near its limit | row | text colour and a mark on the limit's side | the maintainer, 2026-11-08 | |
| 96 | Loading, no parameters, nothing matches | list | a one-line empty state | VS Code's empty views | |
| 97 | No group shows which stage frees it (owed) | none | the plan's stage badge in place of the box, in plan mode | prototype | |

### Interactive tab

| # | Feature | Today | Home | Rests on | F |
|---|---|---|---|---|---|
| 98 | Slider groups | Interactive | kept | prototype | |
| 99 | The slider's name opens its range and scale | Interactive | kept | the maintainer, 2026-11-07 | |
| 100 | Click the number to type it | Interactive | kept | the maintainer, 2026-11-07 | |
| 101 | ↺ back to the last fit, and its mark on the track | Interactive | kept | prototype | |
| 102 | The range pop-up (from, to, scale, default) | Interactive | kept | prototype | |
| 103 | "No value here can be moved by hand" | Interactive | a one-line empty state | VS Code's empty views | |

### Plan tab

| # | Feature | Today | Home | Rests on | F |
|---|---|---|---|---|---|
| 104 | The preset select | top of the tab | the plan menu on the plan's name (plans, presets, Save as new plan…, Revert) | prototype | |
| 105 | + Stage | top of the tab | kept | prototype | |
| 106 | Drag handle, ↑ and ↓ reorder | stage | kept | prototype | |
| 107 | Run this stage, `.` | stage | the stage's ⋯ menu and its context menu; `.` stays | interaction rule 12 | |
| 108 | Remove a stage | stage | the stage's delete icon | prototype | |
| 109 | The globs a stage frees, and an add field | stage | the Free row with + Add, which opens a grouped picker | prototype | |
| 110 | The globs a stage fixes | #1520 | the Fix row with + Add | prototype; the maintainer, 2026-11-09 | |
| 111 | "+N → N free, N held, Rwp" with its lists | stage | the stage's Rwp and free count at the row's right; the lists in a disclosure | WP-1208; STYLE § Components (disclosure) | |
| 112 | "not applied" past the first edit | stage | kept, as words | WP-2127 | |
| 113 | Iterations, tolerances, seeds, restraint weight | stage, Advanced only | the stage's ⋯ › Stage settings…, a popover | interaction rule 12 | |
| 114 | The closing stage | foot of the plan | the plan's last row, with "Never freed" under it | prototype | |
| 115 | "N you freed by hand, held by the plan" | foot of the plan | kept, a disclosure | WP-1208 | |
| 116 | The correlation guard's threshold | foot, Advanced only | plan menu › Plan settings… | interaction rule 12 | |
| 117 | Undo and redo a plan edit | ⌘Z in the panel; palette | ⌘Z and ⇧⌘Z for every edit in the window | interaction rule 10 | |

### Model tab

The prototype has no Model tab. What it edits becomes one of three things in the new design:
values the Parameters tab already holds, structural edits on the phase's and the atom's menus,
or the instrument's settings in a dialog. That split is flagged row 1.

| # | Feature | Today | Home | Rests on | F |
|---|---|---|---|---|---|
| 118 | "Structure & instrument" | Model header | removed | "infoslop" ruling | 4 |
| 119 | The 3D toggle | Model header | removed; the Structure tab | the maintainer, 2026-11-07 | |
| 120 | "A box beside a value frees it…" | Model header | removed; the `?` box | STYLE principle 5 | 4 |
| 121 | Replace from CIF… | Structure column | the phase band's ⋯ menu | interaction rule 12 | 1 |
| 122 | "No phase yet. Pick peaks and index them…" | Structure column | the Parameters tab's one-line empty state, with Add a phase… | VS Code's empty views | 1 |
| 123 | The phase picker | Structure column | the phase bands | prototype | |
| 124 | The phase's name | Structure column | the phase band's ⋯ › Rename… | interaction rule 12 | 1 |
| 125 | Change the space group, with its preview card | Structure column | the phase band's ⋯ › Change space group…, a dialog holding the preview | interaction rule 11 (offer the candidates) | 1 |
| 126 | The symmetry summary | Structure column | the space group typeset in the phase band; the folded held line | the maintainer, 2026-11-06 | |
| 127 | The cell, the scale, size and strain | Structure column | the Parameters tab | prototype | |
| 128 | An atom's label and species | atom table | shown in its atom row; changed from the row's context menu (Rename…, Change species…) | the maintainer, 2026-11-07 (label and species locked in the row) | 1 |
| 129 | x, y, z solved onto the site, occupancy, Biso | atom table | the Parameters atom table | prototype | |
| 130 | Anisotropic ADPs and the U^ij expander | atom table | the atom's context menu › Anisotropic ADPs; the U^ij rows open under the atom | interaction rule 12 | 1 |
| 131 | Remove an atom; add an atom | atom table | the atom's context menu › Delete, or Delete on a selected row; the phase band's ⋯ › Add atom…, a popover | interaction rule 12 | 1 |
| 132 | "A new atom's position decides its site…" | atom table | removed; the `?` box | STYLE principle 5 | 4 |
| 133 | Load profile…, Save profile…, "wrote <path>" | Instrument column | the Instrument dialog, and File › Export › Instrument profile; the path in a toast | prototype's File › Export and toast | 1 |
| 134 | Source and geometry (anode, wavelengths, ratio, polarisation, geometry, radius, slits, µ) | Instrument column | the Instrument dialog, opened from the Instrument group's ⋯ menu, on the form New project already draws | WP-2131's instrument form | 1 |
| 135 | The profile's refinable values (U, V, W, X, Y, zero, displacement, S/L, H/L) | Instrument column | the Parameters tab's instrument groups | prototype | |
| 136 | The S/L-H/L warning | Instrument column | beside the pair in the Instrument dialog | WP-1014 | |
| 137 | Splitters between the columns | Model tab | removed with the tab | | |
| 138 | The footer: errors, invalid edits, the edit-routing tally | Model footer | errors at their field; the tally removed | "infoslop" ruling | 4 |

### Text tab

| # | Feature | Today | Home | Rests on | F |
|---|---|---|---|---|---|
| 139 | "Project text" and ".rxt" | header | the file's name on the tab's title line | prototype | |
| 140 | The sync state (clean, dirty, stale, checking) | header pill | a word beside the name | STYLE § Components (Fact) | |
| 141 | Apply, ⌘Enter | header | the action bar's Apply; a typed change is a pending edit | prototype | |
| 142 | Re-read | header | inside the stale notice, the only time it can act | STYLE: a control exists only while it can act | |
| 143 | The editor | Text | kept | WP-1013 | |
| 144 | The stale, sync, boot and comments notices | Text | one-line notices over the editor | | |
| 145 | Problems, each linked to its line | under the editor | gutter marks and the list under the editor | VS Code's Problems | |
| 146 | The footer's prose (Alt-drag, verbs) | footer | removed; the `?` box | STYLE principle 5 | 4 |

### Bottom panel: Console and History

| # | Feature | Today | Home | Rests on | F |
|---|---|---|---|---|---|
| 147 | The console log and its echoed calls | foot of the side column | the bottom panel's Console | prototype | |
| 148 | Collapse the console | its header | the status bar's toggle, ⌘J | prototype | |
| 149 | Its sash | its top edge | kept; double-click resets | prototype | |
| 150 | "N frames dropped" | console | kept, one line | | |
| 151 | Follow, Copy | #1521 | kept | prototype; #1521 | |
| 152 | The history graph with lanes | History tab | the History table, one row a node, its count on the tab | prototype; WP-2211 | |
| 153 | Select a node; its API call | History | a row click; the call in the row's tooltip | WP-2211 | |
| 154 | ⇄ compare | History | Compare on the row overlays its fit on the pattern; Compare values… on the row's context menu opens the diff | prototype; WP-2211 | |
| 155 | The selected node's details | History | the row's disclosure | STYLE § Components (disclosure) | |
| 156 | Checkout, Tag, Branch, Label | History | the row's context menu; Restore loads a node as pending edits | interaction rule 12; WP-2211 | |
| 157 | The checkout warning | History | removed; Restore is undoable | interaction rule 11 (undo replaces a warning) | 4 |
| 158 | The diff panel (filter, metrics, ranked paths) | History | kept, opened from row 154 | WP-1217 | |
| 159 | "No history yet" | History | a one-line empty state | VS Code's empty views | |
| 160 | `h` opens History | key | dropped; the status bar's toggle, the palette | rows 238-240 | |

### Report tab

The prototype draws no report. Its home is flagged row 2.

| # | Feature | Today | Home | Rests on | F |
|---|---|---|---|---|---|
| 161 | The head line (Rwp, GoF, regions, unindexed and unobserved counts) | Report | the Report tab of the bottom panel; its count of findings in the status bar | VS Code's Problems panel and count | 2 |
| 162 | The thresholds version | Report head | removed | "infoslop" ruling | 4 |
| 163 | The summary sentence | Report | kept, the tab's first line | WP-1012 | 2 |
| 164 | Layer 1 abstained, gates refused | Report | kept | the FitReport's rule against a confident wrong singleton | 2 |
| 165 | "Applied <kind>", predicted and observed Δχ², Undo | Report | a toast with Undo | interaction rule 11; Gmail's undo toast | 2 |
| 166 | Diagnostics, errors open and the rest folded | Report | kept | WP-1012 | 2 |
| 167 | Suggestions with Apply, rationale, paths, refusal | Report | kept | WP-1012 | 2 |
| 168 | The expected-Δχ² note | Report | printed once, over the suggestions | WP-1012 | 2 |
| 169 | Worst regions, which zoom the plot | Report | kept | WP-1012 | 2 |
| 170 | Peaks with no partner, which zoom the plot | Report | kept | WP-1012 | 2 |
| 171 | Trends, attribution, texture, strain (Advanced only) | Report | a disclosure | STYLE § Components (disclosure) | 2 |
| 172 | Loading, nothing suggested | Report | a one-line empty state | VS Code's empty views | |
| 173 | `?` opens the report | key | `?` opens the list of keys; the report from the status bar's count or the palette | Gmail and GitHub | |

### Series workflow

The prototype draws the series as a workflow in four steps (Patterns, First fit, Run, Results)
with the Trends and Map graphs (ruled 2026-11-08).

| # | Feature | Today | Home | Rests on | F |
|---|---|---|---|---|---|
| 174 | The direction-gap banner | Series tab | the Results step's "Largest walk gap" | prototype | |
| 175 | The paragraph explaining a series | Series tab | removed; the `?` box | STYLE principle 5 | 4 |
| 176 | Add patterns…, Sort by | Series tab | the Patterns step | prototype | |
| 177 | Staging status, the mixed-σ warning | Series tab | the Patterns step, as a state and a warning | prototype | |
| 178 | The pattern table (label, x, file, points, range, σ, reorder, remove) | Series tab | the Patterns step's table | prototype | |
| 179 | "No patterns staged" | Series tab | a one-line empty state with Add files… | VS Code's empty views | 4 |
| 180 | The direction, Run series | Series tab | the Patterns step's Order choice; the Run step | prototype | |
| 181 | Refit mode, carry glob, x label (Advanced only) | Series tab | the Patterns step's More settings | prototype | |
| 182 | The trajectory's parameter, order and Show | Series tab | the Trends graph's Plot menu | prototype | |
| 183 | The trajectory note | Series tab | the point's tooltip | prototype | |
| 184 | The legend's switches | Series tab | the Trends legend gutter | prototype | |
| 185 | The series figure's exports | Series tab | the Trends context menu; the Results step's Save table… | prototype; Origin | |
| 186 | The trajectory's hover tip | Series tab | the Trends tooltip | prototype | |
| 187 | The steps table | Series tab | the Results step's "Largest steps" disclosure | prototype | |
| 188 | The per-pattern table, ▸ to open a pattern | Series tab | the Results step's table, with Open in Refinement | prototype | |
| 189 | The iteration total | Series tab | the Results summary | prototype | |
| 190 | A member's history | Series tab | the History table of a pattern opened from the series | WP-1016 | |
| 191 | Fences | Series tab | the Results step's "Warnings across the series" | prototype | |
| 192 | "Nothing has run yet" | Series tab | a one-line empty state | VS Code's empty views | 4 |

### Peaks-and-indexing workflow

The prototype draws peaks and indexing as a workflow in four steps (Pick peaks, Fit peaks,
Index, Judge), ruled 2026-11-08; PR #1526 built it inside today's Peaks tab.

| # | Feature | Today | Home | Rests on | F |
|---|---|---|---|---|---|
| 193 | Pick peaks, Re-pick | Peaks tab | the Pick step, with "Picking again replaces…" asked first | prototype; interaction rule 11 | |
| 194 | "add at 2θ…" | Peaks tab | a typed row at the foot of the Pick step's table | WP-1027 (every pointer verb has a non-pointer route) | |
| 195 | Index | Peaks tab | the Index step | prototype | |
| 196 | The run's progress, a failure | Peaks tab | the Index step's progress block, with Stop | prototype | |
| 197 | The search form (engines, systems and centring, preset, budgets, d and volume, formula, temperature, line counts, prior cells, prior space groups) | a disclosure | the Index step's short form (systems, largest volume, time limit); the rest under More settings | prototype | |
| 198 | Streamed shortlists | Peaks tab | "Found so far" | prototype | |
| 199 | "No peak list yet. Pick peaks fits…" | Peaks tab | a one-line empty state with Pick peaks | VS Code's empty views | 4 |
| 200 | "N of M lines usable", "σ assumed" | Peaks tab | the Pick step's filter counts; σ assumed as a note | prototype | |
| 201 | The picker's notes | Peaks tab | "Notes from the picker", a disclosure | prototype | |
| 202 | The peak table (#, 2θ that zooms, d, I, flags, use, refit, remove) | Peaks tab | the Pick step's table; refit on each group's row of the Fit step | prototype; #1526 | |
| 203 | Flag and origin chips with help | Peaks tab | words in the Note column, each with its help | STYLE § Components (Fact) | |
| 204 | What the search covered | Peaks tab | above the list, whatever it found | WP-2130 (what was not reached is said) | |
| 205 | The run's diagnostics | Peaks tab | warnings above the list; the rest in "Notes from the search" | #1526 | |
| 206 | The candidate table | Peaks tab | the Index step's table in eight columns | prototype | |
| 207 | Adopt on every row | Peaks tab | kept | the maintainer's ruling B, 2026-11-08 | |
| 208 | A candidate's detail (caveats, partners, "collect to 2θ") | Peaks tab | the Judge step | prototype | |
| 209 | Screen extinctions, its table, Adopt in a group | Peaks tab | the Judge step | prototype | |
| 210 | "No candidate reaches the gate…" | Peaks tab | "rietx's pick" marks the gate's choice | #1526 | |
| 211 | `p` opens the peak picker | key | dropped; the workflow menu, the palette | rows 238-240 | |

### Start screen, New project, File menu

WP-2131 and WP-2133 built these to the round-9 design, so the rebuild mounts them in the new
frame as they are.

| # | Feature | Today | Home | Rests on | F |
|---|---|---|---|---|---|
| 212 | The start screen | Start | kept | WP-2131 | |
| 213 | Its wordmark and version | Start | removed | the maintainer, 2026-11-10 | 4 |
| 214 | New project…, Open…, Back to the project | Start | kept | WP-2131 | |
| 215 | Manual and Tutorials links | Start | kept | WP-2131 | |
| 216 | Recent projects, their ⋯ and right-click menus, Locate… | Start | kept | WP-2131 | |
| 217 | Examples and Open a fresh copy | Start | kept | WP-2131 | |
| 218 | A refused open | Start | kept | WP-2131 | |
| 219 | The New project dialog (pattern, how it was read, phases, ADPs, a typed cell, Add phase, instrument, name and folder, Create) | NewProject | kept | WP-2131 | |
| 220 | "None yet" under Phases | NewProject | kept, one line | WP-2131 | |
| 221 | The File menu (New, Open ⌘O, Open recent, Save a copy ⇧⌘S, Rename, Move to, Export, Close) | FileMenu | kept | WP-2133 | |
| 222 | The toast beside the name | FileMenu | kept | prototype | |
| 223 | ⌘S answers "Saved" | FileMenu | kept | the maintainer, 2026-11-07 | |
| 224 | Browse, the folder picker | Browse | kept for the browser build; the system dialog in the desktop app | prototype | |
| 225 | Export: CIF, reflections, phase fractions, report, result, instrument profile | File menu | kept, plus Pattern plot and Console as a Python script | prototype | |
| 226 | The export dialog | FileMenu | kept | WP-2133 | |
| 227 | Unapplied edits offered back on reopening | #1523 | kept, drawn in the new frame | the maintainer, 2026-11-09 | |

### Keys

| # | Feature | Today | Home | Rests on | F |
|---|---|---|---|---|---|
| 228 | ⌘K opens the palette | App | kept | VS Code, Figma | |
| 229 | ⌘Enter refines (applies, in the Text editor) | App | Apply and refine everywhere, the Text editor included | prototype; row 141 | |
| 230 | Esc closes help, then cancels a run | App | Esc backs out of the gesture in progress and no further; ⌘. stops a run | STYLE interaction rule 2; macOS ⌘. | |
| 231 | `r` runs the fit, applying edits first | App | kept | Gmail and GitHub single-letter verbs | |
| 232 | `.` runs one stage | App | kept | as row 231 | |
| 233 | `f`, `x` free and fix the filtered rows | App | kept | as row 231 | |
| 234 | `/` focuses the filter | App | kept | as row 231 | |
| 235 | ⌘O, ⇧⌘S, ⌘S | FileMenu | kept | WP-2133 | |
| 236 | ⌘Z, ⇧⌘Z in the Plan tab | Plan | every edit in the window | interaction rule 10 | |
| 237 | Esc cancels an armed drag; Enter and Esc in editors and dialogs; ↑ and ↓ on a stage's handle; the palette's arrows; Enter on a help term | panels | kept | STYLE § Interaction | |
| 238 | `p`, `?`, `h`, `t`, `m` open a tab | App | `p`, `h`, `t` and `m` dropped, their tabs one click away and in the palette; `?` lists the keys | Gmail and GitHub (`?`) | |
| 239 | ⌘1, ⌘2, ⌘J, ⌘, | none | added | prototype | |
| 240 | A list of the keys | none | `?`, and every command's key beside it in the palette | Gmail, GitHub and VS Code | |

### Command palette

| # | Feature | Today | Home | Rests on | F |
|---|---|---|---|---|---|
| 241 | The palette: a search box, ranked commands, each with its key and the Python call it makes | Palette | kept, ⌘K | VS Code, Figma; the console's teaching of the API | |
| 242 | Its commands (run, run a stage, undo, redo, cancel, free, fix, filter, peak picker, run indexing, series, report, history, text, model, hide the panels, one cycle, open a project, advanced, theme, save) | Palette | each kept and renamed for its new home; "advanced" goes with row 9, "model" becomes Edit the instrument… and Change space group…; every view-menu and context-menu entry joins it | VS Code (every command in the palette) | |

### Help, and what is everywhere

| # | Feature | Today | Home | Rests on | F |
|---|---|---|---|---|---|
| 243 | A term's help popover with its manual link | Help | kept | STYLE § Components (help term) | |
| 244 | Help the server wrote about one row | Help | kept | WP-1203 | |
| 245 | Tooltips on buttons | everywhere | kept, as verb phrases with the key on a second line | STYLE § Components | |
| 246 | A `?` box per panel | none | added | prototype | |
| 247 | The first-run checklist and its Dismiss | over the side tabs | removed; the New project dialog | prototype | 4 |
| 248 | The Build tab | side tabs | removed; the build's facts in Settings' About line | "infoslop" ruling | 4 |
| 249 | Ten side tabs | side column | four model tabs, the workflows and the bottom panel | prototype | |
| 250 | The side column's splitter; the stacked layout | App | the sash; one column below the measured width | prototype; STYLE § Layout | |
| 251 | Layout kept with the project (widths, console height) | App | kept | WP-1029 | |
| 252 | Typeset space groups | everywhere | kept | the maintainer, 2026-11-06 | |
| 253 | 2θ links that zoom the plot (Report, Peaks) | Report, Peaks | kept | WP-1012 | |
| 254 | Controls disabled while a run is in flight | everywhere | kept | WP-1008 (the 409) | |

## The plan

### The framework stays Svelte 5

Settled on measurement and practice. The framework-free TypeScript in `gui/src/lib` is 33
modules and 9 686 lines, against 15 671 lines of Svelte in `App.svelte` and the panels, and 30
vitest files test it. The rebuild keeps it by ruling, and every module imports into a Svelte
component as it stands. The vitest-and-jsdom harness, the
committed dist, svelte-check and the browser tests all assume it. The traps `gui/CLAUDE.md`
§ Svelte and browser traps records were each found once in a browser, and a new framework starts
that list again. The prototype is plain JavaScript and offers no framework to adopt: its 3000
lines of render functions are what components replace. Tauri takes any web front end. The
alternative, plain JavaScript as the prototype has it, loses the component boundary each screen
is reviewed by.

### Two front ends, one server

The new front end is a second page in the same Vite build: `gui/next.html` with its code under
`gui/src/next/`, beside today's `gui/index.html` and `gui/src/App.svelte`. Both import
`gui/src/lib`, `gui/src/api.ts` and `gui/src/tokens.css`. The build writes both into the
committed dist. The server serves both pages from one session: `/` today's, `/next` the new.
`rietx gui --new` opens the browser at `/next`. Both pages talk to the same routes, so a project
open in one is the project in the other, and the 409 guards both.

A panel built to the prototype's design in an earlier piece (Parameters, Interactive, Plan,
Background, Start, New project, the File menu, Browse) is imported into the new frame and judged
there as part of its screen. Everything else is built new under `gui/src/next/`. Today's panels
are not edited for the new page's sake; a fix the new page needs in a shared panel moves that
panel into `gui/src/next/` first.

### The pieces

Each piece is a screen or a workflow, built new and judged whole beside the prototype at
1440 × 900. The order puts the frame first because every screen mounts in it, then the screen a
person spends most time in.

| Piece | What it builds | Inventory rows | Carries from |
|---|---|---|---|
| R1. The frame | the `/next` page and `--new`; top bar, status bar, the two side panels and the bottom panel with their toggles and sashes; the workflow menu, the File menu, Settings; the command palette and the keys; one menu component and one context-menu service every later piece uses; the start screen, New project and the recovery offer mounted in it; the Console | 1-24, 147-151, 212-242 | #1521 (`lib/statusbar.ts`, the Console's Copy and Follow), #1524 (`lib/workflows.ts`), the graph-window branch (`panels/Menu.svelte`, `lib/portal.ts`), #1522's style guard |
| R2. The refinement window | the Pattern graph (title line, legend gutter, view menu, the fitted range and excluded regions as plot objects, the plot's context menu, the hover readout in the status bar's right half, shown in the piece's screenshots); the Parameters tab with the phase and atom menus; the action bar with one Apply | 25-58, 83-97, 118-138 | #1518's slot widths; the graph-window branch (`lib/exports.ts`, `PatternChart.geometry`, its design) |
| R3. Hand fitting and the other graphs | the Interactive tab; the Peaks, Background and Structure graphs; the Instrument dialog | 59-82, 98-103, 133-136 | #1519 (the Structure tab's fetch-while-shown key) |
| R4. Plan and Text | the Plan tab with Free and Fix rows and stage menus; the Text tab whose edits ride the action bar | 104-117, 139-146 | #1520 (the routes' `turn_off`, merged) |
| R5. History and the report | the History table (WP-2211), Console lines by kind (WP-2212), the Report | 152-173 | WP-2211, WP-2212 |
| R6. Peaks and indexing | the workflow in four steps | 193-211 | #1526 (`src/rietx/gui/peaks.py`'s per-line curves, `lib/peaks.ts`, `PeakFits`) |
| R7. Series | the workflow in four steps, Trends and Map | 174-192 | the series routes; the series gaps in the owed list |
| Swap | `/` serves the new page; today's `App.svelte` and the panels nothing imports are deleted; `--new` goes | every row | — |

R1's order inside the piece: the frame and its menus before the start screen, since a menu
component built twice is the miss the owed list already names (the workflow menu copied the File
menu's drawing).

### The swap

The new page replaces today's when four things hold on one tree:

1. every inventory row whose home is not "removed" can be reached on `/next`, checked by a browser
   pass that walks the inventory and is recorded in the swap's PR;
2. the layout-shift browser test (acceptance row 1) passes on `/next` for every control;
3. the manual's GUI chapters are rewritten for the new page, and their screenshots retaken;
4. the maintainer has looked at every screen.

The swap deletes today's shell and its panels, so its PR waits on the maintainer's approval.

### Tests and the manual, piece by piece

- **vitest.** `gui/src/lib/*.test.ts` stays as it is, since the logic layer stays. Each piece adds
  mount tests under `gui/src/next/`. `gui/src/App.test.ts` and the old panels' tests go at the
  swap, with their components.
- **Browser tests.** Each piece adds its cases to `tests/test_gui_layout_browser.py` against
  `/next`; the cases against `/` go at the swap. `tests/test_gui_browser.py` follows the same
  rule. CI runs no browser test, so each PR quotes its local counts.
- **The manual.** Unchanged until the swap. The new page's tab names stay out of
  `tests/data/gui/panels.json` until then, so `tests/test_gui_manual.py` holds the chapters to the
  page a person gets by default. The `/next` route is listed among the route exclusions, with its
  reason. At the swap, `reference/gui-guide.md`, `reference/gui-power.md` and
  `start/gui-quickstart.md` are rewritten, `docs/docs/make_screenshots.py` drives `/`, and every
  GUI screenshot is retaken.
- **The rulebooks.** `gui/CLAUDE.md` gains a `gui/src/next/` line in R1. Its sections on deleted
  panels are pruned at the swap. `gui/STYLE.md` changes only where a piece settles a rule, and
  says so.

### How the maintainer reviews

The maintainer reviews whole screens, beside the prototype, at each piece's end, and never single
values. A piece's last PR carries whole-window screenshots at 1440 × 900, light and dark, beside
the prototype's at the same size, with any region in question boxed and a zoomed crop beside it.
The prototype's pictures are private, so they stay in the runner's scratch and the PR names their
paths. A small visual value (a gap, a weight, a word) is settled under `gui/STYLE.md` and the
prototype, and listed in the PR under "Settled by Claude". A question goes to the maintainer only
when the prototype and the guide do not settle it, by the triage in the maintainer's rules.

A piece that takes more than one PR merges its earlier PRs on green, because nothing on the
default page changes until the swap. The piece's last PR waits on the maintainer's look.

### What happens to the open GUI pull requests

| PR | Disposition | What carries into the rebuild |
|---|---|---|
| #1517, the palette (WP-2200) | merges tonight, as planned | `theme.py`'s tokens, the generated `tokens.css`, `tests/test_gui_palette.py` and STYLE's colour rules; the rebuild uses them as they are |
| #1520, a plan stage that fixes (WP-2208) | merges tonight | `StageSpec.turn_off`, the `fix` clause in `.rxt`, `turn_off` and `fixes` on `GET /api/plan/resolve`; R4 draws the Fix row against them |
| #1523, edit recovery (WP-2209; files WP-2213) | merges tonight | `src/rietx/gui/recovery.py`, its two routes, `lib/recovery.ts`; R1 redraws the dialog. WP-2213 (the Text buffer and the Model forms join the copy) gets smaller: in the rebuild a Text edit is a pending edit already, and the Model forms become dialogs |
| #1518, fit statistics in the action bar (WP-2210) | closes; the branch stays as a source | R2 takes the slot device (each number's slot as wide as its widest value, the judgement's room kept) and the words-in-danger-colour judgement |
| #1519, the Structure tab (WP-2203) | closes; the branch stays as a source | R3 takes the viewer's fetch-while-shown key and its empty state for a phase-free project |
| #1521, the status bar and the bottom panel (WP-2206, WP-2207) | closes; the branch stays as a source | R1 takes `lib/statusbar.ts` with its tests, the Console's Copy and Follow, and the first-run-moves-nothing browser case; WP-2211 and WP-2212 now build on R1's bottom panel |
| #1522, sentence-case headings (WP-2201) | closes; the branch stays as a source | R1 takes the `style.test.ts` guard against uppercase and tracked headings; the new stylesheet starts in sentence case |
| #1524, the workflow menu (WP-2204) | closes; the branch stays as a source | R1 takes `lib/workflows.ts` with its tests, and the placeholder screen's content |
| #1526, Peaks and indexing (WP-2202) | stays open as a source until R6 starts, then closes | R6 takes the server half (`PeakEditor.curves` serving each line, `tests/test_gui_peaks.py`), `lib/peaks.ts`'s step logic with `peaksteps.test.ts`, and `PeakFits` |
| branch `wp2213-the-graph-window` (head eaabe834f, no PR) | its WP number is retired, since #1523 files WP-2213; the branch stays as a source until R2 has taken what it needs | R1 takes `panels/Menu.svelte` and `lib/portal.ts`; R2 takes `lib/exports.ts`, `PatternChart.geometry` for the legend's positions, and the design its WP file wrote (legend gutter, view menu, regions as objects, context menu) |

A closed PR's branch and diff stay readable on GitHub, and each WP the closed PRs filed lives on
its branch and never reaches `main`. Its design is restated here and in the piece that takes it.
Deleting a branch is the maintainer's call.

## Questions

Answered by the maintainer on 2026-11-11, on PR #1529. Five rows of the inventory waited on the
maintainer. Each was a placement on the main surface the prototype did not draw, or a conflict
between two written rules. Each item keeps its proposal and ends with the ruling in the
maintainer's words.

1. **The Model tab dissolves** (rows 118-138). The prototype has no Model tab. Proposed: values
   stay in Parameters; structural edits (space group, rename, species, add or delete an atom,
   ADPs, Replace from CIF) move to the phase band's ⋯ menu and the atom row's context menu;
   source and geometry open in an Instrument dialog on the form New project already draws.
   **Ruled 2026-11-11: "Yes."** The proposal stands.
2. **The report's home** (rows 161-171). The prototype draws no report. Proposed: a Report tab in
   the bottom panel beside Console and History, its count of findings in the status bar, which
   opens it, as VS Code's Problems panel does.
   **Ruled 2026-11-11: "Yes."** The proposal stands.
3. **The status bar's right half** (rows 7, 8). Empty in the prototype. Proposed: the refinement
   mode and the σ source sit there, as VS Code shows a file's language and encoding, beside the
   report's count.
   **Ruled 2026-11-11: "No."** The right half shows the report's count of findings only. The mode
   and the σ source do not move there, because the maintainer's 2026-11-10 ruling dropped them
   from the header as clutter. Rows 7 and 8 now read "removed".
4. **What goes as chrome text** (rows 3, 4, 6, 37, 54, 81, 118, 120, 132, 138, 146, 157, 162, 175,
   179, 192, 199, 213, 247, 248). The list the 2026-11-10 ruling asked for. Proposed: each is
   removed, and an empty state keeps one line and its action.
   **Ruled 2026-11-11: "Yes, work it out as you go."** The audit list goes as one decision. Each of
   its rows is settled while its piece is built, under the "infoslop" ruling and the prototype,
   and listed in that piece's PR under "Settled by Claude".
5. **The hover readout** (rows 46, 74). `gui/STYLE.md` puts it in a strip under the plot; the
   prototype has none and says no readout restates the plot. Proposed: the status bar's right half
   reads the pointer's 2θ, d, intensities and hkl while it is over a plot, as ImageJ and Origin
   do, and the strip goes.
   **Ruled 2026-11-11: "Yes, but check it looks good when you build it."** The readout takes the
   right half in place of the findings count while the pointer is over a plot. R2's last PR shows
   it in its screenshots, boxed with a zoomed crop, for the maintainer's look.

## Settled by Claude

The calls a reviewer could have made the other way, most important first. Every other row of the
inventory follows the prototype or a written rule, named in its row.

1. **Panels already built to the prototype's design are imported into the new frame**
   (Parameters, Interactive, Plan, Background, Start, New project, the File menu). Grounds: each
   was ported from the prototype by WP-2126 to WP-2133 and merged, and a screen is judged whole
   either way. Alternative: rebuild every panel.
2. **The fit statistics, status bar, Structure tab, sentence case and workflow menu PRs close**,
   their branches kept as sources. Grounds: the ruling folds purely visual port PRs into the
   rebuild. Alternative: merge them into today's GUI for the months until the swap.
3. **A piece's earlier PRs merge on green; its last waits on the maintainer's look.** Grounds:
   nothing on the default page changes before the swap, and the ruling names per-change review
   as the cost. Alternative: every PR waits on a look.
4. **One page in the same build, served at `/next`.** Grounds: one session behind both pages,
   one dist, one `build_info.py` digest. Alternative: a separate package and dist, or a flag that
   swaps what `/` serves.
5. **Svelte 5 stays**, on the measurement in § The framework stays Svelte 5. Alternative: plain
   JavaScript, as the prototype.
6. **Simple and Advanced go.** Grounds: the maintainer's 2026-11-08 remark that an advanced mode
   is probably not needed, and the prototype has none. Alternative: the switch in Settings.
7. **The fitted range and excluded regions become objects on the plot.** Grounds: interaction
   rules 1, 3 and 4, and the graph-window branch's design. Alternative: keep typed fields in a row.
8. **Exports go to the plot's context menu and File › Export.** Grounds: Origin, Igor and Excel
   charts; the prototype's File › Export. Alternative: the view menu.
9. **Esc no longer cancels a run; ⌘. does.** Grounds: STYLE interaction rule 2 limits Esc to the
   gesture in progress, and ⌘. is the macOS cancel. Alternative: keep Esc as the last layer.
10. **`?` lists the keys, and the tab letters go.** Grounds: Gmail and GitHub; four of the five
    tabs they opened are gone. Alternative: keep them pointed at the new tabs.
11. **The palette stays, its button goes.** Grounds: VS Code has no button; the `?` boxes name ⌘K.
    Alternative: a button in the top bar.
12. **History is a table.** Grounds: the prototype and WP-2211. Alternative: keep the lanes.
13. **Log intensity stays, as a third option.** Grounds: today's GUI has it and one track holds
    one choice. Alternative: Linear and √ only, as the prototype.
14. **In the 3D view a click selects an atom and double-click resets.** Grounds: interaction
    rules 3 and 6. Alternative: double-click an atom to show its coordination, as today.

## Tasks

- [x] File the WP; the inventory; the plan; the dispositions.
- [x] `docs/milestones/gui-overhaul.md` rewritten to the rebuild.
- [x] `docs/practice.md` § Where a GUI keeps its secondary controls.
- [x] The maintainer answers § Questions (2026-11-11, on PR #1529).
- [x] R1 filed, once the answers are in, as [WP-2215](2215-the-frame.md). Each later piece is
  filed when its turn comes.
- [x] R2 filed as [WP-2216](2216-the-refinement-window.md).

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_docs_consistency.py tests/test_gui_manual.py
python3 .claude/hooks/wp_index.py
```

The WP closes when the maintainer has answered § Questions and R1 is filed.

## References

- The maintainer's rulings of 2026-11-06 to 2026-11-11, quoted or restated above; the milestone
  record `docs/milestones/gui-overhaul.md`; `gui/STYLE.md`; `gui/CLAUDE.md`.
- [WP-2123](2123-the-layout-shell.md) to [WP-2133](2133-the-file-menu.md), the port's pieces so
  far; [WP-2211](2211-the-history-table.md) and [WP-2212](2212-console-lines-by-kind.md), which
  now build on R1.

## Handover log

- **2026-11-11** — closed by the ghostshift runner that filed R1 as [WP-2215](2215-the-frame.md),
  the last task. Its acceptance holds: the questions are answered and R1 is filed.
- **2026-11-11** — filed by a ghostshift runner on the maintainer's rebuild ruling of the same
  night, in PR #1529. Every feature of today's GUI now has a written home in the new design, and
  the rebuild has an order of seven pieces and a swap. Five placements the prototype never drew
  wait on the maintainer; the rest are settled on the prototype, `gui/STYLE.md` or named
  practice, with the fourteen calls a reviewer might reverse listed in § Settled by Claude. No
  open WP owned the rebuild's plan: the milestone's tables had no row for it, and the
  graph-window branch covered one pane.
  - *Done*: the WP with its inventory (254 rows over `origin/main` at 68fd06973), the plan and the
    dispositions; the milestone rewritten to the rebuild; WP-2211 and WP-2212 re-pointed at R1;
    `docs/practice.md` § Where a GUI keeps its secondary controls; one ROADMAP sentence.
  - *How the inventory was made*: one subagent walked every panel, the keys and the palette
    (330 fine rows, merged here into 254); a second mapped the prototype's elements and its ways
    of hiding controls. Both maps are in the runner's scratch, `~/.cache/ghostshift/rietx/gui-rebuild/`,
    and the prototype map quotes private files, so it stays there.
  - *Measured*: `tests/test_docs_consistency.py` and `tests/test_gui_manual.py`, 36 passed, in the
    worktree's `[dev]` venv on darwin arm64. The CI Vale steps exit 0 (266 warnings, all in files
    this branch does not touch).
  - *Gotchas*: PRs #1517, #1520 and #1523 each edit the milestone's tables, so whichever merges
    second meets a conflict there. This branch's version already states their merged outcome, so
    the resolution takes this side and keeps their WP numbers as plain text until their files
    reach `main`, when they can become links.
  - *Next*: the maintainer answers § Questions. Then file R1, the frame, with the carry-overs its
    row names, and build it.
- **2026-11-11** — the maintainer ruled on the five questions, recorded in § Questions with the
  words: yes to 1, 2 and 4, no to 3, yes to 5 with a look once built. A ghostshift runner wrote
  them in and merged `main` into the branch, which conflicted nowhere.
  - *Done*: § Questions answered; rows 7 and 8 now read "removed", since the status bar's right
    half shows the findings count only; rows 46 and 74 and R2's row name the look the readout
    gets; the status line, the task list and the milestone's R1 row follow.
  - *Next*: file R1, the frame, with the carry-overs its row names, and build it. Each row of
    question 4's list is settled while its piece is built.
