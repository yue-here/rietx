# series — a series a scientist can predict and drive

**Opened 2026-11-16** by the maintainer, in a chat on series design rules ("separate
milestones, one for parametric, one for series"). The block 23xx is claimed for it.
[`../ROADMAP.md`](../ROADMAP.md) § series carries the short prose, and the WP index lists
the rows.

A Claude session wrote this file the same day from that chat. The six rules carry the
maintainer's answer to each, and all six are accepted. The title, § Scope and § Acceptance
are the session's wording. On 2026-11-18 a later session proposed four corrections to
§ Acceptance and found none to make to the title or § Scope. The maintainer approved the
corrections in chat ("Make them"), which ends the draft.

Narrative about the WPs below goes to the record of the release in flight,
[v1.13](v1.13.md) today, as for every other WP (protocol rule 5).

## Scope

The reader is anyone who refines a set of related patterns: a temperature ramp, an in situ
or operando run, a tray of related specimens. That includes a first-time user, an expert
arriving from TOPAS or GSAS-II, and an agent.

The maintainer's account of the typical experiment (2026-11-16, from the session's note):
most series are measured with the specimen in a fixed position and the instrument
conditions fixed. The changes come from the environment, such as thermal expansion, or from
the sample, such as a reaction. The most common case is a temperature series on a
laboratory or synchrotron instrument.

The maintainer's statement of what the module is for (2026-11-16, close to verbatim in the
session's note): "the series module should contain all of the machinery for doing series
refinements, and it should have sensible defaults that work in most situations, but when
they don't work, it's clear that it should be changed because the experimenter is doing
something more advanced than usual."

Four more points the maintainer agreed in the same discussion:

- Before choosing a route, an agent asks the user for the facts a pattern cannot show.
- The skill carries recipes for the scenarios that make up most series.
- Choosing the patterns to calibrate on is the refining agent's judgement. It is no
  heuristic built into rietx.
- Traps belong in the skill.

**Relation to [parametric](parametric.md).** That milestone builds the joint fit and its
equations for an expert who writes their own model. This one decides how a series is
declared and what it does by default. The two share one way of declaring a parameter
(rule 1 below), and rule 2's start from a series result needs WP-2103 from the parametric
milestone. They stay separate
because their readers and their acceptance differ (ruled 2026-11-16).

## The rules

Six. Each follows from [`../DESIGN.md`](../DESIGN.md) § Rules, and the last column says
which. "Accepted" records the maintainer's answer in chat on 2026-11-16.

1. **Each parameter is declared as one of four kinds.** The caller says, with globs,
   whether a parameter is refined separately on each pattern, refined as one value common
   to all patterns, fixed at a value the caller supplies, or computed from an equation in
   the pattern's temperature or time. A parameter with no declaration is refined separately
   on each pattern. The globs work as `SharingMap` and `hold` already do.
   *Accepted* ("I think it's a good idea"). DESIGN Rule 5, convention.

2. **Two calls, and each accepts only the kinds it can honour.** The series call fits the
   patterns one after another, each started from its neighbour's result, and accepts
   per-pattern and fixed parameters. The joint call fits all patterns together in one
   least-squares problem and accepts all four kinds. A joint fit can start from a series
   result. A parameter cannot be declared common or by equation in the series call, so a
   series never approximates one by freezing a single pattern's value.
   *Accepted* ("Yes, two calls"). The session first proposed one call whose declarations
   chose the method, then leaned to two calls on rietx's own convention (each kind of
   answer has its own call and result type), on practice (TOPAS, GSAS-II and FullProf users
   build a different input for each) and on DESIGN Rule 5. The start from a series result
   waits on WP-2103. What would reopen it: evidence that users stop at the series call and
   hold a first-pattern value where they meant a common one.

3. **Fitting one after another gives the same answer as fitting each pattern alone.**
   Starting from the neighbour saves iterations. The one-after-another fit applies no
   smoothing or limit between neighbouring patterns. Where the answer depends on the order,
   the result reports by how much, as `direction="both"` does. A link between neighbours
   is a joint-fit feature: a declared equation, or the kernel of WP-1963 if a real series
   comes to need it.
   *Accepted* ("I think I agree"). DESIGN Rule 2, an identity that can be tested.

4. **rietx contains no code that makes series strategy choices.** It does not choose the
   patterns to calibrate on, the order in which parameters are freed across the series, or
   when the result is good enough. The caller makes those choices. The skill documents how
   for the common cases. A named preset may bundle rule 1's declarations for a common
   experiment, and it does nothing else.
   *Accepted* ("I think this is reasonable"). DESIGN Rule 1, the third kind: facts outside
   the pattern.

5. **A detectable failure mode is reported as a number in a field.** When a calculation can
   expose a known problem, rietx computes it and stores it on the series result, on every
   pattern. It sets no threshold, raises no diagnostic code and takes no action. A value
   that was not measured is `None`.
   *Accepted* ("I think that's reasonable"). DESIGN Rule 1 ("every withheld verdict leaves
   its statistic") and Rule 4, a new output.

6. **Without being asked, rietx does four things in a series.** It detects a failed fit:
   one that diverged, raised, or carries an error-level diagnostic. It retries that pattern
   from different starting values, at most the three attempts that exist today, the last
   from the caller's own starting model. It keeps the best attempt. It does not start the
   next pattern from a failed one. A retry does not change which parameters are free or
   what value a fixed parameter has. Each act is recorded.
   *Accepted*, with one ruling the same day: a fit that converged in a wrong minimum is not
   a failed fit, and the series does not retry it on a goodness-of-fit comparison. The
   ratio is a field under rule 5 (WP-2080, option A, "Yes, field only"). DESIGN Rule 1,
   protecting work already done.

## Ruled after the open

- **The default stays as it is** (maintainer, 2026-11-16: "keep today's default"). A series
  call with no plan refines on every pattern what the default single-fit plan refines: the
  zero shift, five profile terms, the background, the scale and the cell. It assumes nothing
  about the experiment. The typical temperature series, with a calibrated instrument held,
  is a named preset and a skill recipe that a caller opts into. The options put: keep the
  default; hold the instrument at the first pattern's fitted values (measured to fail with
  confident esds, WP-2081); refine the instrument as one common value through the joint fit
  (unmeasured, and not buildable before WP-2103). This answers WP-2081 question 1 with its
  option a. What would reopen it: a measurement showing the common-value route correct and
  affordable on real ramps.
- **`SEQUENTIAL_WIDTH_GROWTH` is removed** (maintainer, 2026-11-16: "Remove"). The warning
  fired when a phase width reached 3× its first measured value, GoF had doubled and the
  growth exceeded 3 esds, on three unaudited constants. The width trajectory and each
  pattern's GoF are already in the result, so rule 5 is met without it. Removed in WP-2081
  on 2026-11-17, with no field added, under `THRESHOLDS_VERSION` 1.15.
- **No skill line says that holding every width invents a transition** (settled by Claude
  under DESIGN Rule 3 and Rule 4's test for a skill row, 2026-11-21). The claim rests on one
  run on the CuCr2O4 ramp, which is development data (WP-2081). A search of the maintainer's
  paper stores found no paper that tests it. The terms were sequential refinement,
  parametric, broadening, splitting beside broadening, pseudosymmetry, Suchomel and Kemei.
  Stinton & Evans (2007) and Stephens (1999) are held, and neither states it. From recall,
  phase-transition studies often report a small distortion first as broadening that
  depends on hkl. That is the mechanism WP-2081 infers, and no paper is named because none
  was read. The practice the trap follows from is already in the skill:
  `references/series.md` § Microstrain evolves along a chain says to hold the instrument
  and leave each phase's widths free. The measurement stays in WP-2081. The alternative was
  a row tagged `(Measured: …)` on the one run. What would reopen it: a published sequential
  or parametric study in which a held profile moves or creates a distortion.
- **Issue #1214 closes when PR #1473 merges** (settled by Claude under rule 6 and the
  maintainer's WP-2080 ruling of 2026-11-16, 2026-11-21). The issue reports a warm fit
  kept in a wrong minimum under a fence that cannot see it. Its options 1 to 3 escalate a
  converged fit on a comparison of fit quality. Rule 6 says the series does not retry such
  a fit, and WP-2003 removed the fence. Its option 4 is documentation, and the reworked PR
  lands it beside the field `SeriesEntry.warm_gof_over_seed`. The PR's body already says
  "Closes #1214". An open issue would promise work the rules exclude. The alternative was
  to keep it open as a record of the two noise draws in 20 that keep a wrong cell. WP-2080
  names what would reopen it: evidence that agents or users do not read the field. A
  comment for the issue was drafted and waited for the maintainer's approval of the batch.
  **Ruled by Yue 2026-11-22:** posted
  (https://github.com/yue-here/rietx/issues/1214#issuecomment-7078724868). The issue had
  already closed on 2026-11-21; PR #1473 is still open.

## Open decisions, answered 2026-11-22

Two were open, and both were the maintainer's. Answered 2026-11-22 under the maintainer's routing rules of that day (WP-2237): each item was settled by Claude and checked by a fresh agent that did not see the pick, or brought to the maintainer, who answered "All as recommended".

- **`SEQUENTIAL_MOMENT_ONSET`** still fires on a tuned threshold, against rule 5. It is
  magnetic, so the magnetic path's owner rules on it. **Ruled by Yue 2026-11-22:** sent to Mike: posted as question
  (3) on #1075 (https://github.com/yue-here/rietx/issues/1075#issuecomment-7078724635).
- **The audit label on today's default plan.**
  `SequentialRefinement.fit:plan` is recorded as unanimous (`ambiguity=1`), and the
  traditional calibrate-then-hold route is a named dissent. A named dissent fails the
  unanimity gate of DESIGN Rule 1. Rule 4 above puts series strategy in Rule 1's third
  kind, since only the experimenter knows whether the instrument held still. The proposed
  correction (2026-11-21): `ambiguity` from 1 to 3; tier 3, the value and the plan kept;
  `grounds` rewritten to cite the 2026-11-16 ruling and its named dissent; `approved` set
  to the maintainer's date. `_audit.py` was unchanged until the maintainer approved.
  **Settled by Claude 2026-11-22, checked blind:** the label correction (`ambiguity` 1 to 3, `grounds` citing the 2026-11-16 ruling and
  its named dissent) is settled. **Ruled by Yue 2026-11-22:** tier 3 with the plan kept, approved 2026-11-22.

## The WPs

| WP | What it adds | Where it stands |
|---|---|---|
| [2081](../wp/2081-how-a-series-holds-what-the-setup-fixes.md) | the design discussion these rules came from, its measurements and its twelve questions | moved here 2026-11-16 |
| [2080](../wp/2080-a-warm-fit-in-a-wrong-basin.md) | the goodness-of-fit ratio as a field, ruled 2026-11-16 | moved here 2026-11-16 |
| [1420](../wp/1420-a-held-phase-re-enters-or-says-it-cannot.md) | a phase held on one pattern gets back in on a later one | proposed for this milestone with tasks 2 to 5 retired as written. Rules 4 to 6 exclude a series code and a retry of a converged fit (issue #1402's option A). **Settled by Claude 2026-11-22, checked blind:** the move stands as proposed (answered 2026-11-22 under the routing rules of WP-2237); the file's `Milestone` header is not touched here. |
| [1453](../wp/1453-both-directions-name-the-lower-cost.md) | the two directions of a series compared by cost | proposed for this milestone. Option 1's cost pair is a rule 5 field whose names go to the maintainer, and rule 6 excludes option 3's cold rung. **Settled by Claude 2026-11-22, checked blind:** the move stands (answered 2026-11-22 under the routing rules of WP-2237); option 1's cost-pair field names go to the maintainer when WP-1453 is built. |
| [1524](../wp/1524-the-step-scans-last-two-blind-spots.md) | the step list's two blind spots | not moved (2026-11-21): WP-2003 removed the scan it targets, and PR #1588 closes it with tests alone |
| [1317](../wp/1317-series-scrubber.md) | the GUI's view of a finished series | not moved: [gui-overhaul](gui-overhaul.md) § R7 carries it (maintainer, 2026-11-21) |
| [2103](../wp/2103-a-joint-fit-has-the-verbs-a-single-fit-has.md) | hold, tie and restart on a joint fit | stays in parametric; rule 2's start from a series result depends on it |
| [2003](../wp/2003-the-chain-actions.md) | the tiers of the series' automatic actions | stays in generality |

The two proposed rows keep `Milestone: unscheduled` in their files until their next edit
carries the move (the moves were settled 2026-11-22). Each has an open pull request that edits the same header line (#1401
and #1594). WP-1317's pull request, #1395, merged on 2026-11-21.

WP-2081's twelve questions under the rules: 2 and 3 fall to rules 1 and 2; 4 to rule 6; 5 to
rule 4; 7 and 9 to rule 5; 11 to rule 2, which keeps the two calls separate. Question 1 is
ruled above: the default stays. Questions 6 (a view of the raw series) and 8 (a structure-free phase beside a
structural one, WP-2108) are work of their own.

## The order

Rules 3 to 6 describe the code as it nearly stands, so their work is small: the field for
WP-2080, a fixed value surviving a restart (WP-2081 question 4), and
`SEQUENTIAL_MOMENT_ONSET` once ruled. `SEQUENTIAL_WIDTH_GROWTH` is removed. Rule 1 comes next, as a declaration on the series call. Rule 2's start
from a series result waits on WP-2103. The default is ruled, so a preset for the typical
temperature series can be written. The documentation for a user arriving from another program's
sequential mode is written with rule 1. Before rule 2 is built, a second real series that
nobody who changes the package has run is named, with its independent measurement. Each
WP's `Priority:` line outranks this paragraph.

## Acceptance

These rows were drafted at the open, as protocol rule 6 asks, and approved with four
corrections on 2026-11-18 (WP-2081's log). Rwp is reported and is no part of any bar.

- **A series equals its patterns fitted alone** (rule 3). On the synthetic LaB6 thermal
  ramp and the CuCr2O4 ramp, every pattern's value from the one-after-another fit agrees
  with the same pattern fitted cold and alone from the caller's models. The bar is the
  measured spread between two independent fits of that pattern, because a fixed fraction of
  an esd would test where the solver stopped (`tests/CLAUDE.md` § Budgets in tests). The
  direction gap of `direction="both"` compares two chains with each other, so it is a
  second check and never stands in for this one. Measured so far: eight CuCr2O4 patterns
  within 1e-6 Å (WP-2081, `cold_check`). The spread is not measured yet.
- **A fixed value stays fixed** (rules 1 and 6). On WP-2081's cold-restart fixture, a zero
  shift fixed at 0.00797° reads 0.00797° on every pattern and every attempt, and the cell
  stays within 2 ppm of the truth. Today the restarted pattern holds 0.0 and the cell is
  546 ppm off.
- **A common parameter gives honest esds** (rules 1 and 2). On a synthetic LaB6 ramp of 7
  patterns over 150 noise replicates, with the zero shift and profile declared common, the
  common zero shift is within 2 esd of the truth, and each pattern's cell error divided by
  its esd has a standard deviation no further from 1 than the same ramp gives with those
  parameters refined on every pattern. Issue #1556 measured 0.79 to 0.93 for that arm, and
  2.30 to 2.43 with them fixed at pattern 0's values. Neither is rerun here.
- **A real ramp with a known answer** (rules 1 and 2). On the CuCr2O4 ramp, every route the
  documentation recommends closes the b and c axes between 111 and 135 K. The ramp is
  development data, so this row can fail a route and cannot prove one. Measured at the
  open (WP-2081's log, 2026-11-16): the default chain and a joint fit with a common zero
  shift both close between 111 and 123 K, and a joint fit with one common profile and no
  sample width closes between 123 and 134 K.
- **No series action or code rests on a tuned threshold over a fit metric** (rules 5 and
  6). The audit table holds no series row at `unaudited`, and each remaining thresholded
  series code carries its owner's ruling. The one left is `SEQUENTIAL_MOMENT_ONSET`, whose
  owner is the magnetic path's.
- **The series call refuses what it cannot honour** (rule 2). A parameter declared common
  or by equation in the series call raises, and the message names the joint call. No series
  result holds a common value by freezing one pattern's.
- **The documentation agrees with itself** (rule 4). The skill, the guide and the manual
  give one route for the typical temperature series. Each skill trap names a source outside
  rietx's own runs. A page in the manual's Switching tab takes a user from another
  program's sequential mode to a first series.

## Not in scope

- The joint fit's machinery and the equation grammar ([parametric](parametric.md)).
- A kernel over the pattern coordinates
  ([1963](../wp/1963-a-kernel-over-the-pattern-coordinates.md)), until a real series needs
  it.
- Rigid bodies in a series (1811, 2114), which belong to rigid-bodies.
- New built-in checks that act or warn on a threshold (rule 5).
