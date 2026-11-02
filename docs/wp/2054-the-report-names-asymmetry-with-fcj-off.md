# WP-2054 — the report names an asymmetric residual the model cannot draw

Milestone: unscheduled · Status: ⬜
Track: What fires, and what stays silent
Depends on: 1977 soft (the flank-lobe half of the same symptom); 2004 soft (a new template's thresholds take audit rows there)
Priority: P2 2026-10-26 — a report that names the wrong cause: on a lab Bragg–Brentano fit with the apertures at their default 0, Layer 2 suggests an impurity phase at 0.50 and nothing mentions asymmetry (#1106, NIST SRM 660c)

## Goal

When a fit's residual is one-sided about its peaks, the FitReport says so whatever the
instrument declares. With the axial apertures at 0, a significant asymmetric residual
produces `refine_axial_asymmetry` with the instruction to declare the apertures (or take
them from a standard), and no longer reads as a missing phase.

## Context

**Source.** Issue #1106 (2026-10-22, @mustachefeeling), on the bundled NIST SRM 660c
pattern (`tests/data/nist_srm660c_100a.cif`, the `_meas` block) with LaB₆ and
`Instrument.bragg_brentano(radiation="CuKa", monochromator_two_theta=26.6)`. The issue
carries a self-contained script.

**Measured at c0e32ab29** (`[dev]`, macOS arm64), the issue's script:

| | apertures 0 (default) | apertures declared (0.025) and refined |
|---|---|---|
| Rwp / GoF | 0.1288 / 2.78 | 0.0867 / 1.87 |
| Layer-1 columns | intensity, mixing, position, width | + asymmetry |
| `unmatched_obs` below 45° | 10, each 0.1-0.3° below a LaB₆ line, up to 25.4 σ at 21.28° | 7, all ≤ 6.7 σ |
| active actions | `add_impurity_phase` 0.50, `increase_background_flexibility` 0.47 | `refine_sample_strain_broadening` 0.12 |

`report.layer2.compare_freed` on the pair: t = 7.4 and 11.7 for the two apertures, ΔBIC +280
at N/f² (N 5332, N_eff 368).

**Why the report cannot see it.**
- Layer 1's `asymmetry` kind (`report/layer1.py:12`, `_KINDS` at :71) is the FCJ
  derivative ∂Ω/∂(S/L). `derivative_bases` builds it only while FCJ is live
  (`model/forward.py:2814`, `build_axial = axial_derivs and fcj_live(sl, hl)`).
- `Geometry.axial_sl`/`axial_hl` default to 0.0 (`schemas/instrument.py:1255-1260`), and
  the `bragg_brentano` preset keeps that.
- `refine_axial_asymmetry` (`report/layer2.py:1009-1021`) fires only on a significant
  `asymmetry` coefficient in a gated region below 40°, so it cannot fire when the model has
  no asymmetry.
- At exactly zero the FCJ column is dead (issue #1075, repro 1): the profile's first-order
  change in S/L vanishes there. So computing the physical column at 0 is not a fix.

**Candidate directions** (the issue's points 1 and 2, plus one from triage).
- (a) A model-free asymmetry column, always present: the odd-cubic direction u³·Ω̂ that
  peak fitting already reads for `PEAK_ASYMMETRY_UNMODELLED`
  (`indexing/peakfit.py:385-404`, u = (2θ − 2θ_j)/Γ). Odd-cubic because a free position
  absorbs the odd-linear part.
- (b) The FCJ column evaluated at a nominal aperture when the model's is 0. The package
  already sizes FCJ nodes as if S/L = H/L = `forward.AXIAL_SIZING_FLOOR` (0.02) when both are
  0 and one is free; that is the natural nominal value.
- (c) The preset declares a nominal nonzero aperture, so the existing column and action
  work. This moves every lab fit built from the preset.
- Point 2 in every case: when the column is significant and FCJ is off, the action says the
  apertures must be declared nonzero first, or taken from a standard or resolution file.

**Practice** (`docs/practice.md` § Axial divergence at zero, checked 2026-10-25 by
WP-1421's survey). GSAS-II never computes a zero aperture: one SH/L, floored at 0.002 for
the profile at every evaluation, refined or not. RIETAN-FP and FullProf do not describe a
zero case. MAUD and EasyDiffraction use an empirical or Bérar–Baldinozzi asymmetry instead
of FCJ (§ Axial divergence quadrature). No code surveyed has a report layer, so none has
the report-side question.

**Tier.** Direction (a) is a new template in an existing basis; its significance is read
through the four existing region gates, so it adds no threshold unless the action needs
one. Direction (c) is a default (a declared aperture), tier 2 if GSAS-II's floor is the
named practice. Either way the action is the "rank with evidence" kind (DESIGN § Rules, 1):
the report names asymmetry beside the other candidates; it does not choose.

**What would fool the new column.** A position error that is not a constant shift inside a
region, a Kα2 weight error (one-sided about Kα1 by construction, see issue #1166), and a
flank lobe from a width error. The column must be measured against all three before it
ranks anything.

**Licensing.** Concepts only from the issue and from FCJ (Finger, Cox & Jephcoat 1994);
nothing ported.

### Inherited

- 2026-11-02, from WP-1977 (PR #1295, reworked to Yue's ruling of
  2026-11-01): every `unmatched_obs` row stays listed and carries
  `UnmatchedPeak.flank`. On #1106's script with the apertures at 0, all 11
  rows say `on_flank`, at 0.9-3.0 FWHM below their LaB₆ line and one 1.0
  above, and `add_impurity_phase` 0.50 is gone, because Layer 2 no longer
  counts a row on a flank (rebuilt from the stored fit, `[dev]`,
  darwin/arm64). The other active action, `increase_background_flexibility`
  0.47, is untouched. So the failing test this WP plans must assert on the
  asymmetry action's absence; its "suggests `add_impurity_phase`" half no
  longer reproduces once WP-1977 merges, and the Acceptance clause
  "`add_impurity_phase` is not the top action" holds already. The flank rows'
  offsets and their `lines_with_lobe` counts are evidence an asymmetry test
  can read.

- 2026-10-31, from the issue triage (issue #1106): the reporter (2026-10-29)
  brings evidence for direction (a) and one new ask, with no code and no
  threshold. Per peak region they fit the residual on the model's own net line
  P and its derivatives P′, P″, P‴ (P‴ the odd direction left once a free
  position takes P′), each with a counting-noise t not divided by the
  serial-correlation factor f, rolled up per term as a coherent z, an
  incoherent χ² and an rms t. Synthetic (rietx's own forward model, so one
  source): axial asymmetry 0.02 with FCJ off, which Layer 1 reads today as
  position (rms t 4.6–5.0), shows shift rms 5.9–6.6 and odd rms 3.4–3.8 in 3
  of 3; a 5 % high-angle second line, silent in Layer 1 today, shows odd rms
  2.83–3.51; the null over 20 clean fits has the largest per-term rms at 1.32.
  Dividing by f biases the null low and eats the signal (the second line falls
  to 1.99–2.17 against 1.18). On four public patterns with FCJ refined every
  term reads far above N(0,1); the odd term is one-signed on SRM 1976a
  (coherent z +31.5) and FAP (+16.3) and has no net sign on SRM 660c (+0.5),
  so an always-present odd column would report something on most lab fits. The
  ask: a `t_noise` field on `BasisCoefficient` beside `stderr` and
  `significant`, the per-term rollups printed ungated on both maturity
  branches, `significant` untouched until WP-2004 rules on the gates; about
  1.6 ms in `report()`; one extra run per additive fixed component reads a
  blank mismatch (2e-4 in d gives 3/3, its control 0/3). They recommend the
  Layer 1 seat over a Layer 0 field and leave it to the maintainer. Tiers as
  they state them: the statistic tier 2 (Rao 1948 score test, Ramsey 1969,
  Turin 1960), the null tier 1, the region rule (4 % of peak height, ≥ 6
  points) tier 3, a BH q per region that never gates. Checked against the tree
  at d87c8cc91: `BasisCoefficient` (`report/schemas.py:922`) carries `kind`,
  `value`, `stderr`, `significant`, `share`, and no noise-only t. A new field
  on the report is a public schema change; the decision belongs with this WP's
  first task.

## Non-goals

- The `unmatched_obs` matching window and a flank-lobe filter on `add_impurity_phase` (the
  issue's point 3): WP-1977, which has the cpd-1c/1f cases and now this one.
- The numpy FCJ column's accuracy at one zero aperture: WP-1955.
- S/L ↔ H/L interchangeability: WP-2012.
- An empirical (Bérar–Baldinozzi) asymmetry model: issue #1090's own placement.
- Tiering the report's existing gates: WP-2004.

## Tasks

- [ ] Maintainer decision: (a), (b), (c) or a combination, recorded here as
      `Decided YYYY-MM-DD:` and answered on #1106.
- [ ] A failing test: SRM 660c with the apertures at 0 reports no asymmetry and suggests
      `add_impurity_phase` (the issue's script, trimmed).
- [ ] Land the chosen direction. If (a): the column joins Layer 1's basis, passes the four
      gates, and its correlation with `position` and `mixing` on SRM 660c and two other
      families (cpd-1c, FAP) is recorded.
- [ ] The action: `refine_axial_asymmetry` fires from the new column when FCJ is off, and
      its rationale says the apertures are 0 and must be declared or calibrated first.
- [ ] Controls: a synthetic symmetric pattern with a Kα2 weight error and one with a width
      error do not fire the action; a synthetic with known S/L does.
- [ ] Audit rows for any new threshold or action site (`rietx._audit`), and a
      `THRESHOLDS_VERSION` bump if one moves (coordinate with WP-2004).
- [ ] Tests + obs/calc/diff PNGs of SRM 660c at both settings to `tests/output/`.
- [ ] Skill: the `refine_axial_asymmetry` reference row says it can now fire with the
      apertures at 0, and what to do then; `help.py` if the action text changes.

## Acceptance

On SRM 660c with the apertures at 0, the report's active actions include
`refine_axial_asymmetry` and its rationale names the zero apertures; `add_impurity_phase`
is not the top action. With the apertures declared and refined, the report is unchanged
from today. The synthetic controls hold.

```sh
.venv/bin/python -m pytest tests/test_fitreport_layers.py tests/test_report_loop.py -n auto --dist loadgroup
.venv/bin/python -m pytest tests/test_audit_table.py tests/test_help.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

## References

- Finger, L. W., Cox, D. E. & Jephcoat, A. P. (1994). *J. Appl. Cryst.* 27, 892-900 (FCJ).
- NIST SRM 660c certificate (LaB₆), `tests/data/README.md`.
- Issues #1106, #1075 (repro 1), #1090 (the related model proposal), #1166.

## Handover log

- **2026-10-26** — created, from the 2026-10-26 issue triage (issue #1106). Checked against
  the tree at c0e32ab29: the issue's script reproduces (Rwp 0.1288 → 0.0867 with the
  apertures refined; with them at 0, no `asymmetry` column, 10 low-angle `unmatched_obs` up
  to 25.4 σ, `add_impurity_phase` 0.50); every code line it cites holds, a few lines moved.
  No open WP owns it: WP-1977 owns the flank-lobe filter (the issue's point 3) and excludes
  Layer 1's ranking; WP-1955 and WP-2012 are the FCJ column's accuracy and the aperture
  pair's symmetry; WP-2004 tiers existing gates and adds no column. *Next:* the decision.
