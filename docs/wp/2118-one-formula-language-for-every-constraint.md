# WP-2118 — one formula language for every constraint

Milestone: parametric · Status: 🔄 2026-11-06 — claimed by ghostshift runner (@yue-here); task 1, the practice review
Depends on: 1964 (the grammar, `ParameterTable.add_expression`, the removal of `Parameter.expr`); 2103 soft (the joint fit's `tie`)
Priority: P2 2026-11-05 — a feature the open milestone was opened for: the maintainer's ruling that one formula language serves single and parametric refinements; task 1 can start before 1964 lands

## Goal

A single refinement declares a parameter set by a formula in WP-1964's grammar, with a
command in the `tie` family, and a joint fit takes the same command. Today's linear ties
read as the simplest such formulas, and every fit that uses them gives the same numbers.

## Context

**The ruling.** The maintainer, 2026-11-05: one formula language for constraints and
restraints, in single and parametric refinements. WP-1964's grammar is that language
(`docs/docs/reference/expressions.md`, version 1). The same day the maintainer ruled that
`Parameter.expr` is removed in WP-1964, and that a single refinement declares a formula
with a **command** beside `tie`, recorded and symmetry-checked like a tie. Grounds: one
place declares what a parameter follows, and one command can serve both kinds of fit.

**What exists.**

- A single refinement links parameters only linearly: `Refinement.tie`, `tie_equal`,
  `untie` (WP-1070) over named variables from `add_variable` (WP-1119, path
  `vars.<name>`). `Refinement._ties` is the one authority for which ties are the user's;
  each verb auto-commits a `set_tie` node, `RefinementState.ties` restores them on
  checkout, and symmetry outranks a user tie in `_apply_ties`.
- A series re-declares a tie per pattern and never carries it (root CLAUDE.md § Data
  flow, WP-1441), because `tie_equal` resolves globs against each pattern's own table.
- WP-1964 put the formula machinery at the table level:
  `ParameterTable.add_expression(target, expression, variables=, constants=)` makes the
  target a derived row written by an `ExpressionBlock`, with exact derivatives on every
  backend. A joint fit declares a formula through
  `ParametricEquation(basis="expression", expression=...)`.
- WP-1995 plans soft restraints written in the grammar. WP-2107 plans formulas evaluated
  over reflections. Both use the same parser.
- `docs/practice.md` § A parameter set by an equation the user writes surveyed fourteen
  programs on 2026-11-03 for the form of a parametric equation. Task 1 extends it.

**Design questions this WP brings to the maintainer** (task 2):

1. How a formula names a model parameter. Grammar names are bare identifiers, so
   `phases.0.atoms.3.biso` cannot appear in the text. Either the command binds short
   names to paths, as `add_expression`'s `variables=` already does, or the grammar
   learns dotted paths (grammar version 2).
2. The command's spelling: `tie` taking a formula as its source, or a new verb beside it.
3. Whether a linear formula is recognised and kept on today's affine route, so old ties
   and their goldens stay bit-identical.

**Invariants that bind the build.** Symmetry outranks a user formula, enforced where
`_apply_ties` enforces it today. A tie onto an anchored coordinate DOF needs
`rebase_anchored_dofs` (root CLAUDE.md § Conventions, WP-1432). An analytic Jacobian
branch must declare what a formula's column reaches (root CLAUDE.md § Invariants). A
stored formula is text, so it moves `SCHEMA_VERSION`, and old projects must open, with a
stored linear tie read as its formula.

**Tier.** The command and the shorthand are named practice (TOPAS, lmfit and Mantid
declare formulas on parameters; practice.md). No new judgement is added.

### Inherited

- **2026-11-05, from WP-1964 (consent item 2).** The grammar's trigonometry is in
  radians only, with `pi`, and GSAS-II's `sind` was left out. rietx gives every angle in
  degrees, cell angles included. Once a formula here can read a cell angle, `cos(beta)`
  would treat 95° as 95 radians without a word. Task 1's review asks how other programs
  meet this, and the fix if a case needs it is additive (`sind`, `cosd`, `tand`).
- **2026-11-05, from WP-1964 (consent item 6).** A joint fit declares its variables at
  construction, `refine_multi(variables={…})`, while a single refinement uses the
  `add_variable` command. WP-2103 gives a joint fit the single fit's commands. The
  command built here should keep the two routes one convention, or say why they differ.
- **2026-11-06, from WP-1964 (the reader output).** A formula's general surfaces are
  `vars.*` rows in `result.parameters` and `RefinedParameter.equations`, and a
  single-refinement formula here reuses both unchanged. The joint fit's
  `preview_equations()` and `result.parametric_equations`/`evaluate()` are joint-fit
  calls today; extend them to a single refinement only when a case needs it.

## Non-goals

- The grammar itself, its functions and its version: WP-1964.
- Restraints written in the grammar: WP-1995.
- Formulas over a reflection: WP-2107.
- A Python-operator front end that builds the same formula. Possible later; no one has
  asked for it.
- Unit checking of formulas.

## Tasks

- [x] **Practice review: what a formula language does well across a program.** Extend
      `docs/practice.md` § A parameter set by an equation the user writes, which covered
      the form of one parametric equation, with the language-level questions: one grammar
      for constraints, restraints and equations (TOPAS, OpenMM's Lepton, Stan, JuMP);
      how a formula names a model parameter; where a declaration lives (on the parameter,
      in a separate list, as a command); how linear constraints keep a fast route; how a
      grammar is versioned and stored text migrated; how an error points at the user's
      text; whether units are checked. A row per program, cited, marked checked or recall,
      and the practice the rows add up to. Run it before task 2, and save it the same
      session (memory rule: every survey goes to practice.md).
- [ ] **Brief the maintainer** on design questions 1-3 above, with task 1's practice and
      measurements where a question turns on cost. Record each ruling here.
- [ ] **The single-refinement command.** Declares a formula for one parameter, auto-commits
      a node, is restored by checkout and replay, and is refused on a symmetry-fixed or
      symmetry-tied path by name.
- [ ] **Today's ties as formulas.** `tie`, `tie_equal` and `add_variable` keep working as
      shorthand. Old projects open, and every golden that uses a tie is bit-identical, or
      the WP says which moved and why.
- [ ] **A series and a joint fit.** The command re-declares per pattern in a series as a
      tie does, and a joint fit takes the same command (with 2103).
- [ ] Tests: unit and property tests, a `test_cross_backend.py` row for a single-fit
      formula, and obs/calc/diff PNGs to `tests/output/`.
- [ ] Manual: the constraints guide and the expressions reference show the command.
- [ ] Skill: the reference row for the command, keyed by its name.

## Acceptance

A single refinement with a nonlinear formula (a Debye-model Biso, `B0 * debye(thD/T)`
with T fixed) recovers its variables on a synthetic pattern within 2 esd. A refinement
using only today's ties gives bit-identical numbers before and after.

```sh
.venv/bin/python -m pytest tests/test_expression.py tests/test_cross_backend.py -q
.venv/bin/python -m pytest tests/test_docs_consistency.py tests/test_manual_api.py -q
.venv/bin/python -m ruff check src tests examples
```

## References

- Eastman et al. (2017), OpenMM 7, PLOS Comput. Biol. 13, e1005659: custom forces as
  formula strings, differentiated by its expression library.
- Coelho (2018), J. Appl. Cryst. 51, 210-218: TOPAS's equations and computer algebra.
- `docs/practice.md` § A parameter set by an equation the user writes.

## Handover log

- **2026-11-05** — Filed at the maintainer's request, after the rulings above. No open WP
  owns a formula in a single refinement: 1070 and 1119 are closed, 1964 builds the grammar
  for joint fits, and 2103 gives a joint fit today's linear verbs. Task 1 is the practice
  review the maintainer asked for, and it can start now. Next: task 1.
