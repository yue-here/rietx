# WP-2224 — A re-fit of a converged model runs one stage

Milestone: unscheduled · Status: 🔄 2026-11-19 — implemented, PR #1711 in review; four questions wait on Yue (handover log)
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
- **A model swap that adds a block (task 3, 2026-11-19).** `2224-batch/swap.py`, tree at
  00dae473c, no closing stage, machine under load (seconds not quotable). Each case fitted the
  standard without the block, added the block at its no-effect value with `edit`, and fitted
  from there once as one stage and once staged.

  | Case | Rwp one stage / staged | Largest gap, one stage from staged | Evaluations |
  |---|---|---|---|
  | brucite + March-Dollase (001) at r = 1 | 0.18476 / 0.18462 | 2.25 esd, profile W (gauss strain 1.51, gauss size 1.44) | 46 / 68 |
  | brucite + spherical harmonics, order 4, at zero | 0.19696 / 0.19695 | 1.01 esd, Lorentzian strain | 60 / 92 |
  | NAC fitted alone, then CaF₂ added at scale 1e-7 | 0.09317 / 0.09317 | 0.00 esd | 19 / 40 |

  All three reach under § Measured's 3 % Rwp rule. Brucite's untextured first fit sits at Rwp
  0.469, so the block moves the model far, and the one stage stops 2.25 esd from the staged
  answer in the Gaussian width trio that `FLAT_DIRECTION` already flags as one direction.
  Design 2 is not loosened: an `edit` still runs the plan. The result goes to Yue.
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
   converged fit of its pattern is a re-fit too. With `history=False` the fact is held on the
   `Refinement`. Superseded in part 2026-11-19: the GUI's Refine passes `refit="stages"`
   until Yue rules on how the stage ladder shows one stage (handover log).

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

- [x] `refit=` on `Refinement.fit` and `refine`, `_collapse` moved to where both the series and
      the single fit import it, the re-fit test of design 2, the fallback of design 3. A plan
      with `turn_off` runs staged.
- [x] The record of design 4, and the `_audit` row for the new default action with its tier
      and families (the eight standards above).
- [x] Measure a re-fit after a model swap that adds a block at its identity value (a
      preferred-orientation block on brucite, a second phase on NAC), one stage against staged.
      Loosen design 2 only if all reach; bring the result to Yue either way.
      Measured 2026-11-19 (§ Measured): all reach by Rwp, brucite + March-Dollase 2.25 esd
      off; design 2 kept strict; with Yue.
- [x] Tests: a first fit is staged; a re-fit is one stage and lands within 0.5 esd of the
      answer the model stood at on three families (never of a staged re-fit, which moves
      zincite 2 esd: § Measured); a written value, another pattern, another mode and a
      non-converged fit each run staged; a rejected one-stage fit falls back; `refit="stages"`
      is today's fit, bit for bit. Tests that pin a number through a second `fit` declare
      `refit="stages"`. Obs/calc/diff PNGs to `tests/output/`.
- [x] Manual: `concepts/plans.md` § Why a fit runs in stages says what staging is for (the
      basin, and the windows) and when a fit takes one stage; `reference/refinement.md` gets the
      keyword. The page's first sentence, "Most of what goes wrong in a refinement is a
      correlation", describes the mechanism and not the purpose.
- [x] `docs/practice.md`: the stopping rules and TOPAS's per-iteration limits from § Practice,
      and rietx's row in § Staging and what a stage holds.
- [x] Skill: the body's fit section says a second `fit` on a converged model runs one stage and
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

- **2026-11-19 (implementation)** — A second `fit` on a model that its last fit of the same
  pattern left converged now runs one stage, `warm_refit`, freeing at once everything the plan
  frees. On the eight comparison standards it lands within 0.21 esd of the first fit's answer
  and costs 0.32-0.50 of a staged re-fit's evaluations (0.15-0.27 once the closing stage is off).
  None of the eight fell back. A first fit, any written value, another pattern, mode or channel
  set, and a plan that fixes a parameter all still run the plan. Four things wait on Yue: the
  text a display prints for a re-fit and for a fallback, keeping a model swap on the staged
  plan, and whether the GUI's second Refine should re-fit (it stays staged until then). A
  fourth came from the review: a plan that frees a block the first fit held still re-fits in
  one stage, and on brucite that lands 2.25 esd off the staged answer.

  *Done.* `refit="single" | "stages"` on `Refinement.fit` and `refine`. The re-fit test is a
  digest of the pattern arrays, fitted mask, mode and the models' values with `vary` and
  `stderr` stripped (`refine._refit_key`), held on the `Refinement` and as the `refit_key` note
  on the answer's node, so a checkout or a reopened tree counts. A rejected one-stage fit
  (`schemas.sequential._rejected`) is discarded: its nodes are noted `refit_discarded`, the
  state and head go back, the plan runs, and the result carries `WARM_REFIT_REJECTED` (info).
  One run directory per job, as the Le Bail alternation does it; the recorder ignores a
  `fit_end` stamped `refit`. `_collapse` moved to `strategy/refit.py`. The GUI passes
  `refit="stages"`. Manual (`concepts/plans.md`, `reference/refinement.md`), practice survey,
  skill body line and diagnostics row, audit rows (code tier 3, the two defaults tier 2).

  *Review* (`/code-review high --fix`, 5 findings). Fixed: `_collapse` dropped the last stage's
  `ftol`, `restraint_weight_scale` and `window_slack_deg`, so a plan ending at c_w = 0.1 would
  re-fit at 1.0 (the closing stage already copies all three, and the series' warm refit shares
  the fix); an empty plan on a re-fit start ran a no-op stage instead of its refusal; a long
  docstring line. Two tests added. Skipped: `_fit_refit` repeats the alternation's
  recorder plumbing (a shared helper would edit the alternation, outside this WP); the GUI history
  has no chip for `refit_discarded` nodes (a visual question, and the GUI runs staged).

  *Measured* (`2224-batch/accept.py`, `swap.py`; `[dev]`, macOS arm64; evaluations do not
  depend on load). Acceptance as § Measured and the docstring quote. Model swap, closing stage
  off, one stage against staged: brucite + March-Dollase at r = 1, Rwp 0.18476 / 0.18462,
  largest gap 2.25 esd (profile W), 46 / 68 evaluations; brucite + spherical harmonics order 4,
  0.19696 / 0.19695, 1.01 esd, 60 / 92; NAC + CaF₂ at scale 1e-7, 0.09317 both, 0.00 esd,
  19 / 40. Design 2 kept strict. The generality review then asked for the route the default
  does take (`held_block.py`): the same March-Dollase block present from the start, held at
  r = 1 by the first fit (Rwp 0.46947), then freed by the plan plus a `po` stage. The default
  ran one stage and landed on the `edit` route's numbers exactly: Rwp 0.18476 against staged
  0.18462, profile W 2.25 esd off (Gaussian strain 1.51, size 1.44), 46 / 68 evaluations. So a
  plan or `set_vary` that frees what the converged fit held is a re-fit under design 2 and is
  not safe; this went to Yue with a recommendation to run such a fit staged. Suites, on the tree with `main` merged
  (6bcd9a161), `[dev]`, macOS arm64, no other suite running (sampled each minute). Fast:
  14 925 passed, 434 skipped, 32 xfailed, about 10 min. Before review the branch's fast run had
  14 922 passed, 1 failed (the stale GUI help-key fixture, since regenerated) and 434 skipped,
  so passed+skipped moved by exactly the two tests the review added. Full: 15 882 passed, 445
  skipped, 50 xfailed, 1 failed, about 37 min. The failure is
  `test_pair_diagnostic_class.py::test_the_two_site_winner_finds_each_site_its_own_moment`
  (moment 0.6995 against 3.5). It fails the same way on a snapshot of `origin/main`, with
  this WP's default switched to `"stages"`, and on main's Linux nightly of 2026-11-18;
  WP-1418's log has it. The 13 added tests (19 cases) cost 40.4 s of worker time locally
  (largest: the one-stage re-fit on three families, 11.1 s). They stay in the fast tier because they are
  the default's acceptance, split over three per-family xdist groups.

  *Gotchas.* Folded from WP-2225's note (this file's former `### Inherited`): the staged
  re-fit's 2.05 esd on zincite V and 0.83 on fluorite V is the width twin hold re-solving U, X
  and Y, and the first fit's answer does not stop short; quote it as such. The GUI's
  `test_running_the_same_plan_twice_shows_the_second_run` is what a one-stage GUI re-fit breaks:
  the stage ladder finds no run matching the plan on screen and its Rwp column goes blank.
  `import rietx.refine as m` gives the function; use `importlib.import_module`.

  *Generality* (the author's answers first, one line each; the judge's report follows them,
  unedited):
  `WARM_REFIT_REJECTED` weak on families: the row now names its injected case.
  `Refinement.fit:refit` contested for a newly freed block: measured (`held_block.py`, above),
  2.25 esd, sent to Yue with a recommendation to run such a fit staged. The row now names its
  dissent and gives the families as seven materials from four instruments.
  `turn_off` refusal: kept. Collapsing such a plan through `closing_stage`'s `fixed_at_end` is
  plausible and unmeasured, so it is a follow-up, not this branch.
  GUI hold: design 5 and `concepts/plans.md` now say it is temporary.
  Skill row weak on its cause clause: retagged `(Hypothesis: …)`, and `help.py` no longer
  calls it the usual cause.
  A `tie` that moves a value ends a re-fit: the docstring and manual now say so.

  **WARM_REFIT_REJECTED**

  **holds.** The case for acting is stronger. The fallback reuses the series' rejection test, which the maintainer has already ruled on, and the code reports a second fit the package ran on its own. The one gap: no real fit has ever triggered it.

  | Question | Author's answer (where) | What I found | Verdict |
  |---|---|---|---|
  | 1. What it decides | "nothing: the result is the staged plan's answer, and the message names why the one-stage re-fit was discarded" (`_audit.py` row, `responds`) | The code decides nothing itself. It reports two acts the caller did not ask for. The one-stage attempt (`warm_refit`, the single stage the plan is collapsed into) is discarded. Then the full plan runs from the restored start (`refine.py` `_fit_refit`). | clear |
  | 2. Kind | `ambiguity=1` | The trigger is `_rejected` (the series' test: the fit diverged, or it carries an error-level diagnostic). Throwing away a diverged fit is one of Rule 1's protections of work already done. Kind 1 agrees. | agrees |
  | 3. Case against acting | none given | Nothing substantive found. One small point: if the staged plan is also rejected, its result is returned rather than the better of the two attempts. The series' ladder keeps the best attempt. Nothing is lost, because the discarded nodes stay in the history tree with the note `refit_discarded`. When the code fires, it costs one extra one-stage fit. | none found |
  | 4. Case for acting | "Says out loud that the package ran a second fit, as SEQUENTIAL_RESEED does for the series' ladder" (`grounds`) | Every refiner would discard a diverged fit. Without the code, a result would list the full plan's stages and give no reason. Measured cost of staying silent: none given, since the code never fired on real data. | strong |
  | 5. Tier | 3, "the trigger is the series' own _rejected (ruled by the maintainer 2026-11-03)", `approved="2026-11-19"` | Tier 3 is right: the trigger is rietx's own test. One of the codes it reads, `MODEL_FAR_FROM_DATA`, is itself a rietx threshold and is tiered in its own row. `approved` gives the date of Yue's ruling on the design (WP § Context). The maintainer has not yet approved this row. | holds |
  | 6. Families | "On the eight comparison standards it fires on none from a converged start (WP-2224 § Measured)" (`evidence`) | No firing on the eight standards. They cover four laboratory/instrument groups, and all eight are development data. The only firing is injected: `tests/test_refit_single.py::test_a_rejected_one_stage_fit_falls_back_to_the_plan` patches `_rejected` so that it rejects every `warm_refit`. That test checks the plumbing: the state is restored, the answer equals the staged one bit for bit, and the job leaves one run directory. It does not test the trigger. The rule asks a row whose guard no ordinary fit reaches to name its injected case, and this row names none. | weak on this point |
  | 7. What records it | the code (`evidence`) | The code is `info`. Its message names the error codes and the rejected attempt's Rwp. The discarded nodes carry `refit_discarded`. | holds |

  What would change the verdict: a real one-stage re-fit that `_rejected` rejects, named in the row, would remove the only gap. A case where the staged fallback lands worse than the discarded attempt would weaken the row.

  **rietx.refine.Refinement.fit:refit**

  **holds.** The case for acting is stronger when the re-fit has the same free set: on 8 of 8 standards the one stage keeps the answer to within 0.41 esd, at about 0.4× the time. The row names no dissenter. It also leaves out the one measured case where one stage lands 2.25 esd away from the staged answer.

  | Question | Author's answer (where) | What I found | Verdict |
  |---|---|---|---|
  | 1. What it decides | "Under `"single"` (the default) a re-fit runs the plan collapsed into one stage, `warm_refit`" (`Refinement.fit` docstring) | The caller passes plan X. When the start is an accepted fit's answer, the package runs X collapsed into one stage instead of X. Under `refit="stages"` the caller decides. | clear |
  | 2. Kind | `ambiguity=1` | The kind-1 claim is that every competent refiner re-fits a converged model with everything free at once. That holds when the free set is unchanged. It is contestable when a changed plan frees a group the converged fit held (row 3). | agrees, with one exception |
  | 3. Case against acting | No dissenter named. The rule asks the author to name one or say none exists. | (a) McCusker et al. 1999, which the skill §2 and the WP cite, frees groups cumulatively, each converged before the next. `docs/practice.md` § Staging says GSAS-II and FullProf users "stage a first approach by hand". The re-fit test treats a changed plan as still a re-fit (WP design 2), so such a user's situation reaches the one stage. WP § Measured task 3: brucite with a March-Dollase (001) block at r = 1 ended 2.25 esd from the staged answer on profile W (Rwp 0.18476 against 0.18462). That run went through `edit`, which the default sends staged. A structure that already carried the block at r = 1, held, followed by a plan with an added `po` stage, has the same digest and takes the one-stage path. That route is not tested. The gap lies in the Gaussian width trio that `FLAT_DIRECTION` (the code for a combination the data barely determine) already flags. (b) Against (a): the "edit" start was measured. The model was converged under each plan minus its last stage, then fitted with the full plan. Result: 8 of 8 within 0.00 esd max (`2224-batch/summary.txt`, "start edit"). (c) BGMN and MAUD stage by default (practice.md), and RIETAN-FP does under `NAUTO = 2`, though practice.md does not say whether that is its default. practice.md does not say what any of the three does on a second run from converged values. Not checked. | contested only for a plan change that frees a far-off block |
  | 4. Case for acting | "8 of 8 reach the staged answer, within 0.41 esd, at 0.35-0.50 of its time; from a cold start one stage reaches 20 of 48, which is why a first fit stays staged" (`evidence`) | `summary.txt` "start warm, single": 8/8, time 0.39× (0.34-0.50), evaluations 0.25×, largest gap 0.41 esd, cell gap at most 10.8 ppm. The saving is time, not calls or numbers. On these standards a staged re-fit takes 0.22-0.67 s and one stage 0.08-0.27 s; with the closing stage on (the shipped default before WP-2222), 0.37-1.21 s. No large model was measured. The Priority line says users complained about fit time. A staged re-fit moves zincite's profile V by 1.97 esd. WP-2225 traces that to the held instrument width, so it argues neither way. The docstring and `concepts/plans.md` quote "within 0.21 esd" and "0.32-0.50 of the staged re-fit's evaluations (0.15-0.27 with no closing stage)". Those numbers come from `accept.py`, and its printout is not in the WP or in `2224-batch/` at this tree. | strong for an unchanged free set |
  | 5. Tier | 2: "TOPAS, GSAS-II and FullProf run one solve of whatever is free … (docs/practice.md § Staging)" | practice.md lists FullProf, GSAS-II, TOPAS and EasyDiffraction as staging nothing. The row leaves out EasyDiffraction, which supports it. Those practice.md rows carry no checked/recalled mark, and I did not check the programs. Dissenters keep the value at tier 2. But the default switches on an action, and the rule says a dissent counts at the action's judgement ground. The row carries no `grounds` or `approved`. Its judgement answer is "Ruled by the maintainer 2026-11-19, 'Yes, by default'", which WP § Context records. The precedent it leans on, `SequentialRefinement.fit:refit`, is still on `UNAUDITED_BASELINE`. | tier 2 fits the value; the action's ground rests on the ruling alone |
  | 6. Families | "the eight comparison standards (…; six families)" (`evidence`) | By laboratory and instrument I count four groups. NIST's diffractometer (SRM 660c). The CPD round-robin Philips instrument (corundum, zincite, fluorite, brucite; `tests/data/README.md`: "same instrument/conditions"). GSAS-II LabData (fluorapatite). APS 11-BM (NAC, SRM 660a). That is seven materials. "Six" is not broken down. The reference is rietx's own staged answer, which verifies and validates nothing. Distance from SRM 660c's certified cell or SRM 676a's c/a: none given. All eight are development data, and the row does not say so. The test asserting under 0.5 esd uses zincite, fluorite and corundum, all from one instrument. | ≥3 either way; reference and data status missing |
  | 7. What records it | "its one stage is named `warm_refit`" (WP design 4) | `result.stages` holds one stage named `warm_refit`, and history nodes carry the same name. `summary()`'s protocol line reads the private `Refinement._refit_plan`. No result field records which plan the caller passed. | thin but present |

  What would change the verdict: run the brucite case through the default path (block present and held, plan extended), or free the atoms on a converged profile-only fit. Landing within 0.5 esd of staged makes the row unqualified. Landing over 2 esd in a direction `FLAT_DIRECTION` does not flag makes it weak.

  **rietx.refine.refine:refit**

  **holds.** As for `Refinement.fit:refit`, the case for acting is stronger, and on `refine`'s default path the default never acts.

  | Question | Author's answer (where) | What I found | Verdict |
  |---|---|---|---|
  | 1. What it decides | "acts only when `history` is a tree whose head is an accepted fit of `data` at exactly these models' values" (`refine` docstring) | It acts only when `history` is a `RefinementTree` object whose head carries the `refit_key` note. `history=False` (the default) and a path never act (`Refinement.__init__`'s `isinstance` test). | clear |
  | 2. Kind | `ambiguity=1` | As for `Refinement.fit:refit`. | agrees |
  | 3. Case against acting | none given | As for `Refinement.fit:refit`. It is reached only when a caller hands in a live tree. | contested only for a far-off newly freed block |
  | 4. Case for acting | as in `Refinement.fit:refit` (identical `evidence`) | Same measurement. No test drives `refine` itself through a re-fit. | strong |
  | 5. Tier | 2 | As for `Refinement.fit:refit`. | as there |
  | 6. Families | as in `Refinement.fit:refit` | As there. | as there |
  | 7. What records it | — | The `warm_refit` stage name. | thin but present |

  What would change the verdict: the same evidence as for `Refinement.fit:refit`.

  **The re-fit test (`refine.py` `_refit_key`)**

  **holds.** The case for acting is stronger. The test compares a digest of the state, and its strict side fails toward the old staged behaviour.

  | Question | Author's answer (where) | What I found | Verdict |
  |---|---|---|---|
  | 1. What it decides | "Digesting the state, rather than tracking which verbs ran, makes 'no value written since' an observation" (`_refit_key` docstring) | It decides whether a fit is a re-fit. The digest covers the pattern arrays and σ, the fitted mask (`project.fitted_mask`, which includes the 2θ limits), the mode, the models with `vary` and `stderr` stripped, and the named variables. It leaves out the plan, holds, ties, backend and solver. | clear |
  | 2. Kind | none given (no row) | Hash equality is arithmetic, so kind 1. What goes into the hash is a rietx design choice. | kind 1 |
  | 3. Case against acting | none given | Being strict costs one staged fit after any write, including one that moves nothing material, such as a bound or a label. That costs time and moves no answer. `tie` writes the implied value into the models (`tie` docstring), so a tie that changes a value ends the re-fit. The manual's "Changing what is free with … `tie` … keeps it a re-fit" holds only where the implied value equals the stored one. The plan is left out of the key: see the `Refinement.fit:refit` section, row 3. | none found against the test itself |
  | 4. Case for acting | "The strict side is the safe side: the staged plan reached 46 of 48 cold starts" (WP design 2) | Cold, one stage reached 20 of 48. Brucite + March-Dollase through `edit` ended 2.25 esd off. Both support sending any value change staged. | strong |
  | 5. Tier | none (the table cannot see it) | Tier 1 for the equality. Tests: `test_a_written_value_runs_the_plan`, `test_another_pattern_channels_or_mode_runs_the_plan` (pattern, limits, mode), `test_a_fit_that_did_not_converge_leaves_no_refit`, `test_a_free_set_change_keeps_it_a_refit`, `test_a_reopened_tree_at_a_converged_answer_is_a_refit` (all in `tests/test_refit_single.py`). | holds |
  | 6. Families | n/a: no threshold | — | n/a |
  | 7. What records it | node note `refit_key` (`REFIT_KEY_NOTE`) | The note on the answer's node. The decision shows as the `warm_refit` stage name. | holds |

  What would change the verdict: a state the digest calls a re-fit in which a value outside the hashed models moved.

  **A plan with `Stage.turn_off` always runs staged**

  **holds.** It takes the old path and moves no answer. The reason given is weaker than stated, so the case for collapsing such plans too has more behind it than the code admits.

  | Question | Author's answer (where) | What I found | Verdict |
  |---|---|---|---|
  | 1. What it decides | "one stage frees then fixes, and cannot replay a fix a later stage undid (WP-2208), so such a plan runs staged" (`Refinement.fit` comment) | `refit="single"` is ignored for any plan that fixes parameters part way. Nothing tells the caller. | clear |
  | 2. Kind | none given | Kind 1 in effect: it is the pre-WP behaviour. | n/a |
  | 3. Case against acting (forcing stages) | none given | `RefinementPlan.closing_stage` already builds one stage for a plan that fixes. It frees every glob, then fixes the end state through `fixed_at_end(self.stages, paths)` (`strategy/staged.py:444-466`). So the obstacle named in the comment is already solved in the same module. Cost: a re-fit of such a plan pays the full staged time. Magnetic plans build their stages with `turn_off` (`strategy/magnetic.py:2328`), so magnetic re-fits never get the speed-up. Not measured. | moderate |
  | 4. Case for acting | the same comment | Staged is the bit-for-bit old fit, so it moves no number. | holds |
  | 5. Tier | none | Test: `test_a_plan_that_fixes_runs_staged`. | holds |
  | 6. Families | n/a | — | n/a |
  | 7. What records it | none given | None. The result lists the plan's stages and gives no note that `refit` was declined. | none |

  What would change the verdict: a re-fit of a `turn_off` plan collapsed through `closing_stage`'s `fixed_at_end` that keeps the answer. That would make the refusal unnecessary.

  **`_collapse` keeps the last stage's ftol, restraint weight and window slack**

  **holds.** The case for acting is stronger. The answer converged under the last stage's objective, and the closing stage keeps the same three settings.

  | Question | Author's answer (where) | What I found | Verdict |
  |---|---|---|---|
  | 1. What it decides | "the objective and windows the plan's answer converged under are its last stage's, which the closing stage copies for the same reason" (`strategy/refit.py` comment) | It decides the one stage's `ftol`, `restraint_weight_scale` and `window_slack_deg`. Before this change the one stage solved at the defaults, for example a restraint weight of 1.0. | clear |
  | 2. Kind | none given | Kind 1: a re-fit re-solves the objective the answer converged under. | kind 1 |
  | 3. Case against acting | none given | None found against the choice. Side effect: `_collapse` is shared with the series, so a series' warm patterns change too wherever a user's plan sets these on its last stage. No preset sets them. A grep finds only `closing_stage`, `refit.py` and `magnetic.py:1393`'s `ftol=last.ftol`, so series run on presets are unchanged. No series test or measurement is given, and the WP's non-goals say the series' `refit=` is unchanged. "As `closing_stage` does" holds for these three settings only: `closing_stage` takes the last stage's `max_iter` and Le Bail settings, while `_collapse` takes the plan's maximum. | none found |
  | 4. Case for acting | the same comment | With a scheduled restraint weight, the old one stage minimised a different S = S_y + c_w·S_G than the one the answer converged under. | strong |
  | 5. Tier | none | Test: `test_the_one_stage_keeps_the_last_stages_objective_and_windows`. It checks the built stage and runs no fit. | holds |
  | 6. Families | n/a | — | n/a |
  | 7. What records it | none given | `StageResult.ftol` records the ftol a stage ran at (project CLAUDE.md). I did not check whether c_w and slack are recorded. | partial |

  What would change the verdict: a series run on a user plan with a scheduled restraint weight whose answers moved away from the staged ones.

  **The GUI's Refine passes `refit="stages"` (`gui/session.py`)**

  **holds** as a temporary hold. The case for holding is stronger, because the alternative is a display change waiting on Yue. Two costs are not recorded.

  | Question | Author's answer (where) | What I found | Verdict |
  |---|---|---|---|
  | 1. What it decides | "staged until the stage ladder has a view of a one-stage re-fit" (code comment) | The GUI's Refine never takes the one-stage path, and the GUI user cannot choose it. | clear |
  | 2. Kind | none given | Not a question the data could settle. It is a display question, held for the maintainer. | n/a |
  | 3. Case against acting (forcing stages) | none given | GUI users pay the staged time: 0.22-0.67 s against 0.08-0.27 s on the standards, and 0.37-1.21 s with the closing stage on. The same `.rex` project now gives two answers depending on where it is re-fitted. On zincite a staged re-fit moves profile V by 1.97 esd and a one-stage re-fit does not (WP § Measured, explained by WP-2225). WP design 5 still says "the GUI's second Refine inherits it", so the WP file was not updated. | moderate |
  | 4. Case for acting | "after one, no run on record matches the plan on screen and the Rwp column goes blank (WP-2224, with Yue)" (comment) | Visual design questions go to Yue. `"stages"` is the old fit bit for bit (`test_refit_stages_is_the_fit_without_a_refit_bit_for_bit`). | strong |
  | 5. Tier | none | The value is a literal inside `gui/`, which `NOT_WALKED` declares out, so the table cannot see it. | n/a |
  | 6. Families | n/a | — | n/a |
  | 7. What records it | `concepts/plans.md`: "The GUI's Refine always runs the plan in stages" | No field records it. The manual states it as permanent. | thin |

  What would change the verdict: Yue's ruling on how the stage ladder shows a one-stage re-fit.

  **Skill: the §2 body line and the `WARM_REFIT_REJECTED` row in `references/diagnostics.md`**

  **weak** for one clause of the diagnostics row; the body line holds. The case for both entries is stronger. The row's stated cause has no run behind it and carries no Hypothesis tag.

  | Question | Author's answer (where) | What I found | Verdict |
  |---|---|---|---|
  | 1. What it decides | Body: "A second `fit` of a converged model runs one stage (`refit="stages"` walks it)". Row: "the likely cause is a plan or free set that frees what the converged fit held: pass `refit="stages"` for such a change" | The body line tells an agent what the default does and how to opt out. The row advises a next call. | clear |
  | 2. Kind | n/a | Rule 4's skill test: the body line names a keyword and the row names a code. Both pass. | passes |
  | 3. Case against | none given | The row's tag "(Measured: no firing on the eight `rietx compare` standards from a converged start, WP-2224)" covers how often the code fires. The cause it names has never been observed, since the code never fired, so it needs "(Hypothesis: …)". `help.py`'s entry says the same thing as "the usual cause", a claim of frequency with zero firings behind it. The body line does not mention the one measured trap: a newly freed block far from its starting value (brucite + March-Dollase, 2.25 esd). The package's own output could carry that (WP-1338's cheapest place). The line was paid for by cuts elsewhere in the body ("A failure raises." among them), which I did not judge. | weak on the cause clause |
  | 4. Case for | WP task: "a reference row for the fallback's diagnostic code" | A code needs its row, and the default changes what a second `fit` does. An agent needs that line before it calls `fit` a second time. | strong |
  | 5. Tier | n/a | — | n/a |
  | 6. Families | n/a | — | n/a |
  | 7. What records it | n/a | — | n/a |

  What would change the verdict: a real firing whose cause was a newly freed group would let the cause clause keep "Measured". Otherwise retagging it "(Hypothesis: …)" fixes the row.

  Next: Yue's four answers, in this order. Whether a fit that frees what the converged fit held
  runs staged decides one more clause in `_refit_key`'s caller (the free set at the last fit's
  end against the plan's globs) and a test. The GUI one decides whether `gui/session.py` drops
  `refit="stages"` and the ladder gains a one-stage view (a GUI WP). The model-swap one keeps
  or loosens design 2. The display text one may reword `_warm_refit_rejected` and
  `_protocol_lines`. When WP-2222 merges, merge `main` and
  re-run `accept.py`, then drop the "closing stage" bracket from the quoted numbers in
  `fit`'s docstring and `concepts/plans.md`.

- **2026-11-19** — created, from Yue's question on whether staging still earns its cost and
  the measurement it led to. A model that has already converged can be re-fitted in one stage
  for the same answer at about 0.4× the time, and Yue ruled that this is the default. No open WP
  owns it: WP-2222 turns the closing stage off and touches no stage count; WP-2080 is the
  series' wrong-basin case and its `refit=` is unchanged here; WP-1109 and WP-2045 are closed.
  The probe and its table are in `2224-batch/`. Next: task 1, after WP-2222 merges or with its
  default declared in the tests.
