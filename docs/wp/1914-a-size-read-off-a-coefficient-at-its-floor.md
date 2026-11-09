# WP-1914 — a size read off a coefficient at its floor

Milestone: unscheduled · Status: 🔄 2026-11-09 — claimed by @yue-here (ghostshift runner)
Track: What fires, and what stays silent
Depends on: —
Priority: P3 2026-10-07 — a derived number that reads as a finding on every lab_sample_refine fit of a purely Lorentzian specimen; the reading's own esd flags it, the agreement ratio beside it does not

## Goal

A sample-broadening coefficient that the fit drove to its floor of zero reads
as absent in `result.microstructure`, the way one at exactly zero already does,
whichever driver solved it.
The size and strain agreement ratios are then not computed from it.

## Context

**Found while building WP-1545's notebook 04** (2026-10-07, macOS arm64,
`[dev]`). A synthetic CeO₂ pattern with a known Lorentzian size of 300 Å and
strain of 1.0×10⁻³ and no Gaussian specimen broadening, fitted with
`lab_sample_refine` against a calibrated instrument. The fit drives
`phases.0.gauss_size` to 2.5×10⁻¹³, and `result.microstructure[0]` reports:

| term | coefficient | value | esd | unavailable |
|---|---|---|---|---|
| `lor_size` | 0.2664 | 298.9 Å | 1.2 Å | — |
| `gauss_size` | 2.5×10⁻¹³ | 1.59×10⁸ Å | 3.5×10¹⁶ Å | **None** |
| `lor_strain` | 0.1106 | 9.65×10⁻⁴ | 2.4×10⁻⁵ | — |
| `gauss_strain` | 2.2×10⁻¹⁷ | 4.1×10⁻¹¹ | — | `not_measured` |

and `size_agreement = 532 341`, `strain_agreement = 4.3×10⁻⁸`.

**Why.** `model/microstructure._reading` returns `at_zero` only when
`not coefficient > 0.0`. A softplus entry with `min=0.0` never reaches exactly
zero while the solver can still move it (root CLAUDE.md, the softplus clause),
so a coefficient the data wants at zero arrives as a tiny positive number and
reads as a measurement. `gauss_strain` escaped only because its column measured
nothing and `ParameterTable.stderr_physical` omitted its esd. The agreement
ratios (`_agreement`) then compare a real reading against this one.

**Reproduce.** `examples/tutorials/04_peak_shape_and_microstructure.py`
(WP-1545) prints the table above in its "Measure the sample" cell. The
notebook reads the rows with their esds and does not print the ratios.

**Superseded in part (2026-11-09, re-measured at `eee8486d5`, macOS arm64,
`[dev]`).** The softplus transform is gone (WP-1938): every coefficient
refines in its own units with `min=0.0` as a box bound. WP-1929 then keyed
`at_bound` on the LM driver's exact active set, and the maintainer decided
(2026-10-09, folded in from `### Inherited`) that this WP's first task
becomes "read the flag". Re-run on notebook 04's CeO₂ pattern:

| driver | `gauss_size` coefficient | reading | `size_agreement` | `at_bound` |
|---|---|---|---|---|
| `lm` (default) | 0.0 | `at_zero` | `None` | True (`FLOOR_HIT`) |
| `trf` | 3.4×10⁻²⁴ | 4.3×10¹³ Å ± 4.6×10³³ | 1.4×10¹¹ | True (`FLOOR_HIT`) |

`gauss_strain` behaves the same way (LM 0.0 → `at_zero`; TRF 3.8×10⁻¹¹ →
5.4×10⁻⁸ ± 2.5, `strain_agreement` 5.4×10⁻⁵). So the default driver already
lands the coefficient exactly on its floor and the table reads it absent. The
defect survives under `solver="trf"`, which keeps its iterates strictly
inside the box. The definition is therefore the bound test's own answer,
`FLOOR_HIT`, read through `staged.bound_findings`. The significance
alternative (esd over value) is not the floor question: the uncalibrated fit's
`gauss_size` reads 6020 Å ± 12350 off its floor, and WP-1944 keeps a general
"esd exceeds value" rule out of scope.

The tier of the rule this WP adds: **physics**, no new threshold. A
coefficient on its zero floor is a width the data put at zero, and the test
that says so is `staged.bound_findings`, which already feeds `FLOOR_HIT` and
`at_bound` (WP-1929). The reading becomes a third projection of it. Kind of
ambiguity (DESIGN § Rules, 1): none — every competent refiner reads a width at
zero as no broadening.

## Tasks

- [x] Decide what "at its floor" means for a softplus coefficient: an internal
  coordinate past where `log(1+eᵘ)` is indistinguishable from zero, or a reading
  whose esd exceeds its value (a significance test, as WP-1523 did for a phase
  scale). Name the threshold's source in its docstring.
  *Settled (2026-11-09) on the maintainer's 2026-10-09 ruling ("read the
  flag"): the bound test's `FLOOR_HIT`, no threshold of this module's own.*
- [x] Apply it in `_reading`, reusing `at_zero` or a new absence name, and keep
  `_agreement` from reading an absent term.
  *`microstructure_table(floors=)` from `refine._build_result` and
  `multi._hist0_floors`; `at_zero` reused, so no vocabulary member is new.*
- [ ] Find the siblings: every other consumer that tests a softplus coefficient
  with `> 0` (the size flags in `refine._size_flag_diagnostics`,
  `SIZE_UNUSUALLY_SMALL`, the Stephens and extinction readers). Fix the class or
  say which were left and why.
- [ ] Rebuild WP-1545's notebook 04 and update its prose if the Gaussian rows
  now read as absent.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_microstructure.py tests/test_tutorials.py -q
```

## Handover log

- **2026-10-07** — filed from WP-1545. No open WP owns the microstructure
  report: 1131 and 1336, which built it, are closed, and 1467 is about the
  Stephens block's floor during the solve, not about reading a coefficient after.
