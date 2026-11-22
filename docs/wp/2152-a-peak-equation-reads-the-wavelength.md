# WP-2152 — a peak equation reads the wavelength

Milestone: parametric · Status: 🔄 2026-11-22 — built (PR #1785); one question for the maintainer, the warning on an equation reading wavelength
Depends on: —
Priority: P3 2026-11-22 — a workaround covers it: a per-pattern coefficient through `SharingMap(per_histogram=[...])`, which the warning already names

## Goal

A peak equation can read `wavelength`, the emission line's λ in Å. A size-like width term
is then written once, with its λ dependence in the text, for patterns at several
wavelengths.

## Context

WP-2107 built peak equations (`rx.PeakEquation`, `Phase.peak_equations`,
`Instrument.peak_equations`). An equation reads the reflection's `h`, `k`, `l`, `m`, `d`,
`theta` (radians) and `two_theta` (degrees, before the phase's equations act). It cannot
read λ.

**Why it matters.** A crystallite-size width goes as (180/π)·K·λ/(L·cosθ), so its
coefficient in degrees differs between wavelengths. A strain width does not. The package
already shares the size across wavelengths for its built-in terms
(`params.multi.SIZE_LAMBDA_POWER`, root CLAUDE.md, WP-1131). A peak equation's
coefficient has no such factor, so a joint fit at two wavelengths shares it in degrees.

**The ruling this serves.** On 2026-11-20 the maintainer ruled on that case (WP-2107's
handover, review finding 1, option a). A joint fit warns and converts nothing.
`PEAK_EQUATION_SHARED_ACROSS_WAVELENGTHS` (`multi._peak_equation_sharing_diagnostics`)
fires once per equation whose degree-valued coefficients are one column across patterns
declaring two or more wavelengths. It names the `SharingMap(per_histogram=[...])` glob
that unshares them. The guide's practice line says TOPAS writes such a term per pattern,
or with `Lam` in the expression (`docs/docs/guides/peak_equation.md`). This WP builds the
second spelling on rietx's own terms. TOPAS's `Lam` is no alias: the 2026-11-04 ruling
takes no TOPAS spelling as one.

**The name.** `wavelength`, the field's own name on `EmissionLine` and in `help.py`.
`lambda` is a Python keyword, and `lam` is TOPAS's spelling.

**The seams.**

- `schemas/peak_equation.py`: `REFLECTION_NAMES` (line 51) and `INSTRUMENT_NAMES`
  (line 53). An instrument-level `shift` equation may read it too. `CONDITION_NAMES`
  stays the frozen integers, so a condition on `wavelength` is refused as a moving
  condition. A coefficient may not take a reflection name (WP-2107 consent item 3), so a
  stored equation with a coefficient named `wavelength` would stop reading. Grep the
  tests and examples for one before adding the name.
- `model/peak_equations.py`: `ReflectionFrame.bindings`, `image_bindings` and
  `evaluate_angle` bind the names. Each call site passes the line's λ:
  `model/forward.py` lines 1285, 1474, 1603, 4668, 4727 and 4919 (main f590981ab). An
  equation is evaluated per emission line, so each line binds its own λ.
- λ is a table entry (`instrument.source.lines.N.wavelength`, WP-1134) and can refine. The
  equation reads it from `values`, never from a frozen copy, so a free λ moves the
  equation's term. A wavelength column takes the scalar chain
  (`least_squares.py` near line 176), which finite-differences through `decode`. So the
  column stays whole, and `tests/test_cross_backend.py` needs a row with λ free and an
  equation reading `wavelength` to prove it.
- `PEAK_EQUATION_SHARED_ACROSS_WAVELENGTHS` keeps firing on an equation that reads
  `wavelength`, unless the maintainer extends its silence list. That list is the
  2026-11-20 ruling's ("silent with one wavelength, an unshared or parametric coefficient,
  or an `intensity_factor`"), so adding a case amends a ruling and goes to the maintainer.
  An equation reading `wavelength` may still carry a coefficient that belongs per
  wavelength, so the case is a judgement.
- Versions. `params/expression.py` says `GRAMMAR_VERSION` moves on "a change to what any
  expression means, or to what is accepted". The reflection names are the peak equation's
  vocabulary, not the grammar's, so the version that moves is a call for this WP to make
  and record. `SCHEMA_VERSION` (`schemas/common.py`) is 0.62 today. A 0.62 build reading a
  stored equation that uses `wavelength` refuses it as an unknown name.
- Surfaces that list the names: `help.py`'s two `peak_equations` families, the guide's
  line 53, `reference/data.md`, the Theory tab's `fm-peak-equation`
  (`theory/forward-model.md`), the guide's practice paragraph, and the skill's row.

**Tier.** Physics: a size width's λ dependence is Scherrer's. No threshold is added.

## Non-goals

- Converting a shared coefficient between wavelengths. The 2026-11-20 ruling chose a
  warning.
- An equation in d on a time-of-flight bank, which stays refused by name.
- Any other TOPAS reserved name.

## Tasks

- [x] Bind `wavelength` at every evaluation site, per emission line, read from `values`.
  Bound in one place, `ReflectionFrame.bindings`, as 2·d·sinθ off the line's Bragg
  angle, so every phase site has it with no λ passed. The instrument level refuses
  it (handover 2026-11-22).
- [x] Refuse a condition on it, with the existing moving-condition message.
- [x] A test: a size term written as `y*wavelength/cos(theta)` on two patterns at two
  wavelengths, one shared coefficient, against the built-in `lor_size` twin to 1e-12
  relative. A second test with λ free.
- [x] `tests/test_cross_backend.py`: the λ-free row (`peak_equations_wavelength`).
- [x] Record which version moves, with its reason. Bump it. The schema's: an "Also in
  0.62" note in `docs/contracts/schema.md`, and no new number, since 0.62 is unreleased
  (the rule above `SCHEMA_VERSION`). `GRAMMAR_VERSION` stays 2: the grammar parses any
  name, and the names are the schema's. Settled by Claude under those two written rules.
- [x] Bring the warning's silence question to the maintainer with its options, or record
  that it was left firing. Left firing, unchanged, and brought as a brief in the
  2026-11-22 handover entry.
- [x] Manual: the guide's name list and practice paragraph, `reference/data.md`, the
  Theory equation. Help entries. Skill row. Also `switching/topas.md`'s name table
  (`Lam` → `wavelength`). The instrument help entry is unchanged, since it cannot read λ.

## Acceptance

The two-wavelength twin matches to 1e-12 relative, and the λ-free row agrees on every
backend.

```sh
.venv/bin/python -m pytest tests/test_peak_equations.py tests/test_cross_backend.py tests/test_help.py tests/test_manual_api.py
.venv/bin/python -m ruff check src tests examples
```

## References

- Scherrer, P. (1918). *Nachr. Ges. Wiss. Göttingen, Math.-Phys. Kl.* 1918, 98-100.
- TOPAS Technical Reference v8, Table 2-3 (`Lam`).
- WP-2107 (peak equations and the 2026-11-20 ruling), WP-1131 (the size across
  wavelengths), WP-1134 (λ a table entry).

## Handover log

- **2026-11-22** — Ghostshift runner, PR #1785. A phase's peak equation can now read
  `wavelength`, the λ in Å of the emission line each peak is drawn at. A size width is
  written once, as `y*wavelength/cos(theta)`, with one shared `y` for patterns at several
  wavelengths. On two single-line patterns at 0.4139 and 0.7107 Å it reproduces the
  built-in `lor_size`, which the joint table converts by λ_h/λ_0, to 1e-12 relative.
  The instrument's equation cannot read it. One question waits on the maintainer: whether
  the shared-across-wavelengths warning should stay quiet on such an equation. It still
  fires, unchanged.

  *Done.* The name binds in one place, `ReflectionFrame.bindings`, as 2·d·sinθ off the
  Bragg angle the caller passes. Every phase evaluation site (the forward width, shift and
  intensity terms, the exact coefficient columns, the orbit check and the compile's window
  sizing) holds one line's Bragg angles, which `two_theta_deg` took off that line's λ in
  `values`. So the binding is that λ to rounding, it follows a refined λ, and no call site
  carries the line index. It is computed only for a phase whose equations read it
  (`ReflectionFrame.wavelength`). A condition on it is refused by the existing
  moving-condition rule. A coefficient named `wavelength` is now refused as the
  reflection's name; no test, example or fixture declared one. Tests: the two-wavelength
  twin, a free-λ twin (pattern 1's λ moved 1 % in its values, against `lor_size` at the
  moved share on the same compiled model), and the refusals. Cross-backend row
  `peak_equations_wavelength`: LaB6, λ free beside a `lor_fwhm` and a `shift` equation
  reading it. Versions: an "Also in 0.62" note in `docs/contracts/schema.md`, no new
  number. Manual, help, the TOPAS name table and the skill row name it.

  *Measured* (`[dev,jax,torch]` venv, macOS arm64). Twin: 3.6e-16 relative on one
  pattern, under 1e-12 on both patterns of the joint table. Cross-backend
  `-k peak_equations`: 14 passed, 2 skipped (no axial columns in either config, the
  existing skip). A mutation that froze the binding at 1.5406 Å still passed the
  cross-backend row, as expected: every method there differentiates the same residual.
  The free-λ twin is the test that catches a frozen λ. Fast selection (`-m "not slow"`,
  same venv, on main 8fec2ea18 merged): 15556 passed, 65 skipped, 32 xfailed, in
  11 min 11 s beside other runners. The branch adds 12 cases: 5 in
  `test_peak_equations.py` (two tests, three refusal rows) and 7 cross-backend rows, of
  which 1 is the existing axial skip. No base run was made, so the delta is counted from
  the diff, not measured. The two added tests cost 0.21 s and 0.14 s (local junit).
  The full suite did not run: no number a golden pins can move, since the binding is
  computed only for an equation that reads `wavelength`.

  *Gotchas.* (1) Within one pattern with Kα1 and Kα2, an equation reading `wavelength`
  widens the Kα2 image's size term by λ2/λ1, about 0.25 %. The built-in `lor_size` gives
  both lines one width in degrees. On Cu Kα the two differ by 7.9e-4 of the peak height
  (brucite, `lor_size` 0.05). Per-line Scherrer is the physics; whether the built-in size
  terms should follow it is a default for every user, so it is not changed here and not
  filed. (2) `report/strain.py` takes θ off the compile-time λ (`model.line_wavelengths`)
  through a clipped arcsin, so its λ binding is the compile-time λ too. That predates this
  branch and changes that report's numbers on a fit with λ refined; left for an owner.
  (3) A joint fit's twin must compile each pattern from `MultiParameterTable.structures`,
  as `multi.py` does. Compiled from the shared structure, `lor_size`'s windows are sized
  at histogram 0's value and the twin misses by 1e-5.

  *Review* (`/code-review high --fix`, six findings). Accepted: the code's help entry now
  names the `wavelength` route and says the warning still fires; `ReflectionFrame.at`
  uses `dataclasses.replace`. Declined: the same wording in the warning's own suggestion
  and its "in degrees" unit (both belong to the question below), and the strain report's
  stale λ (Gotcha 2). The review's note that the instrument refusal departs from this
  WP's Context is answered under *Settled*.

  *Generality.* Not dispatched: `_audit.py` is untouched and the branch adds no flag,
  threshold or automatic action. The instrument refusal is a rule about where λ exists.

  *Settled by Claude.* (1) The instrument level refuses `wavelength`, where the Context
  said it "may read it too". Grounds: its shift is also evaluated on `generation_window`'s
  2θ grid and at the satellite report's lattice positions, which belong to no emission
  line, so λ has no value there. A λ-dependent shift on every phase is written on each
  phase. (2) λ is recovered as 2·d·sinθ in the frame rather than passed by each of the
  six call sites. Grounds: one site instead of six, the same values, and the smallest
  change; the WP's sketch passed it explicitly. (3) Versions: the schema note sits under
  0.62 and `GRAMMAR_VERSION` stays 2, under the rule above `SCHEMA_VERSION` and the
  docstring of `GRAMMAR_VERSION`. The grammar parses any name; the names a peak equation
  binds belong to the schema, as WP-2107 split them.

  *For the maintainer: the warning on an equation that reads `wavelength`.*

  1. **The decision.** Should `PEAK_EQUATION_SHARED_ACROSS_WAVELENGTHS` stay quiet when
     the equation reads `wavelength`? Trigger: it amends your 2026-11-20 ruling's list of
     cases where the warning is silent.
  2. **Why it matters.** In a joint fit of patterns at different wavelengths, a peak
     equation's coefficient is shared by default. The warning fires once per equation
     whose shared coefficient is in degrees, because a size term in degrees needs a
     different value at each wavelength. Your ruling made it silent for one wavelength,
     an unshared coefficient, a parametric coefficient and an intensity factor. Today a
     user who writes the λ in fits correctly and still sees, for 0.4139 and 0.7107 Å:
     "Phase 0 (brucite)'s peak equation lor_fwhm = y*wavelength/cos(theta)
     (phases.0.peak_equations.0) shares its coefficient y in degrees across patterns at
     λ = 0.4139-0.7107 Å." The suggestion then says to give each pattern its own `y`. An
     agent that follows it fits two sizes where the specimen has one. Only joint fits at
     two or more wavelengths with a peak equation meet it. Importance: minor.
  3. **Aim.** Expert builders porting a TOPAS joint fit, for whom a warning on a correct
     model is noise and its suggestion is wrong advice.
  4. **Options.**
     - (a) Do nothing. The warning fires on every shared coefficient in degrees. The code's
       help entry already says it still fires on a λ-reading equation. No code. Undoable.
     - (b) Silent when the expression reads `wavelength`. The case above prints nothing. A
       mixed equation such as `y*wavelength/cos(theta) + x/cos(theta)` also goes silent,
       although its `x` is a size term in degrees. About five lines in
       `multi._peak_equation_sharing_diagnostics`, plus a test row. Undoable.
     - (c) Silent per coefficient: warn only on coefficients not multiplied by
       `wavelength`. The mixed case still warns on `x` alone. Needs an expression walk or
       a derivative test at two λ values, which is a new rule to maintain for a rare case.
     - (d) Keep firing, and change the text for a λ-reading equation: drop "in degrees"
       and name the `wavelength` route in the suggestion. A reader-output change, settled
       in its PR.
     Dropped: converting the coefficient between wavelengths, which your ruling declined.
  5. **Practice** (recall, not checked against the programs' docs). TOPAS evaluates `Lam`
     in a peak's equation and warns about nothing; the user owns the λ dependence. GSAS-II
     has no user peak equations, and its size is a physical length per phase and
     histogram, converted to degrees internally. rietx's own built-in size terms are
     converted silently (`SIZE_LAMBDA_POWER`), so the package acts where the physics is
     stated.
  6. **Recommendation.** (b), a lean. The crux is whether writing `wavelength` states
     the λ dependence the way a parametric coefficient does. Your ruling warned because
     "the package cannot tell which kind the user wrote", and here the user wrote it.
     (c) loses on cost: a new analysis to catch a mixed equation nobody has been seen to
     write. (d) keeps a warning on a correct model, so every such fit carries a warning
     with nothing to act on. Seeing mixed equations in real ports would flip the pick
     to (c).

  Next: (1) the maintainer answers the question above; (b) or (d) is a small follow-up on
  this WP, (a) closes it. (2) The strain report's stale λ (Gotcha 2) and the per-line
  size width (Gotcha 1) need an owner if either is wanted.

- **2026-11-22** — Filed by the session closing WP-2107, from its handover's follow-on of
  the 2026-11-20 ruling. No open WP owns the peak equation's names: 1964 and 2107 are
  closed, and 2070 is a neutron line. Premises checked on main f590981ab:
  `REFLECTION_NAMES` has no λ, and no evaluation site passes one. Next: the binding.
