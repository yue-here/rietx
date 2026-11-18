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

## Findings (2026-11-18, on `439032dde`)

**The audit (task 1).** Paths under `src/rietx/`. The class behind most hazards is one: **several
readers use the aggregate as a proxy for the shape**, testing `COMPONENT_AGGREGATE == "background"`
and then reading a hump's fields. That is WP-1103's lesson one axis over. A third member landing
in `"background"` breaks each of them, and one landing anywhere new passes the two `compile_model`
filters silently.

Break or mislead for a third member:

- `model/forward.py:4702-4706`: `component_paths` builds a `HUMP_FIELDS` triple for every
  background-aggregate member. `CompiledModel.background` (`:1061-1070`) feeds each triple to
  `hump_curve`, and `optimize/least_squares.py:2371` and `strategy/staged.py:1527-1543`
  (`check_hump_width`) unpack it.
- `model/forward.py:4052-4053` (`_compile_extra_peaks`): reads `eta`, `fwhm`, `center` of every
  ticks-aggregate member.
- `indexing/extinction.py:997-1010`: reads `.position` and `.fwhm` of every background-aggregate
  member.
- `refine.py:9715-9717`: `n_extra_components = len(component_paths) + len(peak_components)`,
  so a member in neither tuple is not counted. `n_background_components` is right only for a
  background-aggregate member that joins `component_paths`.
- `io/exporters.py:411-412`: every background-aggregate member is written to the CIF as an
  "explicit Gaussian background peak".
- `io/recipe.py:1653-1664`: names every member's field `background_peak_{i}_{field}`.
- If the curve reads the zero shift: `model/forward.py:2989-2996` withdraws polarisation and line
  weights from the analytic chain when `peak_components` is non-empty, and would need the same
  withdrawal for `instrument.zero_shift`, or that column comes back short (the WP-1070 failure).
  `refine.py:1615-1630` (`_peak_only_instrument_path`) inherits the same gap.

Correct only if the member's aggregate is `"background"` and its curve is inside
`CompiledModel.background()`: the Le Bail and Pawley nets (`model/forward.py:3314, 3473`) and
`solve/cost.py:333-345`, which subtract only `extra_peak_curve` explicitly; `evaluate`,
`evaluate_with_background`, `evaluate_parts` (`model/forward.py:2368, 2388, 2410`);
`optimize/statistics.py:773-776` (`background_absorption`) and `:1033-1036`
(`_roughness_nuisance`), which treat every non-peak component path as background;
`report/background.py:137`; `gui/background.py:120`, which reads `component_paths`.

Member-blind and correct: `params/vector.py:349, 2673, 5109` (through `COMPONENT_FIELDS`, which
raises `KeyError` on a missing row); `capabilities.py:462-476`; `model/forward.py:2975` (an amplitude
takes the whole-model FD column, correct and slow); `optimize/least_squares.py:196, 2153-2166`;
`refine.py:7420`; `io/recipe.py:1400, 1424, 1466`; `io/instrument_profile.py:152, 1236, 1865`;
`io/projects/topas_input.py:658` and `io/projects/fullprof.py:4059` (refuse any non-empty list);
`strategy/staged.py:299` (the `mccusker_structural` glob would free an untied amplitude);
`indexing/extinction.py:974-978`. `multi.py` keeps **no** second builder: it compiles each
histogram through `compile_model` and reads `model.background` (`multi.py:2498`),
`peak_component_prefixes` (`:2532, 2552`), `_tick_rows` (`:2635`) and `_extra_peak_diagnostics`
(`:2637`), and `params/multi.py:180` makes every `instrument.*` path per histogram. Outside
`src/`: `gui/src/lib/history.ts:381-386` needs a print-format row for any new field (the GUI
track's file, so owed rather than edited here).

**The lock works today, and so does the silent break's repair.** Probe
`~/.cache/ghostshift/rietx/wp-1512/probe/lock_today.py`: synthetic LaB6, Cu Kα1, 15-110° at
0.02°, Poisson noise, a five-Lorentzian diffuse shape on a 0.1° grid at 150 counts peak.
`ref.tie("instrument.background.scale", "phases.0.scale")` with the curve stored as c*·D holds
the amplitude to the phase scale in one fit. A preset-style `set_vary(["instrument.background.*"])`
then frees `c0`-`c3` and **not** the scale, whose row reads `tied: = 1·phases.0.scale`. So the
break the Priority line names is closed by one call with no new code.

**The acceptance's premise is wrong.** One fit with the tie does not reach the outer loop's fixed
point, and it should not. The loop holds the curve fixed while it refits S, so its fixed point
makes χ² stationary with respect to the Bragg term alone. The joint fit makes χ² stationary
with respect to S everywhere S appears, which is the least-squares answer. Measured: the loop
converged in 7 refits to S = 3.03735e-4 at Rwp 0.062786; the one tied fit landed 0.50 % lower, at
S = 3.02224e-4, with the lower Rwp 0.062781 (truth 3e-4, one noise draw). The lock test should pin
the joint minimum instead, and the loop's offset is a number to report, not a bar.

**What ignoring the zero shift costs.** Probe `zero_and_glob.py`: truth zero shift 0.05°, applied
to the Bragg peaks by the model and to the curve by hand. Fitted with the curve frozen at
compile against the curve shifted, zero shift free in both:

| diffuse feature width (HWHM) | ΔS/S, frozen vs following | GoF, following → frozen |
|---|---|---|
| 2.5° | −9.0e-5 | 1.020 → 1.020 |
| 0.5° | −8.9e-4 | 1.021 → 1.028 |
| 0.15° | −1.6e-3 | 1.021 → 1.044 |

A DIFFaX faulted-minus-ideal curve has features as narrow as the Bragg peaks it broadens, so the
last row is the realistic one. GSAS-II's fixed curve applies no shift because it is a measured
histogram that already carries the instrument's zero offset. A simulated curve does not.

**Practice** is in `docs/practice.md` § A curve computed by another program: GSAS-II and FullProf
add a file curve to the background with one multiplier; FullProf also refines a shift and a
stretch; TOPAS lets the user write the shift, the amplitude and where the curve lands.

## Non-goals

- Computing any diffuse term (WP-1516 scopes it).
- The measured-blank background's semantics (WP-1309).

## Tasks

- [x] Audit every reader of `extra_components` and list them here, before
      writing the member. (§ Findings, 2026-11-18.)
- [x] Decide the four design questions above, in this file. **Option A**, Yue's ruling of
      2026-11-18: no new component. The curve, stored as c*·D, goes in
      `BackgroundFixedPlusChebyshev`'s fixed curve, and
      `ref.tie("instrument.background.scale", "phases.0.scale")` holds its amplitude to the phase
      scale. Yue chose A "for now, as the easiest". What would flip it to C (the member, with the
      curve following the zero shift): a second case needing a blank and a simulated curve
      together, or a sharp curve on a pattern with a large zero shift. So the four questions
      close as follows. Aggregate: the background, since the curve is in the background slot.
      Zero shift: the curve does not follow it (0.16 % on S at 0.05° with 0.15°-wide features,
      § Findings), and the manual says so. σ: `fixed_sigma`, already there. Screening: no change
      (handover 2026-11-18, settled point 3).
- [x] ~~The member: schema, `SCHEMA_VERSION` bump, evaluator in `xp` ops,
      refinable fields through the one registration helper, cross-backend
      `CONFIGS` row, manual equation with its `*Source:*` line, `help.py`.~~
      **Declined** under option A: no member is built, so none of its rows is owed, and
      `gui/src/lib/history.ts` needs no new print format either.
- [x] A test pinning the lock, restated (handover 2026-11-18, settled point 1): a synthetic
      Bragg-plus-diffuse pattern where one fit with the tie reaches the **joint** least-squares
      minimum to 1e-6, and a preset glob over `instrument.background.*` leaves the tied scale
      alone. `tests/test_simulated_curve_tie.py`.
- [x] Skill: a reference row saying a simulated curve goes in the fixed slot, with the tie.
      Under option A the row points at the slot instead of away from it. Plus the
      `help.py` entry for `instrument.background.scale` and a section of the manual's blank
      guide.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_simulated_curve_tie.py tests/test_manual_api.py tests/test_help.py tests/test_skill.py -n auto --dist loadgroup
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

The lock test above passes. Restated under option A: the cross-backend and
extra-component rows the member would have needed are gone with the member, and
`solution case 1`'s rebuild on the member is replaced by the synthetic joint-minimum
test, since no member exists to rebuild it on.

## References

- Treacy, M. M. J., Newsam, J. M. & Deem, M. W. (1991). *Proc. R. Soc. Lond.
  A* 433, 499–520. The DIFFaX recursion whose output the run fed in.

## Handover log

- **2026-11-18** (ghostshift runner, draft PR #1678) — audit, practice survey and three probes
  landed; no code. **Stopped for a decision of Yue's** before writing the member.

  **The decision.** Whether WP-1512 builds a new component at all, or closes as documentation of
  a tie in the slot that exists today. Three triggers send it: the member would be a new
  top-level name beside `rx.HumpComponent` and `rx.PeakComponent`, where the field has no
  standard term (TOPAS `user_y`, GSAS-II "fixed background file", FullProf "background file");
  it is a stored-format change (a `SCHEMA_VERSION` bump, contract clause 5); and a measurement
  contradicts the WP's acceptance.

  **Why it matters.** The WP was filed because a run that put a simulated stacking-fault curve
  in the fixed-background slot needed an outer loop of refits to keep the curve's amplitude in
  step with the phase scale, and since 1.5.0 every preset frees that slot's scale silently. Both
  problems turn out to be solved today by one call,
  `ref.tie("instrument.background.scale", "phases.0.scale")`, with the curve stored as c*·D.
  What the slot cannot do is hold a measured blank and a simulated curve together, report the
  curve as anything but background, or move the curve with the zero shift. Importance:
  moderate. The one observed use is `solution case 1`.

  **Aim.** Correct numbers for a user who brings a curve from DIFFaX or a Debye sum, with the
  smallest surface that gives them.

  **Options.**
  - *A. Document the tie.* A skill row and a manual paragraph. Cost: an hour. Reversible. The
    curve stays frozen on the axis, so with a zero shift of 0.05° and curve features as narrow
    as 0.15° the phase scale reads 0.16 % low and GoF rises from 1.02 to 1.04 (measured,
    § Findings). The user can still shift the curve by hand before the fit.
  - *B. The member as filed, frozen at compile, landing in the background.* Cost: the member,
    fixes at the seven break sites in § Findings, tests, manual, help; about a day. Allows a
    blank and several curves at once and a correct CIF description. Same accuracy as A. Adds a
    name and a format bump.
  - *C. B, with the curve following the zero shift* (and, for full correctness, displacement and
    transparency). Cost: B plus an `interp` op on numpy, jax and torch with its conformance row,
    and the zero-shift withdrawal from the analytic chain. The only option that removes the
    measured bias. FullProf (a refinable shift b₄) and TOPAS (`fo_transform_X`) both offer it.
  - Dropped: a new aggregate beside `"background"` and `"ticks"`, since it touches about ten
    more readers and no program does it except TOPAS's free per-object flag.

  **Practice.** `docs/practice.md` § A curve computed by another program, read this session:
  GSAS-II 5.8.4 source, the FullProf manual, the TOPAS 5 Technical Reference. Settled practice
  is a file curve in the background with one multiplier. None ties the amplitude to a phase
  scale by default; TOPAS lets the user write it.

  **Recommendation.** A lean for A. The crux is whether B's name and format bump buy anything
  A lacks, and on accuracy they buy nothing: A and B both freeze the curve. So the real choice is
  A against C. C is the accurate option, but its bias measured at 0.16 % of the scale for the
  sharpest curve tried, and its cost is a new backend op for a use seen once. A second case
  that needs a blank and a simulated curve together, or a sharp curve on a pattern with a
  large zero shift, would flip it to C.

  **Settled here, for whichever option is chosen.** (1) The acceptance is restated: one tied
  fit must reach the joint least-squares minimum, not the outer loop's fixed point, which is a
  different point (0.50 % apart in S, the joint fit at the lower Rwp; § Findings). Grounds: the
  measurement and least-squares theory; the alternative is to keep the WP's bar, which a correct
  fit fails. (2) σ, if a member is built, is one optional field like `fixed_sigma`. Grounds: that
  precedent. (3) The absorption screen needs no change: a tied amplitude has no column of its
  own, its curve rides on `phases.0.scale`'s column, and an untied one lands in the background
  block (`optimize/statistics.py:773-776`). Grounds: the code read. (4) For B or C the aggregate
  is `"background"`. Grounds: GSAS-II and FullProf, and clause 3 then costs nothing; the
  alternative is TOPAS's per-object flag.

  **Owed outside this WP's files**, if B or C is chosen: `gui/src/lib/history.ts:381-386` needs a
  print-format row for the new field (the GUI track's file, not edited here).

  Next: on Yue's answer, tick task 2 with the chosen option, then the member (B or C) or the
  skill row and manual paragraph (A). Gates run: none, since nothing outside `docs/` changed.
- **2026-09-28** — created from the review of `solution case 1`, with
  WP-1510, 1511 and 1513 to 1517. Nothing started.
