# WP-2002 rulings, and the second round of briefs

The maintainer answered the batch (`batch.md`) on 2026-10-19. Four classes are ruled and
B1 is confirmed. For nine items the answer was a question back. This file records the
rulings, then the plain-language briefs written in reply to those questions. The briefs
are the text the maintainer read before answering. The next session reads the answers
against this wording. Three picks changed from `batch.md`'s revised picks: B4 (keep f), B5
(drop and report) and B9 (a "geometry not stated" state). Each is marked.

"Second pass" means measuring a threshold on three unrelated dataset families after the
ruling (`batch.md`, opening paragraph).

## Rulings received (2026-10-19)

- **B1** (absent-phase hold, release, collapse restore): confirmed ("yes I think"), with
  a request to restate what the hold is. The restatement is below; it changes nothing.
  `PHASE_SUPPORT_SIGMA` stays tier 3 for the second pass.
- **B7** (default plan): the declared geometry picks the plan. "If the user knows it's BB
  geometry, that information should lead to the preset. If unknown, we should not free
  factors which might not be appropriate for a given refinement." So a Bragg-Brentano
  instrument gets displacement freed with the zero, and an unknown geometry gets
  `mccusker_default`, which frees nothing geometry-specific. It is built in a follow-up
  WP, not yet filed (see B9's geometry question). That WP must keep a calibrated
  instrument's Kα2 ratio and axial terms fixed, since `lab_bragg_brentano` frees those.
  The intermediate-tolerance half of B7 was not asked separately: the batch's option 1
  (invariance test in plain esds) stands as the plan.
- **B10** (numerical settings): "yes, tier 1". A numerical setting is tier 1 when a test
  bounds its error over the claimed domain. The six solver-path switches stay tier 3
  until refits of three families on either side give one answer. One sentence goes into
  `docs/milestones/generality.md` § The rule, under tier 1.
- **B12** (pick and opt-in verbs): "yes to all". 1(a) `auto_background` returns its
  evidence beside the pick. 2(a) `solve_magnetic` uses N/f². 2(b) its R tie-break is
  dropped, so a ΔBIC tie abstains. 3(a) `profile_fraction`'s warning becomes an info
  record. The skill's instruction is a default path. The four ΔBIC rows stay tier 3, and
  `SOLVE_D_MIN` goes to a form-factor follow-up (the revised pick).
- **B14** (hand rows): option 3, "yes if I understand correctly: you want to make more
  variables visible to the demotion tests?". The reply corrected the reading. The test is
  the audit table's own (`tests/test_audit_table.py`), and demotion is a separate step.
  The substance the maintainer agreed to is unchanged. The next session should confirm
  in a line that the yes stands.

## Rulings received, second round (2026-10-19)

- **B4**: option 1. "We should report the more accurate number, but also report the one
  comparable to other codes." f stays on every reported esd, and the textbook esd is
  reported beside it. The manual must explain the two numbers plainly, with a comparison
  against GSAS-II, FullProf (SCOR) and TOPAS, and the "switching from another code" pages
  must say it too.
- **B3**: Suortti seed agreed (two-start test, then GSAS-II's 0 unless 0.3 is closer to a
  reference). Stephens seed agreed (tier 3 until a second dataset compares the starts; the
  seed recorded in the result).
- **B8, cell clamp**: agreed. On a runaway the cell goes back to its stage-start value and
  is held for that stage, with a record entry.
- **B9, limits**: "no need to impose chosen limits on quantities that remain physical.
  Unlimited occupancy is fine. We can give a warning. The flexibility can be useful." So
  occupancy loses its 1.5 ceiling and a warning fires above 1. The session reads the
  principle as covering March-Dollase r too: its 0.15 floor goes, and r keeps only the
  pole floor `MARCH_R_MIN`. A limit that keeps a value physical or away from a pole stays.
- **B9, geometry**: a "geometry not stated" state, which also tells the user to state the
  geometry. It joins the B7 follow-up WP.
- **B11**: agreed (Le Bail converge-with-cap in WP-1542; budgets treated as not affecting
  the answer once a test confirms the margin under both solvers).
- **B16**: agreed (both numbers tier 3, a third dataset under TRF in the second pass).
- **B1**: "yes, but it should be an option, not mandatory. A caller should be able to set a
  different threshold." Asked whether other codes do this.

Asked back, answered in § Third round below: B5 (what is accurate, the root cause, other
codes), B8's cell window (tier 2?) and size floor (a warning instead?), B7 (does the
session agree with the geometry take?), B2 (is the turn common enough to keep; is the
stationary-angle test a demotion?). Not yet answered: B6, B13, B15, and the B14 confirmation.

## Rulings received, third round (2026-10-19)

Answers to § Third round below.

- **B5**: "usually this is often not a big deal, as the other codes evidently show. We
  should fix anything obviously wrong, warn during ingestion, and give the option to
  correct. Don't spend too much effort on this." So option 4's classifier is not built.
  The obviously wrong part is today's floor, which hands a σ ≤ 0 channel about a million
  times its neighbours' weight. The ruling as the lead reads it: a σ ≤ 0 channel takes no
  weight by default (GSAS-II's fxye rule), the reader warns with the count and the lines,
  and a reader option keeps such channels at σ of one count instead. Built in WP-1952,
  forwarded there.
- **B1**: on by default. The threshold and an off switch become a caller's option
  (`phase_support_sigma`, a plan field, `None` for off).
- **B2**: keep the turn (tier 3, approved). The stationary-angle test was first ruled a
  demotion on a brief that misstated its cost. The session then found two errors in that
  brief (WP-1929's record): without the test the moment sizes' esds become stopping-point
  artefacts (0.0015 and 0.0011 μB with the angle columns left out; 0.031 and 0.159 μB with
  them in, and 0.0035 to 0.47 μB as the convergence tolerance moved), and near the
  direction the ordinary esd can exclude the symmetric direction when the χ² ridge to it is
  too low to. Re-asked, ruled **option 2** (2026-10-19): keep the test and its effect on
  the other esds; the angle reports its distance from the symmetric direction with the
  likelihood interval (`profile_interval`, run automatically on the answer-producing stage
  for each angle the test passes) in place of no esd.
- **B7**: agreed, with the two additions; in WP-2015.
- **B8**: agreed. The cell window is tier 2 (TOPAS, Tech Ref § 2.17). The 2 nm size floor
  is removed; the range backstop stays; `SIZE_UNUSUALLY_SMALL`'s message gains the
  Bragg-model caveat.
- **B9**: the reading is correct for March r. Its 0.15 floor goes, `MARCH_R_MIN` stays.
- **B6**: yes. **B13**: yes. **B15**: yes.
- **B14**: asked to explain again, and re-explained in the session (the table's scanner
  sees module-level numbers, listed seats and record fields; option 3 lifts what a retune
  could turn into a different answer). Asked whether option 1 was better, the lead said
  no: the scanner still misses the next inline number, so option 1 is complete only for
  today's 91, and its ~50 extra rows are guards that dilute review. The risk in option 3
  is misclassification; the list of ~50 goes to the generality reviewer at handover, and a
  flagged row moves to the lifted set. **Option 3 confirmed** (2026-10-20). The lead would
  switch to option 1 if that review finds several misclassified rows.

## Rulings received, fourth round (2026-10-20)

The previous session's handover left five questions and three confirmations. This round's
briefs are in the session transcript; the measurements behind them are summarised here.

- **Confirmations.** The emission-line weight widening stands, and so does the rename of
  `QPA_FRACTION_UNDETERMINED` to `QPA_FRACTION_RANGE`. The interval's cost was re-explained
  and is not yet confirmed.
- **The peak-position limits** (zero shift ±0.5°, displacement and both capillary offsets
  ±1 mm, transparency ≤ 0.05). Asked "check other codes": GSAS-II 5.8.4 and FullProf set no
  default limit on any of them, and TOPAS v9's Table 2-1 has no row for them (its macros'
  own limits, in `Topas.inc`, are not on this machine). The brief recommended keeping them,
  saying a removal traded a flagged 1117 ppm cell error for an unflagged 5129 ppm one. The
  maintainer: "This sounds like the type of overfitting we're trying to avoid. Shouldn't we
  not limit, but loudly report degeneracies?" Measured in reply (11-BM NAC, zero and both
  capillary offsets free, R = 1000 mm): bounded, the cell lands −1097 ppm from the
  acceptance band's centre with an esd of 2612 ppm and seven warnings; unbounded, −5109 ppm
  with an esd of 2579 ppm and six warnings, among them two `FLAT_DIRECTION` findings naming
  the cell and an offset. So the brief's "unflagged" was wrong, and the bound only made the
  cell look 4.6 times closer than the data support. **Removed**: the four position
  corrections are unbounded; transparency keeps its physical floor of 0.
- **The TCHZ width limits.** "Keep until next session. Check what other codes do." Checked:
  GSAS-II and FullProf bound none of U, V, W, X, Y; GSAS-II floors the computed Gaussian
  variance and Lorentzian width at each reflection, as rietx does; FullProf substitutes a
  default width when one goes negative; TOPAS's table has no TCHZ row. Next session.
- **`auto_background`'s pick**: option 1, keep the pick at tier 3. Measured before asking:
  the hump score separates lab from synchrotron data rather than detecting a hump (0.10-2.3
  on all 25 lab patterns, 0.036-0.067 on five synchrotron or low-background ones), and on
  seven real patterns refitted four ways no near-trigger choice moved a cell, scale or Biso
  past 0.8 esd. The one choice that mattered (FAP's air term left out, score 0.75) is one the
  pick does not make, and `AIR_SCATTER_UNDECLARED` fires when it is made.
- **Mike Gaultois's second read of the batch** (PR #1050, 2026-10-20): agreed. The cell
  window goes to tier 3 (TOPAS bounds every phase's cell each iteration; rietx bounds a
  barely-seen phase's once per stage, ten iterations' worth). Two premises it named are
  checked: TOPAS's default occupancy limit is 0 to 2·Val + 1 (Table 2-1), so the B9 brief's
  "no default occupancy limit is recalled" was wrong and the removal stands on the
  principle alone; the 0.3-10 000 nm size range is in v9 § 2.17's prose about `CS_L`, not in
  its table, so the citation holds for v9.
- **Answered the same day** (three short questions after the briefs): `OCCUPANCY_ABOVE_ONE`
  is an info record, with no significance gate; every ΔBIC tie in `solve_magnetic`
  abstains, the tied classes listed fewest moment parameters first; the stationary angle's
  automatic interval stays automatic at 20-32 refits an angle. All three as recommended.
- **Two re-tiers the generality reviewer asked for, approved the same day ("yes", "yes").**
  The twelve solver stop constants (Coelho's LM rules `_M_HI`, `_M_LO`, `_Q_TRIGGER`,
  `_Q_WINDOW`, `_LAMBDA_FAIL_FACTOR`, `_LAMBDA_FAIL_FLOOR`, `lm._CONVERGED_RUNS`; BCCG's
  `_CONVERGED_FRACTION`, `_CONVERGED_RUNS`, `_SMALL_FACTOR`, `_SMALL_RUNS`; `_CAUCHY_ARMIJO`)
  move from tier 2 to tier 3 with refits of three families on either side owed, as B10's
  switches. `DENSE_JACOBIAN_MAX_BYTES` joins the six as the seventh solver-path switch.
  `SCHERRER_K`, `BOND_SLACK_ANG` and `STEPS_PER_FWHM_*`, which the reviewer listed beside
  them, were not asked and stay at tier 2 for the second pass.
- **Landed under an existing ruling, not asked again.** The profile walk's four settings
  (`PARAMETER_INTERVAL_CHI2_TOL`, `_MAX_REFITS`, `_SETTLE_RUNS`, `_XTOL`) and the width
  grid's two (`FRACTION_PROFILE_FWHM_MIN`, `_N_FWHM`) moved from `caller` to tier 3 once B2
  option 2 and the skill made their verbs default paths. They are numerical settings, so
  B10's class ruling of 2026-10-19 applies (tier 3 with a domain test owed), and their
  `approved` date is that ruling's.

## Fifth round: asked 2026-10-21, from the owed tests

The 3rd session ran the owed tests and asked five questions. The briefs are in the session
transcript and the PR (#1085); the measurements behind each are in `waiting.md`, by class.

- **Q1. Numerical settings that failed their domain test**, as one class: the peak window's
  area tolerance (2 %), the four FCJ node-rule constants, the reflection-list margin, the
  axial and magnetic window-sizing floors, the origin-fix clip and the texture sphere
  sampling. Each has a measured passing value and a cost (`waiting.md` § B10). Practice
  checked: GSAS-II 5.8.4 computes each peak over 50 FWHM below and 75 above its position
  (`GSASIIpwd.getWidthsCW`), about 0.6 % of a pure Lorentzian's area dropped, and
  recomputes that range at every evaluation.
- **Q2. The bar for an invariance test across a staged plan** (B7's tolerance, B9's Biso
  and harmonic seed): the last stage's frozen compile carries a scatter of up to 0.16 esd,
  part of it the window truncation Q1 decides.
- **Q3. Pitschke's roughness seed**, which shares Suortti's 0.3 and is not start-invariant.
- **Q4. Biso's and the scale's esds when roughness ends switched off**, which depend by
  up to 4.4x on which off point the solver stops at.
- **Q5. The TCHZ width box** (the fourth round's "keep until next session"): its ceilings
  are chosen limits on physical quantities, and GSAS-II and FullProf bound none.
- **Q6. A class for a cap on what a report lists** (the three geometry caps). The record's
  rule has none, so they stay tier 3. Beside it, a defect: the 3.5 Å contact radius also
  bounds the bond search, so a bond past it (Cs–Cl near 3.57 Å) is never found, unnoted.

## Fifth round's answers (2026-10-21)

The maintainer answered on 2026-10-21, with a note beside the six: **widen tier 2's program
comparison to the programs rietx-bench runs** (GSAS-II, FullProf, TOPAS, RIETAN-FP, BGMN,
MAUD, EasyDiffraction).

- **Q1**: asked back. The brief's opening sentence did not parse, and the maintainer asked
  what the other programs do and why rietx does what it does. Re-briefed below.
- **Q2**: asked back: how do RIETAN-FP and BGMN, which also refine in stages, handle it?
- **Q3**: asked back: check the other programs' starting values.
- **Q4**: delegated ("whichever you consider reasonable, this is rare"). The lead chose
  a report over the recommended (b): `ROUGHNESS_UNCONSTRAINED`, which already fires at
  both off states and asks for the block to be dropped, now also says the scale's and
  Biso's esds depend on which off state the fit stopped at. (b), a canonicalising re-solve
  at b = 0, would add an automatic step, a record field and an audit row for a case the
  maintainer called rare. The judge held the choice, measured on one family.
- **Q5**: (a), remove the five ceilings, "confirm with other codes too and let me know".
- **Q6**: "doesn't appear to be a question", read by the lead as agreement with the
  recommendation. Tier 1 gains a cap clause (`generality.md` § The rule): a cap on what a
  report lists is kept once a test shows the report complete inside the cap and its notes
  counting what lies outside. The bond-search defect is fixed in the same change, and the
  three geometry caps move to tier 1. The judge rated the clause's authority weak, since
  the reply could also mean "not mine to decide", so the reading goes back to the
  maintainer as the sixth round's Q4 below.

## Sixth round: asked 2026-10-21, Q1-Q3 re-briefed with the seven programs' practice

The three briefs are below, whole, under § The three briefs as sent. The full practice
tables are `practice.md`. The measurements added this round, on SRM 660c, FAP, cpd-1a and 11-BM NAC
(macOS arm64, `[dev]`, compiled tier on, with other sessions' agents running):

- `WINDOW_AREA_TOL` at 5e-3, about GSAS-II's 0.5 % of a Lorentzian: 0.39, 0.34, 0.43 and
  0.33σ at a point; answers 0.88 esd (LaB6 `u`), 0.23, 0.62 and 0.05; whole fit 1.09, 1.54,
  1.44 and 1.05× today's. Fails both bars on three of four.
- 1e-3 on the last stage only, 2e-2 before it: within 0.001, 0.008 and 0.000 esd of the
  all-1e-3 answer on FAP, cpd-1a and NAC, at 1.91, 1.33 and 1.09× (all-1e-3: 3.49, 2.12,
  1.19×). LaB6 at 1.12× lands with today's setting, 9.2 esd in `axial_sl` from the all-1e-3
  answer, which sits in the mirrored S/L ↔ H/L minimum (WP-2012).
- A closing stage: the protocol at today's windows, then one stage freeing every glob the
  plan freed, recompiled at the answer at 1e-3. Within 0.002, 0.052 and 0.002 esd of the
  all-1e-3 answer on FAP, cpd-1a and NAC, at 2.26, 1.54 and 1.44× (LaB6 1.36×, today's
  basin).
- Biso started at 0.5 and at 1.5 Å² on every atom, largest non-background disagreement in
  plain esd (today's / 1e-3 on the last stage / closing stage): FAP 0.119 / 0.013 / 0.000;
  cpd-1a 0.751 / 0.734 / 0.064 (sample displacement, then cell c); NAC 0.008 / 0.006 /
  0.000; LaB6 9.0 / 9.0 / 9.4 in `axial_sl`, the two starts in the mirrored minima under
  every setting. Tight windows on the last stage alone fix the truncation and not the
  path; the closing stage fixes both on three of four.
- Q1 asked: keep 2 %, tight everywhere, tight on the last stage, or a middle cut. Q2 asked
  the bar, with the closing stage as an option. Lead's pick, joining them: the closing
  stage at tight windows, and a 0.1-plain-esd bar for a staged plan's start test. Q3
  asked again with the finding that no program supplies a Pitschke start; lead's pick (c),
  split the constant. Q4-Q6 came from the handover's reviews: whether the fifth round's
  Q6 answer meant yes, how tier 2 counts a dissenting program, and a backstop for a
  runaway instrument width. Q7 came from the full suite: removing the width ceilings
  moved the brucite TRF fit. All seven wait on the maintainer; the briefs are below.
- A correction to the fifth round's Q5 brief and to this session's report: the TCHZ size
  term is X (Γ_L = X/cosθ + Y·tanθ), so the old ceiling that capped the Lorentzian size
  near 8 nm at Cu Kα was X ≤ 1°, not Y ≤ 1°. The code review caught it in the schema's
  docstring.

## Sixth round's answers (2026-10-21)

The maintainer answered all seven, with a standing instruction: "Please use qualitative
judgment to decide what to do if no clear option." Where an answer leaves a choice open,
the lead decides by the design rules and records the choice here.

- **Q1 and Q2**: Q2 option 3, the closing stage at tight windows with a 0.1-plain-esd bar,
  "if it's consistent with practice", and "I assume this default can be changed through
  options?" Practice, as replied: of the three programs that stage automatically, BGMN
  ends every ladder with a closing run and RIETAN-FP ends with everything refining
  together while its windows move at every evaluation; MAUD has no final cycle. The
  0.1 % cut lies between GSAS-II's 0.5 % and the whole peak BGMN and EasyDiffraction
  compute. The 0.1-esd bar is rietx's own, since no program tests start dependence. The
  option did not exist (`forward.WINDOW_AREA_TOL` is a module constant), so the build adds
  one plan setting, `closing_window_tol`, default 1e-3. `None` drops the closing stage and
  returns today's answers bit for bit, as `intermediate_ftol=None` does.
- **Q3**: (c).
- **Q4**: (a). The cap clause and the three geometry caps' tier-1 rows stand.
- **Q5**: "my intention for tier 2 is, is this thing already validated in a known code
  somewhere. No doubt there will be disagreement. If different codes do things
  differently, we can choose what we do based on our design guidelines and principles,
  but we should probably choose within existing practice unless there are clear reasons
  not to do so." So a dissenting program does not move a statistic, threshold or default
  off tier 2, and both rows (the default solver, the cell-length floor) stay. A choice
  outside the seven programs' range names its reason. An action's judgement ground is
  unchanged: a named dissenter still outweighs a program default as evidence that every
  refiner would act (DESIGN.md § Rules, 1).
- **Q6**: no backstop. "No need to bound these values. I would like callers to set the
  bounds themselves." With a concept to consider: "opt-in sets of bounds and defaults for
  particular scenarios. Instead of setting overfit defaults by default (ahem), we load
  sets of defaults that have been tested on smaller numbers of datasets. This would be
  like sharing a topas .inp, but more flexible or usable." Filed as its own WP. Not
  generalised here: the sample-width backstops (`strain_cap`, `size_cap`, from issue
  #140) stay. Whether they move into such a set is that WP's question.
- **Q7**: (a), with a question: under what conditions would someone use TRF instead of
  LM? Answered from the manual: to reproduce a number measured before 1.8, when TRF was
  the default, or as a second driver to check a minimum. It holds none of LM's
  inequalities (the Stephens cone, texture positivity, the Γ_G² floor), and from a poor
  start it can stop in a basin LM leaves (issue #900). Measured before the build: brucite
  under TRF with every ceiling at the axis width, Rwp 0.17878 and t 0.36, −1.22, 0.40,
  2.29; the no-ceiling control in the same script 0.17891 and t −203.34.

## Seventh round: asked and answered 2026-10-21

The 5th session's handover left two items for the maintainer. The 6th session re-briefed
both in plain words (below, whole) after one new measurement: the synthetic LaB6 round
trip of `tests/test_refine_synthetic.py`, five noise draws, one Gaussian noise vector
shared by both draws (`q1_synthetic.py` in that session's scratchpad). Data drawn at 2 %
and fitted with the closing stage land, against the same data drawn at 1e-3: cell and
zero 0.01 esd apart, W 0.10, the scale 0.19, the background constant 3.4. When the data's
windows match the windows of the fit's last stage, the two fits agree within 0.02 esd on
every non-background row. The background constant sits about 8 esd from truth in every arm,
which is weighting by the observed counts (σ² = y_obs biases the level about one count
low), not a window.

**Answers.**

- **Q1**: option 2, evaluation outside a fit defaults to the closing stage's windows. With a
  question: "we got the different window settings from bgmn and rietan though??" Answered:
  the closing *run* is BGMN's (one last all-free solve restarted from the answer), and
  RIETAN-FP's automatic mode has the same shape; neither changes its window setting
  between stages. RIETAN-FP recomputes its windows at every evaluation with one cut (0.002
  of each peak's height), BGMN computes whole peaks. So two window settings in one fit are
  rietx's own, because rietx freezes windows per stage and they do not, and 1e-3 is
  rietx's measured value between GSAS-II's 0.5 % and BGMN's whole peak. In both programs a
  calculated pattern uses the fit's windows, which option 2 matches.
- **Q2**: option 2, each setting fixed by its kind.

**The lead's choices inside the answers** (the sixth round's standing instruction):

- A stage run by hand (`Refinement.run_stage`, the GUI's single-stage run) takes the
  closing windows by default. The brief proposed it under option 2 and the maintainer did
  not object. A caller wanting the fast stage passes `window_area_tol=WINDOW_AREA_TOL`.
- A recorded `window_area_tol` of `None` keeps meaning the declared stages' 2 %, so every
  history written before this round replays unchanged; only the compile's own default moves.
- The FCJ rule on the closing stage is the first proposal's set (`NODES_PER_FWHM` 12,
  `MIN_NODES` 10, `MAX_NODES` 1024, `SKIP_EXTENT_FWHM_RATIO` 3e-4: worst 0.25 and 0.81 of
  the lab and synchrotron bars), the margin chosen over the cheapest set (11 / 8 / 768 /
  3.5e-4 at 0.95 of the bar): the cost falls on one stage only. It is chosen by the window
  fraction: a compile at windows as tight as `CLOSING_WINDOW_TOL` or tighter samples FCJ
  at the closing rule, so a record's window fraction also says which rule ran.

### The two briefs as sent (2026-10-21)

#### Q1. Which windows should evaluation outside a fit use?

**The decision.** Whether `predict()` and `compile_model()` should default to the closing stage's 0.1 % windows instead of 2 %. These two calls evaluate a model without fitting it. People use them to redraw a figure, to compute a curve on another grid, and to draw a synthetic pattern for testing a refinement against known truth. This needs you because it changes a default users call, and it moves the synthetic data in 39 test files (the previous session's count).

**Context.** Outside a fit, rietx still computes at 2 %. That has two consequences.

First, `predict(data)` after a default fit no longer returns the curve the fit minimised. The previous session measured the gap at 1.85e-4 of the tallest peak. You would not see that on a plot. In the tails it is not small against the noise: on a synthetic LaB6 pattern I drew today, the 2 % and 0.1 % curves differ by up to 0.8σ at one point.

Second, synthetic data drawn at 2 % are missing 2 % of each peak's tails, and the closing stage then fits tails the data lack. When the closing stage became the default, 127 fast tests failed. Two of the four parallel subagents that sorted them found recovery tests failing for this reason. The tests covered texture coefficients, magnetic moment angles, and the claims of `AIR_SCATTER_UNDECLARED` (the diagnostic saying the pattern shows air scatter the model does not declare). When the data were redrawn at 0.1 %, every one of them recovered its truth. The subagents made those tests pass by declaring `closing_window_tol=None`, which runs only the declared stages. So those tests now exercise a path that a default user never runs.

Today I measured the size of this effect on the synthetic LaB6 round trip: synchrotron data, 4200 points, five noise draws, with the same noise added to both patterns. I compared data drawn at 2 % with data drawn at 0.1 %, both fitted with the closing stage:
- cell and zero shift: 0.01 esd apart
- Caglioti W: up to 0.10 esd
- phase scale: up to 0.19 esd
- background constant: up to 3.4 esd

When the data's windows match the windows of the fit's last stage, the two fits agree within 0.02 esd on everything but the background. So the shifts above come from the mismatch alone. This pattern has narrow, nearly Gaussian peaks. Lab peaks with Lorentzian tails lose more area at 2 %, so I expect larger shifts there. I have not measured one.

One option is ruled out: making `predict` default to whatever windows the object's last fit used. A test requires that a never-fitted copy with the same models predicts the same array as the fitted one. That keeps `predict` a function of the model alone.

**Aim.** A curve computed from an answer should be the curve that produced it, and synthetic tests should exercise the path users run. This serves anyone who redraws a figure or checks a refinement on synthetic data. It also serves you, through tests that test what ships.

**Options.**
1. **Do nothing.** Evaluation stays at 2 %. `predict` stays up to 1.85e-4 of the peak height away from `y_calc`. A user checking a refinement on synthetic data sees the shifts above and cannot tell them from a refinement error. The tests keep their `None` declarations. No cost.
2. **Default evaluation outside a fit to 0.1 %.** `predict` on the fitted grid should then match `y_calc` to about 8e-6 of the peak height, the gap frozen windows always left (expected, not measured). Synthetic data would carry the tails.
   - Cost to users: a pure Lorentzian's window becomes 20 times wider, because the area left out falls as one over the window width. One evaluation took 0.01 to 0.02 s at either setting on the LaB6 grid (measured).
   - Cost to me: the synthetic data in 39 test files move, and the numbers pinned in them need re-pinning. The `None` declarations that exist only because of the mismatch can then go.
   - Reversible: one constant.
3. **Give `predict` a window argument and keep 2 % as its default.** A user who knows to ask gets 0.1 %, and tests that draw synthetic data pass it. Everyone else still gets a `predict` that disagrees with `y_calc`.

**Practice.** GSAS-II, MAUD, RIETAN-FP and EasyDiffraction recompute peak ranges at every evaluation (`practice.md`, checked last session). Each of the seven programs surveyed has one window setting. So in each of them, the pattern calculated at the answer is the fitted curve. From memory, and not checked this session, a calculate-only run in TOPAS or FullProf uses the same peak-range setting as its refinement. Among the programs surveyed, rietx is the only one with two window settings inside one fit, so the question does not arise elsewhere. Option 2 matches what they do.

**Recommendation.** Option 2. The answer is computed at 0.1 %, so anything computed from the answer should be too. The strongest case against is the re-pinning work in 39 files. A user's own script that calls `compile_model` would also see its numbers move slightly. I would change my mind if one `predict` call took more than about a second on a large lab pattern with Lorentzian peaks.

A related default waits on this answer. A stage run by hand (`run_stage`, and the GUI's single-stage run) also computes at 2 %, and no closing stage follows it. A GUI user who ends on a hand-run stage gets an answer up to about 1 esd off on lab data. That is the 2 % window's measured error. Option 2 could cover hand-run stages too, at an estimated 1.2 to 3.5 times that stage's time (inferred from whole-fit measurements). I would include it unless you want hand-run stages kept fast.

#### Q2. The six other numerical settings that failed their tests

**The decision.** Whether I apply each setting's measured fix. On 19 October you ruled that a numerical setting needs no sign-off from you once a test shows its arithmetic error stays under a tenth of the counting noise. A numerical setting is one that controls how carefully rietx computes and decides nothing about the science. Seven of them failed that test. The peak window was the largest failure, and the closing stage fixed it. Last round I proposed the same rule for the other six: tight values where the answer is computed. Your ruling built the closing stage but did not say whether the six follow it. Nothing has been built for them. Your standing instruction would let me decide this myself. I'm asking because the fixes move every converged fit.

**Context.** Reading the six again, my proposed rule fits only two of them. They fall into three groups.

*Settings frozen for each stage, where a closing-stage value helps.*
- **The FCJ sampling rule (four constants).** rietx computes FCJ axial-divergence asymmetry (Finger, Cox and Jephcoat) as a sum of shifted copies of the symmetric peak. These constants set how many copies each peak gets.
  - Error today: up to 5.6e-3 of the peak maximum on Lorentzian lab peaks. That is eight times the bar, which is a tenth of σ at FAP's strongest peak. Synchrotron peaks fail at every shape.
  - Effect on answers: small. SRM 660c with 512 copies on every reflection moved no parameter past 0.04 esd.
  - Fix: the cheapest set that passes uses 1.13 to 1.43 times as many copies, and lands only 5 % inside the bar. An earlier passing set cost 1.15 to 1.3 times the whole fit on the two lab protocols. On the closing stage alone, the cost would fall on one stage.
- **The reflection margin (0.5°).** rietx generates reflections only up to 0.5° past each end of the scan. A reflection just outside the scan whose tail reaches in is therefore missing.
  - Error: 0.12 to 0.19σ at the last points of FAP and cpd-1a, with answers moving 0.02 to 0.10 esd. The closing stage's wider windows made it worse.
  - Fix: generate reflections out to the widest window. A 5° margin already gives results identical to 20°. This is cheap enough to apply to every stage.

*Window floors that the closing stage probably fixes already.*
- **The axial sizing floor (0.02).** When the axial-divergence ratios S/L and H/L start at zero, rietx sizes windows and copies as if they were 0.02. A stage that refines them to a typical 0.05 is undersampled until the next stage recompiles. The errors are 0.27 of the peak maximum, and 19.5 % of a peak's area dropped. A floor of 0.05 passes, at 1.25 to 1.8 times the fit time.
- **The magnetic sizing floor (0.1°).** The same problem, for a magnetic peak width that starts at zero. The frozen windows drop 3.2 to 4.1 % of a magnetic peak. A plan ending on the width stage moved the moment by 0.07 to 0.57 esd.

Both errors last only until the next recompile. The closing stage recompiles at the refined values, so neither floor should bind at the answer. That is an inference: I have not measured either floor with the closing stage on. One exception: the package's own default magnetic solve runs without a closing stage.

*Settings unrelated to stages.*
- **The origin-fix clip (`A5_CLIP`, 1e-3).** In a polar space group, rietx fixes the floating origin by weighting the atoms (Flack and Schwarzenbach 1988). The clip is a floor on those weights. It puts light atoms' z esds 1.40 % off, against a 1 % bar. A clip of 1e-4 gives 0.14 %, at no measured cost.
- **The texture sphere sampling (2000 directions).** `TEXTURE_NOT_POSITIVE` warns when the refined pole density goes negative somewhere, which is unphysical. rietx checks 2000 directions and can miss a narrow dip. Dips down to −2e-3 to −7.9e-3 go unreported, against a bar of 1e-3 (the precision the warning prints). Checking 32 000 directions passes, at ten times the check's cost. A local minimisation started from the lowest of the 2000 directions passes at every order.

**Aim.** Keep each setting's arithmetic error below the noise, at the smallest added fit time. This serves every user, mostly without their noticing.

**Options.**
1. **Do nothing.** All six stay at tier 3 with their failures recorded. Tier 3 is the audit table's tier for a setting chosen without a test that bounds it. WP-2017 inherits them; it is the planned second pass that measures every tier-3 setting on three dataset families. Users keep the errors above:
   - answers move up to 0.04 esd from the FCJ rule and up to 0.10 esd from the margin
   - some negative texture goes unwarned
   - light-atom esds in polar groups stay 1.4 % off
2. **Fix each by its group.**
   - the margin: extended to the widest window, on every stage
   - the FCJ rule: the passing set, on the closing stage only
   - the two floors: measured with the closing stage on, and left alone if they pass
   - `A5_CLIP`: set to 1e-4
   - the texture check: given the local minimisation

   Each lands at tier 1 under your 19 October ruling once its test passes. The clip has no measured cost. The FCJ change adds time to the closing stage; I expect under 1.3 times that stage's time, not measured. The margin and texture fixes add work I expect to be small, also not measured. Every converged fit moves slightly, and the goldens (the bit-identity reference results) need re-pinning. Each constant can be reverted on its own.
3. **Tight values on every stage.** The FCJ passing set and the 0.05 axial floor apply everywhere. This is the simplest code. It costs 1.15 to 1.3 times and 1.25 to 1.8 times the fit time on every fit, on top of the closing stage's 1.05 to 2.05 times.

**Practice.** Last round's survey of the seven programs covered only the peak window. I have not checked how they set FCJ sample counts, reflection margins, origin fixing or texture positivity checks. No program manual I have read states the accuracy of a setting like these.

**Recommendation.** Option 2. Each fix has already been measured to pass, and only the FCJ change has a cost worth weighing. The strongest case against: it makes six changes that move every converged fit, for errors mostly under 0.1 esd in the answer, and WP-2017 will measure these settings on three families anyway. If you prefer a split, I can make the three cheap fixes now (margin, clip, texture) and leave FCJ and the two floors to WP-2017.

## Eighth round: is the closing stage the best trade? (2026-10-21)

The maintainer asked why the closing stage exists, whether its errors are real in physical
units, what programs that move their windows at every evaluation do, and whether the closing
stage is the best trade. The 6th session measured five variants on the four acceptance
protocols, two interleaved rounds, with another session's suite running (so the ratios
compare and the seconds read high). Time is against the fit with no closing stage. "Away" is
the largest shift from the shipped answer in plain esd, non-background rows.

| Variant | LaB6 | FAP | cpd-1a | NAC | cpd-1a start gap |
|---|---|---|---|---|---|
| no closing stage | 1.0×, 0.255 away | 1.0×, 0.905 | 1.0×, 0.960 | 1.0×, 0.154 | 0.75 (6th round) |
| closing stage, shipped | 1.39-1.40× | 2.31-2.35× | 1.58-1.62× | 1.21-1.29× | 0.070 |
| shipped, `intermediate_ftol` 1e-4 | 1.29-1.30×, 0.000 | 2.23-2.28×, 0.000 | 1.28-1.29×, 0.112 | 1.18-1.21×, 0.000 | 0.123, fails |
| shipped, declared stages at 5 % windows | 1.38-1.40×, 0.002 | 2.25-2.36×, 0.001 | 1.40-1.45×, 0.114 | 1.24-1.25×, 0.000 | not run |
| 1e-3 windows on every stage, no closing | 1.88-2.09×, 0.007 | 4.51-4.61×, 0.001 | 2.62-2.65×, 0.156 | 1.15-1.21×, 0.002 | not run |

The start gap is `tests/test_staged_start_invariance.py`'s measure (every Biso started at 0.5
and at 1.5 Å², bar 0.1 esd). The closing stage itself took 12, 9, 15 and 7 iterations (0.18,
0.80, 0.66 and 0.13 s). In physical units, switching it off moves cpd-1a's fractions by at
most 0.12 wt% (two toward the weighed values, one away), the fluorapatite's Lorentzian size
by 2.5 % and its strain by 3 %, LaB6's widths by 1-2 % and NAC by under 0.4 %.

**Answer.** "keep closing as built, and cascade that decision down. set closing as default
but give the option to turn it off for speed." The closing stage stays on by default at
1e-3. `closing_window_tol=None` is the speed switch, and it already reached every surface:
`RefinementPlan` and `PlanSpec`, a project file, and the GUI text document's `closing none`
line. What the round added is the record of the trade where a user and an agent choose:
`reference/refinement.md` § The closing stage carries this round's cost and what switching
it off moves, and the skill's `batch-operating.md` row 9c.34 when to switch it off
(`surprises.md` § 8, where a single-fit rule would go, has 46 B left under its budget).
The tree had moved on from three records by then: `waiting.md` § B10 and WP-2017's
inherited line still described the edge margin as built, and the theory page's
reflection-generation sentence too; all three now say it was reverted. Re-measured on the
tree: the closing stage's bar 2 is 0.008, 0.011 and 0.019 esd (FAP, cpd-1a, NAC), and
LaB6's two starts are 9.1 esd apart behind it (the mirrored axial minima).

### The four items behind it, asked 2026-10-21, answered 2026-10-22

**Answers.** "1. option 1. 2. keep 0.5 3. a. 4. a"

1. **How the FitReport reads a fit: option 1**, the misfit from a model at the closing
   precision and the shapes from one at the declared precision, inside the report builder.
   Built as `report._reading_models`: `build_report` takes `instrument=` beside
   `structure=`, and every caller in the package passes both. All 72 tests of
   `test_fitreport_layers.py` and `test_report_loop.py` pass, the 11 that failed among
   them.
2. **The reflection margin: kept at 0.5°**, tier 3, for WP-2017.
3. **The axial floor: (a)**, tier 3 with cpd-1a's 0.138 esd a strict xfail, for WP-2017.
4. **The caller-tier ruling: (a)**, applied on this branch. The definition is in
   `_audit.py`'s docstring and the record's § The rule; `GTOL` and `XTOL` are tier 3;
   `Harmonic.order` has no default, `DEFAULT_HARMONIC_ORDER` and its row are gone, and
   `harmonics=True` is refused naming the crystals that pass λ/2 and λ/3.

**Item 1's evidence, as the brief gave it.** The displaced-specimen case misranked
(axial asymmetry first) only where the closing FCJ rule's skip ratio (3e-4) and the
closing windows met: with data, fit and report self-consistent at one precision, each
alone ranked the displacement first, and the skip ratio set back to 0.02 alone recovered
it (0.99). In the model that ratio cannot go back: at 0.02 the skipped asymmetry leaves
9.5e-3 of a peak's maximum, 13× the lab bar and 54× the synchrotron one
(`tests/test_lab_instrument.py`'s FCJ cases). Last round's declared-precision copy failed
the same case for the opposite reason: its FCJ rule leaves 5.6e-3 (7.8× the bar) against
data with exact asymmetry, which the report read as asymmetry. The misfit from the
accurate model and the shapes from the copy ranked the displacement first at 0.995. A
compile costs 4-19 ms against a report's 0.24-1.57 s on the four protocols (quiet machine).
Every report before this WP read a declared-precision model against real data, so the
early-stage misreading was latent there; the synthetic data hid it by sharing the model's
precision. Item 2 corrected the session's own earlier label: the ridge the edge margin
freed was on `tests/test_scale_b_ridge.py`'s synthetic narrow scan, not cpd-1a.

## Ninth round: the 6th session's handover items (answered 2026-10-22)

**Answer.** "1. Fix the TRF issue 2. End with closing stage 3. Infer what I would do"

1. **The brucite TRF error: fixed by a retry.** macOS's system LAPACK (Accelerate)
   `gesdd` failed 20 times in 20 on the 7279 × 28 step matrix (condition 7.9e10).
   OpenBLAS's `gesdd`, installed from SciPy 1.18.1's macOS 12 wheel into a scratch
   venv, decomposed the same matrix, with singular values equal to `gesvd`'s to the
   last bit. A plain restart from the last accepted point also passed, but only
   because two of the 28 columns came out 5e-4 different the second time, so it
   was ruled out as luck. SciPy's supported alternative, `tr_solver="lsmr"`, landed
   at Rwp 0.17873 with 20 of 43 σ² negative, against `gesvd`'s 0.17872 and 19 of
   43; it changes the subproblem solver for the rest of the stage, so it was not
   taken. Built: `optimize/lapack.py` (`eigh`, `eigvalsh`, `svd`, `lstsq` call numpy
   unchanged and repeat a `LinAlgError` with `syev`, `gesvd` or `gelss`; TRF's step
   SVD is reached through its module's own name, only on a thread inside the
   package's solve). Every decomposition on the fit path goes through it, 41
   calls, and a test refuses a bare one there: `optimize/`, `model/`, `params/`,
   `report/`, `background/`, `solve/` and `refine.py`, among them the scale–B
   separation every stage measures and the report's region solves.
   `StageResult.n_lapack_fallbacks` records the count, tier 1.
   Practice: TenPy's `svd_robust` does the same retry; SciPy's `svd` docstring
   notes MATLAB and Octave call `gesvd` by default. Not generalised: the 44
   calls in `crystallography/`, `indexing/` and `gui/`, on small symmetry
   matrices or caught by their own handlers, none met failing;
   `isotropy._svd_rows` already falls back and records its driver.
2. **`solve_magnetic`'s winner: ends in a closing stage.** Only when the package
   chose the plan. The trials and the reference stay at the declared windows,
   where ΔBIC compares them; the winner then runs its plan's closing stage from
   its own refinement. Its Rwp, GoF, R_mag and moments are that fit's, its ΔBIC
   the ranking's, and a caveat says which is which. Two-site Pnma: moduli esds
   0.00242 and 0.00179 → 0.00151 and 0.00111 μ_B; the solve 16.5 → 17.1 s (one
   run each). Cr₂WO₆ at 4 K (the moment guide): blind 2.0353 ± 0.0459 → 2.0383 ±
   0.0467 μ_B; the alternate model started from the winner's magCIF 2.1255 ±
   0.0450 → 2.1240 ± 0.0440, scale shift 0.47 → 0.41 esd. Siblings checked: the
   other package plans without a closing stage (indexing validation, the
   extinction screen, the report's rival fits) hand the caller a ranking, never
   refined values.
3. **The three design questions, inferred.**
   - *A closing-off fit's report: kept.* Measured on the fluorapatite and cpd-1a
     fitted with `closing_window_tol=None` (the two patterns where switching it
     off moved answers most, 0.9 and 0.96 esd): read at the closing precision and
     at the fit's own 2 %, the report printed the same text, passed the same
     regions (2 and 1) with the same leading shape, and suggested no action
     either way; shares moved by 0.04 or less except one cpd-1a region, 0.43
     against 0.57. The eighth round's rule (misfit from the accurate model)
     stands, and `reference/refinement.md` says so beside the speed switch.
     A known-truth case, asked for by the generality judge: the eighth round's
     displaced specimen (−0.10 mm in the data, the displacement held at 0),
     fitted with the closing stage on and off and read both ways, ranks the
     displacement's cos θ shape first among the position templates in all four
     (R² 0.539-0.555, constant 0.527-0.542, not separable over this range), and
     no reading suggests an action.
   - *A loosened `closing_window_tol`: keeps the closing node rule.* The line
     moved from `CLOSING_WINDOW_TOL` to `WINDOW_AREA_TOL`, so anything finer than
     the declared stages takes the closing rule. Inferred from the eighth
     round's framing of the switch as speed: a caller loosening the windows asks
     for coarser windows, not for an asymmetry error 7.8× the lab bar. No
     compile the package makes sits between the two, so nothing moved.
   - *`build_report` without `instrument=`: refused.* A non-Pawley `model=`
     without `structure=` and `instrument=` raises `TypeError` naming them,
     since one model alone brings back both misreadings the eighth round
     measured. Every package caller passes both; one test called it bare.

## The sixth round's briefs, kept whole

### The three briefs as sent (2026-10-21)

Kept here whole, so the session that reads the answers reads them against this wording. A seventh round's answers land under a new heading above this one.

#### Q1. How far rietx computes each peak

**The decision.** Whether rietx computes peak tails further than it does today. Further costs fit time. It needs you because it trades accuracy against speed, and the established programs choose differently.

**What last round's sentence meant.** Some constants in rietx decide nothing about the science. They set how carefully rietx does its arithmetic: how far out each peak's tails are computed, how many sample points the axial-divergence integral uses, and how far past the scan's end reflections are still generated. On 19 October you ruled that such a setting needs no sign-off from you once a test shows its arithmetic error is too small to matter, for every kind of data it is meant to handle. "Too small to matter" was set at a tenth of the counting noise. The last session wrote those tests, and seven settings failed. This brief is about the largest, the peak window. The other six follow the same pattern and can take the same answer.

**Context.** rietx computes each peak out to the point where the tails it leaves out hold 2 % of the peak's area. Past that point the peak contributes nothing. Measured on four patterns (SRM 660c LaB6, the GSAS-II fluorapatite tutorial, the CPD round robin's cpd-1a, and 11-BM NAC):
- The calculated pattern is off by up to 2.15σ at a point.
- Refined values move by up to 0.97 esd on lab data when the tails are computed fully (cpd-1a's zincite scale; the fluorapatite Lorentzian size). NAC moves 0.17 esd.
- The background coefficients move 2 to 5 esd. They soak up the missing tail intensity.

Why rietx works this way. It sets each peak's window once, at the start of a stage, and holds it while the solver runs. If the windows moved during a solve, a data point could enter or leave a window between two evaluations, and χ² would jump by a small step. The solver chooses its next move from derivatives. It cannot see that jump in them, so it can stall or zigzag. A fixed window avoids the jumps at any width. Its price is that it cannot follow a peak that widens during a stage. By the end of such a stage 3 to 6.5 % of the area is missing, until the next stage resets the windows.

**What the other programs do.** I checked all seven this session, from each manual or source, and by running FullProf, RIETAN-FP and BGMN. The middle column is the area a pure Lorentzian loses to each default.

| Program | Default cut | Area lost | When the window is set |
|---|---|---|---|
| rietx | 2 % of each peak's area | 2 % | once per stage |
| TOPAS | where the peak falls to 0.001 of the strongest line's height | 2.0 % | rebuilt when a width moves past a set tolerance |
| MAUD | ±15 FWHM | 2.1 % | every evaluation |
| RIETAN-FP | 0.002 of each peak's height (its examples; no default) | 2.8 % | every evaluation |
| FullProf | 6 FWHM in its PbSO₄ example (no default; examples use 3 to 15) | 5.3 % | once per run, at the starting widths |
| GSAS-II | 50 FWHM below the peak, 75 above | 0.5 % | every evaluation |
| BGMN | no cut seen out to 22° | about 0 | not documented |
| EasyDiffraction | none | 0 | every evaluation |

So rietx's 2 % is in the middle. TOPAS and MAUD leave out the same. FullProf's examples leave out more than twice as much, and FullProf holds its windows for a whole run, as rietx holds them for a stage. GSAS-II computes four times further, and BGMN and EasyDiffraction compute everything. No program's manual states what its cut costs in accuracy. I infer that TOPAS and MAUD users carry the same shifts measured above, but I did not test those programs.

**Aim.** Answers as close as the data allow, at a fit time a batch user accepts. I have read your earlier rulings as putting accuracy first.

**Options.** All measured on the four patterns. Times are whole-fit wall clock against today's.
1. **Keep 2 %.** Matches TOPAS and MAUD. Lab answers stay up to an esd off and nothing says so. No cost. Reversible.
2. **Tight windows everywhere, 0.1 %.** Passes both accuracy bars on all four patterns. Costs 1.1 to 3.75 times the fit time, the fluorapatite the dearest.
3. **Tight windows on the last stage only.** The earlier stages keep 2 %. The answer matches option 2's within 0.008 esd on three patterns, at 1.06 to 1.91 times the fit time. On LaB6 both today's setting and option 3 land in a different minimum from option 2: the two axial-divergence parameters swap roles, the mirror pair already forwarded to WP-2012 (the work package on that interchange). That is a question of path, which is Q2.
4. **A middle cut at 0.5 %**, close to GSAS-II. It still fails: 0.33 to 0.43σ at a point, and answers move up to 0.88 esd. It costs 1.05 to 1.54 times. I would not pick it.

Options 2 and 3 change every converged fit slightly, and the bit-identity goldens get re-pinned in the same commit. All four can be undone by restoring the constant.

**Recommendation.** Tight windows only where the answer is computed. On its own that is option 3: the answer comes from the last stage, and the earlier stages only steer the fit towards its minimum. It recovers option 2's answers on three of four patterns at about half option 2's extra cost. If you also take Q2's closing stage, the tight windows go on that stage instead, and Q1 needs nothing more. The other six failing settings would follow the same rule: tight wherever it is cheap, and only on the answer's stage where the cost bites.

The case against: the fluorapatite still pays 1.9 times. A batch user fitting 200 patterns feels that. Option 1 is defensible on practice, since TOPAS and MAUD do the same. I would change my mind if the tight windows moved a certified value away from its certificate. I have not measured that against SRM 660c's certified cell.

#### Q2. How close two different starts must agree

**The decision.** How close two runs of a staged plan must agree before a starting value or a stopping tolerance counts as not changing the answer. You asked how RIETAN-FP and BGMN, which also stage, handle it.

**Context.** The tests ask whether Biso's default start of 0.5 Å², the harmonic seed, or the looser tolerance on intermediate stages changes the answer. They do: by up to 0.16 esd in Biso last session, and by 0.75 esd in cpd-1a's sample displacement this session. The cause is in rietx, not in the starts. Each stage fixes its peak windows, reflection list and axial-divergence sample points at the stage's start. So the last stage computes on a model fixed wherever the earlier stages stopped, and different starts stop the earlier stages in slightly different places.

**What RIETAN-FP and BGMN do.**
- RIETAN-FP's automatic mode refines subsets in its first cycles: background and scale, then widths, asymmetry, cell, atoms. Then everything refines together until convergence. Its windows follow the parameters at every evaluation, so nothing stays fixed where the subsets stopped. It holds Le Bail intensities for a cycle, and its manual warns that they depend on where they started.
- BGMN runs an automatic ladder. Isotropic models come first, and anisotropic terms are added in later runs. Every ladder ends with a closing run: everything free, restarted from the previous answer. Terms the data cannot support are switched off. Only the ray-traced instrument function is held for the whole fit.

The others, for completeness. MAUD's wizard adds parameter groups stage by stage and has no closing run. FullProf has no staging, so a user runs files one after another, and each run holds its windows at its starting widths. A FullProf user who stages by hand meets the same path effect as rietx. GSAS-II, TOPAS and EasyDiffraction do not stage. None of the seven tests whether its answer depends on the path, and none of the manuals mentions it. So the bar is rietx's own to set.

**Aim.** Two users with the same data and different starts get the same numbers.

**What I measured this session.** Biso started at 0.5 and at 1.5 Å² on every atom, under three settings. The number is the largest disagreement between the two starts on anything but the background, in plain esd (without the Bérar-Lelann inflation).

| Pattern | Today | Tight windows on the last stage | Closing stage at tight windows |
|---|---|---|---|
| Fluorapatite | 0.119 | 0.013 | 0.000 |
| cpd-1a | 0.751 (sample displacement) | 0.734 | 0.064 (cell c) |
| 11-BM NAC | 0.008 | 0.006 | 0.000 |
| SRM 660c LaB6 | 9.0 (axial S/L) | 9.0 | 9.4 |

Tight windows on the last stage fix Q1's truncation and leave the path effect. The closing stage fixes both on three patterns. LaB6's two starts land in its two mirrored minima under every setting, so no window setting can make them agree. The closing stage costs 1.36 to 2.26 times today's fit time, against 1.06 to 1.91 for tight windows on the last stage alone.

**Options.**
1. **Keep the 0.01-esd bar, change no code.** Biso's start, the harmonic seed and the intermediate tolerance stay at tier 3 with their failures recorded.
2. **Raise the bar to 0.1 plain esd, change no code.** The fluorapatite and NAC pass. cpd-1a (0.75) and LaB6 fail.
3. **End every plan with a closing stage at tight windows, and set the bar at 0.1 plain esd.** The closing stage recompiles at the answer and solves once more with everything the plan freed. It is BGMN's closing run. It also gives what RIETAN-FP and the per-evaluation programs get by moving their windows continuously. The fluorapatite, cpd-1a and NAC pass. LaB6 fails, correctly, and stays recorded with WP-2012. Costs 1.36 to 2.26 times today's fit time, and it covers Q1.
4. **The closing stage with the 0.01 bar.** The fluorapatite and NAC pass. cpd-1a fails at 0.064.

Options 3 and 4 change every converged fit and re-pin the goldens. All four can be undone.

**Recommendation.** Option 3. It is the only option that meets the aim on more than one lab pattern, and it settles Q1 in the same stage. A 0.1-esd bar matches the answer bar Q1's window tests already use. A user cannot see a difference of 0.064 esd between two starts. LaB6 still fails it, for the reason a start test exists to catch: two minima close together.

The case against: a fit that has already converged pays for one more solve, about a fifth more than Q1's option 3 alone (2.26 against 1.88 times on the fluorapatite). The 0.1 bar is also ten times looser than the 0.01 that Suortti's start passed. I would change my mind if the closing stage cost more than about 2.5 times on any lab pattern, or if the intermediate tolerance and the harmonic seed still failed 0.1 behind it. I have not rerun those two.

#### Q3. Where Pitschke's roughness model starts

**The decision.** Pitschke's strength c and Suortti's depth b both start at 0.3 from one shared constant. Whether Pitschke keeps that start.

**Context.** Suortti's start was shown not to matter. Pitschke's does. On CPD zincite, from 0 the fit lands outside the model's valid range: the scale doubles, Biso(O) moves from 0.05 to 0.59 Å², χ² is 4.8 % lower, and `ROUGHNESS_OUTSIDE_REGIME` fires. From 0.3 the correction switches itself off. On CPD corundum Biso moves 0.26 esd between the two starts.

**What the other programs do.** None supplies a default start for Pitschke's model. RIETAN-FP and TOPAS have it with no default start given (TOPAS's would be in a macro file I may not read). FullProf has the same formula with no default, and its shipped examples start the strength at 1.2 to 1.5 and τ near 0.14. GSAS-II, MAUD, BGMN and EasyDiffraction have no Pitschke model. GSAS-II's own roughness model is Suortti's, and it starts at zero, unrefined. So last round's fallback, "GSAS-II's 0", has no program behind it for Pitschke.

**Options.**
- (a) Keep 0.3 for both, with Pitschke at tier 3 and its failure recorded.
- (b) Start Pitschke at 0.
- (c) Split the constant: Suortti's start recorded as not affecting the answer, Pitschke's kept at 0.3 at tier 3 with its failure recorded.

**Recommendation.** (c). From 0.3 the fit reaches the switched-off branch, which lies inside the model's valid range. The lower χ² from 0 is one the model itself flags as invalid. FullProf's examples start further from 0 than 0.3 does. The case against: a careful user may want to see that the data prefer a correction, even an out-of-range one. The warning already shows them that.

### Three more, from the handover's reviews (2026-10-21)

The generality judge and the code review read this session's changes at handover. Three
of their findings are decisions for the maintainer. They are numbered on from Q1-Q3.

#### Q4. Did the fifth round's Q6 answer mean "yes"?

Q6 proposed a class for caps on what a report lists. The answer was "doesn't appear to be
a question". The lead read it as agreement and built it: tier 1 now holds such a cap once
a test shows the report complete inside the cap and its notes counting what lies outside,
or, for a cap on distance, the report stating the distance. The three geometry caps moved
to tier 1 on it. The judge points out the answer could also mean "not mine to decide".
Two facts bear on it. No caller can change any of the three caps (3.5 Å for contacts, 24
contacts an atom, 200 atoms a phase). The search time at 200 atoms is unmeasured.

- (a) Confirm. The clause and the three rows stay.
- (b) Undo. The clause goes, and the three caps return to tier 3.

Lead's pick: (a). A cap that says what it dropped hides nothing, and the table feeds only
the report and the CIF writer, never a fitted number.

#### Q5. How tier 2 counts a program that does otherwise

The rule now calls a program that does otherwise by default a dissenter, and one without
the feature neither. It says what a dissenter outweighs only for an action, and it does
not say how many of the seven must agree. Two rows turn on this.

- The default solver. Six programs damp their steps (Marquardt). FullProf takes
  Gauss-Newton steps scaled by fixed relaxation factors. rietx's row stays tier 2 on the
  lead's reading that the dissent clause governs actions only.
- The 1.5 Å cell-length floor. TOPAS alone floors cell lengths; the other six leave them
  unbounded. The row stays tier 2, reading "no floor" as "without the feature". The judge
  notes that removing the TCHZ ceilings read "no ceiling" as "doing otherwise", the
  opposite reading.

Options:
- (a) A dissent counts against a default or a threshold too. The solver joins the seven
  solver-path switches B10 already holds at tier 3 until refits of three families on
  either side agree. The cell floor moves to tier 1 on a physics argument: no crystal has
  a lattice translation near 1.5 Å (recalled, not checked: Be's a of about 2.29 Å is among
  the shortest), so the floor can only stop a runaway.
- (b) Dissent counts only against actions (today's reading), and the rule says so.
- (c) As (b), and "no limit" always reads as "doing otherwise" for a bound. The cell floor
  then leaves tier 2, as in (a).

Lead's pick: (a). It matches how B10 already treats the other solver switches, and it
makes the two bound readings agree.

#### Q6. A backstop for a runaway instrument width

With the ceilings gone, nothing stops an instrument width (U, W, X or Y) widening until the
lines merge into the background, on a weak pattern or along a series chain. No
single-fit diagnostic reports a runaway width. The sample-broadening terms already have a
backstop: `params/vector.py`'s `strain_cap` and `size_cap` hold a phase's Lorentzian width
to the width of the fitted range, so a peak cannot become wider than the scan. Issue #140
is why: a Cu phase's `lor_strain` reached 1.1e5 on a 248-pattern series, and a real 16 wt %
phase was starved below 1 wt %. Before the ceilings went, U, W, X and Y stopped at 1 and V
at 0.5.

- (a) Extend the range backstop to the instrument widths. It is set by the fitted range,
  so it is no chosen number, and it fires only on a runaway.
- (b) A diagnostic only, naming a width wider than some fraction of the range.
- (c) Nothing until a real fit shows a runaway.

Lead's pick: (a). It is the same physical argument the sample terms already rest on.

#### Q7. Removing the width ceilings moved one acceptance fit

The full suite ran once on the final tree and found one consequence of Q5's build. The
brucite Stephens test fits under TRF, the bounded solver the cone test needs. TRF scales
each step by the distance to a parameter's finite bounds. An infinite upper bound gets a
different scaling, so the path changes even where no width comes near a ceiling. Without
the ceilings the fit stops at a worse point: Rwp 0.17891 against 0.17877, U on its floor
of -0.05, and one strain coefficient's esd 66 against 14 737 (t = -203 against 0.37). The
test's "at most one coefficient 2σ from zero" fails. No width reached 1 in either fit (Y
0.086 at most). Any finite ceiling restores the old answer to its printed digits: every
ceiling at 10, or at 1000. The default solver, LM, is unaffected, and the bit-identity
goldens did not move. The test is a strict xfail until this is ruled.

- (a) A ceiling no peak can reach: the width of the whole 2θ axis (180° for X and Y,
  180² deg² for U, V and W). It caps nothing physical and gives TRF a finite bound.
- (b) No ceiling, and re-pin the brucite test at the new, worse point.
- (c) Restore the old ceilings.

Lead's pick: (a). It keeps the ruling's substance and restores the measured answer.
(b) re-pins a number that moved away from the better fit. Not yet measured: the brucite
fit at a 180° ceiling itself.

## Still open (first round's list, kept for the record)

1. B4: keep f, and report the textbook esd beside it?
2. B5: drop and report zero and negative esds, built in WP-1952?
3. B8: count and then remove the window; put the cell back and hold it after a runaway;
   keep the 2 nm floor?
4. B9: the reading below, plus a "geometry not stated" state in the B7 follow-up?
5. B2, B3, B11, B16: as recommended below?
6. B6, B13, B15: yes?

---

## B4. Which esd is scientifically accurate (pick changed)

**The decision.** Whether rietx keeps multiplying every reported esd by the Bérar-Lelann
factor f. The batch recommended stopping. Asked what is scientifically accurate, the
second-round pick is to keep it.

**Context.** The textbook least-squares esd assumes each point's residual is independent
of its neighbours. Rietveld residuals are not independent. When the model misfits a
peak's shape, the misfit runs across many consecutive points with the same sign. Two
things follow.

The textbook esd is too small. It counts each point as separate information.

It also depends on how finely you stepped. Collect the same total counts in steps half as
wide. The summed misfit over the peak stays the same, but the point count doubles. χ²_red
halves, and every esd shrinks by √2, though the specimen and the information are
unchanged. That is arithmetic from the formula. Hill & Madsen (1984, J. Appl. Cryst. 17,
297) reported the step-width effect (recalled). Fine-stepped synchrotron scans show it
most: the 11-BM NAC example has 22 003 points against 132 reflections.

f measures how often neighbouring residuals share a sign, and scales the esd up to
compensate. Measured values are 1.13 on residuals with no correlation, 2.15 on the FAP lab
example and 8.07 on NAC. The 1.13 is a known property of the paper's formula, because
same-sign neighbours happen by chance (`optimize/statistics.py`, `berar_lelann_factor`'s
docstring). So on a perfect fit, rietx's esds are 13 % above the textbook value.

Neither number covers systematic error. With f applied, SRM 660c's refined cell still sits
4.9 esds from its certificate. Without f it would sit 4.9 × f esds away.

**Aim.** Report the esd closest to the true uncertainty, and keep a comparison with
GSAS-II easy.

**Options.**
1. Keep f, and report the textbook esd beside it. Today's esds do not change. A user
   comparing with GSAS-II reads one more field. Cost: one field and its writer. Undoable.
2. Stop multiplying, and report f beside the esd (the batch's pick). Every esd shrinks by
   1/f: to 0.89 of today's on uncorrelated residuals, 0.47 on FAP, 0.12 on NAC. Esd
   goldens are re-pinned, and the bound test's margin (B16) is re-measured. Undoable.
3. Do nothing. Esds stay as they are, and nothing tells a GSAS-II user why rietx's are
   larger.

**Practice.** GSAS-II 5.8.4 does not apply it. Its esds are the covariance times GOF²
(source checked by the first session). FullProf computes the same factor as SCOR and
leaves its own esds unmultiplied. It then prints "A better estimate of the accuracy of
structural parameters is obtained multiplying sigmas by the parameter SCOR" (the binary's
strings, checked by the first session). TOPAS was not checked. Bérar & Lelann (1991,
J. Appl. Cryst. 24, 1) and McCusker et al. (1999) are not in the Zotero library (searched
2026-10-19). So practice computes f and leaves the multiplication to the user, and
FullProf's own advice is to multiply.

**Recommendation.** Option 1. On correlated residuals the textbook esd is too small, by an
amount set by the step size. That error has a known direction, and f corrects most of it.
The batch picked option 2 because GSAS-II users would dissent. That is a question of
convention, and the extra field answers it. It stays at tier 3 on the maintainer's dated
approval, since GSAS-II does not do it by default.

The strongest case against: f is one number for every parameter, while correlation affects
a peak position and a scale differently. It also overstates by 13 % when there is no
correlation. The pick would change if repeated scans of one specimen scatter by about the
textbook esd. That is the direct test of a precision estimate, and no such set is on disk.

---

## B5. What a zero esd should become (pick changed)

**The decision.** What rietx does when a file's esd column holds a zero or a negative
number.

**Context.** Today such an esd is raised to a thousandth of the column's median esd
(`schemas/pattern.py`, `_floor_sigma`). Issue #897 (a reporter's two-column file) had one
zero among esds of 3.0. That point got σ = 0.003 and a weight a million times its
neighbours', since weight goes as 1/σ². One point can then pull the whole fit, and nothing
reported it.

What is accurate depends on what the zero means, and the file rarely says.
- A raw count of zero, where the writer computed √0. A zero count still carries an
  uncertainty of about one count. rietx already uses that convention when a file has no
  esd column.
- A masked or unmeasured channel. Some neutron reduction writes these as y = 0, e = 0
  (recalled for Mantid, not checked). The point holds no measurement and should not be
  fitted.
- A negative esd has no meaning.

The current floor is wrong in all three cases.

**Options.**
1. Keep the floor.
2. GSAS-II's xye reader: a channel with y ≤ 0 gets zero weight, whatever its esd (checked
   by the first session).
3. Drop every channel with a non-positive esd from the fit, and report which channels were
   dropped and why.
4. Refuse the file and name the lines.

**Recommendation.** Option 3. It invents no number and cannot go wrong in units, and the
rest of the file stays usable. Its cost is a small bias where a raw file holds many genuine
zero counts, such as a sparse neutron background, because those points leave the fit. It is
built in WP-1952 (the WP for plain x-y files), which already plans a per-line report. That
WP also establishes what a zero marks in each format. It may restore genuine zero counts at
σ = 1 count where a file is known to hold raw counts. Until it lands the floor stays, and
the table names WP-1952 as its replacement. The pick would change if WP-1952 finds a format
where a zero esd marks good data.

---

## B8. Three limits that act on every fit

**The cell window.** For a phase the data barely see, each stage limits its cell to ±5 % of
the starting lengths (plus 0.05 Å) and ±2° on angles. It was built after an unseen phase's
cell ran to 39 293 Å on a 68-pattern in-situ series. Later the absent-phase hold (B1)
arrived, and it freezes the whole cell of exactly those phases. The window now matters in
one corner only: a held phase whose cell is tied to a visible phase's cell. There the
visible phase pins it anyway, and the window is expected never to act. **Recommendation:**
count the stages across the test suites where it binds. If the count is zero, remove it
from single fits; chain fits belong to WP-2003. The case against is TOPAS. It bounds every
cell by default (per rietx's docstring, not checked).

**The cell clamp.** After each stage, a cell length that moved more than 15 % from the
stage start is pulled back to the 15 % edge (6° for an angle). Honest moves within a stage
are about 0.03 %, 500 times smaller. It fires only on a runaway. The measured case is a
visible phase sharing its cell with a 2 % trace copy; its cell ran from 4.16 Å to 3803 Å in
one stage. When it fires, the user gets a cell 15 % off. No fit produced that value, and
its esds come from the runaway point. Only the `CELL_RUNAWAY` diagnostic says so.
**Recommendation:** on a runaway, put the cell back to its stage-start value and hold it
for that stage, with a record entry. A refiner would do the same. The code already does
this for a collapsing phase (B1), so it reuses that path. It fired in none of 104 fits in
WP-1523's sweep, so ordinary fits do not change.

**The 2 nm size floor.** Crystallite size from peak broadening may not go below 2 nm.
Below a few nanometres a crystallite is a cluster of a few unit cells. Broadened Bragg
peaks no longer describe its pattern, and the Debye scattering equation is needed
(recalled). The number itself comes from one private archive of 606 TOPAS refinements.
Without it, the only fence left is a peak wider than the scan. That fence is about 13 times
looser. **Recommendation:** keep 2 nm at tier 3, with its single-archive evidence stated in
the row. When it binds, `BOUND_HIT` already reports it.

---

## B9. Limits and defaults inside features you turn on (geometry pick changed)

A "box" here is a pair of limits on one parameter, a lower and an upper bound. For example,
occupancy may not leave 0 to 1.5. It has nothing to do with the unit cell; the batch should
have said "limits".

**The decision.** How to judge 21 defaults of this sort. They sit inside features the
caller switches on, such as preferred orientation, extra peaks and humps. Or they sit on
parameters no default plan frees, such as occupancy and specimen offsets.

**Recommendation** (the batch's revised pick):
- A limit that keeps a parameter out of an unphysical region, or away from a pole in the
  model, stays. Occupancy ≥ 0 and March-Dollase r > 0 are this kind.
- A chosen limit that a competent refiner would need to pass needs a source, or it widens.
  Two have a named dissenter. Occupancy ≤ 1.5: a mineralogist who declares Mg on a mixed
  Fe-Mg site and refines occupancy as site scattering needs 2.2 for full Fe. March
  r ≥ 0.15: a pressed clay or mica plate can need less. The 0.15 was also chosen on an Rwp
  comparison, which the house rules reject as evidence. No default occupancy limit is
  recalled in GSAS-II, FullProf or TOPAS.
- Starting values, such as Biso 0.5 and the peak-width starts, get a two-start test. If fits
  from two starts agree, the start does not matter.
- Instrument facts the package assumes are recorded in the result as assumed. These are the
  geometry, the polarisation (0.99 in the capillary preset, 0.5 with no preset) and the
  Kα2/Kα1 ratio of 0.5.

**The geometry question from the B7 ruling.** Today an `Instrument` built without naming a
geometry is treated as a capillary (`Geometry.kind` defaults to `debye_scherrer`,
`schemas/instrument.py` ~line 1207). The B7 principle, that an unknown geometry frees
nothing that might not apply, suggests a third state: geometry not stated. Under it the
default plan frees nothing geometry-specific, and the report suggests no geometry-specific
correction. Today the report suggests capillary corrections for such an instrument
(`report/layer2._POSITION_ACTIONS_BY_GEOMETRY`). The presets (`Instrument.bragg_brentano`,
`Instrument.debye_scherrer` and the transmission one) already state their geometry, so only
hand-built instruments change. Old project files store the geometry explicitly and should
open unchanged (inferred, to be checked). The recommendation is to put this in the same
follow-up WP as B7, since both read the same field.

---

## B1. The absent-phase hold, restated

A fit sometimes contains a phase the data barely show. It may be an impurity that has not
yet formed in an in-situ ramp, or one too weak to see. Its peaks are so small that changing
its cell, positions, peak widths or B leaves the calculated pattern unchanged. Least
squares then lets those parameters wander anywhere. On one ramp such a phase's cell walked
14.9 Å from the truth while Rwp did not move.

So at the start of each stage, rietx asks of each phase whether its scale is at least three
times its counting-noise esd. If not, it holds the phase's cell, positions, widths and B for
that stage. The scale stays free, so the phase can still appear. At the end of the stage the
test runs again. A phase that now passes is released, and the stage solves once more. A
phase that fell below the line during the stage is put back where the stage found it and
held, with one more solve. `StageResult.held` and `StageResult.released` list each one.

It passes because it touches only parameters the data cannot determine, so it cannot move
an answer the data support. A GSAS-II, FullProf or TOPAS user does the same by hand when a
phase vanishes. The weak point is the 3σ line. A weak phase that appears with its cell more
than a peak width from its CIF (thermal expansion, a solid solution) could stay under 3σ
because its peaks sit in the wrong place. The hold would then freeze the wrong cell. So the
threshold stays tier 3. The second pass tests a weighed phase at 0.1-1 wt % and a minor
phase started one peak width off its cell.

---

## B2. Magnetic moment directions

**The moment turn.** In some magnetic structures, rotating a moment about one axis leaves
the powder pattern unchanged, because the powder average cannot see that angle. Like the
absent phase's cell, the angle then sits wherever the start put it. Without the turn, one
answer reported 27.84° against a reference of 10.20°. The turn rotates the moment about
that invisible axis to a conventional reference direction and checks the pattern is
unchanged. It then holds the angle and records the turn in `StageResult.moment_turned`. A
refiner would fix such an angle by convention too. **Recommendation:** keep it.

**The stationary-angle test.** After the fit, it asks whether each moment angle sits on a
direction the symmetry singles out, such as along an axis, using a χ² test at 95 %. If so,
the angle keeps its value and loses its esd. A parameter sitting on such a direction makes
the covariance ill-defined and inflates the other esds. The review found the test too
lenient. On LaMnO₃ (NIST BT-1 data) a polar angle stopped 5.2° (0.091 rad) from 90°. The
test could not tell it from 90°, so the angle lost its 3.5° (0.0608 rad) esd. No refiner
would quote an off-axis angle without its esd. **Recommendation:** measure before ruling.
Fit simulated weak moments tilted 1-3σ off the axis, and count how often the test drops an
esd it should keep. If it drops ones a refiner would quote, demote it: report the test's
number and keep the esd.

---

## B3. Starting values for parameters that sit at zero

A seed is the value a stage gives a parameter before solving, when it would otherwise start
at its floor. The start can decide which minimum the fit finds, so a seed can change the
answer.

**Surface roughness.** The roughness stage starts Suortti's b at 0.3. Roughness lowers
low-angle intensity and Biso can mimic it, so the start may decide which of the two takes
the effect. GSAS-II starts at 0. **Recommendation:** refit three lab datasets from 0 and
from 0.3. If both land in the same place, the seed does not matter and needs no approval.
If not, report where each lands, and switch to GSAS-II's 0 unless 0.3 is closer to a
reference.

**Anisotropic strain (Stephens).** The width formula has a square root with infinite slope
at zero, so the solver cannot move a block that starts at exactly zero. Some start is
forced. rietx uses 1000 ppm isotropic, GSAS-II's isotropic microstrain default. On one
pattern the start changed the minimum found: χ² 1.160 from 1000 ppm against 1.482 from the
previous stage's strain (WP-1467). **Recommendation:** keep it at tier 3 until a second
dataset compares the starts. Record the seed in the result, which nothing does today.

---

## B11. When a fit stops

**Iteration budgets.** A stage stops after at most 100 iterations (400 evaluations). These
guard against a runaway, and a converging fit stays about ten times inside them.
**Recommendation:** treat them as not affecting the answer, once a test confirms that
margin under both solvers. Those are the default LM and the optional TRF, and under TRF
three test fixtures do hit the limit.

**Le Bail cycles.** Le Bail alternates between extracting peak intensities and refitting
everything else, three times per stage. Issue #740 used a synthetic pattern with the cell
and profile at the truth. It reached Rwp 4.56 % after 3 cycles and 1.62 % from 100 to 400
cycles, against 1.09 % for the true structure. GSAS-II runs 10 cycles, and FullProf's manual
suggests about 10. **Recommendation:** repeat until the intensities stop changing, with a
cap, built in WP-1542 (the WP that owns #740). Le Bail fits then reach a lower Rwp at some
extra cost. The remaining gap, 1.62 % against 1.09 %, is a separate problem WP-1542 also
owns.

---

## B16. The test that says a limit stopped a parameter

When a parameter ends at a limit, such as Biso at 0, rietx decides whether the limit
actually stopped it. The answer feeds the `BOUND_HIT` and `FLOOR_HIT` diagnostics and the
`at_bound` field. Under the default solver with up to 128 free parameters, the solver knows
which limits were active, and rietx reads its list. Otherwise rietx asks two things. Is the
value within a hundredth of an esd of the limit? And does the residual still push against
it? Over 32 measured cases on two datasets, the 0.01-esd line sits 13 times above the
largest real gap and 236 times below a fit that stopped early. In a default fit it only
reports. **Recommendation:** keep both numbers at tier 3, and add a third dataset under TRF
in the second pass. If f is kept (B4, option 1), the margin stays as measured.

---

## Three plain ones

- **B6:** anomalous dispersion (f′, f″) stays on by default. GSAS-II applies the same table
  to every X-ray pattern with no switch.
- **B13:** 58 numbers that only decide whether a diagnostic message appears move to the WPs
  auditing those messages (2004, 2005 and 2007). If 2005-2007 are cancelled at their gate,
  43 of them need a new home.
- **B15:** a magnetic site naming a bare element, with no charge, gets an assumed ion for its
  form factor. Keep the assumption where the element has a single magnetic ion (Ce, Eu,
  Yb), and for the other lanthanides once a citation is added. Sm waits for a citation,
  since its free-ion form is known to be poor. For U, Np and Pu, stop guessing and ask the
  caller to name the ion, listing the candidates. GSAS-II's bare U is U³⁺, where rietx
  picks U⁴⁺.

---

## Third round: answers to the questions sent back (2026-10-19)

Foreign-code behaviour below was read this session. GSAS-II 5.8.4 from its source in
`rietx-bench/tools/gsas2` (lines checked by the lead where marked). TOPAS from the
Technical Reference Version 9 (2 October 2026), decoded from topas-academic.com. FullProf
8.20 from its manual, the binary's strings and runs on its PbSO₄ example. Three Sonnet
agents read the sources; the lead checked each load-bearing line marked "checked".

### B2. The moment turn, and the stationary-angle test

**Is the turn common enough to keep?** It is needed in a narrower case than the hold it
serves, but the case includes textbook structures, and a caller cannot do it by hand.

The hold itself is common. Any collinear magnet whose magnetic cell is uniaxial
(tetragonal, hexagonal, trigonal) or cubic has a moment direction the powder average cannot
see (Shirane 1959). The hold fixes that angle.

The turn is needed only when the invisible rotation is a mix of rietx's two moment angles.
That happens when the site's coordinate frame does not have its pole along the unique axis.
Two families do this: R groups on rhombohedral axes, and the general-direction description
of the k = ½½½ rock-salt antiferromagnets (MnO, NiO, CoO). The second is the classic
textbook case of powder indeterminacy.

Without the turn there are two outcomes, and both give a wrong answer.
- Hold one angle where it started. The other angle then sweeps a circle that may never
  reach the right angle to the unique axis. Measured: the fit stopped at ψ = 27.84°
  against a true 10.20° (`tests/test_magnetic.py:1810-1823`). ψ is the one angle the
  powder can measure.
- Hold nothing. The covariance is singular. On 2 of 16 noise seeds the esd of ψ came out
  as 448° and 20 490°, where the other 14 gave 0.7-0.9° (issue #599).

A caller cannot easily do it themselves. They would have to rotate the site's frame so that
one angle is the invisible rotation. rietx derives that frame from the site symmetry and
has no verb for choosing another.

Other codes do nothing here. GSAS-II has no powder-indeterminacy logic; a flat moment column
falls to its generic rule, which drops a column with norm below 1e-14 for that cycle and
prints "Parameter(s) dropped" (`GSASIImath.py:263-268`). TOPAS stops with "cannot be
refined as it has no derivative" only when symmetry makes a moment component exactly zero
(Tech Ref § 14.1). FullProf's manual does not mention the case, and the program has no
handling for it (manual p. 20, the binary's strings). None of the three handles the
powder-only case.

**Recommendation: keep the turn** at tier 3, with the measured failure as its ground. It
moves the moment only along a rotation the pattern cannot see, checks that the pattern is
unchanged before accepting, and records the turn in `StageResult.moment_turned`.

**Is the stationary-angle test a demotion?** Yes. The batch asked for a measurement first,
but the LaMnO₃ case already decides it: the test removed a 3.5° esd from an angle 5.2° off
the axis, which a refiner would quote as 84.8(35)°. Rule 1 lets the package act alone only
where every competent refiner would. One counter-example of that kind fails it, so how
often it happens does not change the ruling.

What the demotion loses is small. Near a symmetric direction the textbook esd is too large,
because the pattern depends on the square of the offset there. Too large is the safe side.
An angle exactly on the axis has a zero Jacobian column, and the general covariance rule
already reports no esd for that (`statistics.normal_covariance`, WP-1110). Demoted, the
angle keeps its esd. The test's Δχ² to the symmetric direction goes in a record field, and
`MOMENT_ANGLE_STATIONARY` becomes an info record with that number. Neither GSAS-II nor
TOPAS has such a test; each prints the esd as computed.

### B7. The geometry take

**Agreed, with two additions.**

1. Under "geometry not stated" the report must not go quiet about a peak-position error it
   can see. A Bragg-Brentano specimen's displacement error leaves a cos θ-shaped misfit,
   which leaks into the cell if nothing absorbs it. Today the report suggests a capillary
   correction for such an instrument. Under the new state it should say that a
   position error of that shape is present, and ask the user to state the geometry.
2. "Not stated" needs a reading at every place that uses the geometry: 70 references in 15
   files, among them the forward model, absorption, preferred orientation, the report, the
   exporters and the FullProf and GSAS-II importers. The follow-up WP audits every reader
   before writing the new state. This is the rule the extra-components union taught
   (root `CLAUDE.md`): its counts and builders were right only while there was one kind.

Practice backs the take. TOPAS assumes no geometry. A correction applies only when a macro
names it, so nothing geometry-specific is refined unless stated (Tech Ref § 1.3, § 22.1.7).
GSAS-II always picks one. It reads Bragg-Brentano when the instrument file has a Kα1/Kα2
pair or its source text says "lab data", and Debye-Scherrer otherwise
(`GSASIIfiles.py:509-519`, `GSASIIdataGUI.py:2075-2081`). The choice changes which position
and absorption terms it offers. FullProf's geometry flag `Ilo` defaults to 0, one setting
for both Debye-Scherrer and Bragg-Brentano, and refines displacement and transparency only
when the user frees them (manual p. 70). So GSAS-II guesses from the wavelength, as rietx's
capillary default does in effect. TOPAS and FullProf refine nothing geometry-specific
unless asked, which is the take.

### B8. The cell window and the size floor

**The cell window: tier 2, agreed.** TOPAS bounds every cell by default (Tech Ref Version 9,
§ 2.17, Table 2-1, checked this session): a, b, c within 0.995·Val − 0.05 to
1.005·Val + 0.05 Å, angles within ±0.2°. Val is the current value, recalculated each
iteration, so in TOPAS it is a limit on each step rather than on the answer. rietx's solver
takes one fixed pair of bounds per stage, so the window is TOPAS's step limit compounded
over a stage: 0.5 % per iteration is 5.1 % over ten (`params/vector.py:593-613`). It also
applies only to phases the data cannot see, because a bound changes the solver's steps even
when not reached. GSAS-II has no cell bound of any kind (`GSASIIstrMain.py:1198-1230` acts
only on user limits), nor has FullProf (bounds on request only, manual p. 125). One program doing it by default meets tier 2. The count the batch
proposed is no longer needed, since the window costs nothing where it does not act.

**The 2 nm size floor: agreed, a warning is enough.**

- Physics. Below about 2 nm a crystallite is a few unit cells, and broadened Bragg peaks
  stop describing its pattern; the Debye scattering equation does. But the size is still a
  physical quantity. Under the B9 principle a chosen limit should not block it.
- Numerics. The floor guards against a runaway: a phase's peaks widening until they behave
  like background. A second fence already covers the end where that becomes meaningless,
  a peak wider than the fitted range (`size_cap`'s range backstop). On a Cu 10-80° scan
  that fence sits at about 0.15 nm.
- Practice. TOPAS's crystallite-size macro limits size to 0.3-10 000 nm (Tech Ref § 2.17).
  GSAS-II clamps the stored size to 0.001-10 µm after each refinement, silently
  (`GSASIIstrIO.py:3531-3540`, checked). FullProf has no size limit and no small-size
  warning, and says its apparent size carries no physical interpretation (manual pp. 21,
  25). So the codes that floor size do so at 0.3-1 nm, below rietx's 2 nm.
- The warning exists. `SIZE_UNUSUALLY_SMALL` fires below 5 nm today.

**Recommendation.** Remove the 2 nm floor. Keep the range backstop, since a peak wider than
the scan is not measured by it. Add to `SIZE_UNUSUALLY_SMALL`'s message that below about
2 nm the Bragg-peak model may not describe the pattern. Two tests pin the 2 nm number and
change with it (`tests/test_strain_cap.py:348`, `tests/test_help.py:667`). The flag's own
5 nm threshold goes to WP-2005 with the other diagnostic thresholds (B13).

### B1. The absent-phase hold as an option, and what other codes do

**Other codes.** None holds a vanishing phase's structural parameters automatically.
- GSAS-II floors every phase scale at 1e-12, silently (`GSASIIstrMath.py:3178`, checked),
  and has no significance test. A column that goes exactly flat (norm under 1e-14) is
  dropped for that cycle with a printed warning (`GSASIImath.py:263-268`, checked). A
  user can fix a phase's fraction, cell, Uiso and moments in a sequential run by hand
  ("Fix FXU").
- TOPAS floors scale at 1e-11 by default (Tech Ref § 2.17, Table 2-1). Its nearest feature
  is opt-in: `Remove_Phase(0.3, 0.5)` deletes a phase whose weight percent is below 0.3 %
  and whose esd exceeds half its value, at the end of a cycle, and prints "Deleting phase"
  (Tech Ref § 20.19). Both numbers are the caller's.
- FullProf 8.20 resets a negative scale to 10⁻¹⁰ each cycle, halves its shifts and prints
  "Scale factor <0, fixed to 1.E-10" (a run and the binary's strings, checked). It never
  removes the phase or holds its other parameters.

So the closest practice, TOPAS's, is an opt-in removal with caller-set thresholds. rietx's
hold is on by default, which no program does. It stays tier 3 on the maintainer's
approval, ruled "yes" on 2026-10-19.

**Reading of the ruling.** "An option, not mandatory": today the hold has no switch, so it
is mandatory. The session reads the ruling as on by default at 3σ, with a caller able to
switch it off or set another threshold. The other reading is off by default, as TOPAS's
removal is. On by default is the more accurate default. An unseen phase's free cell walked
14.9 Å from the truth on the in-situ ramp while Rwp did not move. In a chain that wandered
cell seeds the next pattern, so the phase is in the wrong place when it appears.

**Where the switch lives.** One number, read in five places (`refine.py:513, 1571, 1719`,
`multi.py:405`, and the cell window's screen through `CompiledModel.phase_support`). The
proposal is a plan field, `RefinementPlan.phase_support_sigma`, default 3.0, `None` for no
hold, carried by `PlanSpec` so the GUI and `.rxt` see it. `PHASE_UNCONSTRAINED` reads the
same number, so the diagnostic follows the caller's choice. This is a B14 lift into a seat.

### B5. Zero and negative esds: what is accurate

**An esd of zero is never a measurement.** It claims the intensity is exact, which no
counted quantity is. A negative esd has no meaning. So every such value is an artefact of
whatever wrote the file. There are four causes, and they need different treatment.

1. **√0 of a zero count.** The writer computed σ = √N on raw counts, and N was 0. The
   √N estimate of Poisson variance fails at zero: the true variance is the expected count,
   which is above zero. The point is a real measurement and belongs in the fit with σ of
   about one count. This is the case when counts are low: neutron data, high-angle tails,
   short scans.
2. **A channel with no measurement.** Masked pixels, the beamstop shadow, gaps between
   detector modules, and bins beyond the detector edge after integration. Integration
   software writes these as y = 0, σ = 0 (recalled for pyFAI and Mantid, not checked). The
   point carries no information and must leave the fit.
3. **A processing error.** Subtraction or scaling that zeroed or negated the column. A
   negative esd is always this.
4. **Rounding.** A normalised pattern with σ near 10⁻⁴ printed to three decimals reads 0.

What a file cannot tell a reader is which one it holds. It can tell case 1 apart in one
common situation. Where the esd column is Poisson on one scale, σ²/y is the same constant c
on every channel with counts (c = 1 for raw counts). Then a zero esd at y = 0 is a zero
count, and its σ is √c, one count on the file's scale. That matches rietx's own fallback
for a file with no esd column, √max(y, 1), and TOPAS's default weighting 1/Max(Yobs, 1)
(Tech Ref § 6.2).

**Why not drop every zero.** Dropping genuine zero counts biases the background upward.
At a mean of one count per channel, 37 % of channels read zero, and the survivors average
1.58 counts. At three counts the bias is 5 %, and at ten it is negligible. That is
arithmetic on the Poisson distribution. GSAS-II's xye reader zero-weights every channel
with y ≤ 0, so it carries this bias on sparse data.

**Other codes.**
- GSAS-II 5.8.4 depends on the reader, and none reports anything (all checked). The xye
  reader zero-weights y ≤ 0, skips a line whose esd is negative, and replaces an esd of
  0 with Poisson 1/y (`imports/G2pwd_xye.py:170-186`). The skip has a defect: the 2θ value
  is appended before the skip, so every later point is paired with the wrong angle. The
  fxye reader zero-weights a channel when y ≤ 0 or σ ≤ 0 (`G2pwd_fxye.py:86-91`). The CIF
  reader raises every esd below 1 to 1 (`G2pwd_CIF.py:280-292`, agent-read).
- TOPAS weights by 1/σ² whenever the file has σ, otherwise 1/Max(Yobs, 1) (Tech Ref § 6.2,
  § 21.10). The reference is silent on σ ≤ 0. A zero σ would divide by zero (inferred).
- FullProf 8.20 is silent and inconsistent (runs on its PbSO₄ example, agent-run). An esd
  of 0 acted as σ = 1, a hundred times the weight of its σ = 10 neighbours. A negative esd
  acted as its absolute value. A channel with y ≤ 0 got weight 1 whatever its esd. A file
  with no esd column was weighted 1/y, although the manual says σ = y (p. 74). The manual
  mentions none of this.

**Options.**
1. Keep today's floor (σ raised to 10⁻³ × the median esd). Wrong in all four cases: it
   gives the point about a million times its neighbours' weight.
2. Drop every channel with σ ≤ 0 and report it. Never invents a number. Biases sparse
   backgrounds as above.
3. GSAS-II's xye rule. Silent, and drops genuine zero counts.
4. Classify. A zero esd at y = 0 in a column that is Poisson on one scale becomes a zero
   count at σ = √c. Every other σ ≤ 0 drops the channel. Both are reported, by line.

**Recommendation.** Option 4, built in WP-1952 (the WP for plain x-y files). It is the
only option correct in case 1 and in cases 2-3. The constant-ratio test costs one median.
Case 4 (rounding) falls to the drop, which loses a few points and reports them. Until
WP-1952 lands the floor stays, and the table names WP-1952 as its replacement.

The case against: the ratio test may misfire on a column that is nearly Poisson. Examples
are counts with a dead-time correction, or a sum of two detector banks. There a zero count
would get a slightly wrong σ. That is still far better than today's 10⁻³ floor. The pick
would change if WP-1952 finds a format where a zero esd marks good data.
