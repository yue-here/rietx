# WP-2005 rulings on the part-2 batch, 2026-11-21

A ghostshift runner worked through the 31 codes in `batch.md` on 2026-11-21, at `origin/main`
`c1033a0e8`. The maintainer had asked for each item to be checked against the design rules,
ruled where the call is clear, and brought to him only where it needs his judgement. Nothing
here was approved by the maintainer when this record was written (2026-11-21); the outcomes were added on 2026-11-22. No row of `src/rietx/_audit.py` changed, and no code,
level, text or threshold changed.

The premise was checked first. All 31 codes are still `unaudited` in `_audit.ROWS`. No ruling
on them is in the WP's handover log, in `docs/milestones/generality.md` § Decisions or in the
git log since the batch merged (#1638). Two facts in the batch were wrong and are corrected
below. McCusker et al. (1999) is held on this machine, so `PATTERN_UNDERSAMPLED` and
`DATA_SUPPORT_LOW` no longer wait on reading it. And the half of sin θ_min under
`ROUGHNESS_OUTSIDE_REGIME` is the turnover of Pitschke's own formula, not a number of rietx's.

Each item is in one of four groups.

- **Settled by Claude** (9). A written rule, a ruling or a measurement settles it. Each line
  names the grounds and the choice a reviewer could have made instead.
- **Consent lines, answered 2026-11-22** (19). A written rule gave the call to the maintainer,
  and the call was clear. Two rules do this here. Any change to what a fit hands a reader goes
  to him (ruled 2026-11-01), and so does every tier-3 approval (§ The rule). Each line reads "I
  will X because Y, unless you object". Seventeen were settled by Claude and checked blind;
  two (`MODEL_FAR_FROM_DATA`, `PHASE_UNCONSTRAINED`) were ruled by Yue, who answered "All as
  recommended".
- **Full brief, answered 2026-11-22** (1). `HIGH_CORRELATION`, below.
- **Not Yue's** (2). The magnetic codes are Mike's to rule (#1075, 2026-11-04). The question
  was posted on 2026-11-22.

Two rulings of the maintainer's decide most of the class-A rows. On 2026-11-04 (WP-1944,
ruling 3) he removed `EXTINCTION_UNDECLARED`, a warning read off the residual that suggested an
opt-in correction. On 2026-11-03, 11-04 and 11-16 he reversed three thresholded warnings or
actions over a fit metric, and chose "a field, and the caller decides" each time. § Demotion
then fixes the shape. Where the threshold decides whether a code fires, the code goes and its
number stays in a record field.

## Settled by Claude, 2026-11-21

Each is "settled by Claude under <grounds>, 2026-11-21". The alternative follows.

| Code | Ruling | Grounds | Alternative a reviewer could pick |
|---|---|---|---|
| `BACKGROUND_ABSORPTION` | Q1 and `BACKGROUND_ABSORPTION_GUARD` (R² 0.25) go to the maintainer together, after a three-family measurement | the mechanical ground needs three unrelated families, and the constant's docstring names none | approve at tier 3 on the docstring's ranges |
| `ROUGHNESS_ABSORPTION` | measure R² 0.9 on three roughness families first | mechanical ground; one synthetic pattern on disk; roughness on Bragg-Brentano lab data is not a rare feature | tier 3 now under "where three families do not exist" |
| `HUMP_TOO_NARROW` | measure 4× instrumental FWHM on three families, with an injected collapsed hump as the known truth | the rare-feature clause names magnetic, Stephens strain and TOF; amorphous humps are common in capillary and amorphous-content data; a flag's truth can be injected on any family (§ The rule, *Holds*) | tier 3 now as a rare feature (the batch's proposal) |
| `PATTERN_DEAD_CHANNELS` | tier `background.diagnostics.DEAD_*` on three detector families first, then the code | mechanical ground; the constants are unaudited and record no family | approve the code row alone at tier 1 |
| `FROZEN_COMPILE_STALE` | re-measure the 1e-2 gap under today's defaults before approval | the 358 fits behind it ran on 2026-09-23 (`420855515`), before staged plans stopped converging intermediate stages (WP-2045) and before the closing stage went off by default (WP-2222, 2026-11-19); both change how far the last stage moves from its frozen compile | approve on the 358 fits, as the batch proposes |
| `PAWLEY_OVERLAP_UNRESOLVED` | measure 0.3 on three families, or find a program default, before tiering | tier 2 needs a citation that tested the number or a program default; "I > 3σ(I)" is a crystallographic convention, recalled and not checked in any program, and 0.3 is I/σ ≈ 3.3, outside a 2σ-3σ range | tier 2 now at 1/3 on the 3σ convention |
| `RESOLUTION_UNCONSTRAINED` | code row tier 2 on McCusker et al. (1999) § 5, Synchrotron | the paper names the failure (U, V, W unconstrained on predominantly Lorentzian data) and the remedy (constrain or fix), read in the paper on 2026-11-21; "predominantly" is a majority, so the test has no free constant (`staged.check_resolution_supported`'s docstring); no change to what the standard fit prints | tier 3 for the one-half, as a factor of rietx's own |
| `SPECIES_FALLBACK_NEUTRAL` | survey what the programs do with an untabulated ion, then tier the fallback and the code together | tier 2 must name the programs; the fallback is a default action the table cannot yet see; the 2026-11-21 look at GSAS-II 5.8.4's `GetFormFactorCoeff` was not conclusive | tier the code at 1 now and leave the fallback unseen |
| `PATTERN_UNDERSAMPLED` | tier `SAMPLING_HEIGHT_FRACTION` and `SAMPLING_PROMINENCE_SIGMA`, then the code; the paper is not a blocker | McCusker et al. (1999) § 2 is held (Zotero) and says "at least five steps … across the top of each peak", which confirms `STEPS_PER_FWHM_MIN`'s tier 2 | wait for the paper, as the batch proposes |

Two of the batch's questions are settled as well.

- **Question E** (the convention). A code stating a tiered threshold's outcome is tier 1 for its
  own part, and the threshold keeps its row. A code voicing the package's own act is tier 3.
  The grounds are § The rule's first paragraph, which tiers the statistic, the threshold and
  the action separately, and two approved precedents (`CELL_RUNAWAY`, 2026-10-19;
  `SEQUENTIAL_UNRECOVERED`, 2026-11-03). So `ABSORPTION_MU_R_OUT_OF_RANGE` and
  `BRINDLEY_OUTSIDE_REGIME` move from tier 2 to tier 1 in the next session, and their
  thresholds' tier-2 rows stay. The alternative is to let a code inherit its threshold's tier.
- **Question F** (responses). Yes, a response falls under the 2026-11-01 reader-output ruling.
  It changes what `summary()` prints for every fit that raises the code (§ The rule,
  *Attention is a cost*, clause 3), so the 23 come in one batch, each with its silence pair. The
  alternative is to give them responses without asking.

## The consent lines, answered 2026-11-22

Answered 2026-11-22 under the maintainer's routing rules of that day (WP-2238): each item was
settled by Claude and checked by a fresh agent that did not see the pick, or brought to the
maintainer, who answered "All as recommended". The outcome of each line is in its last column.
Every line changes what a reader of some fit receives, or asks for a tier-3 approval.

| Code | Consent line | Departs from `batch.md`  Outcome |
|---|---|---|---|
| `SIZE_UNUSUALLY_SMALL` | I will remove the code because its 5 nm threshold comes from one archive (one family), decides whether it fires, and the size is already in `RefinementResult.microstructure`, unless you object. | no; PR #1477 edits its text, so this lands after #1477 or drops that edit | **Settled by Claude 2026-11-22, checked blind:** remove the code, as proposed; the size stays in `RefinementResult.microstructure`. Grounds: the maintainer's rulings of 2026-11-03 and 2026-11-16 ("a field, and the caller decides"). |
| `STRAIN_UNUSUALLY_LARGE` | I will remove the code for the same reasons (`STRAIN_FLAG_WIDTH` 1.5, one archive), unless you object. | no; same note on #1477 | **Settled by Claude 2026-11-22, checked blind:** remove the code, as proposed. Grounds: the maintainer's rulings of 2026-11-03 and 2026-11-16 ("a field, and the caller decides"). |
| `BISO_UNUSUALLY_LARGE` | I will make it `info` at tier 2 because the Lindemann limit is cited (Gilvarry 1956) and a refiner of a rattler or superionic site quotes the Biso anyway, unless you object. | no | **Settled by Claude 2026-11-22, checked blind:** `info` at tier 2, as proposed. Grounds: the maintainer's rulings of 2026-11-03 and 2026-11-16 ("a field, and the caller decides"). |
| `RESTRAINT_TENSION` | I will remove the code because its 3σ threshold is rietx's own and decides whether it fires, while `RestraintReport` already carries each restraint's `deviation_over_sigma`, unless you object. | yes: the batch kept it as `info` | **Settled by Claude 2026-11-22, checked blind:** remove the code, as proposed; `deviation_over_sigma` stays on `RestraintReport`. Grounds: the maintainer's rulings of 2026-11-03 and 2026-11-16 ("a field, and the caller decides"). |
| `LOW_ANGLE_UNMODELLED` | I will remove the code and its suggestion because it is a residual-read warning on a threshold measured on one pattern (the family you reversed three times), and issue #1219 found three competent responses; its statistic becomes a record field, built in the same change, unless you object. | yes: the batch kept it as `info` without the suggestion | **Settled by Claude 2026-11-22, checked blind:** remove the code and its suggestion, as proposed; its statistic becomes a record field in the same change. Grounds: the maintainer's rulings of 2026-11-03 and 2026-11-16 ("a field, and the caller decides"). |
| `AIR_SCATTER_UNDECLARED` | I will remove the code entirely because it has the shape of `EXTINCTION_UNDECLARED`, which you removed on 2026-11-04: a warning, read off the residual, that a term was not declared. It fired on 20 of 20 clean patterns (#1215), and in WP-2017 declaring the term moved the answer by 0.049 esd (#1577). Findability stays with the help entry and the manual, unless you object. | yes: the batch kept it as `info` naming both causes | **Settled by Claude 2026-11-22, checked blind:** remove the code, as proposed. Grounds: the maintainer's rulings of 2026-11-03 and 2026-11-16 ("a field, and the caller decides"). |
| `EXTRA_PEAK_ON_REFLECTION` | I will make it `info` because a refiner modelling a shoulder or a stacking-fault peak at a Bragg position quotes the fit anyway; its 0.08° tolerance is WP-2004's row, and if that row ends tier 3 the code follows § Demotion to a field, unless you object. | no | **Settled by Claude 2026-11-22, checked blind:** `info`, as proposed; it follows WP-2004's row for the 0.08° tolerance. Grounds: the maintainer's rulings of 2026-11-03 and 2026-11-16 ("a field, and the caller decides"). |
| `ROUGHNESS_UNCONSTRAINED` | I will keep the warning only where a Suortti block ended exactly at an off state (the scale and Biso esds then differ ×1.1 to ×4.4 between the two off states), and move the "under 1 % depression" case to a field holding the largest depression, unless you object. | yes: the batch made the whole code `info` | **Settled by Claude 2026-11-22, checked blind:** keep the warning only where a Suortti block ended exactly at an off state, and move the "under 1 % depression" case to a field, as proposed. Grounds: the maintainer's rulings of 2026-11-03 and 2026-11-16 ("a field, and the caller decides"). |
| `HARMONIC_FRACTION` | I will remove the code because the fraction is a refined parameter, already reported with its esd, and its 15 % warning fails Q1 for a detuned monochromator; you ruled on 2026-11-03 that a line restating a number the reader already inspects is noise, unless you object. | yes: the batch proposed one `info` record | **Settled by Claude 2026-11-22, checked blind:** remove the code, as proposed. Grounds: the maintainer's rulings of 2026-11-03 and 2026-11-16 ("a field, and the caller decides"). |
| `HARMONIC_ABSENT` | I will remove it with `HARMONIC_FRACTION`, for the same reason, unless you object. | yes | **Settled by Claude 2026-11-22, checked blind:** remove it with `HARMONIC_FRACTION`, as proposed. Grounds: the maintainer's rulings of 2026-11-03 and 2026-11-16 ("a field, and the caller decides"). |
| `DISPERSION_NEGLECTED` | I will make it one `info` record, with no threshold, stating the largest change in \|f\|² per element, because the root CLAUDE.md says `dispersion = None` "says so through `DISPERSION_NEGLECTED`", and the 2 %/5 % split is a threshold between levels, unless you object. | no | **Settled by Claude 2026-11-22, checked blind:** one `info` record with no threshold, as proposed. Grounds: the maintainer's rulings of 2026-11-03 and 2026-11-16 ("a field, and the caller decides"). |
| `ABSORPTION_THICKNESS_MATTERS` | I will remove the code because `FLAT_PLATE_BIAS_MIN` (0.05 Å²) decides whether it fires and `AbsorptionCorrection.equivalent_delta_biso` already holds the number, unless you object. | yes: the batch offered approving the threshold | **Settled by Claude 2026-11-22, checked blind:** remove the code, as proposed; `equivalent_delta_biso` holds the number. Grounds: the maintainer's rulings of 2026-11-03 and 2026-11-16 ("a field, and the caller decides"). |
| `ABSORPTION_PLATE_THICKNESS` | I will remove the code and its inline 0.7 because `AbsorptionCorrection.intensity_fraction_of_optimal` already holds the number, unless you object. | the batch offered this as one of two options | **Settled by Claude 2026-11-22, checked blind:** remove the code and its inline 0.7, as proposed; `intensity_fraction_of_optimal` holds the number. Grounds: the maintainer's rulings of 2026-11-03 and 2026-11-16 ("a field, and the caller decides"). |
| `NEUTRON_RESONANT_ABSORBER` | I will split it into `NEUTRON_RESONANT_ABSORBER` (`info`, a complex b, tier 1) and `NEUTRON_STRONG_ABSORBER` (warning, Cd, Eu, Sm and Gd, tier 1). These are two consequences, and the 1000 barn line sits in a gap in the shipped table, from Yb's 34.8 to Cd's 2520, so no resonant absorber lies near it, unless you object. | proposes the second name | **Settled by Claude 2026-11-22, checked blind:** split into `NEUTRON_RESONANT_ABSORBER` (`info`) and `NEUTRON_STRONG_ABSORBER` (warning), both tier 1, as proposed. Grounds: the 1000 barn line sits in a gap in the shipped table (Yb 34.8 to Cd 2520), so the element set is a fact of the table, not a tuned threshold. |
| `ROUGHNESS_OUTSIDE_REGIME` | I will split it and keep both halves: `ROUGHNESS_OUTSIDE_REGIME` (warning, sin θ_min < τ, tier 2 on Pitschke Eq 18) and `ROUGHNESS_PAST_TURNOVER` (`info`, τ < sin θ_min < 2τ, tier 1), because u(1 − u) peaks at u = ½, so the half is the formula's turnover (`RoughnessPitschke`'s docstring), unless you object. | yes: the batch dropped the `info` band as rietx's own | **Settled by Claude 2026-11-22, checked blind:** split into `ROUGHNESS_OUTSIDE_REGIME` (warning, tier 2) and `ROUGHNESS_PAST_TURNOVER` (`info`, tier 1), as proposed. Grounds: the maintainer's rulings of 2026-11-03 and 2026-11-16 ("a field, and the caller decides"). |
| `DATA_SUPPORT_LOW` | I will split it into `DATA_SUPPORT_LOW` (warning, under three reflections per parameter) and `DATA_SUPPORT_BELOW_PREFERRED` (`info`, three to five), both tier 2 on McCusker et al. (1999) § 9, "at least three and preferably five" (read 2026-11-21), unless you object. | proposes the names; WP-2004 still tiers the two constants | **Settled by Claude 2026-11-22, checked blind:** split into `DATA_SUPPORT_LOW` (warning) and `DATA_SUPPORT_BELOW_PREFERRED` (`info`), both tier 2 on McCusker et al. (1999) § 9, as proposed. Grounds: the maintainer's rulings of 2026-11-03 and 2026-11-16 ("a field, and the caller decides"). |
| `LEBAIL_ALTERNATION_STOPPED` | I will make it one `info` record naming why the opt-in passes stopped, because all three stop reasons rest on an Rwp change (`LEBAIL_CONVERGED_REL`), the family you reversed, and the kept pass is the best, unless you object. | no | **Settled by Claude 2026-11-22, checked blind:** one `info` record naming why the passes stopped, as proposed. Grounds: the maintainer's rulings of 2026-11-03 and 2026-11-16 ("a field, and the caller decides"). |
| `MODEL_FAR_FROM_DATA` | I will tier the code row 3, citing its threshold's approval (2026-10-19) and the series quarantine its error level drives (WP-2003 C2 Q5), with the failing case written in: a correct model of flat Poisson data reads Rwp above 0.8 below about 0.65 counts per step under rietx's √max(y,1) weights (simulated 2026-11-21: 0.81 at 0.6, 0.77 at 1.0, 0.73 at 2.0), unless you object. | adds the measured case, which the judge had derived as 1-2 counts and which is lower | **Ruled by Yue 2026-11-22:** tier 3 approved, dated 2026-11-22, with the low-count failing case written in ("All as recommended"). |
| `PHASE_UNCONSTRAINED` | I will tier the code row 3 on the absent-phase hold's approval (2026-11-04), as `CELL_RUNAWAY` carries its clamp's, unless you object. | no | **Ruled by Yue 2026-11-22:** tier 3 approved, dated 2026-11-22 ("All as recommended"). The grounds cite the maintainer's approval of the absent-phase hold (2026-11-04) directly: `CELL_RUNAWAY`'s row cites its own ruling (B8, 2026-10-19), not its clamp's, so the precedent stated in the consent line was wrong (the blind check found this). |

## `HIGH_CORRELATION`, answered 2026-11-22

Answered 2026-11-22 under the maintainer's routing rules of that day (WP-2238): each item was
settled by Claude and checked by a fresh agent that did not see the pick, or brought to the
maintainer, who answered "All as recommended". **Ruled by Yue 2026-11-22:** deferred. The
demotion waits for one agent run on `tests/eval_report_agent` after WP-2008 rewrites skill
rule 7, so one spend measures this demotion and WP-2003's contested one together. The pick
flips if the warning is found causing harm in fits today. The brief below is as written on
2026-11-21.

**The decision.** Should `HIGH_CORRELATION` stop being a warning? It goes to you because two
written instructions conflict. Body rule 7 of the agent skill tells an agent to act at the
threshold: "Above a correlation of 0.98 (`HIGH_CORRELATION`), fix one member or extend the
range." The record's judgement ground keeps a warning only where every competent refiner
would act, and the batch names one who would not.

**Why it matters.** After each fit, rietx takes the correlation of every pair of refined
parameters from the covariance matrix that the esds come from. When a pair exceeds |ρ| 0.98
(`schemas.plan.CORRELATION_GUARD`, rietx's own number, unaudited), it prints a warning naming
the pair. A warning means "act before you quote a result number" (§ The rule, *Attention is a
cost*, clause 2). It is the loudest code in the package. Over the eight `rietx compare`
standards it is 44 % of all warning rows. On cpd-1a under `qpa` it is 24 of the 49 printed
warnings (WP-2037, darwin arm64). 37 test functions name it. A cell correlated at 0.99 with
the zero shift is normal on one pattern without an internal standard, and today it reads as a
fault. An esd from the full covariance already carries the correlation: two correlated
parameters come back with large esds, not wrong values. Fixing one member gives the other a
smaller esd that is only right if the fixed value is right. If we demote wrongly, an agent
quotes a value whose large esd it must then read. If we keep it wrongly, readers learn to skip
warnings, and each fit's real warnings sit among the correlation rows. Importance: moderate.

**Aim.** The fifth aim, attention is a cost, for every reader of a fit, human or agent. Also
the agent-first thesis: an agent weighs numbers better than it obeys a fixed rule.

**Options.** Dropped: raising the threshold to 0.99, a retuned number of the kind you have
reversed three times.

- (a) Make it `info` now. `FLAT_DIRECTION` stays the warning for a direction the data do not
  determine at all. Rule 7 is rewritten as vocabulary under WP-2008 (the skill carries
  vocabulary and sourced traps, nothing prescriptive; generality.md § Decisions, 2026-10-18).
  Cost: a level change, a help sentence, a release note and a skill edit. It can be undone.
  Not measured: how many tests assert the level.
- (b) As (a), but register one agent run on `tests/eval_report_agent` first. § The rule asks
  for that before a *contested* demotion lands, and a poor result sends the explanation back
  rather than holding the demotion. Cost: an eval spend you approve per session, not priced
  here.
- (c) Keep a warning, scoped by purpose. The response is `warning`, but it counts only under a
  deliverable whose paths the pair touches. A cell–zero pair warns under `cell` and not under
  `qpa`. Cost: a response and a silence pair. It still claims that every refiner acts before
  quoting a cell.
- (d) Do nothing. The code stays an unaudited warning on the baseline.

**Practice.** From `docs/practice.md` § Correlations (sources read for WP-2050) and McCusker et
al. (1999), read 2026-11-21:

- GSAS-II 5.8.4 lists the pairs above max(0.95, 0.99 × the largest) in its log and asks for no
  act.
- TOPAS v9 gives the matrix (`C_matrix_normalized`) and flags nothing.
- FullProf 8.20 writes the matrix on request, and its manual advises refining separately any
  pair above about 50 %.
- McCusker et al. put the covariance matrix in their list of checks for a refinement that is
  going badly: "it may not be sensible to refine both".
- RIETAN-FP, BGMN, MAUD and EasyDiffraction were not checked.

No program checked warns on every fit. The advice to act applies to a refinement in trouble,
and other codes already report that case (`FLAT_DIRECTION`, `STAGE_MAX_ITER`, `BOUND_HIT`). The
skill's rule 7 is stricter than any program checked.

**Recommendation.** (a), a lean. The crux is whether a high correlation alone, with an honest
esd, is something every refiner acts on before quoting. Practice says no. (c) loses there: a
GSAS-II user quotes the cell beside a correlated zero under the `cell` purpose too. (b) costs
a spend, and the run would test the skill's wording rather than the level. A run showing
agents land further from the reference values after the change would flip me to (c).

## Not Yue's: the magnetic codes

`MAGNETIC_WIDTH_MOVED_MOMENT` and `STAGE_FREES_MAGNETIC_WIDTH_WITH_MOMENT` are Mike's to rule
(#1075, 2026-11-04). No "Ruled by Mike" was found on either in WP-1343, WP-1418, WP-1929 or
WP-2004. The question goes to Mike on #1075. **Ruled by Yue 2026-11-22:** posted
(https://github.com/yue-here/rietx/issues/1075#issuecomment-7078724635), with a third question
added on `SEQUENTIAL_MOMENT_ONSET` (WP-2081). Draft as first written:

> WP-2005 asks two magnetic questions. (1) `MAGNETIC_WIDTH_MOVED_MOMENT` warns when freeing
> the magnetic width moves a released moment by more than 1 esd
> (`report.schemas.MAGNETIC_WIDTH_MOMENT_SHIFT_SIGMA`). Would every competent refiner act on
> that before quoting the moment? If so, is 1 esd a number you would approve at tier 3, and on
> which families? (2) `STAGE_FREES_MAGNETIC_WIDTH_WITH_MOMENT` warns when one stage frees the
> magnetic width with the moment it first frees. A refiner with a strong magnetic signal
> frees both at once. Should it stay a warning, become `info`, or go? (Claude wrote this
> question.)
