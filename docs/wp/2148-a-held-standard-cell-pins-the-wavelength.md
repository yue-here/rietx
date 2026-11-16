# WP-2148 — A held standard's cell pins the wavelength, and a skipped λ is said

Milestone: unscheduled · Status: 🔄 2026-11-16 — claimed by @mustachefeeling
Track: What fires, and what stays silent
Depends on: —
Priority: P2 2026-11-15 — a silent wrong answer on a path few fits run (a standard-plus-sample wavelength calibration freed in one stage: λ is dropped, the sample cell takes its error at −496 ppm, z −109, and the fit reports converged), plus a false refusal of the same calibration staged apart

## Goal

A constant-wavelength fit refines λ beside a free sample cell whenever a
phase with a held cell is in the pattern, in one histogram or in a joint
fit. A stage whose glob would free λ and cannot says so in its result.

## Context

**The physics.** A powder pattern measures d = λ/(2 sin θ), so for one
phase λ and the cell trade exactly. Any phase whose cell is held pins the d
scale for the whole histogram. λ is then measurable, and every other phase's
cell refines against it. That is how a wavelength is calibrated against a
certified standard in a mixture. The fence already admits the single-phase
case (`tests/test_wavelength_freedom.py`,
`test_a_held_cell_makes_the_wavelength_measurable`), and its refusal text
already says "Hold the cell (what a certified standard is for, and how a
wavelength is calibrated)".

**What the tree does, checked at `98d7ba8e3`** (a table-level script: two
cubic phases, phase 0's cell held, phase 1's free, one histogram):
- `ParameterTable.check_wavelength_against_cell` (`params/vector.py:3028`)
  refuses a free λ whenever any cell length is free. With phase 0 held and
  phase 1 free it raises, naming `phases.1.cell.a`, the sample's cell.
- `set_vary(["phases.1.cell.a", λ], True)` returns only the cell. The skip
  (`params/vector.py:3984`, through `_cell_is_free`, `:4044`) asks whether
  any cell is free. It does not ask whether a held cell pins the scale.
- The joint check `params.vector.check_wavelength_freedom` (`:133`, called
  from `MultiParameterTable`) counts wavelengths: all N free is refused, even
  when a held standard cell in the shared structure pins every histogram.

**Measured by the reporter** (issue #1550, `origin/main` `a23d06e14`, a
synthetic Debye-Scherrer pattern of Si held at its certificate plus CeO₂
free, λ planted 500 ppm high, the refusal bypassed in-process):
- One histogram, λ freed in its own stage: λ lands 0.92 esd from the
  planted value and CeO₂ a 0.98 esd from its truth, GoF 1.013.
- Two histograms, both λ free: each within 1.15 esd, GoF 1.017.
- One stage freeing CeO₂ a and λ together, on `main`: λ is skipped with no
  message, CeO₂ a comes back 496 ppm low (z −109), GoF 17.9, status
  `converged`, and no diagnostic names the skipped λ.
- The genuinely flat case, the Si cell freed as well: λ's esd is 360-870×
  the held-standard case's, pairwise ρ = +1.000 and `FLAT_DIRECTION` fires.
  So the data separate the two cases by about three orders of magnitude in
  the esd, and the fence must keep refusing the second.
- One more defect under the bypass: `WAVELENGTH_CALIBRATION` says "The shift
  is taken against the held cell" where no cell is held.

**The TOF twin.** The reporter's fork fixed the same false refusal for bank
DIFCs (`mustachefeeling/rietx` commit `b9212ec20`, branch
`pr/tof-t5-20261106`, no PR on 2026-11-15; T-5 is fenced at ROADMAP § v2+).
Its `params.multi.check_calibration_freedom` treats a bank's scale as
pinned when its DIFC is held or a phase present in it has a held cell, links
each free DIFC to the free cells of the phases in its bank, and refuses by
name a linked set that reaches no pin. Under that rule λ plays DIFC's part,
and the single-histogram check and the joint N − 1 count become two cases of
one connectivity rule. Read it as prior art: the fork's code is the
reporter's, and a shared rule is worth having only if T-5 lands with it.

**Which phase is "present".** A phase pins the scale only if the data see
it. A held cell of a phase the data cannot see (WP-1301's absent-phase
hold, scale under 3σ of its esd) pins nothing. The rule needs the phase's
support, read where WP-1301 reads it. Measure what a held but unseen
standard does before deciding.

**Two consumers, one answer.** The refusal at the solve and the glob skip in
`set_vary` answer one question, so they must read one predicate. Otherwise
the silent variant stays. `set_vary` can already decline a row
(`StageResult.blocked_by_hold`, `HOLD_BLOCKED_PLAN` for a caller's hold,
WP-1435). A λ declined by the fence needs the same kind of record. Whether
it reuses that record or gets its own is this WP's call.

**Tier.** The pin rule is physics (Bragg's law). The skip report is
bookkeeping of an action the package took (DESIGN.md § Rules, rule 1: act
and record it in a field). A new diagnostic code or record field needs its
`rietx._audit` row, and its text is reader output for the maintainer before
merge.

### Inherited

## Non-goals

- TOF DIFC freedom (T-5, fenced). Note here if the rule is written so T-5
  can share it.
- Refining a wavelength without any held cell or held λ: still a flat
  direction, still refused.

## Tasks

- [ ] One predicate: is this histogram's d scale pinned (a held λ, or a held
      cell of a phase the data support)? Read by `check_wavelength_against_cell`,
      the glob skip and the joint check.
- [ ] The joint fit: replace the N − 1 count by the pin rule over shared
      cells, keeping every case `test_wavelength_freedom.py` refuses today.
- [ ] A λ the fence declines in a stage is recorded on `StageResult` and
      reported, never dropped silently.
- [ ] `WAVELENGTH_CALIBRATION`'s text names what the shift is taken against.
- [ ] Tests: the reporter's arms A, B and the one-stage variant on a seeded
      synthetic pattern; the flat arms A0 and B0 still refused; a held but
      unsupported standard. Obs/calc/diff PNGs to `tests/output/`.
- [ ] `_audit` rows, `help.py` if a field is added, and the manual's
      wavelength-calibration text.
- [ ] Skill: the row keyed by `WAVELENGTH_CALIBRATION` or the fence's
      refusal, if one exists, says a held standard in the mixture is enough.

## Acceptance

Arm A (one histogram, Si held, CeO₂ and λ free) lands λ within 3 esd of the
planted value in both plan shapes. The flat arms are refused. No stage drops
λ without a record.

```sh
.venv/bin/python -m pytest tests/test_wavelength_freedom.py tests/test_acceptance_wavelength.py
.venv/bin/python -m pytest tests/test_audit_table.py
.venv/bin/python -m ruff check src tests examples
```

## References

- Issue #1550 (measurements and the reproducer's design).
- NIST SRM 640 series certificates (the Si cell); WP-1134 (refinable λ).

## Handover log

- **2026-11-15** — created, from the 2026-11-15 issue triage (issue #1550).
  Checked against the tree at `98d7ba8e3`: the refusal and the silent glob
  skip both reproduce at table level; the fit-level numbers are the
  reporter's and were not rerun. No open WP owns the wavelength fence:
  WP-1134, which built it, is closed, and the open wavelength WPs (2070,
  2056) concern neutron lines and low-angle asymmetry. Next: the predicate,
  then the record of a declined λ.
