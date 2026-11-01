# WP-2073 — The QPA record says what its fraction rests on, and QPA at given values has a route

Milestone: unscheduled · Status: ⬜
Track: Render what the fit already knows
Depends on: — (2060 soft: a one-sided limit for a sub-3σ phase is its profile interval)
Priority: P3 2026-10-31 — a view over what the fit already knows: `PHASE_UNCONSTRAINED` fires on the unseen phase, but the QPA row, the exported table and the series trajectory carry none of it

## Goal

A weight fraction read from `result.qpa`, `write_qpa_table` or `qpa_trajectory` carries the
support the fit measured for its phase and the paths it rests on that were held or ended at a
bound. QPA at a caller's parameter values has one documented route, with esds where the caller
supplies a scale covariance.

## Context

**Source.** Issue #1213 (2026-10-29, mustachefeeling), three questions about QPA for weak and
near-absent phases. The width side of the same cases is #1212 (folded into WP-2004).
Everything is rietx simulating its own data, one synthetic family (LaB6 plus one cubic minor
phase, lab Cu Kα). The issue carries a self-contained 15 s script.

**Reproduced at d87c8cc91** (`[dev]`, macOS arm64), the issue's script, to its printed digits:

| case | W (esd), truth | codes on the phase | `profile_fraction` |
|---|---|---|---|
| unseen (CaF2 absent, seeded broad, a hump) | 7.27 ± 3.12 wt %, truth 0 | `PHASE_UNCONSTRAINED`, `BACKGROUND_ABSORPTION`, `STRAIN_UNUSUALLY_LARGE` | 97.65-97.88 %, excess 14.81, fit not admissible |
| absorbed (absent perovskite takes a broad LaB6 foot) | 17.74 ± 2.19, truth 0 | `BACKGROUND_ABSORPTION`, `BOUND_HIT` | 16.42-18.92 %, excess 0.31, admissible |
| real nano (CaF2 9.45 wt %, 3 nm) | 9.92 ± 0.46 | `BACKGROUND_ABSORPTION`, `FLOOR_HIT`, `SIZE_UNUSUALLY_SMALL` | admissible |
| real weak (CaF2 2.05 wt %) | 1.96 ± 0.36 | `FLOOR_HIT` | admissible |

The unseen case's QPA table row is `CaF2,0.072668612,0.031224557,...` with no `#` caveat.

**What the tree carries today.**
- `PhaseQuantity` (`schemas/results.py:420`): `weight_fraction`, its esd, scale, Z, M, ZMV,
  Brindley fields. No support, held or at-bound field.
- `unmeasured_phases` / `unmeasured_held` on the QPA record are set only for a phase with no
  line in range or a held scale (WP-1958), never for a free scale under 3σ.
- `write_qpa_table` (`io/exporters.py:302`) takes only the `QuantitativePhaseAnalysis`, so its
  caveats can name only unmeasured phases and microabsorption.
- `SeriesResult.qpa_trajectory` (`schemas/sequential.py:883`) skips only
  `weight_fraction is None`, so every `PHASE_UNCONSTRAINED` pattern plots as an ordinary point.
- `STRAIN_UNUSUALLY_LARGE`'s message (`refine.py` ~10377) reads "refined {term} to" for every
  value it flags, including one the hold kept at the caller's seed (the unseen case's
  `lor_strain` 10). That is WP-1076's "a message that names its discriminator makes the same
  claim".

**The single-fit absorbed case has no rule.** The issue measured six candidate rules on twelve
arms (its tables). Every one that fires on an absent phase broadened into an unmodelled feature
either also fires on a real 3 nm phase or misses it. A rival model (a broad copy of the phase
whose lines coincide) separates them: 9/9 negatives collapse to ≤ 0.05 wt %, 0/15 positive fits
move. That is Rule 1's third kind: the package reports and stops. So that half is documentation.

**QPA at given values.** After `set_values`, `result_` is `None`. The working public route is
`fit(data, plan=RefinementPlan(stages=[Stage("evaluate", [])]))`: 0 free, W bit-identical to the
fit's (0.019621971029780586), esd `None`. Two traps reproduced: `run_stage` with an empty stage
on an already-fitted object refits the previous free set (15 free; the scale asked for, 1.16e-5,
went back to 5.8e-6); and `Refinement` deep-copies its inputs, so the caller's own `Structure`
still holds the seed. `optimize.qpa.compute_qpa(..., scale_cov=...)` takes a caller's scale
covariance and is undocumented and not exported.

**Tiers.** The support significance is the hold's own measurement (`phase_support_sigma`,
already audited); held and at-bound paths are facts the stage records. A record field and a
caveat decide nothing for the caller, so no new action and no Rule 1 kind beyond reporting.
The 1b docs recipe rests on one synthetic family and says so.

**Decisions for the maintainer** (the brief's triggers):
- New fields on `PhaseQuantity` are a stored-format change (`SCHEMA_VERSION`).
- `Refinement.qpa(*, scale_cov=None)` or `rx.compute_qpa` names a top-level API.
- The issue's open questions: whether the fields belong on the record or the table writer
  takes the diagnostics (the issue leans to the record); whether `qpa_trajectory` marks or
  skips a `PHASE_UNCONSTRAINED` point; whether `QPA_FRACTION_RANGE`'s suggestion names the
  unmodelled-background reading before "quote the range" when `fit_admissible` is false.

### Inherited

(none)

## Non-goals

- Abstaining (`None`) on a `PHASE_UNCONSTRAINED` phase. Measured to drop 9/12 real sub-3σ fits.
- A one-sided upper limit for a sub-3σ phase: WP-2060 (profile intervals, #1075).
- A single-fit rule for the absorbed case. The series route is WP-2004's width-growth field.
- Changing `run_stage`'s continue-the-free-set semantics.
- A molar basis: WP-1340.

## Tasks

- [ ] `PhaseQuantity.support_sigma` for every phase (the hold's significance, written whether
      or not it fired) and `PhaseQuantity.conditional_on` (the phase's paths held at a handed-in
      value or ending at a bound, at the answer). Name the writer of each default at review;
      `None` where unmeasured.
- [ ] `write_qpa_table` adds a `#` caveat per such phase; `qpa_trajectory` carries the flag per
      point (mark or skip, as ruled).
- [ ] `STRAIN_UNUSUALLY_LARGE` and `SIZE_UNUSUALLY_SMALL` say "held at" when the hold kept the
      value.
- [ ] Docs: `docs/docs/reference/qpa.md` § One basin gains the absorbed case (a profile that
      confirms the esd does not establish the phase exists; the rival-model refit, measured on
      one synthetic family) and a "Fractions at given values" section (the empty-stage route,
      why its esds are `None`, the `run_stage` trap, the values on `ref.structure`).
- [ ] The QPA-at-values API as ruled, documented in the manual partition.
- [ ] Tests (the issue's four cases as fixtures) + obs/calc/diff PNGs to `tests/output/`.
- [ ] Skill: the `PHASE_UNCONSTRAINED` reference row names the new field; else none.

## Acceptance

On the issue's unseen case the QPA row carries `support_sigma` < 3 and `conditional_on`
naming `phases.1.lor_strain`, and the table carries a caveat line; on the real-weak case no
caveat. A QPA at given values with a supplied scale covariance reproduces the fit's own esd
(0.3649 % in the issue).

```sh
.venv/bin/python -m pytest tests/test_qpa.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

## References

- Issue #1213 and its script; #1212 (the series side); #203 (`profile_fraction`, WP-1320);
  #954 (WP-1958, unmeasured phases); #1075 (WP-2060).
- TOPAS `Remove_Phase` (v6 Technical Reference § 10.15): opt-in, acts on the user's own
  numbers. Not re-read in triage.

## Handover log

- **2026-10-31** — created from the issue triage (#1213). No open WP owns the QPA record's
  support fields: WP-1958 is awaiting its close and covered only a phase with no line in range;
  WP-1340 is the molar basis; WP-2060 takes only the upper-limit alternative.
