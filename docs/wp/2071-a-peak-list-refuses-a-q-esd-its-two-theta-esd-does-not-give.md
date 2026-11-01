# WP-2071 — A peak list refuses a q_esd that its two_theta_esd does not give

Milestone: unscheduled · Status: 🔄 2026-11-01 — claimed by @yue-here (ghostshift runner)
Track: What fires, and what stays silent
Depends on: —
Priority: P3 2026-10-31 — a silent no-op, but no package path produces it: only a caller's hand edit of `two_theta_esd` does, and rebuilding through `PeakList.from_positions` is the workaround

## Goal

`PeakList` validates `q_esd` against `two_theta_esd` the way it already validates `q`
against `two_theta`, so an edit to one uncertainty that leaves the other stale is refused
by name rather than silently ignored by the indexer.

## Context

**Source.** Issue #1236 (2026-10-30, @mustachefeeling). `ObservedPeak` stores the
position twice (`two_theta`, `q`) and its esd twice (`two_theta_esd`, `q_esd`).
`PeakList._q_matches_two_theta` (`schemas/indexing.py:991`) ties `q` to `two_theta` at
rtol 1e-9 and names the remedy; nothing ties `q_esd`. The SVD indexer weights lines by
`PeakList.q_esd()` (`indexing/svd.py`, through `sigma_effective`), so an edit to
`two_theta_esd` never reaches the search. The reporter's weighting experiment ran an arm
that was a no-op and read "no effect".

**Reproduced at `d87c8cc91`** (the issue's snippet): `from_positions` with
`two_theta_esd=0.002`, peak 1's `two_theta_esd` tripled by `model_copy`, round-tripped
through `model_validate_json` with no error; `two_theta_esd` ratio 3.0, `q_esd` ratio 1.0.

**The check is safe to add** (checked at `d87c8cc91`): both constructors,
`indexing/pick.py` `peaks_of_group` (line 338) and `PeakList.from_positions` (line 1091),
derive `q_esd` through `schemas.indexing.q_esd_of_two_theta`; nothing in `src/` edits
`two_theta_esd` after construction. The reporter checked 1318 picked lists (59 975 lines)
from two commits: all satisfy it exactly.

**Siblings.** `d` is a property, so it cannot drift. `two_theta_esd_fit` is deliberately a
separate number (the fit's σ before a merge widened it, #934) and needs no tie. The
`wavelength` already reaches `q` through the existing check. No other derived field
is stored on `ObservedPeak`.

**Design.** Extend the existing validator in the same vectorised pass: compare stored
`q_esd` with `q_esd_of_two_theta(two_theta, two_theta_esd, wavelength)` at a relative
tolerance; a pair where both are non-finite agrees. The message names the same remedy as
the `q` check. Making `q`/`q_esd` computed fields instead would remove the duplication
but changes the serialised schema; this WP does not.

**Tier.** Arithmetic on the list's own fields (physics): no `_audit` row unless the
refusal gets a diagnostic code.

**Old files.** A stored peak list written by any shipped constructor satisfies the check
exactly, per the reporter's 1318-list control. A hand-edited stored list would now fail
to load; the message must say how to rebuild it.

## Non-goals

- Making `q`/`q_esd` computed fields (a schema change).
- Any change to how the indexer weights lines.

## Tasks

- [ ] The `q_esd` check in `_q_matches_two_theta` (or a sibling validator), relative
      tolerance, non-finite pairs agree, message naming the remedy.
- [ ] Tests: the issue's reproduction now raises; both constructors' lists pass; a JSON
      round trip of a picked list passes; a non-finite pair passes. Make it fail once on
      purpose and read the message.
- [ ] Skill: none. The refusal names its own remedy, the package's own output.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_peak_picking.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

No test of the existing `q` refusal was found at `d87c8cc91` (grep for its message), so
the new test file or `tests/test_peak_picking.py` covers both checks.

## References

- Issue #1236 (reproduction and the 1318-list control).

## Handover log

- **2026-10-31** — created by the issue triage from #1236. No open WP owns the peak-list
  schema: WP-1520 (a search refines each assignment once) reads `q_esd` but owns the
  refinement memo, and WP-1915 (an unmeasured direction poisons a candidate's esds) owns
  candidate covariance.
