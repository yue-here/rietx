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

**Measured 2026-11-01 (task 1), on the tree at 52cec09a1.** `[dev]` venv,
darwin/arm64. The tree has moved since WP-1908's numbers.
- cpd-1c under `qpa_plan`, 5-150°: nine `unmatched_obs`. Six are flank lobes
  0.15-0.29° below a strong line: 31.62° (12.0σ), 34.28°, 36.08° (12.1σ),
  47.40°, 56.32° and 67.80°. Each tick's drawn height is 4935-24175 counts and
  the local FWHM of the drawn curve is 0.12-0.20°, so the lobes sit 0.8-1.5
  FWHM out. Two more sit at 5.10° and 5.34°, at the pattern's start, 20° from
  any line. The last, 32.66° (5.0σ), sits 0.11° below a fluorite line whose
  drawn height is 46 counts, smaller than the residual itself. The report
  abstains and suggests no `add_impurity_phase` on this tree.
- cpd-1f: three lobes 0.17-0.18° below lines of 3176-13211 counts (FWHM
  0.10-0.18°) and three at the pattern's start. No `add_impurity_phase`.
- SRM 660c, #1106's script, apertures at 0: eleven `unmatched_obs`, each
  0.08-0.32° below a LaB₆ line (FWHM 0.08-0.13°, so up to 2.7 FWHM out), up to
  25.4σ at 21.28°. `add_impurity_phase` 0.50 is active. With the apertures
  refined, twelve remain at up to 7.1σ, 0.14-0.34° from their lines.
- A FWHM-multiple window would need k ≥ 3 to clear SRM 660c, and a strong
  Lorentzian tail is still several FWHM wide at the 5σ level. What separates
  the lobes from a foreign line is the observed curve. In every lobe above,
  it rises into the drawn peak with no dip, at most 2.2σ along the way. A
  foreign line has a valley between it and its neighbour.

**Prior art (task 2).** `docs/practice.md` § When a peak counts as explained
by a reflection. The programs match an observed peak list inside indexing,
with a fixed angular or sin²θ window (DICVOL 0.03°, ITO 0.06°, TOPAS 0.05°).
None scales the window with the peak width, and none flags a difference-curve
peak after a fit.

**#1217 (from the 2026-10-31 triage).** With a measured blank declared, an
under-scaled blank leaves part of its own sharp line in the residual, and
Layer 0 listed it as `unmatched_obs`. The issue asked for a label. The Goal
covers it the simpler way: the blank's line is part of `y_calc`, so the flank
test explains it like a reflection's. The issue's open questions about a
label, a "sharp line" definition and printing the blank's σ/I are not
answered here.

**#1106 point 3 (from the 2026-10-26 triage).** The flank filter the issue
proposed on `add_impurity_phase` is unnecessary once Layer 0 explains the
lobes, because the action reads only `unmatched_obs`. Points 1-2, the
asymmetry column, stay with WP-2054.

**The tier of each rule this WP adds.** One rule: a residual peak whose
observed curve rises into a peak `y_calc` draws, with no valley of
`min_peak_sigma` σ on the way, is explained (`report/layer0.on_drawn_flank`).
It is a peak-resolution test, the reader's eye made explicit (McCusker et al.
1999). It adds no number: both its levels are the report's existing detection
level, `min_peak_sigma` = 5σ, unaudited and owned by WP-2004. Kind of
ambiguity: the data settle it, since no competent refiner reads a shoulder of
a drawn peak as a separate phase. Measured on the IUCr CPD QPA round robin
(twelve fits), SRM 660c and four synthetic LaB₆ cases (`tests/test_flank_lobes.py`).

### Inherited

## Non-goals

- Tick placement. WP-1908 settled it.
- Layer 1's action ranking, except where a changed `unmatched_obs` moves it.

## Tasks

- [x] Reproduce on cpd-1c under `qpa_plan` over 5-150°. List each
      `unmatched_obs` with its distance to the nearest tick, that tick's
      calculated height and the local FWHM.
- [x] Survey prior art for the same test. Record what each code does.
- [x] Choose and land the rule. Keep `EXTRA_PEAK_ON_REFLECTION` on the same
      authority or split it with a reason.
- [x] Re-measure WP-1908's twelve fits. A real impurity must still read as
      unmatched: use a synthetic pattern with a second phase added.
      Each fit was run on origin/main at 52cec09a1 and on this branch. Rwp
      agrees to four places, so only the report differs. `unmatched_obs`
      before → after: 1a 5→3, 1b 11→6, 1c 9→3, 1d 6→3, 1e 7→4, 1f 6→3,
      1g 5→2, 1h 7→3, 1c 20-40° 10→9, 1c 25-33° 1→0, cpd-2 9→3, cpd-4
      17→11, SRM 660c with the apertures at 0 11→0, refined 12→0.
      `unmatched_calc` is unchanged everywhere. 66 rows left the list, and
      65 of them sat 0.08-0.38° from a line drawn at 125-24175 counts,
      below it except for six SRM 660c rows above 140°. The one exception
      is 35.14° on the diverged 1c 20-40° fit, beside a line drawn at 0
      counts. What remains on 1a-1h and
      cpd-2 is 2-5 rows at 5.0-5.9°, the start of the scan 13-20° from any
      line, plus 32.66° on 1c (5.0σ, beside a fluorite line drawn at 46
      counts) and 26.96° on 1b (6σ, 1.26° from any line). Active actions
      that moved: cpd-1b loses `add_impurity_phase` 0.50, and SRM 660c at
      zero apertures loses `add_impurity_phase` 0.50 while
      `increase_background_flexibility` 0.47 stays (WP-2054's question).
      cpd-4 keeps `add_impurity_phase` 0.40 on lines at 119-135° that the
      observed curve separates from their neighbours, on a fit at Rwp
      0.28. The 1c 20-40° fit diverges (Rwp 0.92) on both trees, so its
      nine rows are displaced lines and stay listed. The synthetic
      second phase, silicon beside LaB₆: every silicon line above 8σ that
      sits 0.3-2.0° from a LaB₆ line is still listed (28.44°, 47.30°,
      56.12°, 69.13°, 76.38°, 94.95°, 114.09°). The one silicon line not
      listed, 88.03°, sits 0.04° from a LaB₆ tick, which the 0.08° window
      already hid.
- [x] Tests + obs/calc/diff PNGs of the flank-lobe cases to `tests/output/`.
- [x] Skill: the `unmatched_obs` reference row, if what it means changes.
      `references/judging.md` § 4b, one sentence inside its budget, and the
      manual's `concepts/report.md`.

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
