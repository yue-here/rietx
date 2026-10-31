# WP-2070 — A second CW neutron line that is not a harmonic, with its own weight and offset

Milestone: unscheduled · Status: ⬜
Track: The specimen is not an angle, and the neutron follow-through
Depends on: —
Priority: P3 2026-10-31 — a workaround covers it (a second `Refinement` summed in an external optimiser, which loses joint, parametric and report support); kept at P3 rather than down a rung because the one open decision, schema (a) or (b), is a single question and the contributor is waiting to build it

## Goal

A constant-wavelength neutron instrument can declare a second line at λ₂ = λ₀·ratio
(not λ₀/n), with a weight and a constant angular offset of its own. A pattern carrying
such a component fits natively, in single, joint (`MultiHistogramRefinement`) and
sequential fits, and the report layers see it. With no line declared, every number is
bit-identical to today.

## Context

**Source.** Issue #1208 (2026-10-28, @mustachefeeling). Some CW neutron diffractometers
put a second, weaker component on the high-angle side of every reflection, the
calibrant's included: a second monochromator block or a second beam direction. It
displaces by Δ2θ = 2ε·tanθ + c, with λ₂ = λ₁(1 + ε) and c a constant offset, at relative
intensity r up to a large fraction of the main line. #1201 (the agent reads the
instrument's documentation first) lists this component among its late findings; that
issue is placed in WP-2008.

**What the tree has** (checked at `d87c8cc91` by the issue triage):
- `Harmonic` (`schemas/instrument.py:120`) has `order: int = Field(ge=2)` and `weight`;
  `Harmonic(order=1/1.005)` is refused. `NeutronSource` has `kind`, `wavelength`,
  `harmonics` and forbids extra fields, so `lines=` and `extra_lines=` are both refused.
- No per-line angular offset exists anywhere. A tied "ghost" phase (cell a/(1+ε),
  scale r × main, Biso tied) fits only at c = 0 with ε and r known, and adds a fictitious
  phase to the fractions.
- The GSAS readers refuse a CW neutron file that states a second wavelength: GSAS-I
  `ICONS` `LAM2` (`io/instrument_profile.py:590`) and GSAS-II `Lam1`/`Lam2` on `PNC`,
  because `NeutronSource` has nowhere to put it.
- Three consumers key on the harmonic mechanism: the 1 % weight seed,
  `HARMONIC_FRACTION` above `HARMONIC_IMPLAUSIBLE_FRAC` = 0.15 (`refine.py:8955`), and
  `CompiledModel.harmonic_orders`.

**The decision this WP opens on (the maintainer's: a stored-format change on the
instrument schema).**
- **(a)** Generalise `Harmonic` with a non-integer `wavelength_factor`, a `weight` and an
  optional `zero_offset`. One list, but every consumer above must branch on integer
  versus non-integer, or an r = 0.4 component reads as an implausible harmonic.
- **(b)** Add `NeutronSource.extra_lines: list[NeutronLine]` with `wavelength_ratio`
  (a fixed-by-default `Parameter`), `weight` (bounded at 0, relative to line 0) and
  `zero_offset` (degrees, default 0, fixed). `lines` appends λ₀·ratio after the
  harmonics; the ratio is not a wavelength, so `wavelength_parameters` stays `[λ₀]` and
  `check_wavelength_freedom` is untouched. A fixed ratio of exactly 1/n is refused,
  pointing at `Harmonic`. The reporter recommends (b); the triage leans (b) for the same
  reason (the three mechanism-keyed consumers stay untouched).
- Either needs a `SCHEMA_VERSION` bump and `_audit` rows for the new defaults (the fixed
  ratio, the zero offset, the weight seed). Old files open unchanged: empty means off.

**Measured by the reporter (synthetic, invented numbers; reproduce before relying on
them).** Rock-salt a = 5.60 Å at λ₁ = 1.80 Å, FWHM 0.35°, 10-150°; second line ε = 5e-3,
c = +0.15°, r = 0.4. A one-line fit of the two-line pattern: GoF 1.00 → 6.08, W doubles,
zero takes 0.043°, the cell moves +0.00073 Å (3.6 of its own esd, 66× the clean fit's
esd), over five seeds. Local correlations at the truth with a, zero, ε, c, r, scale,
U, V, W free: resolved case ε–c −0.80, c–zero −0.26, ε–a +0.21, r–scale −0.53;
unresolved (Δ2θ ≲ FWHM) ε–c −0.95, c–zero −0.92, ε–a +0.74. So (ε, c, r) are calibrated
on a standard with its cell held and then held on samples: the `lab_calibrate` pattern.

**Forward model seams.** The offset lives in the shared position function:
`_position_shift_deg` / `apparent_two_theta` (`model/forward.py`) take the line index;
`reflection_positions`, both tick builders (`multi.py` keeps its own, root CLAUDE.md)
and `report.satellites` follow through it; the position memo keys on the offsets.
`generation_window` widens by max(cₖ, 0) low and max(−cₖ, 0) high rather than relying
on `REFLECTION_MARGIN_DEG` = 0.5. `_compile_extra_peaks` maps an extra component onto
each line and needs the offset too. A new derivative path (the ratio, the offset)
grows `tests/test_cross_backend.py`'s configs.

**Prior art** (recall, not checked against the programs' docs this session).
FullProf's `.pcr` carries Lambda1, Lambda2 and Ratio for any CW job, neutron included,
with no per-line offset. TOPAS states any number of lines in a `lam` block (`la`, `lo`,
`lh`), radiation-independent, each refinable; a per-line offset is not a built-in
keyword. GSAS-II's instrument parameters state `Lam1`/`Lam2`/`I(L2)/I(L1)` for X-ray
and a single `Lam` for CW neutron. Search the manuals before the design is fixed and
save the survey in `docs/practice.md`.

**Tier.** The line itself is physics (a second wavelength and a geometric offset); the
weight seed and the calibrate-then-hold staging are named practice (`lab_calibrate`).

## Non-goals

- TOF.
- X-ray Kα lines: `EmissionLine` covers the doublet; a per-line offset there could reuse
  the field later.
- The two GSAS reader refusals: follow-ups once the line exists.

## Tasks

- [ ] The schema, under the maintainer's (a)/(b) ruling recorded here first;
      `SCHEMA_VERSION` bump; old files open unchanged.
- [ ] Forward model: per-line offset in the shared position function, the position memo,
      `generation_window`, `_compile_extra_peaks`, both tick builders.
- [ ] Parameter table and Jacobian: ratio and offset columns, analytic or gated to FD per
      the "branch claims what one name reaches" invariant; cross-backend rows.
- [ ] A calibration stage: a preset or `lab_calibrate` stage after `zero_disp` freeing the
      line's three parameters, weight last.
- [ ] Diagnostics: `HARMONIC_FRACTION` stays silent on the new line; report how far a
      line's ratio, offset and weight moved from the declared values, in esd (the
      `WAVELENGTH_CALIBRATION` shape); `_audit` rows.
- [ ] `help.py` entries for the new fields; `gui/src/lib/history.ts` `PLACES` if a new
      family appears.
- [ ] Tests: recovery of (ε, c, r) within esds, cell held then free (resolved case);
      the one-line fit is worse by GoF and cell shift in esd, never Rwp;
      `tests/test_harmonics.py` bit for bit; empty list bit-identical; a joint and a
      sequential fit accept the line with the ratio shared; refusals (ratio ≤ 0, negative
      weight, fixed 1/n); ticks at the offset positions. obs/calc/diff PNGs to
      `tests/output/`.
- [ ] Manual: `reference/instrument.md` beside harmonics; the equation in
      `theory/peak-positions.md` with its `*Source:*` line.
- [ ] Skill: a row in the instrument reference (or the `references/instruments.md` #1201
      may create in WP-2008) naming the line and the calibrate-then-hold order.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_harmonics.py tests/test_cross_backend.py -q
.venv/bin/python -m pytest tests/test_audit_table.py tests/test_help.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- Issue #1208 (the proposal, the reproduction script, the identifiability table).
- Issue #1201 (the reading step that would have found the line).
- Rodríguez-Carvajal, J. (1993). Physica B 192, 55-69 (FullProf; for the Lambda2 field).

## Handover log

- **2026-10-31** — created by the issue triage from #1208. No open WP owns a second
  neutron line: WP-1132 (neutron µR) and WP-2056 (low-angle CW neutron asymmetry) share
  the track but not the mechanism, and WP-1312 (CW neutron follow-through) is ✅.
  Next: the maintainer rules (a) or (b).
