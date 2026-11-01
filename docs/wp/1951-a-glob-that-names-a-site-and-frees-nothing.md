# WP-1951 — a glob that names a site and frees nothing

Milestone: unscheduled · Status: ✅ 2026-11-01 — a stage glob naming one site that frees nothing is reported, set_vary warns, the verbs name the nearest path; PR #1304, warning-vs-info level open for the maintainer
Track: What fires, and what stays silent
Depends on: —

## Goal

A plan glob whose fixed segments name one concrete site, and which matches
no row, is reported. So is an unknown literal path on `set_vary`, with the
near-miss `STAGE_PATH_UNKNOWN` already gives a stage. A wildcard-index glob
that matches nothing stays silent, as WP-1414 decided.

## Context

**The report (issue #896).** An application lets a person flag parameters to
refine and wants to say why one will not move. The person flags Ti's
position on rutile (P4₂/mnm, Ti at 0,0,0). The app frees
`phases.0.atoms.0.dof.*`, which matches nothing, and nothing says so. The
reporter also asks for a reason on each parameter row (`held_by:
"symmetry" | "tie" | "lock"`).

**The per-row reason exists, checked at `d80ca5f4`.**
`Refinement.parameters()` (`refine.py:2290`) returns `ParameterRow`s.
`ParameterRow.held_because` (`schemas/params.py:173-203`) gives a sentence,
ordered by what the caller can do: rigid body, `locked` ("structurally
fixed by symmetry or by the model"), a tie with its sources, `mode_fixed`,
a `hold()`, a held wavelength cell. The fields it reads (`body`, `locked`,
`tie` with `tie.user`, `mode_fixed`, `held`, `needs_held_cell`) are on the
row, so a program needs no enum. The sentence gives no subject for
"symmetry or the model". `rietx.gui.symmetry.held_causes`
(`gui/symmetry.py:357`) supplies it: "a site symmetry of order 8 allows no
displacement at all".

**The silence, ran at `d80ca5f4`.**
- On rutile, Ti's `x`, `y`, `z` are locked and it has **no `dof` rows at
  all**. Only O has `phases.0.atoms.1.dof.0`.
- `ref.set_vary("phases.0.atoms.0.dof.*")` returns `[]` with no warning.
- A stage with `turn_on=["phases.0.atoms.0.dof.*"]` gives `freed=[]`,
  `unknown_paths=[]` and no diagnostic.
- A literal is already covered. `phases.0.atoms.0.x` fires
  `STAGE_PATH_NOT_FREE` with "nothing to free: every coordinate of this
  site is fixed by its site symmetry" (`refine.py:6075`).
  `phases.0.atoms.0.dof.0` fires `STAGE_PATH_UNKNOWN` with "did you mean
  'phases.0.atoms.1.dof.0'".
- `STAGE_FREED_NOTHING` exists only for a joint fit (`multi.py:1513`).

**Why globs are silent.** WP-1414 (✅) decided that "a single glob that
matched nothing on its own stays silent", because shipped plans carry globs
some models do not have (`phases.*.microstrain.dof.*` on a model without a
Stephens block). `params.vector.unknown_paths_among` (`:357`) implements it,
and two tests pin it: `tests/test_params_surface.py::
test_a_path_that_is_free_or_not_a_phase_literal_stays_silent` (its
`dof-glob` and `pattern` cases) and
`::test_a_hump_glob_on_a_model_without_a_hump_stays_silent`. The skill's
`references/surprises.md` § 8.28 tells an agent to read `StageResult.freed`.

**A narrower rule leaves that decision whole.** A glob whose fixed leading
segments name an existing site (`phases.0.atoms.0.`), and which matches no
row, cannot be a shipped plan's healthy miss. None of the 29 distinct
`turn_on` entries in `PLAN_PRESETS` has a numeric segment (counted at
`d80ca5f4`). WP-1414's `dof-glob` test case must be read before choosing:
if it is a concrete-site glob, the rule changes what it pins, and that
needs the maintainer.

**The verb half is 1414's named leftover.** Its closing entry: "`Refinement.
set_vary("instrument.zero")` returns `[]` silently, while `hold` raises
'unknown parameter path' with no near-miss. Both are one call to
`rietx._nearmiss` away, and are unowned."

**The tier of each rule this WP adds** (written 2026-11-01). The site-glob
branch of `STAGE_PATH_NOT_FREE` is tier 1, ambiguity 1: it is arithmetic on
the table (does any matched row move?), with no threshold. `set_vary`'s
warning and the verbs' near-miss are the same tests on a second surface.

## Non-goals

- A `held_by` enum on `ParameterRow`. The row's fields already say it.
  Adding the symmetry subject from `held_causes` to the sentence is in
  scope only if it is a one-line import.
- Globs with a wildcard index (1414's decision stands).
- A `PlanSpec` validator refusing unknown literals before a fit (1414 left
  it to the maintainer).

## Tasks

- [x] Read 1414's two pinned tests and say whether any case is a
      concrete-site glob. If one is, put the question to the maintainer and
      record the answer as `Decided YYYY-MM-DD:`.
      *Done 2026-11-01:* the `dof-glob` case (`phases.0.atoms.1.dof.*` on
      LaB6) is a concrete-site glob, but it matches B's free `dof.0` and is
      the test's positive arm. The rule fires only when the glob frees
      nothing, so that case still passes unchanged. The `pattern` case and
      the hump test have no numeric segment. No question for the maintainer.
- [x] `STAGE_PATH_NOT_FREE` (or a sibling code) for a concrete-site glob
      that matches no row, naming the site and why (site symmetry, from the
      same text the literal case uses).
      *Done:* `refine._site_glob_diagnostics`, the same code. It fires when
      no row the glob matches can move (`_frees_for_request`), which also
      covers a glob matching only locked or symmetry-tied rows.
- [x] `Refinement.set_vary` and `hold` on an unknown literal: the
      near-miss message `STAGE_PATH_UNKNOWN` gives a stage. `set_vary`
      warns. Whether `hold` keeps raising is recorded.
      *Done:* `set_vary` warns (`UserWarning`) on an unknown literal, and
      when freeing on a declined phase literal or site glob, with the
      stage's text. `hold` keeps raising, since it always has and a hold on
      nothing is a claim; the refusal now names the nearest path, as do
      `unhold`, `untie`, `tie`, `set_values` and `profile_interval`.
- [x] Tests: rutile Ti's `dof.*` fires, `phases.*.atoms.*.dof.*` on the same
      model stays silent, every preset on the acceptance fixtures fires
      nothing new.
      *Done:* `tests/test_params_surface.py`. The preset half is structural
      (`test_no_preset_names_one_site`): the rule needs a concrete site
      index, and no preset glob has one.
- [x] Skill: `surprises.md` § 8.28 gains the concrete-site case. The
      diagnostics reference row if the code is new.
      *Done:* § 8.28, trimmed to stay inside the file's byte budget. The
      code is not new, so the row stands; `help.py`'s entry gains the case.

## Acceptance

On rutile, freeing `phases.0.atoms.0.dof.*` reports Ti as fixed by site
symmetry. `set_vary` on an unknown literal warns with the nearest path.
Every shipped preset fires nothing new on the acceptance fixtures.

```sh
.venv/bin/python -m pytest tests/test_params_surface.py tests/test_skill.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- Issue #896.

## Handover log

- **2026-11-01** — PR #1304. A stage that asks to refine one atom's position
  by a pattern, where the atom sits on a fully fixed special position (Ti on
  rutile's 2a), now says so, where it used to freeze the atom without a word.
  `set_vary` now warns when a call changes nothing it named, and every verb
  that refuses an unknown path names the nearest real one. Wildcard patterns
  stay silent, as WP-1414 decided, and no shipped plan can trigger the new
  report. A joint fit does not get it yet (WP-2028 inherits that).

  *Done:* all five tasks (ticked above with what did each).
  `refine._site_glob_diagnostics` adds a branch to the existing
  `STAGE_PATH_NOT_FREE`: a glob whose fixed segments name an existing site
  (`phases.<i>.atoms.<j>.`) and that frees no row by `_frees_for_request`. It
  says why when the glob reached the coordinates: site symmetry fixes every
  one (no suggestion, as for the literal), a rigid body places them, or they
  move through `dof` rows (named). A biso freed by the same request answers a
  one-site `adp.*` (the displacement stages' pair, copied per atom).
  `Refinement.set_vary` warns (`UserWarning`) on an unknown literal with the
  nearest path, and when freeing on a declined phase literal or site glob,
  through the same two builders, after the call has committed. `hold`,
  `unhold`, `untie`, `tie`, `set_values` and `profile_interval` keep raising
  and name the nearest path (`_path_hint`, retired spellings first). The audit
  row for `STAGE_PATH_NOT_FREE` gets tier 1, ambiguity 1, response `warning`;
  its `.suggestion` row counts 2 sites and stays unaudited.

  *Reader-facing text* (new; `python -m tests.reader_output` exit 0, the
  standard fit unchanged, since it names no site):
  `Stage 'only' asked for phases.0.atoms.0.dof.*, which matches no
  parameter, so nothing was freed for it. Every coordinate of
  phases.0.atoms.0 is fixed by its site symmetry, so the site has no dof
  rows.`, and as a warning `set_vary freed nothing for 'instrument.zero',
  which names no parameter of this model. Did you mean
  'instrument.zero_shift'?`.

  *Review:* `/code-review high --fix` found seven; three fixed in
  `85a1aac5`: the census test `test_multi_diagnostics` was red for the new
  helper (now an `ABSENT` row in `multi.DIAGNOSTIC_SCOPES`),
  `profile_interval`'s hint now goes through `_path_hint`, `set_vary` passes
  a real `Stage`. Its warning-order finding was fixed after the judge's pass
  (warn after commit). Declined: the joint fit (waits on PR #1270, forwarded
  to WP-2028); the GUI not surfacing `set_vary`'s warnings (a design choice,
  below); the package-built site globs (`report/body_misfit`'s released arm,
  an internal trial whose findings are not surfaced, and `io/recipe`'s
  flagged coordinates, which can name a fixed site only after a caller ran
  `fix_special_positions` on a stored plan, and then the report is true);
  the audit evidence now names both. A second runner merged origin/main
  (one conflict, WP-2028's `### Inherited`, both entries kept) and added
  `STAGE_PATH_NOT_FREE`'s pair to `tests/silence.py`, which main's
  WP-2037 rule asks of every code whose audit row says `warning`; the
  fast suite was red on its absence until then.

  *Generality* (judge re-run on the final merged tree, since the first
  pass's verbatim text was lost with the earlier runner's context; pasted
  unedited):

  ### STAGE_PATH_NOT_FREE (code)

  **Verdict: holds** on tier 1 and ambiguity 1. The evidence for reporting is stronger. The `warning` level is contested for one case: a site that symmetry fixes completely.

  | Question | Author's answer | Found | Verdict |
  |---|---|---|---|
  | 1 What it decides | It treats a glob naming one concrete site that frees nothing as the caller's claim (WP file, Context) | It fires only on a `phases.<i>.atoms.<j>.` glob. No preset names one (`test_no_preset_names_one_site`). | holds |
  | 2, 5 Kind and tier | "arithmetic on the table … no threshold" (WP file, tier paragraph) | Agrees: the test is whether any matched row can move. Pinned by `test_a_glob_naming_one_site_that_frees_nothing_says_why`, `test_a_site_glob_that_frees_something_or_names_no_site_stays_silent` and `test_ti_on_rutile_reports_its_site_symmetry` (`tests/test_params_surface.py`). | holds |
  | 3 Case against | none given | GSAS-II 5.8.4 accepts an X flag (its "refine position" box) on a fully fixed atom. It holds each coordinate as "Fixed by symmetry" and lists it in a printed hold list. It gives no warning (`GSASIIstrIO.py:1775-1791`, `GSASIImapvars.py:1587-1591`, read on disk in rietx-bench). A script that loops over every site gets one warning per fixed site. | bears on the level only |
  | 4 Case for | issue #896: the stage froze the site in silence | A user who ticked one site got no answer. The other cases name a real fix. | holds |
  | 7 What records it | `where=[glob]` | Yes. A joint fit does not report it yet, deferred to WP-2028 (`multi.DIAGNOSTIC_SCOPES`). | holds |
  | Level | `responds`: "…or none where the site symmetry fixes every coordinate" | That clause names no action, and a coordinate fixed by symmetry is exact. The record says two consequences get two codes (generality.md, Attention is a cost, clause 2). WP-1414's literal case (`phases.0.atoms.0.z`) already warns, so a split needs a sibling `info` code covering both. | maintainer's call. I lean towards an `info` sibling as a follow-up. |

  What would change it: a ruling on whether "the plan did not reach what it asked" covers a site with nothing to reach.

  ### STAGE_PATH_NOT_FREE.suggestion

  **Verdict: weak.** The new site's advice is mostly arithmetic. But the row stays unaudited while the code row's `responds` now relies on it.

  | Question | Author's answer | Found | Verdict |
  |---|---|---|---|
  | Baseline | none given | The name was already on the list, so no rule is broken | holds |
  | 3 Case against | none given | The rigid-body advice frees `phases.*.rigid_bodies.*…`: every body in every phase, wider than the one site asked about (`refine._site_glob_diagnostics`). | finding |
  | 4 Case for | none given | "Free <site>.dof.*" is what any refiner would do | holds |

  What would change it: auditing this row in the same change, with the body glob narrowed to the owning body.

  ### set_vary warning and the near-miss in the verbs (outside the table)

  **Verdict: weak.** The near-miss holds. Warning rather than raising on an unknown literal is the weak part.

  | Question | Author's answer | Found | Verdict |
  |---|---|---|---|
  | 1 What it decides | "the return value already says what changed and a glob that declines rows is how plans work" (`set_vary` docstring) | That reason covers globs. An unknown literal has no healthy reading, and `hold` and `set_values` raise on the same fact. DESIGN Rule 4 asks a new API for "a raise on failure". | weak |
  | 4 Case for warning | It returns the same list as before (1.11.0 notes) | No caller breaks | holds |
  | Near-miss | "the same tests on a second surface" (WP file) | It shows one nearest path (difflib, 0.6 cutoff, in `_nearmiss`, which the audit does not walk). The caller decides. This matches STAGE_PATH_UNKNOWN. | holds |
  | 7 What records it | none given | Only the UserWarning. The history node records `turn_on=[]` and nothing of the miss. | finding |

  What would change it: a maintainer ruling on whether `set_vary` raises on an unknown literal, which would be a breaking change.

  *Author's answers.* Level: kept at `warning`, beside WP-1414's literal
  case; the split is the maintainer's question below. Suggestion: the
  rigid-body glob repeats the wording of `hold`'s refusal (WP-1805), so
  narrowing it to the owning body is one change for both sites, forwarded to
  WP-1805's `### Inherited`; the row stays unaudited. `set_vary`: it warns
  because raising would break a caller that passes a list mixing a typo with
  good paths, which today gets the good ones freed; whether to break that is
  the maintainer's, below.

  *Open question for the maintainer (warning or info).* A fully fixed site
  leaves the reader nothing to do. At `warning` (this PR), the sentence sits
  among the fit's warnings beside the literal `phases.0.atoms.0.z`, which has
  warned since WP-1414. At `info` under a new code, it sits below the
  warnings and does not mark the fit as needing attention; the literal case
  should move with it, which changes WP-1414's output. GSAS-II says nothing.
  Recommendation, a lean: keep `warning`, since the caller asked for a
  refinement that will not happen. If you prefer `info`, move both cases
  under one sibling code. A second, smaller question: `set_vary` warns on an
  unknown literal where `hold` raises; keep warning (lean), since raising is
  a breaking change for mixed lists.

  *Measured* (`[dev]` venv, macOS arm64, Python 3.12, alone on the machine
  via `serial.py`): FAST_COUNTS. Added 28 tests: 27 in
  `tests/test_params_surface.py`, one silence pair in `tests/test_silence.py`. Full suite not run: the change moves no
  measured number (diagnostics and warnings only).

  *Not generalised, on purpose:* a glob with a concrete site index the model
  lacks (`phases.0.atoms.7.dof.*`) stays silent, being an index typo that
  `STAGE_PATH_UNKNOWN`'s shared rule would have to own; a concrete phase
  index on another family (`phases.0.microstrain.dof.*`) stays silent, each
  family needing its own reason; the symmetry subject from
  `gui.symmetry.held_causes` was not imported into the literal message (not a
  one-liner from `refine.py`).

  *Next:* the maintainer rules on the new reader text (PR #1304 body), on
  the warning-or-info question above, and on `set_vary` warning rather
  than raising. Then merge. After PR #1270 merges, WP-2028 wires the site builder into the
  joint fit.
- **2026-10-11** — created, from the 2026-10-11 issue triage (issue #896).
  Checked against the tree at `d80ca5f4`: `held_because` and the row's fields
  already give the reason, Ti on rutile has no `dof` rows, and a glob naming
  it frees nothing with no diagnostic. No open WP owns it: WP-1414 (the
  turn-on report) and WP-1435 (holds) are closed, and WP-1341 inherits only
  the joint fit's `STAGE_PATH_NOT_FREE`. *Next:* task 1.
