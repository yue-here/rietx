# WP-2037 — a tutorial reads without decoding: the maintainer's notes as rules, the quickstart's fixes, and the checks that hold them

Milestone: unscheduled · Status: 🔄 2026-10-23 — claimed by @yue-here
Track: The repo's own process
Depends on: — (1986 soft, the tutorials' home under Start)
Priority: P3 2026-10-23 — a shipped tutorial describes output it no longer shows and nothing flags it; a reader works around it by reading the output

## Goal

Notebook 01's prose says what its outputs show, in words that a crystallographer new to
Jupyter and to rietx reads without decoding. Its displays and figures carry what that reader
needs. Each rule behind that is written where it belongs: the maintainer's local prose
skills, the tutorials' README, `_display.py` or the plotting docstring. A rebuild that moves
an output tells whoever ran it which prose to reread.

## Context

### Where this came from

The maintainer read notebook 01 (`examples/tutorials/01_quickstart.ipynb`) on GitHub on
2026-10-23 and left ten notes:

1. "You should be comfortable running a Jupyter cell" should be replaced by how to run one
   (a keyboard shortcut or the button).
2. The `PatternData` and diagnostics displays should be easier to read, with aligned columns.
3. A WP should add more manual links to the notebooks once the manual is more complete
   (filed as WP-2038).
4. Are dead channels useful? Which diagnostics are day-to-day items, and which are artefacts
   of rietx's own test cases?
5. "the first pass hands the whole pedestal" is needless jargon.
6. Once the background is set, show a plot of the background and the data only.
7. `data.plot` should show the radiation and wavelength by default.
8. "Ticks that drift away from their peaks across the scan" is hard to parse.
9. Long calls should take one named argument per line.
10. The prose under Out[6] and Out[8] no longer seems to match the output, or the output
    renders in the font of a markdown cell.

The general idea behind all ten: **the reader knows powder diffraction but not rietx, and
perhaps not Jupyter or Python, so nothing on the page should make them decode something.**

### The rules, and where each one folds

Most of the notes widen a rule that already exists. The `yue-docs-style`, `yue-prose` and
`yue-figure-style` skills live on the maintainer's machine, not in this repository, so a
session here can only propose their wording. The current wording of `yue-docs-style`'s six
rules is quoted in WP-1982 § Context.

| Note | Folds into | Proposed wording |
|---|---|---|
| 1, 3 | `yue-docs-style` rule 3, "no programming concept before it is explained or linked" | "Nothing the reader needs comes before it is explained or linked: a programming concept, a tool (a Jupyter cell, a terminal) or a rietx concept. If the explanation fits in one sentence, write that sentence instead of naming the prerequisite." |
| 5 | `yue-docs-style` rule 2, "the crystallographer's term leads" | Add: "and a thing keeps one name on a page". Lines 72-73 of the quickstart call the background level "the floor of the data" and then "the whole pedestal". |
| 5, 8 | `yue-docs-style` rule 6, no economic metaphor | Widen to "No metaphor for an effect: of price ('buys'), of motion ('drift', 'walk') or of agency ('hands', 'takes it up'). Say what changes and where." `docs/vale/rietx/Metaphor.yml` holds the checkable half and lists only the price words today. |
| 8 | `yue-prose`, which this session could not read | "Describe a figure by what the reader can see (left or right, a gap in degrees, whether it grows with 2θ), then the cause, then the consequence, one per sentence." Check whether one of its eight constructions already says this. If one does, nothing is added. |
| 6, 7 | `yue-figure-style` ("caption is the title") | Add: "A figure names what its reader needs when it is seen alone: the radiation or wavelength whenever the pattern or the model knows it, and every part of the model that exists." |
| 10 | WP-1545 § How each notebook reads, "markdown after it says what the output showed" | Already a rule, and it broke because nothing checks it. It goes in `examples/tutorials/README.md`, with "a rebuild that changes an output rereads the markdown under it". |
| 6 | WP-1545's "predict, then run" | Add to the README: "each piece of the model gets a cell showing it against the data before a fit uses it". |
| 4, 2 (in part) | root CLAUDE.md, WP-1076: a field whose empty state reads as an answer | The same rule, applied to the display. `dead_channels: none` when the check could not run is that case. |
| 2 | new: a fourth rule in `_display.py`'s docstring | "A display shows what its reader acts on, laid out to be read: values in one aligned column, numbers to the digits that carry meaning, a unit where there is one, and an empty state that says whether the check ran." |
| 9 | new: code layout, in the tutorials' README or a formatter setting | "A call that does not fit 79 columns takes one argument per line, with a trailing comma (black's and ruff's magic trailing comma). Never pad the `=` signs into a column: PEP 8 forbids spaces around a keyword `=`." |

### What the quickstart shows today

Measured on `bc71dec`'s committed notebook. "Out[N]" follows the execution counts, and line
numbers are in `examples/tutorials/01_quickstart.py`.

**Prose that no longer matches its output.** WP-2002's closing stage (PR #1085) changed the
outputs, and the rebuild (`b4551bf`) left the prose as it was.
- L144: "each pass is five nodes and ends on a `stage:profile` node". Out[7] shows six nodes
  per pass ending on `stage:closing`: 19 nodes, the root plus 3 × 6.
- L108: "frees the background, then the zero shift, then the cell, then the peak widths, one
  stage each". Six stages print: `bkg`, `zero`, `cell`, `profile_w`, `profile`, `closing`.
- L124: "Every stage but the last stops early". Every stage line in Out[6] reads
  `converged (…, ftol=1e-06)`. The prose has to use the output's own word (a looser `ftol`),
  or the output has to say it.
- L126: "Open one". This assumes the HTML `<details>` element, which the text display does
  not have.
- Out[6]'s `FLOOR_HIT` (`instrument.profile.y` = 0.0000(47)) is never mentioned, and the kept
  pass (Out[8], y = 0.0236(39)) has lost it. L156, "They need not match the first pass's", is
  the place to name it.
- The parameter table's third column, `at_bound`, is not described.

**How the fit result renders.** The result's HTML display (Out[6], Out[8]) interleaves
monospace `<pre>` blocks with `<details>`/`<summary>` and `<p>` paragraphs in the body font.
Each diagnostic also carries a paragraph of explanation that the text display does not have.
In a static render those paragraphs read like a markdown cell inside the output, which is
probably the "font of a markdown cell" in note 10. Nobody has looked at GitHub's render yet:
the cloud session that filed this WP could not reach `notebooks.githubusercontent.com`.
`_display.py` says "Text is the authority and HTML a projection of the same rows", and that
paragraph is content only the HTML has.

**Words.**
- L11: the Jupyter prerequisite (note 1). Suggested: "Run each cell with Shift+Enter, or the ▶
  button in the toolbar, in order from the top."
- L72-73: "floor of the data", then "Left at zero, the first pass hands the whole pedestal to
  the peaks". One reading: with c0 = 0, the first Le Bail extraction counts the background
  under each peak as peak intensity. Check that reading against
  `CompiledModel.lebail_update` before rewriting.
- L102: "within a fit's reach, and the zero-shift stage takes it up".
- L103: "Ticks that drift away from their peaks across the scan mean a wrong starting cell or
  wavelength, and a fit will not walk that far." The sentence to copy is the manual's own, in
  `docs/docs/guides/check.md`: "A cell 1 % too large puts every fluorapatite tick about 0.3°
  to the left of its peak between 25° and 40°." State the two cases: the same gap everywhere
  means the zero shift, and the fit corrects it; a gap that grows with 2θ means the cell or
  the wavelength.
- `06_your_own_data.py` L93: "A fit will not walk far to correct it."

**Displays.**
- `PatternDiagnostics` (Out[3]) prints 15 `name: value` rows. The values are not aligned,
  the digits are raw `{:.8g}` (`steps_per_fwhm: 4.6463609`), and it prints `none` for a check
  that could not run: `dead_channels` needs a measured σ, and `coverage_plateau: None` is the
  only sign it was skipped. The notebook then spends a bullet (L58) explaining this, and a
  line (L63) saying three rows are read by nothing. The manual's
  `docs/docs/guides/check.md` avoids the display altogether: `examples/guides/check.py`
  prints its own five-row f-string. That is the workaround this WP removes.
- `PatternData` (Out[1]) is readable already. Aligning its values is the only change.

**The diagnostics' rows, sorted** (note 4; the tiers are `src/rietx/_audit.py`'s, and the
sorting into kinds is this WP's judgement):

| Kind | Rows | Evidence |
|---|---|---|
| Day-to-day: anyone refining checks these | `steps_per_fwhm` (+ `n_peaks_measured`), `contamination`, `signal_to_background` | `STEPS_PER_FWHM_MIN` is tier 2 (McCusker et al. 1999). Kβ and W Lα come from an ageing lab tube. |
| Real, on some instruments | `dead_channels`, `signal_cutoffs`, `coverage_plateau`, `coverage_regions`, `amorphous_hump_score`, `air_scatter_gain` | Dead channels come from issue #274: an ILL D1B neutron file with collapsed-σ cells at both ends, checked against a private Mythen set. They need a measured σ, so they can never fire on a lab file without a σ column, this one included. The `DEAD_*`, `CUTOFF_*` and `COVERAGE_*` constants are still `unaudited`. `HUMP_TRIGGER` and `AIR_SCATTER_TRIGGER` are tier 3. |
| Internal: nothing a reader acts on | `baseline_lambda`, `noise_sigma_median`, `peak_fraction`, `n_peaks`, `peak_density_per_deg` | The quickstart says so itself (L63). `baseline_lambda` is the arPLS stiffness the package chose. |

Whether to hide the third kind from the default print, or keep every row and group them, is
the maintainer's decision. `PatternDiagnostics._READING_ORDER` and
`tests/test_display.py::test_diagnostics_print_every_field_in_reading_order` hold the order
today.

**Figures.**
- `data.plot()` names no radiation. `FAP.XRA` states none (its metadata holds `source_file`
  and `format` only). Readers whose file states one record `wavelength` and `anode` in
  `metadata` ("recorded, never used": `io/formats/base.py`, the `METADATA_KEYS` entries), and
  with `model=` the `Instrument` knows its radiation.
- `data.plot(model=ref)` draws tick rows only (the `plot_pattern` docstring). The starting
  background, Chebyshev c0 = 65 set in the cell before it, is not drawn.

**Enforcement today.**
- `build.py --check` compares cells and the version stamp, never outputs, because a figure's
  bytes depend on the matplotlib that drew it (its docstring).
- Vale reads `docs/docs/` only (`.vale.ini`'s glob), so tutorial prose is never linted.
- `tests/test_tutorials.py` checks that each notebook executes clean, that its links resolve,
  the README's list and stderr and home-path hygiene. Nothing checks prose.

### Seams

- `examples/tutorials/01_quickstart.py`: edit the `.py`, then rebuild with
  `python examples/tutorials/build.py 01_quickstart`. Never edit the `.ipynb`.
- `examples/tutorials/README.md` § Adding a tutorial, where the repository's tutorial rules
  live.
- `examples/tutorials/build.py`: `check()`, and a new report of the outputs that changed.
- `src/rietx/_display.py`: `tree()`, `_leaf`, `_number`, and `table_text` (which already
  aligns the parameter table).
- `src/rietx/background/diagnostics.py`: `PatternDiagnostics.__str__` and `_READING_ORDER`.
- `src/rietx/viz/plots.py`: `plot_pattern` and `_model_ticks`.
- `.vale.ini` and `docs/vale/rietx/Metaphor.yml`.
- `docs/docs/guides/check.md` and `examples/guides/check.py`: the f-string workaround.

### Decisions, 2026-10-23

The maintainer chose both on 2026-10-23, from a brief that measured GitHub's render first.

1. **A notebook display is one monospace block** (the brief's option a). Every
   `_repr_html_` that mixes `<pre>`, `<table>` and `<details>` becomes one `<pre>`. GitHub's
   sanitiser strips `<details>` and `<summary>`, and both GitHub and JupyterLab right-align a
   bare table's cells in the body font. Each diagnostic's explanation stays in the notebook
   form, as indented text under its `help:` line. The text form keeps leaving it out
   (WP-1985). Rejected: a pointer to `rietx.help.explain` in place of the paragraph, the
   rustc `--explain` pattern, because it makes the reader run code to decode a warning. Also
   rejected: keeping the fold with monospace inside it, which leaves several blocks.
2. **`PatternDiagnostics` prints all fifteen rows under three headings** (option a): the
   rows checked on every pattern, the rows that matter on some instruments, and rietx's own
   measurements. Rejected: hiding the third group from the print, which would reverse
   WP-1544's every-field test.

The "not checked" state for `contamination` needs a field, since an empty list today means
both "clean" and "no wavelength given". Recording which searches ran is a record field, not
a change to what `diagnose` computes, so it stays inside the non-goal below.

### Invariants

- `_display.py`'s three rules: a display reads fields and never computes; no glosses (a
  field's name, or the label `help.py` gives it); no colour. "Not checked" has to come from
  fields (`dead_channels` empty and `coverage_plateau` `None`), never from a recomputation.
- A walkthrough has one authority, and it is `examples/`. The build fails on any stderr.
- A `PatternData` carries no wavelength of its own. A λ label on `data.plot()` reads the
  metadata or the model, and is absent when neither has one.
- Tier: no fitted number moves. Display and docs only. `_display.py` and `viz` are both in
  `_audit.NOT_WALKED`, so a new width or digit constant there needs no audit row.

## Non-goals

- The manual links in the tutorials: WP-2038, after WP-1986.
- What `diagnose` computes, or its thresholds. Only how it prints is in scope. The `DEAD_*`
  and `CUTOFF_*` rows belong to the generality audits.
- WP-1986's move of the Guides pages. WP-1985's diagnostic text is closed.
- Notebooks 02-06, beyond the sweep task below.

## Tasks

- [x] On the maintainer's machine, first: look at GitHub's render of 01's Out[6]-Out[8], and
      record which cause note 10 was: the stale prose, or the paragraphs described under
      **How the fit result renders**. Both, measured 2026-10-23 in headless Chrome on the
      `notebooks.githubusercontent.com` frame: the sanitiser strips `<details>`/`<summary>`,
      so every explanation renders open in the body font between two `<pre>` blocks, and
      the parameter table renders in the body font with right-aligned paths.
- [ ] Fold the rules into the local skills (maintainer's machine, no commit here). Record the
      final wording, and anything `yue-prose` already covered, in the handover entry.
- [x] `examples/tutorials/README.md`: the repo-side tutorial rules (prose matches the output,
      and a rebuild rereads it; each model piece shown before a fit uses it; code layout).
- [ ] Quickstart prose: each stale line and each word in § What the quickstart shows today.
      Rebuild.
- [ ] Sweep 02-06 for the same patterns: grep
      `drift|walk|hands|takes it up|pedestal|stops early|five nodes|comfortable`, and stage
      counts and node counts written before the closing stage. Fix them and rebuild.
- [x] Code layout: `examples/tutorials/ruff.toml` (extending the root config, with
      `line-length = 79`), `ruff format` over the sources, and a check that fails on
      unformatted ones. First confirm that `build.py`'s parser still round-trips the
      formatted cells (`test_parse_refuses_what_it_cannot_round_trip`).
- [x] Display: align the values in `_display.tree`'s key/value lines, cut the digits, and make
      `PatternDiagnostics` say "not checked" where a check did not run. Three headings
      (Decision 2). Update `tests/test_display.py`, and
      `guides/check.md`/`examples/guides/check.py` if the display replaces their f-string.
- [x] Notebook displays: one monospace block per output, every `_repr_html_` (Decision 1),
      each diagnostic's explanation indented under its `help:` line.
- [ ] `plot_pattern`: with `model=`, draw the model's background at its starting values, and
      name the radiation or λ from `model.instrument` or `data.metadata`, absent when neither
      knows it. Tests in `tests/test_viz.py`, and look at the figure.
- [ ] Quickstart: a cell showing the background against the data once it is set (needs the
      previous task).
- [x] Enforcement: `build.py` lists the cells whose text output changed, with the markdown
      cell under each. Run Vale's `rietx` style (at least `Metaphor` and `Terms`) over the
      tutorials' markdown cells, by extracting them to a temporary `.md`.
- [ ] Rebuild every notebook, then run the tests below.
- [ ] Skill: probably none, since the agent skill drives rietx and does not teach it. Check
      `docs/skill/rietx/` for any quoted `PatternDiagnostics` output or plot keyword that
      changes.

## Acceptance

The grep in the sweep task returns nothing over `examples/tutorials/*.py`. Every markdown
cell in notebook 01 that describes an output agrees with that output, checked by reading.
And:

```sh
.venv/bin/python examples/tutorials/build.py --check
.venv/bin/python -m pytest tests/test_tutorials.py tests/test_display.py tests/test_viz.py -q
.venv/bin/python -m ruff check src tests examples
.venv/bin/python -m ruff format --check examples/tutorials
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
vale docs/docs
```

## References

- McCusker, L. B., Von Dreele, R. B., Cox, D. E., Louër, D. & Scardi, P. (1999). Rietveld
  refinement guidelines. *J. Appl. Cryst.* **32**, 36-50: five to ten steps across a peak's
  FWHM (`mccusker1999` in the manual's bibliography).
- PEP 8, § Whitespace in Expressions and Statements: no spaces around a keyword `=`, and no
  extra spaces to line up assignments.
- Black and ruff format, the magic trailing comma: one element per line once a call has one.
- Few, S. (2012). *Show Me the Numbers*, 2nd ed. Analytics Press: right-align numbers and
  left-align text in a table.
- `scipy.optimize.OptimizeResult` and xarray's `Dataset` display both align their keys in one
  column. They are the scientific Python precedent for note 2.
- Issue #274: where `dead_channels` comes from.

## Handover log

- **2026-10-23** — Created from the maintainer's ten notes on notebook 01, in a cloud
  session. The quickstart's prose has fallen behind its outputs since the closing stage, and
  its rules exist only in part. This file gathers both so a session on the maintainer's
  machine can fold the rules into the local skills and make the fixes. Filed rather than
  folded because no open WP owns tutorial prose or display layout. WP-1545 (the tutorials)
  and WP-1544 (the displays) are closed. WP-1986 moves the manual's Guides and is in flight
  on other pages. WP-1443 reads the old Part 1, which WP-1986 retires. Next: the first two
  tasks, on the maintainer's machine.
