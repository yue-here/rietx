# WP-2081 — How a series holds what the setup fixes (a design discussion)

Milestone: series · Status: 🔄 2026-11-18 — the rulings are being built; the width-growth removal is in review
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

- **2026-11-15, from the issue triage (issue #1556 § 5): a held setup value's error
  moves every later cell together, and the series has no row for it.** The reporter ran a
  synthetic LaB₆ ramp, 7 patterns × 150 noise replicates, and held zero and profile from
  pattern 1 on at pattern 0's fitted values, the calibrate-then-hold practice this WP
  starts from. Free on every pattern, the cell's pull std is 0.79-0.93 and neighbouring
  patterns' errors correlate at −0.09 to 0.04. Held, the pull std is 2.30-2.43 and the
  correlation 0.85-0.90. So each pattern's cell esd is about 2.4× too small, and a series
  mean's esd about 5.5× too small (rms error 0.88 ppm against a naive esd of the mean of
  0.16 ppm). The cause is the held calibration's own error, shared by every pattern.
  Not rerun here. *Checked against the tree at `98d7ba8e3`:* `SeriesResult` carries no
  row for a held parameter, and `HOLD_BLOCKED_PLAN` is info only. The reporter's
  candidate: a per-pattern score statistic for each held parameter, as a row with no
  threshold, and asks whether that sits inside the maintainer's 2026-11-03 "field, not
  code" ruling. That question is for this WP's discussion. The rest of the issue (a χ²
  pair per chain, now in WP-1453; equivalence mapping; the combined-esd step; unmeasured
  points) is placed elsewhere or held for the maintainer.

- **2026-11-06, from the issue triage (issue #1439): the free set can change
  from frame to frame on its own, through the absent-phase hold.** A design
  proposal from the recurring contributor, from a private multiphase in-situ
  series fitted by their own driver, not by `refine_sequential`. They refitted
  the series with two instrument parameters held and compared the two fits of
  each frame by ΔBIC. In a few percent of frames the two fits refined different
  parameters beyond the declared holds: a minor phase's cell, strain and size.
  The cause was the absent-phase hold (WP-1301; a phase whose scale is under 3σ
  of its counting-noise esd has its structural paths held for the stage,
  `phase_support_sigma`). A minor phase near 3σ fell either side depending on
  the rest of the fit. So the two fits were not nested, and along a chain the
  gate can switch a phase's cell on and off and put steps in its trajectory.
  *Checked against the tree at `a84379aac`:* `sequential._collapse` passes
  `phase_support_sigma` into the collapsed warm plan (the WP-2002 B1 comment
  there), so the hold decides afresh on every warm refit. Each entry records
  what its last stage held (`sequential.py` reads `result.stages[-1].held`).
  The effect has **not** been measured in `rietx.sequential`; the reporter
  offers a synthetic reproduction. The proposal: the cold first frame resolves
  the free set, gates included; every warm refit frees exactly that set; the
  support test still runs per frame and a disagreement is recorded, not acted
  on, as WP-2003 records steps; `SeriesResult` records the set once. A
  companion check compares two `SeriesResult`s of the same frames, one a
  declared restriction of the other, and reports per frame (a) free sets that
  differ beyond the declared holds and (b) a larger model ending at a higher χ²
  than the restricted one, which cannot happen at a true minimum. The reporter
  says (b) found every local minimum they met (a magnetic moment stuck at zero
  from a fixed start). **Where it lands here:** it is question 1 one rank down.
  "What a series frees after the first frame" covers frees decided by a gate
  as well as by the plan, and options b and c above fix the set by a caller's
  statement, where #1439 fixes it by frame 0's own gates. **It pulls against
  WP-1420**, whose goal is that a phase held in one frame gets back in when a
  later frame supports it. A set fixed at frame 0 keeps a late-appearing
  phase's structure held for the whole series, its scale alone free. Decide the
  two together. **Prior art, corrected:** the issue says GSAS-II stops when the
  vary list changes between histograms. GSAS-II 5.8.4 prints the variables
  added and removed and carries on (`GSASIIstrMain.py:1038-1058`, the stop is
  commented out; `docs/practice.md` § Sequential refinement already says so).
  The issue's wider point stands: no program surveyed switches refine flags per
  pattern on a significance test.

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

- **2026-11-18** — the series no longer warns when a phase width grows (one session; package
  code changed).

  A series no longer raises a warning when a phase width grows while the fit worsens. Yue
  ruled it removed on 2026-11-16, because it fired on three thresholds nobody had audited,
  and the width's trajectory and each pattern's GoF were already on the result. A caller
  who wants that reading now puts the two side by side, and the skill says so. Nothing a
  fit computes has moved. The report-thresholds contract moved to 1.15, so a reader
  counting codes can tell the two versions apart. This entry also stands for the two
  2026-11-17 commits of the last session (the joint-ramp measurement and the WP-2028
  fold), which the 2026-11-16 entry below already describes.

  *Done.* Removed `SEQUENTIAL_WIDTH_GROWTH`, its suggestion, `WIDTH_GROWTH_FACTOR`,
  `WIDTH_GROWTH_GOF_FACTOR`, `WIDTH_GROWTH_SIGMA` and `_WIDTH_SUFFIXES`
  (`sequential.py`). Removed the "widths grown with a worsening fit" row of
  `SeriesResult.summary(deliverable="series")`, the help entry and the five audit rows
  with their `UNAUDITED_BASELINE` and `RESPONSE_BASELINE` lines. Removed eleven tests in
  `test_sequential.py` and two in `test_termination_view.py`, and narrowed
  `test_planted_series.EVENT_CODES`. `THRESHOLDS_VERSION` 1.14 → 1.15; its history line
  also names WP-2003's `SEQUENTIAL_DISCONTINUITY` removal, which no version had recorded
  (WP-2004 Inherited asked for that line). The skill, the manual's series and result
  references, `docs/practice.md` and tutorial 05 lose their mentions, and the skill's
  generated API index quotes 1.15. Added a release-note fragment
  (`docs/releases/unreleased/wp2081.code-to-check.md`). The milestone record and WP-2004
  say the removal landed with no field. The ruling supersedes the record field that
  WP-2003's C7 and issue #1212 had proposed.

  *Started in its own session.* The W esd question (WP-2028 Inherited, 2026-11-17) is
  being worked in a separate session, PR #1668.

  *Review.* `/code-review high --fix` found two items. Fixed: the release note named
  only `ImportError`, where attribute access raises `AttributeError`. No change: an old
  saved result carrying the code loses its help text. WP-2003's removal of
  `SEQUENTIAL_DISCONTINUITY` set that precedent, and the help tests require every entry
  to name a live code.

  *Measured* (macOS arm64, worktree venv `[dev]`, Python 3.12.10). The fast selection ran
  twice under heavy load from another session's 17-pattern ramp (load average 35-63).
  The first run was killed from outside at 86 % with no failure. The second run ended
  2 failed, 14701 passed, 433 skipped, 32 xfailed and 23 errors, in about 71 minutes.
  One failure was real: the skill's API index was stale against 1.15, now regenerated
  (`test_skill.py` 174 passed). The other failure and all 23 errors were the manual
  build and the magnetic guide script hitting their 300 s runaway guards. Re-run once
  the load fell, `test_manual.py`, `test_help.py` and the guide-script test passed
  (129 passed). The count check is not done: no baseline ran, so passed+skipped cannot
  be compared. The branch removes 13 tests and adds none, so the junit cost report has
  nothing to rank. The full selection did not run: removing a diagnostic moves no
  fitted number. `tests.reader_output` reports no change, but its fixtures hold no
  series summary, so the removed summary row is a change it cannot see.

  *Generality* (the `generality-review` judge, on the branch diff before this entry and the skill rewording; pasted unedited).

  #### `SEQUENTIAL_WIDTH_GROWTH` (code), deleted

  **holds.** The case against the code is stronger. Its thresholds rest on one real positive chain, and that chain is not on disk. A dissent was already named against it. The case for it is a single synthetic measurement showing that nothing else fires, and the raw numbers that measurement reads are still on the result.

  | Question | Author's answer (where) | What I found | Verdict |
  |---|---|---|---|
  | 1. What must the caller now decide? | "The width trajectory and each pattern's GoF are already in the result, so rule 5 is met without it." (`docs/milestones/series.md` § Ruled after the open, lines 119-123). Release note: "read the two side by side" (`docs/releases/unreleased/wp2081.code-to-check.md`) | The deleted code made five choices the caller now makes. (a) The reference is the first width measured above 3 of its own esds, not the first value. (b) A Gaussian variance term is compared on its square root. (c) Quarantined patterns are skipped. (d) Widths tied to one column count as one trajectory. (e) It fires only where the width ratio is ≥3×, the growth exceeds 3 combined esds, and the GoF ratio is ≥2×. Deleted docstrings: `sequential.py` lines 401-446 and 464-500 of the diff. The series summary's "widths grown with a worsening fit" row goes too. | answered |
  | 2. Which kind of ambiguity? | Row: none given (it was `unaudited`, with no `ambiguity`). WP-2003's draft (the audit of the series' automatic actions) gives `"ambiguity": 3` (`docs/wp/2003-batch/rows.json`:301) | Kind 3 is right. Whether a width grew because the specimen strained or because a phase is missing from the model depends on facts outside the pattern. The deleted docstring says so itself: "the finding reports and never judges". Series rule 5 puts kind 3 in a field with no code. | agrees with the draft; row itself none given |
  | 3. Case against the code | C7 (class 7 of WP-2003's batch, width growth): "Three tier-3 thresholds decide whether the code exists, on one real family." The dissenter it names is "a refiner whose strain grows for real while GoF rises for a second, independent reason" (`docs/wp/2003-batch/batch.md`:639-648). That batch was settled by Claude and relabelled as evidence on 2026-11-02. | Confirmed, and one more mechanism found. With a fixed fractional misfit, χ² grows with the counts, so GoF grows as √counts. A series whose counts rise (a growing phase, a longer count time, a beam refill) can therefore double GoF under a model whose only fault was already there. The deleted GoF constant's docstring guards only against falling counts ("Rwp tracks Rexp"). Both of its measurements were at constant counts ("on the synthetic, whose counts are constant"). The deleted real-growth null test (`test_a_width_that_grows_for_real_is_not_named`) also used one scale throughout. No program among the seven screens widths along a series: the pre-change `docs/practice.md`:398-399 listed this screen among rietx's own behaviours (checked in this repo). | strong |
  | 4. Case for the code | Deleted skill row: "No per-pattern code says so until `STRAIN_UNUSUALLY_LARGE` at 1.5° (Measured: a 0.4 %-split second phase, width 3.65×, GoF 3.1×, nothing else fired)". `docs/wp/1465-a-width-that-became-background.md` (WP-1465, which added the code) Finding 1: a one-phase fit's Rwp went 1.56 % → 11.74 % with no warning, and the width's background-projection R² moved only 0.047 → 0.053. | Real, but synthetic only. What a caller pays now is computing the statistic correctly. The deleted `WIDTH_GROWTH_FACTOR` docstring measures the naive version: against each trajectory's first value, width growth alone fires on 11 of 24 trajectories of the CPD chain (the clean quantitative-phase round-robin chain in the acceptance suite). Taking the first measured value fires on none. One CPD first value is 5.85e-5 with an esd of 3e3, so any later value reads as "946×" it. No number moved off a reference was measured: the soaked phase's scale or fraction error against truth is not given. DESIGN.md § Rules, 1 says "every withheld verdict leaves its statistic". Its inputs stay, but the statistic itself (the ratio with its esd, the GoF ratio) is no longer computed. WP-2003's C7 proposed exactly that field. The 2026-11-16 ruling supersedes it, and that ruling is yours. WP-2080's GoF-ratio field is ruled but not built. | moderate; synthetic only |
  | 5. Tier | none given (row unaudited) | It could only have been tier 3: no program default exists (`docs/practice.md`, checked in this repo). It is not `invariant`, since it changed what a series printed. | consistent with removal |
  | 6. Dataset families | none given in the row. Deleted docstrings and `rows.json`:302 list them. | 1. The synthetic soak (rietx's own test, LaB6 model with a planted 0.4 %-split phase). The reference is a known truth. Development data. 2. The CPD chain (real), silent. A null only, development data. 3. The 75 suite series that set the GoF clean bound of 1.52. Development data. 4. Issue #451's operando chain (the reporter's laboratory, real): widths 3.4×, not on disk. So there is one real positive family, and it is off disk. It falls short of the three-family ground. | fails the mechanical ground, so removal is consistent |
  | 7. What says it fired, or that it is gone? | `THRESHOLDS_VERSION` 1.15 history comment (`src/rietx/report/schemas.py`) | After removal nothing fires. The disappearance is recorded by `THRESHOLDS_VERSION` 1.15 (the report-thresholds contract version), which every `SeriesResult.provenance.report_thresholds_version` stamps, and by the release note. | adequate |

  Missing from the author's case: the WP-2081 handover log has no entry for this removal. Its latest entry (2026-11-16) still says "Neither is built".

  What would change the verdict: a real chain on disk where a width grew with GoF, plus a measurement showing that a caller reading `statistics.gof` by hand either misses it or flags a clean chain.

  #### `SEQUENTIAL_WIDTH_GROWTH.suggestion` (suggestion, value 1), deleted

  **holds.** The case against is stronger: the suggestion assumed one of the code's two readings.

  | Question | Author's answer (where) | What I found | Verdict |
  |---|---|---|---|
  | 1. What must the caller now decide? | none given beyond the code's removal | The deleted text was "Fit the pattern at the onset with the missing component before reading this width…". The caller now decides whether anything is missing at all. | answered |
  | 2. Which kind? | Row: none given. `rows.json`:319: ambiguity 3 | Kind 3 is right. | agrees |
  | 3. Case against | `rows.json`:320: "assumes a missing component, one of the docstring's two readings" | Confirmed by the deleted docstring, which allows that "the width may legitimately grow". | strong |
  | 4. Case for | none found | none found | — |
  | 5. Tier | none given | Tier 3 at best. | — |
  | 6. Dataset families | as for the code | as for the code | — |
  | 7. Record | the code's | It goes with its code, and no orphan site remains (grep of `src/`). | adequate |

  What would change the verdict: none short of the code returning.

  #### `rietx.sequential.WIDTH_GROWTH_FACTOR` (3.0), deleted

  **holds.** The case against is stronger: the value is "the reporter's", fitted between two soaks, and it has no consumer left.

  | Question | Author's answer (where) | What I found | Verdict |
  |---|---|---|---|
  | 1. What must the caller now decide? | milestone: "on three unaudited constants" | The caller picks their own multiple, or none. | answered |
  | 2. Which kind? | n/a (constant) | It was a threshold on a kind-3 report. | — |
  | 3. Case against | Deleted docstring: "3 is the reporter's, and it sits between the two soaks measured" (3.4× operando, 3.65× synthetic). "The width ratio does not separate on its own." | Fitted to two positives, one of them off disk. | strong |
  | 4. Case for | Deleted docstring: against the first measured value it fires on none of CPD's 24 trajectories | That is a null on development data only. | weak |
  | 5. Tier | none given | Tier 3. No program screens this. | — |
  | 6. Families | as for the code | One real positive family, off disk. | fails |
  | 7. Record | `THRESHOLDS_VERSION` 1.15 | adequate | — |

  What would change the verdict: three unrelated real chains where 3× separates a missing-phase soak from real growth.

  #### `rietx.sequential.WIDTH_GROWTH_GOF_FACTOR` (2.0), deleted

  **holds.** The case against is stronger. The value was set for margin on development data at constant counts, and GoF itself moves with counts.

  | Question | Author's answer (where) | What I found | Verdict |
  |---|---|---|---|
  | 1. What must the caller now decide? | as for the code | The caller judges whether a GoF rise is "with" the width. | answered |
  | 2. Which kind? | n/a | It was the threshold on the misfit half. | — |
  | 3. Case against | Deleted docstring: "The value is set for margin". Clean bound 1.52 over 75 suite series; synthetic soak 3.05. | All of it is development data. A rise in counts raises GoF under a fixed misfit, and none of those measurements varied the counts. | strong |
  | 4. Case for | Deleted docstring: "This half is also what keeps a width that grows *for real* silent" | True on the constant-count synthetic only. | weak |
  | 5. Tier | none given | Tier 3. | — |
  | 6. Families | 75 suite series (development), CPD 1.14, synthetic 3.05 | No real positive family on disk. | fails |
  | 7. Record | `THRESHOLDS_VERSION` 1.15 | adequate | — |

  What would change the verdict: a real series with varying counts where a 2× GoF ratio still separates the two readings.

  #### `rietx.sequential.WIDTH_GROWTH_SIGMA` (3.0), deleted

  **holds.** The case against is stronger. Its job was to keep the reference meaningful, and with the code gone it has no consumer.

  | Question | Author's answer (where) | What I found | Verdict |
  |---|---|---|---|
  | 1. What must the caller now decide? | none given | The caller chooses which pattern counts as the reference. Deleted docstring: CPD's "first `lor_strain` is 5.85e-5 with an esd of 3e3, so any later value is '946×' it". | answered; this is the trap the caller inherits |
  | 2. Which kind? | n/a | It was a threshold. | — |
  | 3. Case against | none given | It was rietx's own 3σ, with no source given. | moderate |
  | 4. Case for | the deleted docstring above | It guarded the ratio. It is not needed without the ratio. | weak |
  | 5. Tier | none given | Tier 3. | — |
  | 6. Families | CPD (development) | one | fails |
  | 7. Record | `THRESHOLDS_VERSION` 1.15 | adequate | — |

  What would change the verdict: the code or a ratio field returning.

  #### `rietx.sequential._WIDTH_SUFFIXES` (no row), deleted

  **holds.** The case against keeping it is stronger: it maps width paths to "variance or width", an arithmetic fact, and its only consumer is gone.

  | Question | Author's answer (where) | What I found | Verdict |
  |---|---|---|---|
  | 1. What must the caller now decide? | C7: "`_WIDTH_SUFFIXES` is tier 1, no row" (`docs/wp/2004-…md`, inherited entry; `batch.md`:646) | Whether to compare the square root of `gauss_*`, which are variance coefficients. | answered |
  | 2. Which kind? | n/a | n/a | — |
  | 3. Case against | none needed | It has no other consumer in `src/` (grep). | — |
  | 4. Case for | none found | none found | — |
  | 5. Tier | tier 1 (WP-2003's batch, settled by Claude) | Correct: the variance-versus-width split is arithmetic. A dict of booleans is outside the constant walk, so having no row is consistent. | holds |
  | 6. Families | n/a | n/a | — |
  | 7. Record | n/a | n/a | — |

  What would change the verdict: another consumer of the dict surviving in the tree. None found.

  #### `UNAUDITED_BASELINE` and `RESPONSE_BASELINE` removals

  **holds.** These are removals only: five names leave `UNAUDITED_BASELINE` (the shrink-only list of rows awaiting audit), and the code leaves `RESPONSE_BASELINE` (codes still without a reader response). Their rows are gone, so each list shrinks as designed. No name was added, so no reason is owed.

  What would change the verdict: a name added to either list. There is none.

  #### Skill line, `docs/skill/rietx/references/series.md`:355-359 (and its two synced copies)

  **weak** as wording. It is not a new heuristic the table should see. The case against its verdict is stronger than the case for it.

  | Question | Author's answer (where) | What I found | Verdict |
  |---|---|---|---|
  | 1. What does it decide? | "Read each entry's `statistics.gof` beside the width's trajectory: a width that grows while GoF rises with it stands in for a missing component, and one that grows at a flat GoF is this rule. No code fires on either." | The package decides nothing here and prints nothing. Skill prose is outside the table's sight by declaration (`_audit.py` docstring: "a heuristic written as skill prose (WP-2008)"). No row of the five kinds could hold it. In substance it is the deleted code's conjunction without thresholds, so it is not new. | not a table item |
  | 2. Which kind? | none given | The question is kind 3, but the sentence answers it as if kind 1: "stands in for a missing component". The deleted docstring was more careful: "the finding reports and never judges". | wording overstates |
  | 3. Case against its wording | none given | C7 names the dissent, a real strain growth with GoF rising "for a second, independent reason" (`batch.md`:641). GoF also rises with counts under a fixed misfit. | strong |
  | 4. Case for | It names a field (`statistics.gof`), which DESIGN.md § Rules, 4's skill-row test asks for. The outside source is issue #451's operando chain (a user's report), beside rietx's synthetic. | It passes the skill-row test. It is the only pointer left to this failure mode now that the code and the summary row are gone. | moderate |
  | 5. Tier | n/a | n/a | — |
  | 6. Families | as for the code | One real chain, off disk, plus rietx's synthetic. | thin |
  | 7. Record | "No code fires on either." | Accurate. | holds |

  What would change the verdict: rewording to "may stand in for a missing component; GoF also rises when counts rise". That would make it a pointer to two readings rather than a verdict.

  *Author's answer on the skill line:* reworded as the judge proposed, so the line now names both readings and says GoF rises with the counts. *On the missing entry:* the judge read the diff before this entry was written.

  *Next:* Yue reads the milestone record's title, scope and draft acceptance rows. Then
  rule 1's declaration on the series call, which the milestone's order puts next. The
  remaining thresholded series code, `SEQUENTIAL_MOMENT_ONSET`, waits on the magnetic
  path's owner.

- **2026-11-16** — the discussion began, and the series milestone opened (one chat
  session with Yue; no package code changed).

  *Rulings by Yue, in chat.* Six design rules for series work were put to Yue. Five were
  accepted at once and rule 2 after a second explanation, in a changed form. They are recorded with Yue's words
  in [`docs/milestones/series.md`](../milestones/series.md) § The rules, which is now
  their authority. Yue ruled that series is its own milestone, separate from parametric,
  and this WP moved to it. Yue ruled WP-2080 to option A, the ratio as a field with no
  automatic retry (that file's handover log), and approved the comment posted on PR #1473.

  *What the rules settle here.* Questions 2 and 3 fall to rules 1 and 2, question 4 to
  rule 6, question 5 to rule 4, questions 7 and 9 to rule 5 and question 11 to rules 1 and
  2. Question 1, the default on later patterns, is still open and is the first open
  decision in the milestone record. No question in § Open questions is edited: this entry
  and the milestone record say where each stands.

  *Two more rulings, later the same day.* Question 1 is ruled: the default stays as it is
  (option a), in Yue's words "keep today's default". `SEQUENTIAL_WIDTH_GROWTH` is to be
  removed ("Remove"). Both are in the milestone record § Ruled after the open, with the
  options put. Neither is built. Rule 2 is ruled too: the series call and the joint call stay two
  calls ("Yes, two calls"), the series call taking per-pattern and fixed parameters only.
  All six rules are now accepted.

  *Stale lines above, not yet corrected.* Context says PR #1310 is open and mergeable; it
  has merged. Context says `SequentialRefinement.fit:plan` is unaudited; it has a tier-3
  row approved 2026-11-03, recorded as unanimous, and `fit:refit` is still unaudited.
  WP-2080's trigger no longer waits on anything, and is ruled to a field.

  *Measured: a joint fit on the real ramp* (`2081-batch/measure_joint_ramp.py`, output
  `joint_ramp.json`, `--report` reprints it; run by an Opus subagent, the saved numbers
  re-read by this session; macOS arm64, worktree venv `[dev]`, Python 3.12.10, rietx
  1.12.0.dev0, compiled tier on). All 17 CuCr2O4 patterns in one `refine_multi`, each
  started from the `lab_sample_refine` chain's model for that pattern, Biso held at the
  chain's values. Wall times are from a machine under uncontrolled load.

  | arm | common to all patterns | per pattern | wall, evaluations | b − c closes between | \|b − c\| at 6.8 K (Å), paper 0.00746 | common zero (°) | mean axis error at 6.8 K vs the paper (ppm) |
  |---|---|---|---|---|---|---|---|
  | chain, default (WP table above) | nothing | zero, profile, cell, scale, background | — | 111 and 123 K | 0.00554(113) | −0.00095(65) per pattern | −7 |
  | chain, `lab_sample_refine`, `.prm` | nothing; zero fixed at 0 | cell, scale, background, sample widths | 414 s | 111 and 123 K | 0.00562(90) | 0, fixed | +67 |
  | A | zero; profile fixed at the `.prm` | the same | 584 s, 143 | 111 and 123 K | 0.00563(86) | −0.00073(11) | +10 |
  | B | zero and U, V, W, X, Y declared | the same | 528 s, 227 | 111 and 123 K | 0.00562(89) | −0.00073(11) | +10 |
  | C0 | zero and U, V, W, X, Y | cell, scale, background; every sample width 0 | 428 s, 277 | 123 and 134 K | 0.00801(41) | −0.00073(11) | +21 |

  Five readings.

  - A common zero shift works on real data. It is fixed about 6× tighter than a
    per-pattern zero, the closure does not move, and the +67 ppm of the held-at-0 route
    falls to +10 ppm. The split itself reads the same 25 % under the paper in A and B, so
    the method did not cause that.
  - A joint fit of 17 synchrotron patterns costs about what the chain costs here, 7 to 10
    minutes.
  - Arm B's declaration was narrowed by the package. `multi._hold_width_twins_multi` holds
    U, X and Y from the stage where a per-pattern sample width of the same angular shape is
    free. `StageResult.width_twins_held` records it; no diagnostic code does, and a held term
    is absent from `result.parameters`. Only zero, V and W were common and free at the end.
  - W is not determined in arm B. A second start with the profile moved 30 % ends at the
    same χ² (274072.45 against 274072.74), the same cells and zero to 1e-9, and W at 6.5e-6
    where the first ended on its floor of 1e-8, traded against every pattern's `gauss_size`.
    Both report an esd for W near 1e-12, and `COVARIANCE_DIRECTION_DISCARDED` names W. A
    small esd on a value two starts disagree on by 6.5e-6 looks like a defect against the
    rule that an unmeasured direction has no esd. Not investigated.
  - Arm C0 holds no width at one pattern's value: one profile is refined for all patterns
    and no sample width is free. It closes between 123 and 134 K, which brackets the
    paper's 130 K, and reads the split 7 % over the paper where every other route reads 25 %
    under. Its common Y is 0.0508(37) against 0.0072(34) with the chain's sample widths
    held (arm C in the JSON), so the one profile takes up the specimen's own broadening. This is one specimen on development data, so it shows only that "a held width
    invents a transition" (the cautious routes above) is a statement about a width taken
    from a single pattern.

  Not run: Biso free; an arm that pins one pattern's sample widths so U, X and Y could be
  common beside free widths; a second start for C0. The esd of b − c ignores their
  correlation, as the table above does.

  *Next:* Yue's read of the milestone record's title, scope and draft acceptance rows;
  the open decisions listed there; W's esd in the joint fit, as its own investigation.

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
  `lab_sample_refine` from the `.prm` both closed between 111 and 123 K. Filed in PR #1399.

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
