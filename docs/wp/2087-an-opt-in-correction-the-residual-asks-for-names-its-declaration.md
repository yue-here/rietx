# WP-2087 — An opt-in correction the residual asks for names its declaration in the docs

Milestone: unscheduled · Status: 🔄 2026-11-09 — claimed by @yue-here (ghostshift runner: the unknown-path hint names the declaration)
Track: What fires, and what stays silent
Depends on: [1944](1944-the-structural-plan-frees-extinction-only-where-declared.md)
Priority: P3 2026-11-05 — WP-1944 closed, so nothing blocks it; three opt-in corrections are documented without the declaration a user writes, and nothing is wrong in any number

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
  is a reader-output change this rescope does not make.

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
lacks, both ways. A retired spelling keeps priority. The change is to
error and warning text, which is reader output, so the maintainer reviews
the before and after texts in the PR body before merge.

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
