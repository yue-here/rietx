# WP-2154 — a holder offset shared across a joint fit

Milestone: parametric · Status: 🔄 2026-11-22 — claimed by @yue-here (ghostshift runner)
Depends on: 2103 soft (its joint `tie`, only if the expression route fails)
Priority: P2 2026-11-22 — a feature the open milestone was opened for: the 2108 acceptance row asks for a series, and only single patterns were measured

## Goal

A joint fit over several patterns shares a sample holder's cell and its height offset
from the sample, while each pattern keeps its own sample height and its own holder line
areas and widths. The recipe is measured on a synthetic series and written in the manual.

## Context

**What exists.** WP-2108 fits a sample holder beside a sample in one pattern with nothing
new in the package (`docs/docs/guides/holder_cell.md`, `examples/guides/holder_cell.py`,
`tests/test_holder_cell.py`). Each holder reflection is a declared peak (`PeakComponent`
in `Instrument.extra_components`). Its centre is a formula, set by
`Refinement.tie(path, expression=...)`, of four variables: the holder cell `a_holder`,
the height offset `offset`, the zero shift `zero` and the sample height `height`. The
zero shift and the specimen displacement are tied to the last two. The formula is Bragg's
law for Kα1 plus the zero shift, minus (2s/R)·cosθ at the holder's height s = height +
offset, with R the goniometer radius. Over 12 seeds of fluorapatite over a textured
aluminium holder it recovered both cells, the coordinates and the offset (mean z of the
offset +0.25, of the holder cell −0.24). The holder fitted as an aluminium phase missed
its own cell by about 30 esd.

**Why a series.** Stinton & Evans (2007, § 4.1, example 1) share the height offset
across data sets, and the holder is there to give the sample height. The milestone's
row ([parametric.md](../milestones/parametric.md), the 2108 row) asks for a synthetic
series and records "a joint fit sharing the offset was not tried".

**The open question.** `MultiHistogramRefinement` has no `tie`, which WP-2103 would give
it. It takes `variables=` and `ParametricEquation(basis="expression")`, whose target may
be any table path. WP-2101 measured the same shape for WO₃'s overall B: a formula
equation per site with `vars.b` in `SharingMap(per_histogram=[...])` gave one refined B
per pattern (WP-2103's `### Inherited`). So the joint form is likely this, unmeasured:

- `variables=` declares `a_holder`, `offset`, `zero` and `height`.
- `SharingMap(per_histogram=["vars.height", ...])` keeps the sample height per pattern.
  Whether the zero shift is per pattern is the fixture's choice; say which.
- One expression equation per holder line sets its centre, and two more set
  `instrument.zero_shift` and `instrument.geometry.sample_displacement` from the variables.
- Line areas and widths are per pattern.
- The plan edits of the single-fit recipe carry over: no preset frees a `vars.*` column,
  and the holder stage comes before the zero stage (2108's gotchas).

If an equation cannot target a declared peak's centre or the displacement in a joint fit,
say what refused it, and put the case in WP-2103's `### Inherited` as a customer of its
tie.

**Tier.** No rule is added. This is a recipe over existing machinery.

## Non-goals

- A holder as a Pawley phase (2108's other route, struck there).
- Phase fractions for the holder.
- A new verb on a joint fit, which is WP-2103's.

## Tasks

- [x] A synthetic series: the 2108 fixture over five patterns, one holder cell and one
  offset, a sample height per pattern. Fit it jointly by the route above.
- [x] Measure over 12 pinned seeds: the mean z-score of the truth for both cells, the
  sample's coordinates, the offset and each height; their spread; GoF; time per fit as a
  range. Compare the offset's esd with the single-pattern recipe's.
- [x] A slow test beside `tests/test_holder_cell.py`, holding the milestone's bar.
- [x] A section in `docs/docs/guides/holder_cell.md` with its script under
  `examples/guides/`, every quoted number asserted.
- [ ] The milestone's 2108 row, rewritten to say what the series measured.
- [ ] Skill: none expected, since `holder.md` reaches the guide. Say so, or add the row.

## Acceptance

Over 12 pinned seeds of the synthetic series, both cells, the sample's structure and the
shared offset have a mean z-score under 0.5 in size.

```sh
.venv/bin/python -m pytest tests/test_holder_cell.py tests/test_examples.py -k holder
.venv/bin/python -m ruff check src tests examples
```

## References

- Stinton, G. W. & Evans, J. S. O. (2007). *J. Appl. Cryst.* 40, 87-95, § 4.1.
- WP-2108 (the single-pattern recipe), WP-2103 (a joint fit's verbs), WP-2101 (a per-pattern
  variable through a formula equation), WP-1103 (declared peaks).

## Handover log

- **2026-11-22** — Filed by the session closing WP-2107, from WP-2108's "not tried" and
  its milestone row. Not folded into WP-2103: that WP adds verbs to a joint fit, and this
  recipe likely needs none, since WP-2101 measured the per-pattern-variable shape without
  a tie. It depends on 2103 only if that measurement fails here. Premises checked on main
  f590981ab. Next: the synthetic series.
