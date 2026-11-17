# WP-1942 — a soft restraint on a sum of parameters across phases

Milestone: unscheduled · Status: 🔄 2026-11-17 — all tasks built; PR #1642 awaits its fast suite
Track: Coming from another code
Depends on: —
Priority: P3 2026-10-11 — a named user has waited since 2026-09-01; a variable, a tie and a value restraint cover it today, clumsily

## Goal

A refinement can carry a soft restraint on a linear sum of parameters,
√w·(Σ c_k·p_k − target)/σ, where the paths may belong to different phases.
A helper builds the coefficients for a conserved elemental ratio from the
phases' element counts and cell volumes, so issue #212's
Cu/(Ca+Al) = 1.935 is one call.

## Context

**The use case (issue #212).** A supported-catalyst reduction series loses
only oxygen, so the elemental ratio Cu/(Ca+Al) keeps its as-prepared value of
1.935 throughout. Diffraction alone cannot split the unaccounted mass
between two phases: moving one of them 17 wt % costs 0.2–0.5 pp of Rwp. The
stoichiometry separates them decisively, since the two candidate partitions
imply 2.115 and 1.266.

**Why it is linear.** Moles of element E are proportional to
Σ_p S_p·V_p·n_{E,p}, and the (ZM)_p cancels. So the ratio r = Cu/(Ca+Al) is
the row Σ_p a_p·S_p = 0, with a_p = V_p·(n_{Cu,p} − r·(n_{Ca,p} + n_{Al,p})).
The partials are constant, and no expression language is needed.

**The seams, checked at `f11e22d3`.**
- `Structure` (`schemas/structure.py`) has one field, `phases`.
- `Phase.restraints` holds `BondRestraint`, `AngleRestraint` and
  `ValueRestraint`. A `ValueRestraint.path` is already any dot-path in the
  model tree, so a single-path row may name another phase today. A
  multi-path row has no type.
- `model/restraints.py`: `resolve_phase_restraints` compiles a phase's list
  to items, and `_Value.phase` is already `int | None`. A structure-level
  item can therefore carry `phase=None`. `restraint_residual`,
  `restraint_partials` and `summarise_restraints` read the items.
- `model/rows.py`: `BLOCK_ORDER` ends in `soft_restraint`. WP-1119's seam note
  said a new block. A new item kind inside `soft_restraint` may be enough,
  and it inherits the statistics exclusion (restraint rows stay in the
  covariance and out of Rwp, Durbin-Watson and Bérar-Lelann) and the stage's
  c_w (`Stage.restraint_weight_scale`). Task 1 decides.
- `model/geometry.py` calls `restraint_partials` at σ = weight = 1 for every
  reported geometry esd. A new item kind must be handled there, or excluded
  there by name.
- `optimize/qpa.py`: `phase_zmv(...)` computes `element_counts`, the
  occupancy-weighted atom count per element per cell.
  `PhaseQuantity` (`schemas/results.py`) does not carry it.
- `refine.py`: `RESTRAINT_TENSION_SIGMA = 3.0` and
  `_restraint_tension_diagnostics` flag a row the data pulls more than 3σ
  from its target, per pattern. `sequential.py`'s
  `SEQUENTIAL_PERSISTENT_FINDING` aggregates any code fired in over half a
  series' patterns, counted per (code, path). A multi-path row needs one
  stable `where` key, or the series count splits across its paths.

**What runs today, measured at `f11e22d3`.** Two synthetic cubic phases
(rock salt and Si, Cu Kα1, 20–110°, step 0.02°, true scale ratio 1/0.6). The
spelling: `add_variable("excess", ..., vary=True)`, then
`tie("phases.0.scale", {"vars.excess": 1/a0, "phases.1.scale": -a1/a0})`,
then a `ValueRestraint(path="vars.excess", target=0, sigma=...)`.
- With `"vars.*"` added to the first stage of `mccusker_default`, the fit
  converges. The scale ratio is 1.675 against 1.667 true, and `vars.excess`
  has an esd.
- With the preset unchanged, the plan replaces the vary flags (WP-1208), so
  the variable stays at its start value. Phase 1's scale went to its floor,
  and `MODEL_FAR_FROM_DATA` and `RESTRAINT_TENSION` fired.
- Three costs stay with the workaround. One scale becomes a dependent of
  two sources, so its bound reaches the solver only as an enclosing box,
  and a corner outside it raises on write-back after the solve (skill
  `references/surprises.md` § 8.22). The σ is in scale units, where the
  user means a σ on the ratio. And the caller must know to free `vars.*`.

The probe script is `scratchpad/t212/probe.py` in the 2026-10-11 triage
session. It is 50 lines and is restated by the first test this WP writes.

**The issue's fences, adopted.**
- **Soft, with an honest σ, and self-reporting.** Real phase weights do
  change. A mixed intermediate can form and disappear, and a hard constraint
  would hide it.
- **Coefficients from occupancies are frozen at declaration.** Chaining
  derivatives through refined occupancies is out of scope. A stage that
  frees an occupancy of a phase in the row makes the coefficient stale, and
  that must be reported, never silent.
- **No series-level pool or tie.** It cannot express a ratio, and it blurs
  the line between `sequential` (chained fits) and `multi` (one joint
  residual).

**Prior art, concepts only.** TOPAS states a constraint as a `prm` and an
equation over named parameters. GSAS-II carries linear constraints and
equivalences as (coefficient, parameter) lists. The (path, coefficient) pair
form here follows WP-1119's decision 4, which kept strings out of storage.

**Issue #349's three exports come with this WP** (from the 2026-10-11 issue
triage; WP-1325's mailbox, 2026-09-21): `rietx.navigate` (#349, fenced at
v2+) reads the same quantity. The three: `PhaseQuantity.element_counts:
dict[str, float]`; a weight-fraction covariance beside the existing
`weight_fraction_stderr` diagonal; and `FitReport.unidentified_phase`
(`present`, `n_foreign`, `n_shift_matched`, `strongest_two_theta`), which a
program today recovers by parsing `layer0_actions` for
`add_impurity_phase`. Rechecked at `6f704aaa5` (2026-11-17): none of the
three exists; `optimize/qpa.py`'s `ZMV.element_counts` is still internal.
The third shares no code with the row and may split off if it grows.
**Decided 2026-09-21** (posted on #349): when `navigate` is cut, the nominal
composition is an argument to `sample_from_result`, never a field on a
result, which records measurements only. The same rule binds the ratio
helper here: the declared ratio is an input, and no result field stores it
as if measured.

**What WP-1912 left to reuse** (from the 2026-10-13 triage, #727). The
floating-origin centroid landed without this item, as a row block of its own
(`origin_restraint`, `model/origin.py`), because its restraint has no σ and
the soft-restraint block's √c_w would free the origin at c_w = 0. What this
item reuses is the shape: a linear row whose partials are a constant matrix
over entry paths, chained through C (`origin.origin_partials`, beside
`restraints.restraint_partials`).

**The tier of each rule this WP adds** ([generality § The rule](../milestones/generality.md#the-rule)).
The row is arithmetic on the caller's own prior (tier 1, Waser 1963), and
the helper's coefficients are physics (tier 1, Hill & Howard 1987's
W ∝ S·ZMV). `RESTRAINT_TENSION` reuses its existing 3σ threshold. The
stale-coefficient report is arithmetic (a coefficient is a function of the
occupancies it was computed from), reports and acts on nothing, so it has no
kind of ambiguity. No published reference exists for the worked case: it
ships verified on synthetic known answers and not yet validated.

## Non-goals

- Nonlinear expressions over parameters. That is the formula tie
  (`Refinement.tie(path, expression=...)`, WP-2118; *superseded in part
  2026-11-17*: `Parameter.expr` left the schema at 0.61 and the DSL landed
  as ties over named variables, not as restraints).
- A hard linear constraint. `Refinement.tie` with several sources is one
  already (WP-1119).
- A parametric function of the series axis. That is WP-1325.
- A trigger on a consecutive run of tension across a series. The majority
  rollup exists. Measure a case it misses before building another.

## Tasks

- [x] Decide where the row lives: `Structure.restraints` (the issue's
      proposal and 1119's seam note) or a `LinearRestraint` kind in the
      existing per-phase union. Decide whether it is a new `BLOCK_ORDER`
      block or an item kind in `soft_restraint`. Record both in this file.
      *Decided 2026-10-13 (the maintainer, through the issue triage; #212):*
      the row lives on `Structure.restraints`, and it is an item kind inside
      the `soft_restraint` block, not a new `BLOCK_ORDER` entry: the
      reporter's answers in § Inherited, taken as written.
- [x] The schema type, (path, coefficient) pairs plus target, σ and weight,
      with its JSON round-trip and the `SCHEMA_VERSION` or project-format
      bump it needs. *Done 2026-11-17:* `LinearRestraint` (`terms` as
      `TieSpec.terms` stores them) on `Structure.restraints`, additive under
      the open 0.61 (no bump; its note in `schemas/common.py`); carried and
      renumbered through `carry_restraints` like a phase's own list.
- [x] Compile, residual and analytic partials; the geometry-esd path
      handles or excludes it; `summarise_restraints` and
      `RESTRAINT_TENSION` report it under one stable `where`. *Done
      2026-11-17:* `_Linear` in the soft-restraint block, key
      `restraints.<index>`; geometry builds its own items and never sees it.
- [x] The elemental-ratio helper: coefficients from `element_counts` and
      cell volumes, σ stated on the ratio, and a report when a stage frees
      an occupancy of a phase in the row.
- [x] The three #349 exports from § Inherited (now in Context). *Done
      2026-11-17 (a lane):* `PhaseQuantity.element_counts`,
      `QuantitativePhaseAnalysis.weight_fraction_covariance` (phase order,
      `None` where an esd is, rows summing to zero) and
      `FitReport.unidentified_phase`, a projection of the evidence
      `layer0_actions` words its `add_impurity_phase` from
      (`layer2._impurity_evidence`).
- [x] Tests: the probe above as a regression, a synthetic two-phase series
      where the ratio decides the partition, cross-backend agreement for the
      new partials (`tests/test_cross_backend.py`); obs/calc/diff PNGs to
      `tests/output/`.
- [x] Manual: Part 1 `using/constraints.md` (restraint vs constraint, the
      worked ratio); Part 2 the row's equation with its *Source* line.
      *Done 2026-11-17:* the manual has moved, so Part 1 is
      `guides/restrain.md` § Restrain a sum across phases and Part 2
      `theory/parameterisation.md`'s `par-linear-restraint` and
      `par-ratio-restraint`.
- [x] Skill: a reference row for the new restraint kind and the ratio
      helper, keyed by their names. *Done 2026-11-17:* one
      `references/diagnostics.md` row, keyed by `LINEAR_RESTRAINT_STALE`,
      naming `LinearRestraint`, `elemental_ratio_restraint` and the
      flat-partition trap; the API rows are the regenerated `api.md`.

## Acceptance

The issue's worked case, reduced to a synthetic two-phase pattern where
diffraction alone leaves the partition flat: the restrained fit recovers the
true weight fractions within their esds, and `RESTRAINT_TENSION` fires when
the declared ratio is wrong by 5σ.

```sh
.venv/bin/python -m pytest tests/test_restraints.py tests/test_cross_backend.py tests/test_qpa.py
.venv/bin/python -m ruff check src tests examples
```

## References

- Issue #212 (the use case, the linearity argument and the fences); issue
  #349 (the three exports).
- WP-1119 (named variables and multi-source ties; decisions 3 and 4);
  WP-1325 (parametric series, which names #212 as one instance).
- Hill, R. J. & Howard, C. J. (1987). *J. Appl. Cryst.* 20, 467-474 — the
  weight-fraction relation W_p ∝ S_p·(ZMV)_p the coefficients rest on.

## Handover log

- **2026-11-17 (later)** — gates run on the final tree, follow-ups filed,
  PR #1642 marked ready. Current main (13 commits) merged in cleanly first,
  so the counts below are the merged tree's.
  - *Measured:* fast suite on the workstation (Linux x86_64, `-n 8 --dist
    loadgroup -m "not slow"`, after a 4-file canary of 436 passed, 0 failed):
    3 failed, 14893 passed, 283 skipped, 32 xfailed on cf1ae813b. All three
    were rows the new code owed: `LINEAR_RESTRAINT_STALE` had no silence
    pair (`tests/silence.py`) and no joint-fit scope (`multi.DIAGNOSTIC_SCOPES`,
    absent: a joint fit refuses soft restraints), and the GUI help-key
    fixture lacked its key; fixed in 8ee692b02, after which those three files
    pass (5, 129 and 37) and `test_audit_table` 23 ([dev,jax], darwin arm64).
    `rietx_vale.sh` (the CI Vale step) 0 errors; `tests.reader_output` exit 0
    (unchanged against the merge-base); `test_docs_consistency` 26 passed;
    ruff clean.
  - *Filed:* #1653, the small follow-ups named below (the QPA table export
    and the series trajectory do not carry `element_counts` or
    `weight_fraction_covariance`; the GUI list join drops structure-level
    rows).
  - *For the maintainer:* the Acceptance asks `RESTRAINT_TENSION` to fire on
    the flat-partition pair when the ratio is wrong by 5σ; measured, it
    cannot there (no data pull on the partition), and fires only where the
    data measure it. The tests pin both halves; whether that is the
    acceptance wanted is his call. The tier of `LINEAR_RESTRAINT_STALE`
    (tier 1, arithmetic) is for his read.
  - *Next:* review of #1642.

- **2026-11-17** — every task built, review fixes in; PR #1642 (draft), its
  fast suite and handover steps still owed. A refinement can now hold a sum of
  parameters across phases near a target as a soft observation, and one call
  turns a conserved elemental ratio (issue #212's Cu/(Ca+Al)) into that row.
  On a synthetic pair whose partition the pattern cannot measure (Cu and Ni
  on one fcc cell, unrestrained W_Cu ± 0.97) the ratio row recovers the
  weight fraction to 0.643426 ± 0.0032 against 0.643425 true. The flip side,
  measured and pinned: where the data cannot see the partition, a wrong ratio
  is met silently and `RESTRAINT_TENSION` cannot fire; it fires (−3.6σ) only
  where the data measure the partition (Cu, Ni on their own cells). The three
  #349 exports landed too.
  - *Done:* `LinearRestraint` on `Structure.restraints` (open schema 0.61, no
    bump); `_Linear` in the soft-restraint block keyed `restraints.<k>`, with
    the cross-backend row `toy_linear` (numpy and jax agree); carried through
    edits by the phase list's place rule; `elemental_ratio_restraint`
    (`model/restraints.py`) and `LINEAR_RESTRAINT_STALE` (read off the values
    against the row's declared `occupancies`, so an earlier stage or a series
    carry is seen); `PhaseQuantity.element_counts`,
    `QuantitativePhaseAnalysis.weight_fraction_covariance`,
    `FitReport.unidentified_phase` (a lane); manual `guides/restrain.md` and
    `theory/parameterisation.md` (`par-linear-restraint`,
    `par-ratio-restraint`); skill row in `references/diagnostics.md`.
  - *Review:* a read-only reviewer found four bugs (a row deleted in an edit
    that renumbers phases was silently re-read; a trailing phase removed
    refused the edit; the stale check saw only the last stage; a misspelt
    element built a row) and an inverted σ statement (it is σ·D₀/D away from
    the declared scales); all fixed in fb126f579 with tests. Generality:
    `LINEAR_RESTRAINT_STALE` judged *weak* because it reports no size of the
    change; the message now quotes each occupancy's declared and current value.
    A refined cell volume also moves a coefficient and is not reported (stated
    in the docstring and the theory page).
  - *Measured* ([dev,jax], darwin arm64): `tests/test_linear_restraint.py` 24
    passed; a touched-area selection (restraints, qpa, cross_backend,
    schemas, manual_api, help, audit, planarity) 670 passed, 115 skipped
    before the review fixes; `tests.reader_output` exit 0 (unchanged); Vale
    over the manual 0 errors before the review-fix prose edit.
  - *Not done:* the fast suite on the final tree; Vale re-run after fb126f579;
    the PR body. `io/exporters.py` and `schemas/sequential.py` do not carry the
    new QPA fields; the GUI's list-payload join (`gui/session.py` near 4170)
    would drop structure-level rows (the GUI cannot author them).
  - *Next:* run the fast suite (on the workstation, canary first), re-run
    `rietx_vale.sh`, rewrite the PR body from this entry, mark #1642 ready.

- **2026-10-11** — created, from the 2026-10-11 issue triage (issue #212).
  Checked against the tree at `f11e22d3`: every seam the issue names exists
  as described, `Structure` holds no cross-phase list, and a variable plus a
  multi-source tie plus a `ValueRestraint` already expresses the row when
  the plan frees `vars.*`. No open WP owns it: WP-1119 (✅) decided on
  2026-09-04 that the row is a WP of its own, and WP-1325's mailbox and
  ROADMAP both recorded that nobody had cut it. WP-1340 touches
  `PhaseQuantity` for mole fractions and takes none of the three exports.
  *Next:* task 1.
