# WP-2103 — a joint fit has the verbs a single fit has

Milestone: parametric · Status: ⬜
Depends on: 2102 soft; 2081 soft (how a series holds what the setup fixes)
Priority: P2 2026-11-04 — a feature the open milestone was opened for: an expert steers a fit by hand, and a joint fit offers them almost nothing to steer with

## Goal

A user steers a joint fit the way they steer a single fit. They can hold a parameter,
tie one, set a value, refit from where the last fit ended, and ask for a profile
interval, on the object they already have.

## Context

`MultiHistogramRefinement` has seven public members: `fit`, `fitted_instruments`,
`fitted_structures`, `n_histograms`, `parameters`, `parametric` and `report`. `Refinement`
adds `set_vary`, `set_values`, `add_variable`, `tie`, `tie_equal`, `untie`, `hold`,
`unhold`, `run_stage` and `profile_interval`, and a history. So on a joint fit the only
steering is the `sharing=` map and `parametric=` at construction, and a plan.

The maintainer's ruling of 2026-11-03 bears directly: a series calibrates the setup and
holds it through the series. On a joint fit today that hold has no verb.

The tie has a named customer. WP-1325 had to hold WO₃'s one B per pattern at the chain's
value because a joint fit has no tie verb (`1325-measure/wo3_ramp.py`), where the chain
writes `tie_equal(...biso, "vars.B")`. The milestone's WO₃ row needs that B refined.
`SharingMap.is_shared` treats a `vars.` path as shared, so that line would give one B
across every pattern. WO₃ wants one per pattern. So its tie takes one atom's biso as the
source in each pattern, or 1964's variable per pattern once that lands.

An expert's habits set the bar. In TOPAS they edit a `prm` flag and reruns from the stored
values. `load_save_locals` (v8 onwards, formerly `use_stored_values`) writes each
pattern's local values to a file and reads them back on a restart (Durham tutorial 9.4).
A 100-pattern refinement is rarely right on the first run, so a restart that loses the
per-pattern values costs a whole fit.

The seams:

- `params/multi.py`, `MultiParameterTable`: the shared table. `_canonical` already
  maps a per-histogram path to its shared column.
- `refine.py`'s verbs auto-commit history nodes. A joint fit has no history, so a verb
  here records nothing of that kind. Say what stands in for it, or nothing does.
- A hold is read by `ParameterTable.set_vary` from `Entry.held`, in the table and never
  at the call site (root CLAUDE.md § A hold). Keep that.
- A user tie survives a rebuild through `Refinement._ties`. The joint table needs the
  same authority.

[WP-2081](2081-how-a-series-holds-what-the-setup-fixes.md) is a design discussion about
the chain, and its answer on what "held" means should govern here. Read it first.

## Non-goals

- A history DAG for a joint fit.
- `run_stage` on a joint fit, unless the restart task shows it is the cheaper shape.
- Variables at construction: `variables=` is [1964](1964-a-parametric-equation-the-user-writes.md)'s.

## Tasks

- [ ] Survey which verbs an expert reaches for, from the two Durham inputs and the
  TOPAS and GSAS-II sequential docs. Write the keep and decline list here, each decline
  with its reason.
- [ ] `hold`/`unhold`, reported through `blocked_by_hold` as a single fit is.
- [ ] `tie`/`tie_equal`/`untie` across histograms, or a refusal naming `sharing=`. A
  source atom in each pattern works, as WO₃'s protocol needs.
- [ ] `add_variable` on a joint fit, or a refusal naming `variables=`.
- [ ] `set_values` by canonical path.
- [ ] A restart: refit from the last answer, per-pattern values and coefficients both,
  in process and from a saved result. The bar: a converged fit restarted stops in one
  stage and moves nothing by more than 0.01 esd.
- [ ] Manual: `reference/joint.md`, and the partition in `tests/api_surface.py`.
- [ ] Skill: the series reference's joint row.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_multi_histogram.py tests/test_parametric_series.py tests/test_manual_api.py
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-1325 (the joint path), WP-1435 (the hold), WP-1070 (user ties), WP-2081.

## Handover log

- **2026-11-04** — Filed on the opening of the milestone. No open WP owned it: 2081
  discusses the chain, whose surface differs, and 1325's task "Ties and variables reach
  the joint table" is closed and shipped no verb. Member lists read from the tree that
  day. Next: the survey.
