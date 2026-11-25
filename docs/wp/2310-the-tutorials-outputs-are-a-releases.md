# WP-2310 — The tutorials' committed outputs are a release's, and main's code has moved under their prose

Milestone: unscheduled · Status: ⬜
Track: Render what the fit already knows
Depends on: —
Priority: P3 2026-11-25 — readers of the dev manual and of `/lite/` see 1.12's outputs beside prose that main's code no longer bears out; the cut finds it anyway, at 40 cells to reread

## Goal

The maintainer decides which code the tutorial outputs committed on `main` come from. A check
then holds that choice, so a pull request that makes a tutorial's text untrue learns it in
that pull request.

## Context

**The finding (another ghostshift runner, 2026-11-25), reproduced at `fb3795a6c`** in a
`[dev]` venv on darwin/arm64. `examples/tutorials/build.py` rebuilt every notebook in 59 s.
The text outputs changed in all seven executed notebooks. Tutorial 06 is a template committed
without outputs (WP-1957), so it did not change. A second rebuild on the same machine changed
nothing. The text outputs therefore carry no timing, path or run id. Every difference is
something main's code now prints.

**What changed, read with numbers masked** (scratch script; the masked diff is the evidence
for the check sketched under option B):

- 01: the first fit has no `closing` stage (WP-2222). Its Rwp goes from 0.0930 to 0.0993, and
  a `FROZEN_COMPILE_STALE` info row appears. The second and third passes each run one
  `warm_refit` stage (WP-2224) in place of six. The history holds 8 nodes in place of 19.
  Two markdown cells in `01_quickstart.py` are now untrue under main's code: line 195 ("each
  pass adds six nodes and ends on a `stage:closing` node") and lines 208-212
  (`STAGE_WINDOWS_STALE` "has gone", "its `profile` stage dropped 0.05 %").
- 02: no `closing` stage; Rwp 0.0898 becomes 0.0893. The landing page's output panel quotes
  0.0898, so `test_the_landing_box_is_the_tutorial` fails on the rebuilt notebook until
  `docs/landing/src/index.html` follows.
- 02b: `closing` leaves the history tree and the `HOLD_BLOCKED_PLAN` message.
- 03: the second pass runs one `warm_refit` stage.
- 03b: four lines, numbers only.
- 04: the calibration's `FLOOR_HIT` on `gauss_strain` is gone, so the cell under Out[11]
  ("Both diagnostics say a Gaussian term refined to its floor of zero") is untrue.
- 05: two patterns now take their values from the `warm_staged` rung. The largest
  forward-backward gap moves from a background term to `instrument.profile.y`.

The rebuild's own listing (WP-2039) names 40 markdown cells to reread across the seven.

**Why `build.py --check` does not see it.** It is blind to outputs on purpose. Its docstring
says a figure's bytes move with the matplotlib that drew them, so it compares cells and the
version stamp only. The stamp is compared to major.minor. `docs/RELEASING.md` step 1 then
rebuilds the notebooks at each cut, "so the tagged tree's outputs come from the release
itself". The committed outputs were last rebuilt at `84202d8de` (opening 1.13, the day 1.12.0
shipped), so they are 1.12.0's. They match what the notebook's own `%pip install rietx`
installs today. The landing page's Colab and Jupyter links open the notebooks at the newest
tag (`docs/landing/build.py`, `release_tag`), so those readers see a consistent notebook.

**Two surfaces built from `main` read them as main's.**
- The dev manual renders the committed outputs. `docs/docs/conf.py` says "the page shows what
  the tests ran", which is untrue between a behaviour change and the next cut.
- `/lite/` serves a rietx wheel built from `main` with the committed outputs kept byte for
  byte (`docs/lite/build.py`; `pages.yml` says the two "match by construction"). A reader
  there sees 1.12's outputs and prose, runs the cell, and gets main's.

**And nothing tells the pull request.** WP-2222 and WP-2224 changed what tutorial 01
describes, and neither touched a tutorial. `test_tutorial_executes_clean` executes every
notebook on each push. It checks for errors, stderr, a home path and a figure. It never
compares the text with the committed text.

## The question for the maintainer

Which code should the committed outputs on `main` come from? It sent here because the answer
turns on which surface people read the tutorials on (an unobserved guess about use), and
because option B changes the per-PR workflow `docs/RELEASING.md` describes.

- **A. The last release (today's rule).** Nothing changes per pull request. The cut rebuilds
  and rereads, 40 cells at 1.13 so far. The two untrue claims above get corrected, and `/lite/`
  either says its outputs are the release's or installs the release from PyPI. Cost: prose
  that a merged change made untrue stays untrue on the dev manual and `/lite/` until the cut,
  and the cut's author did not make the change.
- **B. Main's code.** A pull request that changes a tutorial's printed text rebuilds the
  notebooks (about a minute) and rereads the listed cells. The check is a comparison inside
  `test_tutorial_executes_clean`: the fresh execution's text outputs against the committed
  ones, numbers masked. Masking catches every change listed above and is silent on 03b. Exact
  numbers cannot be compared there, because CI runs Linux and the builder runs darwin
  (the goldens' `GOLDEN_PLATFORM` precedent). Costs: notebooks conflict between concurrent
  pull requests; the landing panel then quotes main's numbers, which `pip install rietx` does
  not give until the next release. Not measured: whether a masked comparison holds on Linux
  and Windows, where a diagnostic near its threshold may fire on one platform only.
- Dropped: a check that reports drift without failing. Under A it would fire on every
  behaviour change until the cut, and a report that always fires is read by nobody.

Recommendation: a lean towards B. The crux is who rereads the prose. Under B the author of
the change does it while they know what changed. Under A someone else does it at the cut,
against a list that grows with every release. B loses if the maintainer wants a notebook on
`main` to show what the PyPI release prints, or if the masked comparison differs between
platforms. One nightly run of it in report-only mode on Linux, Windows and macOS settles the
second.

## Tasks

Written once the question is answered.

## Handover log

- **2026-11-25** (ghostshift runner, filed in PR #1846). The tutorial outputs on `main` are 1.12.0's,
  on purpose. Main's code has since changed the stages or diagnostics six of the seven executed notebooks
  print. Tutorial 01's prose and one cell of 04's are now untrue for anyone who runs them
  against `main`. Nothing was regenerated. Regenerating is option B's first step, and which
  option holds is the maintainer's question above. Settled by Claude under `docs/RELEASING.md`
  step 1: no regeneration while the question is open.
  *Measured:* every notebook rebuilt in 59 s (`[dev]`, darwin/arm64, at `fb3795a6c`); a second
  rebuild changed no text, so no output in the set is noise. The rebuild was then discarded.
  `python -m tests.reader_output` is untouched: this branch changes no package code.
  *Next:* the maintainer answers the question. Under A, correct `docs/docs/conf.py`'s claim and
  `/lite/`'s, and nothing else moves until the cut. Under B, run the masked comparison once in
  report-only mode on the nightly's three platforms, then rebuild, reread the 40 listed cells,
  update the landing panel, and make the comparison a gate.
