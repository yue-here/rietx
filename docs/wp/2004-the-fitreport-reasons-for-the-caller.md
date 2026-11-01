# WP-2004 — The FitReport reasons for the caller: its gates, actions and thresholds

Milestone: generality · Status: ⬜
Track: The audits
Depends on: 2002, 2003
Priority: P2 2026-10-26 — 2003 ruled its batch (its width-growth ruling is in Inherited); 2003 is still open, so the bump waits on its demotions landing

## Goal

Every gate, action kind, template and threshold in `src/rietx/report/` is in the audit
table with a tier. The four Layer-1 gates and the share-based maturity are either evidenced
on three families or demoted to numbers the report states. `THRESHOLDS_VERSION` is bumped
once, here, carrying 2003's width-growth rulings too.

## Context

The rule is `../milestones/generality.md` § The rule. This WP applies it to `report/`
(`layer0.py` 266 lines, `layer1.py` 517, `layer2.py` 1 250, `body_misfit.py`,
`background.py`, `identifiability.py`, `localisation.py`, `strain.py`, `texture.py`,
`magnetic.py`, `satellites.py`, `schemas.py`) and to `optimize/statistics.py`'s report-facing
constants.

**What the report decides.** Root CLAUDE.md's invariant "the FitReport must never return a
confident wrong singleton" is right and stays. Its four gates are the question: resolvability
on the scale-normalised Gram, a 0.4·FWHM validity radius, local-χ²_red significance, and
share-based global maturity. `report/schemas.py` carries 18 `ActionKind` members, 4
`GateCode`s, 3 `AbstentionKind`s, and `THRESHOLDS_VERSION = "1.12"` (~line 270) over a
block of constants, some of which (`WIDTH_GROWTH_*` in `sequential.py`) belong to 2003's
seam. ΔBIC's effective sample size N/f² (~lines 255–262) is rietx's own under a cited
statistic: tier the statistic 2 and the threshold on its own evidence.

**The suggestions are the report's ranking.** DESIGN.md's purpose has the report say what
was refined, how well, and what to look at next. Rule 1's second kind ranks alternatives
with their evidence and picks none. The report's suggestions are already a ranking
(`schemas.py`: "active suggestions, ranked as the report ranked them, capped"). So this WP
tiers the ranking's order and its caps, and the purpose settles whether the report
suggests at all.

**The report runs fits.** `layer2.py` (~lines 1098, 1216) and `body_misfit.py` (~line 184)
run rival fits through `fit(telemetry=False)`, which runs `_run_stage` and its holds. That
is why this waits on 2002: a gate measured against a rival fit that a hold has since
stopped altering is a different gate.

**Three screens with thresholds that are quoted, not tuned**, per root CLAUDE.md:
`background_absorption`'s R², `effective_observations`' two bands (Altomare 1995),
`background.diagnostics`' five-to-ten steps per FWHM (McCusker 1999). Tier 2 if the paper
sets the band; check the paper, since "quoted from the papers" is a claim the open could
not confirm for most constants (about 8 of 127 cite one in their comment block).

**What a demotion looks like here.** A Layer-1 statement that fails a gate today is
withheld. Demoted, the report states the number and the gate's reading ("validity radius
0.4·FWHM; this template sits at 0.7"), with what to look at next where the reading names
it (DESIGN.md § Rules, 3), and lets the caller decide. That is Rule 1's third kind, and it
is also what the v1.3 eval found agents use: seven of eight stopped on a stated criterion.
So a demotion that removes a *stated* criterion is contested by definition and goes through
`tests/eval_report_agent` before it lands (the record § A contested demotion; the spend
is approved per session). A poor result sends the explanation back for work and one more
round; the demotion lands either way.

**Fences with open WPs.** WP-1341 (a joint fit has no report) is in flight and owns the
report's *shape* for a joint fit; this WP touches no joint-fit code and no
`multi.py` reader. WP-1133 (a diagnostic names its view) adds a field to `Diagnostic`;
no conflict, but both touch `schemas/common.py`, so merge main before the schema commit.
WP-1339 (where the improvement lives) and 1335 (the report costs more than the fit) are
open under the same track; neither tiers a gate.

### Inherited

- **From WP-1977 (2026-11-01, PR #1295): `build_report`'s `min_peak_sigma` (5.0) now sets two more levels.** Layer 0's flank test (`report/layer0.on_drawn_flank`) explains a residual peak whose observed curve rises into a drawn peak, and uses that same 5σ twice: the drawn apex's prominence and the deepest observed dip allowed on the way. The default is at no declared seat, so the audit table cannot see it; tier it with the detection level when this WP seats `build_report`. The rule moved 66 `unmatched_obs` rows across twelve QPA round-robin fits and SRM 660c, and took `THRESHOLDS_VERSION` 1.13 → 1.14 on 1.12 → 1.13's precedent (a meaning moved, no constant did). A bump this WP owes starts from 1.14.
- **From WP-2003 (2026-10-26, fourth session): three sequential thresholds were removed under your version number.** `DISCONTINUITY_FACTOR` (5.0), `DISCONTINUITY_SIGMA` (3.0) and `MIN_POINTS_FOR_DISCONTINUITY` (5) went with `SEQUENTIAL_DISCONTINUITY` (2003's batch C4; the statistic is now `SeriesResult.steps`, no threshold). None is quoted by name in `report/schemas.py`'s `THRESHOLDS_VERSION` history, but the 1.9 bump treated the sequential `WIDTH_GROWTH_*` constants as covered, and every `SeriesResult.provenance` stamps `report_thresholds_version`. Nothing was bumped in 2003: fold the removal into the one bump this WP owes with the width-growth ruling, and name it in that bump's history line.
- **From WP-2003 (2026-10-26, third session, PR #1169): the width-growth ruling is yours to land, under the one `THRESHOLDS_VERSION` bump.** Ruled 2026-10-26 (`2003-batch/batch.md` C7; the maintainer delegated the rulings to the session's judgement against DESIGN.md § Rules): `SEQUENTIAL_WIDTH_GROWTH` and its suggestion are removed and the statistic becomes a record field with no threshold, since its three tier-3 constants (`WIDTH_GROWTH_FACTOR`, `WIDTH_GROWTH_GOF_FACTOR`, `WIDTH_GROWTH_SIGMA`, `sequential.py:281`, `:299`, `:305`) decide whether the code exists, on one real family (silent on CPD; fired on #451's soak, its width planted). The field carries each pattern's `rung` (clash X6: an escalated pattern's width step is a cold fit's). `_WIDTH_SUFFIXES` is tier 1, no row. Nothing was bumped in 2003; the rows in `2003-batch/rows.json` carry the ruling and name this WP. Separately, WP-2037's ask that `SeriesResult.summary` become a declared seat was not taken up in 2003.
- **From WP-2037 (2026-10-24, second session, PR #1145): a seat of yours, and the suite's alarm numbers.** `rietx.refine.Refinement.summary` is now a declared default seat owned by this WP (`_audit.DEFAULT_SEATS`), its five defaults rowed by 2037: `levels` caller-tier, `deliverable`/`plot`/`plan`/`report` answer-invariant (`tests/test_termination_view.py::test_summary_leaves_the_result_as_it_found_it`). `plan=None` skips the plan-stage veto (the free-path veto stands) and ignores the plan the last `fit()` ran (`Refinement._last_plan`, which the same summary prints as the protocol run), so a suggestion for a parameter an earlier stage freed can print as active; whether `None` should mean `_last_plan` is this WP's report decision. The generality judge also asked that `RefinementResult.summary` (and, for 2003, `SeriesResult.summary`) become declared seats: their `deliverable=`/`levels=` defaults are unseated though `print(result)` is the more-read path. `tests/suite_alarms.py` pins the eight `rietx compare` standards' firing table (`tests/data/suite_alarms.json`, written darwin/arm64, a prompt never a verdict); a retier here that moves a code's firing re-pins it with `python -m tests.suite_alarms --write`.
- **From WP-2037 (2026-10-24, first session): the response column is installed; fill it as each code is tiered.** `rietx._audit.Row` has `response` (the level the reader owes; `tests/test_audit_table.py` holds it equal to every raise site's literal `level=`), `responds` (one sentence; a `warning`'s must name a result number or a plan outcome, `rietx.purposes.RESULT_NUMBERS`/`PLAN_OUTCOMES`) and `scope` (the purposes a code with no `where` bears on, or `("all",)`). Filling a row means deleting its line from `RESPONSE_BASELINE` (253 at landing). Four rows are filled as the worked example: `FLOOR_HIT`, `PATTERN_UNDERSAMPLED` (scope `qpa, structure, microstructure, calibration`), `RESOLUTION_UNCONSTRAINED`, `SITE_SNAPPED_TO_SPECIAL_POSITION`, all with their tiers left unaudited. **20 codes raise at more than one level or at a computed one**, and 8 more through a helper `docs/reference_pages.diagnostic_index` cannot read (the list is in `test_audit_table.py`'s level test docstring); each takes a response only once split into two codes, since a level is never a threshold. WPs 2005-2007 inherit the same column. The silence-fixture registry is 2037's next item and not yet built.
- **From WP-2037 (2026-10-23, at filing): `FLOOR_HIT` on a freed extinction is a plan question, and every code this WP tiers also takes a response.** The skill's worked default on FAP (`examples/skill_worked_default.py`, `mccusker_structural`, a lab powder) frees `phases.0.extinction` and reports `FLOOR_HIT` on it at ρ = +0.057, a warning about a parameter the plan had no reason to free; whether the plan frees extinction on a Bragg-Brentano powder is this WP's to rule, not a level question. And once 2037 lands, `_audit.Row.response` (`warning`/`error`/`info`, one sentence on what the reader does) and `Row.scope` (for a code with no `where`) are filled here for each code as it is tiered, with a silence fixture per warning code; the meta-tests are 2037's.

- **From WP-2002 (2026-10-23, 9th session, PR #1113): an infinite anisotropy is quoted as 10⁶.** `report.strain` divides the broadest fitted strain width by the narrowest (`strain.py` ~390) and caps the ratio at 1e6 (~399). With WP-2002's width twin hold the instrument keeps its stage-start Y, so on CPD corundum one reflection's specimen width clips to zero and `StrainAnalysis.anisotropy` reads 1000000.0 at r² 0.079, `detected` False. The GUI shows the ratio only when `detected`, so no user saw it; `tests/test_acceptance_stephens.py` dropped its `< 6` bar, which had ridden the flat split since WP-1930. An undetected fit's ratio is noise, and a zero denominator has no ratio: `None` there, or the field withheld unless `detected`, is the honest empty state. Also: `docs/docs/reference/refinement.md` rendered at 49 9xx of its 50 000 characters after this session added `StageResult.width_twins_held` (a few table rows were tightened to fit), so the split the 8th session asked for is now owed before any further row.

- **From WP-2002 (2026-10-23, 8th session, PR #1113): two loose ends of the review.** (1) `docs/docs/reference/refinement.md`'s § Held parameters describes the start-of-stage hold and the release, never the collapse restore that `StageResult.collapsed` now records; three sentences there pushed the built twin to 50 279 characters, over `tests/test_manual.py`'s 50 000 cap, so the page needs splitting before the collapse can be explained on it. (2) `strategy.suggest.SUGGEST_SEED_ROUGHNESS` and `SUGGEST_SEED_STEPHENS` are aliases of `strategy.staged.ROUGHNESS_SEED` and `STRAIN_SEED_PPM` since B14's lift, yet keep rows of their own: the roughness one on `UNAUDITED_BASELINE`, the Stephens one at tier 3 repeating its source's evidence. They seed a suggestion's verify probe, whose own start was never measured; tier them as the probe's, or fold each into its source's row.
- **From WP-2002 (2026-10-23, 8th session, PR #1113): 2002's rows settled.** The holds the report's rival fits run are settled; `StageResult.collapsed` now tells a collapse restore from a start-of-stage hold, which `PHASE_UNCONSTRAINED`'s message could use. This WP still waits on 2003.

- **2026-10-23, from [1341](1341-a-joint-fit-has-no-report.md) (closed): the joint report's open work is now WP-2028's.** This WP's fence (Context, "Fences with open WPs") and its Non-goals row "The joint-fit report: 1341" name a WP that closed today. What 1341 left open, the joint fit's guards reading every histogram's table, a hold made in some patterns, WP-1523's test on the joint path and fit-level findings beside their histogram, is [2028](2028-a-joint-fits-guards-see-every-histogram.md)'s. 2028 carries the tier-3 and `THRESHOLDS_VERSION` rule this WP sent 1341 on 2026-10-18. The fence stands with 2028 in 1341's place.
- **From WP-2002 (2026-10-22, 6th session, PR #1085): the report reads two models.** `report._reading_models` takes Layer 1's misfit from a model at the closing stage's precision and the shapes it is fitted with (the derivative bases, and the windows the texture screen shares a point's misfit over) from a twin at `WINDOW_AREA_TOL`, compiling whichever the caller's model is not (4-19 ms against a 0.24-1.57 s report). `build_report` takes `instrument=` beside `structure=` for it, and without both reads the one model as before. It is a heuristic of this WP's subsystem with no table row (an ordering of two compiles, keyed on `CompiledModel.window_area_tol`). Measured while choosing it: shapes at the closing precision read an impurity as texture (0.35) and lost zero shift from displacement (the closing FCJ rule's asymmetry column beside 90°, |cos| 0.9986 with position); a misfit at the declared precision sent a displaced specimen to axial asymmetry (that rule leaves 5.6e-3 of a peak's maximum). Every report before WP-2002 read a declared-precision model against real data, so the second misreading was latent on real fits, unmeasured.
  *7th session (2026-10-22).* `build_report` now refuses a non-Pawley `model=` without `structure=` and `instrument=` (`TypeError` naming them), so the one-model reading is gone. A fit run with `closing_window_tol=None` keeps its misfit read at the closing precision: on the fluorapatite and cpd-1a fitted that way, both readings printed the same report, passed the same regions with the same leading shape and suggested nothing (WP-2002 `rulings.md` § Ninth round). The two-model reading is still a heuristic of this WP's subsystem with no table row.

- **From WP-2002 (2026-10-21, 4th session): tier 2 names seven programs.** `docs/milestones/generality.md` § The rule's tier 2 now reads "by default in an established Rietveld program": GSAS-II, FullProf, TOPAS, RIETAN-FP, BGMN, MAUD and EasyDiffraction, the list rietx-bench runs (the maintainer's instruction). A row resting on a program default names the programs it checked and what each does; a program doing otherwise by default is a dissenter, one without the feature is neither. What each does on peak windows, staging, roughness starts, width limits, dispersion, solver, mode and background seed is in `docs/practice.md`; where each program's manual or source sits is in the maintainer's memory (`foreign-code-sources-on-disk`), and rietx-bench's `tools/` holds BGMN, MAUD, RIETAN-FP and EasyDiffraction's environment beside GSAS-II and FullProf.
- **From WP-2002 (2026-10-20, PR #1050): `Statistics.esd_inflation` is not the factor the esds carry.** It re-measures the Bérar-Lelann f at the result's own compile, while the esds carry the f of the solve's last residual (now `LSQOutcome.esd_inflation`; on any row it is `RefinedParameter.stderr / stderr_uncorrected`). Measured 2026-10-20: 0.07 % apart on NAC Rietveld, 0.75 % on NAC Le Bail, 4 % on a joint fit weighted 1:4. Two readers treat it as the applied factor: the CIF exporter (`io/exporters.py:458-461`, "multiplied by") and `examples/srm660c_lab.py:96`. Making the statistic the solve's factor moves the profile-interval cut and `solve_magnetic`'s N/f² count slightly; the maintainer has not ruled.
- **From WP-2002 (2026-10-20, PR #1050): `report.layer2.predict_then_verify` runs on `_trial()`.** It used `branch()`; the change keeps a rival fit from paying the automatic moment-angle interval, and the trial leaves no history node.
- **From WP-2001 (2026-10-19, PR #1047).** The table is `src/rietx/_audit.py`; this WP's rows are the ones `_audit.WALKED` and `_audit.DEFAULT_SEATS` map to 2004, plus the codes and suggestion rows of its subsystem. Auditing a row means giving it a tier and evidence in place and deleting its line from `UNAUDITED_BASELINE`; `tests/test_audit_table.py` fails until both are done. The walk sees module-level numbers and tuples of numbers only, so a number held in a dict, list or array is audited here by hand: `report.texture._R_GRID` is one.

- **From WP-2002 (2026-10-19, PR #1050).** 2002's batch class B13 proposes handing 15 rows to this WP, pending the maintainer's ruling: seven `background.diagnostics` constants that feed `diagnose()`'s fields and no code (`COVERAGE_*`, `CUTOFF_*` except `CUTOFF_MIN_DEG`), the four `optimize.identifiability` report caps, `refine.MAGNETIC_TICK_PURITY` (its comment at `refine.py` ~768 disagrees with its code at ~7020), and `optimize.statistics.EFFECTIVE_OBS_ALPHA`, `OBS_PER_PARAMETER_MIN` and `OBS_PER_PARAMETER_PREFERRED`. The table: `2002-batch/batch.md` § The B13 hand-off table.

- 2026-10-31, from the issue triage (issue #1212): the width-growth record
  field C7 asks for has the blind spot of the code it replaces. On a synthetic
  chain where a vanishing minor phase broadens into an unmodelled broad
  component (LaB6 plus a cubic perovskite whose lines sit within 0.3 % of
  LaB6's, the issue's script), its `lor_strain` grows from 0.041(7) to
  4.53(2.29), 110×, while GoF rises 1.00 → 2.98 and its fraction climbs to
  18.8 wt % against a truth of 0. `SEQUENTIAL_WIDTH_GROWTH` stays silent
  because the growth test asks for more than 3 combined esds (4.49 < 3 ×
  2.29), and a runaway width is a flat direction whose esd grows with it. A
  slightly weaker phase at the start also fails the reference test (value >
  3σ), and the trajectory is then not judged at all. Checked against the tree
  at d87c8cc91 (`[dev]`, macOS arm64): the issue's script reproduces its table
  to the printed digits, and the series codes are
  `SEQUENTIAL_PERSISTENT_FINDING`, `SEQUENTIAL_RESEED`,
  `SEQUENTIAL_RWP_OUTLIER`, with no width-growth finding. Both tests are in
  `sequential._width_growth_diagnostics` (~line 2671: the reference's
  `value[k] > WIDTH_GROWTH_SIGMA * sd[k]`, the growth's `grown >
  WIDTH_GROWTH_SIGMA * combined`). The issue proposes, for this WP's field:
  take the reference as the first finite positive width and record whether it
  was measured, rather than skipping an unmeasured one; carry the width ratio
  and the GoF ratio as the primary columns, and the growth in esds as a
  secondary column with the note that a runaway width's esd grows with it. It
  reports that WP-1465's survey has no existing series pass GoF 1.14 against
  its first pattern, so relaxing the reference should move nothing on the
  suite; that needs a re-count on the tree. It also measured three default
  width bounds (physical limits, the flag thresholds as bounds, a ±10 % band
  per pattern) and agrees with 2003's B9 ruling that none should be a default:
  each either misses the case or clips a real 2-3 nm phase.

- 2026-10-31, from the issue triage (issue #1215): the issue asks for no
  change to `too_stiff` beyond printing the analytic null beside the
  off-region pair (text only, carried by the new residual-structure WP). It
  measured `too_stiff` silent on a hump of 0.1, 0.3 and 0.6 × mean background
  and firing at 1.2 × on a synthetic capillary family, where the fitted
  background's bulge above its own hull read 2.3 / 9.8 / 41 / 82 %. Not re-run
  here.

## Non-goals

- The holds the rival fits run: 2002.
- The width-growth thresholds' *rulings*: 2003 measures, this WP bumps the version.
- The joint-fit report: 1341.
- `Diagnostic` codes raised outside `report/` (`refine.py`'s 61): 2005.
- A new Layer-1 template or a new action kind.

## Tasks

- [ ] Inventory: one row per gate, action kind, abstention kind, template and constant
      under `THRESHOLDS_VERSION`, with what it withholds or asserts and what the caller
      sees without it.
- [ ] Tier each row per part; for the three quoted screens, open the paper and record
      whether it sets the band or the band is ours.
- [ ] Register and run the `eval_report_agent` round for the contested demotions
      (`tests/eval_report_agent/PROTOCOL.md` § Episode validity: expected answers checked
      against the data first), after the maintainer approves the spend. Where agents do
      worse, rework the number's explanation and run once more; the demotion is not held.
- [ ] The clash table: gates that read the same misfit, the background screen against the
      Layer-0 peak-cluster regions (WP-1055), abstention against maturity.
- [ ] The batch to the maintainer, each brief opening with its stakes line (the record
      § The rule, 2026-10-20); rulings dated into the table.
- [ ] Approved demotions; the `THRESHOLDS_VERSION` bump once, with 2003's rulings folded
      in; the eval fixtures that pin the version updated in the same commit.
- [ ] Goldens re-pinned only if no further from reference; the FAP report golden and the
      slow NAC golden regenerated once, on the final tree.
- [ ] A refused `allow` is reported, never dropped (ruled by the maintainer 2026-10-24,
      `docs/milestones/generality.md` § The rule, clause 4). A caller's `levels=` map keeps
      errors unlowerable, but today an `allow` on a diagnostic raised as an error is ignored
      in silence. `schemas.results.diagnostic_view` gives that row `override=None`, and
      `_diagnostic_header` counts only the rows a map set. Report it in the diagnostics
      header beside "N set by levels=" (for example "1 allow refused: an error stays an
      error"), in the three `summary()` methods and in `usable_under`'s docstring. A test
      covers an `allow` on `MODEL_FAR_FROM_DATA`. The low-count case that makes this matter
      (Rwp > 0.8 on a well-fitted pattern averaging under about 1.6 counts a channel,
      inferred) is that code's threshold, which WP-2005 owns.
- [ ] Tests + PNGs; the fast count moved by exactly the tests added.
- [ ] Skill: none here. List each `references/judging.md` (5 546 words) and
      `diagnostics-reading.md` row that names a demoted gate, for 2008 (DESIGN.md § Rules,
      3; the record § Decisions, the skill's role).

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_audit_table.py -q          # no report/ row at unaudited
.venv/bin/python -m pytest tests/test_fitreport_layers.py tests/test_report*.py tests/test_localisation.py tests/test_body_misfit.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m pytest -n auto --dist loadgroup                # once, final tree
```

The handover carries the eval round's cells (registered first, reported split where
split) and the version bump's diff.

## References

- `docs/milestones/generality.md`; WP-1055, 1069, 1071, 1072, 1076, 1118 (the gates'
  history); 1303 (the v1.3 eval); 1985 (the explanations).
- Altomare, A. et al. (1995). J. Appl. Cryst. 28, 738–744; McCusker, L. B. et al. (1999).
  J. Appl. Cryst. 32, 36–50; Kass & Raftery (1995); Schwarz (1978).

## Handover log

- **2026-10-18** — created, from the milestone's opening session. 1341, 1339, 1335 and
  1133 are open under the report; none tiers a gate, and the fences above say what each
  owns.
