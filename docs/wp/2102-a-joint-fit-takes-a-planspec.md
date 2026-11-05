# WP-2102 — a joint fit takes a PlanSpec

Milestone: parametric · Status: 🔄 2026-11-05 — claimed by @yue-here (ghostshift runner)
Depends on: —
Priority: P2 2026-11-04 — a raise on a documented input type, and an expert's own plan is the first thing they pass

## Goal

`refine_multi` accepts every form of plan that `Refinement.fit` accepts, and each
`report` reads a plan the way the fit that made the result did.

## Context

`refine_multi(plan=PlanSpec(...))` raises `AttributeError: 'PlanSpec' object has no
attribute 'run_stages'`. Found on 2026-11-03 while probing the joint surface as an
expert would. The workaround is a `RefinementPlan` built from `Stage`s.

Root CLAUDE.md § Plans states the rule: a mirror is crossed at the two authorities that
own it, never at a call site, and `resolve_plan` (`strategy/staged.py:801`) converts the
spec outbound. `Refinement.fit` (`refine.py:5374`) and the series path
(`sequential.py:1470`) call it. Three call sites instead test `isinstance(plan, str)`
and look the preset up by hand:

- `multi.py:1431`, `MultiHistogramRefinement.fit`.
- `multi.py:1550`, `MultiHistogramRefinement.report`.
- `refine.py:6493`, `Refinement.report`.

Both signatures in `multi.py` are annotated `RefinementPlan | str`.

The two sites differ. `fit` crashes. Both `report` methods accepted a `PlanSpec` in a
review's probe of 2026-11-04, because `apply_strategy_veto` reads only what the two
types share. What they skip is `resolve_plan`'s mode substitution, and neither has a
`mode` argument, so a report passes `result_.mode`. `project._as_plan_spec`
(`project.py:477`) converts the other way, toward a spec, and is a fourth place to read.

## Non-goals

- Any other change to what a joint fit accepts: [2103](2103-a-joint-fit-has-the-verbs-a-single-fit-has.md).

## Tasks

- [x] Route `fit` through `resolve_plan`, passing `mode`, and widen the annotations.
- [x] Route both `report` sites through it with `result_.mode`. Check whether a report
  on a Le Bail or Pawley result changes, since the substitution then applies. If it
  does, that is a reader-output change and goes to the maintainer.
- [x] Test: a `PlanSpec` and the `RefinementPlan` it converts from give bit-identical
  answers on `refine_multi`.
- [x] Grep for a fourth site and say in the handover what was checked.
- [x] Skill: "none" and why, unless the skill names the limit.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_multi_histogram.py -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-1110 (the mirror rule).

## Handover log

- **2026-11-04** — Filed from the expert-surface probe of 2026-11-03. No open WP owned
  it. It stands alone because it can land in one sitting ahead of everything else in
  the milestone. Next: the first task.
