# WP-2222 — The closing stage off by default

Milestone: unscheduled · Status: 🔄 2026-11-19 — claimed by @yue-here
Track: A long run is not one fit
Depends on: —
Priority: P1 2026-11-19 — paid by every user on every run: users complained about fit time, and the closing stage is 1.2-1.9× of it

## Goal

A plan runs no closing stage unless its caller asks for one.
`closing_window_tol` defaults to `None` on both plan mirrors. `1e-3`
(`CLOSING_WINDOW_TOL`) stays the documented opt-in for a final answer.

## Context

**The ruling, 2026-11-19.** Users complained about refinement speed. The
maintainer said that codes such as TOPAS are fast, with accuracy their users
consider very sufficient, and then: "turn off by default". This reverses
the default of WP-2002's eighth round (ruled 2026-10-21,
`2002-batch/rulings.md` § Eighth round), which kept the closing stage on at
1e-3 with `closing_window_tol=None` as the speed switch.

**What the closing stage is.** After a plan's declared stages, `run_stages()`
appends one more stage. It frees every glob the plan freed, recompiles at
the answer with peak windows that drop 0.1 % of each peak's area instead of
the declared stages' 2 % (`forward.WINDOW_AREA_TOL`), and solves again.
TOPAS drops about the same 2 % as the declared stages (`docs/practice.md`).

**Measured 2026-11-19** (macOS arm64, `[dev]`, compiled tier on, telemetry
off, three interleaved rounds; `examples/bench_refinement.py`'s case
builders). Wall clock as ranges; "moves" is the largest shift from the
closing answer, plain esd, non-background rows.

| Case | 1.9.0 | no closing | closing 5e-3 | closing 2e-2 | closing 1e-3 (1.10-1.12 default) |
|---|---|---|---|---|---|
| 11-BM NAC | 0.34-0.40 s | 0.43 s, moves 0.16 | 0.51-0.54 s, 0.06 | 0.48-0.50 s, 0.16 | 0.53-0.56 s |
| cpd-1a | 0.99-1.05 s | 0.97-0.98 s, 0.92 | 1.34-1.35 s, 0.34 | 1.08 s, 0.91 | 1.64-1.68 s |
| cpd-2 | 2.21-2.22 s | 2.08-2.11 s, 1.99 | 3.04-3.11 s, 0.14 | 2.87-3.01 s, 2.17 | 3.53-3.55 s |
| trigger (simulated) | 1.75-1.76 s | 1.76-1.77 s, 1.24 | 2.41-2.44 s, 0.21 | 2.03-2.13 s, 1.23 | 3.28-3.38 s |

Three readings. The closing stage adds 7-23 evaluations to fits of 46-270,
but each costs up to ~19× a declared stage's, so it is 43-48 % of stage
time on the lab cases. With it off, today's code runs at 1.9.0's speed (NAC
~0.07 s slower). A closing stage at TOPAS's 2 % gives the same Rwp as none on
cpd-1a and trigger: its effect is the tighter tail, never the recompile.

**Paths that keep their own setting.** `strategy.magnetic._close` sets
`closing_window_tol=CLOSING_WINDOW_TOL` itself (magnetic.py, the winner's
close), so the magnetic solve is unchanged. Magnetic-path decisions are
Mike's (since 2026-11-04). A saved project stores its selected plan whole
(`ProjectDocument.plan`, `model_dump_json`), so a project that saved a plan
under 1.10-1.12 keeps `closing_window_tol: 0.001` until its user changes
it. A project with no saved plan follows the new default.

**Three cases that keep the closing stage, ruled by Yue 2026-11-19.**
Seven tests stayed red under the new default because the default changed what
they measure. Yue took all three of the session's leans ("Yes, finish it
here"):

1. *A Pawley series that carries intensities forward runs the closing
   stage.* With 2 % windows each pattern misassigns a little intensity and
   the next pattern starts from it. On the four-pattern chain Rwp read
   0.0339, 0.0345, 0.0347, 0.0372 carried, 0.0339-0.0345 re-seeded, and
   about 0.034 throughout with the closing stage: the WP-1459 (#440) drift
   back. `SequentialRefinement.fit` sets `CLOSING_WINDOW_TOL` on a plan whose
   value is `None` when `mode="pawley"` and `carry_hkl_intensities` is on;
   `carry_hkl_intensities=False` is the way out. A single Pawley fit has
   nothing to compound and stays off. Le Bail carries the same way and was
   not measured.
2. *`lab_calibrate` runs the closing stage, and the `branch` and `path`
   guides ask for it.* At the default the calibrate guide's sample size and
   strain land 2.9 and 2.4 esd from the simulated truth; with the closing
   stage in the calibration alone, 1.3 and 0.8 esd; in the sample fit too,
   0.3 and 0.4 esd. Every later fit holds the calibration fixed. The two guides teach comparisons of one objective,
   which the declared windows blur (Rwp 0.1031 against 0.0988 where the
   page shows one 0.0947; a 0.02 esd direction gap against 0.005).
3. *The GUI preview keeps 1e-3 windows and the shift is accepted.* A preview
   starting from a default fit moves the curve by up to 0.13 % of the
   strongest peak (26 counts on 20 310, the fluorapatite example) and the
   preview's Rwp in the third digit. Retuning the preview for 2 % windows is
   a follow-up WP.

**Tier.** No new rule. A default moves from one named value to another,
both already audited (`_audit.py`, the `CLOSING_WINDOW_TOL` rows). Ground:
the maintainer's ruling, and TOPAS's 2 % cut as named practice.

## Non-goals

- Windows that follow the parameters (WP-2047, WP-2051, filed for later).
- The magnetic close, which keeps its explicit 1e-3.
- Migrating a saved project's stored `0.001`.

## Tasks

- [x] Flip the default on `PlanSpec` and `RefinementPlan`; the help text, docstrings and field descriptions say what the default is and what 1e-3 buys. `Refinement.run_stage`'s `window_area_tol=None` and a FitReport action applied in the GUI follow, to the declared stages' 2 %; `compile_model`, `predict` and the FitReport misfit keep evaluating at 1e-3
- [x] Tests: those that assumed a closing stage by default declare it, or assert the new default
- [x] The three rulings of § Context: a carried Pawley series runs the closing stage (`SequentialRefinement.fit`); `lab_calibrate` declares it and the `calibrate`, `branch` and `path` guides ask for it; the GUI preview's shift accepted in its tests, WP-2225 filed to retune it
- [x] Audit rows, manual (`reference/refinement.md` speed section), skill rows (`batch-operating.md` 9c.34), staged release notes
- [x] Skill: the opt-in row for a final answer: 9c.34 rewritten as the opt-in, and `series.md`'s runaway row says only an opted-in plan has a closing stage

## Acceptance

```sh
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m pytest -n auto --dist loadgroup tests/test_closing_stage.py tests/test_window_domain.py tests/test_staged_start_invariance.py
.venv/bin/python -m ruff check src tests examples
```

## Handover log

- **2026-11-19** — created. No open WP owns the default: WP-2017 measures
  tier-3 thresholds, WP-2047/2051 are closed, and WP-2002 is closed.
