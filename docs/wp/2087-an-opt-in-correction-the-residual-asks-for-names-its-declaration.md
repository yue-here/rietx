# WP-2087 — An opt-in correction the residual asks for names its declaration in the docs

Milestone: unscheduled · Status: ✅ 2026-11-12 — all six tasks merged (PRs #1505, #1515); the maintainer approved the Biso help text and the unknown-path texts as written
Track: What fires, and what stays silent
Depends on: [1944](1944-the-structural-plan-frees-extinction-only-where-declared.md)

## Goal

Each opt-in correction that a fit's residual can give evidence for is
findable from the documentation. Its help entry, its manual section and, where
a skill row already covers the symptom, that row name the declaration a user
writes and the misfit that calls for it. The package adds no diagnostic,
report action or printed line for it.

## Context

**Rescoped 2026-11-05 to documentation pointers only.** The maintainer
ruled on 2026-11-04, on WP-1944's `EXTINCTION_UNDECLARED`: "remove
EXTINCTION_UNDECLARED from the package entirely; keep findability through
documentation; the skill row as concise as possible." The same reading
governs this WP, which WP-1944's runner filed to build residual-triggered
pointers for three more corrections. So findability here means a user can
find the declaration in the docs. It does not mean the fit detects the
need and prints it. WP-1944's follow-up PR records the ruling and shows the
extinction pattern this WP copies: the `help.py` entry says when to declare
it, the theory page's section says how, and one skill row names it among a
symptom's causes.

**From WP-1944's sweep** (the maintainer's ruling of 2026-11-03: "check this
for extinction and any other opt-in features"). The sweep table is in
WP-1944's handover log. Three gaps remain.

- **Stephens anisotropic microstrain** (`Phase.microstrain`). The report
  already computes `FitReport.strain` (`report/strain.py`). The help entry
  and the manual's Stephens section should say what an hkl-dependent width
  misfit looks like and name `Phase.microstrain = StephensStrain.isotropic(...)`.
- **Anisotropic ADPs** (`Atom.aniso`). A powder fit rarely determines it.
  The help entry should say when a declaration is worth trying and name
  `Atom.aniso`.
- **Surface roughness and specimen absorption.** The `BISO_NEGATIVE` and
  `BISO_UNUSUALLY_LARGE` help entries and skill rows name "uncorrected
  absorption or roughness" in prose. They should name the declaration each
  geometry takes: roughness on a Bragg-Brentano plate, µR on a capillary,
  µt on a flat plate (root CLAUDE.md: a correction belongs to a geometry).
  The diagnostic's own `suggestion` stays as it is, because a change to it
  is a reader-output change this rescope does not make. The two help
  entries print as a notebook diagnostic's explanation, so they are reader
  output too. The maintainer approved them as written on 2026-11-09 (PR #1505).

**Which way an undeclared extinction moves Biso** (folded 2026-11-09 from
WP-1944's inherited entry). `model/extinction.py`'s docstring and the theory
page's Primary extinction section said an uncorrected extinction gives "a
spuriously large Biso and a small scale". WP-1944 measured the opposite on
its LaB6 synthetic: with 2.5 µm² planted and extinction undeclared, La's
Biso came out 0.364 ± 0.009 against a true 0.5, and the scale 8 % low.
Sabine, Von Dreele & Jørgensen (1988, p. 374) say the same in their
introduction, of time-of-flight and constant-wavelength work alike: "the
measured temperature factors have lower values than the true temperature
factors", "in some cases negative". A second fixture, measured
here on a rutile synthetic (15-120° 2θ, Cu Kα, true B 0.5 on both sites,
scale, both B, the O coordinate and the background free):

| Planted ext (µm²) | Declared | Ti B | O B | Scale (true 8.0e-3) |
|---|---|---|---|---|
| 5 | no | 0.293 ± 0.021 | 0.279 ± 0.039 | 7.1e-3 |
| 5 | yes | 0.509 ± 0.028 | 0.472 ± 0.041 | 8.0e-3 |
| 20 | no | −0.168 ± 0.032 | −0.075 ± 0.062 | 5.5e-3 |
| 20 | yes | 0.505 ± 0.032 | 0.503 ± 0.045 | 8.0e-3 |

So both B and the scale go down, and a strong extinction makes B negative.
Both texts now say so.

**The unknown-path error names the declaration** (from WP-1944's
inherited entry; settled by Claude on 2026-11-09 under the close-the-class
rule and help.py as the one authority for what a name is; the maintainer
may reverse it). On a phase that declares no extinction,
`set_vary(["phases.0.extinction"], True)` raised "unknown parameter path
'phases.0.extinction'; did you mean 'phases.0.lor_strain'?" (measured by
WP-1944's code review). It is the one place the package meets a user who
already guessed the name. `refine._path_hint` now names the declaration
when the path belongs to an opt-in correction its owner does not declare.
The mapping from path family to declaration is `rietx.help.OPT_IN`, one
row per correction. `tests/test_help.py` executes each row's declaration
and crosses the rows against the families a model declaring nothing
lacks, both ways. A roughness row answers only on an X-ray Bragg-Brentano
instrument, the one the schema accepts. A retired spelling keeps priority. The change is to
error and warning text, which is reader output. The maintainer approved the
before and after texts in PR #1515's body as written on 2026-11-10, before
its merge.

## Non-goals

- Extinction (WP-1944, done in its follow-up).
- Any new diagnostic code, report action, `ActionKind` member or audit row.
- Any change to what a fit prints or returns, except the unknown-path
  answer above (an error's text and `STAGE_PATH_UNKNOWN`'s message).
- Freeing any of these by default.

## Tasks

- [x] Extinction's Biso direction: correct `model/extinction.py`'s docstring
      and the theory page's Primary extinction section (2026-11-09).
- [x] Stephens: the help entry and the manual section name the declaration
      and the misfit that calls for it.
- [x] Anisotropic ADPs: the help entry names `Atom.aniso` and when a
      declaration is worth trying.
- [x] Biso anomalies: the two help entries and their skill rows name the
      declaration each geometry takes, as concisely as the extinction row.
- [x] Skill: stay within `tests/skill_caps.py`'s budgets; re-sync the
      committed copies.
- [x] Unknown-path answer: `refine._path_hint` names an undeclared opt-in
      correction's declaration, from `help.OPT_IN`, with the crossing
      meta-test (2026-11-09).

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_help.py tests/test_params_surface.py tests/test_skill.py tests/test_skill_cli.py tests/test_manual.py
.venv/bin/python -m ruff check src tests examples
```

## Handover log

- **2026-11-12** — closed by a ghostshift runner (PR #1540). Both pull requests
  merged: #1505 on 2026-11-09 (`817553965`) and #1515 on 2026-11-10
  (`67e70ed02`). A user can now find, in the help and the manual, the line
  that declares Stephens strain, an anisotropic displacement tensor, or the
  absorption or roughness correction a Biso anomaly points to. A user who
  guesses an undeclared correction's parameter name is told that line. The
  two calls the earlier entries left for the maintainer are answered, so
  nothing remains. Nothing was run or measured in this session.

  *Rulings recorded.* Both are in Context, beside what they govern.
  (1) The `BISO_NEGATIVE` and `BISO_UNUSUALLY_LARGE` help text, which a
  notebook prints as the diagnostic's explanation, may land as written. The
  maintainer approved it on 2026-11-09, before #1505 merged. (2) The
  unknown-path error and `STAGE_PATH_UNKNOWN` texts in #1515's "What a
  reader receives" were approved as written on 2026-11-10, before its merge.
  Whether `refine._path_hint` names the declaration at all was settled by
  Claude on 2026-11-09, as Context says, and stands.

  *Done.* Status set to ✅ and the Priority line removed. No § Inherited
  to clear. The 2026-11-09 entry left one known defect: the retired
  `using/glossary` address redirects to the phase page of the parameter map,
  so an old link to an instrument entry lands there without its anchor. That
  went to [1986](1986-guides-and-theory-move-over-and-the-old-tree-retires.md)'s
  § Inherited, since 1986 owns the retired addresses. The refinement page
  still does not mention the opt-in answer, for want of 154 characters; the
  parameter-table page does, so that stays a record, not a task.

  *Next:* none.

- **2026-11-10** — the unknown-path answer, by a ghostshift
  runner (PR #1515). A user who guesses the name of an opt-in correction's
  parameter, on a model that has not declared the correction, is now told
  the line that declares it. Before, the package offered the nearest real
  name, which was a different parameter: `lor_strain` for extinction,
  `cell.c` for a texture coefficient. Seven corrections are covered. A
  correction the model has declared, a phase or atom the model lacks, and
  a roughness block on a geometry that refuses one all keep the old answer,
  because a declaration there would be wrong or would raise. The change is
  to error and warning text, so it waits on the maintainer's review of the
  before and after texts in the PR.

  *Done.* `rietx.help.OPT_IN` holds one row per opt-in correction: its
  name, its owner glob, its `PARAMETER_HELP` families and the declaration
  code. `STAGE_PATH_UNKNOWN.suggestion`'s audit row counts 3 sites, not 2. The rows are extinction, March-Dollase orientation, spherical-
  harmonics texture, Stephens strain, the anisotropic displacement tensor,
  and Suortti and Pitschke roughness. The two roughness rows carry
  `geometry="bragg_brentano"` and `source="xray_cw"`, the kinds the schema
  accepts. `help.undeclared_opt_in(path, known, instrument)` decides; a
  row with a geometry answers only when the caller passes an instrument of
  that kind, which every `Refinement` verb and both of its
  `STAGE_PATH_UNKNOWN` call sites now do. A joint fit's `hist.N.` prefix is
  carried onto the owner ("phase 0 of histogram 1"); the joint fit's own
  `STAGE_PATH_UNKNOWN` passes no instrument, so roughness there keeps the
  nearest path. `help.family_matches` is the one depth-aware matcher.
  `refine._path_hint` checks a retired spelling first, then the opt-in
  rows, then the nearest path. `STAGE_PATH_UNKNOWN` builds its own opt-in
  branch: the message names the correction and the suggestion gives the
  declaration. Its help entry
  names the cause. The parameter-table page's verb section and refusal
  table say so too. The refinement page is 154 characters short of room,
  so it does not.

  *Measured.* Fast suite (`-m "not slow"`), `[dev]` venv, darwin/arm64,
  through ghostshift's serial queue, alone: 14418 passed, 1 failed, 418
  skipped, 32 xfailed. The failure was `test_audit_table.py`'s count of
  `STAGE_PATH_UNKNOWN`'s suggestion sites, 2 in the table against 3 in the
  tree; the row now says 3, and that file passes 23 of 23. Main moved since
  the last entry's count, so no exact delta is quotable. Added: 18 cases in
  8 tests, 0.39 s together (`tests.added_test_times`, one local run), none
  near the slow tail. The judge's fixes came after this run: message
  wording, the axis placeholder and tests. The three touched test files
  then passed 179 of 179. `python -m tests.reader_output`: exit 0,
  unchanged against the merge-base; the standard fit prints no unknown
  path. Full suite not run: no measured number can move.

  *Review.* `/code-review high --fix` applied nothing and returned seven
  findings. Fixed: roughness hinted on a capillary, where the declaration
  raises (now gated on the instrument, with a test holding each gate to the
  schema's refusal); the anisotropic declaration failed as copied, with
  `uiso` undefined and a free biso (now `atom.biso.vary = False;
  atom.aniso = AnisoU.isotropic(atom.biso.value / (8 * math.pi**2),
  phase.cell)`, which the test executes on a free biso); a joint fit's
  scoped paths fell back to the nearest path (now handled); the
  suggestion still said to correct the path (now says to declare); the
  matcher was written twice (now one function). Declined: `known` is
  copied per call (an error path, at most a few hundred rows), and the
  retired lookup runs twice in `STAGE_PATH_UNKNOWN` (gone: the opt-in
  branch no longer calls `_path_hint`).

  *Generality.* The judge (generality-review) returned: item 1, the third
  `STAGE_PATH_UNKNOWN` suggestion site, holds (it names two remedies and
  picks neither). Item 2a, the fallback chain, weak: the chain is
  arithmetic and needs no row, but "it exists only once X is declared" was
  false for an indexed family (`texture.c6_0` against `order=4`, a Stephens
  DOF past the subspace), and the source gate was untested; `help.py`'s
  `NOT_WALKED` reason no longer covered `OPT_IN`. Item 2b, the embedded
  values, weak: the March-Dollase axis `(0, 0, 1)` and the texture
  `order=4` read as answers, while extinction 0.0, the roughness blocks,
  the isotropic tensor and the Stephens 1000 ppm seed (GSAS-II's isotropic
  Mustrain default) hold. Author's answer: the message now says "it is a
  parameter of X, which <owner> does not declare", true of every member,
  and the follow-up error names the real indices; the source gate is
  tested; the `NOT_WALKED` reason names `OPT_IN`; the axis prints as
  `(h, k, l)`. The texture order stays 4, the order `report/layer2`
  already prints for a texture action (WP-1944 ruling 2's precedent),
  against GSAS-II's off-by-default 0.

  *Deliberately not generalised.* `NOT_OPT_IN` in `tests/test_help.py`
  names each family only a declaration creates that has no row, with the
  reason: time-of-flight bank parameters, the measured-background scale
  and air term, additive extra components, magnetic structures, rigid
  bodies, distortion modes and named variables. Each is model content or a
  source kind rather than one assignment. A misspelling of an undeclared
  correction (`phases.0.extinctoin`) still gets the nearest real path.

  *Next:* the maintainer reviews the texts in PR #1515's "What a reader
  receives". If any row is reversed, edit `help.OPT_IN`, and the two tests
  follow. The earlier call on the `BISO_NEGATIVE` and
  `BISO_UNUSUALLY_LARGE` help text (entry below) still stands. With both
  answered and this PR merged, the WP can close.

- **2026-11-09** — all five tasks done, by a ghostshift runner (PR #1505).
  A user who reads the help for Stephens strain, an anisotropic
  displacement tensor, or a negative or very large Biso now finds the
  declaration that turns the matching correction on, and the misfit that
  calls for it. Nothing a fit prints changed on the standard fit. The
  theory page and the extinction module had one bias backwards: an
  undeclared extinction lowers Biso, and a strong one drives it negative.
  The parameter map had reached the manual's page-size cap, so it is now
  two pages, one for the phases and one for the instrument and background.

  *Done.* Extinction direction corrected in `model/extinction.py`'s
  docstring and the Primary extinction section, cited to Sabine, Von Dreele
  & Jørgensen (1988, p. 374), with the rutile table in Context. Stephens:
  `_STEPHENS_S` and the theory section give
  `StephensStrain.isotropic(1000, phase.cell)`, say `lab_sample_refine`
  frees it, point at `FitReport.strain`, and name anisotropic size and a
  too-high symmetry as look-alikes. Anisotropic ADPs: the `adp.*` entry
  gives `Structure.from_cif(path, aniso=True)` and
  `AnisoU.isotropic(uiso, phase.cell)`, says the assignment raises while
  `biso.vary` is True, and says when to try one and when to keep it.
  `BISO_NEGATIVE` (help entry and skill row) names roughness on a
  Bragg-Brentano plate, `mu_r` or `capillary_radius_mm` on a capillary,
  and extinction. `BISO_UNUSUALLY_LARGE` names `mu_t` or `thickness_mm` on
  a flat plate. The directions are the theory page's. The diagnostics'
  `suggestion` text is unchanged. Parameter map: `PARAMETER_PAGES` in
  `docs/reference_pages.py` assigns each group to `parameters.md` or the
  new `parameters-instrument.md`, and the build raises on a group shown
  twice, nowhere, or unknown. Before the split the page stood at about
  49 600 characters against the 50 000 cap, and the Stephens sentence alone
  broke it; now 25 400 and 24 000. Links to moved anchors are repointed,
  and nine pages that said the map lists every name now name both. The
  inherited entries are pruned: the extinction claim folded into Context
  with its measurement, the unknown-path error moved to Context as
  waiting on the maintainer.

  *Measured.* Fast suite (`-m "not slow"`), `[dev]` venv, darwin/arm64,
  through ghostshift's serial queue, alone: 14343 passed, 417 skipped,
  32 xfailed (passed+skipped 14760). Added: three cases of
  `test_a_group_shown_twice_or_nowhere_raises`, 0.00 s together. Full
  suite not run: no measured number can move. `python -m
  tests.reader_output`: exit 0, unchanged against the merge-base.

  *Review.* `/code-review high --fix` found five, no code bugs: stale
  links on four more pages (fixed), the ADP entry's biso clause (rewritten:
  the assignment does raise while `biso.vary` is True, measured, so the
  reviewer's "already locked" reading holds only after the declaration),
  the capillary and plate inputs (fixed), "from the residual" for
  `FitReport.strain` (fixed), and an untested arm of the split check
  (test added). Declined: `reference/refinement.md` keeps one link to the
  parameter map, whose intro links the instrument page, because a second
  link puts that page 51 characters over the cap. Left alone: the
  `using/glossary` redirect in `docs/docs_versions.py` now lands instrument
  fragments on the phase page without their anchor.

  *Generality.* The judge (generality-review) returned: items 1, 2 and 6
  (the two skill rows, the extinction direction) hold; item 3 (the two
  help entries) holds with two findings, the unsourced "usually" (removed)
  and that `Diagnostic.explanation` prints under a notebook's `help:`
  line, so these two entries are printed text the maintainer should see;
  items 4 and 5 (the ADP and Stephens guidance) weak: the ADP keep test
  failed near-zero off-diagonal components, the trigger read as X-ray only
  and required single-crystal work, and the Stephens sentence named one
  remedy for a symptom anisotropic size and a too-high symmetry share. All
  three were rewritten as described under *Done*. Neither sentence cites a
  source; both are rietx's own wording.

  *Next:* the maintainer's two calls. (1) The unknown-path error (Context,
  "Waiting on the maintainer"): if approved, `refine._path_hint` names the
  declaration for an opt-in path, as reader output. (2) Whether the
  `BISO_NEGATIVE` and `BISO_UNUSUALLY_LARGE` help text, which a notebook
  prints as the diagnostic's explanation, may land as written. With both
  answered and this PR merged, the WP can close.

- **2026-11-05** — rescoped to documentation pointers only, by WP-1944's
  follow-up session under the maintainer's ruling of 2026-11-04 (quoted in
  Context). The three tasks that designed a diagnostic or an action are now
  help, manual and skill edits. Nothing run here. *Next:* the Stephens task.

- **2026-11-04** — filed by WP-1944's runner from its opt-in sweep. Nothing
  run here. *Next:* the Stephens task.
