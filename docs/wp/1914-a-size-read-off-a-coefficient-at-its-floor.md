# WP-1914 — a size read off a coefficient at its floor

Milestone: unscheduled · Status: 🔄 2026-11-09 — claimed by @yue-here (ghostshift runner)
Track: What fires, and what stays silent
Depends on: —
Priority: P3 2026-10-07 — a derived number that reads as a finding on every lab_sample_refine fit of a purely Lorentzian specimen; the reading's own esd flags it, the agreement ratio beside it does not

## Goal

A sample-broadening coefficient that the fit drove to its softplus floor reads
as absent in `result.microstructure`, the way one at exactly zero already does.
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

### Inherited

- **2026-10-09, from WP-1929 (2nd session): a floor becomes an ordinary
  bound, and the driver says which rows sit on it.** Decided by the
  maintainer: WP-1938 refines every parameter in physical units with native
  bounds, so a coefficient at its floor is at its `min`, with no tiny
  positive softplus value to interpret. WP-1937 exposes the driver's exact
  active set on `LSQOutcome`, and WP-1929 keys `at_bound` on it. A row on its
  bound keeps its value and its marginal esd, flagged. So this WP's first
  task becomes "read the flag", and it waits on 1937-1938. `bound_untested`,
  the test the earlier entry named, is deleted by 1938.

## Tasks

- [ ] Decide what "at its floor" means for a softplus coefficient: an internal
  coordinate past where `log(1+eᵘ)` is indistinguishable from zero, or a reading
  whose esd exceeds its value (a significance test, as WP-1523 did for a phase
  scale). Name the threshold's source in its docstring.
- [ ] Apply it in `_reading`, reusing `at_zero` or a new absence name, and keep
  `_agreement` from reading an absent term.
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
