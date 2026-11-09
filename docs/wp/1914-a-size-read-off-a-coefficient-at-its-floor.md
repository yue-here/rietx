# WP-1914 — a size read off a coefficient at its floor

Milestone: unscheduled · Status: ✅ 2026-11-09 — a width on its floor reads at_zero under either driver
Track: What fires, and what stays silent
Depends on: —

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
- [x] Find the siblings: every other consumer that tests a softplus coefficient
  with `> 0` (the size flags in `refine._size_flag_diagnostics`,
  `SIZE_UNUSUALLY_SMALL`, the Stephens and extinction readers). Fix the class or
  say which were left and why.
  *Swept every `> 0.0`/`<= 0.0` test on a width, size, strain or extinction
  value under `src/rietx`. Only one other reader turns a floor into a
  statement:*
  - *`report/magnetic._width_support_findings` decides "this term sits on its
    zero floor" by `val <= _MAGNETIC_WIDTH_FLOOR_DEG` (1e-12), a proximity of
    its own rather than `FLOOR_HIT`. **Left**: it picks only which cause an
    info message names on a no-esd branch, and magnetic-path decisions are
    Mike's (#1075). Under the default LM driver a floored width is exactly
    0.0, so the two tests agree there.*
  - *Not siblings: `SIZE_UNUSUALLY_SMALL` fires on a size below 50 Å, so a
    floored coefficient (an enormous size) cannot trip it;
    `layer2._size_clause` reads a residual-trend template's coefficient, not a
    refined parameter; `CompiledPhase.skip_extinction` is a compile-time
    freeze under the `moving_paths` rule, not a reading; the Stephens block is
    held by a cone and read by `STEPHENS_STRAIN_NOT_POSITIVE`, and has no
    microstructure row (it replaces `lor_strain`).*
  - *`refine._extra_peak_diagnostics` decides `EXTRA_PEAK_NO_INTENSITY` by
    its own `BOUND_HIT_RTOL` proximity (1e-10 relative), where TRF stops
    1e-10 to 1.6e-6 inside a floor (`bound_findings`' docstring), so under
    TRF the warning can miss a binding area. **Left** (found by the
    review): a declared peak is not a microstructure reading, the fix
    changes when a warning fires, and the joint fit calls it per histogram
    before its bound test runs, so it needs a reorder there. No open WP owns
    extra peaks; the shift lead files it.*
  - *Generalised after the review of #1506: a width **tied** to a floored
    source, or driven by a floored `vars.X`, follows it to zero when its tie
    has no constant (`microstructure.floored_paths`); and `replay`, which runs
    no bound test, reads the recorded `FLOOR_HIT` diagnostics, as
    `cell_runaway` already falls back.*
- [x] Rebuild WP-1545's notebook 04 and update its prose if the Gaussian rows
  now read as absent.
  *Nothing to rebuild: the notebook runs the default LM driver, whose
  Gaussian rows already land on 0.0 and read `at_zero` (its stored output
  says so, and its prose already reads "Their coefficients are at zero").
  The manual's absences table (`reference/derived.md`) gains the floor case.*

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_microstructure.py tests/test_tutorials.py -q
```

## Handover log

- **2026-11-09** — closed by a ghostshift runner (PR #1506). A width the fit
  drives to zero now reads as "no broadening" in `result.microstructure`
  under either solver. The default solver already landed such a width exactly
  on zero, so notebook 04 and every default fit read the same as before. The
  alternative solver (`solver="trf"`) stopped a hair above zero, and the table
  turned that into a domain size of 4×10¹³ Å and a size ratio of 10¹¹. The
  fix reads the package's one bound test, so the table, the `FLOOR_HIT`
  warning and the parameter rows' `at_bound` flag can no longer disagree.
  - *Done.* `microstructure_table(floors=)` reads a path in the `FLOOR_HIT`
    set as `at_zero` whatever it stores. `refine._build_result` passes the
    answer stage's findings; `multi._hist0_floors` translates the joint
    spelling for histogram 0. `at_zero` is reused, so no vocabulary member is
    new. The schema docstring and the manual's absences table
    (`reference/derived.md`) name the floor case.
  - *Measured* (macOS arm64, `[dev]`, notebook 04's CeO₂, before → after):
    TRF `gauss_size` 3.4×10⁻²⁴ deg² read 4.3×10¹³ Å ± 4.6×10³³ →
    `at_zero`; `size_agreement` 1.4×10¹¹ → `None`; `strain_agreement`
    5.4×10⁻⁵ → `None`. LM rows and the uncalibrated fit (no floor) are
    unchanged to every printed digit. `tests.reader_output` exit 0
    (unchanged). Four tests added in `tests/test_microstructure.py`: the
    floor set from both sides, the joint spelling, the tie closure, and an
    end-to-end LaB6 fit and its replay under both drivers. All four pass,
    1.01 s together locally (the end-to-end row; one run, so a rank and not a
    time). Gates on the final tree (macOS arm64, worktree `[dev]`): fast
    selection 14344 passed, 417 skipped, 32 xfailed in 7:28, alone on the
    machine through ghostshift's serial lock; acceptance command 86 passed;
    `test_docs_consistency.py` 25 passed; ruff clean. Full selection not run:
    the acceptance suites run the default LM driver, whose floored widths are
    stored as 0.0 and read the same before and after. No audit-table row and
    no new heuristic, so no generality judge.
  - *Settled by Claude* under the maintainer's 2026-10-09 ruling ("read the
    flag"): the floor is `FLOOR_HIT`, not an esd-over-value significance test.
    The alternative would also blank the uncalibrated fit's `gauss_size`
    (6020 Å ± 12 350, off its floor), which notebook 04 teaches from, and
    WP-1944 keeps a general esd-over-value rule out of scope.
  - *Review* (`/code-review high --fix`, eight findings). Applied: the
    floor set built beside `on_bound`, `_hist0_floors` through `_unscoped`,
    the tie closure, the `replay` fallback (a mutation that drops it fails
    the end-to-end test on TRF's `gauss_strain`, 2.9×10⁻¹⁹), the
    `_at_zero_floor` wording (a caller's floor under 1e-8 also reads as no
    broadening), and the end-to-end test now pins only the decision, never
    where TRF stops. Declined: a shared helper for the `"FLOOR_HIT"` literal
    (two readers, both beside the findings they filter).
  - *Left.* `report/magnetic._width_support_findings`'s 1e-12 proximity floor
    (Mike's path, #1075) and `EXTRA_PEAK_NO_INTENSITY`'s proximity test (no
    owner; the shift lead files it). Both are in the task notes above.
  - *Next:* none in this WP.

- **2026-10-07** — filed from WP-1545. No open WP owns the microstructure
  report: 1131 and 1336, which built it, are closed, and 1467 is about the
  Stephens block's floor during the solve, not about reading a coefficient after.
