# WP-1017 — GUI manual, in-app help, onboarding

Milestone: post-v1.0 (deferred) · Status: ⬜ — deferred 2026-08-14 past the
public release; the GUI ships as a **beta** feature until it lands
Depends on: WP-1011…WP-1016 (soft — chapters can land as their panels do)

## Goal

The GUI is documented where the theory manual lives, helps from inside the
app, and onboards a first-year PhD student without a wizard that hides the
real UI.

## Deferred past v1.0 (2026-08-14, user decision)

**The GUI keeps moving, so documenting it now buys a rewrite.** The intent is
to keep working on the GUI *after* the public release and document it once the
panels settle; until then it ships **as a beta feature**, said out loud in the
README and the release notes rather than left for a user to discover. The
evidence for the decision is this file's own `### Inherited`: eight separate
sessions have written "three sentences in this manual are now wrong" into it
since 2026-07-30, and the mailbox is still growing.

Two consequences that are not this WP's to carry:

- **[WP-1067](1067-user-api-manual.md) is the manual that ships with v1.0** —
  Part 1 (using the library and its API) beside the theory manual as Part 2.
  It declares the GUI's beta status in the README and names `rietx gui` in
  one line in its CLI chapter, with **no walkthrough**, so this WP keeps the
  whole GUI documentation surface.
- **1017 no longer blocks [1003](1003-api-freeze-pypi.md)**. The freeze's
  dependency range was written when the manual was the milestone's last GUI
  row; the note is in 1003's `### Inherited`.

When this WP is picked up, prune the mailbox below against the GUI as it is
*then* — most of it will be about panels that have moved again, and the whole
point of deferring was to stop paying for that.

## Context

- **Inside `docs/manual/`** — same Sphinx/MyST/furo tree, same `-W`, same
  guards (`tests/test_manual.py`); a separate doc root would need its own
  guard set for no benefit. Three layered chapters matching the audience
  gradient:
  - `gui-quickstart.md` — install (`pip install rietx[gui]`) → open →
    fit → read the report.
  - `gui-guide.md` — panel by panel, including *when to branch* (the
    history worktree is the differentiator; teach the workflow, not just
    the buttons).
  - `gui-power.md` — the **normative `.rxt` text-format spec**,
    keyboard/palette, and the console-to-script transition — the API-echo
    story as the on-ramp to the Python API.
- The manual's anti-divergence rules apply and are executable
  (`tests/test_manual.py`): fenced constants are MyST substitutions
  injected from the live package in `docs/manual/conf.py` — **the rxt
  format version becomes a fenced constant injected from
  `gui.textdoc.FORMAT_VERSION`**, so a format bump that misses the manual
  fails the build. A new fenced constant needs a `conf.py` line *and* a use
  in a chapter.
- In-app help: tooltips from `static/help.json`, each with a "learn more"
  anchor into the built manual; `tests/test_gui_help.py` asserts every
  anchor exists (dead-link guard, same spirit as `test_manual.py`).
- First run: a **non-modal progressive checklist** (Load pattern → Load
  structure → Check instrument → Run → Read the report) — never a modal
  wizard; state in `ProjectDoc.ui`.

### Inherited

**From [1078](1078-indexing-provisional.md), 2026-08-18 — a chapter that
documents a name now freezes it, and there is a mechanism for saying it does
not.** Two things to carry when the GUI chapters land. First, the rule the
compatibility chapter states is live and enforced: any *Python* name a Part 1
chapter spells is promoted from provisional to frozen by the release that
documents it, so a GUI chapter that names library API is making a promise on
its behalf. Second, the way out is no longer prose — `PROVISIONAL_MODULES` in
`tests/api_surface.py` declares a subsystem by **module prefix**, the tier
derives from each name's defining module, and `provisional_names()` is the set.
Whether the GUI's Python surface wants an entry there is a question for
whoever writes those chapters; the GUI's *beta* declaration in
`using/compatibility.md` § Provisional by declaration already covers the routes
and the `.rxt` document, and it now carries a `(provisional-by-declaration)=`
target. A chapter documenting a declared-provisional name **must** `{ref}` that
target — `test_the_provisional_promise_reaches_the_chapters_that_document_it`
fails otherwise, derived over the pages rather than a list of page names, so a
new GUI chapter is covered by it the moment it exists.

**From [1067](1067-user-api-manual.md), 2026-08-14 — the beta declaration is
landed, and this WP is now named in public.** README declares the GUI a beta
feature, names `rietx gui` for the first time (it had never appeared there at
all, so a reader could not have discovered the GUI, let alone its status), and
links *this file* as the deferred manual. Two consequences. **The tree you will
write into already exists**: `docs/manual/` is one Sphinx build in two captioned
parts, Part 1 under `docs/manual/using/`, so GUI chapters are a third toctree
or additions to Part 1 rather than a new doc root — and `tests/test_manual.py`'s
`CHAPTERS` is already an `rglob`, so a new subdirectory inherits the `-W` build
and the bib/source guards for free. **The prose-drift problem this WP's mailbox
records eight times now has a mechanism**: `tests/test_manual_api.py` resolves
every dotted name and parameter dot-path a Part 1 page spells and executes its
python blocks, so a panel rename breaks the suite rather than the reader's
trust. Whether a *GUI* chapter can be guarded that way is an open question — its
subject is routes and panels, not importable names — and worth answering before
writing prose, not after. Nothing of this WP's own mailbox was absorbed by
1067, per its non-goal.

**From [1062](1062-rename.md) and [1066](1066-rename.md), landed 2026-08-12 and
renamed again 2026-08-14 — the name is settled at `rietx`, and this WP writes
the most user-visible prose in the repo.** The
distribution, the import and the CLI are all `rietx`; the **format tokens are
deliberately not** — a project directory is `.rex`, the text document `.rxt`
(header `rxt N`), and an instrument profile is tagged plain
`instrument_profile`, because those are versioned contracts and a contract must
not move when a brand does. So do not write `.rietx` anywhere, and where you
need the name in code import it from `_about.py` (`DIST_NAME`,
`PROJECT_SUFFIX`, `TEXTDOC_MAGIC`) rather than spelling a literal.
`tests/test_no_stale_name.py` fails on a reintroduction of the old name, but it
greps the **old** token only — it cannot tell you that a *new* literal should
have been an import.

One thing that lands on this WP permanently: **rietx is also a phase this
software analyses** (0 occurrences today, but `rutile` — the other TiO₂
polymorph — appears 168 times in the QPA test data, and rietx/rutile is the
canonical QPA pair). The manual and onboarding copy need a disambiguation
convention from the first public page: the phase as `rietx (TiO₂)`, the
package in code formatting. Screenshots are the expensive half, and 1062 has
landed, so they can be taken now — every panel, title bar and wizard hint
already reads the new name.

**From [1051](1051-sequential-escalation.md), closed 2026-08-09 — the Series
tab's status column has four chips now, and two of them are new words.** A
rejected warm fit escalates a rung at a time instead of jumping to a cold refit,
so a row can read **restaged** (the full staged plan recovered it, still from the
neighbour's answer — the chain is *unbroken*, which is the point of the chip) as
well as **reseeded** (only the cold rung won), **hard** (nothing rescued it but a
warm attempt was still best) and **unrecovered** (diverged on every rung; the
chain stepped over it, so it seeded no successor and joined no median). The
trajectory plot marks the last of those with a **cross** where a reseed gets a
ring, and the two say opposite things — a ring is a good fit from a different
starting model, a cross is not a measurement. Worth teaching as a pair rather
than listing as four chips.

**From [1047](1047-vendor-pattern-formats.md), in flight 2026-08-08 — the
import wizard's pattern step changed shape, so any screenshot or walkthrough
of it written before this lands will be wrong.** Two changes: (a) the single
"data block" input is gone; the step now renders **one control per reader
option the claimed format declares**, from
`capabilities().reader_options` — so a multi-scan vendor format grows a `scan`
picker with no frontend change, and the chapter should describe the mechanism
rather than enumerate the controls. (b) The preview now shows the reader's own
**diagnostics** (a scan stored high→low and reversed, a duplicated point
dropped, an option that did not apply). That strip is the teachable moment the
onboarding chapter wants: it is where a student sees that opening a file is a
decision with consequences, before it becomes a project. Also worth a sentence:
a binary vendor file and a `.dif` peak list are now refused **by name**, so
"why won't my file open?" has an answer the app gives rather than one the
manual has to.

**Updated 2026-08-09 (1047 tasks 10-12).** Five vendor formats now read
(`.ras`, `.rasx`, `.uxd`, `.xrdml`, `.brml`), nine in all, so a chapter that
lists formats will go stale between sessions — quote `capabilities()`, which
carries each format's own `sniff` and `sigma` prose for exactly this. Two of
those readers **change the numbers**: a PANalytical beam attenuator is applied
and a Bruker absorber's factor goes into σ, each with a diagnostic saying so, so
the preview's diagnostics strip is no longer only about repairs — it is
sometimes about a 188× correction. That is the sharper version of the teachable
moment above, and worth the chapter's one worked example.

**Updated 2026-08-09 (1047 closed).** **Ten** formats read now — Bruker `.raw`
joined the list — so the "quote `capabilities()`" advice above is the whole of
what a chapter should say about *which*. Two additions the pattern step itself
grew, both worth a sentence rather than a screenshot:

- the step **pre-fills the instrument form from the file's own header** when it
  can (anode, and goniometer radius where the file records one), with a line
  saying *why* it chose what it chose. The teachable point is the case where it
  says nothing: a header whose anode name and wavelength disagree gets **no**
  suggestion, because a wrong pre-fill looks like it was read. That is the same
  lesson as the diagnostics strip, one control over;
- a multi-scan file's `scan` control is now a **picker with labels** rather than
  a number box, and the labels arrive from their own route when the control is
  opened. Worth a sentence because the reason is visible to a student: "scan 1"
  says nothing, and a vendor file commonly holds a whole session rather than a
  pattern.

**From [1050](1050-suggest-next-parameter.md), closed 2026-08-08 — the
"what next?" panel this WP's non-goal deferred now has its engine.**
`Refinement.suggest()` is read-only (no history node, no mutation), so a
GUI verb wrapping it does not belong behind the run-in-flight 409 that
mutating verbs carry — the WP-1044 theme-setting reasoning, one verb over —
though it costs two compiles plus two Jacobian builds, so it is a click,
never a keystroke. `SuggestionResult.summary` is one deterministic sentence
built for exactly this surface; groups carry `resolved`/`seeded`/
`absorption` and the Layer-2 `action_kind` agreement for richer rendering,
and an unresolved group must render as the tie it is, never as its top
member.

**From [1045](1045-indexing-search-controls.md), closed 2026-08-08 — the
Peaks tab gained the Search controls disclosure, and nobody has watched a
person use it.** The form renders `ProjectDoc.indexing` (engines/systems
checkboxes with per-system centring chips, preset and shift-template
selects, the numeric bounds and budgets, two prior editors), every control
carries a `title` (its only documentation today), commits are whole-object
on the verb, and streamed per-system shortlists render during a run. Three
onboarding concerns filed unexamined: the centring chips inside the systems
row and the six-number prior-cell input have never been driven in a real
browser (the WP-1027 playwright route is the tool); the priors story —
"state what you know", the calcite example in AGENT_PROTOCOL §7d — is
exactly onboarding material and exists only in the operator guide; and a
`prior_spacegroups` typo is refused server-side in gemmi's words, which the
manual should set expectations for. Also note validation starvation under
`quick` is *gone* (the 1042 note below predates the reserve): heavy
patterns now stream `INDEX_BUDGET_EXHAUSTED` with a validated shortlist.

**From [1042](1042-anytime-results-quick-default.md), closed 2026-08-07 —
the Index button's behaviour changed under the manual's feet.** A GUI index
run now resolves the `quick` preset (a 120 s whole-run ceiling — the fix for
the first-click hang the 15-line lists caused), streams
`elapsed_seconds`/`remaining_seconds` and per-completed-system graded
shortlists on the run's stage events, and can report
`INDEX_BUDGET_EXHAUSTED` with validation starved on heavy patterns. The
manual's indexing section should say what the ceiling means, that `low` from
a truncated run is "unconfirmed", and that the full search is one
`preset="full"` rerun away (a control WP-1045 owns adding to the panel).

From **[1044](1044-gui-view-cursor-theme.md)**, 2026-08-06 — **three sentences
in this manual are now wrong, and one gesture wants documenting.**

- **The theme is not a project setting.** It lives in the app's own store
  (`/api/settings`, beside the recent list), so it follows the person across
  projects, ports and browser profiles — and it is the one setting that is *not*
  refused while a run is in flight. The note below saying a `ui` drag is refused
  mid-run still holds for the widths and Simple/Advanced; it no longer holds for
  the theme. The control is also in the header of the **empty state** now, which
  is the screen a first-time user starts on — worth using in the onboarding tour.
- **Zoom is a fetch and it now stays where it is put.** A drag refetches that 2θ
  window at full point budget, a peak edit or a knob keeps the view (it used to
  reset it), and **double-click means "all of it"** — that is the sentence to
  teach, because the modebar's home button is easy to miss.
- **The armed range/exclude gesture has its own cursor** (`col-resize`); the
  screenshot of the strip should show it armed at least once, since "arming
  changes what a drag means" is the least discoverable thing on the plot.

From **[1016](1016-sequential-series-panel.md)** (closed 2026-08-05) — **there
are nine tabs now, and the ninth is the one panel whose subject is a *method***.
Four things to document rather than list.

- **A series is N separate refinements chained by a warm start**, not one joint
  residual, and the manual has to say so before it says anything else — a reader
  who thinks it is a multi-pattern fit will misread every trajectory. It runs
  under *this project's* protocol (mode, plan, 2θ limits, excluded regions) and
  warm-starts from the current model, which is why the panel states those rather
  than offering them.
- **`direction="both"` is the thing to teach, and it costs a second pass.** It is
  the only check that separates a measured trajectory from an ordering artefact,
  because a smooth curve is exactly what a poisoned chain produces (WP-0505). The
  panel banners `SEQUENTIAL_PATH_DEPENDENT`, dashes the flagged trajectory in the
  warning colour and draws the backward chain beside it — the onboarding line is
  "run it both ways once, then decide whether you need to keep paying for it".
- **A series does not persist**, and this is the one absence a user will notice:
  its patterns are staged uploads and its answer is session-scoped
  (`ProjectDoc.patterns` stays length 1), so closing the window loses the staged
  list. Say it plainly rather than letting it be discovered; the fix is a document
  and it is WP-1003's call.
- **Two controls are behind Advanced because they are measured results, not
  preferences** — `refit="single"` (904 iterations against 1623 for re-walking the
  staged plan, same answer to three decimals) and `carry=["*"]`. `carry` is a
  control for a parameter that provably must not chain; the panel already carries
  that sentence as its help text, so quote it rather than paraphrasing.

Also: the **Build panel's owed list is now empty** ("None — every panel the v1.0
GUI plan named is built"), so any screenshot or walkthrough that showed a
"Series (WP-1016)" row is stale.

From **[1032](1032-gui-repairs.md)** (closed 2026-08-05) — the three sentences
below were forecast by the use-session note that follows; two are now facts and
one is not this WP's to state:

- **Right-click removes a line**, refit is the peak table's `↻`, and the
  component-count prompt is gone from the app entirely (the count survives only
  through the `.rxt` peaks block). The plot now prints the four gestures
  whenever the Peaks tab is up, each naming its non-pointer route — so the
  manual's job there is to *not* repeat that line, and to explain the one thing
  the screen cannot: why every pointer verb has a typed twin.
- **Per-curve visibility toggles** exist and are deliberately unpersisted, next
  to the residual and scale knobs. The paired half of that sentence — the fit
  range and excluded regions *are* persisted — landed with
  [1033](1033-plot-range-regions.md) (below).

From **[1033](1033-plot-range-regions.md)** (closed 2026-08-05) — the strip
below the plot is now a second register of control, and the manual's job is the
distinction rather than the list:

- **Two kinds of knob sit on one plot and only one changes the answer.** The
  residual selector, the scale and the curve toggles are drawing choices and are
  not stored; the fitted range and the excluded regions change what is fitted,
  persist in `project.json` the moment they are set, and move Rwp. That is the
  sentence to write, and the screen can only *imply* it through the separating
  rule and the typed fields.
- **A fifth pointer gesture exists and it is a mode**: `⇥ range` / `✂ exclude`
  arm a drag, suspend the peak verbs while armed, and disarm after one
  selection (Esc cancels). Worth explaining *why* it is armed rather than
  modifier-driven — a region drag and a zoom drag are the same gesture at every
  distance — because that is the difference from the peak verbs one paragraph up.
- **Two numbers on that strip answer questions the manual would otherwise have
  to**: "N of M channels fitted" is what makes a shaded band checkable, and
  "the curves shown were fitted over a different set of channels — re-run"
  is the app saying that settings persist immediately while curves do not.
- The masked channels are drawn recessively under the shading and have their own
  `masked` curve toggle; the exported PNG/HTML deliberately do **not** shade
  (grounds in 1033's file), which is a difference a manual should state once.
- Two new things to document that the forecast did not include: the reflection
  ticks now have a **band of their own** between the two subplots (so "the ticks
  vanish under Σχ²" is no longer true and should not be written as a caveat),
  and **hovering a peak row lights it on the plot and vice versa**.

From **[1034](1034-panel-layout.md)** (closed 2026-08-05) — the chapter's
opening two sentences, and one thing the screen cannot say:

- **There are eight tabs and no modes.** `Parameters | Plan | Peaks | Model |
  Text | Report | History | Build`, all beside the plot, all mounted at once;
  the header's `Split | Full` chooses only how much window the *column* gets,
  and the tab strip travels with it. So the "[ Plot | Model | Text ]" sentence
  the WP-1029 note below asks for is gone, and what replaces it is: where you
  are is the tab, how wide it is, is the layout.
- **An edit empties the plot until the next run, and that is the design.**
  Applying a value discards the fitted curves server-side, because they
  described the values the model no longer holds — so the workflow to teach is
  *edit → Run → compare*, not *edit → watch*. The manual is the only place this
  can be said; the app can only show the empty state's own "Press Run".
- **Two widths are worth quoting once** (measured, 1034 task 1): the `.rxt`
  document's editable columns need 546 px and its comments 756, and the atom
  table needs 472 — which is why the Text and Model tabs get a wider column, or
  `Full`, when a rectangular selection or an eight-column table is the job.
- **`Open…` in the header** opens the wizard with a recent list in it. Say what
  it does to the session: it replaces the open project, and nothing is unsaved
  because settings persist on the verb.

From the **2026-08-04 use session**, which created
[1032](1032-gui-repairs.md), [1033](1033-plot-range-regions.md),
[1034](1034-panel-layout.md) and [1035](1035-symmetry-surfaced.md): **do not
write the panel-by-panel chapter until those land.** All four change controls
this chapter documents, and one of them ([1034](1034-panel-layout.md)) moves
Model and Text out of full-window modes and into right-panel tabs — which
rewrites the paragraph the WP-1029 note below asks for, and with it the
"[ Plot | Model | Text ]" sentence. The quickstart and the `.rxt` spec chapter
are unaffected and can be written now. Three things those WPs will hand over
that a manual must state: the peak picker's **right-click will remove** a line
rather than refit its group (refit moves to the table's `↻`), the plot gains
**per-curve visibility toggles** that are deliberately *not* persisted while the
**fit range and excluded regions** beside them *are* (one is a drawing choice,
the other is protocol), and a phase's **symmetry becomes editable** with a
preview of what the change would invalidate.

From **WP-1027** (closed 2026-08-01), extending the note below: the browser
pass changed two behaviours the manual should state, and the extinction
screen landed. **A drag only moves a line once you are zoomed in enough for
the line to be visible** — the move grab radius is min(10 px, 1.5× the median
FWHM), so at the survey view a drag is always plotly's zoom (tell users:
zoom first, then correct); shift-click and right-click keep the coarse 10 px
aim. **"Screen extinctions" lives in a candidate's expanded detail row** and
serves WP-1025: one table, one row per extinction class, every space group in
the class listed, ΔBIC against the absence-free reference, refuting hkl named
— and the space-group chips become adopt buttons only when the candidate
itself passes the adopt gate. The teaching point is the package's own: the
extinction *symbol* is what a powder measures; a single space group is a
convention the user chooses, never a measurement the table makes.

From **WP-1027** (peak picker + indexing panel, 2026-07-31): **the GUI grew its
indexing surface, and it is gesture-driven — the manual must name the
gestures.** The Peaks tab plus four plot interactions (click empty = add a
peak, drag a marker = move, shift-click = exclude/overrule, right-click = refit
the group), each with a non-pointer route that the docs should surface for
accessibility: a typed add-at-2θ box in the panel, and the `.rxt` peaks block
whose only editable columns are `2theta` and `flags` (everything else derived
and refused). Three reading rules worth a paragraph each: `not_separable` lines
render distinct rather than hidden (the fitter's own explanation of a strong
peak's shape) and the use-for-indexing checkbox is the overrule; a pasted
position list is badged "σ assumed" and its σ(Q)/Q is not a property of the
data; and the candidate table is abstention-first — `best_or_none()` is a badge
on a ranked list, never a headline, with Adopt driven by the server's per-row
verdict and adoption landing as a Le Bail scaffold that flips the mode.

From **WP-1029** (GUI usability, landed 2026-07-30): **the controls this chapter
was going to document have changed, which is why 1029 landed first.** Read the
list below *before* the WP-1015 note underneath it — several of that note's
sentences describe controls that have moved.

- **One top-level selector**, `[ Plot | Model | Text ]`, a segmented control in
  the header. The old pair of toggle buttons is gone, and so is the `Close`
  inside each pane: there is now exactly one control for that choice, and every
  option is named for where it lands you. The five-wide strip
  (Parameters/Plan/Report/History/Build) is unchanged and is the sidebar's tabs
  *within* plot mode — a distinction worth one sentence, since both look like
  tab strips.
- **Panes are draggable and the widths persist** (`ProjectDoc.ui`): the
  plot/sidebar split and the Model pane's first two columns. Until dragged they
  are responsive defaults, which is the behaviour to describe — a manual should
  not print a pixel width. One caveat a user will hit: a drag is refused while a
  run is in flight (see WP-1003's `### Inherited`).
- **A three-way theme** — system / light / dark, in the header as ◐ ☀ ☾. Worth
  a sentence on *why* three: "system" keeps following the machine at dusk, and
  an explicit choice keeps overriding it.
- **The plot has two new knobs.** A residual selector (Δ, Δ/σ, **Σχ²**) and an
  intensity scaling (lin, √, log). Two of these need explaining rather than
  listing. **Σχ² is the one to teach**: a flat stretch contributed nothing and a
  step is where the misfit is, which answers "where is my fit bad?" better than
  any Rwp. And **√ is drawn on the data with the axis relabelled in intensity**,
  so it is the same numbers seen differently, not a different dataset.
- **The 3D drawing knobs are behind a `drawing` disclosure**; only the mode
  buttons and *view down a/b/c* stay in the open. The WP-1015 note below
  describes the bond threshold as if it were on screen — it is one click away
  now, and it is still the one control a first-time user needs.
- **Ellipsoids gained an exaggeration factor, and the manual must not call it a
  probability.** k(p) = √χ²₃(p) diverges as p → 1, so there is no ellipsoid
  above 100 %; "× size" is a drawing scale, the caption prints both figures, and
  a figure exported at a multiplier ≠ 1 is **not** an ORTEP-quotable surface.
  That last clause is the sentence worth writing, because an ORTEP figure's
  quoted probability is the whole reason the number is on the plot.
- **A hopeless fit now says so.** Past `MATURITY_MAX_RWP` (0.35) the header
  shows `⚠ not a fit yet` beside Rwp and links to the Report; the pill still
  reads `converged`, because that vocabulary is WP-1028's. If both are on
  screen at once the manual should say which to believe and why.
- **Element colours are decided per phase**, not per element, so *the same
  element can be drawn in different colours in two different phases* — the
  anchors (H C N O S P F Cl Fe) never move, the rest are separated in OKLab
  against whatever else is in that phase. Worth one sentence, because a reader
  comparing two phase views will otherwise think something is wrong.

From **WP-1015** (structure viewer, landed 2026-07-30): **there is a 3D view, and
its two knobs are the part a manual has to explain.**

It is a **third column of the model pane** (not a tab, not a window), toggled by a
`3D` button in that pane's header and on by default. Two modes: *balls* (spheres
at 0.40× the covalent radius — the shape of the structure) and *ellipsoids*
(displacement ellipsoids at a selectable probability, default 50 %). Everything
geometric is computed server-side by `GET /api/structure3d`; the client draws.

Three things the second pass (2026-07-30) added that a manual should name, all of
them conventions rather than features. The projection is **parallel**, not
perspective, and there is **no Cartesian axis box** — the cell's own edges are
labelled a, b, c, and they are the picture's frame of reference. Rotation is a
free trackball (Jmol's and VESTA's, not plotly's z-locked turntable), with **view
down a / b / c** buttons that snap to the three projections a structure is
normally drawn in, and *reset* for the opening view. And a bond is drawn as two
half-cylinders **coloured by the atoms at each end**, which is worth one sentence
because it is how a reader tells which two species a stick joins without hovering
— and because switching a species off in the legend takes its half-sticks with
it.

What the manual owes it is the two things a user will otherwise misread.
**The bond threshold is a drawing threshold, not chemistry**: a bond is drawn at
d ≤ tol·(rᵢ+rⱼ) on covalent radii, no fixed value is right for both a large cation
and an organic (LaB6 at 1.15 draws every La–B contact and looks like a cage; at
1.05 only the B₆ framework survives), and metal–metal contacts are suppressed
unless the phase is all-metal. It is also the one control a first-time user
*needs*: LaB6 at the default 1.15 draws 210 stick segments and 109 out-of-cell
neighbours, and one turn of the slider to 1.05 turns that into the B₆ octahedron
in a cell. **The ellipsoids are a diagnostic, not
decoration**: their axes are refined quantities, so an over-flexible background —
which improves Rwp while inflating ADPs (CLAUDE.md's block projection R²) —
arrives here as balloons, and a non-positive-definite tensor arrives as a flat
disc with the reason in its hover. Measured on NAC: Na1's Biso of 2.16 Å² against
Al's 0.59 is obvious in the picture and is six ordinary-looking numbers in the
parameter table. That contrast is the best onboarding argument the GUI has for
why the view exists at all.

Costs, measured on an M4: nothing at boot (65–99 ms, unchanged), and 605–1447 ms
from clicking *Model* to a drawn scene — almost all of it fetching and parsing
plotly. Worth a sentence, because a first-time user clicks *Model* and waits a
second.

From **WP-1014** (import & in-GUI editing, landed 2026-07-30): **the onboarding
path now exists and is the empty state.** With no project open the app renders the
import wizard itself (`panels/Model.svelte`, the same component that is the model
editor when a project *is* open), so "how do I start?" is answered by the screen
rather than by a manual page. What the manual owes it is the part the wizard
cannot say in a form: why the instrument step refuses to default (an anode nobody
chose becomes a wavelength in every refined cell), what the aniso opt-in actually
changes (which parameters a plan frees), and why the pattern step names a
*reader* rather than a file type.

Also: the wizard's own copy is deliberately terse and every step already carries
its "why" as a `title` or a muted line — if the manual repeats those sentences
they become two authorities. Link to them instead, or move them.

From **WP-1013** (landed 2026-07-30): the **text pane** is the surface this manual
has the most to explain, and three of its facts are not discoverable from the UI.
It is a *mode*, not a tab — the header's `Text` button and the palette's `t` — so a
chapter that walks the tabs will miss it entirely. `⌥`-drag is a **rectangular
selection**, which is the entire reason the `.rxt` format aligns its columns, and
the pane's footer says so in one line that a manual should expand rather than
repeat. And **a re-render discards the user's own comments**: the pane warns when
the buffer has gained comment lines, but the flow ("apply, then re-read") wants
stating once, properly.

`textdoc.FORMAT_VERSION` is still owed to this WP as a **fenced constant**
(WP-1009's own note says a bump that misses the manual must fail the docs build),
and the `.rxt` grammar chapter should quote `gui/src/lib/rxt.ts`'s token
vocabulary rather than restating it — that array is already pinned to
`textdoc._KEYWORDS` by `test_textdoc.py::test_the_highlighter_quotes_the_parsers_words`,
so a manual that quotes it inherits the guard.

One sentence is worth carrying verbatim into the conflict/undo chapter, because it
is the pane's whole safety story: **there is no merge and no force-apply** — a
document regenerated from state has one authority, so a stale buffer re-reads and
re-applies. The reason is sharper than "merging is hard": the loser's document also
carries the winner's *old* values for every row it did not touch, so applying it
anyway would silently revert them.

From **WP-1011** (landed 2026-07-30): **the command palette is already the
manual's index, and it is executable.** Cmd-K lists every command with the Python
call it makes (`ref.set_vary(glob, True)`, `ref.run_stage(stage)`,
`project.doc.ui["simple"]`), and the console echoes the same string when a control
is clicked — so the chapter that teaches "the GUI is a front for the API" should
quote the palette rather than restate it, and any command added later appears
without the manual being edited. The shortcut set to document is `r` run, `.` run
the selected stage, `Esc` cancel, `f`/`x` free/fix the filtered selection, `/`
focus the filter, Cmd-K palette.

Two things the onboarding path must say plainly, because both are surprising and
both are deliberate. **The filter box is the selection** — a bulk free acts on the
glob, not on ticked rows, because one glob is one history node. And **Simple mode
hides the rows nothing can free** (locked, tied, mode-fixed) along with bounds and
transforms; it reports the count it hid, and Advanced brings them back.

From **WP-1012** (history/report panels, landed 2026-07-30): the palette gained
`?` (report) and `h` (history), and there are now **five things the report panel
says that a user will misread unless the manual says them first** — every one is
the FitReport's own design showing through, so this chapter is where they get
explained rather than in tooltips:

- **A suggestion with no Apply button is not a broken button.** Four `ActionKind`s
  are advice (`report/apply.py`'s `RECIPES`), and the note beside them *is* the
  action. The two background-flexibility ones are the interesting case: they are
  advice because a more flexible background lowers Rwp *while* biasing ADPs up and
  scales down, and the statistic that catches it (`BACKGROUND_ABSORPTION`) is not
  in the report — so there is no honest one-click version.
- **A greyed suggestion with "vetoed:" is the engine agreeing with you and having
  already handled it.** Worth a sentence, because it looks like a refusal.
- **"could not rule out" is the headline, not a footnote.** Measured on the WP's own
  fixture: applying `refine_zero_shift` on a fit whose *cell* was wrong improves Rwp
  from 21.6 % to 9.3 % by putting the error in the wrong parameter, and the report
  said so in advance (confidence capped at 0.5, both templates listed,
  `separable=false`). This is the best worked example in the repo of why the
  never-a-confident-wrong-singleton rule earns its keep — use it.
- **The predicted Δχ² is one number for the whole report**, not per suggestion, and
  it is not a bound (16.19 predicted, 16.33 observed for a cell correction). The
  panel prints it once and says so; the manual should explain why it cannot rank.
- **Undo is a checkout**, and a checkout throws the fitted curves away because they
  described the values it replaced. Users will read the empty plot as a crash.

One onboarding fact: **boot-to-interactive is 104–200 ms** measured in Chrome for
Testing (load → the parameter table's first row), so "it feels instant" is a claim
this chapter may make.

From the **v1.0 GUI plan** (2026-07-29): `gui-power.md` is where the
provisional status of the HTTP routes and `.rxt` format is stated
user-facing (schemas frozen at v1.0, wire/text surfaces provisional) —
WP-1003 states it in the release notes; this chapter is the other half.

From the **indexing plan** (WP-1018…1027, added 2026-07-29): add an
**indexing walkthrough** as an onboarding path — it is the natural entry point
for a user with a pattern and no CIF, which is the audience least served today.
`docs/manual/indexing.md` already exists from WP-1020 for the theory; this
chapter covers the panel (WP-1027). The one thing the walkthrough must teach
rather than gloss is that **a candidate list with no high-confidence entry is a
result, not a failure** — the whole module is built so that "the data cannot
distinguish these" is sayable, and a user who reads that as a bug will go
looking for a setting to force an answer.

From **WP-1009** (text document, landed 2026-07-30): `gui.textdoc.FORMAT_VERSION`
is the fenced constant this WP was asked to inject into the manual (the `rxt 1`
header line), and `gui.textdoc.VALUE_DIGITS` is worth injecting beside it — the
manual has to state that the text view renders **12 significant digits and is
lossy**, and why that is safe (a typed number is compared against the rendered
current value, so an unedited apply is a no-op). Two more things a manual chapter
should say because they are decisions, not accidents: comments in the text pane
do **not** survive a re-render, and a glob line like `profile.* @` is bulk sugar
that the next render expands into one line per parameter.

From **WP-1010** (frontend scaffold, landed 2026-07-30): the app's help text has a
home — `panels/Stubs.svelte` is where "this build can do X" is rendered from
`capabilities().features`, whose flags are derived predicates, so an in-app
capability list cannot drift from the package. Two constants worth injecting into
the manual beside the textdoc ones: the dist is **committed** (a manual chapter
should say `npm --prefix gui run build` is only for contributors, never for users)
and plotly is served from the installed package rather than bundled, which is why
`[gui]` is a plotly-only extra.

## Non-goals

- No screencasts/video, no hosted docs decisions (that is WP-1003's
  release scope).
- No autodoc API reference (0604's decision stands — a rendered API
  reference is its own document with its own failure modes).
- No restating theory — the GUI chapters link into the existing theory
  chapters rather than duplicating equations.

## Tasks

- [ ] `gui-quickstart.md` + toctree wiring; builds `-W`-clean.
- [ ] `gui-guide.md` — panel by panel, when-to-branch workflow section.
- [ ] `gui-power.md` — normative `.rxt` spec with `FORMAT_VERSION` as a
      fenced constant (conf.py line + chapter use), keyboard/palette table,
      console-to-script story.
- [ ] `static/help.json` + tooltip wiring + "learn more" anchors;
      `tests/test_gui_help.py` dead-link guard.
- [ ] First-run progressive checklist (non-modal), persisted dismissal.

## Acceptance

```sh
.venv/bin/python -m sphinx -W -q -b html docs/manual docs/manual/_build/html
.venv/bin/python -m pytest tests/test_manual.py tests/test_gui_help.py -q
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-0604's manual architecture (fenced constants, `*Source:*` lines,
  cited-bib guard) — the machinery these chapters extend.

## Handover log

- **2026-08-14** — **deferred past the public release** (user decision): the
  GUI ships as a beta feature and gets its manual once the panels settle.
  Done: Status line, milestone field and the ROADMAP row moved to a new
  "Post-v1.0" section (shared with 1067, whose § Floor still gates the
  release); § Deferred added above with the grounds and the two hand-offs. Next: nothing here until post-release — the successor is
  [1067](1067-user-api-manual.md), which carries the README's beta
  declaration and the one-line `rietx gui` mention, and 1003, whose
  `### Inherited` now records that this WP no longer blocks the freeze.
  Gotcha for whoever returns: the mailbox below was accurate on 2026-08-06 and
  has not been re-read since; treat every "this sentence is now wrong" entry as
  itself possibly wrong, and prune against the running app rather than against
  the notes.
- **2026-07-29** — created from the v1.0 GUI plan.
