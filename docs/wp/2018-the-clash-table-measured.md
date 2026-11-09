# WP-2018 — The clash table: actions that read or move the same parameter, measured both ways

Milestone: generality · Status: 🔄 2026-11-09 — 8 of the list re-derived (3 dissolved); none measured
Track: The audits
Depends on: —
Priority: P3 2026-10-20 — split from WP-2002 by the maintainer; 38 candidate pairs found and none measured, and one past clash (WP-1320) changed a design

## Goal

For each pair of automatic actions that read or move the same parameter in one fit, the
measured interaction: Rwp and the parameter's value with the actions in both orders, on a
dataset that exercises both. A pair that interacts is reported with what it changes and
what a caller sees; a pair that does not is recorded as measured and independent.

## Context

**Why a clash table.** The generality milestone's plan review asked each audit to keep one,
because heuristics interact (`docs/milestones/generality.md`, the plan review): WP-1320
chose the fraction profile's axis because the collapse rule fought it. WP-2002's readers
listed 38 candidate pairs, deduplicated in `docs/wp/2002-batch/clashes.md` with the
parameter, both actions at file and line, the dataset that exercises both and which reader
named it. Nothing there is measured. Line numbers are of 2026-10-19 and have moved.

**Two pairs to start with.** C1 is WP-1320's clash: `profile_fraction` pins one width per
branch and refits through `run_stage`, against the stage-start hold and the collapse
restore. WP-1320 measured it under the pre-WP-1523 significance test and never since. C3 is
the cell window, the hold and the reset-and-hold that replaced the clamp (2026-10-20).

**What changed since the list.** The B8 cell reset replaced the clamp; the position bounds
went; Le Bail and Pawley now refine the emission lines; the package's own trials inherit
`phase_support_sigma` and `correlation_guard`. Re-derive each pair's file:line before
measuring, and drop a pair one of these changes dissolved, saying why.

### Inherited

- **From WP-2002 (2026-10-21, 5th session, PR #1085).** The closing stage meets every per-stage action, measured by WP-2002's test lanes. `AIR_SCATTER_UNDECLARED` scores lower under it only because its fixture is drawn at the 2 % windows (redrawn at 1e-3, every claim holds). The stopped-early `BOUND_HIT` case and the interval's short-of-minimum case no longer occur, since the closing stage carries the fit to its minimum. `HOLD_BLOCKED_PLAN`, `STAGE_PATH_UNKNOWN` and `HIGH_CORRELATION` name the closing stage. A per-stage finding repeated on the same paths is now reported once, the latest (`refine._run_plan`). Under TRF the closing stage stops CPD brucite where one S_HKL esd collapses (t = -268), LM unaffected.
- **From WP-2002 (2026-10-21, PR #1085).** C20 measured: the Suortti roughness seed, 0.3 against 0, leaves Biso, the scale and b within 2.7e-3 of an esd on five lab patterns from three laboratories (`tests/test_seed_invariance.py`), but Pitschke's c under the same literal is not invariant (zincite lands in the turned-over regime from 0). C18 measured in part: the absent-phase hold flips between `intermediate_ftol` 1e-6 and 1e-9 on cpd-1a with zircon declared, under LM (`docs/wp/2002-batch/waiting.md` § B7). Polish both orderings to a fixed point from one common start: LaB6's polish fixed points are not unique.

## Non-goals

- Fixing a clash found here. A fix is the owning audit's, or a ruling for the maintainer.
- Pairs across fits in a series (WP-2003's).

## Tasks

- [ ] Re-derive the 38 pairs against the tree; drop or merge the dissolved ones with a line
      each.
- [ ] Per pair, the dataset that exercises both, chosen before running.
- [ ] Measure both orders (or with and without one action, where order is fixed by the
      code): Rwp, the shared parameter, and its esd. PNGs to `tests/output/`.
- [ ] The table in this file: pair, effect, size in esds, verdict (independent, ordered,
      or a clash). A clash goes to its owner WP's `### Inherited` or to the maintainer.

## The table

Rows are added as pairs are re-derived and measured. "Read" means the file:line was re-read
against `origin/main` at 4c55b9011 (2026-11-09); nothing below is measured yet.

### Re-derivation, the C3 family (2026-11-09, read only)

The post-solve clamp to ±15 % is gone. `refine.reset_cell_runaway` (refine.py:1805, called at
:5258 and :5502, read) now puts the **whole** free cell of a phase that left
`CELL_SAFETY_FRACTION` back at the stage's start values, and the caller holds it and solves once
more (WP-2002 B8, ruled 2026-10-19). Its docstring states it writes committed values only and
never a bound the solver sees.

| # | Status | Reason (file:line, read) |
|---|---|---|
| C3 | **live, to measure** | Still a triple, with the clamp replaced by the reset: the support window (`least_squares._freeze_cell_windows`, least_squares.py:2944, called :3196; `vector.cell_window`, vector.py:606, applied :4225), the absent-phase hold, and the reset (refine.py:1805). Dataset as listed: the 68-pattern in-situ series and #481's ramp |
| C3a | **live, unchanged** | The window still binds free entries only (vector.py:4218-4226 loops `self._free_idx`), so a held cell is never windowed; the tie case stays the only one where both act |
| C3b | **dissolved** | The clamp wrote the window edge and the collapse restore the stage start. The reset now writes the stage start too, and refine.py:5360-5365 makes the two holds disjoint (a path both reach is the collapse's), so both actions write one value and one record holds each path |
| C3c | **dissolved** | The clamp is gone. The reset acts after the solve on committed values and restores the cell the stage's own residual evaluated, whose volume is positive (refine.py:1821-1826), so the degenerate-cell guard, which acts during the solve, never sees a reset value |
| C3d | **dissolved** | The clamp moved θ after the solve, under a bound test reading the first solve. Now the reset's paths are held (`set_vary(reset_hold, False)`, refine.py:5406) before the second solve (:5469), whose outcome replaces the first (:5523), and `check_guards` (called :5563) takes `free = table.free_paths` (staged.py:2283) into `bound_findings` (:2355): a reset cell is no longer a free column when the bound test runs |

### Re-derivation, C1, C2 and C6 (2026-11-09, read only)

| # | Status | Reason (file:line, read) |
|---|---|---|
| C1 | **live, to measure** | `profile_fraction` still pins one width per branch (`trial.set_vary([axis], False)`, fraction_profile.py:216) and refits through `run_stage` (:224), so each refit meets the stage-start hold and the collapse restore (refine.py:5372-5399). The module's own account of the clash (fraction_profile.py:14-23) is still dated to the pre-WP-1523 test. Dataset: `tests/test_qpa_multimodal.py`'s two-basin fixture |
| C2 | **live, narrowed, to measure** | Since #1075 each probe starts from the fit's own free set (`fresh()`, parameter_interval.py:269-279: the pinned path and every path the fit held), so a probe can no longer free a cell the fit held. Its comment says a refit may still hold *more*, since a lower pinned scale can hide a phase the fit saw: that half of the pair is what to measure. Dataset: a weak phase in a weighed mixture, as listed |
| C6 | **designed apart, confirm by measuring** | `_significance_columns` (refine.py:2205-2218) still leaves out every column that moves only displacements, occupancies and other phases' scales, so the absent-phase test cannot read a scale-B ridge as absence. The docstring's 153.7σ against 0.02σ on the fluorite is why the exclusion exists, not a measurement of the pair; the WP-2002 reader asked for one. Dataset: `tests/test_scale_b_ridge.py`'s fluorite |

## Acceptance

```sh
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

Every pair in `2002-batch/clashes.md` has a measured row or a stated reason it was dropped.

## References

- WP-2002, `docs/wp/2002-batch/clashes.md`; WP-1320 (the fraction profile's clash);
  WP-1523 (the significance test).
- `docs/milestones/generality.md`, the plan review's clash-table requirement.

## Handover log

- **2026-11-09** — The clash table has begun: eight entries of the candidate list (four of its 38 numbered pairs and the four sub-pairs of C3) were checked against today's code, and three of them no longer exist, because the cell reset that replaced the old ±15 % clamp writes the same value as the collapse restore and acts outside the solve. Four remain real and unmeasured, among them the two the WP names first (C1 and C3), and one (C6) was designed apart but never measured. No fit was run, so nothing here says whether any pair actually changes an answer; that is still the WP's whole point. *Done* (PR #1512, docs only): § The table holds C1, C2, C3, C3a, C3b, C3c, C3d and C6 re-derived at 4c55b9011 by reading, each with file:line. Live: C1, C2 (narrowed by #1075), C3, C3a. Dissolved: C3b, C3c, C3d. C6 designed apart, measurement still owed. No clash found, so nothing went to an owner WP, the maintainer or an issue. `### Inherited` kept: both entries still describe the tree as far as read. *Gotchas*: the session was a ghostshift runner cut to about 30 minutes by a hard stop, so no dataset was chosen and nothing was measured; the line numbers above are 4c55b9011's. On this Mac a pytest run with `-n` is refused unless it goes through `testslot.sh`. *Tests* (macOS arm64, `.venv` `[dev]`): `tests/test_docs_consistency.py` 25 passed; `python -m tests.reader_output` exit 0, unchanged. Next: (1) re-derive C4, C5 and C7-C38 the same way, since a dissolved pair saves a measurement; (2) choose the dataset per live pair before running; (3) measure C1 and C3 first, both orders or with and without the action, Rwp, the shared parameter and its esd, PNGs to `tests/output/`.
- **2026-10-20** — Filed by WP-2002's session at the maintainer's request ("split"): the clash table moves here so that 2002 closes on its owed tests and B14's lifts. Nothing measured yet.

