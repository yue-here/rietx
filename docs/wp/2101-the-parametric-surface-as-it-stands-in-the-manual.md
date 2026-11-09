# WP-2101 — the parametric surface as it stands, in the manual

Milestone: parametric · Status: ⬜
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
- Every kind of target an expert asks for is accepted today: cell, scale, a coordinate
  DOF, Biso, occupancy, `instrument.zero_shift`, a profile `w` and a background
  coefficient. Nothing says so in one place.
- Freeing only `vars.a_0` holds the slope at its start of 0. Rwp went from 0.49 to 0.86
  on the ramp and nothing was reported. This is undocumented.
- Equations nonlinear in one scalar already work by scanning that scalar through
  `design` rows. Holding θ at 200, 400 and 800 K gave χ² of 150.1, 150.5 and 155.7, at
  about 0.4 s a fit. The scan gives no esd on θ. That example is not in the manual.
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

- **From WP-2106 (2026-11-09): GSAS-II's fit afterwards has a call now, and a section
  says so.** `switching/gsas2.md` § A parametric equation is fitted with the patterns
  names `rx.fit_trajectory` as GSAS-II's fit to the sequential table, and
  `Gsas2Model.sequential_equations` as where a `.gpx`'s stored equations arrive, with a
  worked call. This WP's task on `switching/gsas2.md` and GSAS-II's "parametric fit
  afterwards" builds on that section rather than writing a second. The skill's series
  reference names `fit_trajectory` in its joint-fit row, and that file sat 1 B under its
  budget after it.

## Non-goals

- Anything WP-1964 adds. Its Manual task extends these pages with the grammar and a
  line-by-line translation of each program's spelling.
- A guide to the fit itself. `guides/equation.md` owns that.

## Tasks

- [ ] `switching/topas.md`: a section mapping TOPAS's parametric vocabulary to rietx's
  (`prm`, `local`, `#list`, an equation on a `prm`, `!` for fixed). Say what is
  expressible now and what waits on 1964, by that name.
- [ ] The inventory, moved from the parked 2105. Every parametric construct in the two
  Durham inputs, each with its rietx spelling, its WP or a named non-goal, and each
  input's free-parameter and channel counts. The milestone's agent row is judged against
  it.
- [ ] `switching/topas.md` § Porting what does not read: the recipe an agent follows.
  Try `read_project_model`. A parametric input usually raises `TopasInpError` naming the
  first construct it cannot read, and `parametric_05.inp` and ZrP₂O₇'s input both do, so
  there is no list to work from. A simple input returns a model and a
  `TOPAS_FEATURES_NOT_IMPORTED` list. Either way, port from the input's text with the
  keyword table, then compare a stated value such as a cell or an Rwp with the input's
  own. Include how to expand `#list` and `#define` by hand and
  where `topas.log` holds the expansion.
- [ ] Skill: decide whether porting is a task shape of its own (a `references/` file behind
  a situation row) or a row in the foreign-inputs line, under the skill's placement rule.
- [ ] `switching/gsas2.md`: the same for GSAS-II's sequential refinement and its
  parametric fit afterwards. Read that program's docs before writing.
- [ ] `reference/parametric.md`: one table of the target kinds accepted.
- [ ] Document the held-slope trap where a reader meets it, in `guides/equation.md`.
  Decide whether it also earns a diagnostic, under Rule 1 of DESIGN.md.
- [ ] A worked `design` scan over a held scalar, in `examples/`, included into
  `guides/equation.md`, with its missing esd stated.
- [ ] The refusal message names `.parameters()`.
- [ ] Skill: the series reference's parametric row, or "none" and why.

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

- **2026-11-04** — Filed on the opening of the milestone. No open WP owned this: 1964's
  Manual task covers the new grammar and 1325's manual tasks are closed. The numbers
  above were measured by session scripts on 2026-11-03 and are not in the repo. Next:
  the TOPAS section.
