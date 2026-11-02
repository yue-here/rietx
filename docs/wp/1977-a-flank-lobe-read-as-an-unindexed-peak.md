# WP-1977 — a flank lobe read as an unindexed peak

Milestone: unscheduled · Status: ✅ 2026-11-02 — PR #1295; every residual peak is listed with its flank evidence, and none on a flank buys an impurity call (ruled 2026-11-01)
Track: What fires, and what stays silent
Depends on: —

## Goal

Layer 0 says, for each residual peak it lists, whether the observed curve
joins it to a drawn peak with no resolving dip. Layer 2 names no single cause
for such a peak, and so suggests no impurity phase on it. A residual the data
resolve keeps today's reading. (Rewritten 2026-11-02 to Yue's ruling of
2026-11-01; the first goal, a flank lobe counted as explained, is the design
the ruling replaced.)

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

**#1106 point 3 (from the 2026-10-26 triage).** The issue proposed a flank
filter on `add_impurity_phase`. Since the rework this is what lands: Layer 2
does not count a row on a flank toward the call. Points 1-2, the asymmetry
column, stay with WP-2054.

**The tier of each rule this WP adds** (rewritten 2026-11-02). Two rules.
(1) The flank test, `report/layer0.on_drawn_flank`: the observed curve rises
from the residual into a peak `y_calc` draws, with no dip of `min_peak_sigma`
σ on the way. It is a measurement now, recorded on every `unmatched_obs` row
as `UnmatchedPeak.flank`, and filters no row. (2) Layer 2 does not count a row
with `flank.on_flank` toward `add_impurity_phase`. Kind of ambiguity: 2. A
shape or asymmetry misfit, an unmodelled Kα2, a lower symmetry and a foreign
line all leave such a shoulder, and the data score them only partly (the
offset in FWHM, how many lines as strong carry a lobe on the same side). So
the package records the evidence, names the four causes in
`rietx.help.explain("UnmatchedPeak.flank")`, and picks none. Tier 3: no
program flags a difference-curve peak after a fit (`docs/practice.md`), and
the 5σ levels are the report's detection level reused, owned by WP-2004.
Measured on the IUCr CPD QPA round robin (one laboratory), SRM 660c and five
synthetic LaB₆ cases (`tests/test_flank_lobes.py`); the firing side on real
data is 11-BM NAC's CaF₂ (`tests/eval_report_agent`'s W1 rows).

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
- [x] Rework to Yue's ruling of 2026-11-01 (2026-11-02): every residual peak
      stays listed and carries `UnmatchedPeak.flank`; `add_impurity_phase`
      does not count a row on a flank; the four causes in `help.py`, one
      skill row in `references/abstention.md`; the manual, the records and
      the tests follow.

## Acceptance

On cpd-1a…1h under `qpa_plan`, every `unmatched_obs` within 0.5° of a
strong reflection carries `flank.on_flank`, and Layer 2 suggests no
`add_impurity_phase`. On a synthetic pattern with an unmodelled second phase,
its strongest isolated peaks still read as `unmatched_obs`, off any flank, and
the impurity call is made. A tetragonal specimen modelled cubic keeps
`reindex_or_recheck_cell`.

```sh
.venv/bin/python -m pytest tests/test_flank_lobes.py tests/test_fitreport_layers.py -n auto --dist loadgroup
.venv/bin/python -m pytest tests/test_acceptance_qpa_roundrobin.py -n auto --dist loadgroup
```

## References

- WP-1908, § Tasks last item and its 2026-10-13 handover entry.
- PR #927 § Not done.

## Handover log

- **2026-11-01** — closed, PR #1295. The fit report no longer calls a
  misfit lobe on the side of a drawn peak an unindexed line. Such a lobe
  is joined to the peak by the observed curve, with no dip between them,
  and the report now checks for that dip instead of only measuring the
  distance to the nearest tick. On the twelve round-robin fits and SRM 660c
  that took 66 false "unindexed" rows out of the list, and two wrong
  "add an impurity phase" suggestions with them. The cost is a blind zone.
  A real foreign line that sits unresolved on the flank of a strong peak is
  now explained away too, out to 2-6 FWHM depending on the peak's height.
  Whether the report should record what it explained is a question for Yue,
  at the end of this entry.

  *Done.* `report.layer0.on_drawn_flank` and its call in `build_layer0`;
  `build_report`'s `match_tol_deg` default quotes `LAYER0_MATCH_TOL_DEG`
  instead of a second literal 0.08. `EXTRA_PEAK_ON_REFLECTION` keeps the
  0.08° window, reason in the constant's comment. `THRESHOLDS_VERSION`
  1.13 → 1.14. Tests: `tests/test_flank_lobes.py` (9), the rewritten
  broad-peak test in `test_fitreport_layers.py`, and a slow acceptance row
  per cpd-1a…1h in `test_acceptance_qpa_roundrobin.py` (no lobe listed
  within 0.5° of a strong line, no active `add_impurity_phase`). Skill
  `judging.md` §4b, manual `concepts/report.md` and
  `reference/report.md`, release note, practice survey § "When a peak
  counts as explained by a reflection". Notes to WP-2054 and WP-2004.

  *Measured* (`[dev]` venv, darwin/arm64). Task 4's table is the
  before/after. The acceptance rows fail on origin/main (8 of 8) and pass
  here (8 of 8). 11-BM NAC's real CaF₂ (`eval_report_agent` W1, two rows)
  and the Kα2 satellites (W2) still read as unmatched: 3 passed. The blind
  zone, on a synthetic Lorentzian of FWHM 0.1° with a foreign line 8-12σ
  tall, five noisy draws per cell: hidden out to 2 FWHM at 10³ counts, 3-4
  at 10⁴, 6 at 10⁵, against 0.8 FWHM for the old 0.08° window. A 50 %
  Gaussian mix halves the reach at 10³-10⁴. `python -m tests.reader_output`
  exits 1 with one change: the SRM 660c standard fit's summary goes from
  "12 observed peak(s) match no reflection." to "0 …". Fast
  selection, `[dev]`, darwin/arm64, beside another runner's suite: 13168
  passed, 310 skipped, 32 xfailed, 3 failed. Two failures were this
  branch's and are fixed (no `validation_matrix` row for the new acceptance
  test; the skill's `api.md` quoting thresholds 1.13); their files then
  passed, 952. The third,
  `test_display.py::test_a_plot_in_a_kernel_shows_once_and_leaves_the_backend_alone`,
  is this Mac's Jupyter kernel spec pointing at a deleted venv. The added
  fast tests cost 11.7 s in all, 7.2 s of it the two blank-line cases.

  *Code review* (`/code-review high --fix`). Taken: scipy's prominence-0
  warning silenced, the reach measured into the docstring. Tried and
  reverted: a walk crossing flat steps, which would carry it along a flat
  background to a far peak. Tried and dropped: a second condition that the
  residual turns negative only inside the drawn peak's upper half; most
  real lobes fail it (cpd-1c 0.23-0.50, SRM 660c 0.08-0.18 of the
  prominence), so it would un-explain them. Declined: the indexing workflow
  counts `unmatched_observed` through `build_layer0`, so its numbers move
  with no `INDEXING_THRESHOLDS_VERSION` bump. Indexing was another runner's
  area this shift, so it was left unbumped. Measured afterwards on the
  merged head d90e81e24: `tests/test_acceptance_indexing.py` 45 passed, and
  22 captured engine units (brucite, corundum, two synthetic monoclinic)
  replay to the same digests, candidate counts and completeness under this
  branch and under origin/main. No rank or grade moves, since consensus and
  the gate never read the count. Only the reported `unmatched_observed`
  and `INDEX_IMPURITY_LINES` move. Settled by Claude under WP-2011's
  precedent: WP-2011 moved this same count and recorded it as an "Also 1.12"
  line under the release cycle's one bump (#991's rule), so this move is
  recorded the same way and the number stays 1.12. A bump to 1.13 was the
  alternative, and it would be a second bump in one cycle. Declined: three
  reader texts still say "match no reflection", which stays true of what is
  listed. Declined: three test and speed cleanups.

  *Generality* (generality-review, verdicts and the first two tables
  unedited, the last two tables summarised; the author's answer under
  each `fails` or `weak`).

  ## `report.layer0.on_drawn_flank` (no table row; a rule the table cannot see)

  **Verdict: weak.** The case for acting is better measured: 65 flank lobes left the list on specimens known to carry no impurity. But the author's own docstring shows the kind-1 claim fails the unanimity gate. No tier is stated, and nothing records which peaks the rule explained.

  | Question | Author's answer (where) | What I found | Verdict |
  |---|---|---|---|
  | 1. What it decides | "a residual peak whose observed curve rises into a peak `y_calc` draws, with no valley of `min_peak_sigma` σ on the way, is explained" (WP file, Context, "The tier of each rule this WP adds") | It drops a peak of at least 5σ from `report.unmatched` when no tick lies within 0.08° and the flank test passes. That also withdraws `add_impurity_phase`, which "reads only `unmatched_obs`" (WP Context, #1106 paragraph). It runs on every `build_report` with no switch. `match_tol_deg` and `min_peak_sigma` are parameters, but this test has no parameter of its own. | Stated. That it is always on with no switch is not stated. |
  | 2. Kind of ambiguity | "Kind of ambiguity: the data settle it, since no competent refiner reads a shoulder of a drawn peak as a separate phase" (WP Context). There is no row, so no `ambiguity` field. | The data settle only one branch. Where the observed curve has a valley, the peak is a line of its own, and the rule lists it. Where there is no valley, the docstring itself says: "A foreign line that the observed curve does not resolve from a stronger neighbour is explained too. No positions test can separate it from a shape misfit" (`layer0.py`, `on_drawn_flank`). So at that peak the data cannot decide. The hypotheses can be listed: a shape or asymmetry misfit, an unmodelled Kα2, a line split by lower symmetry, or a foreign line. Pattern-level evidence could rank them, for example whether the lobe recurs on every strong line at the same offset. The rule picks one hypothesis, silently. That is kind 2 handled as kind 1. | Disagrees. The author's own docstring contradicts the kind-1 claim. |
  | 3. Case against acting | none named (WP Context) | Three competent refiners would act otherwise. (a) Someone screening for a minor phase, such as a trace impurity or a polymorph beside the main form, whose strongest line sits a few FWHM from a host line. The unresolved shoulder is the sign they look for. The docstring measures how far the rule hides such a line. A line 8-12σ tall beside a Lorentzian of FWHM 0.1° is hidden "out to 2 FWHM at 10³ counts, 3-4 at 10⁴ and 6 at 10⁵, where the 0.08° tick window alone hid it out to 0.8". At 10⁵ counts that is about ±0.6° around every strong line. How much of a dense pattern those zones cover was not measured. I found no script or test behind the reach numbers, in the WP file or in `tests/test_flank_lobes.py`. (b) A phase with lower symmetry modelled in a higher one: each split line reads as a shoulder. Before, such lobes reached Layer 2 with `reindex_or_recheck_cell` as the first alternative (`test_broad_peak_lobes_cap_impurity_without_reindex` asserts this). Now no entry is made, and this case was not measured. (c) An unmodelled Kα2 line, which sits unresolved on the Kα1 flank at low angle. `tests/eval_report_agent/test_landing_states.py::test_w2_satellites_vanish_when_the_source_is_fixed` asserts at least 10 `unmatched_obs` at Kα2 positions (31 measured before). The WP does not quote that test's result on this branch. Programs: `docs/practice.md` (new section) finds no program that flags a difference-curve peak after a fit. GSAS-II and FullProf were checked; TOPAS was inferred. | Dissenters can be named, so the rule fails unanimity. |
  | 4. Case for acting | "66 rows left the list, and 65 of them sat 0.08-0.38° from a line drawn at 125-24175 counts … cpd-1b loses `add_impurity_phase` 0.50, and SRM 660c at zero apertures loses `add_impurity_phase` 0.50"; the synthetic silicon case: "every silicon line above 8σ that sits 0.3-2.0° from a LaB₆ line is still listed" (WP Task 4) | This case is real and measured. Sample 1 and SRM 660c are known to be impurity-free (a weighed composition, and certified single-phase LaB₆), so both withdrawn suggestions were wrong. The old behaviour was an accident: "The old, misplaced ticks put them inside the window by accident" (WP Context). A refiner reading the cpd-1c lobes, which recur on each strong zincite line on the same side, would plausibly call them a shape misfit. No number moved off a reference, because the change is report-only (Rwp agrees to four places). The cost to an agent of a false `add_impurity_phase` (extra calls, a phase refined to nothing) was not measured: none given. | Holds, on development data. |
  | 5. Tier and source | No tier is stated. The paragraph headed "The tier of each rule this WP adds" gives the kind and the datasets. It cites "the reader's eye made explicit (McCusker et al. 1999)" and says "It adds no number" (WP Context). | This is tier 3. `practice.md` says "rietx's `unmatched_obs` has no direct precedent", and lists McCusker and Toby as "inferred (recall, no local copy) … Neither gives a numeric rule". The "no number" claim does not survive the record's rule: "a factor is a threshold of its own". Reusing the 5σ detection level for two other quantities, the apex prominence and the allowed valley depth, is a choice. The valley depth sets the blind-zone reach in row 3. Neither level is visible to the table, because `build_report` is not in `DEFAULT_SEATS`. They were handed to WP-2004 (the open audit of the report's thresholds) as one level (`docs/wp/2004-…md` § Inherited, 2026-11-01). The orderings (strictly uphill, the pattern edge never an apex, both directions tried) are invisible to the table too. | Tier missing. The "adds no number" claim is weak. |
  | 6. Dataset families | "Measured on the IUCr CPD QPA round robin (twelve fits), SRM 660c and four synthetic LaB₆ cases" (WP Context) | The CPD patterns are one laboratory and one instrument, a Philips 3020 (`tests/data/README.md` § v0.3), so they count as one family across several materials. SRM 660c is a second, from NIST. The synthetic cases come from rietx's own forward model and count as none. That is two real families, below the three the record requires. The reference is the right kind, a known truth: weighed compositions and a certified single phase. Against it the rule stays silent where there is no fault. Whether it still fires where there is a fault was shown only on synthetic data. 11-BM NAC carries a real CaF₂ impurity (W1, `test_w1_landing_names_the_impurity_…`), and its result on this branch is not quoted. Both real families are development data: the rule was chosen after Task 1 measured the cpd-1c and SRM 660c lobes ("at most 2.2σ along the way"). The author does not say so. The real SRM 660c case has no test. `test_asymmetry_lobes_…`'s docstring names `test_srm660c_apertures_at_zero`, which does not exist in the tree. The new cpd acceptance test checks the list but not the WP's acceptance clause "Layer 1 does not suggest `add_impurity_phase`". | Fails the three-family count. The firing side is synthetic only. |
  | 7. Field that says it fired | none given. The docstring says "the region list still carries its χ²". | None. A dropped peak leaves no entry. `UnmatchedPeak.kind` is an open string and gained no value. A region carries a χ² share and a maximum Δ/σ, but neither the peak nor the valley depth. The record requires that "a kept action leaves a record field". Separately, `docs/docs/reference/report.md:92` still defines `unmatched_obs` as "no calculated tick within {{ LAYER0_MATCH_TOL_DEG }}°". The concepts page was updated; this reference page was not. | Fails. |

  What would change the verdict: a recorded entry for each explained peak (position, height, deepest valley in σ, the apex it joined), for Layer 2 to down-weight rather than drop; plus this branch's results on W1 (real CaF₂ in NAC), on W2 (Kα2) and on a third unrelated real family.

  Author: the tier line now says tier 3, and kind 2 read as kind 1 under
  this WP's Goal, with the dataset families as found. W1 and W2 pass on
  this branch (3 rows), so the real CaF₂ still fires and the Kα2 satellites
  still read as unmatched. The reference page, the dangling test name and
  the acceptance clause are fixed. The reach numbers come from a scratch
  probe of five noisy draws per cell, not a committed test. The record
  field is the question for Yue below. Case (b), a lower-symmetry split,
  was not measured.

  ## `EXTRA_PEAK_ON_REFLECTION` kept on the 0.08° window

  `EXTRA_PEAK_ON_REFLECTION` is a warning that a peak the caller declared sits on a position the model already predicts.

  **Verdict: weak.** Neither side is measured. The comment's reason covers declared peaks the data resolve, which the flank test would not flag anyway. The unresolved case goes unargued.

  | Question | Author's answer (where) | What I found | Verdict |
  |---|---|---|---|
  | 1. What it decides | "That test stays out of the second consumer on purpose" (`layer0.py`, the comment on `LAYER0_MATCH_TOL_DEG`) | Behaviour is unchanged: the warning fires within 0.08° (`refine.py:9546`). Now a declared peak 0.1-0.6° away, on an unresolved flank, draws no warning, although Layer 0 would call a residual peak there explained. The caller must judge alone whether their peak doubles a reflection. | Stated. |
  | 2. Kind of ambiguity | none given. The row is unaudited, on `UNAUDITED_BASELINE`. | The message reports the gap, which is the shape of kind 3, but the code exists only on the 0.08° threshold. The old consistency claim no longer holds: "a component inside Layer 0's tolerance is one Layer 0 would have matched" (same comment, older text). | Cannot tell. |
  | 3. Case against acting (keep the window) | "A declared peak that the data resolve from its neighbour is a legitimate one wherever it sits on that neighbour's flank" (same comment) | True, but beside the point: `on_drawn_flank` never explains a resolved peak. One unstated reason is real: run on `y_calc` whole, the declared peak is its own apex, so sharing the test would need `y_calc` without the component. The designers also call a holder line overlapping a reflection "the design case" (`refine.py`, `_extra_peak_diagnostics`), so firing more often has an attention cost. Nothing measured. | Weak. |
  | 4. Case for acting (extend it) | none given | The warning exists for "two terms describing one peak, with nothing in Rwp to say which owns the counts" (`refine.py`, `_extra_peak_diagnostics`). A declared peak on an unresolved flank is that degeneracy. Nothing measured. | Unmeasured. |
  | 5. Tier and source | none given (`LAYER0_MATCH_TOL_DEG` is unaudited, owned by WP-2004) | Unchanged. For WP-2004's audit: `practice.md`'s windows are indexing windows (DICVOL 0.03°, ITO 0.06°, TOPAS 0.05°, the last inferred). 0.08° lies above all of them, so a tier-2 claim would need a stated reason. | No change. |
  | 6. Dataset families | none given | I found no test of a declared peak on a flank. | none given |
  | 7. Field that says it fired | the code itself | It fires `EXTRA_PEAK_ON_REFLECTION` with the gap in its message and the centre and area paths in `where`. Unchanged. | Holds. |

  What would change the verdict: a fit with a declared peak 1-3 FWHM from a strong, unresolved reflection, showing whether the peak's area trades against the phase scale (their correlation, or the area's esd).

  Author: behaviour is unchanged by this WP, and the window is WP-2004's
  to tier; the question goes there with the reviewer's proposed fit.

  ## `build_report:match_tol_deg` default now quotes `LAYER0_MATCH_TOL_DEG`

  **Verdict: holds.** The case for the change is clear, and there is no case against it.

  (Table: no new decision; removes a duplicate literal; `min_peak_sigma=5.0` is still a literal in both `build_report` and `build_layer0` and now sets three levels, handed to WP-2004.)

  ## Skill row, `docs/skill/rietx/references/judging.md` §4b

  **Verdict: holds.** The row names fields and adds no heuristic of its own. It omits the trap an agent hunting a minor phase would need.

  (Table: passes Rule 4's test for a skill row; "incomplete" because it does not say an unresolved foreign line is excluded too, which by WP-1338 belongs first in the package's help entry.) What would change the verdict: a record field naming each explained peak. The row should then point there rather than at `report.regions`.

  Author: the trap sentence waits on the record field, since it would point
  there; the skill file sits 1 B under its budget.

  *Gotchas.* The full suite was not run: the change moves no fitted
  number (Rwp agrees to four places on all twelve fits).

  **Question for Yue.** Should the report record each peak the flank rule
  explained, for example as a separate `kind` in `report.unmatched` with
  its height and the deepest dip in σ? For: DESIGN.md Rule 1 asks a kept
  action to leave a record field, and an agent hunting a trace phase could
  then see the shoulders. Against: `report.unmatched` has about twelve
  readers in `src/` and the GUI, and each needs auditing for a new kind;
  Layer 2 would then have to decide whether a recorded shoulder weighs
  toward `add_impurity_phase`. Doing nothing leaves the shoulder's χ² in
  `report.regions` and nothing else. Lean: record it, as a follow-up WP,
  because the blind zone reaches 6 FWHM at high counts.

  Next: Yue answers the question; a yes becomes a WP under WP-2004's
  track. Then WP-2054 (#1106 points 1-2) builds its asymmetry test on the
  SRM 660c case this WP emptied.

- **2026-10-15** — filed from WP-1908's open question (PR #927). No open WP
  owns Layer 0's matching window: a search of the open WPs for unindexed and
  unmatched peaks found none on this question.
