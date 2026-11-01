# WP-2049 — a frame no phase is seen in holds the instrument's peak terms too

Milestone: unscheduled · Status: ⬜
Track: What fires, and what stays silent
Depends on: —
Priority: P2 2026-10-25 — a confident number fitted to noise (zero shift at 4.8σ on a blank frame) and a series step flagged from it; sub-onset frames of a ramp are where it lands

## Goal

When no phase in a stage is seen, the instrument parameters that reach the
pattern only through phase peaks (zero shift, displacement, the profile terms)
are held for the stage like the unseen phases' own structural paths, and the
record says so. No result reports one of them with an esd fitted to noise.

## Context

WP-1301's hold (`refine._run_stage`, the `held` set; root CLAUDE.md § Invariants,
"A phase the data cannot see is a flat direction") holds every free structural
path of a phase whose scale is under 3σ of its counting-noise esd. It never
holds an instrument path, because one visible phase gives a shared column real
gradient ("all, never any", WP-1342). The case it misses is the frame where
**every** phase is unseen: then a peak-position or peak-width column reaches
nothing but unseen phases, and it is exactly as flat as their cells.

**Measured 2026-10-25** (`deff4c301`, macOS arm64, `[dev]`), on
`tests/planted_series.py`'s 248-frame series (seed 0), frame 87, the blank
frame. A 1e-14 nudge to the start cell picks which rung the ladder accepts:

| | rung | scale | zero shift | U..Y |
|---|---|---|---|---|
| outcome A (k = 0, −1) | `warm_staged` | 0, at its floor | held, no esd | held |
| outcome B (k = +1, ±2, +3) | `warm` | 8.6e-8 (1.8σ) | −0.02292 ± 0.00476 | refined |

Outcome B also fires `FLOOR_HIT` on `x`, `RESOLUTION_NOT_POSITIVE` twice, two
`HIGH_CORRELATION` pairs among U, V, X and Y, and `STAGE_MAX_ITER`.
`PHASE_UNCONSTRAINED` fires and holds `phases.0.cell.a` only. The zero shift's
step from frame 86 is −0.0289° against a series median of 1.2e-4°, so
`tests/test_planted_series.py::test_the_full_length_series_reproduces_its_committed_signals`
gains `['instrument.zero_shift', 86, 87]` in its `steps`. That row was red on
the Linux nightly on `deff4c301` (run 40184228951) for this reason. Outcome A
is what the committed signals record. The probe is
`docs/wp/2049-batch/frame87.py`.

Which rung wins is rounding. That an instrument column is refined on a frame
with no seen phase is not: it happens whenever the warm rung is accepted.

The tier of the rule this WP adds: physics. A column whose every reach is an
unseen phase is flat by the same argument WP-1301 made for a cell, so the
action is of Rule 1's first kind (`docs/DESIGN.md` § Rules). Which columns
qualify is read off C (`column_reach`), never off a path's name (WP-1342).

## Non-goals

- Which rung the ladder accepts on a blank frame (WP-1051's ladder).
- Background terms: they reach the pattern without any phase and stay free.

## Tasks

- [ ] Hold, in `_run_stage`'s support pass, each free instrument column whose
      reach (`column_reach`) lies wholly in unseen phases, beside the phases'
      own paths; record it in `StageResult.held` and `PHASE_UNCONSTRAINED`'s
      message.
- [ ] The joint twin in `multi.py`, and a series' carry: a held instrument
      value carries from the last frame that measured it.
- [ ] Tests: frame 87 at both nudges gives a held zero shift; the planted
      series' committed signals hold at k = 0 and k = +1.
- [ ] Skill: `PHASE_UNCONSTRAINED`'s row says the instrument can be held too.

## Acceptance

```sh
.venv/bin/python -m pytest -n auto --dist loadgroup tests/test_planted_series.py tests/test_held_phase.py tests/test_absent_phase.py
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-1301 (the hold), WP-1342 (reach, "all, never any"), WP-1051 (the ladder),
  WP-2036 (found it on the nightly).

## Handover log

- **2026-10-25** — filed by WP-2036's session after a measurement lane
  reproduced the nightly's planted-series red on an arm64 Mac. No open WP owns
  the hold: WP-1301 is closed, and what its fix did not cover is a new WP.
  Next: the first task.
