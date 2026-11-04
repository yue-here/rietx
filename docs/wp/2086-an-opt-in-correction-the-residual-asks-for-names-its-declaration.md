# WP-2086 — An opt-in correction the residual asks for names its declaration

Milestone: unscheduled · Status: ⬜
Track: What fires, and what stays silent
Depends on: [1944](1944-the-structural-plan-frees-extinction-only-where-declared.md)
Priority: P3 2026-11-04 — three opt-in corrections have no evidence-gated pointer, so a user who never declares them is never told the fit wanted them; nothing is wrong in any number

## Goal

Each opt-in correction that a fit's residual can give evidence for has a
diagnostic or report action that fires on that evidence and names the
declaration a user writes. None fires as a standing reminder.

## Context

**From WP-1944's sweep** (the maintainer's ruling of 2026-11-03: "check this
for extinction and any other opt-in features"). WP-1944 added
`EXTINCTION_UNDECLARED` and named the declaration in two existing actions
(spherical-harmonics texture, a hump). The sweep table is in WP-1944's
handover log. Three gaps there need design, so they come here.

- **Stephens anisotropic microstrain** (`Phase.microstrain`). The report
  already computes `FitReport.strain` (`report/strain.py`, `StrainAnalysis`:
  `detected`, `anisotropy`, the broadest and narrowest hkl). No action,
  diagnostic or summary line reads it. `ActionKind` has no kind for declaring
  the block. The design question is a new `ActionKind` member (its writer is
  `strain_actions`, modelled on `texture_actions`), its confidence, and its
  audit row.
- **Anisotropic ADPs** (`Atom.aniso`). No evidence source exists. The
  isotropic `refine_biso` template cannot see anisotropy. A powder fit rarely
  determines it, so the first question is whether any residual signature is
  worth a pointer at all.
- **Surface roughness and specimen absorption.** `BISO_NEGATIVE` and
  `BISO_UNUSUALLY_LARGE` name "uncorrected absorption or roughness" in prose
  and no declaration. Naming one needs the geometry at the raise site
  (`_guard_diagnostics` takes the guard alone today), because roughness is a
  Bragg-Brentano correction and µR a capillary one (root CLAUDE.md: a
  correction belongs to a geometry, and so does the action naming it).
  Absorption is an exact reparameterisation of scale and Biso on a capillary,
  so there is no residual signature beyond the Biso anomaly itself.

## Non-goals

- Extinction (WP-1944).
- Freeing any of these by default.

## Tasks

- [ ] Stephens: an action from `FitReport.strain` naming
      `Phase.microstrain = StephensStrain.isotropic(...)`, with its audit row.
- [ ] Biso anomalies: pass the geometry to the raise site and name the
      declaration that geometry takes.
- [ ] Anisotropic ADPs: measure whether any residual signature separates an
      anisotropic site on a fixture with one planted; record the answer, and
      add a pointer only if it does.
- [ ] Skill: a row per new code or action in the diagnostics reference.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_audit_table.py tests/test_help.py tests/test_fitreport_layers.py
.venv/bin/python -m ruff check src tests examples
```

## Handover log

- **2026-11-04** — filed by WP-1944's runner from its opt-in sweep. Nothing
  run here. *Next:* the Stephens task.
