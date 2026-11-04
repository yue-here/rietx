# WP-1964 — a parametric equation the user writes

Milestone: parametric · Status: ⬜
Depends on: 1804 (the derived block); 1325 soft (the joint path, its equations and its form test have landed, and its open tasks are separate); 2103 soft (the tie the WO₃ protocol needs)
Priority: P2 2026-11-03 — the maintainer's direction: the machinery an experienced TOPAS or GSAS-II user needs comes first, and this is the piece they cannot work around

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

### Inherited

- **2026-10-15, from [1325](1325-parametric-series.md), from @mustachefeeling's
  comments on PR #977: linear inside, scanned outside.** Every basis they wanted
  is linear in its coefficients once one scalar is fixed: polynomial, √t, a step
  per gas stage, a changepoint at T*, and Debye B₀ + A·D(T/θ_D). A 1-D grid over
  θ_D or T* gives the nonlinear equation with no nonlinear solver. On 2026-11-03
  that scan ran through `design` rows at 0.4 s a fit on the seven-pattern LaB6
  ramp, and it gives no esd on the scanned value. It stays the documented
  workaround until this WP lands. Debye has no closed form, so `debye(x)` is a
  registered function with its own derivative. For O at θ_D = 500 K it gives a
  zero-point plateau of 0.36 Å², a high-T slope of 0.0029 Å²/K and a crossover
  near θ_D/2. Published practice (Denault et al. 2015, ACS AMI 7, 7264; Brgoch
  et al. 2014, APL 105, 181904) refines Uiso freely and fits θ_D afterwards.
- **2026-10-14, from [1325](1325-parametric-series.md) (seventh session,
  PR #977): three readers assume an equation linear in its coefficients.**
  - `RefinedParametricEquation.evaluate` computes Σ x_j·c_j and √(x·Σ·xᵀ) from
    the user-unit coefficients. An expression needs the block's local Jacobian
    at the coordinate in place of x.
  - `params.parametric.target_columns` reads a pattern's own target column as
    J_coef·Φ_kᵀ/‖Φ_k‖², which needs a constant Φ. The form test and its
    `others_freed` reading both rest on it.
  - `RefinedParameter.equations` is written from each table's `entry_reach`.
    Check that a row the block reaches is marked.

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

- [ ] **Write the grammar first.** The operators, the functions, precedence, the
  spellings under § The grammar's traps, and the version. It goes in the manual
  as a reference page. Beside it goes a conformance table of (expression,
  bindings, expected value or error), which every evaluator runs. Bring the
  names on the main surface to the maintainer as a consent list.
- [ ] **The parser and the tree.** Tokens with columns, limits on length and
  depth, an error that quotes the expression with a caret and suggests the
  nearest known name, and a printer with `parse(print(t)) == t`.
- [ ] **Evaluation and derivative rules.** One tree on every `xp`, the rewrites
  and conventions under § Derivatives, and `debye(x)`. Check by random trees
  against complex-step, plus adversarial points (0, 1e-8, T = T_c).
- [ ] **The block.** One `DerivedBlock` subclass, its declared reach read off the
  tree, the follower paths written, and a cross-backend row. Build it on
  `ParameterTable` so a single fit is one caller away, and record what
  `Parameter.expr` becomes.
- [ ] **Variables on a joint fit.** `variables=` beside `coordinates=`, one
  column shared by every equation that names it. A coordinate may not shadow a
  variable. An unused variable is refused.
- [ ] **An equation feeding an equation.** A named intermediate over variables
  and coordinates, in declaration order, as ZrP₂O₇'s temperature calibration
  needs. A cycle is refused. The bar uses nonzero calibration coefficients: the input
  stores zero, where a broken feed gives the right cells.
- [ ] **The chained column** (moved from 1325 on 2026-11-04). The target's column
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
- [ ] **A preview without a fit.** Evaluate every equation at the starting values
  across the coordinates. Report the value range, any non-finite pattern, any
  target outside its own bounds, and the dependencies each equation resolved to
  (TOPAS's `out_dependences`).
- [ ] **Intervals and minima.** On two synthetic ramps with a known truth (an
  order parameter through T_c, an Avrami fraction against time), measure
  coverage at 2 esd over seeds, against a profile interval. Decide what a joint
  fit owes here and what a documented script covers. Plot obs/calc/diff to
  `tests/output/`.
- [ ] **The result.** Variable rows in `result.parametric`, an equation evaluated
  anywhere through the block's Jacobian, and the three inherited readers.
- [ ] **A variable per pattern.** Declare it, carry it as a column per pattern, and let
  an expression read it (§ A variable per pattern). The test is Stinton & Evans's first
  method on a synthetic ramp: a ΔT per pattern through two phases' cell equations.
- [ ] **A shared coefficient's interval.** `profile_interval`, or a documented script,
  whichever the measurement above chooses. Moved from 2103 to break a cycle between the
  two WPs.
- [ ] **Real data.** The WO₃ Einstein equations and the ZrP₂O₇ calibration, local
  only, each against the TOPAS input's own answer under its protocol. The bars are
  in [the milestone's Acceptance](../milestones/parametric.md#acceptance).
- [ ] **Manual.** The grammar reference, the equation with its *Source* line in
  the Theory tab, a guide on an Einstein cell with a shared θ, and a section in
  `switching/topas.md` and `switching/gsas2.md` translating their spelling line
  by line.
- [ ] **Skill.** The series reference's parametric row, or "none" and why.

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
