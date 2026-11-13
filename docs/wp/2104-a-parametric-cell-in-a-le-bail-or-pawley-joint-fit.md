# WP-2104 — a parametric cell in a Le Bail or Pawley joint fit

Milestone: parametric · Status: ✅ 2026-11-13 — the Pawley arm lands (PR #1547); the joint Le Bail arm is retired to WP-2062
Depends on: 1325 soft (the joint path has landed, and its open tasks are separate); 1964 soft (an equation on the cell)

## Goal

A joint fit in `mode="lebail"` or `mode="pawley"` can share a parametric equation on the
cell, with each pattern's intensities its own.

## Context

`MultiHistogramRefinement.fit` raises `NotImplementedError` for any mode but
`rietveld` (`multi.py:1426`). The stated reason is that "a joint fit of them is just
independent single-pattern fits". That was true with nothing shared. It stops being true
the moment a cell is tied across patterns, because the shared coefficients then couple
every pattern. A cell as a function of temperature is the commonest case, and it is the
case that needs no structure model.

Two different seams sit behind the one refusal:

- **Le Bail** alternates: `Refinement._fit_lebail_alternation` partitions intensities
  and then refines. Here each histogram partitions its own, and the shared step runs
  between partitions.
- **Pawley** holds intensities as an off-table θ block
  (`model.forward.PawleyBlock`, appended in `run_least_squares`). A joint fit has many
  such blocks. `optimize/blocked.py`'s per-pattern blocks are the natural home, and the
  count of intensities per pattern is what the measurement must find out.

The rest of the joint path says the same thing in two rows of `multi.py`'s diagnostic
table (`ABSENT`, "a joint fit is Rietveld-only"). Those rows change with this WP.

### Measured (2026-11-12), and which mode lands

Pawley lands and Le Bail does not, settled by Claude under the 2026-11-05 ruling
(Pawley is the structure-free direction, and Le Bail work stays minimal). Le Bail's
joint arm would be a new partition seam between solves, so its cost was not measured:
measuring it means building it.

The Pawley arm, on `tests/test_parametric_series.pawley_ramp` (LaB6, a(T) on a line,
4 200 points and 19 reflections a pattern, zero and profile shared), through
`docs/wp/2104-measure/pawley_scaling.py`. The machine was shared with other runners
(load average 28-30), so wall clock is a range of one run each and the iteration counts
are the comparable numbers.

| run | free columns | iterations | wall clock |
|---|---|---|---|
| 10 single Pawley fits, each with its own cell, zero and profile | per fit, 19 intensities and its own rows | 440 in all | 3.2 s in all |
| joint, N = 10, dense layout | 228 (190 intensities) | 82 | 8.7-9.4 s |
| joint, N = 10, blocked layout | 228 | 80 | 3.4 s |
| joint, N = 100, blocked (chosen unasked) | 2 208 (1 900 intensities) | 67 | 83 s |

The blocked step holds at N = 100. Its dense twin would be a 7.4 GB Jacobian; the
blocked run peaked at 1.05 GB of physical footprint, against 1.03 GB at N = 10, so the
n × n normal matrix (39 MB at n = 2 208) is not yet what limits it. The intensities are
each histogram's own columns of `optimize/blocked.py`'s arrow, so no new solver path
was needed. At N = 100 the slope landed 0.27 esd and the intercept 0.70 esd from the
truth.

## Non-goals

- A joint Pawley with intensities shared across patterns.
- Restraints on Pawley intensities beyond the existing equal-split rows.

## Tasks

- [x] Measure first: on a synthetic ramp of 10 patterns, what does Le Bail alternation
  through the joint path cost against N single fits, and does Pawley's blocked step
  hold at N = 100? Decide whether one mode lands first, and write it here.
  (§ Measured: Pawley lands; its blocked step holds at N = 100.)
- [x] Lift the refusal for the mode or modes built. A joint fit with nothing shared in
  these modes keeps a message saying it is N single fits.
- [x] `multi.py`'s diagnostic rows, and `force-fix` of intensity paths under
  `mode_fixed` across histograms.
- [x] A cross-backend config, if a new derivative path appears. (No new branch: the joint Pawley Jacobian stacks the single fit's columns. Its stacked layout joins the matrix as a `pawley` row of `test_multi_histogram_stacked_jacobian_matches_analytic`.)
- [x] Manual: `reference/joint.md`, `reference/parametric.md`.
- [x] Skill: the series reference's row.

## Acceptance

A Pawley or Le Bail joint fit shares a parametric cell over a synthetic ramp. Over 12
pinned seeds, the coefficients of a(T) have a mean z-score under 0.5 in size. If only one
mode lands, this file says so, and 2108's second route waits on the Pawley arm.

```sh
.venv/bin/python -m pytest tests/test_multi_histogram.py tests/test_parametric_series.py tests/test_cross_backend.py
.venv/bin/python -m ruff check src tests examples
```

## References

- Stinton, G. W. & Evans, J. S. O. (2007). *J. Appl. Cryst.* 40, 87-95.
- WP-1325 § Scalable solver, WP-1125 (the Pawley block), WP-0308.

## Handover log

- **2026-11-13** — The WP closes (✅). Ruled by Yue 2026-11-13: "go", approving PR #1547
  with the equation guide's moved statistics (9.3 now 9.4; 501.5 now 504.2). The joint Le
  Bail arm is retired to WP-2062, settled by Claude under Yue's 2026-11-05 ruling, and Yue
  raised no objection. So the Pawley arm answers the acceptance, and this file says only one
  mode landed. WP-2062's `### Inherited` note now records the retirement, and the narrative
  is in the v1.12 record.
  *Merge.* Main was merged in at `4c442c0dd` after #1546 (WP-2116, a hump's closed-form
  columns) landed. The merge had no textual conflict. Both sides edited
  `optimize/least_squares.py` and `tests/test_cross_backend.py`, in separate functions:
  WP-2116 in `_make_jacobian`, this WP in the joint closures, which call the single-fit
  Jacobian per pattern. No published or acceptance number moved. Fast suite on the merged
  tree, `[dev]` venv (no jax), darwin arm64, one 27 min run under the machine lock: 14 591
  passed, 433 skipped, 32 xfailed. `tests.reader_output` exit 0, unchanged against the
  merge-base. Ruff clean; Vale exit 0 with no warning on a line this branch wrote.

- **2026-11-12** — A cell series can now share a parametric equation before anyone
  has a structure. A joint fit in Pawley mode gives every pattern its own reflection
  intensities, while the equation's coefficients, and anything else the
  patterns share, are fitted once across all of them. Over twelve synthetic seeds the
  coefficients land without bias, and a hundred-pattern fit runs in about a gigabyte,
  so a long in-situ ramp is within reach. Le Bail was not built, under the 2026-11-05
  ruling, and a joint Le Bail fit still refuses with a message naming Pawley. PR #1547.

  *Decision for Yue (the WP's title names both modes).* Build a joint Le Bail arm, or
  retire it to WP-2062 and close this WP? A joint Le Bail fit would need a partition
  loop around the stacked solve, which is new code in the solver, and the Pawley arm
  already answers the question the WP was opened for. My lean is retire. The 2026-11-05
  ruling points that way, and nothing measured asks for Le Bail. Either answer is
  cheap to record: a retire closes this WP ✅, a build adds a task here.

  *Done.* The joint solve carries one Pawley block per pattern after the table's
  columns (`least_squares._joint_aux_slices`), in both the dense and blocked layouts.
  Each stage drops what an intensity model cannot fit, by what each column moves in
  every pattern (`multi._joint_mode_fixed`), and seeds each block as the single runner
  does (`_seed_joint_pawley`). A Pawley fit that shares nothing, a joint Le Bail fit,
  and an equation on a force-fixed target (a `biso`, a scale) are refused before the
  fit. The intensities count in each pattern's statistics and the pooled ones, the two
  Pawley diagnostics go on their pattern, and `parameters()` marks force-fixed rows.
  The parametric form test and the cross-backend matrix (`MULTI_MODES`) both take the
  Pawley layout. Manual: `joint.md` § Modes, `parametric.md`, `series.md`. Skill: the
  series reference's parametric row.

  *Review (`/code-review high --fix`).* Four fixes, each its own commit. A joint Pawley
  fit no longer quotes phase fractions off its force-fixed scales; its significance
  screen reads undecided, as a single Pawley fit's does; the intensity count no longer
  builds 1 900 names to count them. The fourth also reaches Rietveld joint fits: the
  parametric form test now runs at the committed answer (`_joint_theta`), where it had
  used the cached vector the last stage started from (background c0 0.56 off and
  profile y 36 % off on the 3-pattern probe). Declined, with reasons: exposing each
  pattern's intensities on the joint result (a public-surface change, so it is
  Yue's); tightening the nothing-shared refusal (below); computing the column reach
  once per stage instead of twice (minor cost, kept the diff small).

  *Measured.* § Measured above holds the scaling table. Acceptance: twelve seeds of the
  ten-pattern ramp, mean z 0.20 (intercept, spread 0.65) and 0.13 (slope, spread 1.01),
  bar 0.5; the slow test ran in 109 s alone. Fast suite on main merged in (506289499),
  `[dev]` venv, darwin/arm64, machine shared with other runners: 14 569 passed, 1 failed, 428 skipped, 32 xfailed in one 8:45 run. The
  failure was the equation guide quoting the Rietveld form test's statistic
  from before the review's form-test fix (9.3 now 9.4; 501.5 now 504.2; neither
  verdict moves). The guide and its page now quote the new figures, and that
  test passes alone. Collected
  fast items in the three touched files moved 411 → 421 (+10: four parametric-series
  tests, six cross-backend Pawley rows) and slow 22 → 23. Added-test times
  (`tests.added_test_times`, local): 1.71 s over the five added or renamed tests, the slowest 0.81 s; none joins
  the fast tier's slow tail. `tests.reader_output` exit 0
  (unchanged against the merge-base). Sphinx `-W` exit 0. Vale: no warning on a line
  this branch wrote. jax and torch rows not run locally (not installed); CI's jax job
  selects the `pawley` row.

  *Generality.* The generality-review agent's sections follow unedited, with the
  author's answer under each verdict that asked for one.

  #### Item 1: `multi._refuse_joint_mode` (the check that refuses a joint fit before it starts)

  **weak.** The case for refusing is the stronger one. But the coupling test is narrower than the WP and manual say, and the same unshared fit in Rietveld mode still runs with no reason given for the difference.

  There are two parts. Le Bail was already refused before this change, so only its message is new. The Pawley "N single fits" refusal is the new action. A "joint fit" here is `MultiHistogramRefinement`: one least-squares solve over every pattern.

  | Question | Author's answer (where) | What I found | Verdict |
  |---|---|---|---|
  | 1. What it decides unasked | Docstring, `src/rietx/multi.py` `_refuse_joint_mode`: "with nothing else shared the stacked residual is N independent problems, solved slower and reported as one." | It refuses a call the caller made. The coupling test reads every table entry that is shared, untied, unlocked and not force-fixed by name. Force-fixed means a parameter an intensity-only fit cannot refine: atom parameters, phase scales, texture. The test never reads whether the plan frees the entry. So the dispatch's word "free" does not match the code. A plan that frees no shared row still runs as N single fits unrefused. It also counts dead shared rows as coupling. `phases.*.preferred_orientation.r` and `phases.*.extinction` are not in `mode_fixed_path`, yet `mode_fixed_path`'s own docstring says March-Dollase r "ended 1.7e-13 from its start" under an intensity model. That is my reading of the code; I did not run it. | the refusal fires on a narrower set than stated |
  | 2. Kind of ambiguity | none given (no audit row; the WP handover has no entry for this session) | Kind 1. That the residual splits into independent blocks when no column is shared is arithmetic. | none given |
  | 3. Case against acting | none given | Convention (DESIGN.md § Rules, 5): `_refuse_joint_mode` returns at once for `rietveld`. So `per_histogram=["phases.*"]` in Rietveld mode runs the same unshared joint fit and is not refused. Nothing in the diff names the mistake the Rietveld convention would cause in Pawley. A caller may want one result object for N fits. Whether GSAS-II or TOPAS refuse an unshared multi-pattern fit: not in `docs/practice.md`, not checked. | real but small |
  | 4. Case for acting | Docstring: "solved slower and reported as one"; WP § Measured table (10 single Pawley fits 3.2 s and 440 iterations; joint N = 10 dense 8.7-9.4 s, blocked 3.4 s) | The timing was measured with zero shift and profile *shared*, not on the refused case. "Slower" holds there for the dense layout only. The blocked layout is about even. An unstated reason also holds (my reading, not measured). The joint covariance scales every esd by the pooled goodness of fit (`_guarded_covariance(..., res.fun, ...)` over the stacked residual). So an unshared joint fit would give each pattern's esds the pooled scaling instead of its own, which moves a number off what N single fits report. The cost of refusing is one failed call. The message names both ways out (`Refinement.fit(mode='pawley')`, or share a parameter). | stronger side |
  | 5. Tier, with source | none given | The separability is tier 1, and the refusal is judged on the judgement ground. No program default was checked for this. | none given |
  | 6. Dataset families | WP § Measured: `tests/test_parametric_series.pawley_ramp`, synthetic LaB6 | No threshold, so this is not applicable. The only measurement is one synthetic family. It is development data with a known truth by construction. | n/a |
  | 7. Record that it fired | the raise text, "is N single Pawley fits" | A `NotImplementedError`, tested by `tests/test_parametric_series.py::test_a_joint_fit_refuses_what_an_intensity_model_cannot_fit`. Two things are not covered by any test: the false-pass cases (a shared row the plan never frees, a shared dead row), and an unknown mode, which now raises `ValueError` instead of `NotImplementedError`. | holds |

  Would change the verdict: a coupling test that reads the plan's freed set (or what each shared column moves), plus a stated reason why Rietveld mode keeps running the unshared fit, or the same refusal there.

  *Author:* left as is. The test errs toward running an uncoupled fit, never toward refusing a coupled one, and a refusal in Rietveld mode would change shipped behaviour outside this WP.

  #### Item 2: `multi._joint_mode_fixed` (drops columns a Pawley fit cannot refine)

  **holds.** The case for acting is the stronger one, and no case against was found. It copies the single fit's drop (`refine.mode_fixed_column`, `Refinement._run_stage`). But no test exercises the drop on the joint path.

  A column's "reach" is the set of model parameters it moves, through ties and equations, in every pattern.

  | Question | Author's answer (where) | What I found | Verdict |
  |---|---|---|---|
  | 1. What it decides unasked | `_joint_mode_fixed` docstring: "a per-histogram scale … is the phase scale it is, and a coefficient driving each pattern's `biso` is as dead as the `biso` itself." Manual `joint.md` § Modes: "Every stage leaves out what a single Pawley fit leaves out." | It removes a freed column from the solve when every path it reaches is force-fixed. This is the single fit's "all, never any" rule. A column that also reaches one live parameter stays. It runs before the seeds, as the single runner does (`refine.py` around line 5087). | holds |
  | 2. Kind of ambiguity | none given | Kind 1. With no \|F\|², atom columns have zero gradient. The phase scale is exactly degenerate with the free intensities. | none given |
  | 3. Case against acting | none given | none found | none found |
  | 4. Case for acting | the docstring above | Left in, these columns are flat directions whose values and esds would read as measurements. `mode_fixed_column`'s docstring measured this on LaB6: `vars.B` moved biso 0.5 to 0.7 under Le Bail. | stronger side |
  | 5. Tier, with source | none given | Tier 1 (arithmetic), the same as the single fit. Inherited gap, outside this item: extinction and March-Dollase r are not force-fixed by name in either fit. | tier 1 |
  | 6. Dataset families | none given | No threshold, so not applicable. | n/a |
  | 7. Record that it fired | Manual: "`MultiHistogramRefinement.parameters()` marks those rows `mode_fixed`" | `ParameterRow.mode_fixed`, and the dropped paths are absent from `StageResult.freed`. `_audit.OTHER_RECORD_FIELDS` lists that field as reporting no action, and no diagnostic names a dropped path. The single fit behaves the same. The test gap: `test_a_pawley_joint_fit_shares_a_parametric_cell` asserts no `.scale` or `.atoms.` row in the result. But `pawley_default` (the default Pawley plan) frees no scale or atom path (`strategy/staged.py` `profile_only`), so the assertion passes without the drop ever firing. The reach case in the manual ("a coefficient that drives only `biso`") is also unreachable through a parametric equation, because item 3 refuses that first. No test reaches it by another route. | record holds; test missing |

  Would change the verdict: a joint Pawley test whose plan frees `phases.*.scale` and an atom glob, asserting they leave `freed` and θ (the solve's parameter vector).

  *Author:* added, `test_a_pawley_joint_stage_drops_what_it_cannot_fit`, with a spy so it cannot pass without the drop firing.

  #### Item 3: refusing a parametric equation on a force-fixed target under `mode="pawley"`

  **holds.** The case for acting is the stronger one. The case against is a departure from the single fit's convention (drop quietly), and established practice weakens it.

  | Question | Author's answer (where) | What I found | Verdict |
  |---|---|---|---|
  | 1. What it decides unasked | Raise text in `_refuse_joint_mode`: "an intensity model has no \|F\|² and no phase scale to fit, so an equation on it would refine nothing. Declare the equation in a Rietveld joint fit" | It raises `ValueError` before any compile. The test is on the target's name (`mode_fixed_path(r.target)`), not on its reach. | holds |
  | 2. Kind of ambiguity | none given | Kind 1. The target cannot move. | none given |
  | 3. Case against acting | none given | The single fit drops a force-fixed path quietly and does not refuse it. This refusal departs from that (Rule 5), and the raise text gives the reason. One consequence: a Pawley fit followed by a Rietveld fit on one `MultiHistogramRefinement` object needs two objects if the declarations include `biso`. Practice softens this. `docs/practice.md` § "Pawley or Le Bail first, then Rietveld" (checked there) has TOPAS, FullProf and RIETAN-FP editing the input between the two runs. RIETAN-FP's template comments out the structure parameters. | weak |
  | 4. Case for acting | the raise text | An equation is a constructor argument, which is a more specific request than a plan glob. Dropping it silently would return a declared equation with no coefficients refined. The cost is one edit of the declarations. | stronger side |
  | 5. Tier, with source | none given | Tier 1 | tier 1 |
  | 6. Dataset families | none given | No threshold, so not applicable. | n/a |
  | 7. Record that it fired | the raise | `ValueError`, tested for `biso` by `test_a_joint_fit_refuses_what_an_intensity_model_cannot_fit`. No test covers a scale target, which `parametric.md` names too. | holds |

  Would change the verdict: a measured use where one object really carries a structural equation through a Pawley fit into a Rietveld one.

  #### Item 4: no phase fractions and an undecided significance screen in a joint Pawley fit

  **holds.** The case for acting is the stronger one, and no case for computing them was found. Both copy the single fit.

  The significance screen is the test of whether a phase's scale stands above noise.

  | Question | Author's answer (where) | What I found | Verdict |
  |---|---|---|---|
  | 1. What it decides unasked | Diff comment at `_quantify_phases`: "a Pawley fit force-fixes every scale, so a fraction would be the start's". Comment at the stage return: "the result does not call it decided, the single fit's rule (`StageResult.significance`)" | Verified against `refine.py` line 9422 (QPA only when `mode == "rietveld"`) and line 5642 (`significance=support if mode == "rietveld" else None`). The between-stage support hold still reads the screen, as in the single fit. | holds |
  | 2. Kind of ambiguity | none given | Kind 1 | none given |
  | 3. Case against acting | none given | none found. A fraction needs a refined scale and \|F\|². | none found |
  | 4. Case for acting | the comment above | Otherwise a fraction would be read off the starting scale. That is the failure the audit row `RefinementResult.qpa` (tier 1) cites: 99.99 against 0.61 wt%. | stronger side |
  | 5. Tier, with source | none given | Tier 1, the same as the single fit's `RefinementResult.qpa` row | tier 1 |
  | 6. Dataset families | none given | not applicable | n/a |
  | 7. Record that it fired | none given | `HistogramResult.qpa is None` is asserted in `test_a_pawley_joint_fit_shares_a_parametric_cell`. No test asserts the `None` significance. `result.mode == "pawley"` is the reason a reader sees. | holds |

  Would change the verdict: none plausible short of a Pawley scale that is refined.

  #### Item 5: seeding each pattern's Pawley intensities (`_seed_joint_pawley`)

  **holds.** The case for acting is the stronger one. It reuses the single fit's rule and its approved constant. But that constant's evidence comes from single fits only, and its known failure under TRF carries over.

  The rule: a short Le Bail partition on the first stage, then intensities carried by reflection index (hkl, m) between stages.

  | Question | Author's answer (where) | What I found | Verdict |
  |---|---|---|---|
  | 1. What it decides unasked | `_seed_joint_pawley` docstring: "Carried by (hkl, m) from the previous stage's compile of the same histogram, or, on the first stage, seeded by a short Le Bail partition (`_pawley_seed_cycles`)" | It matches `refine.py` lines 5159-5185, except for the restore after a checkout, which the joint fit has no use for. It sets where the solve starts. The count is `PAWLEY_SEED_CYCLES` = 3. | holds |
  | 2. Kind of ambiguity | none given | Kind 1, if the start moves no answer | none given |
  | 3. Case against acting | none given | The constant's row (`_audit.py`, `rietx.refine.PAWLEY_SEED_CYCLES`, tier 3, approved 2026-10-19) records a failing case: "fails under solver='trf' on FAP: 3 cycles stop at Rwp 8.17 % where 300 reach 7.87 % … 8.8 esd apart". `run_multi_least_squares` accepts `solver="trf"`, so the joint path inherits that failure. The joint path also adds starts the row never saw. Each pattern is seeded at the equation's starting value. On the acceptance ramp (a 0.45 % cell change over 300-1200 K) that puts the hot patterns several peak widths from the start. That is my estimate from `RAMP` and the fixture's FWHM comment; I did not run it. | real for TRF only |
  | 4. Case for acting | WP § Measured: N = 100, "the slope landed 0.27 esd and the intercept 0.70 esd from the truth"; slow test: mean z under 0.5 over 12 seeds (`parametric.md`: 0.20 and 0.13) | Under the default LM the inherited row measured a 300-cycle seed against 3 moving 0.000 esd. The joint acceptance converged and is unbiased on its one family. | stronger side under LM |
  | 5. Tier, with source | inherited row, tier 3 | Tier 3, kept on the row's grounds. No joint-path evidence was added. | holds |
  | 6. Dataset families | the WP names one: synthetic LaB6 | The inherited row's families are single-fit patterns: #740's, the 2 % scale, corundum, FAP, 11-BM NAC, LaB6 with cBN. The joint path's only family is synthetic LaB6. It is development data, and its reference is the synthetic truth. | one family on this path |
  | 7. Record that it fired | none given | The single fit records the seed's partition run in `StageResult.lebail_run`. I could not see whether the joint stage records it. | cannot tell |

  Would change the verdict: a joint seed-sensitivity run (3 against 300 cycles) under LM and TRF on a second family.

  #### Item 6: skill row, `docs/skill/rietx/references/series.md`: "No structure: `mode="pawley"`."

  **holds.** The case for acting is the stronger one. The row names a parameter value, and inside a joint fit it is the only structure-free mode, so it chooses nothing an agent could choose otherwise.

  | Question | Author's answer (where) | What I found | Verdict |
  |---|---|---|---|
  | 1. What it decides unasked | the row; WP task "Skill: the series reference's row" | It steers an agent with no structure to Pawley for a joint equation. `lebail` raises there, so the steer restates what the API allows. | holds |
  | 2. Kind of ambiguity | none given | Kind 1 inside the joint path | none given |
  | 3. Case against acting | none given | Outside the joint path, programs differ (`docs/practice.md` § Structure-free fitting): TOPAS defaults to Pawley, MAUD steers Le Bail then Pawley, FullProf has Le Bail only. The row is scoped to the joint call, so the difference does not bite. | none found within scope |
  | 4. Case for acting | none given | Without the row an agent may try `lebail` first and pay one raise. The raise text names Pawley. | stronger side, small |
  | 5. Tier, with source | none given | DESIGN.md § Rules, 4 "a new skill row … names a field": it passes. It carries no validation verdict (Rule 2). | holds |
  | 6. Dataset families | tag "(Measured: WP-1325, synthetic, ZrMo₂O₈; WP-2104.)" | The WP-2104 part of the tag omits "synthetic, LaB6". The clause itself is an API fact, not a measurement. | minor |
  | 7. Record | n/a | n/a | n/a |

  Would change the verdict: a joint Le Bail mode landing, which would make the row choose between two modes.

  *Author:* the tag stays, because `series.md` sits 31 B under its size budget.

  *Forward references.* WP-2108 `### Inherited`: the joint Pawley arm landed under one
  mode per fit, and the two readers a mixed-mode phase must change. WP-2062
  `### Inherited`: the joint Le Bail refusal, and the question above.

  *Next.* 1. Yue answers the Le Bail question; on "retire", mark this WP ✅ and move its
  narrative to the record. 2. Review and merge PR #1547. 3. If a joint user wants the
  per-pattern intensities, that is a public-surface decision for Yue.

- **2026-11-04** — Filed on the opening of the milestone. No open WP owned it. It split
  from 2103 because it reaches the solver and has a measurement in front of it. Next:
  the measurement.
