# WP-2040 — the tutorials link the manual at each concept's first mention

Milestone: unscheduled · Status: ✅ 2026-10-24 — every concept a tutorial's prose names links the manual in the cell
that first names it (16-27 links a notebook, from 4-7), and each anchor is tested against the
built manual
Track: The repo's own process
Depends on: 1986 soft (guides 18 and 24, new pages)

## Goal

Every rietx concept a tutorial names links to the manual page that explains it, at its first
mention in that notebook.

## Context

The maintainer's note on notebook 01 (2026-10-23; WP-2039 § Where this came from, note 3):
add more manual links to the notebooks once the manual is more complete. The rule this
applies is `yue-docs-style` rule 3 as WP-2039 proposes to widen it: nothing the reader needs
comes before it is explained or linked.

- Counted on `bc71dec`, the tutorials carry 4 to 7 links each to
  `https://rietx.org/docs/stable/…` (01: 4, 02: 4, 02b: 5, 03: 4, 04: 4, 05: 7, 06: 6).
- `tests/test_tutorials.py::test_a_tutorial_links_only_pages_the_manual_has` fails on a link
  to a page the manual does not have. It reads the Markdown sources, so it cannot see an
  anchor. `tests/test_manual.py::test_every_anchor_a_tutorial_links_is_on_its_page` checks
  each anchor against the built manual.
- WP-1986 is still moving Guides pages into the new tree. A link written before it lands may
  point at a page that is about to move, which is why this WP waits for it. *Superseded in
  part, 2026-10-24:* WP-1986 retired the old tree on 2026-10-22, so every page now has its
  final address. What it still owes are two new guides, 18 and 24, which add pages and move
  none. A concept whose only page would be one of those two is listed as having no page.
- Edit each `examples/tutorials/NN_*.py` and rebuild with `build.py`. Never edit the
  `.ipynb`. `build.py` lists every cell whose text output a rebuild changed, with the first
  line of the markdown under it (WP-2039). Reread each one it lists before committing.
- WP-2039 left two tutorial gaps that are not links. Both are filed: the indexer's
  abstention has no worked example (WP-2041), and `best.plot()` names no radiation (WP-2042).

## Non-goals

- The prose and display fixes: WP-2039.
- New manual pages. A concept with no page is listed in the handover entry and gets no link.

## Tasks

- [x] For each notebook, list every rietx concept it names (a verb, a type, a plan, a mode,
      a diagnostic code) and whether its first mention links the manual. Record the table in
      the handover entry. (2026-10-24, in the entry below.)
- [x] Add the missing first-mention links, then rebuild. (2026-10-24: 4-7 links a notebook
      became 16-27, each in the first markdown cell that names its concept.)
- [x] A test that each tutorial anchor is an id on its page of the built manual
      (`test_manual.py::test_every_anchor_a_tutorial_links_is_on_its_page`). The page check in
      `test_tutorials.py` could not see an anchor. (2026-10-24, added in this session.)
- [x] Skill: none. The links are for a person reading a notebook.

## Acceptance

Every concept in the table either links at its first mention or is named as having no page.

```sh
.venv/bin/python examples/tutorials/build.py --check
.venv/bin/python -m pytest tests/test_tutorials.py -q
.venv/bin/python -m pytest tests/test_manual.py -k anchor -q
```

## References

None.

## Handover log

- **2026-10-24** — A reader of any tutorial can now reach the manual's explanation of a rietx
  name where the notebook first names it, without searching. The seven notebooks carried 4-7
  manual links each and now carry 16-27, 162 in all, and every one lands on a section rather
  than a page top. A new test builds the manual and checks each anchor against it, because the
  old check read only the page name, and a renamed heading would have left readers at the top
  of the page with every test green. The rebuild also showed that four notebooks had been
  committed with outputs older than main's diagnostics display, and notebook 01's prose
  described lines that display no longer prints. That prose now matches what the cell shows.

  *Rule applied.* A concept links in the first markdown cell that names it, usually on the
  backticked name itself so the sentence does not grow. A name that appears only in code is
  outside the table. The setup lines that notebooks 02, 02b and 06 repeat are explained in
  notebook 01, which each of them names as the place to start. Where no reference entry
  explains a name, the nearest section that does is linked, so no concept is left with no
  page. `size_coefficient_for_size` has no reference entry and links the theory section that
  gives the conversion. Each link targets the explanatory page (pattern files, the instrument,
  plans, the parameter table, a diagnostic's own anchor), and never the API listing, which
  carries only a signature and a docstring's first line.

  *The table.* Per notebook, link text → target, in order of appearance. `+` marks a target
  the notebook did not link on `origin/main` (generated from the sources):

    **01_quickstart** (26 links, 23 new): +`rx.read_pattern` → reference/pattern-files#reading-a-pattern; +`sigma` → reference/pattern-files#intensities-and-esds; +Plot the pattern → reference/data#plotting-a-pattern; +`rx.diagnose` → reference/pattern-diagnostics; How to check a pattern before fitting → guides/check#read-the-pattern-diagnostics; +Le Bail fit → reference/refinement#modes; +`rx.Structure.from_cif` → reference/structure-files#reading-a-cif; +`rx.Instrument.bragg_brentano` → reference/instrument#constructors; +Chebyshev polynomial → reference/instrument#chebyshev-polynomial; +`rx.auto_background(data).background` → guides/check#size-the-background-from-the-diagnostics; +`Refinement` → reference/refinement#entry-points; About a fit → concepts/fit#the-plan; +`closing` → reference/refinement#the-closing-stage; +Plan presets → reference/plans#profile-only; +`two_theta_limits` → guides/range; +summary → reference/result#printing-a-result; +`ftol` → reference/refinement#stage-tolerances; +diagnostics → reference/result#diagnostics; +`PATTERN_UNDERSAMPLED` → reference/diagnostics-refinement#pattern-undersampled; +every refined parameter → reference/parameter-table#refined-rows; +`at_bound` → concepts/correlations#parameters-on-a-bound; +Le Bail passes → reference/refinement#le-bail-passes; history → concepts/fit#the-history; +`RESOLUTION_UNCONSTRAINED` → reference/diagnostics-refinement#resolution-unconstrained; +Checkout, branch and merge → reference/history#checkout-branch-and-merge; +The fit figure → reference/figures#the-fit-figure

    **02_simple_rietveld** (25 links, 21 new): +`mccusker_structural` → reference/plans#mccusker-structural; +purposes → reference/result#printing-a-result; +`FLOOR_HIT` → reference/diagnostics-refinement#floor-hit; +`RESOLUTION_UNCONSTRAINED` → reference/diagnostics-refinement#resolution-unconstrained; +`PATTERN_UNDERSAMPLED` → reference/diagnostics-refinement#pattern-undersampled; +`result.diagnostics` → reference/result#diagnostics; Diagnostic codes → reference/diagnostics; +difference curve → reference/figures#the-fit-figure; +`closing` → reference/refinement#the-closing-stage; Plan presets → reference/plans; +`result.stages` → reference/refinement#stage-results; +`ref.parameters()` → reference/parameter-table#rows; Site-symmetry degrees of freedom → theory/parameterisation#site-symmetry-degrees-of-freedom; +`result.geometry` → reference/derived#bonding-geometry; +`rx.viz.render_structure` → reference/figures#structure-pictures; +`view` → reference/figures#views; +`mode="ellipsoid"` → reference/figures#drawing-options; project → concepts/project; +`rietx gui` → reference/cli#rietx-gui; +`Project.create` → reference/project#creating-a-project; +history → concepts/fit#the-history; +one kind of fact → concepts/project#what-each-file-is-for; +`rietx watch` → reference/cli#rietx-watch; +`rx.Project.open` → reference/project#opening-a-project; +open a copy → concepts/project#opening-a-project-changes-it

    **02b_steering_a_refinement** (18 links, 12 new): +`tie_equal` → reference/parameter-table#ties; How to tie parameters together → guides/tie#check-that-the-data-allow-the-tie; +`lab_bragg_brentano` → reference/plans#lab-bragg-brentano; +diagnostics → reference/result#diagnostics; +`HIGH_CORRELATION` → reference/diagnostics-refinement#high-correlation; About correlations and esds → concepts/correlations#what-to-do-about-a-correlation; history → concepts/fit#the-history; +`checkout` → reference/history#checkout-branch-and-merge; +`set_values` → reference/parameter-table#editing-the-table; +`hold` → guides/hold#hold-the-parameter; +`HOLD_BLOCKED_PLAN` → reference/diagnostics-refinement#hold-blocked-plan; +`vary` → concepts/parameters#which-parameters-refine; How to keep a parameter fixed whatever the plan frees → guides/hold; +nodes → reference/history#action-kinds; +`ref.summary` → reference/result#printing-a-result; +`exchangeability` → reference/report-evidence#exchanges; About the report → concepts/report; How to choose the next parameter to free → guides/next

    **03_peaks_indexing_lebail** (25 links, 21 new): +`predict` → reference/refinement#entry-points; +`pick_peaks` → reference/peaks#picking-the-peaks; +`flags` → reference/peaks#the-flags; +`PEAK_WIDTH_LAW_MISMATCH` → reference/diagnostics-indexing#peak-width-law-mismatch; +`PEAK_KALPHA2_ALIAS` → reference/diagnostics-indexing#peak-kalpha2-alias; Diagnostics: peaks and indexing → reference/diagnostics-indexing; +`fit_peaks` → reference/peaks#fitting-peaks-you-name; +`unnamed_neighbour` → reference/peaks#the-neighbour-you-did-not-name; +`rietx gui` → reference/cli#rietx-gui; The GUI panel by panel → reference/gui-guide#peaks; +`index_pattern` → reference/indexing#running-the-search; +`SearchSpec` → reference/indexing#the-search-specification; +`budget_seconds` → reference/indexing#presets-budgets-and-the-three-states-of-a-system; +search engines → reference/indexing#three-engines-and-why-the-default-is-all-of-them; +high confidence → reference/indexing#the-confidence-gate; +quick Le Bail fit → reference/indexing#the-whole-profile-test; +`unindexed_two_theta` → reference/indexing#one-candidate; +`search_incomplete` → reference/indexing#presets-budgets-and-the-three-states-of-a-system; +`INDEX_IMPURITY_LINES` → reference/diagnostics-indexing#index-impurity-lines; +`best_or_none()` → reference/indexing#the-result-object; `INDEX_ABSTAINED` → reference/diagnostics-indexing#index-abstained; Indexing → theory/indexing#figures-of-merit-in-both-directions; +`structure_from_candidate` → reference/indexing-evidence#from-a-candidate-to-a-phase; +twice → reference/refinement#le-bail-passes; +which reflections are absent → reference/indexing-evidence#the-extinction-symbol

    **04_peak_shape_and_microstructure** (16 links, 11 new): +`predict` → reference/refinement#entry-points; +specimen terms → reference/data#broadening; The instrument ⊕ sample width split → theory/profiles#the-instrument-sample-width-split; +width terms → reference/instrument#peak-width; `size_coefficient_for_size` → theory/microstructure#reading-a-width-as-a-size; +Hold → guides/hold#hold-the-parameter; +How to calibrate an instrument on a standard and reuse it → guides/calibrate; Plan presets → reference/plans#lab-calibrate; +`save_instrument_profile` → reference/instrument-files#instrument-profile; +`load_instrument_profile` → reference/instrument-files#instrument-profile; +`lab_sample_refine` → reference/plans#lab-sample-refine; +`result.microstructure` → reference/derived#size-and-strain; +`unavailable` → reference/derived#esds-and-absent-readings; +`size_agreement` → reference/derived#separating-size-from-strain; Trends across the pattern → concepts/report#trends-across-the-pattern; Reading a width as a size → theory/microstructure#reading-a-width-as-a-size

    **05_sequential_fits** (27 links, 20 new): +`predict` → reference/refinement#entry-points; +`PatternData` → reference/data#pattern; Read the temperatures from your files → guides/series#read-the-temperatures-from-your-files; +`refine_sequential` → reference/series#entry-points; +`x` → reference/series#series-coordinate; +`carry` → reference/series#carried-parameters; +parameter-path globs → reference/parameter-table#names; +`mccusker_default` → reference/plans#mccusker-default; +`SEQUENTIAL_PERSISTENT_FINDING` → reference/diagnostics-series#sequential-persistent-finding; Read the diagnostics first → guides/series#read-the-diagnostics-first; +which attempt → reference/series#restart-ladder; Check where each fit started → guides/series#check-where-each-fit-started; +`series.trajectory` → reference/series#trajectories; +`direction="both"` → reference/series#forward-and-backward-chains; +`SEQUENTIAL_PATH_DEPENDENT` → reference/diagnostics-series#sequential-path-dependent; +`summary(deliverable="series")` → reference/result#printing-a-result; How to check a series for path dependence → guides/path; +`SEQUENTIAL_DISCONTINUITY` → reference/diagnostics-series#sequential-discontinuity; Check a step against two independent fits → guides/path#check-a-step-against-two-independent-fits; +`warm` → reference/series#restart-ladder; +`SEQUENTIAL_RWP_OUTLIER` → reference/diagnostics-series#sequential-rwp-outlier; +`FLOOR_HIT` → reference/diagnostics-refinement#floor-hit; +`MODEL_FAR_FROM_DATA` → reference/diagnostics-refinement#model-far-from-data; +`PHASE_UNCONSTRAINED` → reference/diagnostics-refinement#phase-unconstrained; `SEQUENTIAL_UNRECOVERED` → reference/diagnostics-series#sequential-unrecovered; +quarantined → reference/series#quarantine; Keep a parameter fixed or tied on every pattern → guides/series#keep-a-parameter-fixed-or-tied-on-every-pattern

    **06_your_own_data** (25 links, 18 new): +`rx.Instrument.debye_scherrer(wavelength=...)` → reference/instrument#constructors; How to limit the fit range or leave out a region → guides/range; +`rx.read_pattern` → reference/pattern-files#reading-a-pattern; +`rx.capabilities().reader_formats` → reference/pattern-files#formats; +`sigma` → reference/pattern-files#intensities-and-esds; +`rx.diagnose` → reference/pattern-diagnostics; How to check a pattern before fitting → guides/check#read-the-pattern-diagnostics; +structure → reference/data#structure; +Chebyshev polynomial → reference/instrument#chebyshev-polynomial; Check the starting cell against the peaks → guides/check#check-the-starting-cell-against-the-peaks; +Le Bail → reference/refinement#modes; +`Refinement` → reference/refinement#entry-points; +plot's title → reference/figures#the-fit-figure; +`profile_only` → reference/plans#profile-only; Plan presets → reference/plans; +`deliverable` → reference/result#printing-a-result; Diagnostic codes → reference/diagnostics; About the report → concepts/report; +`result.parameters` → reference/parameter-table#refined-rows; +`rx.viz.render_structure` → reference/figures#structure-pictures; +`view` → reference/figures#views; +The CIF → reference/exports#the-refinement-cif; +`rietx gui` → reference/cli#rietx-gui; +`rx.Project` → reference/project#creating-a-project; About the project → concepts/project

  Named in prose without a link of their own, each covered by a link in the same cell: in 01,
  `mode` and the stage names `bkg` and `zero` (the mode and plan links), and `profile_only`
  (Plan presets, two lines later). In 02, `dof` (linked in the cell that explains it, one code
  cell after the first mention), `turn`, `atom_labels`, `path=`, `project.fit()` and
  `project.save()`. In 02b, `report`, Layer 1, `next` and `protocol` (the cell's closing links
  to the report concepts and the next-parameter guide). In 03, the Peaks tab and the
  `duplicate_line`, `fit_failed` and `manual` flags. In 04, `lab_calibrate`, `scherrer_k` and
  `separable`. In 05, `labels`, `warm_staged`, `both.backward` and the series summary's rows.
  In 06, the four `diagnose` rows (the cell's guide link). Explained in place and needing no
  page: `max|Δθ|/esd`, the Kα2 ticks and the series' fence.

  *Done.* The links, with notebook 03's intro corrected: it said rietx "declines to name a
  single cell", which its output has not shown since WP-2002, and now says the notebook shows
  how rietx decides. Notebook 01's diagnostics item named `help:`, `means:` and `at:` lines.
  Main's `b6d3430c7` (WP-2037) prints a diagnostic as one line plus `means:` when no
  deliverable is given, so item 2 and the `RESOLUTION_UNCONSTRAINED` sentence were rewritten.
  The other changed outputs, in 02b, 04 and 05, still matched their prose. The anchor test
  went into `test_manual.py`, beside the other tests that read the built manual, because
  `test_tutorials.py` checks the Markdown sources and cannot see a generated heading id.
  Inherited, pruned on arrival: the `build.py` note folded into Context, and the WP-1986
  dependency marked soft, since its old tree retired on 2026-10-22 and pages no longer move.
  WP-2039's two gaps that are not links were filed as WP-2041 (a tutorial shows the indexer
  abstain) and WP-2042 (a result names its radiation). No open WP owned either: WP-1969
  changes when the indexer abstains, and WP-1444, which added figure titles, is closed.
  Forward reference: WP-2037's Inherited carries the stale-output finding, since its open
  tasks change what results print.

  *Measured* (`[dev]` venv, darwin arm64). Links per notebook, before → after: 01 4→26,
  02 4→25, 02b 5→18, 03 4→25, 04 4→16, 05 7→27, 06 6→25. Every anchor resolved against a local
  manual build. `test_tutorials.py` with `test_manual.py`: 96 passed. The new test failed as
  intended on an anchor broken by hand, naming the file and the link, and passed once it was
  restored. Vale on the extracted prose, CI's way: 0 errors and 5 warnings, all on headings and
  the GUI gesture table this WP did not touch. Fast suite, `-m "not slow"`: 11 401 passed,
  265 skipped, 27 xfailed, in 9:29 while a `/pr-review` ran its own pytest in `pr-bench`, so
  the time is a loaded one. This branch adds two tests, both unparametrised functions in
  `test_manual.py`, so passed+skipped moves by +2 against `main`. Main's figure was not
  re-measured locally. `tests.added_test_times` on this run's junit file gives 0.01 s for the
  two together; the manual build they read is a shared session fixture. The full suite did
  not run, because the branch changes no measured number.

  *Review* (`/code-review high --fix`, six findings). Fixed: the anchor check gained a case
  showing it can fail (`test_the_anchor_check_sees_a_missing_id_and_a_missing_page`, on a
  small HTML tree in a temp directory); the Context and the Acceptance block now name the
  anchor test; notebook 01 keeps `rx.auto_background(data).background`, the call form the
  link had shortened. Declined: sharing one link regex between `test_tutorials.py` and
  `test_manual.py`, since that means one test module importing another for one line. Raised
  for the maintainer, outside this WP: **every `/docs/stable/` link 404s today**, the ones
  already on main included. Checked 2026-10-24 with `curl`: `/docs/stable/reference/result.html`
  gives 404 and `/docs/dev/…` gives 200. `docs/docs_versions.py` writes `stable/` from the
  newest release that carries a docs tree, and 1.9.0 carries none. So the links resolve once
  1.10.0 is cut with its docs asset, and the notebooks already say they need rietx 1.10. The
  release is owed (the session-start hook says 1.9.0 is 10 days old).

  *Gotchas.* `build.py --check` compares cells and never outputs, so a display change on main
  leaves the committed outputs stale and nothing goes red. Reread every cell a rebuild lists.
  An explicit MyST label, `(name)=`, gives an id that is no section's, so look up an anchor in
  the built HTML's `id="…"` attributes rather than in the headings.

  Next: nothing here, since the WP is closed. WP-2041 and WP-2042 carry the two gaps. When
  WP-1986 writes guides 18 and 24, a tutorial that names their subject can link them.

- **2026-10-23** — Created from the maintainer's note on notebook 01, beside WP-2039. Filed
  apart from it because it waits on WP-1986, and WP-2039 does not. Next: start once WP-1986
  closes.
