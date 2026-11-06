# WP-2118 — one formula language for every constraint

Milestone: parametric · Status: 🔄 2026-11-06 — task 1 landed (PR #1444); waiting on the maintainer's rulings on design questions 1-3 (task 2)
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

- **2026-11-06** — Task 1 is done, and the WP now waits on the maintainer. The review is in
  `docs/practice.md` § The same language across a program. It found that most formula languages
  name bare identifiers and bind them to the model separately, and that only GSAS-II and JuMP
  keep linear constraints on their own route. It also found that GSAS-II's `sin` takes degrees
  while TOPAS, Stan and every other language read take radians. So a GSAS-II expression ported
  with a cell angle in it changes value without an error. The three design questions below are
  briefed for the maintainer, and tasks 3-8 wait on the rulings. Session by a ghostshift runner,
  PR #1444.
  - *Done.* 8774ad3e7: the practice section, thirteen programs on the seven questions of task 1,
    plus three sub-tables (angles, a minus sign before a power, the esd of a formula after a
    fit). The lead read TOPAS's Technical Reference v9, the GSAS-II 5.8.4 source, the FullProf
    8.20 manual and Stinton & Evans (2007). Two Sonnet agents read the cross-field
    documentation. Their raw notes were scratch files and are not kept. Task 1 ticked.
  - *WP-1964's two checks* (its Inherited note arrives with PR #1442; the next session deletes it
    once that merges, because both are answered here). (1) TOPAS reads a minus sign after the
    power. Its Table 3-1 is silent, and its §20.9.3 Voigt transform
    `Exp(-(Pi FT_K gfwhm)^2 / (4 Ln(2)) - …)` decays only under that reading. This is an
    inference from a documented example. TOPAS was not run, and its lexing of a literal `-2`
    is not stated. Stan, Lepton, Modelica, PEtab v2, muParser and Python agree on −4. (2) The
    esd of a curve with ΔT set to zero: TOPAS's answer is a formula the user writes after the
    fit. `: 0` prints its value, and with `do_errors` its error through the whole covariance
    (§2.9, §2.17). GSAS-II gives no curve esd. Stinton & Evans plot per-set values against the
    refined temperature and report no curve esd. So the route that matches practice is a
    general "evaluate this formula over the fitted variables, with its esd", and no argument
    naming a per-pattern variable is needed. It falls under the third Inherited note: build it
    when a case asks.
  - *Repair.* 4055b690d (00:10 UTC today) added the third Inherited note, from WP-1964's reader
    output, with no log entry. Reconstructed post hoc from the commit: it added that note and
    nothing else. The diff does not say why no entry was written. This entry covers it.
  - *Inherited.* The three notes stay. The first (degrees) is now backed by the angles table,
    and the second and third bear on tasks 3 and 5.
  - *Not run.* The handover's code review, since the branch is docs only. No tests were added, so
    no counts moved. No lanes were dispatched; the two survey agents were not lanes.
  - **Open question for the maintainer (task 2).** Three decisions. Each names something on the
    main API surface, which is why they come to you.

    **1. How a formula names a model parameter.** *Why it matters:* a formula is text such as
    `B0 * debye(thD / T)`. Each name in it must resolve to a number at every evaluation. rietx
    addresses a model parameter by a dot-path (`phases.0.atoms.3.biso`), and the grammar
    allows only bare names, so the path cannot be written inside the text. If this is chosen
    badly, users will either write long, fragile formulas or learn a second naming scheme.
    Moderate. *Aim:* one rule for both kinds of fit. A joint fit's formulas already read only
    named variables and coordinates. *Options.* (a) A formula reads only named variables
    (`vars.<name>`, made by `add_variable`) and constants. To read a model parameter, the user
    first ties it to a variable: `add_variable("zr", …)`, `tie("…atoms.0.occ", "vars.zr")`,
    then `1 - zr` on the other site. Nothing new is learned, and this is the joint fit's rule.
    It costs one extra call when a formula reads a model parameter. (b) The command takes a
    binding, `variables={"zr": "phases.0.atoms.0.occ"}`, as `add_expression` does on the
    table. It is flexible, and it adds a map to every call that reads the model. (c) Grammar
    version 2 accepts dotted paths in the text. That means a grammar change and long formulas,
    and globs still cannot appear. All three can be undone before release. Nothing was
    measured. *Practice:* most languages bind bare names separately (GSAS-II's `assgnVars`,
    Lepton's `addGlobalParameter`, RooFit's argument list). TOPAS names a parameter where it is
    declared, which is closest to (a). Mantid (`f1.Sigma`) and CEL accept dotted names, and
    PEtab v2 refuses them. *Recommendation:* (a), a lean. The crux is whether formulas often
    read model parameters directly. TOPAS's practice of naming parameters suggests the extra
    call is rare, and (a) adds no concept. Evidence that ported inputs mostly read model
    parameters would flip it to (b), which can then be added without breaking (a).

    **2. The command's spelling.** *Why it matters:* this is the verb users type. Today
    `tie(path, source)` takes a path string as `source`, so a formula string passed there is
    ambiguous. Minor. *Options.* (a) A keyword on the existing verb:
    `tie(path, expression="B0 * debye(thD / T)")`. `untie`, the `set_tie` history node and
    checkout's restore of ties serve both, so one record holds every user constraint. (b) A
    new verb beside `tie`, such as `set_expression`. It is clearer to read on its own, and it
    needs its own undo verb and record, or a shared one under two names. *Practice:* Mantid
    calls formula constraints "ties", lmfit puts `expr` on the parameter, and TOPAS writes the
    equation in place of the value. *Recommendation:* (a), a lean. The crux is rietx's
    one-authority rule for user constraints (`Refinement._ties`), which (a) keeps. The name of
    the keyword (`expression`, `formula` or `expr`) is yours. The grammar's page calls the text
    an "expression".

    **3. Whether a linear formula keeps today's linear route.** *Why it matters:* a tie today is
    a row of a constant matrix that maps the free values to the tied ones. Symmetry checks,
    the anchored-coordinate rebase and the "can this move" test all read that matrix. A formula
    is evaluated as a tree at each step, and each derived row declares what it reaches. If
    today's ties moved to the tree, every fit that uses one would change in the last digits,
    and every consumer of the matrix would need a second reading. Moderate. *Options.* (a) Two
    routes and no detection. `tie` and `tie_equal` stay on the matrix, and a text formula is
    always a tree, even when it is linear. Old projects open unchanged, and the tie goldens
    stay bit-identical by construction. (b) One stored form, text, with a detector that sends
    a linear formula to the matrix. It needs a stored-format change and a proof that detection
    reproduces the coefficients exactly. (c) One route, everything on the tree. Every tie golden
    is re-pinned, and the matrix's consumers learn the tree. Speed was not measured. A tree of
    a few nodes per step is small against a pattern evaluation. *Practice:* GSAS-II and
    FullProf keep linear constraints apart, and JuMP keeps affine forms as their own type. TOPAS,
    lmfit and Mantid run a linear tie as an ordinary formula. *Recommendation:* (a), a clear
    call. The crux is accuracy and risk. (a) changes no existing number and no stored file. (b)
    buys only one printed form, and a printer can render a matrix row as `x = 1 - y` without
    changing the route. A ruling that stored constraints must be one text form would flip it to
    (b). This also amends the Context paragraph's "a stored linear tie read as its formula",
    which a session wrote and no ruling backs.

    *Consent items* (I will do these unless you object). The grammar keeps radians with no
    `sind`. Only GSAS-II offers degree functions, and only there are they the default. The
    expressions page and the GSAS-II switching page will say that GSAS-II's `sin(x)` means
    sin(x°), in task 7.
  - *Next:* the maintainer rules on 1-3 and the consent items, and the rulings are recorded in
    Context. Then task 3, the command, once WP-1964 (PR #1442) has merged.
- **2026-11-05** — Filed at the maintainer's request, after the rulings above. No open WP
  owns a formula in a single refinement: 1070 and 1119 are closed, 1964 builds the grammar
  for joint fits, and 2103 gives a joint fit today's linear verbs. Task 1 is the practice
  review the maintainer asked for, and it can start now. Next: task 1.
