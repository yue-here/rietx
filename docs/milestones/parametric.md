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

The aim the milestone tests: such a user ports their own refinement to rietx with the
manual alone. A missing primitive blocks them, and a missing check does not. So the
milestone ranks what an expert cannot express above any new correctness test.

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
| [2105](../wp/2105-a-topas-parametric-input-reads-in.md) | a TOPAS parametric input read into equations |
| [1965](../wp/1965-a-parametric-equation-declared-by-condition-and-glob.md) | a subset by condition and a target by glob, cut on 2026-11-04 from a formula as well |
| [1325](../wp/1325-parametric-series.md) | what remains of it: bounds held inside the step, and starting structures that agree |

**Not in scope.**

- Presets for beginners.
- A kernel over the coordinates ([1963](../wp/1963-a-kernel-over-the-pattern-coordinates.md)).
- XRD-CT ([1962](../wp/1962-xrd-ct-a-pattern-summed-over-the-voxels-its-beam-crosses.md)).
- An equation over a reflection or a data point (TOPAS's `scale_pks` over hkl,
  `lor_fwhm` over hkl, `fit_obj`, and `th2_offset` in `Xo`). That is a different
  compile-time seam, and a later ruling may open it.
- New built-in checks. 1325's next-term test and the replicate reading from #1218 are
  parked in that WP.

Effort is not estimated here. The only number on record is the survey's 600-1000 lines
for the parser, tree and rules, which is recall.

## The order

The documentation comes first because it needs no machinery and tells a user today
what they can already do. 2102 is small and removes a crash on the way in. 1964 is the
piece the rest stands on. 2103 needs nothing from it, and 1995's penalty and 2104's
cell use its grammar, so those three can land in any order. 2105 comes after 1964
because it lowers onto the grammar. 1965 is sugar and comes last. Each WP's `Priority:` line outranks this
paragraph.

## Acceptance

**These rows are written at the open**, as protocol rule 6 asks. The session that opens
a WP sharpens its row here, because a bar set before reading a WP is a bar set too low.

- **The WO₃ input ports** (1964). The 100-pattern ramp (300 K to 90 K, three phases,
  `parametric_06.inp` in the local data root) runs with each cell edge written as an
  Einstein equation and θ refined as one shared variable. At every pattern each
  equation, evaluated on rietx's coefficients, lies within 300 ppm (the FAP suite's bar)
  of the same equation on TOPAS's stored coefficients. The input stores no per-pattern
  cell, because `#list` generates those lines. θ lies within 2 of rietx's esds of the
  stored 71.47 K, and it carries an esd. The input's `scale_pks` line is one overall B
  per pattern, so the protocol holds one B per pattern at the chain's value, as 1325
  did. Rwp is reported and is no part of the bar: on this ramp the untied fits already
  differ (rietx 13.53 %, TOPAS 12.81 %).
- **The ZrP₂O₇ input ports** (1964). Its three Einstein terms on the silicon standard
  and its cubic temperature calibration are written as text, with the calibration
  feeding the terms. The input fixes the calibration coefficients at 0, so a second run
  frees them. The fit converges and every free coefficient carries an esd. TOPAS's 2θ
  calibration curve (0.006-0.011°) depends on `Xo`, so it stays out of the protocol, as
  it did in 1325. Each phase's per-pattern cell has a gap to TOPAS's stored value no
  wider than the gap of rietx's untied fit on the same protocol at its worst pattern.
- **Every evaluator answers one conformance table** (1964). Each row of (expression,
  bindings, expected value or error) passes on numpy, jax and torch. A `polynomial` and
  the same form written as an expression agree to 0.01 esd.
- **A nonlinear coefficient's esd means what it says** (1964). On a synthetic
  order-parameter ramp, T_c and β lie within 2 esd of the truth in at least 90 % of
  seeds.
- **A joint fit has a single fit's verbs** (2103). Each verb the WP keeps works on a
  joint fit and is listed in `reference/joint.md`. Each verb it declines is refused by
  name with the reason.
- **A joint fit takes a restraint and a penalty** (1995). A bond restraint counts once
  per structure, and a hinge written in the grammar holds an equation's target near its
  bound on a synthetic ramp.
- **A shared cell works without a structure** (2104). A Pawley or Le Bail joint fit
  sharing a parametric cell over a synthetic ramp recovers the known a(T) within 2 esd
  of the slope.
- **A TOPAS parametric input reads in, or says why not** (2105). The WO₃ input and a
  committed synthetic fixture read into equations and variables. Every construct the
  reader cannot carry raises or reports by name.
- **The manual stands alone** (2101, 1964). Every parametric construct in the two
  inputs has a line in `switching/topas.md` or a named non-goal, and `switching/gsas2.md`
  says where GSAS-II's practice lands. A fresh agent session given only the manual and
  the WO₃ input ports it. That run is costed and offered to the maintainer when the
  milestone is ready to close.
