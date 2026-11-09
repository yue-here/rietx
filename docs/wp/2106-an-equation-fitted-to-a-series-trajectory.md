# WP-2106 — an equation fitted to a series trajectory

Milestone: parametric · Status: ✅ 2026-11-09 — rx.fit_trajectory and the .gpx's stored equations; follow-ups on #1489
Depends on: 1964 (the grammar and its derivative rules)

## Goal

After a series, a user fits an equation in the grammar to a parameter's trajectory,
weighted by its esds, and gets the coefficients with esds. A GSAS-II user's stored
sequential equations come across too.

## Context

The milestone's reader includes GSAS-II users, and every other WP in it builds the TOPAS
route: one joint residual. GSAS-II's practice is different. Its equation is a
python-syntax string fitted to the sequential results table after the refinement, never
in a joint residual (`docs/practice.md`), and it stores those equations with the
sequential results (`SeqParFitEqList`, GSAS-II 5.8.4). Evans also recommends a
sequential fit as a first look. Series practice here agrees: the setup is calibrated and
held, and full refits are unusual.

A clean-context review of the milestone found this gap on 2026-11-04. rietx has no such
fit: `SeriesResult` carries trajectories, and neither `schemas/sequential.py` nor
`guides/equation.md` fits anything to them. Today a user exports the table and writes a
scipy script.

The comparison with a joint fit is the content of the page a user needs.
`guides/equation.md` § When to declare an equation instead of fitting a series already
says why a joint fit is the stronger form. A trajectory's esds are each conditional on
their own pattern, and a chain's trajectory is path-dependent (root CLAUDE.md § Series).
So the result must say it is a fit to a trajectory, and which direction of the chain it
read.

The seams are small. The grammar gives the value and its exact derivative, so the fit
is a few lines of weighted least squares over one equation, and a quarantined pattern
stays out as it does from a median.

The tier of each rule this WP adds ([generality § The rule](../milestones/generality.md#the-rule)),
written 2026-11-09 at the start: the fit is arithmetic (tier 1), weighted least squares with
each coefficient's esd propagated from the trajectory's own. A quarantined pattern is left
out by the chain's own test (`_rejected`, ruled 2026-11-03), and a point with no esd has
no weight, so it is left out too (tier 1); both are named in the result. The esd follows
the package's convention for every refined esd, scaled by χ²/ν (named practice), and the
unscaled one rides beside it, since a refiner who trusts each pattern's esd would not
scale (no unanimity), so neither is chosen and no threshold reads them. No new diagnostic. The
reference is a synthetic ramp with a known truth and the joint fit beside it; there is no
published number, so the fit ships not yet validated.

GSAS-II's licence is its own (`ATTRIBUTION.md`), and this package takes concepts only from
its code. Any reader takes the stored format from a file's contents.

## Non-goals

- A second fitter for the joint case. That is `refine_multi`.
- GSAS-II's external functions in an equation.
- A new diagnostic beyond what the fit's own numbers say.

## Tasks

- [x] The fit: a trajectory, an expression and a `variables` dict in, coefficients with
  esds and χ² out. Name it as a consent item for the maintainer, since it joins the top
  level. (`rx.fit_trajectory` → `rx.TrajectoryFit`; the names are the handover's consent
  item.)
- [x] Which trajectory: `direction="both"` gives two, so say which is read, or fit each.
  Skip quarantined patterns and say so. (Under `direction="both"` the caller names the chain,
  since their gap is path dependence nothing resolves; `TrajectoryFit.skipped` names each
  point left out.)
- [x] Measure on a synthetic ramp against the joint fit: do the coefficients agree within
  their combined esds, and how much wider are the esds? (Yes, within 0.05 combined esd on
  twenty seeds; the unscaled esds equal the joint ones within 1.1 %, and the scaled ones
  move with five degrees of freedom' χ²/ν, 0.35-1.30× the joint ones.
  `2106-measure/trajectory_vs_joint.py` and its results file.)
- [x] GSAS-II's stored equations: read `SeqParFitEqList` from a `.gpx` into this fit's
  input, or refuse by name. Lower GSAS-II's spelling onto the grammar, with a table of
  each rewrite. (`Gsas2Model.sequential_equations`, one `Gsas2SequentialEquation` each;
  the rewrites are `GSAS2_EXPRESSION_REWRITES`, held equal to the table in
  `reference/foreign-models.md`. The layout was read off the contents of the public
  GSAS-II tutorials' `steel.gpx`.)
- [x] Manual: `guides/equation.md` beside the joint route, and `switching/gsas2.md`.
  (`guides/equation.md` § Fit the equation to the series trajectory, run by
  `examples/guides/equation.py`; the reference halves are `reference/parametric.md` § An
  equation fitted to a trajectory and `reference/foreign-models.md` § Equations stored
  with a sequential fit.)
- [x] Skill: the series reference's row. (The joint-fit row of `references/series.md`
  names `rx.fit_trajectory` as the line through a chain, inside the file's budget;
  `fit_trajectory` joins the API index's series section.)

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_sequential.py tests/test_parametric_series.py tests/test_manual_api.py
.venv/bin/python -m ruff check src tests examples
```

## References

- Toby, B. H. & Von Dreele, R. B. (2013). *J. Appl. Cryst.* 46, 544-549 — GSAS-II.
- WP-1964 (the grammar), WP-1325 (the joint fit), WP-1051 (quarantine).

## Handover log

- **2026-11-09 (a ghostshift runner, closing)** — The checklist is done and the WP closes.
  After a series, a user can now fit an equation to one parameter's trajectory, weighted by
  its esds, and get the coefficients with esds and χ², the way a GSAS-II user works. The
  result says it is a fit to a trajectory and which chain it read, and names every point it
  left out. On a synthetic ramp it agrees with the joint fit to a twentieth of an esd, and
  its unscaled esds are the joint fit's; the χ²/ν-scaled ones carry the noise of a handful of
  degrees of freedom, so both are reported and neither is chosen. A GSAS-II project's stored
  sequential equations now read in, rewritten in the grammar, and anything outside the
  rewrite table is refused by name. The consent item for the maintainer is below.
  - *Consent item: four names join the top level.* `rx.fit_trajectory(series, path,
    expression, variables, *, coordinates=None, chain=None)` returns
    `rx.TrajectoryFit`, with `rx.TrajectoryVariable` and `rx.TrajectorySkip` beside it (the
    three schema classes are top-level because every class in `rietx.schemas` is). The
    reader adds no top-level name: `Gsas2Model.sequential_equations`, one
    `Gsas2SequentialEquation` each, and `rietx.io.projects.gsas2.lower_gsas2_expression`.
  - *Done.* `src/rietx/trajectory_fit.py` (walked, audit owner 2003; no module-level
    number): the grammar's exact gradient, scipy TRF with the variables' own bounds, the
    covariance through `optimize.statistics.normal_factors`, a unit residual giving the
    unscaled inverse. Coordinates are a `CoordinateTable` row per pattern as passed (keyed
    by `SeriesEntry.index`, so a pattern that failed every rung keeps its row), or the
    series axis as `x`. Under `direction="both"` the caller names the chain;
    asking a one-way series for the other chain raises. A step or angle path is refused. Quarantine is `_rejected`, the
    median's test. The `.gpx` layout (`SeqParFitEqList` of `ExpressionObj`: `expression`,
    `freeVars` label → [name, value, flag], `assgnVars` label → column, `depVar`, and
    `SeqPseudoVars` for a pseudo-variable dependent) was read off the contents of the
    public GSAS-II tutorials' `steel.gpx`, now `tests/local_data.py`'s
    `gsas2-tutorials/steel`. The equation is parsed with python's `ast`, which runs nothing,
    and printed in the grammar; every rewrite is a row of `GSAS2_EXPRESSION_REWRITES`, held
    equal to the table in `reference/foreign-models.md` by test, and checked against python
    evaluating the same text. GSAS-II's `sin`/`cos`/`tan` are taken as degree functions on
    `docs/practice.md`'s record; no GSAS-II source was opened. Manual:
    `guides/equation.md` § Fit the equation to the series trajectory,
    `reference/parametric.md` § An equation fitted to a trajectory, `reference/foreign-models.md`
    § Equations stored with a sequential fit, `switching/gsas2.md`. Skill: the joint-fit row
    of `references/series.md` and the API index's series section.
  - *Measured* (`[dev]`, darwin/arm64). `2106-measure/trajectory_vs_joint.py` and its
    results file: twenty seeds of the guides' seven-pattern LaB₆ ramp, each run as a chain
    both ways and as one joint fit of the same expression. Largest gap between the
    trajectory's coefficients and the joint fit's: 0.045 combined esd (a0), 0.031 (k), the
    same on both chains. Unscaled esd over the joint esd: median 1.000, range 0.995-1.011.
    Scaled: median 0.90, range 0.35-1.30, with the trajectory's χ²/ν at 0.13-1.70 on five
    degrees of freedom. Against the truth, (value − truth)/esd has rms 1.00 and 0.68 for the
    joint fit and the unscaled trajectory esds alike, and 1.31 and 0.85 for the scaled
    ones. The guide's own seed: the two lines 0.07 and 0.03 of the joint esds apart.
    Fast selection (`-m "not slow"`, `[dev]`, darwin/arm64, on the Mac at `-n 2` through
    the shared test gates, since pearl did not answer ssh): on 1aa46f2b1, before the
    review fixes, 14386 passed, 415 skipped, 32 xfailed and 2 failed in 15:35. Both
    failures were `reference/series.md` over the manual's 50 000-character page cap,
    after this branch's section on it; the section moved to `reference/parametric.md` in
    the next commit, and the page is now byte-identical to main. On the final tree the
    touched files re-ran green: `test_trajectory_fit.py`, `test_projects_gsas2.py`,
    `test_manual_api.py`, `test_audit_table.py` and `test_skill.py` (378 passed),
    `test_manual.py` and `test_reference_pages.py` (112 with `test_manual_api.py`),
    `test_docs_consistency.py` (25), and the equation guide's script. The run added 21
    tests to the fast tier, together 0.03 s locally (`tests.added_test_times`); the
    review commit added 8 more. The full suite was not run: nothing here moves a
    measured number of an existing fit.
  - *Review.* `/code-review` was not run, because from this session it would read the main
    checkout's stale branch; an Opus subagent reviewed the branch diff instead.
    It found eleven things; fixed in 18c8eb6e4: a pair of variables the trajectory moves
    only together got small, confident esds (now `None`, through
    `discarded_directions`), step and angle paths were fitted (now refused), a cancelled
    chain refused the full coordinate table, a non-finite value was labelled `no_esd`, the
    lowering's parentheses doubled the nesting (a 30-term sum hit the depth limit; it now
    builds the grammar's own tree, read from the rewrite table alone, which also makes
    the manual-table test able to fail), `1e999` lowered to an unbound `inf`, and two
    messages and two doc lines. Declined: none; the degree reading against GSAS-II's own
    output is #1489, item 1.
  - *Generality* (the judge's sections, condensed from its tables into prose, its words kept, then the
    author's answer):

    > **WALKED += "trajectory_fit.py": 2003.** Holds. Adding a file to the walk only widens
    > what the table sees. Confirmed at trajectory_fit.py:566: no module-level number, one
    > string `SERIES_AXIS_NAME`. Note: the solver settings are scipy's inline defaults
    > (`method="trf"`, `x_scale="jac"`, ftol/xtol/gtol 1e-8), which no walk sees. Against:
    > none found. What would change it: nothing on the entry itself.
    >
    > **(a) Quarantined point left out via `_rejected`.** Holds; the case for is stronger.
    > The fit drops points the caller passed; kind 1. An error-level code means "do not read
    > the values, for any purpose" (generality.md, Attention clause 2). None found against:
    > GSAS-II stops its chain at a failed histogram, so it has nothing to drop
    > (practice.md:326). One test for both the median and this fit keeps them from drifting
    > apart. Synthetic data only; recorded in `TrajectoryFit.skipped`. What would change
    > it: a case where an error-level code about one phase leaves another phase's point
    > sound.
    >
    > **(b) Point with esd None, ≤0 or non-finite left out.** Holds. Arithmetic: 1/esd² is
    > undefined. When every esd is missing, the fit refuses rather than falling back to unit
    > weights. But a non-finite *value* with a good esd is also labelled `no_esd`
    > (trajectory_fit.py:617): wrong label.
    >
    > **(c) Two esds, `esd` scaled by χ²/ν, `esd_unscaled` beside it.** Holds; both are
    > reported, which is the right answer for kind 3. The naming leans one way: the plain
    > name `esd`, the first number `__str__` prints and `covariance` are all scaled, and with
    > χ²/ν < 1 it is narrower than the unscaled esd. `chi2_floor=True` is neither used nor
    > offered. The refined-esd convention also includes the Bérar–Lelann inflation, which is
    > not applied, and the change does not say so. TOPAS scales by the GoF
    > (practice.md:929); whether GSAS-II's `DoParEqFit` scales is not recorded
    > (practice.md:931), so the tier-2 claim rests on one program. What would change it:
    > GSAS-II's scaling default recorded in practice.md.
    >
    > **(d) Forward chain by default under direction="both".** Weak; the case against is
    > stronger. Kind: none given. The difference between the chains is path dependence,
    > which the package reports with no threshold. A refiner whose ramp was measured
    > cooling, or whose sample shows hysteresis, reads the chain in acquisition order or
    > fits both. What would change it: under "both", requiring `chain=`, or fitting both
    > chains and returning the coefficient gap.
    >
    > **(e) GSAS-II's sin/cos/tan read as degree functions; any other spelling refused.**
    > Holds, on a reading of GSAS-II's code that nothing in this branch measures against
    > GSAS-II's own output. practice.md:900 says "checked". The comment cited a heading that
    > is "Angles". steel.gpx has no trig function, and the property test checks the rewrite
    > against lambdas built on the same assumption: that verifies the arithmetic, not the
    > convention. What would change it: a stored trig equation whose fitted values GSAS-II
    > wrote, reproduced.
    >
    > **(f) `at_bound` from scipy's TRF `active_mask`.** Weak; the package's own record
    > counts against it. TRF's mask is set within XTOL of a bound whatever the gradient
    > (least_squares.py:300-311, WP-1929), and proximity tests missed 9 of 32 binding cases
    > (WP-1434). A held variable was written `at_bound=False` without any check: WP-1076's
    > shape. What would change it: LM's exact active set or the multiplier test, and `None`
    > for a held variable.
    >
    > **(g) Covariance through `normal_factors`.** Holds. Tier 1; the unit residual gives a
    > factor of exactly 1 (statistics.py:177-183, `chi2_floor` off). A flat direction gets
    > `esd` = `None`.

    Author: (b) taken, a non-finite value is skipped as `no_value`. (c) both kept and
    named; the docs now say the scaling is a refined esd's and that Bérar–Lelann is not
    applied, and the tier claim is narrowed to that. (d) taken: `chain=` is required under
    `direction="both"`. (e) the comment's heading fixed; the check against GSAS-II's output
    is issue #1489, item 1. (f) partly taken: `None` on a held variable, and the field is
    documented as scipy's proximity-based active set; a load test is #1489, item 5.
  - *Left, on issue #1489:* a GSAS-II-written `.gpx` for the refused arm of the
    milestone's `.gpx` row (no GSAS-II install was at hand, so the refusals are tested on
    pickles of the same layout), evaluating a `TrajectoryFit` at a coordinate, a
    pseudo-variable dependent, and GSAS-II's own table as a trajectory.
  - *Overlap.* WP-2101 owns `switching/gsas2.md`'s GSAS-II sequential section and the skill's
    series rows too; its `### Inherited` names what this branch wrote there. No 2101 or 2103
    branch was on origin at the start.
  - PR #PR_N. Next: the maintainer's ruling on the four names; then issue #1489's first
    item closes the milestone's `.gpx` row.

- **2026-11-04** — Filed from the clean-context review of the milestone. No open WP
  owned it: 1325 and 1964 build the joint route, and 2105 fenced the `.gpx` on a claim
  that proved false. Next: the fit's name, then the fit.
