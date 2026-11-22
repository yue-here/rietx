# WP-2152 — a peak equation reads the wavelength

Milestone: parametric · Status: 🔄 2026-11-22 — claimed by @yue-here
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
- [ ] Bring the warning's silence question to the maintainer with its options, or record
  that it was left firing.
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

- **2026-11-22** — Filed by the session closing WP-2107, from its handover's follow-on of
  the 2026-11-20 ruling. No open WP owns the peak equation's names: 1964 and 2107 are
  closed, and 2070 is a neutron line. Premises checked on main f590981ab:
  `REFLECTION_NAMES` has no λ, and no evaluation site passes one. Next: the binding.
