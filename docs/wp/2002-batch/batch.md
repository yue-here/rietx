# WP-2002 decision batch: what one fit decides for the caller

This batch asks your rulings on the 247 rows of WP-2002 that still need one. WP-2002 is
the audit of every automatic action a single refinement takes. Six readers proposed a tier
for every row, and 157 rows that needed no approval are already in the audit table
(`src/rietx/_audit.py`). The batch follows the record's order (`docs/milestones/generality.md`
§ The order). This pass asks only the judgement ground: shown the statistic, would every
competent refiner take this action? The mechanical ground asks whether a threshold holds on
three unrelated dataset families. It is measured afterwards, and only for the thresholds of
actions that survive this pass. The rows fall into 16 classes. Eight need a real judgement:
B3, B4, B5, B8, B9, B10, B12 and B14. Five ask you to confirm that an action passes, so that
its threshold goes to the second pass: B1, B2, B7, B11 and B16. Three are plain: B6, B13 and
B15.

*How this was made.* Six readers proposed a tier for every row (`inventory.json` beside this file). One agent drafted the classes and checked the readers' claims. A second, fresh-context agent drafted the case against each class. The lead session corrected the sentences the review found wrong and wrote a revised pick after each review. Where the two picks differ, the revised one is the recommendation. The clash candidates are in `clashes.md`, unmeasured.

**Vocabulary.** Tier 1 is physics or arithmetic. Tier 2 is established practice: a
validating citation, or the same action taken by default in GSAS-II, FullProf or TOPAS.
Tier 3 is rietx's own, kept only with your dated approval. "Invariant" is the record's fourth
class: the setting changes cost and leaves the accepted answer alone, and a test asserts
that. "Caller" marks an action only the caller can turn on. A failed action is demoted to
its kind of ambiguity (DESIGN.md § Rules, 1). Kind 2 ranks the alternatives with their
evidence and picks none. Kind 3 reports the number with its meaning and stops. A row marked
* is a hand row, which the table's walk cannot see (B14). `rows.json` beside this file gives
every row's class, proposed tier, kind and demotion.

| Class | Rows | What you decide | My pick |
|---|---|---|---|
| B1 Absent-phase hold | 4 | Confirm it passes | Pass; 3σ to the second pass |
| B2 Magnetic moment actions | 11 | Confirm under the rare-feature clause | Pass |
| B3 Seeds | 7 | Where a floored parameter starts | Test roughness for invariance; keep strain at GSAS-II's value |
| B4 Bérar-Lelann esd inflation | 3 | Keep multiplying every esd? | Demote to a reported factor |
| B5 σ handling | 3 | What a zero esd becomes | GSAS-II's rule, inside WP-1952 |
| B6 Anomalous dispersion | 1 | Plain | Keep, tier 2 |
| B7 Default plan, stage tolerance | 7 | Confirm; invariance test | Plan passes; tolerance by test |
| B8 Bounds on every fit | 21 | Cell window, cell clamp, 2 nm size floor | Remove the inert window; keep the clamp; drop the 2 nm floor |
| B9 Defaults inside opt-in features | 21 | One reading; two assumed instrument facts | Boxes kept while reported; record assumptions |
| B10 Numerical settings | 32 | How the rule reads for a quadrature | Tier 1 only with a domain-wide test |
| B11 Stop rules | 8 | Le Bail cycle count | Converge with a cap, in WP-1542 |
| B12 Pick and opt-in verbs | 45 | Three verbs | Evidence travels; fix magnetic ΔBIC; demote one warning |
| B13 Hand-off | 58 | Send to 2004, 2005, 2007 | Send |
| B14 Hand rows | 21 (+70) | How unseen rows enter | Lift what can drift; list the rest |
| B15 Assumed magnetic ion | 2 | Split by element | Keep lanthanides; refuse actinides |
| B16 Bound test | 3 | Plain | Pass; third family in the second pass |

---

## B1. The absent-phase hold, its release and the collapse restore

**The decision.** Confirm that three actions pass the judgement ground, so that only their
threshold, 3σ, goes to the second pass.

**Context.** At each stage start, a phase whose scale is under 3σ of its counting-noise esd
has its cell, positions, widths and B held; its scale stays free (`StageResult.held`, the
record field; `refine.py:1175-1223`). At the stage's answer, a held phase that now reads at
or above 3σ is released and the stage solves once more (`StageResult.released`). A phase
that fell under 3σ while solving is restored to its stage-start values and held, with one
extra solve (`refine.py:4114-4133`, read). Free, an absent phase's cell walked 14.9 Å from
the truth over 13 sub-onset patterns while Rwp did not move (the record's v1.3 row). With
the release and the restore, the worst cell error on that ramp fell from 11.96 Å to 0. The
3σ (`PHASE_SUPPORT_SIGMA`, `model/forward.py:344`) came in with WP-1523: over 20 blank fits,
one phase then read as present, against nine before. Its stated failure: a real phase at
about 1/16 000 of a strong phase's scale was seen in 1 fit of 8. The restore has no record
field of its own; it appends to `held` (read; B14 fixes it). `held_reach` lists what each
held column also stopped, such as b and c under a cubic a. It records `held` and takes no
action of its own.

**Aim.** The package decides alone only where every competent refiner would, and records
each action.

**Options.**
1. Keep all three; the 3σ goes to the second pass. Nothing changes for a user now.
2. Demote to kind 3, a report of each phase's significance. An invisible phase's cell would
   refine again (measured: 14.9 Å at unchanged Rwp). Undoable.
3. Option 1, and move `held_reach` to the non-action record fields (`OTHER_RECORD_FIELDS`).

**Practice.** GSAS-II, FullProf and TOPAS take no automatic hold; the user fixes a vanished
phase by hand (the record, tier 2 paragraph). A detection limit at three standard
deviations is the analytical-chemistry convention (Currie 1968, Anal. Chem. 40, 586;
recalled, not in the local corpus). If you accept it, the threshold's value is tier 2.

**Recommendation.** Options 1 and 3. The only dissenter is on the threshold: a refiner
watching a 2-3σ trace phase would keep it refining. The second pass should use three
families with a weighed minor phase: the IUCr round-robin mixture with the smallest weighed
fraction, a Durham tutorial, and one private-corpus file. I would change my mind if a
weighed phase above 1 wt % is held on any of them.

**The case against**, from a fresh-context judge (the `generality-review` role).

**Review: Case against.** The brief names a dissenter on the threshold only. There is also one on the action. Take a refiner on an in-situ ramp. A new phase appears at a cell more than a peak width from its CIF (thermal expansion, a solid solution). Its misplaced peaks keep its scale under 3σ. The hold freezes the cell where it is wrong, so the scale cannot climb to the release. That refiner would free the weak phase's cell. On disk the evidence is partial. CaF₂ held 1.2 % off its cell still reads 6.74σ (`refine.py:1662`), but it is a major phase. WP-1523's sweep (the 3σ support test) moved one weak real phase to held at 2.46σ (`refine.py:1210-1211`).

**Thinner than claimed.** The proposed second pass cannot fail. The round robin's smallest weighed phase is 1.15 wt % (`tests/data/README.md:141`), far above where 3σ bites on 7251 lab channels. Currie (1968) puts detection at 3.29σ and decision at 1.645σ (recalled). The 3σ convention is IUPAC's. In both, a detection limit licenses a report of absence. It does not license freezing parameters.

**Verdict:** holds for the action; weak for the threshold plan and its tier-2 citation.

**Would settle it:** a weighed phase at 0.1-1 wt %, and a minor phase started one FWHM off its cell.

**Rows that differ:** `PHASE_SUPPORT_SIGMA` stays tier 3. The citation does not carry tier 2.

**Revised pick after the review.** Unchanged for the action. The threshold stays tier 3, since the Currie citation does not carry it. The second pass adds a weighed phase at 0.1-1 wt % and a minor phase started one FWHM off its cell.

**Rows.** Tier 3, kind 1: `StageResult.held`, `StageResult.released`, `StageResult.held_reach`
(or a non-action field). Tier 3 pending the second pass: `PHASE_SUPPORT_SIGMA` (tier 2 if you
accept the convention). If demoted: kind 3.

---

## B2. The magnetic moment actions

**The decision.** Confirm that two moment actions pass under the rare-feature clause. That
clause (the record, § Where three families do not exist) judges an action with one family
on disk by the judgement ground alone, and keeps its threshold at the measured value.

**Context.** The moment turn (`StageResult.moment_turned`; `refine.py:898`, `:1055`) acts on a
moment whose azimuth the powder average cannot see. It turns the moment about its flat axis
onto a meridian before holding the azimuth, and only if the turned moment reproduces the
pattern. Without it, one answer sat at ψ = 27.84° against 10.20°. The stationary-angle test
(`StageResult.moment_angle_tests`; `optimize/least_squares.py:787`) asks after the solve
whether an angle sits on a direction the symmetry fixes, by a χ̄² cut at 95 % (Self & Liang
1987). Where it does, the angle keeps its value and loses its esd. Without it, a two-site
Pnma set reported modulus esds of 0.031 and 0.159 µB against 0.0015 and 0.0011 µB with the
column removed: about 20 and 140 times too large (WP-1929, per reader R). You ruled the 95 %
on 2026-10-12. One finding: `MOMENT_FLOOR_MU_B`'s docstring says a moment at 1e-3 µB is held,
and no single-fit code does so (appendix, item 11).

**Aim.** The whole field is in scope, and the package acts only where every refiner would.

**Options.**
1. Keep both at tier 3 under the clause, their explanations naming the one family.
2. Demote the angle test to kind 3. Other esds then grow 20-140 times on that set. Undoable.
3. Demote the turn. The azimuth is then held wherever the start put it.

**Practice.** GSAS-II and FullProf users constrain moment directions by symmetry, or refine
the higher-symmetry model and compare by Hamilton's test (recalled). I know of no program
that drops a covariance column automatically (recalled).

**Recommendation.** Option 1. Both act on a flat direction, as the absent-phase hold does.
The dissenter for the angle test would fit the higher-symmetry model and test it; the cut
passes any angle up to about 3.3σ off the direction, so a weakly determined angle that
truly sits off it can lose its esd (corrected after review). I would
change my mind if a second magnetic family shows the test dropping the esd of an angle a
published refinement determined.

**The case against**, from a fresh-context judge (the `generality-review` role).

**Review: Wrong in the brief.** "At 95 %, one angle in twenty that truly sits off the symmetric direction loses its esd" (`draft.md:125-126`) inverts the test. An angle passes when Δχ² is at most the cut (`schemas/results.py:887-890`). The 5 % is how often an angle truly on the direction keeps its column. An angle truly off it passes at the test's miss rate, which depends on signal strength. WP-1929 (the stationary-angle test) derives Δχ²/(χ²_red f²) = (δ/σ)²/4 (`docs/wp/1929-*.md:335`). So the 2.71 cut passes any angle up to 3.29σ off the direction.

**Case against.** The one real check shows low power. On LaMnO₃ (NIST BT-1) the polar angle stops 0.091 rad from 90°. It scores 0.57 against 2.71 and loses its esd. Before, its esd was 0.0608 rad (`tests/test_acceptance_magnetic_lamno3.py:181-185`). A refiner following that GSAS-II tutorial would fix Mz = 0 or quote the angle with its esd. rietx quotes an off-direction value with no esd, which neither would do. The denominator carries f², the B4 factor, so a large f widens the effective cut by f².

**Thinner than claimed.** The 20-140× figures come from a simulated set (`tests/test_pair_diagnostic_class.py:91`). With an exact angle column they were 3× and 22× (`docs/wp/1929-*.md:331`). Two real magnetic families are on disk (HB-2A Cr₂WO₆, BT-1 LaMnO₃), not one.

**Verdict:** weak for the angle test; holds for the moment turn.

**Would settle it:** the pass rate on simulated weak moments tilted 1-3σ, and LaMnO₃'s statistic without f².

**Revised pick after the review.** Keep the turn. Measure the angle test before ruling on it: its pass rate on simulated weak moments tilted 1-3σ, and LaMnO₃'s statistic without f². If it drops the esd of an angle a refiner would quote, demote it to kind 3: report the Δχ² and keep the esd.

**Rows.** Tier 3, rare feature, one family: `moment_turned`, `moment_angle_tests` (kind 1),
`MOMENT_PROBE_ANGLE_RAD`, `STATIONARY_ANGLE_STEP`, `STATIONARY_ANGLE_MAX_ITER`,
`MOMENT_FLOOR_MU_B`, `_flat_rotation_axis:h`*. Tier 2: `STATIONARY_ANGLE_LEVEL` (95 %, ruled
2026-10-12). Tier 1: `_flat_moment_scan:modulus_floor`*, `_onto_flat_meridian:pole_tol`*.
Invariant, test owed: `_FLAT_AXIS_TEST_DIRECTIONS`*. If demoted: kind 3.

---

## B3. The seeds

**The decision.** Where a stage starts a parameter that sits on its floor. A start can
change which minimum a fit finds.

**Context.** The roughness stage, last in any plan with a surface-roughness block, starts
Suortti's b at 0.3 (`strategy/staged.py:198`; `refine.py:3863`). The value sits between the
model's sensitivity peaks, b ≈ 0.17 for data from 5° and 0.46 from 20° (WP-0502). WP-1938
measured b's derivative at b = 0 as live (2.7e6, against the scale's 1.9e6), so 0 is a usable
start too. Roughness trades with Biso for the low-angle intensity, so the start may decide
which absorbs it (clash C20). The `lab_sample_refine` preset starts an all-zero Stephens
block (the anisotropic strain coefficients) at 1000 ppm on the isotropic ray
(`staged.py:486`; `refine.py:3869`). Some start is forced there, because the width has
unbounded slope at zero. WP-1467 showed on one pattern that the start changes the minimum:
χ² 1.160 from 1000 ppm, 1.482 from the template's own isotropic strain. The roughness seed is
recorded in `StageResult.seeded`; the strain seed is recorded nowhere (read).

**Aim.** A right answer in the fewest calls, and every action recorded.

**Options.**
1. Keep both. Add a record field for the strain seed (B14).
2. Test the roughness seed: refit three lab families from b = 0 and from 0.3. If b, Biso
   and the scale agree within their esds, the seed is invariant and needs no approval.
3. Demote to kind 2: run both starts and keep the ranking. That stage's cost doubles.
4. Start roughness at 0, as GSAS-II does.

**Practice.** GSAS-II starts `SurfRoughA` and `SurfRoughB` at 0 (`GSASIIfiles.py:261`,
`GSASIIdataGUI.py:2078`, checked). That is a named dissenter for 0.3. GSAS-II's isotropic
microstrain default is 1000 µstrain, and its Reset puts generalised coefficients on the
isotropic ray at 1000 (`GSASIIddataGUI.py:180-190`, `:1432`, checked). FullProf and TOPAS were
not checked.

**Recommendation.** Option 2 for roughness. If it is not invariant, switch to GSAS-II's 0
unless the measurement favours 0.3 against a reference. Option 1 for strain: it matches GSAS-II's
isotropic default (its generalised start is 0.01 each; corrected after review), and WP-1467's open checklist already compares starts. I would change my mind if
b = 0 lands in a worse minimum on two of the three families.

**The case against**, from a fresh-context judge (the `generality-review` role).

**Review: Wrong in the brief.** "It is GSAS-II's own value" (`draft.md:172`) holds only for the isotropic model. A new GSAS-II histogram starts its generalised coefficients at 0.01 each (`GSASIIddataGUI.py:1432-1433`, checked). The isotropic ray at 1000 is the Reset button (`:180-191`), which is a user's act. Switching the model does not convert the value (`:151-155`). So tier 2 for the strain seed rests on GSAS-II's isotropic default of 1000 µstrain alone.

**Case against roughness.** rietx's own docstring says two values of b, one each side of the sensitivity peak, give any one depression (`schemas/instrument.py:980-986`). Two starts can land on different branches at near-equal χ². "Agree within esds" can then fail with neither answer wrong. Option 4 is also not GSAS-II's start. GSAS-II starts a = 0, b = 0 (`GSASIIfiles.py:261`), where its a column has no gradient. rietx starts a at 0.5 (`schemas/instrument.py:1019-1021`).

**Thinner than claimed.** The strain evidence is three patterns from one series. One pattern carries the comparison of starts (`docs/wp/1467-*.md:68-72`).

**Verdict:** holds for the roughness test; weak for the strain seed's tier 2.

**Would settle it:** both b starts on three families, naming the branch each reaches and Biso against a reference. For strain, a second family comparing 1000 ppm with the previous stage's isotropic value.

**Revised pick after the review.** Option 2 for roughness, naming the branch each start reaches on each family. The strain seed stays tier 3, since GSAS-II's generalised start is 0.01, until a second family compares the starts.

**Rows.** Tier 3 (invariant if the test passes): `StageResult.seeded`,
`_ROUGHNESS_STAGE:seed`*, `SUGGEST_SEED_ROUGHNESS` (the suggestion probe's copy). Tier 2:
`lab_sample_refine:strain_seed`*, `SUGGEST_SEED_STEPHENS`. Tier 1: `_run_stage:strain_seed`*
(seeding an all-zero block at all). Invariant: `compile_model:lebail_pawley_intensity_seed`*
(Le Bail's equal start). If demoted: kind 2.

---

## B4. The Bérar-Lelann esd inflation

**The decision.** Whether every reported esd keeps being multiplied, with no switch, by a
factor that corrects for serially correlated residuals.

**Context.** After the usual covariance (the inverse normal matrix scaled by χ²_red), rietx
multiplies every reported esd by f = √(S''/S) (Bérar & Lelann 1991, § IV;
`optimize/least_squares.py:2848`, read). f grows when neighbouring residuals share a sign.
Verified values: about 1.13 on uncorrelated residuals, so every esd is 13 % larger even with
no correlation (`optimize/statistics.py:419`); 2.15 on the FAP lab example; 8.07 on the NAC
synchrotron example (`docs/releases/1.6.0.md:328-330`). A user comparing a rietx esd with
GSAS-II's on synchrotron data therefore sees it about eight times larger. rietx's own
absent-phase test refuses the inflated esd as evidence (`refine.py:1651-1680`, read): with
it, a present LaB₆ phase read 0.23σ where counting noise gave 2865σ. That test drops √χ²_red as well as f, and χ²_red did most of
that work (corrected after review). f also feeds three
statistics: ΔBIC's effective count N/f², the fraction profile's Δχ² cut, and the moment-angle
test's scale.

**Aim.** Trust built by checking against references and stating methods plainly.

**Options.**
1. Keep, tier 2 on the citation. Esds stay 1.13 to 8 times larger than GSAS-II's.
2. Demote to kind 3. The reported esd becomes the χ²_red-scaled one, and f is reported beside
   it with its meaning. Every esd shrinks by 1/f, one number per fit: 0.89 on white
   residuals, 0.47 on FAP, 0.12 on NAC (inferred from the factors). Esd goldens move; with
   no independent reference, the record's rule is to re-pin and name the mechanism. The
   three statistics keep reading f. Undoable.
3. A switch, default off.

**Practice.** GSAS-II 5.8.4 does not apply it: "Berar" and "Lelann" appear nowhere in its
source, and its esds are the covariance times GOF² (`GSASIIstrMain.py:397`, checked).
FullProf computes SCOR and prints "A better estimate of the accuracy of structural
parameters is obtained multiplying sigmas by the parameter SCOR"; its own esds are
unmultiplied (manual eq 3.7 and the `fp2k` binary's strings, checked). TOPAS was not
checked. The paper recommends the correction (docstring; not in the corpus).

**Recommendation.** Option 2. Every GSAS-II and FullProf user is a named dissenter by
default, and FullProf's printed advice to multiply by SCOR shows the choice is not unanimous
either way. The strongest case against: f
widens esds that already under-cover systematic error. SRM 660c's cell sits 4.9σ from its
certificate with f applied (`docs/VALIDATION.md:287-291`, reader O, unverified). My answer:
f measures serial correlation and does not estimate systematic error, and the reported f
keeps its warning. I would change my mind if the inflated esd covers its certified value,
and the plain one misses it, on two of three validation families.

**The case against**, from a fresh-context judge (the `generality-review` role).

**Review: Wrong in the brief.** "rietx's own code refuses the inflated number" (`draft.md:197-199`) proves too much. The absent-phase test drops both √χ²_red and f (`refine.py:1658`). In the 0.23σ against 2865σ case (two dead channels under LaB₆), χ²_red does most of the work. By this argument the χ²_red scaling, which B4 keeps at tier 2, would go too.

**Case against.** FullProf prints SCOR, the same factor, and says multiplying sigmas by it is "a better estimate" (`fp2k` strings, checked). A FullProf user who follows that advice multiplies. So neither choice is unanimous, and kind 3 still follows. The open point is the record's rule on a moved golden. SRM 660c's cell sits 4.9σ from the certificate with f applied (`docs/VALIDATION.md:291`; arithmetic checked). Without f it sits about 4.9·f σ away, further from honest coverage.

**Couplings the brief omits.** The bound test (`staged.bound_findings`) reads `stderr_internal`, which carries f (`optimize/least_squares.py:504`, `:2848`; `strategy/staged.py:2012`). Its 13× margin was measured with f included, so it falls to 13/f (B16). B7's 0.03-esd bound has the same unit question (inferred).

**Verdict:** holds.

**Would settle it:** a ruling on whether esd coverage of a certificate counts as a reference. Also the B16 window re-measured in plain esds. TOPAS and the IUCr guidelines (McCusker et al. 1999) were not checked.

**Revised pick after the review.** Unchanged: demote to a reported factor. The bound test's margin (B16) and the 0.03-esd bound (B7) are re-measured in plain esds in the same change.

**Rows.** `Statistics.esd_inflation`: the statistic tier 2, the multiplication demoted to
kind 3. Tier 2, kind 1, kept (GSAS-II's own default, checked): `normal_factors:chi2_red_scaling`*,
`normal_factors:jacobi_equilibration`*.

---

## B5. σ handling

**The decision.** What rietx does with a zero or negative esd in a file, and whether a
result records which σ rule fired.

**Context.** With no esd column, σ = √max(y, 1) (`schemas/pattern.py:179`). An esd at or
below zero is raised to 10⁻³ of the column's median positive esd (`pattern.py:43`). A
measured blank adds its own variance (`model/forward.py:4011`), which is arithmetic. Issue
#897 (a reporter's request about two-column files) showed one zero esd among 3.0s. That
point got σ = 0.003 and weighed about 10⁶ times its neighbours, since weight goes as 1/σ². No
diagnostic said so. WP-1952 (the xy-reader WP) holds the open choice: floor, drop or refuse.
No result field says which σ rule fired (`schemas/results.py:1690-1694`, read). A project's
`DataRef.has_sigma` records the fallback, and the text summary prints "σ source"
(`refine.py:5533-5536`). Nothing records the floor. Reader P cites a
`RefinementResult.weighted` field; there is none.

**Options for a non-positive esd.**
1. Keep the floor: tier 3, no source for 10⁻³.
2. GSAS-II's rule: a zero esd falls back to Poisson for that channel, a negative one drops
   the channel (`imports/G2pwd_xye.py:176-185`, checked).
3. Drop every such channel, as rietx's pdCIF reader drops a column with any zero.
4. Refuse the file and name the lines.

**Practice.** GSAS-II as in option 2; its Poisson weight is 1/y, zero at y ≤ 0, where rietx
uses σ = 1 (checked). FullProf and TOPAS were not checked.

**Recommendation.** Option 2, built in WP-1952 with the by-line report it already plans. It
keeps the point. The review shows it can still let one channel dominate on scaled data. Demote the floor to kind 3 in the table
now: the cause of a zero esd lies outside the pattern. Keep the Poisson fallback at tier 2.
Add a result field naming the σ rule and the channels each touched (B14). I would change my
mind if WP-1952 finds files where a zero esd marks a channel meant to be excluded; then
option 3.

**The case against**, from a fresh-context judge (the `generality-review` role).

**Review: Wrong in the brief.** Option 2 is not GSAS-II's rule as built. GSAS-II's xye reader zero-weights any channel with y ≤ 0, whatever its esd (`imports/G2pwd_xye.py:172-174`, checked). rietx's fallback gives σ = 1 there (`schemas/pattern.py:179`). "It cannot let one channel dominate" (`draft.md:264`) is false for scaled data. A Poisson σ is in count units. On a pattern scaled up 1000× (monitor-normalised or summed), √y is about 30× smaller than its neighbours' esds. That channel then weighs about 1000× more (arithmetic). Issue #897's failure (one zero esd weighing 10⁶× its neighbours) comes back in the other direction.

**Case against.** A neutron refiner whose reduction writes masked bins as y = 0, e = 0 (recalled for Mantid; not checked). Under option 2 those bins pull the model to zero at weight 1. GSAS-II's y ≤ 0 rule and option 3 both drop them. Option 3 cannot go wrong in units. GSAS-II's rule is one reader's; its other readers were not checked.

**Verdict:** weak.

**Would settle it:** what a zero esd marks in each format rietx reads (masked, saturated, uncounted), established before WP-1952 (the xy-reader WP) picks.

**Rows that differ:** `compile_model:background_sigma_widening` is tier 1 as a formula. Its scale is frozen at compile while the scale row refines (clash C26), so it is arithmetic on a stale input.

**Revised pick after the review.** Demote the 10⁻³ floor to kind 3 now. Leave its replacement to WP-1952, after that WP establishes what a zero esd marks in each format rietx reads. Dropping the channel and reporting it (option 3) is the lead candidate, since it cannot go wrong in units.

**Rows.** `PatternData.sig:poisson_fallback`* tier 2, kind 1. `_floor_sigma:relative_floor`*
tier 3, demoted to kind 3. `compile_model:background_sigma_widening`* tier 1.

---

## B6. Anomalous dispersion on by default

`Source.dispersion` applies Cromer-Liberman f′ and f″ to every X-ray phase unless the caller
sets it to None. GSAS-II applies the same table to every X-ray histogram with no switch
(`GSASIIstrIO.GetFprime`, called on every refinement path; checked). Without it, ZnO's
reflections are mis-scaled by 16 % at Cu Kα, and the round-robin QPA error rose from 0.62 to
2.26 wt % RMS (WP-1001, per reader P). The dissenter reproduces an old number without
dispersion. They set None, and `DISPERSION_NEGLECTED` says so. Near an absorption edge the
package refuses and asks for measured values. Recommendation: tier 2, kind 1, keep.

**The case against**, from a fresh-context judge (the `generality-review` role).

**Review: Checked.** GSAS-II computes f′ and f″ for every X-ray histogram (`GSASIIstrIO.py:251-273`). It does so on every refinement path (`GSASIIstrMain.py:513`, `:756`, `:823`, `:1002`). The QPA numbers hold: RMS 2.26 → 0.62 wt % (`docs/VALIDATION.md:621`). WP-1001 recorded 0.69, and 0.62 is the current figure.

**Case against.** It is weak. The only dissenter reproduces a number from before dispersion, and setting `None` serves them. FullProf's manual describes Δf′ and Δf″ supplied by the user (ITY = 2, checked). I did not find whether FullProf applies tabulated values at a lab anode by default. TOPAS was not checked. The QPA gain rests on one family: the round robin, one laboratory, Cu Kα.

**Verdict:** holds.

**Would settle it:** nothing further is needed for tier 2. GSAS-II's default carries it.

**Revised pick after the review.** Unchanged: keep, tier 2.

---

## B7. The default plan and the stage tolerance

**The decision.** First, confirm that running the `mccusker_default` preset when the caller
names no plan passes. It frees scale and background, then zero and cell, then the
profile widths. It frees no structural parameter (corrected after review). Second, decide whether the looser tolerance of intermediate stages
becomes invariant by test.

**Context.** `fit` and `refine` default to `mccusker_default` (`refine.py:4284`, `:9560`),
whose order follows McCusker et al. (1999) J. Appl. Cryst. 32, 36. Every stage but the last
stops at a relative cost change of 1e-6, the last at 1e-9 (`INTERMEDIATE_FTOL`). WP-1123
measured 1.2 to 1.6 times fewer evaluations, with every non-degenerate parameter within
0.03 esd of the fully converged plan, on 11-BM NAC, two IUCr round-robin samples and a
simulated case. Three hundredths of an esd is a small move. The comment asks for
re-measurement after a later Jacobian change (`schemas/plan.py:53-58`, read), and no test
asserts the bound (read). A looser intermediate stop can also change a hold read at that
stage's end (clash C18). `CORRELATION_GUARD` (0.98, three rows) moved to B13: it only
reports, and nothing acts on its findings (`strategy/staged.py:1940-1956`, read).

**Options for the tolerance.**
1. Invariant by test: refit three families at 1e-6 and 1e-9, and assert every non-degenerate
   parameter within 0.05 esd and the same held set. No approval after.
2. Tier 3, with the mechanical ground in the second pass.
3. Converge every stage at 1e-9: the bit-identical way back, 1.2-1.6 times slower.

**Practice.** GSAS-II, FullProf and TOPAS ship no default plan; the user turns parameters
on. GSAS-II stops after 3 cycles or a relative change of 0.001 (`GSASIIobj.py:20`, checked).

**Recommendation.** The plan passes at tier 2. A TOPAS user who frees everything at once
from a good start dissents on cost only, since both reach one minimum inside the basin. For
the tolerance, option 1, with clash C18 checked in the same test. I would change my mind if
a hold decision flips between the two tolerances on any family.

**The case against**, from a fresh-context judge (the `generality-review` role).

**Review: Wrong in the brief.** "It frees scale and background, then cell and zero, then the profile, then the structure" (`draft.md:294-295`) is false. `mccusker_default` frees scale and background, then zero, cell, W, and U, V, X, Y. It frees no structural parameter (`strategy/staged.py:351-360`). That is `mccusker_structural` (`:363-383`).

**Case against the plan.** A lab Bragg-Brentano refiner frees specimen displacement with the zero. rietx's own `lab_bragg_brentano` preset does so (`strategy/staged.py:411-419`). On a Bragg-Brentano instrument the default plan frees zero only. It also holds the Kα2 ratio at its seed (B14). So rietx's own presets dissent from its default. No program ships a default plan. McCusker et al. (1999) advise a person; they did not validate a fixed default.

**Case against the tolerance.** The invariant class's precedent moved 0 of 1030 accepted values (`docs/milestones/generality.md:124-129`). A 0.03-esd bound is a tolerance, so "invariant" stretches the class. Its esd carries f (B4), so its units shift if B4 lands (inferred).

**Verdict:** weak for the plan's tier 2; holds for the tolerance test, with the class question open.

**Would settle it:** the default plan against `lab_bragg_brentano` on three Bragg-Brentano families, with cells read against certificates.

**Revised pick after the review.** The default plan becomes a real judgement. On Bragg-Brentano data rietx's own `lab_bragg_brentano` preset frees specimen displacement, and the default does not, so tier 2 does not hold as written. Either keep it at tier 3, with the second pass comparing the two presets on three Bragg-Brentano families against certificates, or choose the preset from `Geometry.kind` in a follow-up WP. The tolerance: option 1, with the test written in plain esds.

**Rows.** Tier 2, kind 1: `fit:plan`, `refine:plan`. Invariant, test owed:
`INTERMEDIATE_FTOL`, `PlanSpec:intermediate_ftol`, `StageSpec:ftol`, `StageResult.ftol`,
`run_least_squares:ftol`* (the final 1e-9). If the test fails: tier 3; demoted, kind 3.

---

## B8. Bounds that act on every fit

**The decision.** Three parts: the per-stage cell window, the post-solve cell clamp, and the
2 nm crystallite floor.

**Context.** *The window.* A phase whose screen reads under 3σ at stage start gets a cell box
of ±5 % (plus 0.05 Å) and ±2° for that stage (`optimize/least_squares.py:2177-2196`;
`params/vector.py:567`). It was built after an unseen phase's cell ran to 39 293 Å on a
68-pattern in-situ series (WP-1110). Reader P found, and I confirmed by reading, that the B1
hold runs first and fixes every structural column of the same phases.
`ParameterTable.bounds()` boxes free entries only (`vector.py:3769`). So on the single-fit
path the window can bind only on a cell column the hold left free, one that also drives a
visible phase's cell through a tie. The visible phase then pins it (inferred). A count would
settle it: over the fast and acceptance suites, the stages where a windowed cell entry is
still free, and those where it binds. I expect zero and zero.

*The clamp.* After every solve, a free cell length more than 15 % from the stage start (an
angle more than 6°) is pulled back to that edge, with no re-solve (`refine.py:1227-1286`,
read). A visible phase sharing its cell with a 2 % trace copy ran from 4.1566 to 3803 Å in
one stage, and the next stage crashed. WP-1110's 51 honest stage moves were at most 2.8e-4
relative, about 500 times inside the edge. The clamped cell sits at a value nobody measured,
and only the `CELL_RUNAWAY` diagnostic records it.

*The size floor.* A size term may not drive the crystallite below 2 nm, armed once it gets
there (`SIZE_CAP_MIN_SIZE_A` = 20 Å). The 2 nm comes from one private archive of 606 TOPAS
refinements, whose smallest well-determined size is 33 nm (`vector.py:886-898`). The strain
cap beside it uses only the fitted range: a line wider than the scan carries no information.

**Options.**
1. Window. (a) Keep, tier 3. (b) Remove it from the single-fit path if the count is zero;
   joint fits are WP-2003's. (c) Keep it for the tied-column case.
2. Clamp. (a) Keep, tier 3, kind 1, since a 15 % move in one stage is no measurement; add a
   record field. (b) Restore the stage-start cell and hold it, as the collapse restore does;
   a redesign, so a follow-up WP. (c) Demote to a report; the next stage then crashes.
3. Size floor. (a) Keep 2 nm; one family, so it fails the mechanical ground as written.
   (b) Drop the floor, keep the range backstop, and let `SIZE_UNUSUALLY_SMALL` (a report at
   5 nm, WP-2005's) explain a small size. (c) A physics floor of one cell's longest edge.

**Practice.** The window's pad and 1.5 Å floor follow TOPAS's default cell bounds (Technical
Reference § 2.17, per the docstring; not checked). GSAS-II sets no default bounds (WP-1110).
I know of no program that clamps a cell after a solve or sets a crystallite floor (recalled).

**Recommendation.** 1(b) after the count. 2(a) now, filing 2(b); reader R names the
dissenter, a refiner who would restore and hold. 3(b): it matches the strain cap, and the
dissenter is a refiner of 1-2 nm nanoparticles whose answer is now pinned at 2 nm. I would
change my mind on the window if the count finds a stage where it binds, and on the floor if
a real file's size runs away to the range fence.

**The case against**, from a fresh-context judge (the `generality-review` role).

**Review: Window, 1(b).** The read checks out. The hold takes the lower of the screen and the prior (`refine.py:1214-1219`). The window takes the screen alone (`optimize/least_squares.py:2193-2195`). So every windowed phase is held, except where a column also moves a visible phase (`refine.py:516-519`). The case against is TOPAS. Per its docstring (not checked), TOPAS bounds every cell on every iteration by default: ±0.5 % plus 0.05 Å (`params/vector.py:593-597`). Removing the window moves rietx further from that practice.

**Clamp, 2(a).** Its one trigger is a synthetic two-phase LaB₆ under TRF (`params/vector.py:505-513`). It fired in none of 104 fits in WP-1523's sweep (`docs/wp/1523-*.md:346`). After a clamp, θ is re-encoded but the Jacobian and esds stay those of the escaped point (`refine.py:4009-4028`; inferred). A refiner who saw a runaway would stop, or restore and hold. The collapse restore already does the second, so 2(b) reuses that path rather than redesigning.

**Floor, 3(b).** The range backstop is about 13× looser: ≈54° against ≈4° FWHM on a 10-80° Cu scan (`params/vector.py:903`). Dropping 2 nm leaves almost no fence. The 1-2 nm dissenter is weak, since below 2 nm a careful refiner uses the Debye equation (recalled).

**Verdict:** 1(b) holds once counted; 2(a) weak; 3(b) weak.

**Also.** `params/vector.py:524` says honest moves sit "five orders inside" the clamp. 0.15 / 2.8e-4 ≈ 540.

**Revised pick after the review.** Window 1(b) after the count. Clamp 2(b): restore and hold, through the collapse restore's existing path. Size floor 3(a): keep 2 nm at tier 3, one family, declared untested beyond it.

**Rows.** Window, tier 3 (removed if inert): `cell_window`*, `_freeze_cell_windows`*,
`CELL_WINDOW_FRACTION`, `CELL_WINDOW_ANGLE_DEG`; tier 2 (TOPAS, docstring):
`CELL_WINDOW_PAD_A`, `CELL_MIN_LENGTH_A`. Clamp, tier 3, kind 1: `clamp_cell_runaway`*,
`CELL_SAFETY_FRACTION`, `CELL_SAFETY_ANGLE_DEG` (its factor of 3 has no angle survey). Size
floor, tier 3, demoted to kind 3: `SIZE_CAP_MIN_SIZE_A`, `size_cap_hi`*, `_freeze_size_cap`*.
Tier 1: `SIZE_CAP_RANGE_FRACTION`, `STRAIN_CAP_RANGE_FRACTION`, `strain_cap_hi`*,
`_freeze_strain_cap`*, `tie_window`*, `_ANGLE_MIN_DEG`, `_ANGLE_MAX_DEG`. Invariant:
`_DegenerateCellGuard:penalty_factor`* (any factor above 1 rejects the trial); reader R's
`:penalty`* is the same literal.

---

## B9. Defaults inside opt-in features and schema fields

**The decision.** One reading for 21 defaults, and what to do with two that assume a fact
about the instrument.

**Context.** Three shapes. *Boxes* on parameters held by default or inside an opt-in block:
March-Dollase r in [0.15, 6], harmonic weight up to 0.5, the extra-peak and hump width
windows, the TCHZ width boxes, geometry offsets of ±1 mm, occupancy in [0, 1.5], zero shift
of ±0.5°, emission-line weight in [0, 2]. Each guards a runaway, and `BOUND_HIT` reports a
bind. Readers P and B tiered the opt-in ones `caller`; the record tiers a verb's thresholds
on their own evidence (§ A pick on top of a ranking), so I keep `caller` for the switch
only. *Starting values* the solve moves away from: the TCHZ starts, Biso 0.5, the harmonic
seed. *Held values that describe the instrument or specimen.* `Geometry.kind` defaults to a
Debye-Scherrer capillary (`schemas/instrument.py:1207-1208`, read). A lab Bragg-Brentano user
who builds an `Instrument` without naming a geometry gets the capillary position corrections
and absorption branch, and the report suggests capillary actions (reader P). The
`debye_scherrer` preset holds the polarisation K at 0.99. A lab-capillary user with a Cu tube
(K about 0.5 to 0.8, recalled) then gets intensities wrong by a smooth function of 2θ, which
Biso partly absorbs (inferred). The µR estimate assumes a packing fraction of 0.6, where
GSAS-II's calculator assumes 0.50: a 20 % difference in µR, carried into the Biso shift the
capillary correction makes (inferred). The result records µR as estimated, and the shift.

**Options.**
1. Keep every default at tier 3.
2. The reading: boxes tier 3, kept while `BOUND_HIT` reports a bind, with the second pass
   asking only whether a box binds an honest fit on three families. Starts become invariant
   by a two-start test. Held instrument facts are kind 3, and the result records them as
   assumed.
3. Require the caller to state `Geometry.kind`. It breaks code that builds an `Instrument`
   by hand. Undoable.

**Practice.** GSAS-II's absorption calculator assumes packing 0.50 (`Absorb.py:89`, checked;
a utility that acts on nothing). GSAS-II reads polarisation from the instrument file. I
recall no default occupancy bound in GSAS-II, FullProf or TOPAS.

**Recommendation.** Option 2, with option 3 for `Geometry.kind` considered in a follow-up.
Keep the packing fraction and the goniometer radius: the caller asked for the estimate or
the mm reading, and the result records it. I would change my mind if the second pass finds
a box binding an honest fit on any family.

**The case against**, from a fresh-context judge (the `generality-review` role).

**Review: Wrong in the reading.** "Kept while `BOUND_HIT` reports a bind" keeps a box because it is visible. The record rejects visibility as the ground (`docs/milestones/generality.md:77-82`, fourth review). A box passes on unanimity or not at all.

**Case against.** A mineralogist refining site scattering declares Mg on an Fe-Mg site. Full Fe then reads 26/12 ≈ 2.2. `Atom:occ`'s [0, 1.5] caps that (`schemas/structure.py:500`). A refiner of a pressed clay or mica plate may need March r below 0.15. That 0.15 rests on an Rwp comparison, 30.8 → 13.2 % (`schemas/structure.py:33-38`). Rule 4 rejects an Rwp comparison as evidence.

**Agreed.** `Geometry:kind` (default `debye_scherrer`, `schemas/instrument.py:1207-1208`) and the preset polarisation of 0.99 (`:2462-2470`) belong as recorded assumptions. GSAS-II's packing of 0.50 is checked (`Absorb.py:89`).

**Verdict:** weak.

**Would settle it:** per box, a program's default bound or a family where an honest fit lands outside it.

**Rows that differ:** `Atom:occ` and `MARCH_R_MIN`'s 0.15, each with a named dissenter. `bragg_brentano:ka2_ratio` belongs here (B14).

**Revised pick after the review.** Rule each box on unanimity, not on visibility. A box that guards a pole or a non-physical region stays (occupancy ≥ 0, March r > 0). A chosen cap with a named dissenter (occupancy ≤ 1.5, March r ≥ 0.15) needs a program's default or a family, or it widens to the physical limit. `Geometry.kind`, the preset polarisation and the Kα2 ratio become recorded assumptions.

**Rows.** Tier 3 boxes: `MARCH_R_MIN` (the pole at 0 is tier 1, the 0.15 tier 3),
`MARCH_R_MAX`, `HARMONIC_WEIGHT_MAX`, `EXTRA_PEAK_FWHM_MIN`, `EXTRA_PEAK_FWHM_MAX`,
`HUMP_FWHM_MIN`, `HUMP_MIN_WIDTH_MULT` (it also floors a hump's width in the extinction
screen, `indexing/extinction.py:737`), `TCHZ_BOUNDS`*, `TCHZ_BOUNDS_COARSE`*,
`Geometry:bounds`*, `Atom:occ`*, `EmissionLine:weight`*, `Instrument:zero_shift`*.
Invariant, test owed: `HARMONIC_WEIGHT_SEED`, `TCHZ_DEFAULTS`*, `Atom:biso`*. Tier 3, kind 3,
recorded as assumed: `Geometry:kind`*, `debye_scherrer:polarization`*. Tier 3, kind 3, kept:
`Geometry:packing_fraction`* (reader R named the same default `Geometry.packing_fraction`*),
`bragg_brentano:goniometer_radius_mm`*.

---

## B10. Numerical settings: how the rule reads for a quadrature

**The decision.** How the three-family ground applies to a setting whose correctness is a
convergence property. It is a question about the rule itself.

**Context.** The class holds the axial-divergence quadrature's node counts, the peak
windows, the finite-difference step, the solver's switches and polish tolerances, the
Gaussian-width floor, the texture sphere sampling and some cost caps. Changing one moves
accuracy or cost, and no refiner has a view on it. Three dataset families rarely reach the
domain's edges, so they do not test a quadrature; its error over the claimed angles, widths
and apertures does. Measured this session: the node cap `MAX_NODES` = 64 binds below about
6.5° 2θ on a lab Bragg-Brentano pattern (axial ratios 0.025, FWHM 0.07°). Against a 512-node
reference the peak is off by 0.19 % of its height at 5°, 0.71 % at 4° and 2.8 % at 3°;
uncapped, under 0.06 %. Large-cell materials on lab data (zeolites, MOFs, clays) have their
first peaks there. No setting in this class has a test that bounds its error over its
domain. Single-case checks exist for `WINDOW_AREA_TOL` (`tests/test_extra_components.py:1426`),
the FCJ profile (`tests/test_lab_instrument.py:329-356`, 1 % at 22° only), `BVLS_MAX_COLUMNS` and
`_CURVATURE_GATE` (`tests/test_lm_solver.py:628-645`, `:691`), `_MIN_GAMMA_G2`
(`tests/test_gaussian_width_floor.py`) and `A5_CLIP` (`tests/test_floating_origin.py`). The
compiled-tier rows have bit-identity tests (`tests/test_compiled_kernels.py`).

**Options.**
1. Apply the ground as written: tier 3 until three families run. Those fits would have
   passed the node cap.
2. A reading: tier 1 when a test bounds the error over the claimed domain below the model's
   own accuracy or the data's noise; invariant when only cost moves and a test asserts
   identity; otherwise tier 3 with the owed test named in the row. One sentence added under
   tier 1 in `generality.md` § The rule.
3. Declare numerical settings outside the audit.

**Practice.** GSAS-II, FullProf and TOPAS fix their quadrature orders internally, with no
published convergence tests I know of (recalled). The node rule follows Finger, Cox &
Jephcoat (1994) (docstring).

**Recommendation.** Option 2. It asks the question that can fail, and the node cap failed
it. I would change my mind if you want every tier-3 item held to three families; then
option 1, with each domain sweep counted as a family.

**The case against**, from a fresh-context judge (the `generality-review` role).

**Review: Agreed.** The node-cap measurement reproduces from `fcj_low_angle.py`. 0.19 % of peak height at 5° is under counting noise for a 10⁴-count peak. 2.8 % at 3° is not (arithmetic).

**Case against the reading.** A domain test bounds error against a reference, and a solver switch has none. Crossing `BVLS_MAX_COLUMNS` (128 columns, where the exact active-set step ends) changes which minimum FAP's Pawley fit reaches: Rwp 0.0803 against 0.0782 (`optimize/lm.py:728-731`). That is a different answer, not an error over a domain. `_CURVATURE_GATE`, `_POLISH_FEASIBLE`, `_POLISH_STATIONARY`, `_PCG_TOL` and `_PCG_BUDGET_PER_VARIABLE` likewise decide where a stage stops. "The claimed domain" is itself chosen, and tier 1 inside it says nothing outside. "The data's noise" is no single number either, since it falls by orders from a lab scan to an 11-BM one.

**Verdict:** holds for quadratures and windows; weak for solver switches.

**Would settle it:** for each switch, refits of three families on either side asserting one answer. Otherwise tier 3.

**Rows that differ:** the six solver-path rows above.

**Revised pick after the review.** Option 2 for quadratures and windows. The six solver-path switches stay tier 3, kept only if refits of three families on either side give one answer.

**Rows.** Tier 3 until a domain test exists (24): `NODES_PER_FWHM`, `MIN_NODES`, `MAX_NODES`
(failing below 6.5°), `SKIP_EXTENT_FWHM_RATIO`, `WINDOW_MIN_DEG`, `WINDOW_AREA_TOL`,
`REFLECTION_MARGIN_DEG`, `StageSpec:window_slack_deg`, `AXIAL_SIZING_FLOOR`,
`MAGNETIC_SIZING_FLOOR`, `FD_STEP`, `BVLS_MAX_COLUMNS` (FAP Pawley reads Rwp 0.0803 on one
side of it and 0.0782 on the other, `lm.py:731-735`), `_CURVATURE_GATE`, `_PCG_TOL`,
`_PCG_BUDGET_PER_VARIABLE`, `_POLISH_FEASIBLE`, `_POLISH_STATIONARY`, `_MIN_GAMMA_G2` (your
choice in WP-1938), `TEXTURE_SPHERE_SAMPLES`, `A5_CLIP`, `MIN_IMAGE_SHELL`, and three
report-only geometry caps the WP still tiers (`CONTACT_MAX_ANG`, `MAX_ASYM_ATOMS`,
`MAX_CONTACTS_PER_ATOM`). Invariant: `_BASES_CHUNK_ROWS` (bit-identical at 1-4096 rows in
reader M's probe; no test), `_DENSE_EIGEN_MAX`, `largest_eigenvalue:lanczos_tol`*,
`FLOOR_SEEDS`*, `_NS_PER_ELEMENT`*, `n_threads:cap`*, `compiled:tier_on_by_default`*. Tier 1:
`ParameterTable:aniso_symmetry_tolerance`*.

---

## B11. Stop rules and runaway guards

**The decision.** Confirm that the iteration budgets are runaway guards that leave a
converging answer alone, and decide the Le Bail cycle count.

**Context.** `StageSpec.max_iter` = 100, scaled by `NFEV_PER_ITERATION` = 4 into an
evaluation budget, and LM's 18 inner trials (`_INNER_MAX`) are runaway guards. A converging
fit stays an order of magnitude inside them (WP-1109, docstring). Reader S reports that
`max_iter` binds under the non-default TRF solver on three fixtures, where `STAGE_MAX_ITER`
says so. Le Bail refreshes the extracted intensities 3 times per stage (`lebail_cycles`).
Issue #740 (verified) used a synthetic LaMnO₃-like neutron pattern with the cell and profile
at the truth. Rwp was 4.56 % at 3 cycles and 1.63 % at 100, against 1.09 % for the true
Rietveld model: about four times the true model's Rwp. In a full plan the cycles accumulate
across stages, which softens this (inferred). `FROZEN_COMPILE_CHI2_REL` only decides whether
an info code fires (`refine.py:4955`, read), so it moved to B13.

**Options for `lebail_cycles`.**
1. Keep 3, tier 3, with #740 as its stated failure.
2. Raise to 10, the practice below.
3. Repeat each stage's partition until its relative change falls under a tolerance, with a
   cap. Every refiner runs the extraction until it stops changing.

For the budgets: invariant, with a test asserting the margin on three families.

**Practice.** GSAS-II's Le Bail extraction runs 10 cycles by default (`DoLeBail`,
`GSASIIstrMain.py:761`, checked). FullProf's manual tells the user to run "a few cycles (say
10)" first (checked, its profile-matching section).

**Recommendation.** Option 3, folded into WP-1542 (the WP that owns #740), with option 2 in
the meantime. The budgets become invariant with a margin test. I would change my mind if
#740's gap closes at 3 cycles inside a full plan.

**The case against**, from a fresh-context judge (the `generality-review` role).

**Review: Checked.** GSAS-II's `DoLeBail` defaults to 10 cycles (`GSASIIstrMain.py:761`). It is the stand-alone extraction. How often an ordinary GSAS-II refinement refreshes Le Bail intensities was not checked. FullProf's "a few cycles (say 10)" sits in its profile-matching section, with no parameters refined (manual, checked).

**Case against.** #740's own numbers show more cycles do not close the gap. Le Bail stays at Rwp 1.62 % from 100 to 400 cycles. The true structure reaches 1.09 % and Pawley 1.06 % (`i740.json`). Option 3 removes the 4.56 % and leaves the 1.62 %. "Change my mind if the gap closes at 3 cycles" tests the wrong gap.

**Budgets.** "Invariant" needs its solver named. `max_iter` binds under TRF on three fixtures (reader S). Cr₂WO₆ at 150 K crawls under TRF through ten continuations of 400 evaluations (`docs/wp/1929-*.md:255-256`).

**Verdict:** holds for option 3 inside WP-1542 (the Le Bail WP); weak for the budgets as invariant under both drivers.

**Would settle it:** the margin test run under LM and TRF.

**Revised pick after the review.** Option 3 inside WP-1542, judged against the true-structure Rwp and not against 100 cycles. The budgets become invariant only with a margin test under both LM and TRF.

**Rows.** Invariant, margin test owed: `StageSpec:max_iter`, `run_least_squares:max_iter`*,
`NFEV_PER_ITERATION`, `_INNER_MAX` (its comment is two decades off, appendix item 6). Tier 3:
`StageSpec:lebail_cycles` (fails #740), `LEBAIL_CONVERGED_REL` (the opt-in multi-pass stop;
one family, LaB₆ with cBN), `cherry_pick:fallbacks`* (restates the defaults for old history
nodes; it should import them). Caller: `_fit_lebail_alternation`*.

---

## B12. Pick verbs and opt-in verbs

**The decision.** Three verbs need a ruling. `auto_background` drops the evidence behind its
pick. `solve_magnetic` sets its margins on a ΔBIC built from the raw point count, and on one
unmeasured tie-break. `profile_fraction` raises a warning whose existence turns on a chosen
number.

**Context.** *`auto_background`* picks P-spline knots from a hump score (`HUMP_TRIGGER`
0.05), adds an air-scatter term from a nested-fit gain (`AIR_SCATTER_TRIGGER` 0.3), or picks
a Chebyshev order by a scan. No default path calls it (grep this session, GUI included), but
the skill tells agents to (`SKILL.md:62`, `:87`). It returns the background alone, and the
scores are dropped (`background/auto.py:88-127`, read). The record allows a pick verb only if
the whole ranking travels with the pick. On the thresholds (per reader B): the hump score
reads 0.047 with a real hump and 0.043 without, so 0.05 cannot separate them; the air
trigger misses real low-angle rises (#636); the whiteness stop fired on none of six real
fixtures.

*`solve_magnetic`* returns every trial with its ΔBIC and magnetic R (`MagneticSolution.trials`,
read), so its ranking travels. Its ΔBIC uses the raw point count
(`strategy/magnetic.py:1200`, `:2419`, read). rietx's own `delta_bic` docstring says that
lets any χ² gain outvote the penalty on correlated powder residuals (#270). The tie widths,
6 and 10, are Kass & Raftery's bands applied to that inflated ΔBIC. `SOLVE_TIE_R_MAGNETIC`
(2 % of R_mag) turns a ΔBIC tie into "solved", and its comment calls it "a chosen margin, not
a measured one" (read). `SOLVE_D_MIN` = 1.5 Å merges candidates as indistinguishable even
where the data reach 0.77 Å.

*`profile_fraction`* warns (`QPA_FRACTION_UNDETERMINED`) when an admissible weight fraction
lies more than 2 half-widths outside its esd interval. The 2 is "chosen, not measured",
between controls at 0.79 or less and a synthetic two-basin case near 75
(`schemas/fraction.py:28-35`, read). The range itself rides in the result.

**Options.**
1. `auto_background`. (a) Return the evidence beside the pick, in a small result. It breaks
   the examples and two skill rows. (b) Tier the verb `caller` as it stands; this fails the
   record's travel clause. (c) Demote the thresholds to reported scores with no pick.
2. `solve_magnetic`. (a) Use N/f² in its ΔBIC, as `compare_freed` does, and measure how many
   verdicts change on Cr₂WO₆ and LaMnO₃. (b) Demote the R tie-break: a ΔBIC tie stays a tie,
   the solve abstains, and R_mag is reported. (c) Set `SOLVE_D_MIN` from the data's d range.
3. `profile_fraction`. (a) An info record stating the excess for every profile, the
   record's rule where a threshold decides whether a code exists. (b) Keep it.

**Practice.** GSAS-II's background order is the user's; it reports Durbin-Watson and acts
on nothing (`GSASIIstrMath.py:4995`, reader B checked). GSAS-II and FullProf users solve
magnetic structures by hand and compare the fits themselves (recalled).

**Recommendation.** 1(a), 2(a) with 2(b) and 2(c), and 3(a). Each keeps the verb and fixes the
part that fails. I would change my mind on 1(a) if you prefer agents to call `diagnose()`
and `select_chebyshev_order()`, which already return the evidence; then 1(b), with the
docstring pointing there.

**The case against**, from a fresh-context judge (the `generality-review` role).

**Review: Wrong in the brief.** "Tier 2 once the count is N/f²" (`draft.md:607`, and the rows' notes) contradicts the record's own worked example. Schwarz and the Kass-Raftery bands are cited, but "the effective sample size N/f² is rietx's own" (`docs/milestones/generality.md:40-42`). A band applied to rietx's N/f² stays tier 3.

**`auto_background`.** 1(a) holds. The threshold evidence is synthetic. The 0.047 against 0.043 is WP-1130's planted 40-count hump. #636's rise is a synthetic capillary pattern (`inventory.json`). The brief's "real" means planted.

**`SOLVE_D_MIN`, 2(c).** The magnetic signal dies with the form factor, not the data's d range. In rietx's own table, Mn³⁺'s ⟨j₀⟩ (the magnetic form factor) is 0.39 at d = 1.5 Å and 0.04 at 0.77 Å (run this session). So magnetic intensity falls about 100×. A limit taken from the data's range would split classes on reflections with no magnetic intensity. A magnetic refiner would set it where that intensity falls under the noise.

**`profile_fraction`, 3(a).** The 2 sits 2.5× above the controls and 37× below the trace case (`schemas/fraction.py:28-35`). That gap is wide, but it is one synthetic family. 3(a) follows the record.

**Verdict:** holds for 1(a), 2(a), 2(b), 3(a); fails for the tier-2 rows; weak for 2(c).

**Rows that differ:** `SOLVE_TIE_DELTA_BIC`, `SOLVE_K_TIE_DELTA_BIC`, `K_VECTOR_UNSEPARATED` and `MAGNETIC_SUBGROUP_PREFERRED` stay tier 3.

**Revised pick after the review.** Unchanged for 1(a), 2(a), 2(b) and 3(a). The four ΔBIC rows stay tier 3. Drop 2(c); set `SOLVE_D_MIN` where the form factor falls under the noise, in a follow-up.

**Rows.** `auto_background`'s thresholds, tier 3, kind 2 (15): `AIR_SCATTER_TRIGGER`,
`HUMP_TRIGGER`, `_KNOT_STEP_HUMPY_DEG`, `_KNOT_STEP_SMOOTH_DEG`,
`AUTO_BACKGROUND_SEED_PERCENTILE`, `auto_background:lambda_smooth`*,
`BackgroundPSpline:lambda_smooth`*, `background_envelope:quantile`*,
`background_envelope:window_deg`*, `diagnose:air_gain_polynomial_terms`*, `peak_mask:3.0`*,
`peak_mask:baseline_lambda`*, `select_arpls_lambda:dw_floor`*,
`select_chebyshev_order:dw_stop`*, `select_chebyshev_order:max_order`*. Tier 1:
`_MIN_FIT_CHANNELS`, `profile_fraction:theta_mid`*. Invariant: `arpls:max_iter,tol`*,
`_walk:bracket_growth`*. Caller: `auto_lambda`*, `solve_magnetic`*, `build_pawley_restraint`*,
`compile_origin`*, `anti_bump_restraints`*. Magnetic, tier 3, rare feature:
`SOLVE_TIE_DELTA_BIC`, `SOLVE_K_TIE_DELTA_BIC`, `K_VECTOR_UNSEPARATED`,
`MAGNETIC_SUBGROUP_PREFERRED` (tier 3 even with N/f², which is rietx's own count; corrected after review); `SOLVE_TIE_R_MAGNETIC` (demoted
to kind 2); `SOLVE_D_MIN` (tier 1 once derived from the data); `SOLVE_K_OFFSET_MARGIN_DEG`,
`SOLVE_K_TRIALS`, `SOLVE_MAX_CONTINUATIONS`, `SOLVE_MINIMUM_RTOL`, `SOLVE_RELEASE_FRACTION`,
`SOLVE_SEED_MU_B`, `SOLVE_SEED_TILT`, `SOLVE_TOP_K`. Fraction profile:
`QPA_FRACTION_UNDETERMINED` and `FRACTION_PROFILE_EXCESS` (demoted to kind 3),
`default_fwhm_grid:top`* tier 3. Pawley mode (opt-in), tier 3, LaB₆ only:
`PAWLEY_OVERLAP_FWHM_FRAC`, `PAWLEY_OVERLAP_LAMBDA`, `build_pawley_restraint:off_data_scale_floor`*.
`MODEL_FAR_FROM_DATA_RWP` tier 3: it gates `solve/cost.py:477`'s refusal of an extraction, and
sits in the gap between honest bad fits at Rwp 0.2-0.5 and the zero-scale attractor at
0.99999 (WP-1028).

---

## B13. Hand-off of constants that only gate a diagnostic

**The decision.** Send 58 rows to the audits of the codes or report fields they gate.
Reversible: each is one owner change in the table.

**Context.** The WP's non-goal gives a literal that gates a diagnostic to WP-2005 (the audit
of `refine.py`'s codes). I checked every row's read sites with grep. 34 go to WP-2005. 15 go
to WP-2004 (report-facing numbers): seven `diagnose()` constants that feed no code, four
identifiability caps, the tick-row cut, and three statistics constants no reader proposed.
9 go to WP-2007 (the indexing audit), because `flag_ghosts` drops flagged peaks from
indexing's usable list. Eight constants stay here because they also gate an action:
`HUMP_MIN_WIDTH_MULT` (B9), the envelope's window and quantile and the air-gain polynomial
(B12), `BOUND_HIT_ESD_FRAC` and `BOUND_HIT_COS_MIN` (B16), `MODEL_FAR_FROM_DATA_RWP` (B12) and
`LEBAIL_CONVERGED_REL` (B11). `CORRELATION_GUARD`'s three rows came here from B7. Reader R's
claim that `MODEL_FAR_FROM_DATA_RWP` reaches the series ladder is false; the one reader of
`usable` is `solve/cost.py:477`.

**Options.** (a) Hand off as the table at the end says. (b) Tier them here: 58 approvals
with no action to judge. (c) Send the no-code `diagnose()` constants to WP-2005 instead.

**Recommendation.** (a).

**The case against**, from a fresh-context judge (the `generality-review` role).

**Review: Checked.** `MODEL_FAR_FROM_DATA_RWP` reaches `usable` (the fit-can-be-read flag) only through `solve/cost.py:477`. It is the only error-level code in `refine.py` (`:8093`), so no sibling threshold gates that refusal. Nothing acts on `CORRELATION_GUARD`'s findings (`strategy/staged.py:1940-1956`). The magnetic pairing reads its own covariance (`strategy/magnetic.py:1613-1622`).

**Case against.** The hand-off sends rows behind a gate. The record lets you cancel WPs 2005-2007 after 2004 (`docs/milestones/generality.md:228-238`). The 43 rows sent to 2005 and 2007 could then stay `unaudited` indefinitely, on a baseline that only shrinks. 2004 is not behind the gate. The WP's non-goal places them, so (a) is right on the rule. The handover should state the consequence.

**Verdict:** holds.

**Would settle it:** whether the gate decision also decides these 43 rows.

**Revised pick after the review.** Unchanged. If WPs 2005-2007 are cancelled at the gate after 2004, these 43 rows need another home.

---

## B14. Hand rows: how rows the walk cannot see enter the table

**The decision.** The route by which 91 hand rows reach the audit table. The table's test
holds every row equal to something the walk sees, so a hand row cannot enter as written.

**Context.** The walk sees module-level numbers, tuples of numbers, and defaults at listed
seats. It misses 40 inline literals and numbers inside dicts or arrays, 16 defaults at seats
it does not list (preset constructors, `Atom`, `Geometry`, `run_least_squares`), and 35
actions with no record field of their own. Of the 91, 50 are tier 1, tier 2 or invariant
(division guards, a 1e-12 start nudge, a pole tolerance, the Kα doublet table), 7 are
caller verbs, and 34 carry a judgement in another class. Four kept actions have no record
field: the collapse restore, the cell clamp, the Stephens strain seed, and which σ rule
fired.

**Aim.** Every action recorded, and a retune that would move an answer fails a test.

**Options.**
1. Lift everything. Each literal becomes a named module constant, each default seat joins
   `DEFAULT_SEATS`, and each kept action without a field gets one (`StageResult`: the
   collapse restore, the cell clamp, the strain seed; `RefinementResult`: the σ rule, with
   counts). Cost: 40 lifts, about 8 seats, 4 schema fields, each field with its writer
   named. Undoable.
2. Record hand rows only in the WP file. No code. Nothing catches a retune, and "every
   heuristic has a row" stays false for 91.
3. Mixed. Option 1 for whatever a retune could turn into a different answer: the tier-2 and
   tier-3 numbers (about 20 lifts), the judged defaults (about 8 seats) and the four fields.
   The WP file lists the tier-1 floors and invariant internals.

**Practice.** None outside rietx; no other code keeps such a table.

**Recommendation.** Option 3. It guards what can drift and spends nothing on what cannot. I
would change my mind if you want the table complete by construction; then option 1.

**The case against**, from a fresh-context judge (the `generality-review` role).

**Review: Case against option 3.** The record's acceptance names every threshold constant and every action, held to the tree both ways by a meta-test (`docs/milestones/generality.md:249-253`). Fifty rows listed only in a WP file are invisible to the guard, so a later retune passes silently. The batch's own tier-1 list shows the risk of tiering by eye.

**Rows that differ.** `bragg_brentano:ka2_ratio` is not physics. 0.5 is the 2j+1 degeneracy ratio. The preset's docstring says measured ratios run a few percent above it and that a monochromator clips it (`schemas/instrument.py:2507-2511`). `mccusker_default` does not free it, so a default fit holds it as an instrument fact. That is B9's recorded assumption, with Hölzer et al. (1997) as the tier-2 source. `lorentz_polarization` is tier 1 as a formula. Its input K is a held assumption (B9).

**Verdict:** holds.

**Would settle it:** your stance on completeness, and a re-tier of the Kα2 row.

**Revised pick after the review.** Unchanged. The Kα2 ratio moves to B9 as a recorded assumption, tier 2 (Hölzer et al. 1997).

**Rows.** This class holds the 21 hand rows with no other decision. Tier 1:
`pspline_penalty_scale`*, `lorentz_polarization`*, `build_pawley_restraint:group_scale_floor`*,
`compile_model:fcj_sizing_from_moving_paths`*, `compile_model:reflection_floor_deg`*,
`lebail_update:floors`*, `TEXTURE_SAMPLE_PSI_DEG`*, `_feasible_start:trf_nudge`*,
`brindley_tau:series_switch`*, `_psd_pinv:magnitude_inversion`*, `Refinement._final_compile`*,
`mode_fixed_column`*, `ExtraComponent:fwhm_floor_repair`*, `bragg_brentano:ka2_ratio`*,
`Phase:off_state_defaults`*, `PreferredOrientation._r_bound_is_reachable`*,
`_MODE_SUBSTITUTES`*. Tier 2: `_LAUE_COEF`* (Sabine 1988), `_KA_DOUBLETS`* (Hölzer et al.
1997). Invariant: `CompiledPhase.skip_extinction`*, `_formula_units:tol`*. The other 70 hand
rows sit in their classes, marked *.

---

## B15. The substituted magnetic ion and Landé g

A magnetic site that names a bare lanthanide or actinide, with no oxidation state, gets an
assumed ion for its form factor (`crystallography/magnetic/form_factor.py:433`, read). The
info code `MAGNETIC_ION_ASSUMED` records it, on the ordinary CIF read path. For Ce, Eu, Sm
and Yb the assumed ion is the element's only magnetic state, since the other common state
carries no moment; that is physics. Pr, Nd, Gd, Tb, Dy, Ho, Er and Tm take the 3+ ion, the
textbook majority, though Pr⁴⁺ and Tb⁴⁺ oxides exist (recalled). For U, Np and Pu the table
picks U⁴⁺, Np⁴⁺ and Pu³⁺ as a "common default", uncited. A refiner of a uranium
intermetallic chooses U³⁺ or U⁴⁺ from chemistry the pattern does not carry. The moment error
from a wrong ion is unmeasured. `assumed_lande_g` derives g from Hund's rules for the
assumed ion, which is physics.

**Recommendation.** Split the table by element. Tier 1 for Ce, Eu, Sm, Yb. Tier 2 for the
other lanthanides once a citation is added (Jensen & Mackintosh 1991, recalled), otherwise
tier 3. Demote U, Np and Pu to the refusal that lists the element's ions (kind 3).
`assumed_lande_g` tier 1. The table lives in WP-2006's directory; this WP tiers it because
`strategy/magnetic.py` raises its code.

**The case against**, from a fresh-context judge (the `generality-review` role).

**Review: Checked practice.** FullProf makes the user name the magnetic ion and its charge, e.g. `MHO3` (manual, scatterer note, checked). It assumes nothing. GSAS-II 5.8.4 maps a bare element to one ion's coefficients. Bare U equals U³⁺ (`atmdata.py:1706-1709`). Bare Ce equals Ce²⁺ (`:1638-1641`). So the one program that assumes picks U³⁺ where rietx picks U⁴⁺ (`crystallography/magnetic/form_factor.py:459`). That is a default dissent, and it supports demoting the actinides. GSAS-II's Ce²⁺ looks like table coverage rather than a physics claim (inferred).

**Case against the label.** A refusal stops the fit. Kind 3 reports a number and stops, which is different. The ions are enumerable (U³⁺, U⁴⁺, U⁵⁺), and their ⟨j₀⟩, ⟨j₂⟩ and g differ, so the data can score them. That is kind 2: refit with each, rank them, pick none.

**`assumed_lande_g`.** Hund's-rule g describes the free ion's ground multiplet. For Sm³⁺ the dipole form, coefficient 2/g − 1 = 6, is known to be poor because of J-mixing (recalled).

**Verdict:** holds for the split; weak for the refusal's label and for Sm under tier 1.

**Would settle it:** a ranked refit of a uranium compound with each ion. For Sm, a citation for the dipole form's validity, or Sm out of tier 1.

**Revised pick after the review.** Split as proposed. For U, Np and Pu: kind 2 (refit with each ion and rank them) or a refusal that lists the ions. Sm leaves tier 1 until a citation covers its dipole form.

---

## B16. The bound test

`bound_findings` decides whether a parameter's limit carried load. Under the default LM
driver at 128 columns or fewer (`BVLS_MAX_COLUMNS`) it reads the exact active set. Elsewhere
it asks for two things: the value within a hundredth of an esd of the limit
(`BOUND_HIT_ESD_FRAC`), and the residual not orthogonal to that column (`BOUND_HIT_COS_MIN`,
1e-4). It feeds the `BOUND_HIT` and `FLOOR_HIT` codes (WP-2005's) and the `at_bound` field.
In a single default fit nothing acts on it (I read the consumers). Two consumers act:
`profile_interval`, a caller verb, goes one-sided at a bound and reuses `BOUND_HIT_ESD_FRAC`
(`strategy/parameter_interval.py:172`, read); `multi.py`'s parametric test holds at-bound
columns (WP-2003's). WP-1434 measured 32 binding cases on FAP and Si SRM 640c. The esd
threshold sits 13 times above the largest binding gap (7.7e-4 esd) and 236 times below an
early stop (2.36 esd).

**Recommendation.** Keep both thresholds at tier 3, with a third family in the second pass
under TRF or above 128 columns. `profile_interval:one_sided`* tier caller.

**The case against**, from a fresh-context judge (the `generality-review` role).

**Review: Checked.** 1e-2 sits 13× above the largest binding gap and 236× below the early stop (`strategy/staged.py:1690-1702`).

**Case against.** The upper margin rests on one synthetic early-stopped case: the `make_lab6` sweep at 2.36 esd. Nothing measured sits between 7.7e-4 and 2.36 esd. A TRF fit stopping 0.1 esd short of a bound is covered by no measurement. The binding side has two real families, FAP and Si SRM 640c. The esd is `stderr_internal`, which carries f (`optimize/least_squares.py:504`, `:2848`). If B4 removes f at that seam, the 13× margin falls to 13/f: 6× on FAP (f = 2.15), under 2× at NAC's f = 8.07 (arithmetic; that B4 would touch this seam is inferred).

**Verdict:** holds.

**Would settle it:** a third family under TRF with ftol swept, with gaps quoted in plain esds.

**Revised pick after the review.** Unchanged, with the margin re-measured in plain esds if B4 lands.

---

## Added after the handover's code review

A review of the branch's diff (`/code-review high`) found that nine of the 157 rows landed
without approval did not meet their tier. They are back at `unaudited`, and each joins a
class above:

- `optimize.blocked.DENSE_JACOBIAN_MAX_BYTES` joins **B10**. It switches a large series from
  the dense to the blocked solve automatically. The two paths agree to 6.4e-6 esd, and the
  test allows 0.01 esd. That is invariant within a margin, and the record's precedent for the
  class was bit-identical. Whether a tested margin qualifies is part of B10's reading.
- `schemas.instrument.Source:polarization` (0.5) joins **B9**'s recorded assumptions. 0.5 is
  right for a beam with no monochromator. A lab file with a diffracted-beam monochromator
  and no declared polarisation is fitted at 0.5, which biases intensities and Biso. The
  package's own presets compute K for a graphite monochromator.
- `optimize.statistics.MAX_SHIFT_CONVERGED` joins **B13**, to WP-2004. Its docstring says it
  sets the level of one report sentence and gates nothing, the same property as the three
  statistics constants already sent there.
- The six `background.auto.auto_background` defaults join **B12**. The verb is tiered
  `caller` because no default path in the code calls it. But the agent skill presents its
  P-spline as the default background (`docs/skill/rietx/SKILL.md` ~62, ~87), so every agent
  that follows the skill makes these choices by default. Whether a skill instruction is a
  default path is part of B12's ruling.

The review also changed `refine:backend` from `invariant` to `caller`: another backend can
move a fitted number (fp32 Jacobian columns on Apple MPS, about 1e-13 on jax), and the
optional backends are the caller's to choose.

**Owed, needing no ruling: 17 tier-2 rows rest on citations nobody read this session.** Their
evidence says so ("docstring; paper not on disk"): seven `optimize.lm` constants and four
`optimize.bccg` constants citing Coelho, plus `SCHERRER_K` and five others. The review
reports the TOPAS-Academic V5 technical reference and the Patterson Scherrer paper are in the
local corpus. The next session checks each value against its source and moves any that do
not match back to `unaudited`.

---

## The B13 hand-off table

"Gates" names the code or field the constant decides. Every read site was checked with grep
this session.

| Row | Gates | Goes to |
|---|---|---|
| `BOUND_HIT`, `BOUND_HIT.suggestion` | the code itself (`refine.py:5668`) | 2005 |
| `FLOOR_HIT`, `FLOOR_HIT.suggestion` | the code itself (`refine.py:5668`) | 2005 |
| `schemas.plan.CORRELATION_GUARD`, `PlanSpec:correlation_guard`, `Refinement.run_stage:correlation_guard` | `HIGH_CORRELATION`, `FLAT_DIRECTION` (`refine.py:5668`, `:5741`). GSAS-II lists pairs from max(0.95, 0.99 × the worst \|ρ\|) (`GSASIImath.setHcorr`, checked) | 2005 |
| `strategy.staged.BACKGROUND_ABSORPTION_GUARD` | `BACKGROUND_ABSORPTION`; also aliased as a report threshold (`report/schemas.py:511`) | 2005 (2004 reads it) |
| `strategy.staged.ROUGHNESS_ABSORPTION_GUARD` | `ROUGHNESS_ABSORPTION` | 2005 |
| `refine.AIR_SCATTER_UNDECLARED_FRACTION`, `_SCORE` | `AIR_SCATTER_UNDECLARED` (`refine.py:8557-8558`) | 2005 |
| `refine.DISPERSION_NEGLECT_FRAC`, `_SEVERE` | `DISPERSION_NEGLECTED` and its level (`refine.py:7646`, `:7653`) | 2005 |
| `refine.FLAT_PLATE_BIAS_MIN` | `ABSORPTION_THICKNESS_MATTERS` (`refine.py:6801`) | 2005 |
| `refine.FROZEN_COMPILE_CHI2_REL` | `FROZEN_COMPILE_STALE` (`refine.py:4955`); the fresh χ² is reported either way | 2005 |
| `refine.HARMONIC_ABSENT_FRAC`, `HARMONIC_IMPLAUSIBLE_FRAC` | `HARMONIC_ABSENT`, `HARMONIC_FRACTION` (`refine.py:7899`, `:7907`) | 2005 |
| `refine.LOW_ANGLE_MIN_CHANNELS`, `LOW_ANGLE_UNMODELLED_RATIO` | `LOW_ANGLE_UNMODELLED` (`refine.py:8448`, `:8459`) | 2005 |
| `refine.PAWLEY_UNRESOLVED_REL` | `PAWLEY_OVERLAP_UNRESOLVED` (`refine.py:7475`) | 2005 |
| `refine.RESONANT_ABSORBER_SEVERE_BARN` | `NEUTRON_RESONANT_ABSORBER`'s level (`refine.py:7731`) | 2005 |
| `refine.RESTRAINT_TENSION_SIGMA` | `RESTRAINT_TENSION` (`refine.py:8029`) | 2005 |
| `refine.ROUGHNESS_MIN_DEPRESSION` | `ROUGHNESS_UNCONSTRAINED` (`refine.py:9401`) | 2005 |
| `refine.SIZE_FLAG_SIZE_A` | `SIZE_UNUSUALLY_SMALL` (`refine.py:9305`) | 2005 |
| `refine.STRAIN_FLAG_WIDTH` | `STRAIN_UNUSUALLY_LARGE` (`refine.py:9122`) | 2005 |
| `refine._CENTROID_SITES_NAMED` | the length of `ORIGIN_FIXED_ON_POLAR_AXIS`'s message (`refine.py:6273`); invariant | 2005 |
| `background.diagnostics.DEAD_LEVEL_FRACTION`, `DEAD_LEVEL_WINDOW_DEG`, `DEAD_WEIGHT_RATIO_MIN`, `_DEAD_INTERVAL_DECIMALS`, `_DEAD_REPAIR_PASSES` | `PATTERN_DEAD_CHANNELS` (`refine.py:8266`; also at read, `io/readers.py:209`, WP-2006's) | 2005 |
| `background.diagnostics.CUTOFF_MIN_DEG` | `PATTERN_DEAD_CHANNELS` (as `max_run_deg`); also `diagnose()`'s cutoffs | 2005 |
| `background.diagnostics.SAMPLING_HEIGHT_FRACTION`, `SAMPLING_PROMINENCE_SIGMA` | `PATTERN_UNDERSAMPLED` (`refine.py:8246`); also `diagnose()`'s peak census | 2005 |
| `background.diagnostics.COVERAGE_INFLATION_THRESHOLD`, `COVERAGE_SMOOTH_DEG` | no code: the `counting_coverage` field of `diagnose()` | 2004 |
| `background.diagnostics.CUTOFF_FRACTION`, `CUTOFF_INTERIOR_FRACTION`, `CUTOFF_ONSET_FRACTION`, `CUTOFF_PLATEAU_DEG`, `CUTOFF_SMOOTH_DEG` | no code: the `signal_cutoffs` field of `diagnose()` | 2004 |
| `refine.MAGNETIC_TICK_PURITY` | no code: which tick row a reflection draws on (`RefinementResult.ticks`); its comment and code disagree (appendix item 2) | 2004 |
| `optimize.identifiability.EXCHANGE_MIN_LOADING`, `SOFT_MODES_K`, `SOFT_MODE_MIN_LOADING`, `TOP_CORRELATIONS_K` | report caps read by `report/identifiability.py` | 2004 |
| `optimize.statistics.EFFECTIVE_OBS_ALPHA`, `OBS_PER_PARAMETER_MIN`, `OBS_PER_PARAMETER_PREFERRED` | `DATA_SUPPORT_LOW` and the data-support record (`refine.py:8229-8239`); no reader proposed them | 2004 |
| `background.diagnostics.GHOST_ESD_MAX_DEG`, `GHOST_MATCH_K`, `GHOST_MIN_PARENTS`, `GHOST_N_PARENTS`, `GHOST_RATIO_RANGE`, `GHOST_RATIO_TOL`, `GHOST_TOL_DEG` | `flag_ghosts`, which drops a flagged line from `PeakList.usable()` (indexing) | 2007 |
| `background.diagnostics._ANODE_MATCH_TOL`, `_KBETA`* | `identify_anode` and the Kβ positions `flag_ghosts` reads | 2007 |

Count: 34 to WP-2005, 15 to WP-2004, 9 to WP-2007.

---

## Appendix. Findings that are not decisions

The Write tool refused a separate `findings.md` ("subagents should return findings as
text"), so the findings live here. "Verified" means I read the lines or ran the check this
session; "unverified" means a reader's claim I did not re-check.

1. `model/profiles/fcj.py:70` `MAX_NODES = 64` binds below about 6.5° 2θ on lab
   Bragg-Brentano data: 0.19 % of peak height at 5°, 0.71 % at 4°, 2.8 % at 3°; uncapped
   ≤ 0.06 %. Verified (`fcj_low_angle.py` beside this file, run this session).
2. `refine.py:768-777` says a reflection between 5 % and 95 % magnetic draws on neither tick
   row; `refine.py:7020-7023` puts every reflection under 95 % on the nuclear row. Verified.
3. Stale "Biso in [0, 25]" at `params/vector.py:1032` (`tie_window`'s docstring);
   `viz/compare.py:144, 265, 267, 419, 421` still build atoms with Biso in [0, 25], a box the
   schema dropped in WP-1534. Verified.
4. `optimize/statistics.py:1142` `MAX_SHIFT_CONVERGED` has no reader in src; only a docstring
   (`schemas/results.py:122`) names it. Verified.
5. `optimize/bccg.py:133` `bccg.solve` has no caller; `optimize/lm.py` uses only
   `bccg.projected_cg` (`:724`, `:745`). Verified.
6. `optimize/lm.py:129-132` says `_INNER_MAX = 18` reaches λ ≈ 1e14. From the comment's own
   premise (floor 0.1, ×10 a failure) 18 failures reach 1e17; from λ = 0 the 18th trial runs
   at 1e16. Verified by arithmetic.
7. `optimize/least_squares.py:2239-2240` calls the size cap "the tier-1 bound"; its 2 nm
   floor is from one private archive (`params/vector.py:886-898`). Verified.
8. `strategy/magnetic.py:185` `SOLVE_D_MIN = 1.5` Å is fixed whatever the data reach; BT-1
   LaMnO₃ reaches 0.77 Å and HB-2A Cr₂WO₆ 1.34 Å. Arithmetic verified; λ and range are
   reader S's.
9. `strategy/magnetic.py:1200`, `:2419` use a raw-N ΔBIC against `report/layer2.py:193-210`'s
   own warning (#270). Verified.
10. `strategy/magnetic.py:138-144` `SOLVE_TIE_R_MAGNETIC` is "a chosen margin, not a
    measured one" and decides "solved". Verified.
11. `schemas/structure.py:400-407` says a moment at `MOMENT_FLOOR_MU_B` is held; no
    single-fit code reads it to hold (its readers: `strategy/magnetic.py:331`,
    `sequential.py:905`, `report/magnetic.py:288`). Verified.
12. The collapse restore, the cell clamp and the Stephens strain seed leave no `StageResult`
    field (`refine.py:4114-4133`; the clamp leaves only `CELL_RUNAWAY`; `strain_seeded` at
    `refine.py:3865-3869` does not reach the result built at `:4275`). Verified.
13. No result field says which σ rule fired, and nothing records the floor
    (`schemas/results.py:1690-1694`). Verified.
14. `background/auto.py:107-125`: `auto_background`'s `wavelength=` and `source=` change
    nothing in the returned model. Verified.
15. `background/diagnostics.py:229` `STEPS_PER_FWHM_MAX` is read by no code in src or tests.
    Verified.
16. `schemas/plan.py:53-65`: the 0.03-esd bound predates a Jacobian change, and no test
    asserts it (`tests/test_validation_matrix.py:233-261` only requires it declared).
    Verified.
17. `schemas/plan.py:89` `lebail_cycles = 3`: #740 gives Rwp 4.56 % at 3 cycles against
    1.63 % at 100. Verified.
18. One literal, two proposed names: `optimize/least_squares.py:1000` is both
    `_DegenerateCellGuard:penalty` (R) and `:penalty_factor` (O). Verified.
19. One default, two proposed names: `Geometry.packing_fraction` (R) and
    `Geometry:packing_fraction` (P), `schemas/instrument.py:1266`. Verified.
20. `run_least_squares:ftol` was proposed by readers O and S. Verified.
21. 0.95 is both `STATIONARY_ANGLE_LEVEL` (`optimize/least_squares.py:565`) and
    `PARAMETER_INTERVAL_LEVEL` (`schemas/interval.py:27`), with no test equating them.
    Verified.
22. The arPLS λ of 1e7 is spelled at four sites (`background/select.py:66, 82`,
    `background/estimators.py:49`, `viz/compare.py:622`). Verified.
23. The occupancy box [0, 1.5] is spelled six times (`schemas/structure.py:500` verified; five
    reader sites in `crystallography/cif.py`, `io/recipe.py` and three project importers
    unverified).
24. `_formula_units`' 0.02 twice, `_CONVERGED_RUNS` twice, `_Q_WINDOW` inline at
    `lm.py:553`. Unverified.
25. WP-1110's text says the window covers phases under 1σ; the constant is 3. Unverified.
26. Reader claims found false: `MODEL_FAR_FROM_DATA_RWP` reaching the series ladder (R; the
    reader of `usable` is `solve/cost.py:477`); a `RefinementResult.weighted` field (P; none
    exists). Verified.
27. Not chased: a 12° synthetic dropout returns a one-channel dead run at 92.0° (reader B);
    the whiteness stop fired on none of six real fixtures (reader B). Unverified.
28. TOPAS was checked for no row this session; every TOPAS statement above comes from a
    docstring or is recalled.
