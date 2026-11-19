# WP-2103 — a joint fit has the verbs a single fit has

Milestone: parametric · Status: ✅ 2026-11-17 — a joint fit holds, ties, sets values and restarts from its answer in one stage (PR #1643; follow-ups #1649)
Depends on: 2102 soft; 2081 soft (how a series holds what the setup fixes)

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

**Owed to WP-2101 (2026-11-19): a joint fit's hold must silence `VARIABLE_NOT_FREED`.** This PR added the hold verb, so the condition below now applies and is not met here.
The code names each parametric equation whose coefficients no plan stage freed. In a
single fit, a coefficient the caller holds is left out, read off the table with
`ParameterTable.held_by` (maintainer's ruling 2026-11-19, option (a)). A joint fit has
no hold verb yet, so `multi._parametric_not_freed_diagnostics` names every unfreed
coefficient, and its docstring says so. When this WP adds `hold` to a joint fit, that
builder leaves out a held coefficient the same way, with a test that fails when the
filter is removed.

## Non-goals

- A history DAG for a joint fit.
- `run_stage` on a joint fit, unless the restart task shows it is the cheaper shape.
- Variables at construction: `variables=` is [1964](1964-a-parametric-equation-the-user-writes.md)'s.

## Tasks

- [x] Survey which verbs an expert reaches for, from the two Durham inputs and the
  TOPAS and GSAS-II sequential docs. Write the keep and decline list here, each decline
  with its reason. (§ The survey below.)
- [x] `hold`/`unhold`, reported through `blocked_by_hold` as a single fit is.
- [x] `tie`/`tie_equal`/`untie` across histograms, or a refusal naming `sharing=`. A
  source atom in each pattern works, as WO₃'s protocol needs.
- [x] `add_variable` on a joint fit, or a refusal naming `variables=`.
- [x] `set_values` by canonical path.
- [x] A restart: refit from the last answer, per-pattern values and coefficients both,
  in process and from a saved result. The bar: a converged fit restarted stops in one
  stage and moves nothing by more than 0.01 esd.
- [x] Manual: `reference/joint.md`, and the partition in `tests/api_surface.py`.
- [x] Skill: the series reference's joint row.

### The survey (2026-11-17)

Sources: `docs/practice.md` (GSAS-II's sequential run, its Hold constraint, "Copy flags",
`Copy2Next`, checked in source there), this WP's Context on TOPAS (`prm` flags edited and
rerun from stored values, `load_save_locals`), and the WO₃ protocol of
`docs/wp/1964-measure/wo3_formula.py`. No web source was read in this session.

**Kept**, each built on `MultiHistogramRefinement`:

- `hold`/`unhold`: GSAS-II's Hold constraint ("will not be varied, even if vary flag is
  set") and the calibrate-then-hold practice the 2026-11-03 ruling names.
- `tie`/`tie_equal`/`untie`, linear and `expression=`: GSAS-II's equivalences and TOPAS's
  `prm` equations; WO₃'s one B per pattern tied across the sites.
- `add_variable`: TOPAS's `prm`, which a tie names.
- `set_values`: editing a stored value before a rerun, as an expert edits an `.inp`.
- `refit` (the restart): TOPAS's rerun from stored values (`load_save_locals`) and
  GSAS-II's start from an earlier run's results.

**Declined**, each with its reason:

- `set_vary`: a plan replaces the vary flags (WP-1208), so a joint fit frees through its
  plan's globs and keeps a row fixed through `hold` (#1205's ruling stays for this verb).
- `run_stage`: `refit` is the cheaper shape for the restart task (one stage at the
  answer's window fraction) and a plan stage covers the rest (Non-goals).
- A history (`checkout`, nodes): a Non-goal; `parameters()` carries `held` and `user`
  ties, and the stages carry `blocked_by_hold`, in its place.
- `profile_interval`: the Goal names it, but no task does, and a joint profile refits the
  whole stack per point. Filed as a follow-up issue.
- `remove_variable`: a variable lives in every pattern's table, which cannot drop a row
  without a rebuild; no task asks for it. The same limit makes `untie` refuse a formula
  tie (the follow-up issue covers both).
- GSAS-II's "Copy flags" across histograms: a bare glob already reaches every pattern's
  row, so it is the default spelling here.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_multi_histogram.py tests/test_parametric_series.py tests/test_manual_api.py
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-1325 (the joint path), WP-1435 (the hold), WP-1070 (user ties), WP-2081.

## Handover log

- **2026-11-17** — A joint fit can now be steered by hand the way a single fit is. A
  person can hold a calibrated setup through every pattern, tie each pattern's sites to one
  B (WO₃'s protocol) or to a variable of their own, set values, and rerun a converged fit
  from its answer in one stage, in process or from a result saved to JSON. Nothing a joint
  fit already did moves: the reader output is unchanged, and the new hold report fires only
  on a caller's hold. Left for #1649: a joint profile interval, taking a formula tie or a
  variable back, and the mirrored WO₃ run.

  *Done.* `MultiHistogramRefinement.hold`/`unhold`/`tie`/`tie_equal`/`untie`/`add_variable`/
  `set_values`/`refit`, each a thin call onto `MultiParameterTable`, which holds the
  registers (`user_holds`, `user_ties`, `user_variables`), the authority every stage reads.
  Rows are named as `parameters()` prints them. A bare tie target is tied in every pattern,
  each to its own source; a source in another pattern, a bare target onto one pattern's row,
  and a shared target onto a per-pattern source are refused naming `sharing=`. A stage glob
  reaching a row tied onto a variable frees the variable, as a parametric expression's are
  freed (`_parametric_reached`), unless it is declared `vary=False`. `_hold_diagnostics`
  moved from ABSENT to FIT in `multi.py`'s placement table: a joint result now says
  `HOLD_BLOCKED_PLAN`. `parameters()` marks a caller's tie `user=True`. `refit` runs one
  stage, `"restart"`, through a private `_RestartPlan` whose stage compiles at the window
  fraction the answer's last stage ran at, with no closing stage. The WP-1964 inherited case
  is `test_a_tie_onto_an_expression_variable_drops_that_pattern_from_the_form_test`. The
  survey is in § Tasks.

  *Measured* (macOS arm64, worktree venv `[dev]`, Python 3.12). The restart bar: 1 iteration,
  0.0 esd moved, in process and from saved JSON, on the cheap LaB6 pair; a one-stage restart
  at the default window fraction moved 2.9 esd, which is why `_RestartPlan` exists. Positive
  arm: `cell.a` set 50 esd off comes back within 3e-5 esd in 4 iterations. Form test on the
  five-pattern line: 5 patterns, 3 dof untied; 4 and 2 with pattern 4's background tied onto
  `vars.c0`. `tests/test_joint_verbs.py` is 19 tests, about 6.5 s serial. Related files
  (multi_histogram, parametric_series, manual_api, multi_diagnostics, audit_table,
  parametric_expression, joint_report) 410 passed serially before the review fixes. On the
  workstation (venv rietx-py312, Linux): canary gs2103c 113 passed in 36 s on d60b979bc.
  Its fast suite was paused for memory beside other jobs and not re-admitted for 20 min, so
  it ran on the Mac instead (`-n 4`, behind the shared suite lock): 14706 passed, 432 skipped,
  32 xfailed, 0 failed, on d60b979bc plus this entry. Added tests: 3.5 s in all. ruff clean; Vale 0 errors; `python -m tests.reader_output` exit 0.

  *Review.* A read-only reviewer found three bugs, each fixed with a test that fails on the
  parent (d60b979bc): a tie on a shared size row ignored the WP-1131 value scales (it is now
  written in each pattern's units, and a formula on such a row is refused); `unhold` missed
  per-pattern rows a bare `hold` had held; and a refused formula could stay installed in an
  earlier pattern's table (every table's refusal is now asked of a copy first).

  *Decisions.* Inherited from WP-2101: the mirrored WO₃ run moves out of this WP to #1649,
  and which spelling of one B per pattern the milestone row judges (this WP's tie, or
  WP-2101's formula) is the maintainer's; #1649 recommends the tie. `add_variable` defaults
  to `vary=True`, unlike `Refinement.add_variable`, matching the constructor's `variables=`
  rule that a stage frees a variable through the rows it drives.

  *Gotchas.* A joint fit's per-pattern tables are never rebuilt, so the registers stand in
  for `Refinement._ties` only as the list `untie`/`unhold` read; a formula or a variable
  cannot be taken back (#1649). `tie_equal` with `hist.*.` raises a plain int-conversion
  error rather than a worded refusal.

  Next: #1649's three items, the WO₃ decision first, since it sets what the milestone row
  judges.

- **2026-11-04** — Filed on the opening of the milestone. No open WP owned it: 2081
  discusses the chain, whose surface differs, and 1325's task "Ties and variables reach
  the joint table" is closed and shipped no verb. Member lists read from the tree that
  day. Next: the survey.
