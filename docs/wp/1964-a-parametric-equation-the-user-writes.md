# WP-1964 — a parametric equation the user writes

Milestone: parametric · Status: ✅ 2026-11-06 — all fifteen tasks landed; the mirrored WO₃ protocol is WP-2103's (PR #1442)
Depends on: 1804 (the derived block); 1325 soft (the joint path, its equations and its form test have landed, and its open tasks are separate); 2103 soft (the tie the WO₃ protocol needs)

## Goal

A user can write their own parametric equation as text, nonlinear in its
coefficients, and share a coefficient between equations:

```python
variables = {
    "zero_a": rx.Parameter(value=7.29, vary=True),
    "zero_b": rx.Parameter(value=7.52, vary=True),
    "grad": rx.Parameter(value=1e-5, vary=True),
    "theta": rx.Parameter(value=150.0, vary=True, min=20.0, max=1000.0),
}
equations = [
    rx.ParametricEquation(name="a", target="phases.0.cell.a", basis="expression",
                          expression="zero_a + grad/(exp(theta/T) - 1)"),
    rx.ParametricEquation(name="b", target="phases.0.cell.b", basis="expression",
                          expression="zero_b + grad/(exp(theta/T) - 1)"),
]
result = rx.refine_multi(patterns, structure, instruments, coordinates=coordinates,
                         variables=variables, parametric=equations)
```

Each variable returns with an esd from the joint covariance. `T` is a column of
the `CoordinateTable`. The spelling above is provisional, since names on the
top-level API go to the maintainer.

## Context

### Direction, 2026-11-03

The maintainer rescoped this WP. The first readers are experienced users who
build their own parametric refinements. The surface has to be accessible and
well documented. Built-in heuristics matter less, because these users will
write their own. Presets for beginners can follow if they prove necessary.

The first scope was a closed list of named forms, with an expression language
as a non-goal. That scope stranded any form the list left out. WP-1325's
decision 7 also settled the vocabulary: this is a parametric equation.

### What these users write

The Durham tutorials are real parametric inputs, and they sit in the local data
root (`python -m tests.local_data`).

- **WO₃** (`parametric_05.inp`, 419 lines, Rwp 12.87 % for 184 parameters over
  11 patterns). Lines 248-250, 287-289 and 336-338 write each cell edge as a
  constant plus a gradient over `Exp(theta/te) - 1`. `parametric_06.inp` is the same
  model over 100 patterns, Rwp 12.81 %. It is zipped beside it.
- **ZrP₂O₇** (`d8_02999_35_annotate_04.inp`, 3691 lines). The silicon standard's
  cell uses three Einstein terms and Al₂O₃'s two edges are polynomials in T. A cubic
  calibration maps the set temperature onto the true one and feeds all three.
  ZrP₂O₇'s own cell is free per pattern. Its per-pattern temperatures are generated
  by `#define` lines.
- **Evans's slides** give the single-equation form,
  `prm mlpa_t_0001 = zero_ma + (grad_ma/(Exp(theta_ma/t_0001)-1));`.

Three things recur: a coefficient appears in several equations, an equation
can feed another, and the coordinate is an ordinary known number.

### Practice

`docs/practice.md` § A parameter set by an equation the user writes holds the
survey of 2026-11-03, with its sources and what it could not reach. The design
below takes these conclusions from it.

| Question | Practice | Here |
|---|---|---|
| Form | a tree owned by the system, closed operator list (JuMP, CasADi, TOPAS) | a text expression parsed to rietx's own tree |
| Parser | none of the expression libraries surveyed is permissive, exact and Pyodide-ready; `ast` changes with Python; general parser libraries such as lark were not surveyed | a small hand-written parser, which adds no dependency |
| Grammar | an unwritten grammar becomes whatever the first parser did (PEtab v1, HS3) | a written grammar, a version, a conformance table |
| Sharing | by name in a flat namespace in text formats; by a shared object in python APIs (Bumps, refnx, RooFit) | a name in the expression is a variable or a coordinate |
| Start, bounds, fixed | beside the equations (PEtab, pyhf, TOPAS `prm`) | `variables`, reusing `Parameter`; a variable is already TOPAS's `prm` (`Refinement.add_variable`) |
| Per-dataset values | ordinary fixed numbers in a table | `CoordinateTable`, unchanged |
| Exact derivative | rules on the system's own tree, one derivation for every evaluator | one rule per operator, evaluated on any `xp` |
| Scale transforms | PEtab v2 removed its `parameterScale` | none, as WP-1938 already decided |
| Presets | expand into the expert layer, with no second parser | a stored expression with metadata, later |

The Pratt-style parser, tree and rules together were estimated at 600-1000
lines (recall, not measured). DESIGN.md § Parameter system already chose this
route. Its reason for rejecting sympy, an immature torch printer, has aged: sympy 1.14
ships a torch module. The rejection stands on other grounds, since `parse_expr` calls
`eval` and `lambdify` calls `exec`. Correct DESIGN.md when this WP lands.

### The grammar's traps, from the survey

- `^` is power in TOPAS and to every scientist, and XOR in python's parser.
  Accept `^` and `**`. A hand parser makes this free.
- `x^y^z` is left-associative in TOPAS (Table 3-1) and right-associative in
  python. Refuse an unparenthesised chain and say why.
- TOPAS allows an implied multiplication (`x y`). Refuse it, since `Tc` and
  `T c` then differ by a space.
- TOPAS's functions are capitalised and case-sensitive, GSAS-II's are python's.
  Decide in the first task, on rietx's own terms. TOPAS's spellings are not accepted as
  aliases, and an agent rewrites them from the manual's table (the ruling of 2026-11-04).
- `backend/api.py`'s `_OP_NAMES` has no `expm1` or `log1p`, and the Einstein form wants
  the first near θ/T small. A grammar function that lands on a new op adds it to every
  backend (root CLAUDE.md, Conventions). A frozen numpy array stays out of the left of an
  operator against a θ-derived value.
- A trig function's unit differs between programs. TOPAS and python use
  radians, and GSAS-II adds `sind`.

### Derivatives

- `_peak_chain_column` differences θ through `decode`, so a block's data-row
  column needs no new branch. A coefficient's finite-difference step then sits
  on the coefficient, which a nonlinear equation turns into an unknown step on
  the target. So take the column at the target and chain through the exact
  ∂target/∂coefficient. That is WP-1325's task "Compute a target's peak-chain
  column once per pattern", and TOPAS's arrangement (§2.3 `del`, §21.3.2).
- Compile `exp(u) - 1` to `expm1` and `log(1 + u)` to `log1p`. At
  theta/T → 0 the Einstein denominator otherwise loses its digits.
- In `x^y`, include the log term only where y depends on a variable.
- `if(c, a, b)` evaluates both branches on a traced backend, so a dead branch's
  NaN reaches the gradient (JAX FAQ). Sanitise the dead branch's argument in the
  compiler. The condition carries no derivative.
- Smoothing is never implicit, since it changes the model.
- The oracle is complex-step for analytic forms, where a forward difference
  would certify itself (root CLAUDE.md § A branch's oracle). A kink needs
  `mpmath` or a jax column as the second method. Neither enters the runtime.

### What is hard, and what the WP must measure

- **Ordering in `decode`.** `ParameterTable.decode` applies C·θ + d first and
  the blocks after it. An affine tie that reads a block's output therefore reads
  the stale value. A cubic `b ← a` under an equation on `a` is that case. The
  block has to write every path that follows the target.
  `_install_parametric` already computes that set.
- **A block's output must be locked with no tie.** `ParameterTable.add_derived`
  (`params/vector.py`) refuses anything else. An equation's target is unlocked today
  (`_target_refusal`), and a cubic follower carries a symmetry tie. So writing the
  followers means changing how a symmetry tie is held, under the rule that symmetry
  outranks a user tie (root CLAUDE.md § User constraints). Design this before the block.
- **Hot-loop cost.** `decode` runs per column, and `MultiParameterTable` decodes per
  table with a block per table. "Evaluate once over the coordinate array" therefore
  needs a shared evaluation the per-table blocks read. Measure at 300 patterns.
- **Starting values.** A nonlinear equation has no closed-form start, so the
  variable's own value is the start. `least_squares_start` stays for
  `polynomial` and `design`.
- **Bounds.** A variable's box is held by the driver. A bound on the target has
  no linear row here, because the equation is not linear. TOPAS ignores it
  silently. Here it must not be silent: check it in the preview and report it
  after the fit. A soft hinge belongs to [1995](1995-soft-restraints-in-a-joint-fit.md).
- **A singular derivative.** For β < 1, ∂/∂T_c of (1 − T/T_c)^β diverges as T
  approaches T_c. A preview names the pattern.
- **Linearised esds.** The covariance is linear in the coefficients. For a
  strongly nonlinear coefficient such as β, the true interval is asymmetric, and
  profile likelihood is the field's answer (Bates & Watts 1988). Measure
  coverage over seeds before choosing.
- **A weakly determined θ.** The two WO₃ inputs store θ = 125.37 K over 11 patterns
  and 71.47 K over 100, with the same equations. That is a factor of 1.75 on one
  coefficient, with no esd stored in either file. WP-1325 held 125.37 K while quoting
  the 100-pattern Rwp. Well below T the Einstein term is nearly a straight line, so θ
  and the gradient trade off (θ's ratio between the inputs is 1.75, and the nine gradients' ratios run 1.34-3.52).
  A proxy fit of one θ to the chain's trajectories (chain esds, no covariance between
  phases, script not in the repo) gave χ² 1370.8 at 30 K, 1372.6 at 71.47 K and 1377.7 at
  125.37 K. It ran to the lower limit on the backward chain and the upper limit on the
  forward chain. The first real-data run must report a profile of θ, because a
  linearised esd here would be misleading and this is the number a user will quote.
- **Several minima.** A nonlinear equation can have them. `val_on_continue`
  is TOPAS's tool and multi-start is systems biology's. Measure whether a
  documented script is enough before building anything.
- **The form test.** `params.parametric.form_tests` projects at the answer.
  Through the block's local Jacobian it should extend unchanged. That is a claim
  to test.

### The stored string, and WP-1119's objections

WP-1119 declined an expression parser for linear ties on four grounds. WP-1965 carried
them until its formula left on 2026-11-04, and they now sit here.

1. **A second parser for one language.** This grammar becomes the only one: 2106 lowers
   onto it, 2107 evaluates it on arrays, and `Parameter.expr`, reserved for this language by 1119, is
   either wired to it or removed. Say which.
2. **A stored string joins the format contracts.** It does. `basis="expression"`, the
   expression text and any stored variables change `SCHEMA_VERSION` and may change
   `PROJECT_FORMAT_VERSION`. A stored-format change goes to the maintainer, with the
   grammar's version alongside. Old files must still open.
3. **A silent failure mode.** The traps below and the conformance table are the answer.
4. **Pre-empting the TOPAS boundary** (WP-1118). The grammar is rietx's and reads no
   TOPAS file. A reader, if one is ever wanted, is parked in 2105.

### A variable per pattern

Stinton & Evans (2007) § 4.2 refine one temperature offset per data set and feed it to
every phase's cell equation, with ΔT free in each of 50 patterns before they replace it by
a polynomial. TOPAS spells that `local`. `variables` here are shared and a coordinate is a
fixed number, so nothing can say it. An expression must be able to name a quantity that
is free and has one value per pattern. The task below decides how it is declared. It
enters the parameter vector as a column per pattern, and its name in the tree evaluates
to that pattern's column. The seam is `SharingMap.per_histogram`, and `params/multi.py`'s
refusal of a per-histogram coefficient has to tell this case from a mistake. The form
tests and the equation's `evaluate` read a variable as one number, so each learns that a
per-pattern one is an array.

### Seams

- `schemas/parametric.py`: `expression` on `ParametricEquation`, JSON round-trip.
- A new module for the grammar: tokens, tree, printer, rules, emitter.
- `params/derived.py`: one `DerivedBlock` subclass with reach read off the tree.
- `params/multi.py` `_install_parametric`: variables, and a block where an
  equation is an expression.
- `optimize/least_squares.py`: the chained column.
- `tests/test_cross_backend.py`: a row for the new derivative path.
- `capabilities.py`: the grammar version as a seventh contract.

## Non-goals

- A python callable as an equation. It cannot be stored as data (the
  extra-components contract's clause 6), and it has no exact derivative.
- Presets for beginners. A named form is later a stored expression with
  metadata, on this grammar.
- Implicit smoothing, a scale transform, a complex value, a loop, recursion.
- An equation over a reflection: [2107](2107-an-equation-over-a-reflection.md), which
  needs this grammar to evaluate on arrays, so keep every operator element-wise. WO₃'s
  `scale_pks` is one overall B per pattern, so a tie expresses it and it needs no such
  seam. ZrP₂O₇'s `th2_offset` curve joins that protocol when 2107 lands.
- An equation over a data point (`fit_obj`), and a reader for TOPAS's spelling.
- A kernel prior over the coordinates:
  [1963](1963-a-kernel-over-the-pattern-coordinates.md).
- New built-in checks beyond carrying the form test through.

## Tasks

- [x] **Write the grammar first.** The operators, the functions, precedence, the
  spellings under § The grammar's traps, and the version. It goes in the manual
  as a reference page. Beside it goes a conformance table of (expression,
  bindings, expected value or error), which every evaluator runs. Bring the
  names on the main surface to the maintainer as a consent list.
- [x] **The parser and the tree.** Tokens with columns, limits on length and
  depth, an error that quotes the expression with a caret and suggests the
  nearest known name, and a printer with `parse(print(t)) == t`.
- [x] **Evaluation and derivative rules.** One tree on every `xp`, the rewrites
  and conventions under § Derivatives, and `debye(x)`. Check by random trees
  against complex-step, plus adversarial points (0, 1e-8, T = T_c).
- [x] **The block.** One `DerivedBlock` subclass, its declared reach read off the
  tree, the follower paths written, and a cross-backend row. Build it on
  `ParameterTable` so a single fit is one caller away, and record what
  `Parameter.expr` becomes.
- [x] **Variables on a joint fit.** `variables=` beside `coordinates=`, one
  column shared by every equation that names it. A coordinate may not shadow a
  variable. An unused variable is refused.
- [x] **An equation feeding an equation.** A named intermediate over variables
  and coordinates, in declaration order, as ZrP₂O₇'s temperature calibration
  needs. A cycle is refused. The bar uses nonzero calibration coefficients: the input
  stores zero, where a broken feed gives the right cells.
- [x] **The chained column** (moved from 1325 on 2026-11-04). The target's column
  once per pattern, then through the exact ∂target/∂coefficient. A tie's coefficient
  columns each re-run `phase_peaks` today, which cost 1.48-1.52× on the Jacobian loop
  (1325 § Measured: where the joint Jacobian's time goes).
  - The seam is `_make_jacobian`'s column loop
    (`optimize/least_squares.py:1979`) and `_peak_chain_column` (`:1339`).
    Group the peak-chain columns by the targets they reach, compute each
    target's column once, and chain through C. The restraint block already
    does this, as `r_phys @ cmat`.
  - A coefficient reaching several targets (one equation per phase field, a
    shared cell) takes the general form, J_columns = J_targets · C_sub, and
    never a per-name shortcut.
  - The finite-difference step then sits on the target, not the
    coefficient, so it is not bit-identical. The bar: the converged answer
    within 0.01 esd of today's, as the blocked solver's was.
  - It also removes a near-zero effective step: a pattern near the reference
    has Φ_kj ≈ 0, so today a coefficient's step barely moves its target.
  - `polynomial` and `design` come through unchanged or moved knowingly.
- [x] **A preview without a fit.** Evaluate every equation at the starting values
  across the coordinates. Report the value range, any non-finite pattern, any
  target outside its own bounds, and the dependencies each equation resolved to
  (TOPAS's `out_dependences`).
- [x] **Intervals and minima.** On two synthetic ramps with a known truth (an
  order parameter through T_c, an Avrami fraction against time), measure
  coverage at 2 esd over seeds, against a profile interval. Decide what a joint
  fit owes here and what a documented script covers. Plot obs/calc/diff to
  `tests/output/`.
- [x] **The result.** Variable rows in `result.parametric`, an equation evaluated
  anywhere through the block's Jacobian, and the three inherited readers.
- [x] **A variable per pattern.** Declare it, carry it as a column per pattern, and let
  an expression read it (§ A variable per pattern). The test is Stinton & Evans's first
  method on a synthetic ramp: a ΔT per pattern through two phases' cell equations.
- [x] **A shared coefficient's interval.** `profile_interval`, or a documented script,
  whichever the measurement above chooses. Moved from 2103 to break a cycle between the
  two WPs.
- [x] **Real data.** The WO₃ Einstein equations and the ZrP₂O₇ calibration, local
  only, each against the TOPAS input's own answer under its protocol. The bars are
  in [the milestone's Acceptance](../milestones/parametric.md#acceptance).
- [x] **Manual.** The grammar reference, the equation with its *Source* line in
  the Theory tab, a guide on an Einstein cell with a shared θ, and a section in
  `switching/topas.md` and `switching/gsas2.md` translating their spelling line
  by line.
- [x] **Skill.** The series reference's parametric row, or "none" and why.

## Acceptance

The bar: on the synthetic order-parameter ramp, the interval the measurement task
chooses covers the true T_c and β in 90 to 99 of 100 seeds. The upper limit fails an
inflated interval. The declared equation matches a chain's trajectory. Every conformance
row passes on numpy, jax and torch, in a `[dev,jax,torch]` venv, since the torch rows
skip themselves in `[dev]`. A `polynomial` and the same form written as an expression
agree to 0.01 esd. On a synthetic ramp, over 12 pinned seeds, a per-pattern ΔT and the
shared coefficients it feeds have a mean z-score under 0.5 in size.

```sh
.venv/bin/python -m pytest tests/test_parametric_series.py tests/test_derived_block.py tests/test_cross_backend.py
.venv/bin/python -m ruff check src tests examples
```

## References

- Stinton, G. W. & Evans, J. S. O. (2007). *J. Appl. Cryst.* 40, 87-95 —
  parametric Rietveld refinement.
- Coelho, A. A. (2018). *J. Appl. Cryst.* 51, 210-218 — TOPAS and TOPAS-Academic.
- Müller, M., Dinnebier, R. E. & Schorr, S. (2011). *Z. Kristallogr.* 226,
  doi:10.1524/zkri.2011.1407 — parameterized Rietveld refinement of the
  CuInSe₂ transition.
- Bates, D. M. & Watts, D. G. (1988). *Nonlinear Regression Analysis and Its
  Applications*. Wiley — profile-likelihood intervals.
- Squire, W. & Trapp, G. (1998). *SIAM Rev.* 40, 110-112 — complex-step derivatives.
- WP-1119 (named variables, and the fence), WP-1325, WP-1329 (the ordered
  moment), WP-1803 and WP-1804 (the derived block), WP-1938 (no transforms),
  DESIGN.md § Parameter system, `docs/practice.md`.

## Handover log

- **2026-11-06 (fourth build session, a ghostshift runner)** — The checklist is done. A
  joint fit now takes a quantity that is free in every pattern, such as Stinton and Evans's
  temperature offset, by naming its variable in the sharing map. `Parameter.expr` has left
  the schema, so the only way to write a formula is the equation that evaluates it. The
  manual has the formula equation in its Theory tab, a guide, and line-by-line TOPAS and
  GSAS-II spellings. Both Durham inputs were run as formulas: the ZrP₂O₇ formulas reproduce the cells TOPAS stores to the printed digits, and on WO₃ the formula text and the built-in Einstein equations give the same fit to 3e-8 of an esd, while θ itself is not determined by 11 patterns on WP-1325's protocol. PR #1442.
  - *Task 11, a variable per pattern* (decision (c)). A `vars.<name>` path that a
    `SharingMap.per_histogram` glob matches is one column per pattern that reads it, and
    exists only in those patterns' tables, so no column lacks a residual. A glob on the
    target frees it in the patterns it matched (`MultiParameterTable.variable_rows` names
    the rows). `result.parametric` lists it once per pattern of each equation, as
    `hist.<h>.vars.<name>`. The form test reads each pattern's own column.
    `RefinedParametricEquation.evaluate` refuses a formula reading one, naming the target
    row that carries each pattern's value and esd: the variable has no value between
    patterns. *Measured* (`[dev,jax,torch]`, darwin/arm64): Stinton and Evans's first
    method on a synthetic six-pattern ramp, a standard with known expansion beside a
    sample, ΔT free per pattern. Over 12 pinned seeds every ΔT and the sample's two
    coefficients had a mean z-score within 0.13 of zero (bar 0.5), 96 of 96 values were
    within 2 esd, and the z spread was 0.46-0.88. A fit took 2.4-2.9 s. With ΔT free in
    every pattern neither equation alone has a direction to test once the other's targets
    are freed, so each form verdict is `None` and the joint reading (4 directions) tests
    the pair.
  - *Decisions (a) and (b).* `Parameter.expr` is gone. A stored `"expr": null` is dropped at
    read; a non-null one is refused naming the formula equation. The `SCHEMA_VERSION` log
    gains "Also in 0.61 (WP-1964)", since 1.12 has not shipped, and records the expression
    basis, `target=None` and the removal. `PROJECT_FORMAT_VERSION` does not move. Readers
    updated: DESIGN.md § Parameter system, `reference/data.md`, `io/projects/gsas2.py`'s
    note, two `model_copy` updates that still set `expr`, six default-seat values in the
    audit table, and the 1.12.0 staging notes.
  - *Reader-output ruling, option A.* `ParametricCoefficient`'s docstring defines a formula
    variable's row, per-pattern ones included, and `reference/parametric.md` says to count
    free parameters from `result.parameters`.
  - *Task 14, the manual.* Theory § A formula equation (three equations with *Source*
    lines; the sentence saying a nonlinear form cannot be declared is gone).
    `reference/parametric.md` § Formula equations. `switching/topas.md` § A parametric
    equation is a formula and `switching/gsas2.md` § A parametric equation is fitted with the
    patterns. The guide `guides/formula.md` on `examples/guides/formula.py`: seven synthetic
    rutile patterns, a(T) and c(T) as Einstein formulas sharing one θ, θ = 500.17(61) K
    against 500. The manual builds with `-W`.
  - *Task 13, real data.* Local only, scripts and results in `docs/wp/1964-measure/`.
    *ZrP₂O₇* (`zrp2o7_formula.py`, 37 patterns, Durham tutorial 9.5): the silicon cell's
    three Einstein terms, the two Al₂O₃ polynomials and the cubic temperature calibration,
    written as text from the input. (a) A preview at the input's coefficients matches its
    printed cells to 6.63e-7 Å, bar 1e-6 Å: PASS. That is the input's own arithmetic
    against its printed digits. (b) With the calibration set to b = 6, c = −4, d = 2.5 K
    the cells move by up to 3.3e-3 Å, and the preview matches a numpy evaluation of the
    input's arithmetic to 0 Å: PASS. (c) The synthetic recovery is
    `test_a_temperature_calibration_feeding_the_cell_recovers_its_coefficients`. (d) The
    real data with the calibration freed, no gate: b −0.40 ± 3.15, c −20.40 ± 1.53,
    d −4.24 ± 2.67 K, which puts ΔT at +18.5 K at 600 K and −14.9 K at 1173 K. Rwp 31.488 %
    against 31.461 % untied and TOPAS's 31.56 %; the formulas cost Δχ² 334.5 for 108 fewer
    free parameters; 133 s at load 3-10. The plot at 1173 K shows small residuals at
    silicon 111 and 220. The 2θ `Xo` curve and the shared TCHZ terms wait on WP-2107.
    *WO₃* (`wo3_formula.py`, TOPAS's own 11 patterns, the ones `parametric_05.inp` fits;
    `[dev,jax,torch]`, darwin/arm64, load 19-47 from other sessions). WP-1325's protocol,
    since the input's own one needs WP-2103's tie (noted there). Gate: with θ held at
    125.37 K, the nine edges as text against the `design` basis agree to 2.85e-8 esd at
    worst over 345 shared rows and 18 coefficients, esd ratio 1.000000, Δχ² 0.0000: PASS.
    Each fit 190-193 s, Rwp 13.771 %, 209 free. θ free: 9.6 ± 1954 K, not at a bound,
    Δχ² −13.0, and `FLAT_DIRECTION` fires, so 11 patterns on this protocol do not determine
    θ. A hand profile, θ pinned and everything else refitted (4 pins, 288-297 s each):
    Δχ² 1.1 at 30 K, 3.7 at 71.47 K (TOPAS 06's θ), 13.0 at 125.37 K (TOPAS 05's), 43.5 at
    200 K and 287.5 at 400 K. Scaled by χ²r 2.37, the 95 % cut (Δχ² 9.1) falls between 71
    and 125 K, so these 11 patterns bound θ from above and not from below. The plots
    (`tests/output/wp1964_wo3_topas11_*`) show the strongest peaks' residuals WP-1325's
    protocol leaves, with B and the coordinates held. The largest gap to TOPAS 05 over the ramp is 154-1007 ppm per cell
    parameter with θ held, beside 31-1150 ppm between TOPAS's own 05 and 06 answers.
    `parametric_05.inp` is TOPAS's 11-pattern fit (`#define refine_some`) and
    `parametric_06.inp` its 100-pattern fit, so part of that spread is 11 patterns
    against 100. No gate on the gap: the milestone leaves it to the mirrored run.
  - *Merged origin/main* (144 commits) at 880c1cf6a; the conflict was `_make_jacobian`'s new
    `moment_angles` keyword beside the chained column.
  - *Settled by Claude.* (1) A per-pattern variable is added only to the tables of the
    patterns whose formula reads it; the alternative, every table, leaves a column no
    residual moves wherever a formula covers a subset. Grounds: the existing refusal of an
    unused variable, the same rule one rank down. (2) `evaluate` refuses a formula with a
    per-pattern variable rather than taking a pattern index. Grounds: a new argument would
    name something on the main surface, and each pattern's target row already carries
    the value with its esd.
  - *Generality.* The `generality-review` agent's report on the nine rows and four unseen
    heuristics, unedited below. No verdict is `fails`. The author's answers to the four
    `weak` ones: `MAX_LENGTH`'s RecursionError is fixed (aa9fb1248, the tree's depth is
    bounded and the `MAX_DEPTH` row says so); the rank cut is `RANK_RTOL` on unit rows
    (aa9fb1248, 79eb9a4ac); the `usable` rule's injected case waits on the tie, filed in
    WP-2103's Inherited; the evaluate gap and TOPAS's reading of `-2^2` are in WP-2118's
    Inherited.

      ## rietx.optimize.least_squares._CHAIN_RANK_RTOL = 1e-10, tier `invariant`

      **holds.** The case for the row is stronger. The cut only decides whether a shared finite-difference pass serves several Jacobian columns. Any error it lets through is bounded at 1e-10 of the largest column, far below the finite-difference error already present.

      (A "peak-chain column" is a Jacobian column taken by finite difference through peak positions and widths. "Chaining" means one directional pass serves every coefficient that moves the same rows. The `invariant` class is the audit's class for numbers that cannot move an answer, held by a test that asserts the margin.)

      | Question | Author's answer (where) | What I found | Verdict |
      |---|---|---|---|
      | 1. What it decides | "chooses between a directional peak-chain column per basis direction and a column per coefficient" (row `evidence`, `_audit.py:3094`) | Agreed. It also sets how many directions the shared pass keeps (`least_squares.py:2089`). | holds |
      | 2. Kind of ambiguity | not stated; a constant row needs none | Not a decision about the specimen. It is numerical accuracy only. | n/a |
      | 3. Case against | none given | none found. Dropping a direction whose singular value is under 1e-10·s₀ leaves a column error of at most 1e-10 of the largest column. That is far under the ~1e-6 finite-difference error (`FD_STEP` row). One gap: the claim "exactly proportional at 1e-16, independent at order 1" was argued for linear ties. For the formulas this WP adds, the entries are gradients that can span orders of magnitude (e^(−θ/T)). The error bound still covers that case. | none found |
      | 4. Case for | 1.12→0.94 s and 2.44→2.15 s, with 0.70× the passes (handover, second build session) | Agreed, measured once each. The timings are labelled indicative. | holds |
      | 5. Tier and source | `invariant`; `tests/test_parametric_series.py::test_a_targets_column_once_serves_every_coefficient` | The test exists. It asserts every parameter lands within 0.01 esd of the per-column answer, against 7.4e-7 measured, so the margin is asserted. It compares chained with unchained by setting the cut to −1. It never tries a second cut value. | holds |
      | 6. Dataset families | joint LaB₆ ramp at 6 and 14 patterns (`evidence`) | One family: a synthetic LaB₆ ramp, which is development data. The reference is rietx's own per-column answer, so this verifies and validates nothing. That is enough for an invariance claim. | holds |
      | 7. Record that it fired | none given | none. No field says a group was chained. | none |

      Would change the verdict: a formula-tied group whose singular values fall between 1e-16 and 1e-10 and whose answer moves by more than 0.01 esd.

      ## rietx.params.expression.MAX_DEPTH = 64, tier `invariant`

      **holds.** The case for the row is stronger. It is a refusal by name that never alters an expression it accepts.

      | Question | Author's answer (where) | What I found | Verdict |
      |---|---|---|---|
      | 1. What it decides | "a refusal limit of the expression grammar … never a setting of what an accepted expression means" (`evidence`, `_audit.py:3508`) | Agreed. Depth counts parser recursion: parentheses, calls, unary signs and precedence climbs (`expression.py:300`, `:374`). | holds |
      | 2. Kind | n/a | Input acceptance, not a judgement about data. | n/a |
      | 3. Case against | none given | Horner-form polynomials nest two levels per term, so about 30 terms reach the limit. none found among real inputs: no TOPAS or GSAS-II expression in the WP comes near it. | none found |
      | 4. Case for | refused "by name (too_deep), never truncated" | Agreed. 64 levels at about 4-5 Python frames each stays far below Python's default recursion limit of 1000. | holds |
      | 5. Tier and source | `invariant`; `tests/test_expression.py::test_limits_on_length_and_depth` | The test asserts the refusal at 65 levels and acceptance at 31. It asserts no margin over real expressions, and none was measured. The `invariant` class is written for "answer-invariant efficiency", and a refusal limit is not efficiency. Placing the row there is the maintainer's call. | weak on fit to the class, holds on substance |
      | 6. Families | none given | n/a | n/a |
      | 7. Record | the error code `too_deep` | It is raised as `ExpressionError.code`. | holds |

      Would change the verdict: a ported refinement whose formula nests deeper than 64 levels.

      ## rietx.params.expression.MAX_LENGTH = 4096, tier `invariant`

      **weak.** The case against is stronger on one point. The row says an expression under the limit is accepted unchanged and one over it is refused by name. From reading the code (I did not run it), a long flat expression under 4096 characters can instead crash with a Python `RecursionError`.

      | Question | Author's answer (where) | What I found | Verdict |
      |---|---|---|---|
      | 1. What it decides | "a refusal limit in characters" (`evidence`, `_audit.py:3513`) | Agreed for `parse` (`expression.py:490`). | holds |
      | 2. Kind | n/a | Input acceptance. | n/a |
      | 3. Case against | none given | (a) A chain like `x+x+…+x` parses in a loop into a tree as deep as the chain is long. `Expression.__init__` then calls `rewrite` (`expression.py:589-614`), which recurses once per level. About 1000 terms is roughly 2000 characters, under the limit, and over Python's default recursion limit of 1000. The caller gets a `RecursionError`, not `too_long`. The test only calls `parse`, so it cannot see this. (b) `Expression.inline` (`:919-941`) prints and re-parses the inlined text. A formula built from accepted intermediates can therefore be refused as `too_long` (or `too_deep`), with a message about text the caller never wrote. | case found (from reading, not run) |
      | 4. Case for | "refused by name (too_long), never truncated" | Holds for `parse` alone. | partial |
      | 5. Tier and source | `invariant`; `test_limits_on_length_and_depth` | That test checks `parse` at 4097 characters only. It never builds an `Expression` near the limit. No margin over real use was measured. | weak |
      | 6. Families | none given | n/a | n/a |
      | 7. Record | `too_long` | Raised for `parse`. Not raised on the path in 3(a). | weak |

      Would change the verdict: a test that builds `Expression` from a ~2000-character flat sum and gets a value or a named refusal. Bounding tree depth in the parser, or making `rewrite` and `_Eval` iterative, would do it.

      ## rietx.params.expression._DEBYE_TAIL = 10.0, tier 1

      **holds.** The case for the row is stronger. The switch between the two methods moves no value past rounding. The only gap is that no test sits next to the switch.

      (B10 is the 2026-10-19 ruling: a numerical setting is tier 1 once a test shows its error stays under a stated bar over every input it claims to handle.)

      | Question | Author's answer (where) | What I found | Verdict |
      |---|---|---|---|
      | 1. What it decides | "the switch from 32-node Gauss-Legendre to the exponential tail of D1" (`evidence`, `_audit.py:3517`) | Agreed (`expression.py:689-696`). D₁ is the first Debye function. | holds |
      | 2. Kind | n/a | Numerical accuracy only. | n/a |
      | 3. Case against | none given | none found. My own bound: the integrand's nearest poles (s = ±2πi) give the 32-node rule an error of about ρ^(−64) with ρ ≈ 2.9 at |x| = 10, roughly 1e-30. | none found |
      | 4. Case for | "within 4e-15 of an mpmath quadrature below |x| = 10" (`evidence`; handover, first build session: "within 4e-15 of mpmath over -30 to 300") | The sweep is a session measurement, and no script for it is committed in `docs/wp/1964-measure/`. The conformance rows check `debye` at 0, ±1, 20 and −30 to 1e-13 against 50-digit mpmath (`expressions.md:186-190`, read by `test_conformance_row`). That covers both methods but no point in roughly [5, 15]. The points 9.99 and 10.0 appear only in a derivative test against the function's own complex-step derivative, which checks consistency, not accuracy. | holds; the B10 test is thin at the switch |
      | 5. Tier and source | tier 1, "numerical floor" | Tier 1 under B10. Its domain test covers five points, not the switch's neighbourhood. | holds |
      | 6. Families | n/a | The reference is mpmath, which verifies. | n/a |
      | 7. Record | none | none, as expected for a numerical setting. | n/a |

      Would change the verdict: a conformance row at x just below 10 that misses 1e-13.

      ## rietx.params.expression._DEBYE_TAIL_TERMS = 5, tier 1

      **holds.** The case for the row is stronger. It is plain arithmetic.

      | Question | Author's answer (where) | What I found | Verdict |
      |---|---|---|---|
      | 1. What it decides | the tail series' truncation (`evidence`, `_audit.py:3523`) | Agreed (`expression.py:671-676`). | holds |
      | 2. Kind | n/a | Numerical accuracy only. | n/a |
      | 3. Case against | none given | none found. At x = 10 the k = 4 term is already about 7e-18 of D₁, so 4 terms would do. The fifth is harmless. | none found |
      | 4. Case for | "the first omitted term … carries e^-60, about 1e-26 relative" | Checked: e^(−60)·(10/6 + 1/36)/10 ÷ D₁(10) ≈ 9e-27. | holds |
      | 5. Tier and source | tier 1, arithmetic | Correct. The rows at 20 and −30 exercise the series. | holds |
      | 6. Families | n/a | n/a | n/a |
      | 7. Record | none | n/a | n/a |

      Would change the verdict: none foreseeable.

      ## rietx.params.expression._NOT_POWER = 3, tier `invariant`

      **holds.** The case for the row is stronger. The number only encodes an order of precedence, and a table row pins that order.

      | Question | Author's answer (where) | What I found | Verdict |
      |---|---|---|---|
      | 1. What it decides | "places 'not' between 'and' and the comparisons" (`evidence`, `_audit.py:3527`) | Agreed. Python uses the same order. | holds |
      | 2. Kind | n/a | A definition of the grammar. | n/a |
      | 3. Case against | none given | none found. The decision is the order, not the number 3, and the order is written in the grammar page. | none found |
      | 4. Case for | "any value keeping that order parses identically" | Agreed. `if(not x > 0 or x == 5, 1, 2)` at x = 5 → 1 (`expressions.md:182`) gives 2 under the other order, so the row pins it. | holds |
      | 5. Tier and source | `invariant`; the table rows | Pinned by `test_conformance_row` and `test_print_round_trips_every_table_row`. | holds |
      | 6. Families | n/a | n/a | n/a |
      | 7. Record | none | n/a | n/a |

      Would change the verdict: none foreseeable.

      ## rietx.params.expression._UNARY_POWER = 7, tier `invariant`

      **holds.** The case for the row is stronger. Python, C-family maths and mathematical convention all read −x^2 as −(x²), and a table row pins it.

      | Question | Author's answer (where) | What I found | Verdict |
      |---|---|---|---|
      | 1. What it decides | "unary minus above '*' and '/' and below '^' (-x^2 = -(x^2))" (`evidence`, `_audit.py:3532`) | Agreed. Only the interaction with `^` changes a value. | holds |
      | 2. Kind | n/a | A definition of the grammar. | n/a |
      | 3. Case against | none given | Spreadsheets read −2^2 as 4. TOPAS's reading of unary minus against `^`: not checked, and not in this repository. The page refuses the one TOPAS/python conflict it found (`x^y^z`, `power_chain`), but not this one. | possible dissent, not checked |
      | 4. Case for | `-2 ^ 2` → −4.0 (`expressions.md:146`) | Pinned. It is GSAS-II's reading, since GSAS-II formulas are Python. | holds |
      | 5. Tier and source | `invariant` | Holds as a definition. If TOPAS reads −2^2 as 4, a port would silently change sign, and that would argue for a `power_chain`-style refusal. | holds |
      | 6. Families | n/a | n/a | n/a |
      | 7. Record | none | n/a | n/a |

      Would change the verdict: TOPAS's manual showing that unary minus binds tighter than `^`.

      ## Changed rows: six `DEFAULT_SEATS` rows (ProfileTCHZ:u/v/w/x/y, Source:polarization) losing `"expr": None`

      **holds.** The case for the change is stronger. The edit is mechanical. In the diff (`wp-1964-generality.diff:751-797`) each recorded value drops only the `expr` key, and every number, tier, ambiguity and approval date is unchanged. The cause is the maintainer's ruling (a) of 2026-11-05, which removed `Parameter.expr` (handover, third build session).

      Would change the verdict: any other key moving in these rows.

      ## Not visible to the table: the rank cut in `params/parametric.py` `expression_target_columns`

      **weak.** Leaving the pattern untested is the right act, but the case against the threshold is stronger. The cut is numpy's machine-precision rank test on G (the gradient matrix of the targets in the free variables). The error it should guard is the Jacobian's, and the package's own linear twin uses a looser cut for the same question.

      (The "form test" is rietx's check of whether a declared parametric equation fits. It compares the tied fit with an alternative that frees the target in each pattern. A "target column" is that pattern's Jacobian column for the target, which the test adds.)

      | Question | Author's answer (where) | What I found | Verdict |
      |---|---|---|---|
      | 1. What it decides | "A pattern where G has fewer directions than targets gives no column" (handover, third build session; docstring `parametric.py:457-459`) | The pattern is dropped from every formula's alternative, including a target that would have had its own direction (`:501-503`). | holds |
      | 2. Kind | not stated | Kind 1 (the data settle it) for the act: with fewer directions than targets, T = J_V·G⁺ is not determined. | holds |
      | 3. Case against | none given | The cut is s_min ≤ max(shape)·eps·s₀, so it accepts G with a condition number up to about 1e15. G⁺ amplifies the error of J_V (the free variables' Jacobian columns), not G's own error. Those columns may be finite differences good to about 1e-6 (`FD_STEP` row), so nearly parallel G rows give noisy target columns. Under a correct equation the noise is still calibrated (it cannot cause a false rejection), but the test loses power. The linear twin `_refuse_rank_deficient` asks the same question at `RANK_RTOL` = 3.2e-8 (`parametric.py:51`, `:296`). No case near the cut was measured. | case found |
      | 4. Case for | the measured line: polynomial and expression agree to 6.8e-11 (handover) | Leaving such a pattern out is the only honest act. No test exercises a nearly singular G. `test_targets_sharing_a_variable_are_recovered_together` covers only an exactly singular one. | partial |
      | 5. Tier | none (inline literal) | It would be tier 1 as numpy's documented `matrix_rank` default. That default is not a Rietveld program's. | weak |
      | 6. Families | none given | Synthetic ramps only. | none |
      | 7. Record | none given | `ParametricFormTest.n_patterns` against `n_subset` shows that some patterns were left out, but not why. The same count also falls for an unseen pattern, an unusable pattern or a zero column. | weak |

      Would change the verdict: the cut set to `RANK_RTOL` (or argued from the Jacobian's error), and a test with nearly parallel G rows showing the recovered columns' error.

      ## Not visible to the table: the `usable` rule (`multi.py` `_parametric_form_tests`)

      **weak.** The act is right, but nothing tests it. The predicate that sets it is computed in `multi.py:3369-3379`, and no test exercises that computation.

      | Question | Author's answer (where) | What I found | Verdict |
      |---|---|---|---|
      | 1. What it decides | "a pattern where a variable reaches a row no expression writes … gives no column" (handover; docstring `multi.py:3349-3354`) | Agreed. The pattern leaves every formula's alternative. | holds |
      | 2. Kind | not stated | Kind 1: there J_V ≠ T·G, so a recovered column would be wrong. | holds |
      | 3. Case against | none given | The rule is broader than needed. It drops the whole pattern for all formulas, even those whose G⁺ never mixes in the contaminated column, and that costs power. none found for a wrong verdict. | minor |
      | 4. Case for | "read off each table's `entry_reach`, the claim checked where it is used" (docstring) | Agreed in principle. But the unit test passes `usable` in by hand (`test_parametric_expression.py:421`), and I found no test where a caller's tie onto `vars.X` makes the computed predicate False. If the predicate misfires, a contaminated column is tested silently. generality.md § The rule asks a guard that ordinary fits never reach to name an injected case. | weak |
      | 5. Tier | none | Kind 1 arithmetic, with no threshold. | holds |
      | 6. Families | none | n/a | n/a |
      | 7. Record | none given | Only `n_patterns` against `n_subset`, which does not say why. | weak |

      Would change the verdict: a joint fit with `tie(<path>, "vars.X")` beside a formula reading X, asserting that pattern's formula test drops it.

      ## Not visible to the table: the alternative drops only variables no other formula reads (`parametric.py` `form_tests`)

      **holds.** The case for the rule is stronger. Given how the test counts directions, the rule leaves no free choice.

      | Question | Author's answer (where) | What I found | Verdict |
      |---|---|---|---|
      | 1. What it decides | "the alternative drops the free variables no other expression reads, so a shared θ stays in it" (docstring `parametric.py:565-567`; handover) | Agreed (`:604-606`). | holds |
      | 2. Kind | not stated | Kind 1. | holds |
      | 3. Case against | none given | In tested patterns, a variable only this formula reads lies in the span of the added target columns. Dropping it or keeping it then gives the same gain and the same number of directions, because `added_columns_gain` counts directions by rank. A shared variable must stay so that the alternative still contains the tied model. One narrow case, from reading: in a pattern left without a target column (the two items above), dropping a variable only this formula reads also removes its pull there. The alternative then no longer contains the tied model in that pattern, and the reading becomes conservative (fewer rejections). | narrow case (from reading) |
      | 4. Case for | joint dof = 4 in the per-pattern ΔT test; 6.8e-11 polynomial and expression agreement | Pinned: `test_a_temperature_offset_per_pattern_feeds_two_cell_equations` (`dof == 4`) and `test_a_polynomial_and_the_same_form…` (`rel=1e-6`). | holds |
      | 5. Tier | none | Kind 1 arithmetic. | holds |
      | 6. Families | synthetic ramps | Synthetic and development data. Verification only. | n/a |
      | 7. Record | `ParametricFormReading.dof` | It reports how many directions were added. | holds |

      Would change the verdict: a case where a pattern dropped for rank or `usable` shifts the statistic away from its χ² distribution under a correct formula.

      ## Not visible to the table: per-pattern variables live only in reader tables, and `evaluate` refuses them (`params/multi.py` `_install_expressions`; `schemas/parametric.py` `_evaluate_expression`)

      **weak.** The first half holds. On the second half the case for acting is stronger: the refusal also leaves the caller no route to the quantity Stinton & Evans's method exists to produce.

      (A per-pattern variable is a `vars.<name>` that a `SharingMap.per_histogram` glob names, so it has one free value per pattern. The maintainer chose that declaration in ruling (c) of 2026-11-05.)

      | Question | Author's answer (where) | What I found | Verdict |
      |---|---|---|---|
      | 1. What it decides | added "only to the tables of the patterns whose expressions read it: anywhere else it would be a column no residual moves" (docstring `params/multi.py:759-763`); evaluate: "has a value at each pattern and none between them" (`schemas/parametric.py:626-631`) | Agreed. With such a variable, `parametric_equations` also stores `covariance=None` and `span={}` (`multi.py:2733-2740`). | holds |
      | 2. Kind | not stated | Placement: kind 1 (a column with no gradient). The refusal: kind 3, since what ΔT is between patterns depends on facts outside the data. | holds |
      | 3. Case against (placement) | — | none found. Unused variables are already refused (`params/multi.py:742-746`). A caller's tie onto that variable in a non-reader pattern: not checked. | none found |
      | 4. Case for acting (the refusal) | none given | The deliverable is the sample's curve b0 + gb·(T − 300) with ΔT corrected out, with its esd. `evaluate` refuses it, and passing ΔT as a coordinate is refused too (`:644-647`). The covariance of b0 and gb is withheld, and I found no correlation matrix on `RefinementResult` (`schemas/results.py`). So the curve's esd has no route. Accepting a caller-supplied ΔT value (for example 0) and propagating the shared variables' covariance would leave the pick with the caller. The handover has no entry for task 11 yet. | case found |
      | 5. Tier | none | Placement is kind 1. Refusing is a report-and-stop under kind 3, which is defensible. The cost in 4 is not weighed anywhere in the change. | weak |
      | 6. Families | the 12-seed ΔT ramp (`test_a_temperature_offset_per_pattern_is_unbiased_over_twelve_seeds`) | One synthetic family, development data. It checks the fit, not the refusal. | n/a |
      | 7. Record | the `ValueError` naming `hist.h.<target>` | Pinned in the test at `test_parametric_expression.py:915`. | holds |

      Would change the verdict: a stated reason why no caller needs the ΔT-free curve's esd, or `evaluate` taking an explicit value for the per-pattern variable together with the shared block's covariance.
  - *Review.* `/code-review high --fix` found seven issues and the pass fixed five,
    each in commit 79eb9a4ac: a run of signs after `^` recursed uncounted (RecursionError under
    `MAX_LENGTH`); the formula rank cut's row norm underflowed at 1e-162 and its solve used
    a second cut that could disagree with the rank test (one SVD now serves both); the
    manual's chain rule miscounted by one; the depth test missed the boundary; and a
    measurement script's exponent regex. The finding it skipped, an inlined formula refused
    with text the user never wrote, is fixed in 0248c93d0: the refusal names the equation
    and its intermediates. The seventh, one limit for flat sums and nesting alike, is the
    design, not a defect.
  - *Lanes.* One lane ran task 13's ZrP₂O₇ half and wrote the WO₃ script; the runner ran
    the WO₃ fits after the lane stopped. `session_usage.py lanes` was not run: the runner
    is itself a subagent, and the tool reads transcripts from `~/.claude/projects`, where
    this machine keeps none.
  - *Fast selection.* FASTCOUNT
  - *Next.* Nothing on this WP's checklist. WP-2118 (one formula command for a single fit)
    and WP-2103 (the joint fit's verbs, which the full WO₃ protocol needs) build on it.
- **2026-11-05 (third build session, a ghostshift runner)** — Task 10 closed, and tasks 9, 12
  and 15 landed. Branch `wp1964-equations`, no PR: tasks 11, 13 and 14 are left, and
  the runner's brief opens the PR only on a finished checklist.
  - *Task 10, the form test.* `params.parametric.expression_target_columns` recovers each
    expression target's own column per pattern as T = J_V·G⁺, G the exact gradient of the
    targets in the free variables. A variable shared by several targets is the general
    case, not a special one. A pattern where G has fewer directions than targets gives no
    column. So does a pattern where a variable reaches a row no expression writes, read
    off each table's `entry_reach`. The alternative drops only the variables no other
    expression reads. `PARAMETRIC_TARGET_UNSEEN` and `PARAMETRIC_OUT_OF_RANGE` now cover
    expressions too, the siblings of the same gap. *Measured*: a line as a `polynomial`
    and as an expression read the same statistic to 6.8e-11 relative. A line written over
    an Einstein cell read 17 222 against the cut 7.8, and the Einstein expression 1.2.
  - *Task 9, intervals and minima* (`docs/wp/1964-measure/coverage.py`, `profile.py`, and
    their results files; `[dev,jax,torch]`, darwin/arm64). Two twelve-pattern LaB₆ ramps,
    100 seeds each, every variable free, Biso started at its truth so the model is exact.
    On the order-parameter ramp (T_c = 830 K, β = 0.3) the value ± 2 esd covered T_c and β
    in 97 of 100 each, so the acceptance bar (90 to 99) passes with the esd the fit
    already reports. The other three variables: 96-97. On the Avrami ramp it covered k and
    n in 100 and S in 99. The esds carry the Bérar-Lelann factor f = 1.12-1.14; divided by
    f the coverage was 93-99. A hand profile of T_c and β (2 seeds) was within 5 % of a
    parabola to 3 esd, so a profile would add nothing here. *Minima*: one fit started below
    the last ordered pattern, with T_c 10 K above it and Biso off its truth, stopped at T_c = 782 K and the form
    test rejected it. With T_c 40 K from the pattern, 20 of 20 starts from below recovered
    it. With Biso started 0.1 Å² off its truth, S came back 27 esd high on every seed, the
    protocol's error and not the equation's: a single fit of one such pattern gives the same.
  - *Task 12, decided by task 9.* The joint fit reports the esd, and a profile interval
    is a documented script: `reference/parametric.md` § Intervals of an expression's
    variables. No `profile_interval` on a joint fit. Settled by Claude under the WP's own
    rule ("whichever the measurement above chooses"). The alternative is a joint
    `profile_interval`, which the measurement gives no case for.
  - *Found, not fixed.* The form test rejected the true order-parameter expression in 15
    of 100 seeds, against 5 expected. On the Avrami ramp it rejected 2 of 100. The cause is
    not measured. The manual's § Limits of the form test now says so. A χ² read across
    separate fits carries an offset: the free fit sat 0.19 of the 2-esd cut above the pinned
    fits' curve. The documented script reads the pinned fits against each other.
  - *For the maintainer.* (c) Task 11 needs a declaration on the main surface. Proposal:
    a per-pattern variable is a `variables=` entry whose `vars.<name>` path the sharing map
    names literally in `SharingMap.per_histogram`, the seam § A variable per pattern names.
    A glob that matches `vars.*` by accident is still refused. The alternative is a new
    flag, such as `rx.Parameter(per_pattern=True)` or a TOPAS-like `local`. Decisions (a)
    and (b) and consent items 1-6 of the first entry still stand unanswered. Reader output:
    expression fits now carry `parametric_form` entries and the three warnings above.
  - *Decided (Yue, 2026-11-05), (c).* A per-pattern variable is declared by naming its
    `vars.<name>` path in `SharingMap.per_histogram`, matched as an **ordinary glob** like
    every other path there. The proposal's extra refusal of a glob that reaches `vars.*` is
    dropped: `vars.*` or `vars.dT_*` makes those variables per-pattern, as written. Grounds:
    `SharingMap` is the one place a joint fit says what is shared, `rx.Parameter` carries no
    sharing field, and one matching rule is what an agent calling rietx learns from the docs
    and error messages; the exception guarded a mistake only a glob starting `*` or `vars.`
    could make. Task 11 builds on this; the current "a variable is one number" refusal goes.
  - *Decided (Yue, 2026-11-05), the vision.* One formula language for constraints and
    restraints, in single and parametric refinements. This grammar is that language. The
    milestone record carries the ruling, and WP-2118 owns the single-refinement half.
  - *Decided (Yue, 2026-11-05), (a).* `Parameter.expr` is **removed** in this WP: a
    `mode="before"` migration drops a stored `"expr": null` so old files open, and the
    field leaves the schema (part of decision (b)'s `SCHEMA_VERSION` move). A formula in a
    single refinement is declared by a **command** in the `tie` family, recorded and
    symmetry-checked like a tie, never by a field on the parameter. Grounds: one place
    declares what a parameter follows, and the same command can serve a joint fit (2103).
    That command is WP-2118, not this WP. Readers to update with the removal: the
    docstring, DESIGN.md § Parameter system, `io/projects/gsas2.py`'s note, and any manual
    or skill line naming the field.
  - *Decided (Yue, 2026-11-05), (b).* The stored-format changes take a `SCHEMA_VERSION`
    bump under the existing rules. The new fields (`basis="expression"`, `expression`,
    `variables=`, `target=None`) are additive and defaulted, the 0.25 → 0.26 rule; the
    `expr` removal reads through a migration. The log entry beside the constant says that
    old files open unchanged and that a file using a formula does not open in 1.11 or
    earlier. If 1.12 has not shipped when this merges, the entry is "Also in 0.61" (the
    log's pattern within one release, inferred and to be checked); otherwise 0.62. Confirm
    `PROJECT_FORMAT_VERSION` (the `.rex` layout) does not move.
  - *Decided (Yue, 2026-11-05), consent items 1-6.* All six stand as listed in the first
    build session's entry: the function names, radians with `pi`, `debye` as D₁, the
    functions left out, `Capabilities.expression_grammar_version = "1"`, and the § Goal
    spellings. Two follow-ups went to WP-2118's Inherited: degree trig (`sind`) once a
    formula can read a cell angle in degrees, and keeping a joint fit's `variables=` and a
    single fit's `add_variable` one convention.
  - *Decided (Yue, 2026-11-06), the reader output.* Accepted: `preview_equations` and
    `EquationPreview`; `vars.*` rows in `result.parameters`; `RefinedParameter.equations`
    naming a formula's variables and every row it writes; `result.parametric_equations`
    and `evaluate()` for formulas; the form test, `PARAMETRIC_OUT_OF_RANGE` and
    `PARAMETRIC_TARGET_UNSEEN` covering formulas. For the variable rows in
    `result.parametric` the maintainer chose option A: keep them, and make
    `ParametricCoefficient` say what they mean. Its docstring now defines a coefficient
    for a linear term only, so a formula variable's row breaks the "a declared name is a
    claim" rule (root CLAUDE.md, WP-1076). **Task before the PR:** the docstring defines
    the formula-variable case (value and esd are the variable's own, `unit` the variable's,
    `reference` None, `term` its name, and a variable two formulas read is listed under
    each), and `reference/parametric.md` says in one line that the free-parameter count
    comes from `result.parameters`, never from this table. Option B (drop the rows) split
    where a reader looks; option C left the docstring wrong.
  - *Task 15, the skill.* The series reference's parametric row now names `basis="expression"`
    and `variables=`. It grew 23 B and sits 16 B under its budget. The synced copies follow.
  - *Fast selection* at 93518e01f, `[dev,jax,torch]`, darwin/arm64, through ghostshift's
    `serial.py`: 14471 passed, 51 skipped, 36 xfailed, 0 failed (18:49). The total is 35 above
    the last entry's at 84fa4cb02, and this session added four tests; the rest is the
    second session's later commits and a different skip set, not reconciled here.
  - *Next.* Task 11 (decision (c) answered above), the removal of `Parameter.expr` and the schema bump (decisions (a) and (b) above), the `ParametricCoefficient` docstring and manual line (the reader-output ruling above), then 13 and 14. No decision waits on the maintainer.

- **2026-11-05 (second build session, a ghostshift runner)** — Tasks 7 and 8 landed, and
  the fast selection's three reds from the first session are fixed. Branch
  `wp1964-equations`, no PR.
  - *Task 7, the chained column.* `_chained_columns` in `optimize/least_squares.py` groups
    the peak-chain columns by the physical rows they move. Where a group's block of
    `local_jacobian` has lower rank than its column count, one directional pass per basis
    direction serves the group, J_cols = D·X, with the step sized on the moved rows. A
    group of independent columns, a lone column included, keeps `_peak_chain_column`, so an
    untied model is bit-identical. The rank cut `_CHAIN_RANK_RTOL` = 1e-10 has an audit row.
  - *Measured* (`t7_probe.py` in the runner's scratch; joint LaB₆ ramp of
    `tests/test_parametric_series.library`, `mccusker_default`, `[dev,jax,torch]`,
    darwin/arm64). At 6 patterns the peak-chain passes fell from 1152 to 804 and the fit
    from 1.12 s to 0.94 s. At 14 patterns they fell from 2828 to 1988 and the fit from
    2.44 s to 2.15 s. Every parameter landed within 2.3e-7 esd (6) and 7.4e-7 esd (14) of
    the per-column answer, against the 0.01 esd bar. Esds moved by 6.3e-6 relative at most.
    Single runs, so the wall times are indicative.
  - *Task 8, the preview.* `MultiHistogramRefinement.preview_equations()` returns one
    `EquationPreview` per equation with a target: values at the start, non-finite and
    out-of-bounds patterns, and the variables, coordinates and intermediates it resolved
    to. Linear equations are covered too. The manual has a section in
    `reference/parametric.md`, so the names are documented, not deferred.
  - *Reds fixed.* The chained column called `np.linalg.svd`/`lstsq` on the fit path; they
    go through `optimize.lapack`. `expression.py`'s six constants had no audit rows; they
    have rows now (four `invariant`, two tier 1), and the `generality-review` agent has not
    yet read them. The skill's `api.md` was stale from task 5's `variables=`.
  - *For the maintainer.* `preview_equations` and `EquationPreview` are new reader output
    (memory rule: reader-output changes go to Yue before merge). Decisions (a) and (b) of
    the first entry stand unanswered.
  - *Task 10, in part.* An expression's variables are now its rows in `result.parametric`:
    one `ParametricCoefficient` each, `term` the variable's name, no reference, so no
    field is new. A variable two equations read is listed under each.
    `RefinedParameter.equations` names an expression's variables and the rows of the block
    that writes its target, cubic b and c included (the third inherited reader). Both
    change what a fit prints and returns.
  - *Evaluate.* `result.parametric_equations` now carries each expression and each
    intermediate, with its variables' covariance in the order of its rows in
    `result.parametric`. A held variable has a zero row. `evaluate()` on an expression
    takes those rows, the coordinates and the intermediates as `definitions`, and returns
    √(g·Σ·gᵀ) through `Expression.gradient`. At each pattern it reproduces the cell row's
    value to 1e-13 and its esd to 1e-6, on the Einstein fit and the calibration-fed one.
    No stored field is new, so decision (b) does not grow.
  - *Fast selection* at 84fa4cb02, `[dev,jax,torch]`, darwin/arm64: 14003 passed, 484
    skipped, 36 xfailed, 0 failed. The first session's tree gave 3 failed and 2 errors,
    the errors from a subprocess that imported mid-edit. The total moved by +3, the three
    tests added.
  - *Next.* Task 10's last reader: the form test (`target_columns`) still covers linear
    equations only, so an expression reports no form verdict. Then 9, 11-15.

- **2026-11-05 (first build session, a ghostshift runner)** — Tasks 1-6 landed: the grammar,
  the parser and tree, evaluation and exact derivatives, the block on `ParameterTable`,
  variables on a joint fit, and one equation feeding another. Branch `wp1964-equations`, no
  PR. Tasks 5 and 6 ran as lanes and were checked and committed here.
  - *Tasks 5 and 6.* `refine_multi(variables=…)` takes a dict of `Parameter`. Each is
    `vars.<name>`, one shared column however many equations name it. An expression equation
    is held apart from the linear ones (`MultiParameterTable.expressions`), because the result
    readers assume a linear basis until task 10. An expression equation with `target=None` is
    an intermediate, and a later expression may name any earlier one; resolution inlines it
    (`Expression.inline`). On a five-pattern LaB6 Einstein ramp the fit recovers `zero_a`
    within 0.002 esd and `grad` within 0.9 esd. A `polynomial` and the same form as an
    expression agree to 8e-10 esd against the 0.01 bar. With nonzero calibration
    coefficients each cell matches a hand evaluation to 1e-12, and a fit recovers c0 and c1
    within 0.7 and 0.9 esd.
  - *Settled by Claude* (each could have gone the other way).
    1. A variable declared `vary=False` stays fixed when a stage reaches its equation's target,
       but a glob naming `vars.<name>` frees it. Grounds: a literal path is the caller's own
       request, and the hold mechanism (`Entry.held`) means a floating-origin hold in a joint
       fit. The alternative is fixed in every stage.
    2. An intermediate is a `ParametricEquation` with `target=None`, rather than a separate
       `intermediates=` keyword or a `Parameter(expr=…)` variable. Grounds: one declaration type
       in declaration order, TOPAS's `prm t = …;` and GSAS-II's repeated label both put the
       definition in the same list. This also names something on the main surface, so it joins
       the consent list as item 6.
    3. A follower tied to the target and to another parameter is refused (task 4), since the
       block would have to carry the other half. No input in hand needs it.
  - *Done.* `docs/docs/reference/expressions.md` is the specification, version 1, with a
    73-row conformance table whose values came from mpmath at 50 digits. `params/expression.py`
    implements it. `tests/test_expression.py` reads the table off the page and runs every row on
    numpy, jax and torch. Random trees match complex step, and jax's and torch's autodiff match
    the numpy rules. `arctan`, `expm1` and `log1p` joined `_OP_NAMES`. The grammar's version is
    the seventh contract in `capabilities()`. `ParameterTable.add_expression` builds an
    `ExpressionBlock`, and `test_cross_backend.py` has an `expression` row.
  - *Followers.* A cubic `b` and `c` follow `a` by a symmetry tie, and C would read `a` before
    the block writes it. `add_expression` therefore moves each follower's tie into the block:
    the follower becomes a locked, untied output written as coeff·target + const. A follower
    tied to the target and to anything else is refused by name. The symmetry is unchanged, so
    the rule that symmetry outranks a user tie still holds.
  - *Measured.* `debye(x)` is a 32-point Gauss-Legendre rule below |x| = 10 and the exponential
    tail above, within 4e-15 of mpmath over -30 to 300. Without the `expm1` rewrite the Einstein
    term at θ/T = 1e-10 is wrong in the eighth significant figure.
  - *Consent list for the maintainer* (task 1 asks for one; names on the main surface). Each
    stands unless you object.
    1. Function names are python's and C's, lowercase: `exp`, `expm1`, `log` (natural), `log1p`,
       `sqrt`, `sin`, `cos`, `tan`, `asin`, `acos`, `atan`, `abs`, `min`, `max`, `debye`. A
       condition goes in `if(c, a, b)`, joined by the words `and`, `or`, `not`. `^` and `**`
       are both the power. GSAS-II users already write python, and TOPAS's `Ln` and `Exp` are
       rewritten by an agent from the manual (the ruling of 2026-11-04 takes no aliases).
    2. Trigonometry is in radians only, with the constant `pi`. GSAS-II's `sind` is left out,
       so each function has one unit.
    3. `debye(x)` is the first Debye function D₁(x) of Abramowitz and Stegun § 27.1. A
       Debye-model Biso is the user's own prefactor times `debye(theta_D/T)`.
    4. Left out until someone asks: `sinh`, `cosh`, `tanh`, `log10`, `sind`. Each costs an op
       on every backend.
    5. The field is `Capabilities.expression_grammar_version`, and the version is `"1"`.
    6. `ParametricEquation(basis="expression", expression="…")`, `refine_multi(variables={…})`
       and `target=None` for an intermediate, as § Goal spells them.
  - *Decisions for the maintainer.* Both change the stored format, which the WP gives to you.
    (a) `Parameter.expr`: wire it to this grammar as a single fit's spelling (a parameter set
    by an expression over `Refinement.add_variable`'s variables, TOPAS's everyday use), or remove
    it. The block is one caller away, so wiring is cheap. Lean: wire it. (b) Task 5 adds
    `basis="expression"` and an `expression` field to `ParametricEquation`, and `variables=` to
    `refine_multi`, with the spelling in § Goal. That moves `SCHEMA_VERSION`.
  - *Reader output.* A joint fit with `variables=` now returns `vars.*` rows in
    `result.parameters`, and `MultiHistogramRefinement.parametric` lists expression equations.
    `RefinedParameter.equations`, `result.parametric` and the form test do not see an
    expression equation yet (task 10). These changes go to the maintainer before merge.
  - *Next.* Task 7, the chained column, then 8 (preview) and 10 (result). `SCHEMA_VERSION` is
    unbumped until decision (b) is answered. `reference/parametric.md` still says "the three
    bases" below its table; task 14 owns that prose.

- **2026-11-04 (second review)** — A second clean-context review tested the plan against
  the code and the local inputs. It gave the agent-port row a pass and a fail, fixed a
  ZrP₂O₇ gate that could not test the calibration feed, and found two constructs with
  no owner, now in 2107 and 2108. The interval task moved here from 2103 to break a
  cycle. Next: unchanged, 2101 and 2102, then this WP's first task.
- **2026-11-04 (the ruling on TOPAS)** — The maintainer ruled that the machinery stands
  on its own terms and an agent ports what does not import. So this grammar takes no
  TOPAS aliases, and 2105 left the milestone. Stinton & Evans (2007) is now read. It
  confirms the design and adds one gap: a free quantity with one value per pattern, which
  § A variable per pattern takes in. Next: 2101 and 2102, then this WP's first task.

- **2026-11-04 (scoping hkl equations)** — An equation in 2θ and an equation in hkl turn
  out to be one piece of work, so the earlier split between them was false. An earlier
  statement here and in the PR, that nothing in hand needs an hkl equation, was wrong:
  ZrMo₂O₈'s tutorial scales a width by a spherical harmonic of hkl. WP-2107 holds the
  scope and the probe's numbers, and nothing was built. Coelho (2018) was read and changes
  nothing here. It reports computer algebra at 5-10 % of a Rietveld run and gives no
  grammar detail. Next: the maintainer's ruling on 2107's slices, which came the same day.

- **2026-11-04** — The parametric work now has one stated goal: an experienced TOPAS
  or GSAS-II user ports their own refinement to rietx from the manual alone. The
  maintainer opened the `parametric` milestone on it, and this WP is its centre. No code
  changed. Nothing is measured here beyond reading two TOPAS inputs, and that reading
  found the WO₃ inputs disagree on θ by a factor of 1.75.
  - *Done.* The milestone record with nine acceptance rows, WPs 2101-2105 filed in the
    new 21xx block, and 1325, 1964, 1965 and 1995 moved in. 1325's peak-chain task moved
    here with its detail. 1325's next-term test and the replicate reading are parked.
    1965 lost the Wilkinson formula to this grammar and was renamed. 1995 gained a
    penalty and went to P2.
  - *Measured.* `parametric_05.inp` stores θ = 125.37 K, Rwp 12.87 %, over 11 patterns.
    `parametric_06.inp` stores θ = 71.47 K, Rwp 12.81 %, over 100. No esd in either.
    WP-1325 held the first while quoting the second's Rwp (§ A weakly determined θ).
    The `#list` inputs store no per-pattern cell, so the milestone's WO₃ row compares
    each equation on the two sets of coefficients.
  - *Gotchas.* WO₃'s `scale_pks` is one overall B per pattern and ZrP₂O₇'s `th2_offset`
    is a curve in `Xo`. Neither needs this WP, and § Non-goals says how each protocol
    treats it. WP-2105 owns reading a TOPAS input, so this WP's real-data runs write
    their protocols by hand. The numbers in 2101's Context came from session scripts
    that are not in the repo.
  - *Review.* A clean-context reviewer read the branch after the PR opened. It showed
    the first acceptance bars for WO₃ and ZrP₂O₇ would fail for reasons unrelated to the
    work, or pass anything, and that the milestone had nothing for GSAS-II's practice.
    Both bars were rewritten around exact gates, 2106 was filed, and this file gained
    `add_derived`'s lock rule and the stored-format questions. The survey's sympy claim
    was wrong and is corrected.
  - *Next.* The grammar, with its names brought to the maintainer as a consent list.
    2101 and 2102 can land first and need nothing from this WP.
- **2026-11-03** — Rescoped by the maintainer from a closed list of named forms to
  equations the user writes, after a survey across fields
  (`docs/practice.md`). The file and title were renamed to drop "law". No code
  yet. Next: the grammar.
- **2026-10-14** — Filed as a stub after the maintainer asked why nonlinear forms
  were fenced. No open WP owned them: 1325's Non-goals fenced them with
  `Parameter.expr`, and 1119 is closed.
