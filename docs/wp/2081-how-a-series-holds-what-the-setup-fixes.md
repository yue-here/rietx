# WP-2081 — How a series holds what the setup fixes (a design discussion)

Milestone: unscheduled · Status: ⬜
Track: A long run is not one fit
Depends on: 2003 soft (PR #1310 reshapes the ladder this discusses)
Priority: P2 2026-11-04 — a scoping WP whose decision sets what a series frees after its first frame; Yue's account (2026-11-03) shows the default refits the instrument on every frame where an expert fixes it, and a held setup value lost on the cold rung carries to every later pattern (measured); no move

## Goal

A series a scientist can predict, and can drive the way an expert drives one. A zero
shift, a wavelength or a resolution function either stays at the value the scientist
meant on every frame, or the series says plainly where it did not. Stages that run over
the whole series, as an expert's do, have a spelling. The first task is a discussion
between Yue and Claude that decides how. Yue's caveat below governs it: the expert's method shows
what a series must be able to do, and it need not be what rietx or an agent does by
default.

## Context

### How a human expert runs a series

Yue's account, given in chat on 2026-11-03 and recorded close to verbatim.

> The traditional sequential first gets a good fit on the instrument parameters that
> should stay constant or change predictably, then runs the series holding those fixed.
> A full refit is very unusual without a good reason. Instrument parameters might be
> refined, but as a fudge for sample-dependent parameters such as broadening in a
> specific phase. The usual situation is VT, in situ or operando on a single lab,
> synchrotron or neutron instrument.
>
> The usual shape of the human workflow:
>
> 1. Visually inspect the waterfall or heatmap for phase transitions and other non-linear
>    changes.
> 2. Try to get good fits on each phase present in the sequence when its signal is strong
>    (if possible), to nail down the profile and background.
> 3. Considerations: the background may evolve with environmental changes (temperature,
>    gases), so continuous background changes need refining, which is tricky because the
>    phase is also changing. Spectator phases can be excluded or modelled with Pawley.
>    Exclusion regions need checking across the series so peaks do not wander in or out,
>    so modelling can be preferable.
> 4. Once profile and background are well determined, do a cautious fit with most
>    parameters locked; depending on the system, maybe cell, scale and background are
>    released.
> 5. Gradually release more until the scientific question is resolved.
>
> **Caveat.** This is not necessarily the optimal method for agents and need not be
> followed. It indicates how a human expert might find how a structure changes with
> temperature, or the quantity of different phases as a battery charges.

**Terms used below.** A *frame* is one pattern of a series. A *plan* is rietx's staged
list of what to free, and each stage's `turn_on` globs name the parameters. A *warm start*
begins a frame from the neighbouring frame's answer. A *rung* is one attempt at a frame,
and the *ladder* runs up to three: `warm` (the plan collapsed into one stage, from the
neighbour), `warm_staged` (the whole plan, from the neighbour) and `cold` (the whole plan
from the models the caller passed in). A *hold* (`ref.hold`) fixes a parameter against
every plan. `carry` names which values pass from frame to frame. Three hooks run the
caller's code: `prepare` edits the models before a frame's fit, `constrain` declares holds
and ties on that frame's refinement, and `on_result` receives each finished frame.

### The crux: what a series does on the frames after the first

`refine_sequential` with its defaults, `plan="mccusker_default"` and `refit="single"`,
frees on every frame what the plan frees. That is the zero shift, U, V, W, X and Y and the
background, beside the scale and the cell. Yue's account says an expert does the reverse.

rietx already disagrees with itself here. `docs/skill/rietx/references/series.md`
(§ Microstrain evolves along a chain) says to hold the instrument profile after
calibrating it once and to let the per-phase widths refine, and its opening example passes
`plan="lab_sample_refine"`. The default does the opposite. So does the guide:
`examples/guides/series.py` runs `plan="mccusker_default"`, and the manual's
`guides/series.md` quotes it.

What each preset frees on a later frame, measured by `resolve_plan(name, "rietveld")`,
`_collapse` and a real `ParameterTable` for LaB6 (`2081-batch/measure_routes.py`, output
`routes.json`). A count of setup paths is for that instrument. Every preset below frees
the background. The two magnetic presets are left out.

| preset | setup paths, Bragg-Brentano | setup paths, capillary | sample paths |
|---|---|---|---|
| `mccusker_default` (the series default) | 6: zero, U, V, W, X, Y | the same 6 | scale, cell |
| `lab_bragg_brentano` | 9: those 6, displacement, Kα2 weight, axial S/L | 7: those 6, axial S/L | scale, cell |
| `lab_sample_refine` | 1: displacement | 0 | scale, cell, four width terms, Biso |
| `mccusker_structural` | 6 | 6 | those of `mccusker_default`, plus coordinates, Biso and whatever the model declares |
| `profile_only`, `pawley_default` | 6 | 6 | cell |
| `lab_calibrate` | 9 | 7 | scale, Biso |

No preset is named for synchrotron or capillary data (checked: nine presets in
`PLAN_PRESETS`, none so named or described). `lab_sample_refine` is the nearest. On a
capillary it frees no setup path, because displacement is locked there, but its name and
its `PLAN_INFO` title say lab. Its route gives the traditional run today: pass a calibrated
instrument in, and the plan frees none of its profile or zero terms on any rung, cold
included, so nothing needs holding. The route is measured below on a capillary ramp. It
also frees Biso and the four widths, and Yue's cautious step 4 releases fewer.
`resolve_plan` accepts it for Le Bail and Pawley (probed; a series in those modes was not
run).

**What the routes do on the ramp** (`routes.json`; macOS arm64, worktree venv `[dev]`,
Python 3.12.10, rietx 1.11.0.dev0, compiled tier on, 3-8 s for the script). Seven synthetic
LaB6 frames from `tests/test_sequential.py`, capillary, cell growing 0.05 % a step, true
zero shift 0.008°. The instrument is constant by construction, so this shows what each
route does. It cannot show which route is right on real data. The real ramp below does that.

| route | setup paths free per frame | rows refined per frame | cell error, mean (ppm) | cell error, sd over frames (ppm) | mean cell esd (ppm) | evaluations, frames only |
|---|---|---|---|---|---|---|
| default | 6 | 13 | −0.59 | 1.10 | 1.20 | 127 |
| fit frame 0 alone, pass its models in, then a custom plan of scale, background and cell | 0 | 7 | −1.83 | 0.43 | 0.47 | 60 |
| the same calibration, then `lab_sample_refine` | 0 | 13 | −1.82 | 0.43 | 0.40 | 79 |
| second pass over the cautious route, freeing Biso too | 0 | 9 | −1.82 | 0.43 | 0.40 | 43 |

"Rows" counts the cell's a, b and c as three. The calibration fit is extra: it is the
default arm's frame 0 again, 37 evaluations. Three readings:

- Fixing the setup shrinks the cell's esd and its frame-to-frame scatter by about 2.6×.
  The esd is conditional on the held values, so part of that is bookkeeping.
- The held routes sit 1.83 ppm low on every frame, about four of their own esds. That
  offset is frame 0's calibration error carried down the series, and no esd contains it.
- A joint fit over frames 0 and 6, sharing the zero shift and profile with a cell per
  frame, gives 0.007983(12)° against 0.00797(2)° from frame 0 alone. Calibrating across
  chosen frames, as Yue's step 2 does, is closer to the truth here.

**The same question on a real ramp** (`real_ramp.json`, from `measure_real_ramp.py`; macOS
arm64, worktree venv `[dev]`, Python 3.12.10, rietx 1.11.0.dev0, about 15 minutes). Seventeen
CuCr2O4 + CuO patterns from APS 11-BM, 6.8 to 288.7 K (`tests/data/seqrefine_cucr2o4/`,
development data of WP-2003, unsealed). The instrument is the file's own `.prm`, with an
8-term Chebyshev background. The model is `Fddd` on every frame. The spinel distorts below
about 130 K, so b and c are equal in truth above that temperature and split below it
(Suchomel et al. 2012, by way of `tests/data/README.md`). That gives a truth no fit statistic
supplies: where the split closes, and how large it is at 10 K (0.00746 Å in the paper).

Every frame of every route converged. "Closes" means |b − c| under 0.0001 Å.

| route | what can take up a change in peak width | b − c closes between | \|b − c\| at 6.8 K (Å), paper 0.00746 | b − c at 288.7 K (Å) |
|---|---|---|---|---|
| default | zero and all five profile terms, free on every frame | 111 and 123 K | 0.00554(113) | closed |
| `lab_sample_refine`, instrument from the `.prm` | the plan's sample widths | 111 and 123 K | 0.00562(90) | closed |
| cautious plan (scale, background, cell), instrument from the `.prm` | nothing | never | 0.00882(36) | 0.00270(32) |
| cautious plan, zero and profile from the default's fit of the 6.8 K frame | nothing | 47 and 75 K | 0.00554(80) | closed |
| cautious plan, zero and profile from the default's fit of the 288.7 K frame | nothing | 220 and 243 K | 0.00826(33) | closed |

Five readings:

- The transition lands at the right temperature only on the two routes where the width can
  change between frames. The three routes that hold the width put it near 60 K, near 230 K
  or nowhere. Which frame calibrates moves the transition by about 170 K.
- The likely mechanism is width against splitting (inferred; no fit tested it). A held width
  that is too narrow can be widened only by splitting b from c. A held width that is too wide
  swallows a real split. The default's U runs from 0.0036 at 6.8 K to 0.00031 at 288.7 K, so
  this specimen's width changes with temperature and no single frame speaks for the ramp.
- The false split is confident. On the cautious route the gap at 288.7 K is 8 of its esds.
  Only the 6.8 K calibration tripped the ladder, on four frames. The other two held routes
  stayed on warm rungs and each raised one code, `SEQUENTIAL_PERSISTENT_FINDING`.
- A closed gap is the data's answer under that width, and a warm chain does not create it.
  Eight frames refitted alone from the CIF's gap of 0.00687 Å landed within 1e-6 Å of the
  chain (`cold_check` in the JSON). On a closed frame the esd of b − c is 0.03-0.07 Å, so a
  closed frame reports no measurable gap and its "0.0 esds" in the script's output means
  nothing.
- The default and the width-free held route agree on the closure and on the split at 6.8 K.
  What separates them is smaller. The held route's esd on a is 1.8× tighter (36 against
  64 ppm), and that esd is conditional on the held values. It also carries the `.prm`'s zero of
  0 against the default's −0.0009°, which moves all three axes by about +75 ppm. Against the
  paper's cell the default's three errors average −8 ppm and the held route's +67 ppm. That is
  one comparison, 6.8 K against 10 K.

This does not show the traditional route failing. Steps 4 and 5 of Yue's account are one
sequence, and a scientist who reached step 5 would free sample width, as the `lab_sample_refine`
row does. It shows that the cautious pass read on its own, on a specimen whose width
changes, gives a false transition with a small esd. No route recovers the paper's split:
routes whose width was fitted at 6.8 K read 25-26 % low, and the other two held routes read
11-18 % high. Anisotropic strain was not tried. The ramp is one specimen on development data, the scans need not be the
paper's, and the model's b is the paper's c (an axis relabelling, compared in the paper's
order). The frame-0 plot shows a low-angle hump near 1.5° that the Chebyshev leaves in the
difference curve; its effect on the cell was not measured.

### The map: Yue's five steps against the tree

Read on `d7b62a3ac`. A row is marked *checked* where the tree was read or searched,
*measured* where it was run, and *inferred* where it was neither.

| step | what rietx offers today | what is missing | status |
|---|---|---|---|
| 1. Look at the raw series | `plot_pattern` draws one pattern. The GUI's Series panel lists each staged file's name, reader, points, range and σ, and draws one frame's fit after the run. `rietx watch` draws a run's snapshots. `plot_trajectory` needs a finished series. `rx.diagnose`, `rx.pick_peaks` and `rx.fit_peaks` work per pattern. | Any view of several patterns before a fit. "Waterfall", "heatmap" and "contour" have no hit in `src/` or `gui/src/`. WP-1444 and WP-1317 each rule it out of scope as later work. Nothing computes a statistic over the raw series, such as a frame-to-frame correlation. `SeriesResult.steps` exists only after a fit. | checked |
| 2. Fit each phase where its signal is strong | One fit over chosen frames exists: `refine_multi` with one structure per frame and `SharingMap(per_histogram=["phases.*.cell.*"], shared=["instrument.profile.*", "instrument.zero_shift"])`. `list_scans` gives each scan's temperature for Bruker `.raw` v3 only. | Nothing picks or helps pick the frames, so the choice is by hand from a view step 1 lacks. Nothing passes the joint fit's profile into a series except the caller's own code. A phase unseen on one chosen frame was not tried. | checked; joint fit measured on one phase |
| 2. Calibrate profile and background on one frame, then carry them | Two calls: fit the frame, then pass `ref.fitted_structure` and `ref.fitted_instrument` as the series' start. `save_instrument_profile` and `load_instrument_profile` carry the profile between sessions, and leave out the background and displacement by design. | A way to say this in one call. A series' `plan` runs on frame 0 and, collapsed, on every later frame, so one `fit` cannot free a parameter on frame 0 only without the three hooks of the measurement below. The series guide teaches neither route. Nothing says which frame to use, and on the real ramp that choice moved the transition by about 170 K. | measured |
| 3. An evolving background | Every preset frees `instrument.background.*` on every frame from the neighbour's value. Chebyshev and penalised P-spline backgrounds are available, and the P-spline's penalty acts along 2θ inside one pattern. `prepare` can rewrite the background per frame. `BackgroundFixedPlusChebyshev` holds a measured curve with a refinable scale. A joint fit can target a background coefficient with a `ParametricEquation`, so it can follow a declared function of temperature (docstring; not run). | Any link between frames inside a chain, such as a limit on how far the background moves between neighbours. `report.background.worst_absorption`, which measures a background imitating peaks, is per fit. `SeriesResult` does not carry it, so a chain cannot report the trading Yue calls tricky, and a caller must build each report from `results_`. | checked |
| 3. Spectator phases | A spectator can be a Rietveld phase, a `PeakComponent` per line (a declared peak with a free centre), or a measured curve in `BackgroundFixedPlusChebyshev`. `prepare` may add or remove a phase on a frame, and trajectories join by name (WP-1991). | A Pawley or Le Bail spectator beside a Rietveld phase. `mode` is one value for a whole fit, `CompiledModel.mode` is one value, and `Phase` has no mode field. A series takes one `mode`. | checked |
| 3. Exclusion regions across the series | `PatternData.excluded_regions` is per pattern, so a caller may give each frame its own list. `two_theta_limits` is one range for the series. The GUI copies the project's regions onto every frame (`gui/series.read_members`). | A series-level argument in the API. Any warning when a reflection moves into or out of a region: nothing in `report/`, `model/` or `sequential.py` compares the two. The only mention of the regions in a fit's output is the summary line that lists them. | checked |
| 4. A cautious first pass | A custom `RefinementPlan` or `PlanSpec` freeing scale, background and cell works, and `constrain` can hold more. The ramp's second row above is this. | A preset or a guide. `lab_sample_refine` releases more than this step does, and no other general preset fixes the instrument. On the real ramp this pass with no width freedom invents a split that never closes, so a guide must say what it cannot be read for. | measured |
| 5. Gradual release across the whole series | Nothing built for it. rietx's stages run inside one frame. `refit="stages"` re-walks the plan on each frame from its neighbour's answer, which is still one pass. A second `fit` starts again from the models the object was built with, and frame 0 runs cold. | A way to run pass 2 from pass 1's trajectory. It can be forced: a `prepare` hook writes each frame's first-pass values over the carried ones (the ramp's last row, about ten lines for a cubic phase, each released parameter by hand). The cold rung then starts from that frame's own answer too (measured). The record does not know: `entry.rung` says `warm` and `seeded_from` names the neighbour. `fitted_structures` holds one model per entry, so its positions shift after a failed frame. Nothing links the two passes or compares them. | measured |

Step 5 is the plainest gap. A human's release stages go over the whole series, and rietx's
stages run inside one frame.

### How it arose

Ruling WP-2080 (2026-11-02) needed to know whether its trigger sends extra frames to the
cold rung. Reading `sequential.py` for that answer showed that the cold rung forgets a held
setup value, and this WP was filed for that. Yue's account of 2026-11-03 widened it: the
held value is a symptom, and the default on later frames is the question.

### The surface as it stands

`src/rietx/sequential.py`, re-read on `d7b62a3ac`.

- `SequentialRefinement(structure, instrument, *, backend, solver, carry=("*",),
  carry_hkl_intensities=True, history=False)`. `refine_sequential(patterns, structure,
  instrument, ...)` is the one-call wrapper over it.
- `fit(patterns, *, x, x_label, labels, mode, plan, refit, two_theta_limits, direction,
  reseed, reseed_factor, first_rung_factor, verify_steps, prepare, constrain, on_result,
  on_error, events, cancel, progress, telemetry, label)`.
- The ladder, `RUNGS = ("warm", "warm_staged", "cold")` (WP-1051). `cold` is also what the
  first pattern runs.
- `SeriesResult`: one `SeriesEntry` per pattern (its rung, rungs tried and raised, the
  pattern it was seeded from), the trajectories, `steps`, failures and diagnostics.
- The joint fit (`multi.py`, `MultiHistogramRefinement`) is a different object. It stacks
  the patterns into one residual, and `SharingMap` decides which paths are one number for
  every pattern. `instrument.*` and `.scale` are per pattern by default, and a `shared=`
  glob overrides that. WP-1325 builds a parameter as a declared function of each pattern's
  coordinate on top of it.
- `SequentialRefinement.fit:plan` and `:refit` are in `UNAUDITED_BASELINE`
  (`src/rietx/_audit.py`), so today's default carries no recorded Rule 1 kind.

**PR #1310 (WP-2003), open and mergeable on 2026-11-04 at `4c54a0350`.** It sets
`reseed_factor` and `first_rung_factor` to `None` by default and removes `RESEED_FACTOR`,
`FIRST_RUNG_FACTOR` and `SEQUENTIAL_RWP_OUTLIER`. A warm frame then climbs the ladder when
it diverged, raised or carries an error-level diagnostic. `SeriesEntry.rwp_over_median`
replaces the fence as a field with no threshold, and Yue ruled on 2026-11-03 that no
summary line or code reports it. So a cold rung becomes rarer, and the held-value failure
quieter. That branch's record runs this WP's script: frame 3 stays 547 ppm off at GoF 9.76
and no diagnostic names it. Its audit row for `carry` also cites this WP.

**What the code does, verified against the tree.**

1. Every rung and every `verify_steps` refit goes through `_fit_one`. That builds a new
   `Refinement` and runs `prepare` and then `constrain` on it. So a hold or a tie declared
   in `constrain` applies on every rung (WP-1441). `on_result` runs on the reported chain
   only: the backward verification pass of `direction="both"` passes `None`.
2. `vary=False` on the models does not keep a parameter fixed. A plan replaces the vary
   flags (WP-1208), and `_collapse` frees the union of the plan's `turn_on` globs. Only
   `ref.hold(...)` protects a parameter (WP-1435), and a blocked glob reports
   `HOLD_BLOCKED_PLAN` at level `info`. The stage that frees `instrument.zero_shift` is
   `zero` in `mccusker_default` and `zero_disp` in `lab_bragg_brentano` (with
   `sample_displacement`). `load_instrument_profile` returns its "frozen" instrument as
   `vary=False` only, so a plan that frees those paths refines them.
3. The cold rung restarts from the initial models: `previous=None`, so no carried values,
   no carried variables (`previous_vars={}`) and no carried hkl intensities. The
   `verify_steps` refits are cold in the same way (`_verify_steps` passes `None`).
4. "Refine once, then freeze" has no declaration. A hold fixes whatever value reaches the
   rung. `carry` passes a value forward, and the plan refines it again unless it is held.
   The cold rung uses the initial value. A spelling does exist: three hooks together hold
   pattern 0's value on every rung. The damage is wider than one frame, because the
   pattern after a cold frame warm-starts from the cold frame's answer, so the initial
   value carries on down the chain.
5. Today's workaround is to calibrate separately (`lab_calibrate`, then
   `save_instrument_profile`), pass the calibrated instrument in and hold the setup
   parameters in `constrain`. A hold of a value the caller passed in survives the cold
   rung, because the initial model already holds it. The custom-plan route above reaches
   the same place with no hold, because no plan frees the paths. For one refined number
   across frames the joint fit is the tool.

**The cold-rung measurement** (`2081-batch/measure_cold_rung.py`, output `cold_rung.json`;
macOS arm64, worktree venv `[dev]`, Python 3.12.10, rietx 1.11.0.dev0, compiled tier on;
1.7-3.7 s for all four arms, the numbers below reproduced on `d7b62a3ac`). The first four
patterns of `tests/test_sequential.py`'s thermal LaB6 ramp, true zero shift 0.008°, start
model 0.0, plan `mccusker_default`. Frame 2's warm rungs are made to raise, as issue #224's
runaway neighbour made them raise, so the ladder keeps its cold rung.

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
  absorbs the missing zero shift and lands 546 ppm short, and GoF rises from 1.04 to 9.73.
  Frame 3 warm-starts from frame 2's answer, so it carries 0.0 too: −547 ppm, GoF 9.76,
  after climbing all three rungs.
- It is not silent on `main`, because the error is gross. `SEQUENTIAL_RESEED` says frame 2
  was refitted from the initial model, and `SEQUENTIAL_RWP_OUTLIER` fires on frames 2 and 3
  at 7.3× the Rwp fence. Neither names the held parameter or its value. After PR #1310
  nothing names frame 3. A setup error a tenth this size would move the cell by about
  55 ppm and could pass both (not measured).
- The three-hook workaround holds 0.00797° on every frame, cold rung included, and the cell
  stays within 2 ppm of the truth. `on_result` keeps pattern 0's value, `prepare` writes it
  into each later pattern's instrument, and `constrain` holds it.

**Practice** (`docs/practice.md` § Sequential refinement, "Parameters the setup fixes" and
"How a person works a series"). GSAS-II, FullProf, TOPAS and EasyDiffraction keep the fixed
flag on the parameter, and their series honour it on every pattern (GSAS-II read in source;
FullProf and TOPAS from their manuals; EasyDiffraction from the earlier survey). None of
them has a plan that frees a parameter the user fixed. None restarts a pattern from the
initial models, so a held value on a cold restart is a question only rietx has. GSAS-II
spreads flags across histograms with "Copy flags" and applies only wildcard-histogram
constraints in a sequential run. One refined number across patterns is a joint fit
everywhere: TOPAS's top-level parameters across `xdd`s, FullProf's multi-pattern PCR,
GSAS-II's plain multi-histogram refinement (recall). "Refine on the first pattern, then
freeze" is a manual step in every program surveyed (inferred).

Three findings are new in this rewrite, each in `docs/practice.md` with its source. GSAS-II
draws waterfall and contour plots over several histograms. With `Copy2Next` off, its
default, a GSAS-II sequential run starts each histogram's phase parameters from that
histogram's own result in an earlier run, so a second pass needs no setup there (checked in
source). GSAS-II and FullProf choose Rietveld or Pawley-like extraction per phase (checked),
and TOPAS does too (recall). The literature was not searched: Yue's account is the evidence
for the traditional workflow.

**Related WPs.** WP-1441 (ties and variables reach every pattern through `constrain`);
WP-1435 (the hold, and why `vary=False` is not one); WP-1208 (a plan replaces the vary
flags); WP-1051 (the ladder and the quarantine); WP-2003 (the chain actions and their
tiers, PR #1310); WP-2080 (a warm fit in a wrong basin; its ruled trigger escalates to
`warm_staged` only, so it sends no frame to the cold rung); WP-1325 (the parametric joint
fit); WP-2028 (the joint fit's screens); WP-2015 (the declared geometry picks the
`Refinement.fit` plan, which would free displacement on Bragg-Brentano); WP-1317 (the
post-fit series scrubber, which rules a waterfall out of its own scope).

**Tier.** Nothing here adds a rule yet. Any default the discussion chooses for the cold
rung is new judgement (tier 3, generality § The rule), because no program surveyed has a
cold rung. Any default for later frames falls under Rule 4 of `docs/DESIGN.md` § Rules.

### Inherited

## Open questions for the discussion

None is ruled. Rwp is inadmissible as evidence for any default here (Rule 4). Admissible
evidence is a cell or fraction against a known truth or an independent measurement, an esd,
and the movement of a setup parameter against its own esd. One real ramp is above. It has a
known truth for one quantity, so it can veto a route but cannot choose a default alone. A
series with a real change of setup, such as a heated lab specimen, was not run.

1. **What does a series do on the frames after the first, by default?** It serves whoever
   calls `refine_sequential` with no plan, whoever fills the GUI's Series panel, and an
   agent reading the guide. The options:

   | option | what changes | Rule 1 kind | named dissent |
   |---|---|---|---|
   | a. No change to the default; the guide and manual teach the traditional route | Docs only. The skill and the guide stop disagreeing | Adds no action. Today's default stays unrated | Yue's account of the traditional sequential |
   | b. A plan for later frames, an argument beside `plan` | Frame 0 and later frames can differ in one `fit`. It must say what the cold rung runs | No kind: a caller's statement, off by default | None |
   | c. A series-level declaration of what the setup fixes | Named paths refine on the calibrating frame and hold after it, on every rung. Also answers questions 2 and 4 for those paths | No kind: a caller's statement, off by default | None |
   | d. A report when a series frees setup parameters on every frame | Each setup path's movement across the series, in its esds, with what that means. It is reader output, so it goes to Yue before merge | Kind 3: only the experiment knows whether the setup moved. The statistic stops there, with no threshold, as `SeriesResult.steps` does | None needed |
   | e. Change the default: later frames stop freeing setup paths | Every default series changes number, and frame 0's calibration error reaches every frame (1.83 ppm above). Needs a plan-level notion of which paths are setup | Kind 1 fails its unanimity gate on the dissent at right, so at most kind 2 or 3 | Yue's account itself (an instrument term refined as a fudge for sample broadening). A heated lab specimen whose height moves with temperature, and a tray with one mount per frame (both inferred). Parametric refinement, which refines one value across all frames (Stinton & Evans 2007) |

   The same gate applies to today's default, because the traditional sequential is a
   named dissent to freeing the setup on every frame. Neither behaviour is unanimous.

   The real ramp bears on three options. Option e is safe there only if the frames keep
   somewhere for the specimen's width to go: holding the instrument and freeing sample
   widths matched the default's closure, and holding every width did not. So a notion of
   "setup" must exclude the width the specimen adds. Option d's statistic needs rethinking.
   Across the default's chain no setup parameter moved more than 1.9 of its own esds, yet
   freezing the width at either end of that range moved the transition by tens of kelvin or
   more. The marginal esds of five correlated profile terms are large (the cause is
   inferred), so a report in those units would have said nothing moved. A width at a stated
   2θ, propagated through the covariance, is a candidate and was not measured. Option a's
   guide must warn that the cautious pass alone cannot be read for a split or a width.

2. **How is "refine once, then freeze" spelled?** It serves a scientist with a script and
   an agent following the skill. Today it takes two calls, or three hooks. A spelling must
   say which frame or frames calibrate, because Yue's step 2 picks them by signal and frame
   0 need not be the strongest. On the real ramp neither end frame was a safe calibration,
   and only an instrument measured apart from the series gave the right closure, with widths
   free. Candidates: a documented two-call recipe; the declaration of question 1(c); a
   calibration step over chosen frames built on the joint fit, which measured closer to the
   truth on the synthetic ramp and was not tried on the real one. It also has to say which
   parameters follow a predictable change, since Yue's account allows for that as well as
   for constants.

3. **Do stages run over the whole series?** It serves anyone releasing parameters
   gradually (Yue's step 5). Today a stage is inside one frame. Candidates: a
   documented `prepare` recipe with its record repaired; a `fit` argument that starts each
   frame from its own answer in an earlier `SeriesResult`, as GSAS-II does with `Copy2Next`
   off; a list of plans run as passes. It must decide what `rung` and `seeded_from` record,
   which start wins between a neighbour and a frame's own earlier answer, what a cold rung
   means in pass 2, and whether the passes' trajectories are compared.

4. **Does a hold keep its value across the cold rung?** It serves anyone who holds a setup
   value today, and it is a smaller bug fix wanted whatever question 1 decides. A hold
   fixes the value that reaches the rung, so a cold frame holds the initial value and the
   next frame inherits it. Option A: the last accepted pattern's value, written after
   `constrain`, the order `_carry_variables` uses for named variables, and limited by
   `carry` as variables are. `set_values` accepts a held path (probed), so no new write
   path is needed. On the measured arm option A gives the three-hook row's value, 0.00797°.
   The alternatives are the caller's value (today) and the first pattern's value. Three
   points to settle with it: a value `prepare` set for this frame on purpose must win over
   the write; the `verify_steps` refits are cold too, so they need the same answer; and
   when a frame runs with a setup value different from its neighbours', the series should
   say so by name. PR #1310 makes that last point sharper, as nothing else will.

5. **What should an agent do, as opposed to a human?** It serves agents, and it sets what
   the skill says. Yue's caveat keeps this open, and no answer is written here. Examples of
   what it covers: whether screens over the raw series replace visual inspection, whether
   an agent needs the traditional order given what a fit costs it, and whether it should
   read a waterfall as an image.

6. **Is there a view of the raw series before a fit?** It serves a person at step 1, and
   the answer to question 5 may make it serve agents. WP-1444 and WP-1317 both left it as
   later work. To decide: a figure, a GUI panel or both, and its owner.

7. **What does a series say about an evolving background?** It serves anyone quoting phase
   fractions along a ramp or a battery cycle. `worst_absorption` is per fit and absent from
   `SeriesResult`. To decide: whether an entry carries it, and whether a link between
   frames is wanted at all, or whether that is the joint fit's job.

8. **Should a spectator phase be Pawley beside a Rietveld phase?** It serves in situ cells,
   holders and sample environments. Today `mode` is one value for a fit. To decide: per-phase
   modes, which would reach `CompiledModel.mode`, the force-fix of a Le Bail phase and QPA,
   or a recipe from the existing members.

9. **Does a series check its exclusion regions?** It serves anyone masking a spectator's
   peak on a ramp where a sample peak moves. To decide: a series-level `excluded_regions`
   argument, and a report (kind 3) of reflections crossing a region's edge.

Lower questions, still open:

10. Should `vary=False` mean "fixed" anywhere, for example on a series' models or on a
    loaded instrument profile?
11. Should the chain and the joint fit share a surface, given that one refined number
    across frames is a joint-fit question?
12. How should GUI and agent users meet the answers: a control, a field on the result, a
    skill row, a manual page?

## Non-goals

- WP-2080's trigger and its factor.
- The ladder's other rules (WP-2003).
- The joint fit's guards (WP-2028) and the parametric joint fit (WP-1325), except where
  questions 2 and 11 ask whether the two surfaces meet.

## Tasks

- [ ] The discussion with Yue on the open questions. Record each ruling in this file
      with its grounds, and mark any call settled by Claude as such.
- [ ] Turn the rulings into work: fold each into this WP's tasks or the owning WP, or
      file a new WP, each with its practice row and the measurement it rests on.
- [ ] Skill: decided with the rulings. Until then none, because the surface it would
      describe is open. `references/series.md` already states the traditional route, so
      the discussion also decides whether the guide moves to it.

## Acceptance

The rulings are in this file and the follow-up work is filed.

```sh
.venv/bin/python -m pytest tests/test_docs_consistency.py -q
.venv/bin/python docs/wp/2081-batch/measure_cold_rung.py
.venv/bin/python docs/wp/2081-batch/measure_routes.py
```

`measure_real_ramp.py` stays out of this list because it takes about 15 minutes. Its `--report`
flag reprints the saved numbers without fitting.

## References

- `src/rietx/sequential.py` (`_fit_one`, `_chain`, `_ladder`, `_collapse`,
  `_carry_variables`, `_verify_steps`), `src/rietx/refine.py` (`Refinement.hold`),
  `src/rietx/multi.py`, `src/rietx/params/multi.py` (`SharingMap`),
  `src/rietx/io/instrument_profile.py`, `src/rietx/strategy/staged.py` (the presets),
  `src/rietx/schemas/pattern.py` (`excluded_regions`), `src/rietx/gui/series.py`.
- `docs/skill/rietx/references/series.md`, `examples/guides/series.py`.
- `docs/practice.md` § Sequential refinement.
- `docs/DESIGN.md` § Rules (Rule 1 and Rule 4).
- Stinton, G. W. & Evans, J. S. O. (2007). Parametric Rietveld refinement. *J. Appl.
  Cryst.* 40, 87-95.
- Issue #224 (a warm rung that raises and a cold rung that does not).
- Suchomel, M. R. et al. (2012), the CuCr2O4 ramp's reference; the citation is in
  `tests/data/README.md`.

## Handover log

- **2026-11-04** — rewritten around Yue's account (a ghostshift runner, one session). No
  package code changed, and no question is ruled. Yue said in chat on 2026-11-03 how an
  expert runs a series: fit what the setup fixes, hold it, then release parameters in
  stages across the whole series. A full refit on every frame is very unusual. rietx's
  default does that refit, so the held value on the cold rung stopped being the whole
  question. The account is recorded above with Yue's caveat that agents need not follow it.

  *Done.* The seven open questions are replaced by nine plus three lower ones, in the
  order the map gives. Old 1 and 3 moved into questions 1 and 2, old 2 and 6 into 4, old
  4, 5 and 7 into 11, 10 and 12. Added the crux, the preset table, the map of Yue's five
  steps (each row marked checked, measured or inferred) and `2081-batch/measure_routes.py`
  with `routes.json`. Re-verified the five-point code reading on `d7b62a3ac`, correcting
  one word: `HOLD_BLOCKED_PLAN` is an `info` diagnostic. `measure_cold_rung.py` still runs
  and reproduces its table. PR #1310's state is written from `gh pr view` and its diff.
  Practice survey added to `docs/practice.md`. Ran one real ramp beyond the brief
  (`measure_real_ramp.py`, `real_ramp.json`) because the synthetic ramp's constant
  instrument could not say which route is right. Holding every width put the CuCr2O4
  transition near 60 K, near 230 K or nowhere, against about 130 K. The default and
  `lab_sample_refine` from the `.prm` both closed between 111 and 123 K.

  *Gotchas.* `measure_routes.py` patches `_fit_one` on the same positional signature as
  `measure_cold_rung.py`. Its `prepare` hook copies a cubic phase's released values by
  hand, so it is an existence proof and no recipe. The synthetic ramp's instrument is
  constant by construction, and that flatters every held route. `measure_real_ramp.py`
  takes about 15 minutes, so use `--report`; `--step-two` and `--cold-check` rerun parts.
  Its printed "combined esds" line means nothing on a closed frame, where the esd of b − c
  is 0.03-0.07 Å. GoF is in the JSON and was used for nothing.

  *Next:* the discussion with Yue (task 1), starting at question 1.

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
