# WP-2087 — An opt-in correction the residual asks for names its declaration in the docs

Milestone: unscheduled · Status: 🔄 2026-11-09 — claimed by @yue-here (ghostshift runner)
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

**Waiting on the maintainer: the unknown-path error** (from WP-1944's
inherited entry). On a phase that declares no extinction,
`set_vary(["phases.0.extinction"], True)` raises "unknown parameter path
'phases.0.extinction'; did you mean 'phases.0.lor_strain'?" (measured by
WP-1944's code review). It is the one place the package meets a user who
already guessed the name. Having `refine._path_hint` name the declaration
for an opt-in path would fix it. That changes an error's text, which is
reader output, so it goes to the maintainer before it lands. This WP's
rescope does not cover it.

## Non-goals

- Extinction (WP-1944, done in its follow-up).
- Any new diagnostic code, report action, `ActionKind` member or audit row.
- Any change to what a fit prints or returns.
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

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_help.py tests/test_skill.py tests/test_skill_cli.py tests/test_manual.py
.venv/bin/python -m ruff check src tests examples
```

## Handover log

- **2026-11-05** — rescoped to documentation pointers only, by WP-1944's
  follow-up session under the maintainer's ruling of 2026-11-04 (quoted in
  Context). The three tasks that designed a diagnostic or an action are now
  help, manual and skill edits. Nothing run here. *Next:* the Stephens task.

- **2026-11-04** — filed by WP-1944's runner from its opt-in sweep. Nothing
  run here. *Next:* the Stephens task.
