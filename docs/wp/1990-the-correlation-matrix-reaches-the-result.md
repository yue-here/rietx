# WP-1990 — the correlation matrix reaches the result

Milestone: unscheduled · Status: 🔄 2026-11-08 — claimed by @mustachefeeling
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

- [ ] Decide storage: on the final answer only, or on every history node.
  Measure first: the packed lower triangle of P = 300 is ~45k floats, and a
  history node is ~10 kB today (root CLAUDE.md § Conventions).
- [ ] `Identifiability.correlation` (paths in table order, packed lower
  triangle), `None` where not measured; `SCHEMA_VERSION` bump under WP-1117.
- [ ] An export: a labelled table and a CSV writer beside the existing
  exports.
- [ ] The text FitReport's printed block, if the maintainer wants it on by
  default: rows with at least one off-diagonal |ρ| over the guard only.
- [ ] Correct the `HIGH_CORRELATION_OMITTED` suggestion to name the new
  field, with a test that the named attribute exists.
- [ ] Tests (round-trip, the field equal to `LSQOutcome.correlation`, `None`
  on a joint fit)
- [ ] Skill: the reference row for `HIGH_CORRELATION_OMITTED` names the
  field, or "none" if the package's own suggestion now carries it

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

- **2026-10-16** — created, from the 2026-10-16 issue triage (issue #992).
  Checked against the tree at `138d55dc`: `Identifiability` has no matrix
  field and the `HIGH_CORRELATION_OMITTED` suggestion claims one; the solver's
  `LSQOutcome.correlation` is the full matrix, sign-corrected. No open WP owns
  it: WP-1460 owns how often `HIGH_CORRELATION` fires, not what the result
  carries. Next: the storage measurement, then the field.
