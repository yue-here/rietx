# WP-2118 — one formula language for every constraint

Milestone: parametric · Status: ✅ 2026-11-07 — `tie(path, expression=...)` in a single refinement and a series; the joint fit's half is WP-2103's
Depends on: 1964 (the grammar, `ParameterTable.add_expression`, the removal of `Parameter.expr`); 2103 soft (the joint fit's `tie`)

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
stored formula is text, so it moves `SCHEMA_VERSION`, and old projects must open.
(Superseded in part, 2026-11-07: ruling 3 keeps a stored linear tie linear, so it is not
read as a formula. `TieSpec.expression` is additive in schema 0.61, which is unreleased, so
`SCHEMA_VERSION` stays at 0.61.)

**Tier.** The command and the shorthand are named practice (TOPAS, lmfit and Mantid
declare formulas on parameters; practice.md). No new judgement is added.

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
- [x] **Brief the maintainer** on design questions 1-3 above, with task 1's practice and
      measurements where a question turns on cost. Record each ruling here.
- [x] **The single-refinement command.** Declares a formula for one parameter, auto-commits
      a node, is restored by checkout and replay, and is refused on a symmetry-fixed or
      symmetry-tied path by name. `Refinement.tie(path, expression=...)`, stored as
      `TieSpec.expression`; `tests/test_tie_expression.py`.
- [x] **Today's ties as formulas.** `tie`, `tie_equal` and `add_variable` keep working as
      shorthand. Old projects open, and every golden that uses a tie is bit-identical, or
      the WP says which moved and why. Under ruling 3 the linear route is unchanged, so this
      is a check: the eleven test files that tie and assert bit-identity, plus the backend
      goldens, the textdoc and the series, pass unchanged (1049 passed).
- [x] **A series and a joint fit.** The command re-declares per pattern in a series as a
      tie does, and a joint fit takes the same command (with 2103). The series half runs
      through the `constrain` hook with no change to `sequential.py`. The joint-fit half is
      WP-2103's: a joint fit has no `tie` verb yet, so the rule for its `expression=` is
      handed to 2103's Inherited section.
- [x] Tests: unit and property tests, a `test_cross_backend.py` row for a single-fit
      formula, and obs/calc/diff PNGs to `tests/output/`.
- [x] Manual: the constraints guide and the expressions reference show the command.
      `guides/tie.md` § Tie to a formula, `reference/expressions.md`,
      `reference/parameter-table.md` (`TieSpec.expression`), both switching pages with the
      GSAS-II degree warning (consent item); the TOPAS writer refuses a formula tie.
- [x] Skill: the reference row for the command, keyed by its name. The generated
      `api.md` row carries `expression=` and the radians trap in its first line;
      `series.md`'s `constrain=` row names `ref.tie`.

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

- **2026-11-07** — Tasks 3-8 are done and the WP closes (second session of the day). A single
  refinement can now set a parameter by a formula: `tie(path, expression="...")`, over
  variables declared with `add_variable` and numbers. A Debye-model Biso refined on a
  synthetic LaB6 pattern recovers its Debye temperature within 2 esd, and today's linear ties
  are untouched, so no stored file or golden moved. The joint-fit half of task 5 is WP-2103's,
  because a joint fit has no `tie` verb yet. Session by a ghostshift runner, PR #1456.
  - *Done.* 69f3a31e8: `Refinement.tie(path, source=None, *, scale, offset, expression=None)`;
    `TieSpec.expression` (additive, schema 0.61, recorded in `common.py`'s history);
    `_apply_ties` declares formula ties after every linear tie, through
    `refine._add_formula` → `ParameterTable.add_expression`; `parameters()` reads a formula's
    target as `tied: = <text>` and the rows its block took over (a cubic `b`, `c`; a user's
    linear follower) as the linear ties they are; `untie`, `set_values`, `remove_variable`
    and `_tie_entry` know a formula's rows; the `set_tie` node renders
    `ref.tie(path, expression=...)`. a98f94466: `test_cross_backend.py` row `tie_expression`.
    8536aef05: manual (`guides/tie.md` § Tie to a formula, `reference/expressions.md`,
    `reference/parameter-table.md`, both switching pages with the GSAS-II degree warning, the
    consent item); `willis1975` in the bibliography; the TOPAS writer refuses a formula row,
    which it would otherwise have written as the constant 0. 744e01265: the skill's generated
    `api.md` row and `series.md`.
  - *Refusals*, each by name: a name that is not a declared variable; a formula reading no
    variable (`set_values`); a value off the target's bounds or not finite at the variables'
    present values; a site DOF or rigid-body increment (a step from where the fit began, which
    no formula can set absolutely); `source` and `expression` together; `scale`/`offset` with
    `expression`; plus every existing target refusal (symmetry-fixed, symmetry-tied,
    mode-fixed, already tied).
  - *Measured* (`[dev,jax,torch]` venv, darwin/arm64). Acceptance: θ_D = 1291.7 ± 113.5 K
    against the true 1100 K on seed 7 (1.69 esd), 1090 ± 67 (seed 8, −0.14), 1160 ± 80
    (seed 9, 0.75); Rwp 0.040-0.041, GoF 0.98-1.03. A linear formula and the matrix tie agree
    to 4e-16 relative in value and 1e-10 of the column's scale in the analytic Jacobian.
    `tie_expression` passes fd, jax and torch. The eleven test files that tie and assert
    bit-identity, plus backend goldens, textdoc and sequential: 1049 passed.
  - *Finding: the WP's acceptance formula as written is degenerate.* `B0 * debye(thD/T)` at one
    T gives one Biso, so B0 and θ_D cannot both be recovered. The test uses the Debye model's
    full form (James 1962; Willis & Pryor 1975), B = 6h²T/(m k θ_D²)[D₁(θ_D/T) + θ_D/4T], with
    θ_D the one free variable. The Willis & Pryor citation is from recall and was not checked
    against the book; the formula's two limits were checked by derivation (high T:
    6h²T/(m k θ²); T → 0: 3h²/(2 m k θ)).
  - *Series.* No change to `sequential.py`: the `constrain` hook declares a formula as it
    declares a tie. A per-pattern number (the temperature) goes into the text, because a
    variable is carried from the previous pattern under `carry=["*"]`.
  - *Collision.* `multi.py` and `params/multi.py` untouched. WP-2103's Inherited gains the
    joint-fit keyword's rules.
  - *Gotcha.* A formula target is a derived row the table holds `locked`; every refusal that
    read `locked` as "structurally fixed" now checks the user register first.
  - *Review* (`/code-review high --fix`, 10 findings, 4 fixed in 6a12399d6). Fixed: `replay`
    read a formula tie as an affine row with no terms and set its target to 0 (a sibling the
    `spec.terms` sweep missed); the `.rxt` document printed a formula with its own spacing and
    re-parsed it collapsed, so an unedited save read as an edit; a held target refused a
    formula that a rebuild accepts; the register-and-commit block was duplicated
    (`_register_ties`). Also `body_misfit` now drops a tie by `sources`, not `terms`.
    Declined: the table still holds a formula's rows `locked` with no tie, and only
    `parameters()` reads them as ties, so `STAGE_PATH_NOT_FREE` calls a cubic `b` under a
    formula-set `a` "fixed by symmetry or by the model", and `_cell_runaway_withheld` does not
    carry a withheld `a` to `b` and `c` (a table-level "written by a block" flag reaches into
    WP-1964's code; a follow-up if a case shows it). `set_values` on a user follower of a
    formula target says "set the variables it reads", which names the wrong fix there.
    `TieSpec` accepts `expression` beside non-empty `terms` (a validator narrows a stored
    format, which is the maintainer's). `TieSpec.sources` re-parses the text per call.
  - *Inherited.* All three notes were consumed: the degrees note became the manual's warning
    (consent item); the joint fit's convention is handed to WP-2103's Inherited; the reader
    surfaces (`vars.*` rows, `RefinedParameter.equations`) are reused unchanged, with
    `equations=[]` on a single fit as before.
  - *Counts* (`[dev,jax,torch]` venv, darwin/arm64, fast selection, run alone through the
    machine queue): 14659 passed, 57 skipped, 36 xfailed in 9:48. Added: 27 cases in
    `tests/test_tie_expression.py` (3.69 s in all, the series test the slowest at 1.49 s), and
    the `tie_expression` row's 8 cases in `test_cross_backend.py` (1 skip: no axial columns).
    The full suite was not run: no measured number can move, since the linear route is
    unchanged. Reader output: unchanged against the merge-base (`tests.reader_output` exit 0).
  - *Generality.* Not dispatched: `_audit.py` is untouched and the WP adds refusals only, no
    threshold, fallback or automatic action.
  - *Next:* merge. Then WP-2103 builds the joint fit's `tie` with `expression=` from its
    Inherited note.

- **2026-11-07** — Task 2 is done. The maintainer ruled design questions 1-3 and the two
  consent items in a session with the shift lead, after the brief in the 2026-11-06 entry.
  Task 3 is next, and nothing waits on the maintainer. PR #1453.
  - *Ruling 1, how a formula names a model parameter: (a).* A formula reads only named
    variables (`vars.<name>`, made by `add_variable`) and constants. To read a model
    parameter, the user first ties it to a variable. The maintainer asked which option was
    easiest for agents, which was closest to TOPAS and which fitted the design ethos, then
    chose (a). Grounds: it extends a rietx convention (WP-1119's variables, and the
    2026-11-06 ruling that a joint fit's formulas read them) and adds no concept, so one rule
    holds in every fit. It is closer to TOPAS, which names a parameter where it is declared,
    than a per-call name map. The pull towards a name map for agent ease is answered by the
    same consistency, since agents already use variable plus tie in a joint fit. A name map
    can be added later without breaking (a), if a measured case shows formulas mostly read
    model parameters directly. A fourth option, naming a model parameter in place
    (`name(path, "zr")`, TOPAS's exact form), was raised and not chosen, because it adds a
    second naming layer beside variables.
  - *Ruling 2, the spelling: a keyword on the existing verb,*
    `tie(path, expression="...")`. `untie`, the `set_tie` node and checkout serve both kinds,
    and `Refinement._ties` stays the one record of user constraints. The keyword is
    `expression`, rietx's own term (`ParametricEquation(basis="expression", expression=...)`
    and the grammar's reference page). Recall puts "expression" as the commonest noun
    (GSAS-II, Lepton, muParser, OpenMM, COPASI) and `expr` as the commonest keyword in Python
    fitting libraries (lmfit), so lmfit users type four more letters.
  - *Ruling 3, linear ties: (a), two routes and no detection.* `tie` with a path source and
    `tie_equal` stay on the constant matrix. `tie(path, expression=...)` always runs as a
    formula, even when it is linear. No stored file or tie golden moves.
  - *Consent items, both stand.* The grammar keeps radians with `pi` and gains no `sind`. The
    manual warns that GSAS-II's expression `sin`, `cos` and `tan` take degrees
    (`GSASIIobj.py:1640-1642`), so a ported GSAS-II formula with an angle changes value
    without an error. That warning lands with task 7.
  - *Inherited.* The fourth note (WP-1964's generality review) is deleted: #1442 merged on
    2026-11-06, and the 2026-11-06 entry answers both of its checks. The other three stay.

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
