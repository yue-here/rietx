# WP-1512 — A simulated diffuse curve is a component, and its amplitude rides on the phase scale

Milestone: unscheduled · Status: 🔄 2026-11-18 — claimed by @yue-here (ghostshift runner)
Track: Data and metadata in, a structure out
Depends on: —
Priority: P3 2026-09-28 — a workaround covers it (the background slot plus a refit loop), and since 1.5.0 that workaround breaks silently on a preset

## Goal

A curve on 2θ computed by another program (a stacking-fault diffuse term
from DIFFaX, a Debye sum, an amorphous reference) enters a fit as a member
of `Instrument.extra_components`, with its own amplitude, its source and its
σ. A tie holds that amplitude to a phase scale, so "the diffuse term is
locked to the Bragg scale" is one declared constraint instead of a loop of
refits.

## Context

**Source.** `solution case 1` (private corpus map § 5), described in
WP-1510. The agent modelled stacking faults in DIFFaX and fitted
`y = Chebyshev + S·Bragg + S·c*·D(2θ)`: D the faulted minus the ideal DIFFaX
pattern, c* a unit conversion it calibrated with `Refinement.predict()` at
scale 1, S the phase scale. The lock mattered. A free diffuse amplitude is
degenerate with the background and the Bisos, so only a locked one tests
whether the diffuse term helps. It found no seam for this and built one:

- S·c*·D went in as the fixed curve of `BackgroundFixedPlusChebyshev`, with
  `fixed_source` unset.
- An outer loop refit up to four times, rebuilding the curve from the new
  phase scale until S moved by less than 1 %.
- c* was calibrated once, over a narrower 2θ window than the final fit
  used.
- The curve was interpolated onto the data at 2θ minus the fitted zero
  shift, by hand.

**The workaround breaks silently now.** In 1.4.0 the fixed curve had no
scale. WP-1309 (1.5.0) added `instrument.background.scale`, and every preset
frees `instrument.background.*`. Checked on `c1bd21dd` with a minimal
script: a stage turning on `phases.0.scale` and `instrument.background.*`
frees `c0`–`c3` *and* `scale`. So the run's script, rerun today, lets the
diffuse amplitude float free of the phase scale, and nothing says so. WP-1309
recorded that break for a *measured* blank, with `instrument.background.c*`
as the escape. A simulated term is a different object and should never have
been in that slot.

**The seam.** `ExtraComponent` (`src/rietx/schemas/instrument.py:1670`),
the union behind `Instrument.extra_components`, with its six-clause member
contract in the comment above it. It has two members today, a hump and a
sharp peak (WP-1103). This would be the **third**, and root CLAUDE.md's rule
applies: a third member audits every reader of the list before an evaluator
is written (`n_extra_components`, the CIF description, a reopened result,
an analytic branch's declared reach, the absorption statistics, both tick
builders, and `multi.py`'s own copy).

**The lock is already expressible.** `Refinement.tie(path, source, *,
scale, offset)` is affine (`src/rietx/refine.py:1858`), so the member's
amplitude tied to `phases.0.scale` with `scale=c*` is the whole constraint.
The outer loop's fixed point should then come out of one fit.

**Design questions.**

- **Aggregate membership** (contract clause 2). A diffuse term from the
  phase is not instrument background. Decide whether it joins
  `y_background`, a new aggregate, or the phase's own share, and what the
  Le Bail/Pawley partition subtracts (clause 3).
- **Does the curve move with the zero shift?** A curve computed on the
  specimen's 2θ axis does, which puts an interpolation inside the traced
  residual. Check whether `xp` has an `interp` op (`_OP_NAMES`). If not, it
  is a new op on every backend (root CLAUDE.md, the hot-path rule).
- **σ.** A simulated curve has none. A tabulated measured reference does.
  One field, optional, like `fixed_sigma`.
- **Screening.** `background_absorption` anchors its targets at `phases.`
  (`_structural_targets`). Decide whether a tied amplitude is a target.

## Non-goals

- Computing any diffuse term (WP-1516 scopes it).
- The measured-blank background's semantics (WP-1309).

## Tasks

- [ ] Audit every reader of `extra_components` and list them here, before
      writing the member.
- [ ] Decide the four design questions above, in this file.
- [ ] The member: schema, `SCHEMA_VERSION` bump, evaluator in `xp` ops,
      refinable fields through the one registration helper, cross-backend
      `CONFIGS` row, manual equation with its `*Source:*` line, `help.py`.
- [ ] A test pinning the lock: a synthetic Bragg-plus-diffuse pattern where
      one fit with the tie reaches the outer loop's fixed point to 1e-6, and
      `instrument.background.*` does not reach the member.
- [ ] Skill: a reference row saying a simulated curve goes here, with the
      tie, and never in the background slot.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_cross_backend.py tests/test_extra_components*.py -n auto --dist loadgroup
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

The lock test above passes. `solution case 1`'s final joint fit, rebuilt
on the member, reaches its recorded fit quality in one call (ratio in the
handover).

## References

- Treacy, M. M. J., Newsam, J. M. & Deem, M. W. (1991). *Proc. R. Soc. Lond.
  A* 433, 499–520. The DIFFaX recursion whose output the run fed in.

## Handover log

- **2026-09-28** — created from the review of `solution case 1`, with
  WP-1510, 1511 and 1513 to 1517. Nothing started.
