# WP-1999 — a held cell's ties leave the answer with it

Milestone: unscheduled · Status: 🔄 2026-10-19 — claimed by @yue-here
Track: A long run is not one fit
Depends on: —
Priority: P2 2026-10-18 — a reported value that is not a measurement, on the series path (a trajectory point with no fit behind it)

## Goal

When WP-1301 holds a phase's cell for a stage, every parameter tied to a held
path leaves `RefinementResult.parameters` with it. A series trajectory then
has no point at that pattern for any cell edge, where today it has none for
`a` and a stale one for `b` and `c`.

## Context

Found by WP-1545's notebook 05 lane (2026-10-18), on the broken-frame series:
at 700 K the phase's scale reaches its floor, `PHASE_UNCONSTRAINED` holds the
cell, and `series.trajectory("phases.0.cell.a")` correctly has no 700 K point.
`trajectory("phases.0.cell.b")` does. Its value is the previous pattern's
carried value and its esd is `None`.

**The mechanism.** The hold sets a held path's `vary` to `False` before the
answer is built. The result's rows come from `refine.py:6953`, which keeps an
entry when `e.vary or e.tie is not None or e.path in derived`. A tetragonal or
cubic cell ties `b` (and `c`) to `a`, so the followers pass on their tie while
their source is gone. Root CLAUDE.md's hold clause says "a value that is not a
measurement is the caller's: held paths leave `RefinementResult.parameters`".
The followers are the same non-measurement.

**What to decide.** Whether the filter should drop a tied row whose sources are
all held (the narrow fix), or every tied row whose sources do not move
(`ParameterTable.moving_paths`, the root rule for "can this parameter move?").
The second also drops followers of a user-fixed source, which every result
reports today with esd `None`. That changes the reported set for ordinary fits,
so measure how many goldens and tests move before choosing.

## Tasks

- [ ] Reproduce with a single fit (a cubic phase whose scale is floored) and
  with WP-1545's notebook 05 broken series.
- [ ] Choose the narrow or the `moving_paths` rule, with the count of moved
  tests for each.
- [ ] The fix at `refine.py:6953`, and a test that a held source's followers
  leave `parameters` and the trajectory.
- [ ] Find the siblings: any other surface that lists a tied row beside its
  source (`Refinement.parameters()`, the GUI's parameter table, a CIF export,
  `stage_reports_`), and say which hold the same leak.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_held_phase.py tests/test_sequential.py -n auto --dist loadgroup
```

## Handover log

- **2026-10-18** — filed by WP-1545's session. No open WP owns it: WP-1420 is
  about a held phase *re-entering* a chain, and this is a reporting leak a
  single fit shows too.
