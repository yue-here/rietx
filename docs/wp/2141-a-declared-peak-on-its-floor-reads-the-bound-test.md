# WP-2141 — A declared peak on its floor reads the bound test

Milestone: unscheduled · Status: ✅ 2026-11-13 — closes in PR #1566; EXTRA_PEAK_NO_INTENSITY reads FLOOR_HIT under either solver and in a joint fit
Track: What fires, and what stays silent
Depends on: 1914 soft (PR #1506 lands the same reading for widths)

## Goal

`EXTRA_PEAK_NO_INTENSITY` fires where the package's one bound test (`staged.bound_findings`,
read as `FLOOR_HIT`) says a declared peak's area sits on its floor, under either solver and in a
joint fit.

## Context

- **What the code does.** `refine._extra_peak_diagnostics` decides "this declared peak has no
  area" with its own proximity test: `area <= 0` or `|area - lo| <= BOUND_HIT_RTOL·max(1, |lo|)`
  (`BOUND_HIT_RTOL` = 1e-10). The docstring calls this the bound test's distance "where no solve
  stands behind it". A solve does stand behind it here.
- **Why it can miss.** Since WP-1938 the default LM driver lands a floored value exactly on its
  bound, so the proximity test holds. TRF keeps its iterates strictly inside the bounds and stops
  just above the floor. WP-1914 measured that on a width: `gauss_size` stored 3.4×10⁻²⁴ deg²
  under TRF, read as a 4.3×10¹³ Å domain size while `FLOOR_HIT` beside it said the width was on
  its floor. An area stopped the same distance above zero escapes a 1e-10 window. Not measured on
  a declared peak.
- **Order in a joint fit.** `multi.py` calls `_extra_peak_diagnostics` inside its per-histogram
  loop (line 2508 on 2026-11-09), before `bound_findings` runs (line 2546), so the bound test's
  answer does not exist yet when the peak is judged. The single fit calls it from
  `_build_result` (`refine.py`, after the ticks); check whether the bound findings exist there.
- **The rule to follow.** Yue ruled on 2026-10-09 that a reading at a floor reads the flag ("read
  the flag", recorded in WP-1914's Inherited, from WP-1929). WP-1914's PR #1506 does that for
  widths: `microstructure_table(floors=)` reads a width named by `FLOOR_HIT` as `at_zero`, wired
  through `refine._build_result` and, for joint fits, `multi._hist0_floors`. `replay` runs no bound
  test, so it reads the recorded `FLOOR_HIT` diagnostics. Reuse that wiring once #1506 merges.
  Root CLAUDE.md states the same rule as an invariant: where a fact has a computing authority, a
  second surface is a projection of it, never re-derived.
- **Found by** WP-1914's sibling sweep (PR #1506, *Siblings*). No open WP owns extra peaks:
  WP-1103 (✅) shipped `PeakComponent`.
- **Tier.** No threshold of its own: the code stops using its own and reads the authority's,
  so it inherits the bound test's tiers. That is tier 1 on LM's exact active set and on the
  no-solve fallback (`BOUND_HIT_RTOL`), and tier 3 on the TRF path (`BOUND_HIT_ESD_FRAC`,
  `BOUND_HIT_COS_MIN`, approved 2026-10-19, a third-family TRF pass owed). Corrected
  2026-11-13 from "Tier 1" on the generality judge's reading.

## Non-goals

- `report/magnetic._width_support_findings`, which has the same shape (a 1e-12 proximity) but
  only picks which cause an info message names; magnetic-path decisions are Mike's.
- `EXTRA_PEAK_ON_REFLECTION`, the other half of the same function.

## Tasks

- [x] Read `FLOOR_HIT` (or `bound_findings` directly) in `_extra_peak_diagnostics`; keep the
      `area <= 0` clause for an area whose stated lower bound is below zero.
- [x] In the joint fit, run the bound test before the extra-peak diagnostics, or pass its
      findings in.
- [x] `replay` reads the recorded `FLOOR_HIT` diagnostics, as WP-1914's fallback does.
- [x] Tests: a declared peak with no feature under it, fitted under `lm` and `trf`, single and
      joint; the code fires in all four. Pin the rule, never where TRF stops.
- [x] Find the remaining siblings: any other reader deciding "on its floor" by its own distance.
      Fix the class or say which were left and why.
- [x] Skill: none; the code's row and suggestion are unchanged.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_extra_components.py tests/test_multi_diagnostics.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-1914 (PR #1506), WP-1929 (the bound test's active set), WP-1938 (native bounds), WP-1103.

## Handover log

- **2026-11-13** — The warning that a declared peak refined to no intensity now
  follows the package's own bound test, the same one that prints `FLOOR_HIT`, under
  either solver and in a joint fit. Before, it used a private distance window of 1e-10,
  which could disagree with the `FLOOR_HIT` line printed beside it under `solver="trf"`.
  Measured here, the gap is narrower than the WP feared: on the LaB6 fixture TRF stopped
  the area 1.9e-22 above zero, inside the old window, so the old code already fired there.
  The disagreement needs TRF to stop between 1e-10 and a hundredth of an esd above the
  floor. A stage stopped early does that (about 2e-5 at `ftol=1e-5`), and the tests now
  build that case, both end to end and as a unit row. One behaviour moved on purpose: an
  area held on a *positive* lower bound no longer reads "no intensity", because it still
  puts counts in the pattern; `BOUND_HIT` reports it instead.

  *Done.* `refine._extra_peak_diagnostics` takes `floors=` (the `FLOOR_HIT` paths,
  closed over ties by `floored_paths`) and fires on `area <= 0 or area_path in floors`;
  its `BOUND_HIT_RTOL` import is gone. `_build_result` passes the `floors` set it already
  built for the microstructure block, so `replay` reads the recorded `FLOOR_HIT`
  diagnostics through WP-1914's fallback with no new code. `multi._build_result` now
  computes per-histogram esds and the whole bound test (free and tied halves) before the
  per-histogram loop; the loop reads the slices, esds and floor sets built there once. The pre-loop uses `zip`, never a
  second `for h in range(n)`, because `tests/test_multi_diagnostics.py`'s meta-tests find
  the per-histogram loop by that shape. `_hist0_floors` became `_hist_floors(at_bounds, h)`.
  The help entry for the code names the floor test and says a TRF area can sit a hair
  above zero.

  *Measured* (`[dev]` venv, macOS arm64). Probe on `_clean_lab6()` with the peak at 43.5°
  (on a LaB6 line the phase already fits): area only freed, LM lands 0.0, TRF 1.89e-22,
  `FLOOR_HIT` on the area under both, esd 0.78. With centre and width freed too, TRF does
  not reach the floor at all: the centre walks to its bound (`BOUND_HIT`) and the area
  fits noise at 0.60 ± 0.45, with no `FLOOR_HIT` on it; the new rule correctly stays
  silent there. Joint fit, seeds 1 and 2: histogram 0 floors and fires, histogram 1 fits
  a 0.84 counts·deg excess at a free optimum and stays silent, under both solvers.
  `python -m tests.reader_output`: exit 0, unchanged against 8d87f1878.

  *Siblings.* Searched for readers deciding "on its floor" by their own distance. Left,
  with reasons: `indexing/pick.py` `no_intensity` and `indexing/diagnostics._at_zero`
  read the peak picker's own fitter, which runs no `bound_findings`, so there is no
  authority to read; `indexing/peakfit.py`'s position `at_bound` is the same fitter;
  `optimize/lm.py`'s `n_bound_hits` is a field nothing reads;
  `params.vector._floor_seed_target` acts on a start value before a stage rather than
  reading a fit, and TRF already moves a start strictly inside its bounds;
  `report/magnetic._width_support_findings` is this WP's non-goal (Mike's path).

  *Review.* `/code-review high --fix` found five issues and the session took four. The
  end-to-end tests passed on the pre-WP code, because TRF converged at the default ftol
  lands inside the old window: `_floor_plan` now stops the area stage at `ftol=1e-5` with no
  closing stage, where TRF leaves the area near 2e-5, and a deliberate revert of the
  `floors` clause failed both TRF cases. The joint fit had copied each correlation slice and
  built histogram 0's floor set twice; both are now built once. The joint test now plots.
  The help text's "at or below zero" case was added by this session rather than declined.

  *Counts* (`[dev]` venv, macOS arm64, through ghostshift's `serial.py`, so no other suite
  ran beside it): fast selection 14689 passed, 433 skipped, 32 xfailed, 10:04 wall clock on
  a shared machine. This WP adds 9 cases (5 + 2 + 2), all passes; no baseline was measured
  here, CI's is the comparison. Added-test cost from the local junit: 2.71 s for the
  single-fit pair, 1.57 s for the joint pair, 0.08 s for the five unit rows; 4.36 s in
  `tests/test_extra_components.py`, none in the slow tail. `python -m tests.reader_output`
  exit 0. Vale 0 errors; ruff clean.

  *Generality* (the `generality-review` judge's sections, unedited; dispatched although
  `tests.audit_delta` reported no table change, because the firing rule of a code changed):

  #### Item 1: `refine._extra_peak_diagnostics`, the test behind `EXTRA_PEAK_NO_INTENSITY`

  (`EXTRA_PEAK_NO_INTENSITY` is a warning that a declared extra peak refined to no area, so its centre is not a measurement. `FLOOR_HIT` is the diagnostic for a parameter whose lower limit of zero "carried load". It comes from `staged.bound_findings`, the package's single bound test. TRF is scipy's trust-region-reflective solver, which the caller opts into with `solver="trf"`; the default solver is LM.)

  **Verdict: holds.** The case for the change is stronger. It replaces the function's own distance test with the bound test the package already reports, and it fixes a false message on a positive lower bound. One correction: the author labels it tier 1, but its TRF branch now rests on two tier-3 constants.

  | Question | Author's answer (where) | What I found | Verdict |
  |---|---|---|---|
  | 1. What it decides unasked | WP Context: the old rule was "`area <= 0` or `\|area - lo\| <= BOUND_HIT_RTOL·max(1, \|lo\|)`". New docstring (`refine.py` ~10602): "'On its zero bound' is the package's one bound test, read rather than restated." | It decides when to warn that a declared peak has no intensity and its centre is "a walk rather than a measurement". It reports only and gates nothing (docstring: "Both **report and gate nothing.**"). Three behaviours change. (a) Under TRF, an area stopped just above zero now fires when `FLOOR_HIT` names it. (b) An area held on a positive lower bound no longer fires. `BOUND_HIT` (the bound diagnostic for any limit other than a zero floor) covers it. (c) A corner case is now silent: under TRF, an area within 1e-10 of zero where the residual is not pressing against the floor (cosine below `BOUND_HIT_COS_MIN`, 1e-4). The old rule fired there. The change neither names nor tests (c). | holds |
  | 2. Rule 1 kind | none given (the code's audit row, `_audit.py:691`, is still `unaudited`, with no `ambiguity`) | Kind 1. At zero area the centre's Jacobian column is zero, which is arithmetic. Whether the area *is* at zero is the bound test's verdict, which is also kind 1. The table has no row value to compare. | holds; no row to agree |
  | 3. Case against acting | none given | Against warning on a peak whose area the bound test puts on its floor: none found. Every refiner reads 2e-5 ± 0.8 counts·deg (the test fixture's TRF stopping point) as no intensity. Against the narrowing in (b), the old firing at a positive bound: none found. The old message there was false. It printed "refined to no intensity … at its zero bound" for a peak that still puts counts in the pattern, and that peak's centre is constrained by data. | none found |
  | 4. Case for acting | WP Context: "TRF keeps its iterates strictly inside the bounds and stops just above the floor … An area stopped the same distance above zero escapes a 1e-10 window. Not measured on a declared peak." WP-1914's width case: `gauss_size` stored 3.4×10⁻²⁴ under TRF while `FLOOR_HIT` said it was on its floor. | The miss is real but narrow. The test's own docstring (`tests/test_extra_components.py`, `_floor_plan`) says that at the default ftol of 1e-9, "TRF lands the area within 1e-19 of zero, inside the `BOUND_HIT_RTOL` distance the pre-WP-2141 code used". So the old rule missed only on a stage stopped early (ftol 1e-5, no closing stage), where the area stopped near 2e-5. The general evidence is WP-1434, quoted in the `bound_findings` docstring: "nine of 32 genuinely-binding cases ended 1e-10 to 1.6e-6 inside their limit, `converged`". Cost of the old rule: a missing warning beside a `FLOOR_HIT` that names the same path, and a centre and esd quoted as if measured. The change measures no cost on any default path. Separately, the joint test's seed 2 leaves an area of 0.84 with an esd near 0.8. That is a peak with no significant intensity, and neither the old rule nor the new one fires on it. A 3σ significance test, like the absent-phase hold's, would. That is outside this change. | holds, narrow |
  | 5. Tier | WP Context: "**Tier.** No threshold changes: the code stops using its own and reads the authority's. Tier 1." | Partly wrong. On the LM exact-active-set path, and on the fallback path with no solve behind it, the test reduces to `BOUND_HIT_RTOL` (tier 1, `_audit.py:4434`: scipy's own 1e-10, checked there). On the TRF path, `FLOOR_HIT` comes from a two-part test: within `BOUND_HIT_ESD_FRAC` (0.01 esd) of the floor, and residual angle at least `BOUND_HIT_COS_MIN` (1e-4). Both constants are **tier 3**, approved 2026-10-19 (`_audit.py:4419`, `:4426`). Both rows say "second pass owed (a third family under TRF)". The code inherits those tiers and that open item on the very branch this WP adds. Moving onto approved constants is still the convention: root CLAUDE.md says a second surface of a fact is "a projection of it, never re-derived". No program default applies, and none is claimed. | weak (mislabelled) |
  | 6. Dataset families | none given (no handover entry yet; the WP log has only its 2026-11-09 creation) | For the new firing: one synthetic family, `_clean_lab6`, under LM and TRF. Single fit; joint fit with seeds 1 and 2, which are one family. It is development data with no independent reference, so it verifies the decision rule and validates nothing. Margins measured on macOS arm64 only: TRF area about 2e-5 against a 0.01-esd window of about 0.008, a margin of about 400. Seed 2's free optimum is 0.84, far outside the window. The constants underneath rest on WP-1434's FAP (the GSAS-II example dataset), Si SRM 640c and synthetic `make_lab6`: two real families, development data. | weak (one synthetic family; inherited thresholds have two real families and an owed TRF pass) |
  | 7. Record of firing | the docstring and the help entry (`help.py`, `EXTRA_PEAK_NO_INTENSITY`) name `FLOOR_HIT` | The code itself, with `where = [centre path, area path]`. Beside it: `FLOOR_HIT` on the area path and `RefinedParameter.at_bound`, which come from the same findings. `replay` reads the recorded `FLOOR_HIT` diagnostics. `test_either_driver_reports_a_declared_peak_on_its_floor` pins replay against the fit. | holds |

  Evidence that would change the verdict: a real declared-peak dataset where TRF stops within 1e-10 of zero without pressing on the floor, so the new rule falls silent where the old one fired. Or the owed third-family TRF pass on `BOUND_HIT_ESD_FRAC` / `BOUND_HIT_COS_MIN` moving either constant.

  #### Item 2: the joint fit runs the bound test before its per-histogram loop (`multi.py`, `_hist_floors`)

  (`_hist_floors(at_bounds, h)` replaces `_hist0_floors`. It returns histogram h's `FLOOR_HIT` paths with their `hist.h.` prefix removed. A shared parameter's path has no prefix, so it passes to every histogram.)

  **Verdict: holds.** The case for it is stronger. It is plumbing that applies item 1's rule per histogram and adds no number of its own. Before it, the joint fit judged declared peaks with the old distance test, because the bound test had not yet run.

  | Question | Author's answer (where) | What I found | Verdict |
  |---|---|---|---|
  | 1. What it decides unasked | WP Context: "`multi.py` calls `_extra_peak_diagnostics` inside its per-histogram loop … before `bound_findings` runs … so the bound test's answer does not exist yet when the peak is judged." | It decides the same thing as item 1, once per histogram. A floored shared area fires in every histogram. A floored per-histogram area fires only in its own. Moving the test earlier changes none of its inputs: `outcome` is not reassigned between the new location (`multi.py:2457`) and the old one, and the loop has no `continue` that could misalign `per_floors[h]`. `per_floors[0]` is the same set the microstructure block (the per-phase size/strain table) read before (`floored_paths(mt.tables[0], …)`). | holds |
  | 2. Rule 1 kind | none given | Kind 1, as item 1. No row exists to agree. | holds; no row |
  | 3. Case against acting | none given | none found | none found |
  | 4. Case for acting | the WP Goal: "under either solver and in a joint fit" | Without it, a joint fit under TRF would judge a peak by a distance its own `FLOOR_HIT` contradicts, and the single fit and the joint fit would disagree on one fact. No cost is measured on a default path. | holds |
  | 5. Tier | WP Context: "Tier 1" | It inherits item 1's tiers: `BOUND_HIT_RTOL` (tier 1) on the exact and fallback paths, and `BOUND_HIT_ESD_FRAC` and `BOUND_HIT_COS_MIN` (tier 3, approved 2026-10-19, a TRF pass owed) on the TRF path. | weak (same mislabel as item 1) |
  | 6. Dataset families | none given | One synthetic family (`_clean_lab6`, seeds 1 and 2), LM and TRF, macOS arm64. It asserts `fired == [True, False]`. `_hist_floors` is also unit-tested for h = 0 and h = 1 (`tests/test_microstructure.py::test_a_joint_fit_hands_histogram_0_its_own_floor_spelling`). | weak (one synthetic family) |
  | 7. Record of firing | none beyond item 1 | The code appears in each `HistogramResult.diagnostics`. The joint `FLOOR_HIT` carries the `hist.h.`-scoped or shared path, and `at_bound` sits on the joint parameter rows. | holds |

  Evidence that would change the verdict: a joint fit where a writer moves θ (the solved parameter vector) after the solve but before the old call site, which would make the earlier bound test read a different vector. I found no such writer at `multi.py:2431-2677`.

  Author's answer to the two `weak (mislabelled)` tier rows: agreed. The Context's tier line now says the code inherits the bound test's tiers, tier 3 on the TRF path. On corner case (c): a free optimum within 1e-10 of zero against an esd near 0.8 is vanishingly rare under noise, and WP-1914's width reading made the same choice. On the seed-2 area of 0.84 ± 0.8 with no significance test: outside this WP; noted for whoever owns a significance reading of declared peaks.

  Next: none in this WP. For whoever owns a significance reading of declared peaks: the
  joint test's seed 2 leaves an area of 0.84 ± 0.8 counts·deg, which neither rule calls "no
  intensity" (the judge's note under item 1, question 4). The owed third-family TRF pass on
  `BOUND_HIT_ESD_FRAC`/`BOUND_HIT_COS_MIN` now also governs this code.

- **2026-11-09** — created, from WP-1914's sibling sweep (PR #1506). No open WP owns extra peaks;
  WP-1103, which shipped them, is closed. Read against the tree at `origin/main` on 2026-11-09:
  the proximity test and the joint-fit call order are as described; nothing was run. Numbered
  2141, past the 2130s, because another shift is filing GUI WPs there today. Bookkeeping PR:
  #1513. Next: wait for #1506 to merge, then reuse its `floors=` wiring.
