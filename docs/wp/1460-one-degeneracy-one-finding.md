# WP-1460 — one degeneracy, one finding

Milestone: unscheduled · Status: ⬜
Track: What fires, and what stays silent
Depends on: — (1454 soft: it removed the commonest source; 1302 soft: the render cap)
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
(`SEQUENTIAL_PERSISTENT_FINDING` across a series), `viz/compare.py`,
`io/recipe.py`, `optimize/identifiability.py`, `help.py`,
`gui/src/App.test.ts`, `tests/test_high_correlation_dedup.py` and the skill's
`references/diagnostics.md`. The grep is a starting list, not the audit: a
reader that keys on `where` without naming the code is the one it misses.

### Inherited

- **From WP-1906 (2026-10-06), a count on a skill's worked example.** The
  P-spline default (`rx.auto_background(data)`) on FAP.XRA under
  `mccusker_structural` reports 770 `HIGH_CORRELATION` findings and two
  `FLAT_DIRECTION`, against none with `kind="chebyshev"` on the same fit
  (cells equal to 2e-7 Å). So the skill's worked default uses a Chebyshev
  background, and the body says nothing about the flood. When this WP lands,
  the default can go back to the P-spline.
- **From WP-1545 (2026-10-07), the tutorials took the same workaround.**
  Notebook 01's Le Bail fit of FAP.XRA under `profile_only` reported 832
  `HIGH_CORRELATION` rows with `rx.auto_background(data)` (770 with
  `two_theta_limits=(15, 130)`) against none with a 6-term Chebyshev. Notebooks
  01 and 02 use the Chebyshev, and 01's prose names the flood as the reason.
  When this WP lands, rewrite that paragraph in
  `examples/tutorials/01_quickstart.py` and rebuild the notebook.
- **From WP-2050 (2026-11-01), the guard now knows the unresolved set.**
  `check_guards` reads `statistics.resolved_correlation`, which names the
  columns an unresolved eigen-direction dominates (eigenvalue ≤ n·FD_STEP²
  on the unit-diagonal matrix). A ρ against one of them is `nan` and never
  reported. That set is the candidate this WP's grouping wants for its flat
  case, and it is recorded nowhere yet: a set-level finding naming it would
  also be the record WP-2050's generality review asked for. Two gaps it left
  for this WP. No message says which pairs were withheld (Yue's ruling of
  2026-11-01: a correlation whose value is rounding is not shown to users;
  the mask is a developer signal a nightly test asserts). Two unresolved directions leave ρ
  between members of different ones set by rounding (by construction; not
  measured).

## Non-goals

- Changing `correlation_guard` or `FLAT_DIRECTION_RHO` (WP-1454's non-goal too).
- The render cap. It stays, and it is what keeps `summary()` short today.

## Tasks

- [ ] Audit the readers above, and write here which of them count rows, key on
      a pair, or print them.
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

- **2026-09-24** — created by WP-1454's task 2 on its own branch, from the
  audit above. Next: the reader audit, because it decides whether grouping can
  replace the pair rows or has to ride beside them.
