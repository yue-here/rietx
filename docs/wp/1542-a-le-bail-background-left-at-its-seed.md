# WP-1542 — a Le Bail background left at its seed

Milestone: unscheduled · Status: 🔄 2026-11-05 — tasks 1-7 landed (PRs #1357, #1394, #1434); three questions wait on the maintainer on PR #1434, then this WP closes
Track: What fires, and what stays silent
Depends on: —
Priority: P3 2026-11-01 — was P2: WP-2062 moves every site where rietx picks a structure-free fit to Pawley (decided 2026-11-01), so no default path will run Le Bail; a caller who picks `mode="lebail"` still meets this

## Goal

A Le Bail fit whose background sits at a seed that is too low says so, and
the Le Bail call has a stated background protocol that does not need the
person to spot a flat line in a plot.

## Context

**The failure, from a real run** (2026-09-28, the review of `solution case 1`,
private corpus map § 5; WP-1510 has the source). The agent followed SKILL.md
§2 rule 5 and seeded every coefficient of an `auto_background` P-spline at a
low percentile. The pattern carried a broad diffuse hump over several degrees.
The free per-reflection intensities absorbed it, the background stayed at its
seed, and the Lorentzian width term grew to carry the hump's tails (it fell 4×
once the background was corrected). The cell was unaffected, so nothing looked
wrong. Every structure fit after it inherited a background that was too low,
with light-atom Biso at bounds and strong peaks under-predicted, for about two
hours, until the person saw the flat line in a plot.

**What worked** was a SNIP estimate held fixed under a 4-term Chebyshev: Le
Bail Rwp fell to 0.74× its first value. A fully free background went the other
way (`BACKGROUND_ABSORPTION`, R² 0.70 against the scale). The agent wrote its
own SNIP although `rietx.background.snip` ships, and the skill names neither it
nor this failure.

**Why nothing fired.** Root CLAUDE.md § Background flexibility: a background
able to imitate the peaks is measured (`background_absorption`), and the
too-stiff side has no guard. Under Le Bail the intensities are free, so a hump
the background cannot reach goes into them rather than into the residual. The
tell named in WP-1323's review is a width term that grows while the background
sits at its seed.

**Why it is not WP-1323's.** That WP's stop rule watches Rwp across passes, and
this failure lowers Rwp. WP-1323 shipped in 1.6.0 and closed with this filed
here (2026-10-03, at the maintainer's request).

Tier of each rule task 7 adds: `lebail_tol` is new judgement, tier 3, a default of
ambiguity 1, measured on five families of six patterns (#740 synthetic, corundum, 11-BM
NAC, FAP, BT-1 LaMnO3) against a 1e-10 reference and #740's true structure, failing on
FAP. `lebail_cycles` is answer-invariant by a measured 2× margin. SQUAREM S3 and its
factor are named practice, tier 2 (Varadhan & Roland 2008 and their R package).

### Inherited

- **2026-11-05, from WP-2076: what the Le Bail partition does to weak lines, measured.** A line with no
  neighbour takes Σ net / Σ Ω over its whole window, with `net` clamped at zero per channel, so a weak or
  forbidden line takes rectified noise and shows as a false peak. On an F m -3 m row the reference
  calculates 408 counts where 250 were observed, and the background sits about 10 counts low at high
  angle (160 against Pawley's 171). A signed net lowers χ² from 9854 to 4117 and does not restore
  nesting. WP-2076 § Findings.

- **2026-11-02, from WP-2062: no default path will run Le Bail.** The
  maintainer decided on 2026-11-01 that Pawley replaces Le Bail at the
  extinction screen, the GUI's Adopt and new-project wizard, and the prose
  that says "Le Bail before Rietveld", after Pawley's known bugs are fixed.
  This WP's decision 4 there said this WP drops a rung once that holds, so
  its Priority line now reads P3. The failure here still reaches a caller
  who picks `mode="lebail"`, and Pawley's own seed partition
  (`refine.py:4404-4411`) is one Le Bail pass.

- **2026-10-27, from WP-2011 and WP-2062: every surveyed program re-extracts
  Le Bail intensities inside the refinement, and rietx does not.** GSAS-II
  re-extracts once per least-squares iteration (`GSASIIstrMath.py:4808`,
  checked), FullProf once per cycle (ran), and TOPAS, RIETAN-FP and MAUD
  likewise (`docs/practice.md` § Structure-free fitting). rietx partitions
  `lebail_cycles` times before each solve and never inside one. That is a
  candidate cause beside the background for issue #740's plateau. WP-2062's
  decision 0 (repair Le Bail by re-extracting per iteration, or use Pawley
  where rietx picks the method) and its decision 4 may move this WP's
  priority. The indexer's validation is Pawley since WP-2011, so a Le Bail
  background no longer reaches `index_pattern`.

- **2026-10-24, from WP-2039: a model's starting background is now drawn before a fit.**
  `data.plot(model=ref)` draws the background at its starting values, dashed, over the
  channels a fit would use (`viz.plots._starting_model`). An `auto_background()` model
  starts its P-spline at zero and its air-scatter term at 0.001, so the figure shows a
  dashed line along zero: a seed left unset is visible before any fit runs. Usable as the
  picture this WP's report points to.

- **2026-10-16, from the issue triage (#726): a second case where the seeded
  `profile_only` prefit was not enough.** The 2026-10-11 PbSO₄ neutron entry
  below now has a companion: #726's comment of 2026-10-15, on a lab
  Bragg-Brentano pattern with a steep background. The facts and the reporter's
  PR offer are in WP-1910's Inherited section. Read it beside the
  seed-versus-SNIP measurement task.

- **2026-10-11, from the issue triage (#726, the reporter's comment of
  2026-10-11 09:56Z): the extinction screen's shared fit does not seed the
  background, and on a neutron pattern it never recovers.** Checked at
  d80ca5f4: `determine_extinction_symbol` calls `seed_widths(ins, peaks)` and
  nothing else on the instrument (`indexing/extinction.py:714-716`), so the
  background stays where the caller's instrument has it. That answers the
  2026-10-07 entry below for the screen. The indexer's `validate_by_lebail`
  is a separate path and is still unmeasured. The reporter's case, not
  re-run here: the PbSO₄ D1A histogram of `tests/data/gsas2_pbso4.gpx` with
  `constant_wavelength_neutron`'s all-zero Chebyshev, `validation_plan`
  replayed in `P m m m`. After the `bkg` stage the background sits at 3.6
  counts (median, 10-30°) where the data sit at 200. Rwp is 0.58 there and
  0.35 once the widths are freed, with `w` going from 0.21 to 1.37 deg². Le
  Bail then hands the pedestal to every reflection, including (0,0,1), (1,0,0)
  and (0,1,0), which Pnma forbids. On the reporter's reading, each class is
  then scored by how many reflections it has left to carry the background.
  Task 4 should add this pattern beside the hump and high-pedestal fixtures.
  On the X-ray histogram, seeding the background flipped the screen to a
  wrong class (WP-1910's Inherited, reproduced), so a seed alone does not
  fix this pattern.

- **2026-10-08, from the second issue triage (issue #833): a second voice
  for #725's default.** #833's third item asks for `auto_background(seed=True)`
  as the default, beside a REML-chosen P-spline λ and a
  `BACKGROUND_ORDER_AT_CAP` finding, which are WP-1931's. No new evidence
  for the seed itself; the 2026-10-05 entry's "whether a default changes is
  the maintainer's" still stands, now asked by two issues.
  Decided 2026-10-08: the default stays `seed=False` until task 4 has
  measured the seed beside the SNIP-held protocol; the choice is made then,
  from those numbers.

- **2026-10-08, from the issue triage (issue #740): a second case of this
  WP's failure, with a sharper reading of its mechanism.** The reporter's
  synthetic LaMnO3-like Pnma pattern (CW neutron, 2.4 Å, background
  300 + 2·2θ) at the true cell and profile, background free and seeded at the
  10th percentile of y (SKILL.md §2 rule 5), gives Rwp 1.62 % under one Le Bail
  stage at 100 or 400 `lebail_cycles`, against 1.09 % for the Rietveld fit
  of the true structure and 1.06 % for Pawley. The deficit is at 90-150°, where
  the weak dense reflections sit. The reporter's open question was whether the
  EM partition or its weights cause it. A probe points away from
  both: the Le Bail intensities are partitioned at stage start against the
  *seed* background (the same point as the 2026-10-05 entry above), and
  re-partitioning on the fitted background closes the gap. The mechanism
  (intensities absorbing the seed's deficit where reflections are dense) is
  the reading the numbers fit, not something the probe isolated.
  Measured: after the one stage the fitted background sits at 0.88 of the
  true one at 100° and 0.95 at 140° (0.99 at 20° and 60°), and the residual rms
  by 20° band, starting at 10°, is 0.94 0.89 0.97 1.07 1.85 2.34 1.74. Two
  stages in a row (100 cycles each, so the second partitions on the background
  the first fitted) end at 1.18 %, three at 1.10 % with bands 0.94 0.87 0.94
  1.04 1.01 1.16 1.05. One stage seeded at the Rietveld fit's own background
  ends at 1.09 %. The seed here is 346 counts against a true background of
  580 at 140°. This differs from the case 1542 was filed on
  in one respect: there the free intensities absorbed a hump and Rwp *fell*;
  here a low pedestal seed leaves Rwp *above* the structure's, so the finding
  1542 task 3 designs should fire on the background having moved a long way
  from its seed across stages, not only on a width growing. It also sharpens
  task 4: the comparison of protocols should include "partition again after
  the background solve", since a second stage does it for free.
  Not tested: the reporter's second observation, that a `profile_only` run on
  the pattern's own passes rises 1.72, 1.81, 1.82, 1.82 %. It is the same
  seed in the first pass, but the rise across passes was not reproduced.
  Checked against the tree at 5d1f5f67: reproduced to the digit. Rietveld
  0.0109; Le Bail 0.0456 / 0.0163 / 0.0162 at 3 / 100 / 400 cycles; Pawley
  0.0106 (the reporter's script, 5 s on this machine). `lebail_update` runs at
  stage start (`refine.py:3565`, on `table.x0()`) and after the solve
  (`refine.py:3864`); the reported Rwp equals the one recomputed from the
  returned `y_calc` (0.0163 both). No other open WP owns
  it: 1323 (the stop rule) is shipped, 1511 chooses between cells and 1545 is
  the notebook that reproduces the 03 case.

- **2026-10-05, from the issue triage (issue #725): a second user asks for
  §2 rule 5 as `auto_background`'s default, and the proposed default is the
  start of this WP's own failure.** The proposal: `auto_background(data, …,
  seed=True)` sets the Chebyshev constant term, or every P-spline
  coefficient, to a low percentile of y_obs over the fitted range; `seed=False`
  keeps today's zeros; the skill rule becomes "seed it yourself only for a
  hand-built background". Not proposed: seeding inside the Le Bail stage.
  Evidence: a CW neutron showcase run (λ ≈ 2.4 Å, FWHM ≈ 0.5°) whose unseeded
  first pass sent every TCHZ term to its bound and whose seeded run did not;
  not reproduced on lab silicon by the reporter. *Checked at `32ef5a6`*:
  `auto_background` returns all-zero coefficients for both kinds (15 P-spline
  and 5 Chebyshev on the issue's silicon, 5th percentile 893 counts), and the
  first `lebail_update` runs at stage compile on `y_obs − 0`. *Superseded in
  part 2026-11-03: the seed landed as an opt-in (PR #744), and task 4 measured it.* Task 4 should
  measure this seed beside the SNIP-held protocol, on the hump fixture and a
  high-pedestal one. Whether a default changes is the maintainer's.
- **2026-10-13, from the issue triage (#725): the showcase pattern cannot be
  shared, and the PbSO₄ neutron histogram is offered instead.** Posted
  2026-10-12: the run where the TCHZ terms went to their bounds is not the
  reporter's to share, and they offer the CW neutron histogram of
  `tests/data/gsas2_pbso4.gpx` as task 4's public high-pedestal case, beside
  #744's synthetic. Checked against the tree at c3d0367: the file holds
  `PWDR PBSO4.CWN Bank 1` (λ = 1.909 Å, the reporter's "D1A") and
  `PWDR PBSO4.XRA Bank 1`. It shows the pedestal going to the reflections
  (the 2026-10-11 entry from #726 above), not TCHZ terms reaching their bounds,
  so it is a fixture for task 4 and not a reproduction of that run.

- **From WP-2002 (2026-10-19, PR #1050).** Batch class B11. GSAS-II's stand-alone `DoLeBail` runs 10 cycles by default (`GSASIIstrMain.py:761`), and FullProf's manual says "a few cycles (say 10)". On #740's pattern the Le Bail fit plateaus at Rwp 1.62 % from 100 to 400 cycles, against 1.09 % for the true structure (`2002-batch/i740.json`). More cycles close the 4.56 % to 1.62 % gap and not the rest. The batch proposed a converge-with-cap cycle rule inside this WP. *Ruled 2026-10-19: agreed. It is task 7, added 2026-11-05.*

## Non-goals

- The alternation's stop rule and keep-best (WP-1323, shipped).
- A too-flexible background, which `BACKGROUND_ABSORPTION` already measures.

## Tasks

- [x] Reproduce on a fixture the tree can hold: a synthetic pattern with a
      broad hump under the peaks, Le Bail from a low-percentile seed. Record
      the background's movement from its seed and the width terms per pass.
      `tests/test_lebail_background_hump.py`; numbers in the 2026-11-03 entry.
- [x] Name the test for "the background never left its seed while a width
      grew", with where its threshold comes from (measured here or quoted).
      *2026-11-03: the named test did not reproduce, and no statistic measured
      separates the hump from the benign pedestal.* **Closed without a test,
      2026-11-03, by the maintainer's ruling on Q1** (no finding; second
      2026-11-03 entry).
- [x] A finding that names it, on the Le Bail path at least. **Closed
      without a finding, 2026-11-03, by the maintainer's ruling on Q1.** The
      skill's held-SNIP rule and the starting-model plot carry it.
- [x] The protocol: whether the Le Bail call should start from a SNIP estimate
      held under a low-order Chebyshev, as a default or as the skill's rule.
      Measure both on the fixture before choosing. *The skill's rule, settled
      by Claude under the measurement (2026-11-03 entry).* **Q2 ruled
      2026-11-03 by the maintainer: `auto_background`'s `seed` default stays
      `False`**, under DESIGN.md § Rules, Rule 4. `seed=True` stays an opt-in.
- [x] Skill: SKILL.md §2 rule 5 and `references/judging.md` name
      `rietx.background.snip` and this failure.
- [x] Tests, with obs/calc/diff PNGs to `tests/output/`.
- [x] The Le Bail cycle count converges under a cap (WP-2002's class B11, ruled
      2026-10-19, `docs/wp/2002-batch/rulings.md`). Each stage repeats its
      partition until the relative change falls under a tolerance, in place of
      the fixed `lebail_cycles` = 3. Judge it against #740's true-structure Rwp
      (1.09 %), never against 100 cycles. The `_audit` row
      `StageSpec:lebail_cycles` cites this WP. It moves Le Bail numbers, so it
      goes through the reader-output check. **Landed 2026-11-05 on PR #1434:** a
      cycle's share of the Bragg counts ≤ `lebail_tol` = 1e-7 under a cap of
      `lebail_cycles` = 25 000.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_lebail_alternation.py tests/test_background_auto.py tests/test_skill.py tests/test_lebail_background_hump.py tests/test_lebail_cycles.py
.venv/bin/python -m ruff check src tests examples
```

On the hump fixture, the protocol's fit leaves the hump in the background,
with the width terms within their no-hump values. The low-seed fit reports
no finding, by the maintainer's ruling of 2026-11-03 on Q1.

## References

- WP-1323 (the alternation; this was its Inherited entry), WP-1055
  (`FitReport.background`), WP-1454 (λ against the data).
- Ryan, C. G. et al. (1988). *Nucl. Instrum. Meth.* B34, 396 — SNIP, as
  `rietx.background.estimators` cites it.

## Handover log

- **2026-11-05** — ghostshift runner, PR #1434. A Le Bail stage no longer stops
  after three cycles. It repeats its partition until one cycle moves less than
  1e-7 of the Bragg counts, under a cap of 25 000 cycles. Task 7's yardstick holds:
  #740's pattern ends at Rwp 1.07 % against 1.09 % for the true structure, where
  three cycles left 1.61 %, and its cell comes within 4.6 ppm of truth where three
  cycles left 34.9 ppm. Most patterns pay up to 2.1× in wall clock, and BT-1 LaMnO3
  pays 150× (0.45 s to about a minute). The stop measures how fast the intensities
  move, and on FAP that leaves one near-degenerate pair unsettled, 1.23 σ at that
  peak and 0.001 esd in the answer. So the tolerance sits at tier 3 with FAP as its
  stated failing case. It waits on the maintainer's approval, with two other
  questions below.

  *The ruling.* WP-2002 class B11, `docs/wp/2002-batch/rulings.md`: "agreed (Le Bail
  converge-with-cap in WP-1542; budgets treated as not affecting the answer once a
  test confirms the margin under both solvers)". Its recommendation: "repeat until
  the intensities stop changing, with a cap, built in WP-1542". The batch's option 3
  reads "judged against the true-structure Rwp and not against 100 cycles".

  *Done.* The convergence test is
  Σ_k A_k|ΔI_k| / Σ_k A_k I_k ≤ `Stage.lebail_tol` (1e-7), where A_k is the counts a
  unit intensity lays on the pattern. The sum is read off a plain cycle. The cap is
  `Stage.lebail_cycles` (25 000). A cut partition in the last stage warns
  `LEBAIL_CYCLES_AT_CAP`. `tol=0` is an exact fixed count, bit-identical to the old
  loop, and `lebail_cycles=3, lebail_tol=0.0` is the way back. `NodeAction` keeps
  3 / 0.0 as its defaults, so an old node replays what it ran. Plain cycles need
  thousands of repeats because the update is a Richardson-Lucy step, so
  `forward._settled_partition` accelerates it with SQUAREM S3 (Varadhan & Roland
  2008) under the package's own step bound. Partitions stay between solves, so
  frozen-per-stage holds, and a cancel is read between cycles. New record fields are
  `StageResult.lebail_cycles_run` and `.lebail_settled`, and `Stage`, `StageSpec` and
  `NodeAction` gain `lebail_tol`. `sequential._collapse` takes the plan's tightest
  positive tolerance.

  *Measured: the tolerance* (`[dev]`, macOS arm64; machine load 50-67 from other
  runners, so seconds are loaded). Bar 1 of `tests/test_window_domain.py`, max|Δy|/σ
  at fixed parameters ≤ 0.1, from a flat start against a 1e-10 reference:

  | Pattern | 1e-6 | 1e-7 | 1e-8 | cycles at 1e-7 |
  |---|---|---|---|---|
  | #740 | 0.237 | 0.027 | 0.003 | 515 |
  | #740 at 2 % scale | 0.036 | 0.005 | | 671 |
  | BT-1 LaMnO3 | 0.147 | 0.015 | 0.000 | 12 293 |
  | FAP | 0.101 | 0.011 | 0.001 | 350 |
  | corundum | 0.003 | 0.000 | | 44 |
  | 11-BM NAC | 0.000 | 0.000 | | 8 |
  | LaB6+cBN | 0 | 0 | | |

  1e-7 is the largest decade under the bar on all seven from flat. From the fit's own
  intensities (warm) it reads 0.029 on #740, 0.001 at 2 % scale, 0.000 on corundum and
  NAC. **FAP fails warm at 1.23**: reflections 5 0 6 and 10 -5 0, d 0.9371 and
  0.9372 Å, swap over 3044 further cycles (I 0.14 → 56.7 and 46.7 → 1e-10), Rwp
  10.108 → 10.103 %. At 1e-8 FAP still reads 0.554, and LaMnO3's cycles more than
  double (28 259). A stop on estimated distance (Aitken, s₂²/(s₁−s₂)) left FAP at
  1.23, so it was dropped. Bar 2, 0.1 plain esd off the background against 1e-9:
  #740 0.023, FAP 0.001, corundum 0.000. At 2 % scale the plan alone ends 0.40 apart
  between two settled tolerances and 0.006 once polished, so that row needs the polish.
  On that pattern two starts settle 1.38 σ apart, so no tolerance closes such a pair.

  *Measured: the cap.* Dearest partition in a fit: 8495 on LaMnO3, 1088 on #740, 161
  on FAP. From a flat start: 12 293 on LaMnO3. 25 000 is twice that.
  `test_the_tolerance_meets_its_bar` asserts 2× on six patterns.

  *Measured: three cycles against the stop* (Rwp old → new, wall old → new, largest
  and total cycles, worst non-background move from three cycles):

  | Pattern | Rwp % | wall s | cycles | worst move, esd |
  |---|---|---|---|---|
  | LaB6+cBN | 13.921 → 13.921 | 0.40-0.50 → 0.44 | 11 / 75 | 0.003 |
  | 11-BM NAC | 14.358 → 14.358 | 0.53 → 0.45-0.53 | 23 / 117 | 0.004 |
  | corundum | 15.160 → 15.179 | 0.23-0.26 → 0.33 | 41 / 240 | 1.622 |
  | #740 at 2 % scale | 4.758 → 4.680 | 0.10 → 0.17 | 182 / 933 | 2.545 (cell b) |
  | #740 | 1.607 → 1.066 | 0.12 → 0.25 | 1088 / 2448 | 25.2 (cell b) |
  | FAP | 10.237 → 10.108 | 1.8 → 3.2 | 161 / 732 | 0.783 |
  | BT-1 LaMnO3 | 19.164 → 17.299 | 0.44 → 63-83 | 8495 / 26 406 | 12.8 (cell b) |

  *Measured: acceptance rows and goldens.* No number was re-pinned, and every
  assertion holds.

  | File | Row | Old | New | Bar |
  |---|---|---|---|---|
  | `tests/test_acceptance_nac.py` | Le Bail Rwp | 14.35836 % | 14.35812 % | < 20 % |
  | same | Le Bail a | 10.2512133 Å | −2.5e-9 Å | ±5e-4 of the Rietveld a |
  | same | Rietveld after it, Rwp | 9.28766 % | +7.6e-12 % | < 12 % |
  | `tests/test_acceptance_srm676a.py` | Le Bail Rwp, either setting | 14.43352 % | 14.43286 % | < 25 % |
  | same | R setting a | 5.1272494 Å | −2.9e-6 Å | within 1e-5 relative of the H setting |
  | same | R setting α | 55.2874689° | +6.8e-5° | ±0.02° of certificate |
  | same | H setting a, c | 4.7578039, 12.9879977 Å | +2.7e-6, −1.3e-5 Å | 1e-3 of certificate |
  | `tests/test_backend_shim.py` | `toy_lebail` golden | | unchanged | fixed `n_cycles=3`, bit-identical |

  The extinction screen keeps three fixed cycles, so its rows do not move. No
  ordinary test pin moved either. `tests/test_textdoc.py`'s non-default dictionary
  gained `lebail_tol`.

  *Measured: the Pawley seed.* It stays 3. Under LM a 300-cycle seed against 3 moves
  0.000 esd, 0.000 σ and under 2e-8 of the largest intensity on #740, its 2 % scale,
  corundum and FAP. **Under TRF on FAP it fails**: 3 cycles stop at Rwp 8.17 %, 300
  reach 7.87 %, 8.8 esd apart. So `PAWLEY_SEED_CYCLES` is tier 3 with that failing
  case, and the finding went to WP-2062.

  *Measured: the step bound's factor* (total cycles in a fit, at 2 / 4 / 8). #740
  2127 / 2433 / 5133, its 2 % scale 933 / 930 / 939, corundum 228 / 240 / 225, NAC
  123 / 117 / 117, FAP 1356 / 732 / 750, LaMnO3 22 974 / 27 945 / 26 913. Only 4, the
  package's default, stays within 1.25× of the best on all six. The factor picks the
  path, so at 2 and 8 #740's 2 % scale lands 1.25 esd away (Rwp 4.697 against 4.680 %)
  and at 2 FAP's pair swaps early. That is the tolerance's failing case seen from
  another side.

  *Rejected.* Anderson acceleration in log intensity: at most 2×, nothing on
  corundum. A sparse matrix-vector partition: `add.at` 5.4 ms against `bincount` 6.8 ms
  on FAP's 1.7 M window points. Unbounded SQUAREM: it dropped every landing for
  hundreds of rounds on FAP, found when a probe hung.

  *Review.* `/code-review` ran on the mechanism, and its fixes are one commit: an
  unused import, the silence pair, a false cap warning (now the returned `settled`),
  `_collapse`'s pairing of tolerance and cap, the cancel check inside partitions, and
  the docs of `lebail_cycles_run`. It also found FAP, which became the failing case.
  Declined: none. Not fixed, and put to the maintainer below: `_final_compile` carries
  intensities onto the result's windows unpartitioned, so a one-channel window change
  splits a near-overlap differently (1.6 σ on #740 until the next partition).

  *Not generalised.* `report.schemas.LEBAIL_GAP_CYCLES` stays 5 plain cycles from
  flat, because it measures a gap at a frozen state and is tier-tracked apart. `api_call`
  renders no `lebail_tol`. `suggest`'s probe uses `Stage` defaults with no cancel token.
  The `Stage` dataclass does not refuse a negative `lebail_tol`, though `StageSpec` does.
  An old stored plan with `lebail_cycles: 3` reads as a cap of 3 under the
  new tolerance and warns.

  *Settled by Claude, for the maintainer to reverse.*
  - The extinction screen holds at three fixed cycles until WP-2062 retires it, on the
    grounds in its audit row. A settled partition failed 10 rows of its margin and
    gate tests. The alternative was to re-measure those margins now, for a method the
    screen is about to leave.
  - The Pawley seed holds at 3, on the LM measurement above. The alternative was a
    longer seed that would cure FAP under TRF and cost every index validation.
  - The share stop stays over a distance estimate, on the FAP measurement above.
  - SQUAREM S3 with the package's bound, over plain repetition (355 s on LaMnO3 at
    1e-6) or Anderson.
  - `tol=0` is the way back, in place of a mode flag, because a fixed count is then
    one setting and replays old nodes bit-identically.
  - This WP stays 🔄 with its tasks ticked until the questions below are ruled,
    because closing moves the record into the release narrative and a reversal would
    reopen it.

  *Generality.* the judge's report, unedited, then the author's answers.

  Tables are cut to the questions with findings, to fit the 500-word cap. All findings come from reading; nothing was run.

  ## LEBAIL_CYCLES_AT_CAP
  **weak.** The case for reporting is strong, but the code can miss a real cut.

  | Q | Author | Found | Verdict |
  |---|---|---|---|
  | 1, 7 | "fires exactly when … lebail_settled is False on the last stage" | `/Users/yue/Code/rietx/.claude/worktrees/agent-a28a4f0420048955b/src/rietx/refine.py` overwrites `lebail_settled` after the solve. If the pre-solve partition, which the solve fits against, is cut and a warm restart meets the rate test, it reads True and nothing fires. | gap |

  Flips: a test of that sequence firing the code.

  ## LEBAIL_CYCLES_AT_CAP.suggestion
  **weak.** The row understates the printed text.

  | Q | Author | Found | Verdict |
  |---|---|---|---|
  | 3 | "names the stage setting" | It also prints "The cell is usually the last thing to suffer". None given; the test only checks a suggestion exists. #740 (synthetic pattern) at 3 cycles: cell 34.9 ppm off, against 4.6 settled. | fails |

  Flips: measuring that order, or cutting the sentence.

  ## SCREEN_LEBAIL_CYCLES
  **weak.** Keeping 3 is reasonable; the record is thin.

  | Q | Author | Found | Verdict |
  |---|---|---|---|
  | 5, 6 | "no stated source"; a settled partition "failed 10 rows" | Tier 3 fits. No failing case or family count. `approved` borrows ruling B11, which never exempted the screen. WP-2062 (moves it to Pawley) is unscheduled. | gap |

  Flips: the maintainer's own approval, with a failing case.

  ## LEBAIL_INTENSITY_FLOOR
  **holds.** A numerical floor, tier 1, and tested. Case against: none found.

  ## SQUAREM_STEP_GROWTH, with the steplength bound
  **weak.** A bound is earned; 4 and tier 2 are not.

  | Q | Author | Found | Verdict |
  |---|---|---|---|
  | 5 | "mstep = 4, the default of … R package SQUAREM" | Tier 2 wants a citation that tested it, or a default of the seven programs. This is neither. No other value measured. CRAN claim not checked here. | weak |
  | 3 | "never the fixed point" (docstring) | The stop reads rate, so where it lands follows the path: the row's two starts differ by 1.38. | weak |

  Flips: other factors run on the six patterns, then tier 1.

  ## PAWLEY_SEED_CYCLES
  **weak.** The measurements favour it; the test does not carry them.

  | Q | Author | Found | Verdict |
  |---|---|---|---|
  | 5 | Four patterns, "identical evaluations", plus the named test | The test runs #740 at full scale, which is not among the four. It asserts no evaluation count. "Under both solvers" (B11): default only. | weak |
  | 3 | "the joint solve refines the seed" | `build_pawley_restraint` scales equal-split rows by the seeded group mean. The test never compares off-table intensities. | gap |

  Flips: seed invariance of overlapped intensities across families.

  ## StageSpec:lebail_tol
  **holds.** Failing case named, alternatives tried. The number is the maintainer's.

  | Q | Author | Found | Verdict |
  |---|---|---|---|
  | 3 | FAP (fluorapatite) 1.23σ, answer 0.001 esd | Neither bar measures a near-overlap's split, which `SolveCost.from_pawley` reads. | gap |
  | 6 | "five families" | Four: #740 counts twice. Development status: none given. LaB6+cBN is not in the test. | gap |
  | 4 | Cell 4.6 against 34.9 ppm; 150× cost on LaMnO₃ | The cell is the only truth reference; the rest verify against rietx's own tighter runs. | holds |

  Flips: the FAP pair's split measured.

  ## StageSpec:lebail_cycles
  **weak.** The cap is sensible; "invariant" overclaims.

  | Q | Author | Found | Verdict |
  |---|---|---|---|
  | 5 | "asserts 2x on six patterns" | FAP's strict xfail stops before that assert: five. The 12 293 (2.0×) is unasserted. | weak |
  | 3 | "a cap the stop reaches first" | Largest pattern: 329 reflections. B11 tiered this row 3; its budget clause meant iteration budgets. | weak |

  Flips: a dense pattern inside the cap, or tier 3.

  ## StageResult.lebail_cycles_run
  **holds.** Arithmetic.

  ## StageResult.lebail_settled
  **holds.** Its `None` is honest. It covers the last partition only.

  ## Three-cycle guard
  **holds.** Arithmetic, tested.

  ## sequential._collapse
  **holds.** Tested. Series cost: none given.

  ## tol=0
  **holds.** The caller's choice, recorded as `None`, tested.

  *The author's answers, the reader-facing ones first.*
  - Suggestion (**fails**): the sentence is cut.
  - `LEBAIL_CYCLES_AT_CAP`: fixed. `lebail_settled` now covers every partition of the
    stage, and a test runs that sequence.
  - `SCREEN_LEBAIL_CYCLES`: left so, for a method WP-2062 retires. It is under *Settled*
    above, and question 1 on the PR covers its `approved` date.
  - `SQUAREM_STEP_GROWTH`: 2 and 8 measured on six patterns, above. It stays tier 2,
    because the factor picks the path and so is not tier 1. The row gives the measurement.
  - `PAWLEY_SEED_CYCLES`: measured under both solvers, which found the TRF failing case.
    Tier 3 now, and the test asserts the intensities.
  - `StageSpec:lebail_tol`: both gaps are in the row. The FAP pair's split is measured: it
    moves (I 0.14 → 56.7), and the answer moves 0.001 esd.
  - `StageSpec:lebail_cycles`: the assert now runs before the bar and covers the fresh
    partition. The row states its domain, and past it the warning reports a cut. It stays
    invariant, because a cut is reported rather than silent. Tier 3 is the alternative,
    and that is the maintainer's to pick.

  *Counts.* COUNTS

  **Next**, for the maintainer on PR #1434, in order:
  1. Approve `lebail_tol` = 1e-7 at tier 3 with FAP as its failing case and LaMnO3's
     cost, or pick 1e-8 and pay more than double on LaMnO3 with FAP still at 0.55.
     The row's `approved` date is the ruling on the rule, so an approval moves it.
  2. Rule each reader-output line in the PR's *What a reader receives*.
  3. Decide whether the result's final compile should re-partition. That closes the
     1.6 σ gap and changes what every Le Bail fit returns.
  Then close this WP and move its record to the v1.12 record.

- **2026-11-05** — close-out runner, PR #1430. This WP stays open. Its six
  listed tasks are done, but the maintainer ruled on 2026-10-19 that a Le Bail
  stage's cycle count should converge under a cap "in WP-1542", and that work
  never became a task. The tree still runs a fixed three cycles. A caller who
  picks `mode="lebail"` meets the cost: on #740's pattern three cycles end at
  Rwp 4.56 % and the plateau is 1.62 %. It is now task 7.

  *How it was missed.* The Inherited entry from WP-2002 still read "pending the
  ruling", though the ruling had come the same day. The 2026-11-03 entry's "no
  task is open" counted the list as it stood. The audit row is the live claim:
  `StageSpec:lebail_cycles`'s grounds read "Kept at 3 until WP-1542 replaces
  it", `approved="2026-10-19"`. `model.lebail_update` still loops `n_cycles`
  times with no tolerance (read at 541f0daf7).

  *Why it stays open rather than moving.* The ruling names this WP. The
  2026-11-01 decision that no default path runs Le Bail moved this WP to P3 and
  reversed nothing, as WP-2062's decision 4 says. Settled by Claude under the
  job's rule that an unfinished WP stays open. The alternative was to close and
  forward task 7 to WP-2062, which would have reassigned a ruling.

  *Verified.* The Acceptance rows pass on this branch: 259 passed over
  `test_lebail_alternation`, `test_background_auto`, `test_skill` and
  `test_lebail_background_hump` (`[dev]`, macOS arm64, 4 workers, another
  worktree's tests beside them). Nothing else in this WP changed. Inherited
  stays as it is while the WP is open.

  Next: task 7. Then, at its close, the held SNIP and a declared background
  peak on PbSO₄ and #726's pattern go to WP-2017, and #740's mechanism goes to
  WP-2062, unless a session runs them here first. A withdrawn ruling would
  close this WP instead, with the audit row's grounds rewritten.

- **2026-11-03** — The maintainer ruled both questions of the entry below, in
  chat (recorded by a ghostshift runner). The Le Bail path gets no finding for
  a background left at its seed. `auto_background` keeps `seed=False` as its
  default. WP-1542 has no maintainer question left open. Tasks 2 and 3 are
  closed by the Q1 ruling, and task 4's note states the Q2 ruling.

  *Q1, ruled: no finding.* The skill's held-SNIP rule carries the failure
  (SKILL.md §2 rule 5, `references/judging.md`). So does the starting-model
  plot, `data.plot(model=ref)` (WP-2039). Grounds: none of the three fit-based
  tests measured below separates the hump fit from the benign pedestal fit.
  The one data test that does separate them is `amorphous_hump_score`. On 30
  real patterns it tracks lab against synchrotron data (its `_audit.py` row,
  `HUMP_TRIGGER`). A finding keyed on it would rest on one synthetic fixture.
  What would reopen Q1: a statistic that separates the two cases on real
  patterns (PbSO₄ neutron, #726's lab pattern). WP-2062 putting Le Bail back
  on a default path would reopen it too.

  *Q2, ruled: the `seed` default stays `False`.* Grounds: DESIGN.md § Rules,
  Rule 4's test for a new default. A data-derived start is not Rule 1's
  kind 1, because a competent dissent is named. All seven surveyed programs
  start the background from zero, a constant or the user's numbers
  (`docs/practice.md`, the `auto_background:seed` row). Rule 4 also excludes
  Rwp comparisons as evidence. That leaves #744's width number alone: the
  Lorentzian X at 0.0565 unseeded against a true 0.001. `seed=True` stays an
  opt-in. The #1286 ruling already seeds the held extinction screen.

  *#725 and #833.* The 2026-10-08 entry says "#725 stays open on whether it
  moves". That question is now answered: the default stays. #833's third
  item asked the same and has the same answer. Closing or commenting on
  either issue is for the lead's batch.

  *For whoever next touches DESIGN.md.* § Background subsystem describes a
  two-stage default. A robust estimate comes first. Then either the estimate
  is held under a Chebyshev, or a P-spline is co-refined. The section does
  not say whether the P-spline starts from the estimate. In the code it starts
  at zero. This ruling reads "start from the estimate" as the v0.1 path only.
  DESIGN.md is not edited here.

  *Next:* the held SNIP and a declared background peak
  (`instrument.extra_components`) on the PbSO₄ neutron histogram and #726's
  lab pattern (Inherited), scored against a reference over the whole range.
  That is what would lift SKILL.md rule 5 off tier 3. No task is open
  beside it.

- **2026-11-03** — PR #1357 (ghostshift runner). The failure now has a
  fixture in the tree, and the skill has a protocol that fixes it on that
  fixture. A Le Bail fit seeded at a low percentile under a broad hump ends at
  Rwp 9.37 %, with part of the hump handed to the reflections. Holding a SNIP
  estimate under a 4-term Chebyshev ends at 4.41 %, against 4.07 % for the
  true background held, with every width as it is without the hump. The
  finding the WP asked for is not built. Its named test did not reproduce,
  and none of three statistics measured here tells the hump case from the
  benign one, so whether a finding exists at all goes to the maintainer (Q1).

  *Done.* `tests/test_lebail_background_hump.py`: the Pnma neutron pedestal
  pattern of `test_auto_background_seed.py` plus a Gaussian hump (600 counts
  at 50°, σ 6°), four tests, eight PNGs. SKILL.md rule 5 and judging.md
  § rules 4-5 name `rietx.background.snip`, the held protocol, its window and
  the failure; two paragraphs of that section were tightened to pay for it,
  since judging.md sat 7 B under its budget and the body 12 B. The
  `BackgroundFixedPlusChebyshev` docstring named `rietx.background.estimate`,
  which does not exist; it now names `snip` and `arpls` (a sweep of every
  `rietx.background.*` name in `src`, `docs` and `tests` found no other).
  Inherited pruned: the WP-1545 and WP-1930 entries are deleted, since both
  were about the indexer's Le Bail validation, which is Pawley since
  WP-2011; the #725 entry is marked superseded in part.

  *Measured* (macOS arm64, `[dev]`, one `profile_only` Le Bail pass from the
  true cell and widths; Rwp, background over the truth at 50°, Lorentzian X
  ± esd, true X 0.001):

  | protocol | hump | no hump |
  |---|---|---|
  | P-spline at 0 | 10.13 %, 0.82, 0.072 ± 0.054 | 5.71 % |
  | P-spline `seed=True` | 9.37 %, 0.83, 0.048 ± 0.046 | 4.76 %, X 0 |
  | seed, 4 `lebail_passes` | 8.67 %, 0.82, 0.085 | — |
  | seed, 3 background stages first | 7.69 %, 0.85, 0.007 | 4.40 % |
  | seed, 5 background stages first | 6.32 %, 0.87, 0 | 4.33 % |
  | P-spline co-refined from a SNIP start | 6.26 %, 0.87, 0 | 4.32 % |
  | SNIP held, 15-point window, Cheb 4 | 4.41 %, 0.97, 0 | 4.28 % |
  | SNIP held, 30 points | 6.55 %, 0.87, 0 | 4.30 % |
  | SNIP held, 60 points (the hump's σ) | 20.9 %, 0.62, 0.33 | 4.33 % |
  | true background held, Cheb 4 | 4.07 %, 1.00, 0.006 | — |

  The mechanism. Each stage partitions the intensities against the
  background it starts from and holds them through its solve. So a stage
  closes about half of the background's remaining gap: 0.35, 0.64, 0.76, 0.81,
  0.84, 0.86 of the truth at 50° from the seed through the first five stages,
  and the same shape without the hump (0.60, 0.77, 0.87, 0.92, 0.95 at 140°).
  Every protocol that co-refines the background settles near 0.87 at the hump
  centre. In the seeded fit's zoom the three reflections at 49-54° are drawn
  at twice the observed height. The width growth the WP names is in the
  closing stage (X 0.0076 to 0.048) and is under one esd of X. This agrees
  with #740's reading in Inherited and with the survey's per-iteration
  re-extraction (2026-10-27 entry), which rietx does not do.

  *Q1, for the maintainer: should the Le Bail path carry a finding for this
  at all?* The Goal says the fit "says so". Three candidate tests were
  measured and none separates the hump fit from the benign pedestal fit.
  (a) The background leaving its seed: it leaves it in both (4.2σ rms in the
  hump's first stage, 2.4σ in the pedestal's). (b) A width growing: X ends
  at 0.048 ± 0.046, inside its own esd. (c) The alternation's next step,
  max shift/su of the background (one more background stage after the fit,
  against `MAX_SHIFT_CONVERGED`, 0.1 from McCusker 1999 §7): 1.0 on the hump,
  1.35 on the pedestal, 0.55 SNIP-held, 0.15 on 11-BM LaB6 + cBN, so it fires
  on every seeded fit. One test that does separate exists already and is not
  a fit test: `diagnose(data).amorphous_hump_score` is 0.23 on the hump and
  0.032 on the pedestal against `HUMP_TRIGGER` 0.05. Options: no finding, the
  skill rule and the starting-model plot (2026-10-24 entry) carry it; a
  finding on a Le Bail fit with a co-refined background where the hump score
  is over its trigger, pointing at the held SNIP; or (c), which reports that
  nearly every seeded Le Bail fit has not converged its background. Each new
  finding changes what a fit prints, so it comes to you under the
  reader-output rule anyway. Lean: no finding yet. The hump score's audit
  row (`_audit.py`) says that on 30 real patterns it separates lab from
  synchrotron data and does not detect a hump, so a finding keyed on it would
  rest on one synthetic fixture.

  *Q2, for the maintainer: does `auto_background`'s `seed` default move?*
  The 2026-10-06 ruling kept `seed=False` until these numbers existed. They
  favour the seed on both fixtures (hump 9.37 % against 10.13 %, pedestal
  4.76 % against 5.71 %), and a held SNIP beats both. A default change moves
  every fit that calls `auto_background`, so it is yours and goes through the
  reader-output gate.

  *Settled by Claude under the measurement:* the protocol is the skill's rule,
  not a package default. The held SNIP needs a window sized to the peaks
  (15 points good, 60 points worse than any seed), which the caller knows and
  a default would have to guess. The alternative, a default inside
  `fit(mode="lebail")`, is reversible but moves every Le Bail number.

  *Not generalised:* the class is "a stage partitions against a background it
  then moves". The same frozen partition governs the widths and the cell, and
  the indexer's former Le Bail validation and the extinction screen are its
  siblings. Not measured here: the validation is Pawley since WP-2011, and
  the screen moves to Pawley under WP-2062. Pawley's seed partition is one Le
  Bail pass but its intensities refine jointly afterwards, so the lag does not
  carry. The PbSO₄ neutron and #726's lab patterns (Inherited) were not run.

  *Also cut from judging.md:* rule 4's per-pass Rwp sentence (11-BM LaB6 +
  cBN, 16.821 / 16.907 …). It was stale: WP-1930 moved that pass 1 to
  14.220 % (`tests/test_lebail_alternation.py`'s docstring), and WP-1323's
  file keeps the original numbers.

  *Review* (`/code-review high`, ten findings). Fixed: the width check now
  asserts both fits free the same widths and fails on the 60-point window's
  X; the `hump` consumer carries the module's `xdist_group`; the builders are
  imported from `test_auto_background_seed.py`, so "the same pattern" is
  structural; six PNGs instead of eight, and the module says why it is not
  `slow`; the acceptance command runs the new file; the docstring is
  rewrapped; the window number is back in judging.md beside its bounds.
  Declined: the finding that the width bar cannot fail for the seeded fit.
  It cannot, and that is Q1(b)'s measurement; the test's docstring says so.
  Declined: naming the hump score in rule 5, for the audit row's reason above.

  *Generality* (`generality-review`, on the skill rule; summarised). Item 1,
  SKILL.md rule 5: **weak**. Tier 3, one synthetic family with a truth plus
  the private run judged by Rwp; no outside source holds a background under
  Le Bail; the cause is partly rietx's own (every surveyed program
  re-extracts per cycle, `docs/practice.md` § Structure-free fitting); GSAS-II
  users declare an amorphous hump as a background peak; the agent gets no test
  for "a broad hump". Item 2, judging.md: **fails as written**, for quoting Rwp
  as its evidence, a window number from one fixture, and a snippet without
  `source=`. *Author's answer:* item 2 now quotes the background-over-truth
  ratios rather than Rwp, passes `source="snip"`, and states the window with
  the measured point where the gain is lost (6 FWHMs). The window stays a
  number, because `snip` needs one and the 60-point case shows the natural
  guess failing. Item 1 stands as a tier-3 rule with its evidence tagged;
  what would lift it is the held SNIP on PbSO₄ and #726's lab pattern,
  scored against a reference over the whole range, and a declared background
  peak (`instrument.extra_components`) tried on the same fixture.

  *Gates* (macOS arm64, `[dev]`, another shift sharing the machine). Fast
  selection, on the tree before the review fixes: 13603 passed, 319 skipped,
  34 xfailed, 1 failed in 14:59. The failure is
  `test_display.py::test_a_plot_in_a_kernel_shows_once_and_leaves_the_backend_alone`,
  whose Jupyter kernel spec points at a deleted venv on this Mac (environment,
  not this branch). The four added tests cost 5.1 s there, all in the shared
  fixture. After the fixes: the touched files and the skill suites, 235
  passed; `test_docs_consistency.py` 25 passed; ruff clean;
  `tests.reader_output` unchanged. Full suite not run: the change moves no
  package number.

  *Gotchas.* `judging.md` and the skill body both sit at their budgets, so
  the next skill edit in this section pays with a cut. `run_stage` after a
  Le Bail `fit` re-partitions at its start, and its Rwp can come back above
  the fit's (7.69 % to 9.90 % on three background stages), so do not use it
  as a cheap "one more alternation step".
  *Next:* the maintainer's Q1 and Q2; then tasks 2-3 as Q1 decides; then
  the held SNIP and a declared background peak on PbSO₄ and #726's pattern
  (Inherited), which is what would move the skill rule off tier 3.

- **2026-10-06** — Maintainer decision on #725, through draft PR #744:
  `auto_background(..., seed=True)` is wanted as an option, and the default
  stays `seed=False` (all-zero coefficients). Whether the default ever
  changes still waits on task 4's measurement of the seed beside the
  SNIP-held protocol, on the hump fixture and a high-pedestal one. #744's
  synthetic (a pedestal under peaks 22 times higher, Le Bail
  `profile_only`) is that high-pedestal fixture: Rwp 0.0605 unseeded against
  0.0437 seeded, and the Lorentzian X 0.0565 against 0.0 (true 0.001).
  *Recovered 2026-10-10: committed after PR #796 merged, so it reached main
  only now.*

- **2026-10-03** — filed from WP-1323's Inherited entry when 1323 closed. No
  open WP owns a too-stiff background: the open rows of the index carry no
  Le Bail or background protocol, and 1530's held background is a TOPAS
  reader's. *Next:* task 1.
- **2026-10-08** — #725's proposal landed from outside as an opt-in: PR #744
  (head `ecea30f4`), merged as `ba732997` by `/pr-review` after three rounds.
  `auto_background(data, seed=True)` starts the Chebyshev constant term, or every
  P-spline coefficient, at a low percentile of y_obs over the fitted range.
  `seed=False` is the default and keeps today's zeros. SKILL.md §2 rule 5 and
  `references/judging.md` now name the call in place of the hand recipe. The
  default is unchanged, and #725 stays open on whether it moves. *What it does
  not do:* none of this WP's tasks. A seeded background can still stay at its
  seed while a width grows, so tasks 1-3 measure what they did before. Task 4
  now compares this seed with the SNIP-held protocol rather than with a hand
  seed. *Gate:* stacked with #776, #746 and #801 on `5d1f5f67`; the results are
  in WP-1805's 2026-10-08 entry. The only slow failures are #820's, which also
  fail on `main`. *Gotcha:* `test_skill_claims.py` classifies every number in
  the skill body, so a rule-5 edit that drops a number must drop its row too.
  Round 2 caught that. *Next:* task 1.
