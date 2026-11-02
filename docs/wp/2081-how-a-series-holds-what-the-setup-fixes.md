# WP-2081 — How a series holds what the setup fixes (a design discussion)

Milestone: unscheduled · Status: ⬜
Track: A long run is not one fit
Depends on: 2003 soft (PR #1310 reshapes the ladder this discusses)
Priority: P2 2026-11-02 — a scoping WP whose decision sets the series surface; a held setup value lost on the cold rung carries to every later pattern (measured), and the workaround takes three hooks

## Goal

A series surface whose behaviour a scientist can predict for parameters that the
experimental setup fixes between frames. A zero shift, a wavelength or a resolution
function either stays at the value the scientist meant on every frame, or the series
says plainly where it did not. The first task is a discussion between Yue and Claude
that decides how.

## Context

**How it arose.** Ruling WP-2080 (2026-11-02) needed to know whether its trigger sends
extra frames to the cold rung. Reading `sequential.py` for that answer showed that the
cold rung forgets a held setup value. This WP is the design question that reading left
open. It decides nothing yet.

**The surface as it stands** (origin/main `efb5f2f80`, `src/rietx/sequential.py`):

- `SequentialRefinement(structure, instrument, *, backend, solver, carry=("*",),
  carry_hkl_intensities=True, history=False)`. `refine_sequential(patterns, structure,
  instrument, ...)` is the one-call wrapper over it.
- `fit(patterns, *, x, x_label, labels, mode, plan, refit, two_theta_limits, direction,
  reseed, reseed_factor, first_rung_factor, verify_steps, prepare, constrain, on_result,
  on_error, events, cancel, progress, telemetry, label)`. PR #1310 (WP-2003) removes the
  default Rwp fence and the first-rung budget, so `reseed_factor` and
  `first_rung_factor` are about to change.
- The ladder, `RUNGS = ("warm", "warm_staged", "cold")` (WP-1051). `warm` is the plan
  collapsed into one stage from the neighbour's answer. `warm_staged` is the full staged
  plan from the same start. `cold` is the full plan from the initial models, and it is
  also what the first pattern runs.
- `SeriesResult`: one `SeriesEntry` per pattern (its rung, rungs tried and raised, the
  pattern it was seeded from), the trajectories, `steps`, failures and diagnostics.
- The joint fit (`multi.py`, `MultiHistogramRefinement`) is a different object. It stacks the
  patterns into one residual, and `SharingMap` decides which paths are one number for
  every pattern. `instrument.*` and `.scale` are per pattern by default, and a `shared=`
  glob overrides that. WP-1325 builds a parameter as a declared function of each
  pattern's coordinate on top of it.

**What the code does, verified against the tree.** The lead session's reading, point by
point, with two corrections.

1. Every rung and every `verify_steps` refit goes through `_fit_one`. That builds a new
   `Refinement` and runs `prepare` and then `constrain` on it. So a hold or a tie
   declared in `constrain` applies on every rung (WP-1441). Confirmed. `prepare` also
   runs on every rung. One addition: `on_result` runs on the reported chain only. The
   backward verification pass of `direction="both"` passes `None`.
2. `vary=False` on the models does not keep a parameter fixed. A plan replaces the vary
   flags (WP-1208), and `_collapse` frees the union of the plan's `turn_on` globs. Only
   `ref.hold(...)` protects a parameter (WP-1435), and a blocked glob raises
   `HOLD_BLOCKED_PLAN`. Confirmed, with a correction to the example: the stage that frees
   `instrument.zero_shift` is `zero` in `mccusker_default` and `zero_disp` in
   `lab_bragg_brentano` (with `sample_displacement`). One addition:
   `load_instrument_profile` returns its "frozen" instrument as `vary=False` only, so a
   plan that frees those paths refines them.
3. The cold rung restarts from the initial models: `previous=None`, so no carried values,
   no carried variables (`previous_vars={}`) and no carried hkl intensities. Confirmed.
   The `verify_steps` refits are cold in the same way (`_verify_steps` passes `None`).
4. "Refine once, then freeze" has no declaration. A hold fixes whatever value reaches the
   rung. `carry` passes a value forward, and the plan refines it again unless it is
   held. The cold rung uses the initial value. Corrected in two places by the measurement
   below. A spelling does exist: three hooks together hold pattern 0's value on every
   rung. And the damage is wider than one frame. The pattern after a cold frame warm-starts
   from the cold frame's answer, so the initial value carries on down the chain.
5. Today's workaround is to calibrate separately (`lab_calibrate`, then
   `save_instrument_profile`), pass the calibrated instrument in and hold the setup
   parameters in `constrain`. A hold of a value the caller passed in survives the cold
   rung, because the initial model already holds it. For one refined number across
   frames the joint fit is the tool. Confirmed.

**The measurement** (`2081-batch/measure_cold_rung.py`, output `cold_rung.json`; macOS
arm64, worktree venv `[dev]`, Python 3.12.10, rietx 1.11.0.dev0, compiled tier on; 1.7 s
for all four arms). The first four patterns of `tests/test_sequential.py`'s thermal LaB6
ramp, true zero shift 0.008°, start model 0.0, plan `mccusker_default`. Frame 2's warm
rungs are made to raise, as issue #224's runaway neighbour made them raise, so the ladder
keeps its cold rung.

| arm | frame 0 | frame 1 | frame 2 (cold) | frame 3 |
|---|---|---|---|---|
| zero shift free, nothing forced | 0.00797 | 0.00799 | 0.00801 (warm) | 0.00802 |
| zero shift free, frame 2 cold | 0.00797 | 0.00799 | 0.00801 | 0.00802 |
| held from frame 1 in `constrain`, frame 2 cold | 0.00797 | 0.00797 | **0.00000** | **0.00000** |
| three hooks, frame 2 cold | 0.00797 | 0.00797 | 0.00797 | 0.00797 |

Each free value has an esd of 1.6e-5°. The consequences, from the same runs:

- A free setup parameter is safe on this fixture. The cold frame refines it from 0.0 to
  0.00801°, inside one esd of its neighbours.
- A held one is not. On the cold frame the hold fixes the initial 0.0. The cell edge
  absorbs the missing zero shift and lands 546 ppm short, and GoF rises from 1.04 to
  9.73. Frame 3 warm-starts from frame 2's answer, so it carries 0.0 too: −547 ppm, GoF
  9.76, after climbing all three rungs.
- It is not silent here, because the error is gross. `SEQUENTIAL_RESEED` says frame 2
  was refitted from the initial model, and `SEQUENTIAL_RWP_OUTLIER` fires on frames 2 and
  3 at 7.3× the Rwp fence. Neither names the held parameter or its value. The outlier
  warning rests on the Rwp fence, which PR #1310 removes by default; whether it survives
  that PR is not checked. A setup error a tenth this size would move the cell by about
  55 ppm and could pass both (not measured).
- The three-hook workaround holds 0.00797° on every frame, cold rung included, and the
  cell stays within 2 ppm of the truth. `on_result` keeps pattern 0's value, `prepare`
  writes it into each later pattern's instrument, and `constrain` holds it.

**Practice** (`docs/practice.md` § Sequential refinement, "Parameters the setup fixes",
surveyed this session). GSAS-II, FullProf, TOPAS and EasyDiffraction keep the fixed flag
on the parameter, and their series honour it on every pattern (GSAS-II read in source;
FullProf and TOPAS from their manuals; EasyDiffraction from the earlier survey). None of
them has a plan that frees a parameter the user fixed. None restarts a pattern from the
initial models, so a held value on a cold restart is a question only rietx has. GSAS-II
spreads flags across histograms with "Copy flags" and applies only wildcard-histogram
constraints in a sequential run. One refined number across patterns is a joint fit
everywhere: TOPAS's top-level parameters across `xdd`s, FullProf's multi-pattern PCR,
GSAS-II's plain multi-histogram refinement (recall). "Refine on the first pattern, then
freeze" is a manual step in every program surveyed (inferred).

**Related WPs.** WP-1441 (ties and variables reach every pattern through `constrain`);
WP-1435 (the hold, and why `vary=False` is not one); WP-1208 (a plan replaces the vary
flags); WP-1051 (the ladder and the quarantine); WP-2003 (the chain actions and their
tiers, PR #1310); WP-2080 (a warm fit in a wrong basin; its ruled trigger escalates to
`warm_staged` only, so it sends no frame to the cold rung); WP-1325 (the parametric joint
fit); WP-2028 (the joint fit's screens).

**Tier.** Nothing here adds a rule yet. Any default the discussion chooses for the cold
rung is new judgement (tier 3, generality § The rule), because no program surveyed has
a cold rung.

### Inherited

## Open questions for the discussion

1. Should setup-fixed parameters be declarable on the series itself, rather than in a
   hook?
2. Should a cold rung inherit them? If so, which value: the caller's, the first
   pattern's, or the last accepted pattern's?
3. Should "refine on the first pattern, then freeze" have a spelling of its own?
4. Should the chain and the joint fit share a surface, given that one refined number
   across frames is a joint-fit question?
5. Should `vary=False` mean "fixed" anywhere, for example on a series' models or on a
   loaded instrument profile?
6. When a frame is fitted with a setup value different from its neighbours', what
   should the series record or say?
7. How should GUI and agent users meet this: a control, a field on the result, a skill
   row, a manual page?

## Non-goals

- WP-2080's trigger and its factor.
- The ladder's other rules (WP-2003).
- The joint fit's guards (WP-2028) and the parametric joint fit (WP-1325), except where
  question 4 asks whether the two surfaces meet.

## Tasks

- [ ] The discussion with Yue on the open questions. Record each ruling in this file
      with its grounds, and mark any call settled by Claude as such.
- [ ] Turn the rulings into work: fold each into this WP's tasks or the owning WP, or
      file a new WP, each with its practice row and the measurement it rests on.
- [ ] Skill: decided with the rulings. Until then none, because the surface it would
      describe is open.

## Acceptance

The rulings are in this file and the follow-up work is filed.

```sh
.venv/bin/python -m pytest tests/test_docs_consistency.py -q
.venv/bin/python docs/wp/2081-batch/measure_cold_rung.py
```

## References

- `src/rietx/sequential.py` (`_fit_one`, `_chain`, `_ladder`, `_collapse`,
  `_verify_steps`), `src/rietx/refine.py` (`Refinement.hold`), `src/rietx/multi.py`,
  `src/rietx/params/multi.py` (`SharingMap`), `src/rietx/io/instrument_profile.py`.
- `docs/practice.md` § Sequential refinement.
- Stinton, G. W. & Evans, J. S. O. (2007). Parametric Rietveld refinement. *J. Appl.
  Cryst.* 40, 87-95.
- Issue #224 (a warm rung that raises and a cold rung that does not).

## Handover log

- **2026-11-02** — created (a ghostshift runner, one session). A series in rietx can
  lose a setup value the scientist held. When a frame falls to the cold rung, the hold
  fixes the initial model's value. The frames after it carry that value on. On a LaB6
  ramp this put the cell 546 ppm off, and two warnings fired without naming the cause.
  Other programs keep the fixed flag on the parameter and never restart a frame cold, so
  they do not meet this. How rietx should is a design decision, and this WP holds the
  discussion.

  *Done.* Filed: no open WP owns how a series declares setup-fixed parameters. WP-2003
  tiers the ladder, WP-1325 and WP-2028 own the joint fit, WP-1317 the series viewer.
  The lead session's five-point reading verified against `efb5f2f80`, two points
  corrected (Context). Measured as in Context; script and JSON in `2081-batch/`.
  Practice survey saved to `docs/practice.md`. Filed in PR #1333, with WP-2080's
  ruling.

  *Gotchas.* The measurement forces the cold rung by patching
  `SequentialRefinement._fit_one` on main's positional signature; a change to that
  signature breaks the script.

  *Next:* the discussion with Yue (task 1).
