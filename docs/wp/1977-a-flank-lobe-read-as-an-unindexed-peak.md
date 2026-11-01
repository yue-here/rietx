# WP-1977 — a flank lobe read as an unindexed peak

Milestone: unscheduled · Status: 🔄 2026-11-01 — claimed by @yue-here
Track: What fires, and what stays silent
Depends on: —
Priority: P2 2026-10-15 — a flag that fires wrongly: it drives `add_impurity_phase` on two round-robin fits

## Goal

Layer 0 calls a residual peak unindexed only when no modelled reflection
explains it. A lobe of misfit on the flank of a strong peak counts as
explained.

## Context

**What Layer 0 does today** (`report/layer0.py`, `build_layer0`). It finds
positive residual peaks of Δ/σ ≥ 5 (`residual_peak_indices`). A peak with no
tick within `LAYER0_MATCH_TOL_DEG` (0.08° 2θ) becomes `unmatched_obs`. The
window is a fixed angle. It does not scale with the peak's width, and it
does not look at the residual's shape around the peak.

**What exposed it (WP-1908, PR #927).** Ticks used to sit about 0.11° below
the peaks on cpd-1c, because they lacked the displacement shift. After
WP-1908 the ticks sit on the peaks. Six residual peaks on cpd-1c (31.62°,
36.08°, 47.40°, 56.46°, 62.70°, 67.80°) sit 0.15-0.19° below strong zincite
ticks, on calculated curves of 650-1860 counts. They are the flank lobes of a
profile misfit. The old, misplaced ticks put them inside the window by
accident. Now they read as unindexed peaks. Across twelve `qpa_plan` fits,
`unmatched_obs` moved in both directions (cpd-1c 6 → 11, cpd-4 30 → 18).
Layer 1 then suggests `add_impurity_phase` on cpd-1c (0.30) and cpd-1f
(0.40), and neither specimen has an impurity. WP-1908's Tasks hold every
before/after number.

**Second consumer of the constant.** `EXTRA_PEAK_ON_REFLECTION` reads
`LAYER0_MATCH_TOL_DEG` to ask whether a declared component sits on a
predicted line. A change to the constant moves that check too, so the WP
either keeps the two together or splits them on purpose.

**What a result carries.** `build_layer0` takes a `RefinementResult`, not the
compiled model. It has `ticks`, `tick_hkl`, `y_calc` and the residual. It has
no per-reflection width. A width-scaled window needs the width from
somewhere, such as the local FWHM of `y_calc` around the tick or a new
companion field.

**Open questions, unmeasured.**

- A width-scaled window (k·FWHM), a test of the residual's sign pattern
  (a lobe beside a strong calculated peak with an opposite lobe on its other
  side is a shape or position misfit), or both.
- What GSAS-II, FullProf and TOPAS do for the same question. Search before
  designing (root CLAUDE.md, prior art).

### Inherited

- 2026-10-26 issue triage: #1106 is a second, public case of this WP's symptom. NIST SRM
  660c (`tests/data/nist_srm660c_100a.cif`, the issue's script) with the apertures at 0
  gives 10 `unmatched_obs` below 45°, each 0.1-0.3° below a LaB₆ line (21.06-21.28° up to
  25.4 σ), and `add_impurity_phase` at 0.50. Checked against the tree at c0e32ab29
  (`[dev]`, macOS arm64). The issue's point 3 (a one-sided-flank filter on
  `add_impurity_phase`, beside the displaced-pair filter in `report/layer2.py`) is a
  candidate rule for this WP's task 3. Points 1-2 (an asymmetry column with FCJ off) are
  WP-2054's.

- 2026-10-31, from the issue triage (issue #1217): a second way an
  `unmatched_obs` sits on something the model already draws. With a measured
  blank declared (`BackgroundFixedPlusChebyshev.from_pattern(blank, n_terms=3,
  vary_scale=True)`) and the model otherwise exact, the blank's noise biases
  its refined scale low (0.518-0.531 against a truth of 0.60, synthetic cubic
  perovskite capillary family, three seeds), which is WP-1309's regression
  dilution, here −12 % against 1309's −2.2 %. The under-scaled blank leaves
  part of its own sharp line in the residual, a coherent +6.5 to +8.0σ over
  0.3° at ≈ 42.1°, and Layer 0 lists it as `unmatched_obs` on 2 of 3 seeds. A
  noise-free blank gives 0 of 3. The issue proposes a label and no action: an
  `unmatched_obs` within the validity radius of a sharp line of a fixed
  background component says "on a line of the measured background" (a field on
  `UnmatchedPeak`, a distinct `kind`, or a summary note). This WP's Goal (a
  residual peak is unindexed only when no modelled component explains it)
  covers it. Checked against the tree at d87c8cc91: `UnmatchedPeak`
  (`report/schemas.py:599`) carries only `two_theta`, `height_over_sigma`,
  `kind`, and `report/layer0.py` does not read the fixed background component;
  `EXTRA_PEAK_ON_REFLECTION` asks the converse question for a declared extra
  peak against the ticks. Not reproduced: the issue's script runs on the
  reporter's harness and is not in the issue. The issue's own open questions:
  whether "sharp line" is read off the stored curve minus a running minimum or
  off a blank declared as a phase, and whether the blank scale's row should
  print the blank's own σ/I over its sharp lines, the number that predicts the
  dilution.

## Non-goals

- Tick placement. WP-1908 settled it.
- Layer 1's action ranking, except where a changed `unmatched_obs` moves it.

## Tasks

- [ ] Reproduce on cpd-1c under `qpa_plan` over 5-150°. List each
      `unmatched_obs` with its distance to the nearest tick, that tick's
      calculated height and the local FWHM.
- [ ] Survey prior art for the same test. Record what each code does.
- [ ] Choose and land the rule. Keep `EXTRA_PEAK_ON_REFLECTION` on the same
      authority or split it with a reason.
- [ ] Re-measure WP-1908's twelve fits. A real impurity must still read as
      unmatched: use a synthetic pattern with a second phase added.
- [ ] Tests + obs/calc/diff PNGs of the flank-lobe cases to `tests/output/`.
- [ ] Skill: the `unmatched_obs` reference row, if what it means changes.

## Acceptance

On cpd-1c and cpd-1f under `qpa_plan`, no `unmatched_obs` sits on the flank
of a strong reflection, and Layer 1 does not suggest `add_impurity_phase`.
On a synthetic pattern with an unmodelled second phase, its strongest
isolated peaks still read as `unmatched_obs`.

## References

- WP-1908, § Tasks last item and its 2026-10-13 handover entry.
- PR #927 § Not done.

## Handover log

- **2026-10-15** — filed from WP-1908's open question (PR #927). No open WP
  owns Layer 0's matching window: a search of the open WPs for unindexed and
  unmatched peaks found none on this question.
