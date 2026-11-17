# WP-2101 — the parametric surface as it stands, in the manual

Milestone: parametric · Status: 🔄 2026-11-17 — claimed by ghostshift (second slice)
Depends on: —
Priority: P2 2026-11-04 — a feature the open milestone was opened for, and it needs no machinery

## Goal

Someone arriving from TOPAS or GSAS-II can find out, from the pages they read first,
what rietx's parametric refinement does today, how to spell it, and what it cannot
do yet. An agent can port an input that does not import directly from those pages and
the skill alone, as the maintainer ruled on 2026-11-04.

## Context

The maintainer opened the [parametric](../milestones/parametric.md) milestone on
2026-11-04. Its reader is an experienced user who builds their own refinements.
Measured on 2026-11-03, on a seven-pattern synthetic LaB₆ ramp and by reading the tree:

- `docs/docs/switching/topas.md` and `switching/gsas2.md` never mention parametric
  refinement. `guides/equation.md` and `reference/parametric.md` do cover it, but a
  reader starting from the Switching tab has no way to them.
  *Superseded in part, 2026-11-15:* WP-1964 added a parametric section to both
  Switching pages (`switching/topas.md` § A parametric equation is a formula,
  `switching/gsas2.md` § A parametric equation is fitted with the patterns), each
  linking `reference/parametric.md`.
- Every kind of target an expert asks for is accepted today: cell, scale, a coordinate
  DOF, Biso, occupancy, `instrument.zero_shift`, a profile `w` and a background
  coefficient. Nothing says so in one place.
  *Re-measured 2026-11-15:* a declaration also accepts a size or strain term, axial
  divergence, a wavelength and the specimen displacement (locked on a capillary). A
  target that no plan stage reaches refines nothing, and nothing says so:
  `mccusker_default` left the coefficients of a coordinate, B, occupancy, size,
  strain, axial and wavelength equation at their starts, absent from
  `result.parameters`, with no diagnostic naming them. That is the held-slope trap's
  sibling.
- Freeing only `vars.a_0` holds the slope at its start of 0. Rwp went from 0.49 to 0.86
  on the ramp and nothing was reported. This is undocumented.
- Equations nonlinear in one scalar already work by scanning that scalar through
  `design` rows. Holding θ at 200, 400 and 800 K gave χ² of 150.1, 150.5 and 155.7, at
  about 0.4 s a fit. The scan gives no esd on θ. That example is not in the manual.
  *Superseded in part, 2026-11-15:* WP-1964's formula equations refine θ directly,
  with an esd (`guides/formula.md`: θ = 500.17 ± 0.61 K on a synthetic rutile ramp).
  So the scan task below may now be moot; the next session decides.
- The refusal for an unknown target points at the private
  `mtable.tables[h].entries`, where `.parameters()` is the public answer.

### Inherited

- 2026-11-09, from [1325](1325-parametric-series.md): `reference/parametric.md`
  § Range and visibility warnings describes `PARAMETRIC_OUT_OF_RANGE` as a warning
  after the fit. In a real fit it never fires. A target past its own bound makes the
  write-back after the solve raise `ValueError`, naming the target and the equation,
  before any result exists. Under the default LM driver a linear equation's target is
  now held inside its bounds at every step, so the raise is left to TRF and to an
  `"expression"` equation. 1325's handover entry asks the maintainer whether the
  warning stays, goes, or replaces the raise. Rewrite that section once they rule.
  Done in 1325's PR #1497 (2026-11-09): the warning replaces the raise, settled by
  Claude, and that section and `help.py`'s entry now say a TRF or expression fit
  finishes with it. Nothing is left here.

## Non-goals

- Anything WP-1964 adds. Its Manual task extends these pages with the grammar and a
  line-by-line translation of each program's spelling.
- A guide to the fit itself. `guides/equation.md` owns that.

## Tasks

- [x] `switching/topas.md`: a section mapping TOPAS's parametric vocabulary to rietx's
  (`prm`, `local`, `#list`, an equation on a `prm`, `!` for fixed). Say what is
  expressible now and what waits on 1964, by that name. *Done 2026-11-15:* WP-1964 had
  written the core table; this slice added the constructs the two Durham inputs use and
  a list of the four with no spelling yet. 1964 is closed, so the list names the
  missing pieces, not WPs.
- [ ] The inventory, moved from the parked 2105. Every parametric construct in the two
  Durham inputs, each with its rietx spelling, its WP or a named non-goal, and each
  input's free-parameter and channel counts. The milestone's agent row is judged against
  it.
- [x] `switching/topas.md` § Porting what does not read: the recipe an agent follows.
  *Done 2026-11-17* as § Porting an input that does not read, five steps, under
  § Moving a file across.
  Try `read_project_model`. A parametric input usually raises `TopasInpError` naming the
  first construct it cannot read, and `parametric_05.inp` and ZrP₂O₇'s input both do, so
  there is no list to work from. A simple input returns a model and a
  `TOPAS_FEATURES_NOT_IMPORTED` list. Either way, port from the input's text with the
  keyword table, then compare a stated value such as a cell or an Rwp with the input's
  own. Include how to expand `#list` and `#define` by hand and
  where `topas.log` holds the expansion.
- [x] Skill: decide whether porting is a task shape of its own (a `references/` file behind
  a situation row) or a row in the foreign-inputs line, under the skill's placement rule.
  *Done 2026-11-17:* a sentence in `api-io.md`'s projects paragraph (authored in
  `docs/skill/make_api_index.py`), keyed by `TopasInpError` and `read_project_model`,
  which the agent already holds when porting starts. No new shape file.
- [ ] `switching/gsas2.md`: the same for GSAS-II's sequential refinement and its
  parametric fit afterwards. Read that program's docs before writing.
- [x] `reference/parametric.md`: one table of the target kinds accepted. *Done
  2026-11-15:* § Targets, with an executing block asserting every kind and five
  refusals.
- [x] Document the held-slope trap where a reader meets it, in `guides/equation.md`.
  *Done 2026-11-17:* § Check that every coefficient refined, with the plan-reach
  sibling beside it, both executed by `examples/guides/equation.py`.
- [ ] Decide whether the two traps earn a diagnostic, under Rule 1 of DESIGN.md. A new
  diagnostic changes what a fit prints, so the maintainer rules first (handover entry
  2026-11-17 has the brief).
- [x] A worked `design` scan over a held scalar, in `examples/`, included into
  `guides/equation.md`, with its missing esd stated. *Withdrawn 2026-11-17:* a formula
  equation now refines the nonlinear scalar itself, with an esd (`guides/formula.md`,
  θ = 500.17 ± 0.61 K), so the scan is a weaker spelling of a fit the manual already
  shows.
- [ ] The refusal message names `.parameters()`.
- [x] Skill: the series reference's parametric row, or "none" and why. *Done
  2026-11-17:* the existing row in `series.md` carries the plan-reach rule, tightened to
  stay inside the file's budget, and `diagnostics.md`'s `PARAMETRIC_FORM_REJECTED` row
  carries the held variable, since that code is the name an agent holds there.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_manual.py tests/test_manual_api.py tests/test_examples.py
.venv/bin/python -m sphinx -W -q -b html docs/docs docs/docs/_build/html
```

## References

- `docs/practice.md` § A parameter set by an equation the user writes.
- WP-1325 (the surface), WP-1964 (what comes next), WP-1996 (the Switching tab says
  only what its tests show).

## Handover log

- **2026-11-15** — First slice, by a ghostshift runner, in PR #1573. A TOPAS user reading
  the Switching tab now finds a rietx spelling for every parametric construct the two
  Durham inputs use, and the four that have none yet. The reference page now lists, in
  one table, the twelve kinds of parameter an equation can drive, checked by code the
  manual test runs. One trap came out of the measuring: an equation whose target no plan
  stage frees refines nothing, and nothing reports it. It is documented and has no
  diagnostic.

  *Done.* `switching/topas.md` § A parametric equation is a formula: 14 rows added to
  WP-1964's table (`for xdds`, `#define`/`macro`, shared and `local` names, `!` on a
  coordinate as a `turn_off` stage, an overall B per pattern, a monoclinic angle, implied
  multiplication, `range n` as `scan=n-1`, `Out`/`Get`/`MVW`, `val_on_continue`), an
  executing block for the overall B and the hold, and a list of the four constructs with
  no spelling: a joint fit's `hold`/`tie`/`set_values` (WP-2103), restraints and
  `penalty` in a joint fit (WP-1995), an equation over a reflection or a 2θ point
  (WP-2107), and `fit_obj` (a milestone non-goal). `reference/parametric.md` § Targets:
  the table, the refusals pointer, the plan-reach paragraph, and an executing check of
  14 accepted and 5 refused paths.

  *Measured* (session probes in the runner's scratch, `[dev]` venv, macOS arm64, not in
  the repo). On the LaB₆ ramp of `examples/guides/_lab6_ramp.py`, a linear-in-T equation
  on each kind, beside one on the cell, under a three-stage `PlanSpec` whose last stage
  names the target: every fit converged, and the slope of each target whose truth is
  constant came back within 1 esd of 0 (scale, coordinate, occupancy, zero shift, w, y,
  background c1, axial). B's slope sat at −4.5 esd and the wavelength's at −5.7 esd with
  `FLAT_DIRECTION`. The wavelength is degenerate with the cell; B is the pattern-0 issue
  below. Under `mccusker_default` the coordinate, B, occupancy, size, strain, axial and
  wavelength coefficients never left their starts and had no row in
  `result.parameters`. One B per pattern for every site, written as a formula on each
  site's `biso` with `vars.b` per pattern: patterns 1-6 returned b = 0.00-0.04 ± 0.10 Å²
  (truth 0). Pattern 0 stopped at b = 3.7 with its scale halved. A control with each
  site's B per pattern and no formula did the same (B = 4.0, same scale), so that is the
  probe's plan (scale before cell, with the start cell 0.1 % off) and not the formula. A
  `turn_off` stage on the boron coordinate left it at its start through a stage that
  freed every other atom parameter. A monoclinic β formula previews (90.54-90.86° over the
  ramp). `a0 (1 + ...)` is refused as an unknown function `a0`.

  *Gates.* `tests/test_manual.py tests/test_manual_api.py`: 84 passed. Sphinx `-W`:
  clean. Vale on both pages: no warning on an added line. No example changed, so
  `tests/test_examples.py` was not run. Docs-only branch, so `/code-review` was skipped.

  *Settled by Claude 2026-11-15:* the manual names what is missing and no WP numbers,
  under the manual's practice (a WP number appears in six places in the manual, two of
  them comments) and WP-1996 (the Switching tab says only what its tests show). The
  alternative was naming each WP, as the task text asked when 1964 was open. *Settled by
  Claude 2026-11-15:* the overall B is documented as spellable today, through formulas,
  under the 2026-11-04 ruling (docs plus an agent port what does not import) and the
  measurement above. The alternative was "waits on WP-2103's tie". Forwarded to WP-2103's
  Inherited. Not reached this slice: the held-slope diagnostic (task 7, DESIGN.md Rule 1)
  and the skill's placement (tasks 4 and 10). Nothing in this slice changes text the
  package prints.

  *Gotchas.* Many TOPAS parametric constructs are already handled by a joint fit's
  sharing defaults: say "nothing" in a row rather than inventing a call. A Durham input's
  site `!` often marks a coordinate the symmetry already fixes; check the site before
  porting a hold.

  Next, in order: task 2 (the inventory, with each input's free-parameter and channel
  counts; this slice's table rows are its vocabulary), task 3 (§ Porting what does not
  read), then task 7 with the plan-reach sibling, since one Rule 1 decision covers both.
  Task 8 may be moot (see Context). Task 9's refusal message needs the maintainer, as it
  changes what a reader receives. Tasks 4, 5 and 10 are untouched; task 10's row is where an agent meets the
  plan-reach rule, so it carries that rule too.

- **2026-11-04** — Filed on the opening of the milestone. No open WP owned this: 1964's
  Manual task covers the new grammar and 1325's manual tasks are closed. The numbers
  above were measured by session scripts on 2026-11-03 and are not in the repo. Next:
  the TOPAS section.
