# parametric — a parametric refinement written by hand ports to rietx

**Opened 2026-11-04** by the maintainer, on the session's track review of
2026-11-03 and 2026-11-04. The block 21xx is claimed for it.
[`../ROADMAP.md`](../ROADMAP.md) § parametric carries the short prose, and the WP
index lists the rows.

Narrative about the WPs below goes to the record of the release in flight,
[v1.11](v1.11.md) today, as for every other WP (protocol rule 5).

## Scope

The reader is an experienced TOPAS or GSAS-II user who builds their own parametric
refinements. The maintainer's direction of 2026-11-03: all the machinery in place, on
an accessible and well-documented surface. Built-in heuristics matter less, because
these users will write their own. Presets for beginners can follow later, and they
will expand into the same grammar.

The maintainer's ruling of 2026-11-04: build robust machinery, and do not overfit to
TOPAS. A primitive is designed on rietx's own terms and tested against a known truth,
never against matching a TOPAS keyword. Where an input does not import directly, a user
with a decent agent ports it from the documentation.

The aim the milestone tests: such a user ports their own refinement to rietx with the
manual, the skill and their agent. A missing primitive blocks them, and a missing check
does not. So the milestone ranks what an expert cannot express above any new correctness
test.

The practice behind the design is `docs/practice.md` § A parameter set by an equation
the user writes, surveyed across fields on 2026-11-03.

| WP | What it adds |
|---|---|
| [2101](../wp/2101-the-parametric-surface-as-it-stands-in-the-manual.md) | the surface that exists today, documented for someone arriving from TOPAS or GSAS-II |
| [2102](../wp/2102-a-joint-fit-takes-a-planspec.md) | `refine_multi(plan=PlanSpec(...))` stops crashing |
| [1964](../wp/1964-a-parametric-equation-the-user-writes.md) | the grammar, equations as text, shared variables, one equation feeding another, exact derivatives |
| [2103](../wp/2103-a-joint-fit-has-the-verbs-a-single-fit-has.md) | hold, tie, set values, a restart from a result, a profile interval, on a joint fit |
| [1995](../wp/1995-soft-restraints-in-a-joint-fit.md) | restraints in a joint fit, and a penalty written in the grammar |
| [2104](../wp/2104-a-parametric-cell-in-a-le-bail-or-pawley-joint-fit.md) | a shared cell across Le Bail or Pawley patterns |
| [2107](../wp/2107-an-equation-over-a-reflection.md) | a width, position or intensity set by an equation over a reflection |
| [2108](../wp/2108-a-pawley-phase-beside-a-rietveld-phase.md) | a structure-free phase beside a structural one |
| [2106](../wp/2106-an-equation-fitted-to-a-series-trajectory.md) | GSAS-II's practice: an equation fitted to a sequential trajectory |
| [1965](../wp/1965-a-parametric-equation-declared-by-condition-and-glob.md) | a subset by condition and a target by glob, cut on 2026-11-04 from a formula as well |
| [1325](../wp/1325-parametric-series.md) | what remains of it: bounds held inside the step, and starting structures that agree |

**Not in scope.**

- Presets for beginners.
- A kernel over the coordinates ([1963](../wp/1963-a-kernel-over-the-pattern-coordinates.md)).
- XRD-CT ([1962](../wp/1962-xrd-ct-a-pattern-summed-over-the-voxels-its-beam-crosses.md)).
- An equation over a data point (TOPAS's `fit_obj`). It adds to the pattern, so it is an
  expression member of `extra_components`, and no input read needs it.
- A TOPAS parametric reader ([2105](../wp/2105-a-topas-parametric-input-reads-in.md)),
  moved out under the ruling above. `read_project_model` stays as it is and says what it
  did not carry, and the agent ports the rest.
- Parity with TOPAS's keyword list.
- New built-in checks. 1325's next-term test and the replicate reading from #1218 are
  parked in that WP.

Effort is not estimated here. The only number on record is the survey's 600-1000 lines
for the parser, tree and rules, which is recall.

## The order

The documentation comes first because it needs no machinery and tells a user today
what they can already do. 2102 is small and removes a crash on the way in. 2103 needs
nothing else for its verbs, and it gives 1964 the tie that the WO₃ protocol needs. 1964
is the piece the rest stands on. 1995's penalty, 2104's equation on a cell, 2106 and 2107
all use its grammar. 2108 stands beside 2104. 1325's two tasks stand alone and can land at any point, and the
joint path they harden already exists. 1965 is sugar and comes last. Each WP's
`Priority:` line outranks this paragraph.

## Acceptance

**These rows are written at the open**, as protocol rule 6 asks. The session that opens
a WP sharpens its row here, because a bar set before reading a WP is a bar set too low.

- **The WO₃ input ports** (1964, 2103). The 100-pattern ramp (300 K to 90 K, three
  phases, `parametric_06.inp` in the local data root) runs under the input's own
  protocol: each cell edge an Einstein equation, each angle its equation, one B per
  pattern tied across every atom, and the W coordinates and strains shared as the input
  shares them. WP-1325's run held the coordinates and B and left strains per pattern, so
  this row is the first mirrored run. The exact gate: with θ held at 125.37 K, the
  equations written as text reproduce the `design` fit on the same protocol to 0.01 esd.
  With θ free, the run reports a profile of θ and whether it reaches a bound. On the
  chain's trajectories θ is barely determined: a one-θ proxy fit gave χ² 1370.8 at 30 K,
  1372.6 at 71.47 K and 1377.7 at 125.37 K. So a band around TOPAS's stored θ would pass
  anything. The gap to TOPAS is reported per parameter beside the spread between
  `parametric_05.inp` and `parametric_06.inp`, and it has no gate yet. Those two TOPAS
  answers differ by up to 393 ppm on an edge and 1149 ppm on an angle, and 1325's fit at
  the same θ differs from TOPAS by up to 825 ppm on an edge. The session that runs the
  mirrored protocol sets that gate here. Rwp is reported and is no part of the bar.
- **The ZrP₂O₇ input ports** (1964). The silicon cell's three Einstein terms and the two
  Al₂O₃ cell polynomials are written as text, and the cubic temperature calibration feeds
  all three. The exact gate: a preview with no fit reproduces the cells stored in the
  input at all 37 patterns to 1e-6 Å. The input's own coefficients do this to 6.6e-7 Å,
  the printed digits. The input fixes the calibration coefficients at 0, so a second run
  frees them. It converges and each coefficient carries an esd. TOPAS stores nothing for
  that run, so it has no reference. The 2θ curve in `Xo` (0.0105° at 15°, zero at 54°,
  0.0059° at 90°) joins the protocol once 2107 lands.
- **Every evaluator answers one conformance table** (1964). Each row of (expression,
  bindings, expected value or error) passes on numpy, jax and torch. A `polynomial` and
  the same form written as an expression agree to 0.01 esd.
- **A nonlinear coefficient's interval means what it says** (1964). On a synthetic
  order-parameter ramp with T_c inside the ramp and patterns on both sides, the interval
  1964's measurement chooses (esd or profile) covers the true T_c and β in at least 90 of
  100 seeds.
- **A joint fit has a single fit's verbs** (2103). Each verb the WP keeps works on a
  joint fit and is listed in `reference/joint.md`. Each verb it declines is refused by
  name with the reason.
- **A joint fit takes a restraint and a penalty** (1995). A bond restraint counts once
  per structure, and a hinge written in the grammar holds an equation's target near its
  bound on a synthetic ramp.
- **A shared cell works without a structure** (2104). A Pawley or Le Bail joint fit
  sharing a parametric cell over a synthetic ramp, on one pinned seed, recovers the known
  a(T) within 2 esd of the slope.
- **An equation over a reflection is correct and safe** (2107). On a synthetic phase,
  over 12 pinned seeds, every coefficient of a width, a position and an intensity equation
  has a mean z-score under 0.5 in size, in a single fit and a joint fit. An equation that
  is not single-valued over a Laue orbit is refused by name. Windows follow the equation,
  and every analytic column agrees with its oracle.
- **A structure-free phase sits beside a structural one** (2108). On a synthetic
  two-phase pattern with one phase's intensities scrambled, the other's structure and both
  cells are recovered within 2 esd on one pinned seed.
- **GSAS-II's practice has a home** (2106). An equation in the grammar fits a
  `SeriesResult` trajectory with its esds, the coefficients carry esds, and on a synthetic
  ramp the result agrees with the joint fit's coefficients within their combined esds. A
  stored GSAS-II sequential equation reads in, or is refused by name.
- **A joint fit takes a `PlanSpec`** (2102). A spec and the `RefinementPlan` it comes from
  give bit-identical answers on `refine_multi`.
- **An equation's target stays inside its bounds, and starts agree** (1325). The two
  tasks that WP keeps are ticked, each under its own test.
- **A condition and a glob resolve** (1965). A dropped pattern leaves an equation
  covering the same specimens, and a glob's skipped paths are reported.
- **An agent ports an input from the documentation** (2101, 1964, 2103, 2107). Every
  parametric construct in the Durham inputs has a line in `switching/topas.md` or a named
  non-goal, and `switching/gsas2.md` says where GSAS-II's practice lands. A fresh agent
  session given the manual, the skill and an input ports it, for WO₃ and for ZrP₂O₇. Its
  answers are judged against the hand-written protocols of the rows above. That run is
  costed and offered to the maintainer when the milestone is ready to close.
