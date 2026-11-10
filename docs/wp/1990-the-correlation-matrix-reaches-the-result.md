# WP-1990 — the correlation matrix reaches the result

Milestone: unscheduled · Status: 🔄 2026-11-09 — six of seven tasks landed (#1475); the printed block and a joint fit's matrix wait on the maintainer
Track: Render what the fit already knows
Depends on: —
Priority: P3 2026-10-16 — a view over what the fit already computes; the one defect in it is a suggestion naming a field that does not exist, which misleads but changes no number

## Goal

A `RefinementResult` carries the full parameter correlation matrix with its
paths, a caller can export it in one call, and the `HIGH_CORRELATION_OMITTED`
suggestion points at a field that exists.

## Context

Issue #992 (mustachefeeling, 2026-10-15). TOPAS writes the normalised
correlation matrix on request (`C_matrix_normalized`); rietx computes the
full P×P matrix on every fit and keeps five pairs.

What the tree holds, checked at `138d55dc`:

- The solver forms ρ from the final undamped Jacobian:
  `LSQOutcome.correlation` (`optimize/least_squares.py`, field at line 212),
  sign-corrected for decreasing transforms at line 399, so it is already
  quoted against the user-facing paths.
- `Refinement` holds the covariance privately (`_answer_covariance`,
  `refine.py`).
- `Identifiability` (`schemas/results.py:292`) has `top_correlations`,
  `soft_modes` and `exchangeability`, and no matrix field.
  `top_correlations` is cut at `TOP_CORRELATIONS_K = 5`
  (`optimize/identifiability.py:51`).
- **The defect**: the `HIGH_CORRELATION_OMITTED` row's suggestion
  (`schemas/results.py`, built in the cap at line ~1219) reads
  "result.identifiability carries the full correlation matrix and
  top_correlations list". The first half names nothing. This is the root
  CLAUDE.md's "a message that names its discriminator makes the same claim"
  rule (WP-1076, WP-1118): either this WP makes the sentence true, or the
  sentence changes.
- A joint multi-histogram fit runs no parameter-space screens yet
  (`multi.py`), so the field stays `None` there and means "not measured".
- **Superseded in part, 2026-11-08 (checked at `63d7c120`):** since
  WP-2050 the `HIGH_CORRELATION` guard no longer reads
  `LSQOutcome.correlation` verbatim in a single fit. `check_guards`
  (`strategy/staged.py`) projects out every direction the Jacobian cannot
  resolve (`statistics.resolved_correlation`), so a pair with one
  unresolved member is `nan` and the resolved pairs can differ from the
  solver's. The field carries **that** matrix, the one the guard and
  `top_correlations` read, which is this WP's own reason for choosing ρ; it
  equals `LSQOutcome.correlation` wherever nothing is unresolved, and an
  undetermined pair is `None` rather than a number. Line numbers above have
  drifted (`LSQOutcome.correlation` at 216, `Identifiability` at 353, the
  suggestion in `_cap_one_code`), the facts not.
- The tier of each rule this WP adds: none. The field carries a statistic
  (ρ, arithmetic, tier 1) the fit already computes, and the export is a
  call the caller makes; no flag, threshold or automatic action is added or
  moved.

Why ρ and not the covariance or JᵀWJ, per the issue: ρ is unitless, χ²_red
and the Bérar–Lelann factor cancel in it, and it is the matrix the
`HIGH_CORRELATION` guard reads, so a view and the diagnostics cannot
disagree.

### Inherited

## Non-goals

- The GUI Correlations view (heatmap, threshold filter, click-to-select in
  Params). #992 asks for it as a second WP on this one's field; it is filed
  when this lands, or folded here if the maintainer decides one WP.
- Any change to what `HIGH_CORRELATION` fires on (WP-1460 owns its
  per-pair duplication).

## Tasks

- [x] Decide storage: on the final answer only, or on every history node.
  Measure first: the packed lower triangle of P = 300 is ~45k floats, and a
  history node is ~10 kB today (root CLAUDE.md § Conventions).
  **Decided 2026-11-08: the final answer only** (`RefinementResult`, never a
  `HistoryNode`). Measured on the five-stage LaB6 fit of
  `tests/test_high_correlation_dedup.py` (P = 15 at the answer, 4750
  points; `.venv` `[dev]`, macOS arm64): a node is 5.7-8.5 kB of JSON
  (median 7.8 kB), the result 481 kB. The packed triangle, diagonal
  included, is 2.3 kB at P = 15, 9.3 kB at P = 30, 102 kB at P = 100 and
  922 kB at P = 300 (45 150 floats). On a node that is +30 % at P = 15,
  ×2 at P = 30 and ×120 at P = 300, on every stage of every plan; on the
  result it is 0.5 % at P = 15 and comparable to the curves the result
  already carries at P = 300. A node stores state, not curves, and the
  matrix is evidence about one answer, which is what the result is.
- [x] `Identifiability.correlation` (paths in table order, packed lower
  triangle), `None` where not measured; `SCHEMA_VERSION` bump under WP-1117.
  Landed as a `CorrelationMatrix` (`paths`, `lower`; `matrix()`, `rho()`,
  `from_square()`), filled from `GuardReport.measured_correlation`; 0.61 is
  unreleased, so it is an "Also in 0.61" entry, not a new number.
- [x] An export: a labelled table and a CSV writer beside the existing
  exports. `rietx.io.exporters.correlation_table_csv` /
  `write_correlation_table` and `Refinement.write_correlation_table`; not
  re-exported at the top level, which would have grown the skill's `api.md`.
- [ ] The text FitReport's printed block, if the maintainer wants it on by
  default: rows with at least one off-diagonal |ρ| over the guard only.
- [x] Correct the `HIGH_CORRELATION_OMITTED` suggestion to name the new
  field, with a test that the named attribute exists.
  The suggestion (shared with `FLAT_DIRECTION_OMITTED`) now names
  `result.identifiability.correlation` and `.top_correlations`, and says a
  joint fit carries neither; the test resolves every `result.…` name it
  quotes through the declared fields, and failed on the old text.
- [x] Tests (round-trip, the field equal to `LSQOutcome.correlation`, `None`
  on a joint fit)
  `tests/test_correlation_matrix.py` (11), plus the joint `None` asserted on
  the fit `tests/test_joint_report.py` already runs.
- [x] Skill: the reference row for `HIGH_CORRELATION_OMITTED` names the
  field, or "none" if the package's own suggestion now carries it
  The suggestion carries it, so both `*_OMITTED` rows now point at the
  suggestion rather than restating a field (−58 B on `diagnostics.md`).

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_high_correlation_dedup.py -q   # plus the file this WP adds
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- TOPAS Technical Reference, `C_matrix_normalized` (the file's keyword
  list; papers-only fence for TOPAS).
- Issue #992.

## Handover log

- **2026-11-09** — six of the seven tasks landed (PR #1475); the printed
  block waits on the maintainer. A finished fit now carries every pair's
  correlation, not only the five worst, so a reader can see the whole
  picture of which refined parameters moved together, and can save it as a
  labelled table in one call. The hint that appeared when too many
  correlated pairs were listed used to point at a matrix that did not
  exist; it now names the real field, and a test fails if it ever names
  one that is not declared. Nothing about what is flagged, or any number
  the fit reports, changed.

  *Done.* Storage decided by measurement (task 1's entry: the result only,
  never a history node). `CorrelationMatrix` (`schemas/results.py`: `paths`,
  `lower`, `matrix()`, `rho()`, `from_square()`) on
  `Identifiability.correlation`, filled from
  `GuardReport.measured_correlation`, which `check_guards` stores from the
  same resolved matrix it thresholds; packed from the upper half the guard
  reads, so a quoted pair is the entry bit for bit (the lower half differed
  in the last digit on LaB6). `SCHEMA_VERSION` stays 0.61 (unreleased) with
  an "Also in 0.61" entry. Export: `rietx.io.exporters.correlation_table_csv`
  / `write_correlation_table` (a result or the matrix; refuses a result
  with none) and `Refinement.write_correlation_table`, documented in the
  manual's result and exports pages; not re-exported at the top level,
  which would have grown the skill's `api.md`. Suggestion and help text;
  skill rows (−58 B).

  *Measured.* See task 1 (node 5.7-8.5 kB, result 481 kB, triangle 2.3 kB at
  P = 15 to 922 kB at P = 300). Fast selection (`-m "not slow"`, `-n 2`,
  `.venv` `[dev]`, macOS arm64, on the Mac because pearl did not answer
  a wake; main had not moved, so branch = merged tree): 14351 passed,
  415 skipped, 32 xfailed, 16:01 with another shift's suite queued
  beside it. passed+skipped includes the 11 added tests; no local
  baseline was run (CI's job). The added tests cost 0.12 s in the
  junit total (the shared fit sits in a module fixture). Full selection
  not run: no measured number can move (a field added, nothing
  computed differently). `tests.reader_output` exit 0.

  *Gotchas.* `import rietx.refine` binds the `refine` function, not the
  module (`importlib.import_module("rietx.refine")` in the test's spy). A
  joint fit **does** threshold its own correlation matrix
  (`multi._top_diagnostics`, since WP-2028), unprojected, so it can emit
  `HIGH_CORRELATION_OMITTED`; the field is `None` there as this WP rules,
  and the suggestion says so ("a joint multi-histogram fit carries neither
  yet").

  *Review.* `/code-review` could not be pointed at this worktree from the
  runner's session, so an Opus subagent reviewed `origin/main...HEAD`: no
  correctness finding; one low prose gap (`FLAT_DIRECTION_OMITTED`'s help
  lacked the joint-fit clause), fixed. It measured the WP-2050 margin on
  the LaB6 fixture (smallest unit-normal eigenvalue 5.8e-3 against a cut
  of 1.2e-11), so the exact-equality test has no unresolved pair to meet
  on another platform. *Generality*: not dispatched — `_audit.py` is
  untouched and nothing adds a heuristic (no inline literal, fallback or
  action).

  *Questions for the maintainer.* (1) The printed block in the text
  FitReport (task 4): on by default, rows with an off-diagonal |ρ| over the
  guard only, or not at all? Nothing was built. (2) Should a joint fit carry
  its matrix too? It already forms and thresholds one; carrying it is
  `CorrelationMatrix.from_square(free, outcome.correlation)` in
  `multi.py`, and would let the suggestion drop its joint-fit clause. The
  WP ruled `None`, so it stays `None` until you say otherwise. (3) The GUI
  Correlations view (non-goal; #992's second half) is yours to file as a WP
  when this lands; no issue was opened for it, since #992 already asks.

  Next: the maintainer's answers to (1) and (2); with (1) "no" and (2) "no",
  the WP closes as is.
- **2026-10-16** — created, from the 2026-10-16 issue triage (issue #992).
  Checked against the tree at `138d55dc`: `Identifiability` has no matrix
  field and the `HIGH_CORRELATION_OMITTED` suggestion claims one; the solver's
  `LSQOutcome.correlation` is the full matrix, sign-corrected. No open WP owns
  it: WP-1460 owns how often `HIGH_CORRELATION` fires, not what the result
  carries. Next: the storage measurement, then the field.
