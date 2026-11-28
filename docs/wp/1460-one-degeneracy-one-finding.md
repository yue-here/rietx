# WP-1460 — one degeneracy, one finding

Milestone: unscheduled · Status: 🔄 2026-11-28 — task 1 done; Yue ruled 2026-11-17 that groups replace the pair
rows, built per stage (handover log); the grouping waits on PR #1475
Track: What fires, and what stays silent
Depends on: 1990 (PR #1475; Yue 2026-11-17: the grouping lands after it); 1454 soft (it removed the commonest source); 1302 soft (the render cap)
Priority: P3 2026-09-24 — a correct report said once per pair, up to hundreds of times, burying the rows beside it; `summary()` already caps the view and dropping the rows is the workaround

## Goal

A strongly correlated or flat direction across n parameters is reported once,
as a finding that names the n parameters. Today it is up to n(n−1)/2
`HIGH_CORRELATION` rows plus as many `FLAT_DIRECTION` rows. And the source the
fast selection still floods on, an air term `auto_background` declares beside a
spline that can already draw 1/(2θ), is measured and decided.

## Context

**The guard.** `check_guards` (`src/rietx/strategy/staged.py`, the loop after
`if outcome.correlation is not None`) appends a `HIGH_CORRELATION` finding for
every pair above `correlation_guard` (0.98), and a `FLAT_DIRECTION` beside it
at or above `FLAT_DIRECTION_RHO` (1 − 5·10⁻⁴). `refine._dedup_high_correlations`
keeps one row per pair across stages (WP-1302). `schemas.results._cap_high_correlation`
bounds each code at `HIGH_CORRELATION_MAX = 10` **for rendering only**, so
`summary()` is bounded while `RefinementResult.diagnostics` keeps every row.
One flat direction across n columns is therefore n(n−1) stored rows.
*Superseded in part, 2026-11-16 (checked at `bc77a934e`):* the loop is now
`staged._correlation_findings`, which `check_guards` and the joint fit's
`MultiRefinement._top_diagnostics` (`multi.py`) both call (WP-2028 task 7).
The cap bounds two codes, `HIGH_CORRELATION` and `FLAT_DIRECTION`, each on
its own budget of 10 and each with its own `info` row for what it left out
(`HIGH_CORRELATION_OMITTED`, `FLAT_DIRECTION_OMITTED`; `results._CAPPED_PAIR_CODES`).

**The unresolved set (from WP-2050, 2026-11-01).** `check_guards` reads
`statistics.resolved_correlation`, which names the columns an unresolved
eigen-direction dominates (eigenvalue ≤ n·FD_STEP² on the unit-diagonal
matrix). A ρ against one of them is `nan` and never reported. That set is the
candidate this WP's grouping wants for its flat case, and it is recorded
nowhere yet: a set-level finding naming it would also be the record WP-2050's
generality review asked for. Two gaps it left for this WP. No message says
which pairs were withheld (Yue's ruling of 2026-11-01: a correlation whose
value is rounding is not shown to users; the mask is a developer signal a
nightly test asserts). Two unresolved directions leave ρ between members of
different ones set by rounding (by construction; not measured). Checked
2026-11-16: the joint fit's `_top_diagnostics` passes `outcome.correlation`
to `_correlation_findings` without the mask, so the single fit and the joint
fit threshold different matrices.

**The cost.** WP-1454 read an agent session whose first completed fit printed
about 8 kB, most of it these rows. It then dropped every background-only row
and lost `CAPILLARY_OFFSET_UNAVAILABLE` with them. WP-1454 removed the
commonest source: a declined air term that every plan freed anyway. On NAC at
0.75° knots that took the count from 1074 rows to 0.

**What remains, measured 2026-09-24** (WP-1454 task 2). `check_guards` was
wrapped over the whole fast selection (`[dev]`, Linux x86-64, 5886 passed), and
each call's `HIGH_CORRELATION` pairs were grouped into connected components.
443 calls in 186 tests carried at least one row:

| params in the component | rows | calls | where |
|---|---|---|---|
| 2 | 1 | 423 | everywhere, and correct |
| 3 | 2 | 8 | chains |
| 3 | 3 | 15 | cliques, e.g. scale–Biso–extinction, zero–displacement–cell |
| 4 | 6 | 1 | the capillary offsets on 11-BM (`test_capillary_displacement`) |
| 6 | 13 | 2 | profile u, v, x and the zero shift (`test_diagnostics_geometry`) |
| 23 | 45 | 5 | a spline made rigid by a stiff penalty (the intensity-unit arm of `test_the_penalty_is_equally_stiff_in_any_intensity_unit`) |
| 24 | 276 | 1 | a zero air term declared on purpose (`test_an_undeclared_air_term_raises_no_background_correlation_rows`) |
| 35 | 569 | 2 | `test_pspline_refines_a_curved_background`, below |

**The case a user meets is the last row.** On a humped pattern
`auto_background` chose 3° knots and, because its diagnostics fired, declared
the air term. 1/(2θ) is smooth enough to lie almost inside the span of any
spline fine enough to follow a hump. So a declared term is the same flat
direction a declined one was, and it floods on an intermediate stage of the
default lab plan. On NAC at 8° knots the same term gave one row, so how much a
declared air term buys beside a P-spline depends on the knots. That is not yet
measured. One path declares the term with no rise in range at all.
`auto_background(data, diagnostics=diagnose(data), two_theta_limits=(40, 110))`
uses the caller's whole-file diagnostics as given, so a rise below 40° declares
a 1/(2θ) column over 40-110°, where it is flatter still. WP-1454's review found
this path and declined to change it, because "used as given" is the documented
contract. Decide it with the air-term task below.

**Candidates for grouping** (from WP-1454): connected components of the
thresholded pairs, which is what the table above used; or the flat
eigen-directions of the Jacobi-scaled normal matrix.
`optimize.identifiability.soft_modes` already computes the softest modes of the
unit-column normal matrix, and `GuardReport.measured_soft_modes` carries them.
A component is not a direction: a 3-clique can hold two independent near-flat
directions, and a chain can join two unrelated pairs. So the finding has to
say which it is, and it cannot claim "one degeneracy" where the eigen-analysis
counts two.

**Every reader of the rows is audited first** (WP-1103: a list with one kind
of member is where a count goes wrong). A grep for the code on 2026-09-24
found `refine.py` (`_dedup_high_correlations`, the stage loop's
`correlation_hits`), `schemas/results.py` (`_cap_high_correlation`,
`summary()`), `sequential.py` and `schemas/sequential.py`
(`SEQUENTIAL_PERSISTENT_FINDING` across a series; *superseded 2026-11-16:*
WP-2003 replaced it by `SeriesResult.code_counts`), `viz/compare.py`,
`io/recipe.py`, `optimize/identifiability.py`, `help.py`,
`gui/src/App.test.ts`, `tests/test_high_correlation_dedup.py` and the skill's
`references/diagnostics.md`. The grep is a starting list, not the audit: a
reader that keys on `where` without naming the code is the one it misses.

**The reader audit (task 1, 2026-11-16, at `bc77a934e`).** Every place the
rows are written, read, counted or printed, found by grepping both codes, the
`GuardReport` fields `high_correlations`/`flat_directions`, the
`*_OMITTED` codes, and every `.where` and `len(...diagnostics)` reader in
`src/` and `gui/src/`, then the asserts in `examples/` (a guide script is a
test pin, since `tests/test_examples.py` runs every one, and a published
page). *Counts* means the reader's output changes with the
number of rows; *pair* means it keys on the two paths of one row; *prints*
means a person or client sees each row.

| reader | where | counts | pair | prints | what a group row does to it |
|---|---|---|---|---|---|
| the finding loop | `staged._correlation_findings`; called by `check_guards` and the joint fit's `MultiRefinement._top_diagnostics` | — | writes one finding per pair | — | the seam: a group is built here or just after it |
| the converter | `refine._guard_diagnostics` (one `Diagnostic` per finding: `where` = the pair, `value` = ρ) | — | yes | — | `value` is one float; a group's \|ρ\| range has no field to sit in |
| per-stage record | `refine` stage loop: each stage's `stage_diagnostics` goes onto its history node and `stage_reports_` uncapped and not deduplicated | stores | yes | via GUI | every stage keeps every pair today; but `stage_reports_` is off by default (`fit(stage_reports=False)`, refine.py near 5694) and the history lives on the `Refinement`, not on `RefinementResult`, so a caller holding only a result (a series entry, a saved JSON, a batch item) has neither |
| GUI history row | `gui/session.py` node route, `n_diagnostics = len(node.diagnostics)` | **yes** | — | yes | the count on a node falls with grouping |
| `Refinement` repr | `_display.refinement_text` (near 571): "`{len(result.diagnostics)} diagnostics`" on the last-fit line | **yes** | — | yes | the count falls with grouping, as the summary header's |
| stage-loop collection | `refine` `correlation_hits`, keyed `(code, frozenset(where))` | — | **yes** | — | a component whose membership changes from stage to stage has no stable key |
| cross-stage dedup | `refine._dedup_high_correlations`: worst \|ρ\| over every stage, "Flagged in stages", sorted by \|`value`\| | — | **yes** | — | needs a key and a sort value for a group |
| discarded-direction gate | `staged.check_discarded_directions` (and `multi.py` beside the joint loop): drops `COVARIANCE_DIRECTION_DISCARDED` when its touched set ⊆ a `FLAT_DIRECTION`'s paths | — | **yes** (subset test) | — | a group of n paths would silence every touched set inside it, not only one that is a single pair |
| render cap | `results._cap_one_code`/`_cap_high_correlation`: >10 rows per code → the worst 10 plus an `*_OMITTED` row whose `value` is the count | **yes** | — | yes | by design; with grouping it rarely fires. Its `*_OMITTED` row (results.py near 1652) suggests "result.identifiability for the full correlation matrix", which `Identifiability` does not have at `bc77a934e` (only `top_correlations`, the worst five): the suggestion is false until PR #1475 merges |
| summary header | `results._diagnostic_header`: "N rows, E errors" off the stored list | **yes** | — | yes | the header count falls |
| purpose levels | `results.level_under` / `diagnostic_view`: a row is a warning under a purpose if any `where` path bears on it | — | per path | sets level | a group is a warning under every purpose **any** member bears on; today each pair is judged alone, so a background–scale pair and a background–background pair differ |
| batch tally | `report/batch.py`: `CodeTally.n_rows`, `n_warning`, and the Pareto of warnings by row count | **yes** | — | yes | today the flood dominates the Pareto's shares; grouping changes every share |
| series counts | `sequential._code_counts` → `SeriesResult.code_counts`: once per pattern per `(code, path)`, each path of a row counted | per pattern | per path | yes | **unchanged** only if the group row keeps the code name (`HIGH_CORRELATION`/`FLAT_DIRECTION`; a new group code moves every count to a new key) **and** its `where` is the union of its above-threshold pairs' paths (a group built from eigen-directions rather than components can name a different member set) |
| GUI result panel | `gui/session.py` result route sends every row; `gui/src/lib/report.ts` `orderDiagnostics` ("none dropped") | — | — | **every row, uncapped** | the cap never reached the GUI: a flood is printed in full there today |
| compare UI | `viz/compare.py` `RunRecord.diagnostics` → `compare_app/static/compare-core.mjs` `diagnosticsHtml` | — | — | **every row, uncapped** | as the GUI panel |
| guide pages (`examples/`) | `guides/holder_cell.py:152` asserts a `FLAT_DIRECTION` with `set(d.where) == {"vars.zero", "vars.height"}`; `guides/calibrate.py:97,104` assert `[d.code for d in …diagnostics] == ["HIGH_CORRELATION"]`; `tutorials/02b_steering_a_refinement.py:100` filters on `"instrument.zero_shift" in d.where`, and its prose (line 104) speaks of a pair | **yes** (calibrate) | **yes** (holder_cell, an exact match) | yes, on the published pages | under "replace", holder_cell fails if the pair falls in a component with a third path (the union is no longer the pair): the one case where "replace" breaks a user-facing page; under "beside", calibrate fails if a group row is added next to a lone pair, unless groups need three or more members; 02b survives a union, but its prose would need a word |
| magnetic fold | `strategy/magnetic.py` (docstring near 1667) | — | — | — | **not a reader**: it reads `_answer_covariance` because the deduped rows keep an earlier stage's \|ρ\| (#592) |
| identifiability | `Identifiability.top_correlations` (five worst pairs, answer stage); PR #1475 (WP-1990, open) adds `Identifiability.correlation`, the whole answer-stage matrix, `None` on a joint fit | — | — | — | a route to "every pair reachable" that is not a row, but answer stage only: no earlier stage's \|ρ\|, no "Flagged in stages" |
| vocabulary | `help.py` entries for the four codes, `_audit.py` rows for them and for `HIGH_CORRELATION_MAX`/`FLAT_DIRECTION_RHO` | — | — | — | a new code needs both, and CI's `audit_delta` refuses it at `unaudited` |
| prose only | `optimize/identifiability.py`, `optimize/statistics.py`, `io/recipe.py`, `viz/compare.py` (variant notes), `schemas/instrument.py`, `schemas/plan.py`, `crystallography/wyckoff.py`, `sequential.py` docstring, `refine.py` origin messages | — | — | text | no reader |

Tests that pin the current shape: `tests/test_high_correlation_dedup.py`
(15 stored `HIGH_CORRELATION` rows on a constructed result, "15 rows" in the header,
pair-keyed dedup, the cap's counts); `tests/test_walking_bounds.py` (one
`HIGH_CORRELATION` and one `FLAT_DIRECTION` per flat pair, keyed apart, each
capped at 10 with `value` 4.0 on the omitted row);
`tests/test_background_auto.py::test_an_undeclared_air_term_raises_no_background_correlation_rows`
(asserts the flood: more background-only rows than coefficients);
`tests/test_acceptance_powderline.py` (a `HIGH_CORRELATION` pair touching
`extra_components`, by `frozenset(where)`); `tests/test_capillary_displacement.py`
(a `FLAT_DIRECTION` whose `where` holds the cell and an offset, which a
superset still passes); `gui/src/App.test.ts` (a node row whose `where` is a
pair); and the guide scripts in the table's `examples/` row (holder_cell's
exact pair, calibrate's exact code list). **One test keys on `message`, not
`where`**: `tests/test_magnetic.py` (near 1835) asserts no correlation row's
*message* names the moment DOF `dof1`, so a group message listing n paths
would change what it tests. Every other test reads presence or absence of the code
(`test_floating_origin`, `test_acceptance_si640c`, `test_phase_significance`,
`test_background_measured`, `test_v02_core`, `test_acceptance_lab6_cbn`,
`validation_matrix.py`'s `!HIGH_CORRELATION`), which any grouping that keeps
the code name leaves alone.

What the audit settles. **No reader in `src/` outside `refine.py`/`staged.py`
needs a pair row to exist**: the series count is invariant if a group keeps
the code name and its `where` is the union, and the pair-keyed readers in
`src/` are internal (`correlation_hits`, the dedup, the discarded-direction
gate). Outside `src/`, one guide (holder_cell's exact-pair assert) does key
on a pair. What changes for a caller is counts (the header, the batch tally,
the GUI node count, the `Refinement` repr) and one level rule
(`level_under` over a union). The cap is not what a user sees in the GUI or
the compare UI: both print every row, so the flood reaches those surfaces
today. **What it does not settle** is the question below, which is the
maintainer's because it changes what `RefinementResult.diagnostics` stores.

**Question for Yue (before task 2).** *Answered 2026-11-17: replace, built per stage
after PR #1475 (handover log, 2026-11-28).* Does a group finding **replace** the pair
rows in `RefinementResult.diagnostics`, or **ride beside** them?
- *Replace*: one row per group, `where` = the union, the pairs reachable
  through `Identifiability.correlation` (PR #1475), and through the stage
  records only with `stage_reports=True` or the live `Refinement`'s history.
  So "replace" depends on PR #1475 merging first: without its matrix a caller
  holding only a result has five pairs (`top_correlations`), not every pair.
  Callers lose a row per pair and the earlier-stage \|ρ\| the dedup keeps;
  `level_under` judges the union; the GUI and compare UI stop flooding;
  holder_cell's guide assert needs rewriting.
- *Beside*: the pair rows stay and the group row is added, as `FLAT_DIRECTION`
  rides beside `HIGH_CORRELATION` (WP-1311). No caller loses anything, but
  stored rows grow by one per group, and the acceptance ("no component
  reported as more findings than it has independent directions") cannot hold
  unless the pair rows are demoted (`info`) or moved under the group;
  calibrate's guide asserts break unless a group needs three or more members.
- A sub-question either way: is a group built **per stage** (each stage's
  matrix, then deduplicated by membership) or **from the answer stage** only
  (the matrix PR #1475 stores and the magnetic fold reads)? The dedup today
  keeps the worst \|ρ\| from any stage, so the two give different groups.

The tier of each rule this WP adds: none from task 1, which is an audit. The
grouping reuses `correlation_guard` and `FLAT_DIRECTION_RHO`, and WP-2050's
unresolved cut (eigenvalue ≤ n·FD_STEP²) if it counts eigen-directions, so it
adds no threshold if it stays with those; task 2 confirms that. Task 4's
choice for `auto_background` is a default, whose kind of ambiguity (DESIGN.md
§ Rules, 1) task 4 names.
- **From the 2026-11-19 issue triage (issue #1704), a flat direction whose third member is the
  cell.** Checked against the tree at `dccc45bdb` (macOS arm64, `[dev]` venv) with the
  `lab6` protocol of `tests/test_window_domain.py`: SRM 660c over 20.3-84.6° 2θ, the zero shift
  freed in the displacement's stage. Reproduced to the digit of the issue's Linux numbers. The
  cell lands −984 ppm from the CIF, 6.48 reported esds (17.6 plain). Its reported esd is
  152 ppm, 16× the zero-held fit's 9.6 ppm, so the esd did grow, but not enough to cover the walk.
  The zero lands at −0.344 ± 0.052° and the displacement at −0.690 ± 0.093 mm against the CIF's
  −0.079 mm. `FLAT_DIRECTION` names only `zero_shift ~ sample_displacement` (ρ = 0.99991). The
  cell sits in two `HIGH_CORRELATION` rows, ρ 0.99887 with the zero and 0.99817 with the
  displacement, just under `FLAT_DIRECTION_RHO`. So the finding a reader sees names the pair and
  not the number the reader quotes. A grouping by component would report {zero, displacement,
  cell} as one finding; that is this WP's task 2 with a real fixture. Over the full range
  (20.3-150.9°) the same arm is −23 ppm, 1.76 reported esds, with no `FLAT_DIRECTION`.
  The walk is larger than the esd because the esd measures counting noise only, and a nearly
  flat direction amplifies any systematic misfit along it. That is not WP-2219's case: no
  direction falls under `PINV_RCOND`, and every esd here is finite. Three texts promise more
  than the fit gives, and the grouping's skill task should fix them together:
  `help.py`'s `sample_displacement` entry ("the cell's esd grows to show it", rendered into
  `reference/parameters.md`), which PR #1577 does not touch while it corrects the manual's twin
  sentence in `reference/instrument.md`; `help.py`'s `FLAT_DIRECTION` entry ("Each esd is
  conditional on the other parameter being right"), whereas `statistics.normal_covariance`
  inverts the whole matrix, so the esds are marginal; and the skill's `FLAT_DIRECTION` row
  ("Quote either member as measured, and do not read the esds"), which never reaches a third
  parameter outside the pair. The preset is not this WP's to change: the `lab_bragg_brentano`
  plan text already says to free both only where something pins one. Priority stays P3: a flag
  fired, on the pair. To reproduce: `test_window_domain._protocol("lab6")`, append
  `instrument.zero_shift` to the stage whose `turn_on` holds the displacement, and fit with
  `two_theta_limits=(20.3, 84.6)` (about a minute).

## Non-goals

- Changing `correlation_guard` or `FLAT_DIRECTION_RHO` (WP-1454's non-goal too).
- The render cap. It stays, and it is what keeps `summary()` short today.

## Tasks

- [x] Audit the readers above, and write here which of them count rows, key on
      a pair, or print them. Done 2026-11-16: § The reader audit, and the
      question for Yue under it, which task 2 waits on.
- [ ] Decide the grouping: components, eigen-directions, or components
      annotated with their eigen-count. Write the decision and its evidence
      here. The table above is the fixture set.
- [ ] Land it. A group names its parameters and its |ρ| range, and the pair
      rows stay reachable, since a caller already keys on `where`.
- [ ] The declared air term beside a P-spline. On public data (NAC, round-robin
      sample 2, a pattern with a real low-angle rise), measure what the term
      buys against the spline alone at `auto_background`'s knot spacings.
      Then decide whether `auto_background` still declares it with a spline,
      couples it to the knots, or leaves it to the caller.
- [ ] Skill: the `HIGH_CORRELATION` and `FLAT_DIRECTION` rows in
      `references/diagnostics.md`, if the shape changes.
- [ ] Once the grouping lands, undo the two workarounds the flood forced.
      The skill's worked example uses `auto_background(..., kind="chebyshev")`
      (`docs/skill/rietx/SKILL.md`), because the P-spline default on FAP.XRA
      under `mccusker_structural` reported 770 `HIGH_CORRELATION` and two
      `FLAT_DIRECTION` rows against none with the Chebyshev, cells equal to
      2e-7 Å (WP-1906, 2026-10-06): it can go back to the P-spline. Tutorial
      01 uses a 6-term Chebyshev and its prose names the flood as the reason
      (`examples/tutorials/01_quickstart.py`, "hundreds of correlated
      coefficient pairs"; WP-1545 measured 832 rows under `profile_only`, 770
      with `two_theta_limits=(15, 130)`): rewrite that paragraph and rebuild
      the notebook. Both still true at `bc77a934e`.

## Acceptance

The table above, re-run with the grouping in place: no component reported as
more findings than it has independent directions, and every pair still
reachable.

```sh
.venv/bin/python -m pytest tests/test_high_correlation_dedup.py tests/test_background_auto.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-1454 (the air term, the audit that filed this), WP-1302 (dedup and the
  render cap), WP-1311 (`FLAT_DIRECTION`), WP-1103 (the reader audit).

## Handover log

- **2026-11-28** — post-merge bookkeeping for PR #1597 (maintainer side, ghostshift runner; PR
  #1889). PR #1597 merged today as `0f4894d58`. Yue answered the question task 2 was waiting on, on
  2026-11-17, posted on #1597. A group finding replaces the pair rows in
  `RefinementResult.diagnostics`. It is built in `check_guards` at every stage where pairs are built
  today, and it lands after PR #1475 (WP-1990). The goal is one finding per degeneracy, since a pair
  row beside its group repeats it. `Identifiability.correlation` keeps every pair reachable. Mike
  acknowledged the ruling on #1597 on 2026-11-18.

  *What the ruling settles.* Replace, not beside. The sub-question too: groups are built per stage
  (`check_guards` runs at each stage, `staged.py`, called from `refine.py`), not from the answer
  stage only. *What it leaves to task 2:* the grouping itself (components, eigen-directions, or
  components with their eigen-count), and how groups from different stages are deduplicated,
  since today's dedup keeps each pair's worst \|ρ\| from any stage.

  *Checked against `origin/main` at `0f4894d58`:* PR #1475 is open, not merged, so task 2 cannot
  land yet. `check_guards` and `_correlation_findings` are in `strategy/staged.py`. The Depends-on
  line now names WP-1990 as hard, by the ruling's order. No checklist item landed with #1597
  beyond task 1, already ticked.

  *Gotcha for task 3.* Its text says the pair rows stay reachable "since a caller already keys on
  `where`". Under the ruling they stay reachable through `Identifiability.correlation` instead.
  The audit above records that this field is `None` on a joint fit. So what a joint fit's caller
  can reach under the ruling is open. Task 3 should say what that caller gets.

  Next: wait for PR #1475 to merge. Then task 2: re-measure the fixture table on current main (its
  counts are from 2026-09-24), choose the grouping and the cross-stage dedup, and write both here.
  Task 3 lands it. Mike's claim holds the WP.

- **2026-11-16** — The reader audit is done, and it narrows what the grouping
  has to protect. Nothing in `src/` outside the stage loop and the guard code
  needs a pair row to exist (one guide script, holder_cell, asserts an exact
  pair), and the series count comes out the same if a group keeps the code
  name and names the union of its pairs' paths. What a group would change for a caller is a
  handful of counts and one rule that sets a row's level per purpose. The
  audit also found that the render cap never reached the GUI's result panel or
  the compare UI: both print every row, so a user meets the flood there today
  whatever `summary()` shows. Task 2 was not started, because whether a group
  replaces the pair rows or rides beside them changes what a result stores,
  and that is the maintainer's call.
  *Done:* § The reader audit (a table of every writer, reader, counter and
  printer, with file and symbol), the tests that pin the current shape, and
  the question for Yue with its sub-question (per stage or answer stage only).
  *Inherited pruned:* WP-2050's entry folded into Context, with a new check
  beside it (the joint fit's `_top_diagnostics` thresholds the solver's
  matrix without WP-2050's unresolved mask); WP-1906's and WP-1545's
  workarounds (the skill's worked example and tutorial 01 use a Chebyshev
  because of the flood) are still true at `bc77a934e` and became one
  task to run once the grouping lands. *Stale premises:* the guard loop is now
  `staged._correlation_findings`, shared with the joint fit (WP-2028); the cap
  bounds two codes on separate budgets, each with an `*_OMITTED` row;
  `SEQUENTIAL_PERSISTENT_FINDING` is gone (WP-2003, now
  `SeriesResult.code_counts`); `COVARIANCE_DIRECTION_DISCARDED` (WP-1535) is a
  new pair-keyed reader. *In flight elsewhere:* PR #1475 (WP-1990, open) adds
  `Identifiability.correlation`, the answer stage's whole matrix, which is one
  way to keep every pair reachable under "replace"; it carries no
  earlier-stage \|ρ\| and is `None` on a joint fit. Prose only: no src or
  test change, so no suite ran beyond the docs gate (PR #1597).
  *Next:* Yue answers the question under § The reader audit; then task 2,
  starting from the table's fixture set re-measured on current main, since
  its counts are from 2026-09-24.

- **2026-09-24** — created by WP-1454's task 2 on its own branch, from the
  audit above. Next: the reader audit, because it decides whether grouping can
  replace the pair rows or has to ride beside them.
