# WP-2224 — A re-fit of a converged model runs one stage

Milestone: unscheduled · Status: ⬜
Track: A long run is not one fit
Depends on: 2222 soft (the closing stage off by default; the numbers here are against that default)
Priority: P2 2026-11-19 — users complained about fit time, and every fit after the first on a model re-walks the whole plan at about 2.5× the cost of one stage; `run_stage` with a hand-written free list is the workaround

## Goal

`Refinement.fit` on a model that its last fit of the same pattern converged runs one stage that
frees everything the plan frees, by default. The first fit of a model stays staged. The caller
can ask for the staged plan, and a one-stage fit the package rejects is run again staged.

## Context

**Ruled by Yue, 2026-11-19.** Asked "Should a re-fit of an already converged model run as one
stage by default?", with opt-in as the alternative, Yue answered "Yes, by default". The brief
put the option as: the first fit staged, a re-fit one stage, spelled with the series' own
keyword (`refit="single"`, `refit="stages"` to opt out), and a rejected one-stage fit falling
back to the staged plan as a series does. Yue's question that started it: staging costs time
close to convergence, other programs refine whatever is free, and TOPAS-level accuracy is
enough (memory `topas-accuracy-is-sufficient`, same day).

**What staging is for.** A staged plan gets a cold model into the right basin. While peaks are
misplaced or the scale is wrong, the width and intensity columns point at the wrong repair, and
parameters freed together walk into a false minimum. Once the model is in the basin the last
stage frees everything, so the correlations at the answer are the same whatever the path. A
converged model is already in the basin, and re-walking the stages buys nothing there.

**rietx's second reason.** Peak windows are frozen through a solve (frozen-per-stage
discreteness), and each stage recompiles them. One stage from a rough start ends on stale
windows: on SRM 660c a background term sat 7.5 esd off until a second solve recompiled. A warm
start compiles its windows at the converged values, so it needs no second solve (below:
`single` and `single+2pc` agree to 0.02 esd from a converged model).

### Measured

Eight comparison standards (`viz.compare.STANDARDS`: SRM 660c, corundum, zincite, fluorite,
brucite, fluorapatite, 11-BM NAC, 11-BM LaB6), macOS arm64, `[dev]`, telemetry off, tree at
936d17315, one fit at a time. Scripts and the full table: [2224-batch](2224-batch/README.md).
Baseline: the staged plan with no closing stage. "Reached" is Rwp within 3 % of the baseline's.
Times are medians over the standards that reached, as a fraction of the staged fit from the
same start, with the range. The first pass ran on a loaded machine (the batch README says which
rows), so re-measure before quoting one row.

| Start | One stage (`single`) | Positions, then everything, then a re-solve (`two+2pc`) | Staged |
|---|---|---|---|
| converged by the shipped plan (`warm`) | 8 of 8, 0.40× (0.35-0.50) | 8 of 8, 0.71× | 8 of 8 |
| converged without the last stage, which the fit then frees (`edit`) | 8 of 8, 0.42× (0.30-0.69) | not run | 8 of 8 |
| the standard's own start | 4 of 8 | 8 of 8, 0.75× (0.54-1.04) | 8 of 8 |
| cell +0.1 %, −0.1 % | 3 and 4 of 8 | 8 and 8 of 8, 0.77× | 8 and 8 of 8 |
| cell +0.3 % | 3 of 8 | 7 of 8 | 8 of 8 |
| profile W and X ×4 | 4 of 8 | 6 of 8 | 7 of 8 |
| profile W and X ÷4 | 2 of 8 | 7 of 8 | 7 of 8 |

- **Cold, one stage reaches 20 of 48 and the staged plan 46 of 48.** The two staged misses are
  fluorapatite from W and X ×4 and ÷4, where every plan ends near Rwp 0.169 against 0.0925 with
  `FLOOR_HIT` as its only warning. Not investigated.
- **Warm seconds.** Shipped default (closing stage on) 0.37-1.21 s; staged, no closing stage
  0.22-0.67 s; one stage 0.08-0.27 s.
- **One stage keeps a converged answer, and a staged re-fit can move it.** The reference is the
  baseline, and the `warm` model was converged by the shipped plan, closing stage on. One
  stage ends within 0.41 esd of the baseline on every parameter (SRM 660c's U) and within
  0.08 esd on the other seven standards. The staged re-fit moves
  zincite's profile V 1.97 esd and its axial term 1.17 esd, to a lower Rwp (0.11017 to
  0.10943), and fluorite's V 0.78 esd (0.18169 to 0.18139). Zincite's cell moves 20 ppm, which
  is 0.23 esd. On the other six the staged re-fit stays within 0.62 esd. Brucite's c moves 253 ppm
  under the staged re-fit at 0.00 esd, so that length is not measured by the fit. The
  closing-stage session repeated this on WP-2222's branch, where a first fit has no closing
  stage: one stage within 0.02 esd of the first answer on 8 of 8, the staged re-fit 2.05 esd
  on zincite and 0.83 on fluorite. So the staged first fit stops short of the plan's best
  point on two of eight standards, in instrument profile terms, and a one-stage re-fit does
  not find the rest. Cause not investigated. `refit="stages"` reaches it.
- **A failed one-stage fit reports `status="converged"`.** Most carried `MODEL_FAR_FROM_DATA`
  (error level) and `STAGE_WINDOWS_STALE`; NAC ended `max_iter`.
- **The `edit` start is a plan extension only.** The model was converged under the plan minus
  its last stage, and the timed fit ran the whole plan. A model swap that adds a block (a
  preferred-orientation block, a phase) was not measured.
- **Other levers, for scale.** Closing stage off: 1.40× median (1.23-2.35), WP-2222. Two cold
  stages in place of the plan: 1.3×, with 2 more misses in 48 and a size width up to 8.75 esd
  from the staged answer at Rwp equal to the fourth digit. Stopping at `ftol` 1e-4 on every
  stage in place of 1e-6 and 1e-9: 1.15× at 0.06 esd; at 1e-3 brucite stops short. None of the
  three is this WP's.

### Practice

- TOPAS, GSAS-II and FullProf do not stage. A run solves whatever is free from the current
  values, and the user stages a first approach by hand (`docs/practice.md` § Staging and what a
  stage holds). A re-fit in one stage is what their users do.
- A rietx series already does this: the first pattern runs the plan, later ones the plan
  collapsed into one stage (`refit="single"`, the default), with a ladder that runs the staged
  plan when the collapsed fit is rejected (`sequential.py`).
- TOPAS's reach from a far start rests partly on limits on how far a parameter may move in one
  iteration, by type: a cell length 0.995·Val − 0.05 to 1.005·Val + 0.05, a Beq Val ± 10
  (Technical Reference v9 § 2.18 and Table 2-1, "stabilize refinement"; read 2026-11-19).
- Stopping rules: GSAS-II 5.8.4 `min dM/M` 0.001 and `max cyc` 3 (`GSASIIobj.py:20`); FullProf
  stops when shifts are under `Eps` × esd, "a reasonable value is Eps=0.2 or lower" (manual,
  `LINE 9: NCY, Eps`); TOPAS when the change in S is under `chi2_convergence_criteria` for
  three cycles (§ 20.12; default not found in the text).

Add the last two bullets to `docs/practice.md` (task 6).

### Where the code is

- `Refinement.fit`, `src/rietx/refine.py`. It resets the free set and runs a whole plan from the
  working state.
- `sequential._collapse(plan)`: one stage, `warm_refit`, freeing every glob the plan frees. It
  carries no `seed` (a seed lifts a converged value off its floor) and keeps `strain_seed`. It
  is never used for a plan that fixes (`Stage.turn_off`, WP-2208): the series refits such a plan
  stage by stage, and so does this.
- `sequential.REFIT_MODES`, the `("single", "stages")` vocabulary.
- `schemas.sequential._rejected(fit)`: diverged, or an error-level diagnostic. The series'
  ladder climbs on it.

### Design, settled by Claude under the ruling and the series convention

Each is the implementer's to revisit with a measurement, and a reversal goes to Yue.

1. **Spelling.** `fit(..., refit="single" | "stages")`, default `"single"`, the series' keyword
   and values (DESIGN Rule 5: rietx convention first). `"stages"` runs the plan as today.
2. **When a fit is a re-fit.** All of: the working state is where a `fit` of this pattern left
   it (same parsed-array fingerprint, same `mode`, same fitted channels); that fit's `status`
   was `converged` and it was not `_rejected`; and no value has been written since
   (`set_values`, `edit`, a checkout to another node). `set_vary`, `hold`, `tie` and a changed
   plan keep it a re-fit. Anything else runs the staged plan. The strict side is the safe side:
   the staged plan reached 46 of 48 cold starts. Loosening it for a model swap that adds a block at
   its identity value needs the measurement § Measured lacks.
3. **Fallback.** One rung: a one-stage fit that is `_rejected` is discarded, the models go back
   to where the fit started, and the staged plan runs from there. The test is the series' own
   (`_rejected`, ruled 2026-11-03), and this WP adds no fence beside it: Yue's rulings on
   WP-2080 and WP-2003 leave a tuned fence over a fit metric to the caller. One error-level
   code it reads, `MODEL_FAR_FROM_DATA`, is itself an Rwp threshold.
4. **The record.** The result says what ran: its one stage is named `warm_refit`, and a
   fallback leaves a diagnostic. What a display prints for it is a reader-output change and goes
   to Yue before merge.
5. **A project.** The history head is the working state, so a reopened `.rex` whose head is a
   converged fit of its pattern is a re-fit too, and the GUI's second Refine inherits it. With
   `history=False` the fact is held on the `Refinement`.

### Inherited

- **From WP-2225 (2026-11-19).** The staged re-fit's movement on zincite and fluorite in this
  WP's probe is the width twin hold, and under-convergence plays no part. The plan holds U, X
  and Y at the instrument-only stage's values while their specimen twins sit on their floor, and
  a staged re-fit re-solves them in that stage. A one-stage re-fit applies the hold again, so
  under this WP's default a second `fit` stops showing the effect, and the first fit's answer is
  unchanged. Tolerances, windows and seeds were each ruled out by one change
  (`docs/wp/2225-batch/`). Read this before quoting "the first fit stops short" as a reason for
  or against the one-stage default.

## Non-goals

- One stage from a cold start, and shorter cold presets. Measured: 20 of 48, and 1.3× for two
  more misses.
- TOPAS-style per-iteration move limits, and windows that follow the parameters inside a solve
  (WP-2047 and WP-2051 measured the second and deferred it).
- The stopping tolerance.
- The joint fit (`multi.py`) and the series, whose `refit=` is unchanged.
- Whether staging is more forgiving for an agent. Untested with real agents; an agent's first
  fit from a database CIF is a cold start and stays staged under this WP.

## Tasks

- [ ] `refit=` on `Refinement.fit` and `refine`, `_collapse` moved to where both the series and
      the single fit import it, the re-fit test of design 2, the fallback of design 3. A plan
      with `turn_off` runs staged.
- [ ] The record of design 4, and the `_audit` row for the new default action with its tier
      and families (the eight standards above).
- [ ] Measure a re-fit after a model swap that adds a block at its identity value (a
      preferred-orientation block on brucite, a second phase on NAC), one stage against staged.
      Loosen design 2 only if all reach; bring the result to Yue either way.
- [ ] Tests: a first fit is staged; a re-fit is one stage and lands within 0.5 esd of the
      answer the model stood at on three families (never of a staged re-fit, which moves
      zincite 2 esd: § Measured); a written value, another pattern, another mode and a
      non-converged fit each run staged; a rejected one-stage fit falls back; `refit="stages"`
      is today's fit, bit for bit. Tests that pin a number through a second `fit` declare
      `refit="stages"`. Obs/calc/diff PNGs to `tests/output/`.
- [ ] Manual: `concepts/plans.md` § Why a fit runs in stages says what staging is for (the
      basin, and the windows) and when a fit takes one stage; `reference/refinement.md` gets the
      keyword. The page's first sentence, "Most of what goes wrong in a refinement is a
      correlation", describes the mechanism and not the purpose.
- [ ] `docs/practice.md`: the stopping rules and TOPAS's per-iteration limits from § Practice,
      and rietx's row in § Staging and what a stage holds.
- [ ] Skill: the body's fit section says a second `fit` on a converged model runs one stage and
      how to ask for the plan; a reference row for the fallback's diagnostic code. Paid for by a
      cut while the body is over its budget.

## Acceptance

On the eight standards, a second `fit` with the same plan runs one stage, ends within 0.5 esd
of the first fit's answer on every parameter, and takes under 0.6× the staged re-fit's
evaluations.
`refit="stages"` reproduces today's fit bit for bit.

```sh
.venv/bin/python -m pytest tests/test_refit_single.py tests/test_sequential.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- McCusker, Von Dreele, Cox, Louër & Scardi (1999), *J. Appl. Cryst.* **32**, 36: the staged
  order and the last joint stage.
- TOPAS Technical Reference v9, https://topas-academic.com/Technical_Reference.pdf, § 2.18,
  § 5.16, § 20.12.
- GSAS-II 5.8.4, `GSASIIobj.py:20`, `GSASIImath.py:164-432` (`HessianLSQ`).
- FullProf manual, the `NCY, Eps` line.
- WP-0505 and WP-1127 (the series' collapsed re-fit and its ladder), WP-2080 (a warm fit from a
  neighbour pattern in a wrong basin), WP-2222 (the closing stage off).

## Handover log

- **2026-11-19** — created, from Yue's question on whether staging still earns its cost and
  the measurement it led to. A model that has already converged can be re-fitted in one stage
  for the same answer at about 0.4× the time, and Yue ruled that this is the default. No open WP
  owns it: WP-2222 turns the closing stage off and touches no stage count; WP-2080 is the
  series' wrong-basin case and its `refit=` is unchanged here; WP-1109 and WP-2045 are closed.
  The probe and its table are in `2224-batch/`. Next: task 1, after WP-2222 merges or with its
  default declared in the tests.
