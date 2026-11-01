# WP-1421 — the result reproduces its own number

Milestone: unscheduled · Status: ✅ 2026-10-25 — every task landed or closed by ruling; the joint fit and every view of a result read the answer
Track: What fires, and what stays silent
Depends on: — (1310 soft: it owns which vector reaches the final diagnostics)

## Goal

A `RefinementResult`'s statistics and curves can be reproduced from its own
parameters. Either they come from a compile at the returned values, or the
result says they were measured on the last stage's frozen compile and how far
a fresh compile sits from them. A reader can then check the number a report
quotes.

## Context

Issue #272 (2026-09-06), measured read-only on `origin/main` `2ba7a9a3` on
the two shipped acceptance fixtures, driven exactly as their tests drive them.

**What happens.** `_build_result` (`refine.py`) evaluates the model the last
stage compiled, at the values that stage ended on. That compile froze its
peak windows and FCJ node counts at the stage's *start* (root CLAUDE.md
§ Invariants, frozen-per-stage discreteness). When the last stage moves the
parameters that sized them, a fresh compile at `result.parameters` draws a
different curve and reports a different χ².

| fixture | χ² reported | χ² from a fresh compile at θ\* | Δ | Rwp reported → recompiled |
|---|---|---|---|---|
| Si SRM 640c, 11-BM (`test_acceptance_si640c.py::_fit`) | 88 284.16 | 89 501.76 | −1217.6 (1.38 %) | 0.08263 → 0.08319 |
| FAP, lab Cu Kα (`test_acceptance_fap.py`) | 17 180.94 | 17 177.56 | +3.4 (0.02 %) | — |

χ² here is Σ w(y−y_c)², with the P-spline penalty rows excluded because they
cancel between the two compiles. `y_calc` differs at 9 621 of 47 999 points
on Si (max |Δy| 175 counts on a 198 744-count peak) and at 1 131 of 5 750 on
FAP. `y_background` is bit-identical. Every parameter value matches the
objects the fresh compile was built from.

**Why.** Si's last stage moved λ, zero, `axial_sl`, `axial_hl`, `u`,
`lor_size` and `lor_strain`. Its windows shrank from a mean of 1001 points
(max 1420) to 846 (max 939), and its FCJ nodes fell from 1984 to 403. The
reflection list stayed at 50, so this is window width and node count and not
membership. A `window_slack_deg` sweep at θ\* puts about 1 600 χ² units on
window width alone (89 502 at 0.3°, 87 905 at 0.6°, 87 633 at 1.0°). The
node share was not separated out.

**What it does not do.** The minimum is not biased. A scan of χ² against the
cell with windows frozen at θ\* against recompiled at each point moves the
minimum by ≤ 0.0014 esd(a) on FAP and by 1e-4 of the λ-equivalent esd on
Si. A stage started 0.5 % off in the cell returns an `a` within 0.013 esd of
the next round's re-cut answer. The fit is right. The reported number is the
one the returned model does not give back.

**The package already knows this shape, one rank over.** `schemas/history.py`
documents a node's cached metrics as *as-optimised*, "the agreement the
least squares actually reached", and `docs/manual/using/history.md` calls the
difference `replay` shows a staleness signal. Root CLAUDE.md § Conventions
says the same. That convention was written for history nodes, where the
frozen number is the honest record of what the solver saw. #272 is about the
*result*, the number a reader quotes. WP-1076's rule applies: a reported Rwp
the returned model does not reproduce is a number nobody can check.

**Two shapes.** (a) One final compile at θ\* before `_build_result`, with the
curves and statistics taken from it. It costs one model build per fit. Every
pinned number whose last stage frees a window-sizing parameter then moves,
by 0.7 % relative in Rwp on Si. The history node keeps its as-optimised
metrics, so result and node differ by the amount `replay` already shows.
(b) State it. The statistics block carries which compile produced it, and
the fresh-compile χ² beside it. No number moves, and a reader sees the size.

**Triage recommendation (2026-09-15):** (b) first. It is the honest state
1076 asks for and it moves nothing. Then decide (a) on the spread task 1
measures across every acceptance fixture and golden. A `stage_reports=True`
caller (WP-1058) sees the same effect at every stage boundary, so whatever
lands applies to the stage trajectory too.

Le Bail and Pawley intensities are frozen per stage as well
(`ReflectionState`). A fresh compile must carry them, never re-partition.

**What arrived after the merge, re-checked 2026-10-25 at `7e69f974`**
(`[dev]` venv, darwin/arm64). Superseded in part: the inherited entries
below are folded here, and their mailbox is emptied.

- **The frozen windows can move the minimum, and a plan now re-solves for
  it.** WP-1986 (2026-10-17) measured a gap between two minima on the
  shipped fluorapatite tutorial (`FAP.XRA`, six-term Chebyshev, 15-130°):
  `mccusker_default` ended at Rwp 0.0992 and one empty stage re-solved to
  0.0940, while the fresh and frozen compiles at the returned values differed
  by only 0.8 %, so `FROZEN_COMPILE_STALE` stayed silent. WP-2002 then added
  the closing stage (`RefinementPlan.closing_stage`, `strategy/staged.py`):
  after the declared stages, one more recompiles at the answer and re-solves.
  Re-measured with it, the gap to one more empty stage is 0.00 % under
  `mccusker_default` (0.0945 → 0.0945), `mccusker_structural` and
  `lab_sample_refine`. With `closing_window_tol=None` it is back: 9.26 % under
  `mccusker_default` (0.0992 → 0.0945). A hand-run `run_stage` has no closing
  stage, so it keeps the gap; `docs/docs/guides/next.md` and `stage.md` teach
  the empty stage that closes it.
- **The joint fit, the same.** WP-1341 (2026-10-12) found a joint result's
  report reading cut peak tails as unmatched peaks (44 and 27 on
  `test_multi_histogram`'s WP-1131 size pair). Re-measured: with the closing
  stage the two histograms report Rwp 0.04078 and 0.08166, a compile at the
  answer gives the same five digits, and Layer 0 lists 0 unmatched peaks on
  each. With `closing_window_tol=None`: reported 0.09658 and 0.12971 against
  0.12744 and 0.13130 fresh, 38 and 28 unmatched. The joint path still builds
  its result on the last stage's compile (`multi._build_result`), so the
  closing stage is what hides the gap there. `MultiHistogramRefinement.report`'s
  docstring and `docs/docs/reference/joint.md` still describe the gap as live.
- **The finding's "not biased" sentence is wrong in two measured cases.** It
  rests on #272's two good fits, where the minimum moved ≤ 0.0014 esd. WP-1986's
  hand-run stage is one counterexample (above). WP-1930 (2026-10-09) is the
  other: a wrong P 1 cell on synthetic silicon whose widths ran to their upper
  bounds, χ² 3.29e5 on the frozen compile against 2.56e8 fresh (3.1e4 % apart),
  `converged`, with the info finding still saying "The fit is not biased by
  it". The sentence is in `help.py`'s entry, `_final_compile`'s docstring and
  the skill's `diagnostics.md` row. Reproduce WP-1930's case with
  `ins.profile.w.value *= 1 - 3e-14` before the first fit of
  `test_cell_runaway_safety.py::test_a_wrong_triclinic_le_bail_fit_raises_no_degenerate_cell_error`.
- **`Refinement.report` pairs `result_` with the live models** (from WP-1341,
  2026-10-23). It builds `ParameterTable(self.structure, self.instrument)`
  beside `self.result_` (`refine.py` `report`), so after a cancelled second fit
  or a `set_values` its Layers 1-2 read values that are not the result's. The
  joint `report(h)` was fixed by freezing the answer with the result
  (`multi._freeze_answer`, PR #937). Checked: the single fit's `report` is
  unchanged.
- **#774, the free set reaching the compile.** PR #776 (merged 2026-10-08)
  sizes the FCJ axial floor by value whenever both ratios are positive, so
  `predict()` reads values and not the free set there. The **zero case** is
  open: at exactly zero, free against fixed still differs by max|dy|/max(y) =
  1.66e-4 (re-measured 2026-10-16 at `2c94d848`), because a free ratio at zero
  takes `AXIAL_SIZING_FLOOR` for its nodes *and* its window half-width. The
  issue's options (a) size from values only, (b) freeze and record the count,
  (c) document a tolerance, applied to the zero case, await the maintainer's
  ruling. Sizing by value does not touch the stage-start freeze, so task 2
  stands whichever is taken.
- **The thesis has two more instances, both fixed.** WP-1432: `replay` applied
  a user tie onto a coordinate DOF twice (x = 0.2174 against the node's
  0.2084), fixed by `ParameterTable.rebase_anchored_dofs`. WP-1342:
  `StageResult.held_reach` is a mapping a replay must reproduce, readable only
  while the held column is still in θ. What a state *records* and what
  rebuilding from it *produces* are two objects, and only a test comparing them
  says they agree.
- **Parked here, not this WP's mechanism: the LaB₆/cBN boron esd** (WP-1541,
  2026-10-03). `test_the_one_free_coordinate_agrees` (`lab6_cbn`) gave x =
  0.19838 with esd 2.26e-3 where the row once said 1.7e-3. #674 only shrinks
  esds, so something else moved it; nobody has looked for when.

## Non-goals

- Window sizing (`WINDOW_AREA_TOL`, `WINDOW_MIN_DEG`) and the frozen-per-stage
  invariant. Both stay.
- History node metrics. They stay as-optimised.
- The time-of-flight arm the issue mentions, where an asymmetric profile makes
  the truncation shape-dependent and the minimum does move. Fenced.

## Tasks

- [x] Measure: for every acceptance fixture and every golden, χ² and Rwp on
      the last stage's compile against a fresh compile at θ\*. The table
      goes in the handover and decides (a).
- [x] The statistics block says which compile produced it, and carries the
      fresh-compile χ² when one was measured. The writer is named at review
      (1076). **Closed without a field, 2026-10-25, by the maintainer's
      ruling.** Every result but a Pawley one is now measured on a compile at
      its answer (single fit since #432, joint fit since this WP), so which
      compile produced the figures is a function of `result.mode`, and
      `reference/result.md` says so. A field would be a name whose value the
      mode already fixes. `FROZEN_COMPILE_STALE` quotes both χ² past 1 %.
- [x] Decide (a) from the table. If taken, one compile after the last stage,
      and the goldens regenerated in the same commit with the diff quoted.
- [x] `using/history.md`'s staleness sentence and the results chapter say
      which compile a result's statistics come from.
- [x] Tests: a fixture whose last stage moves a window-sizing parameter
      asserts the statement; under (b) every golden stays bit-identical.
- [x] Skill: a `references/judging.md` row saying which compile a reported
      Rwp comes from, and that the difference is not a fit defect. **Closed,
      2026-10-25, by the maintainer's ruling**: the package's help text and the
      skill's `diagnostics.md` row, keyed by the code and rewritten in this WP,
      carry it, and the skill puts guidance in the cheapest place that holds
      it (WP-1338). The premise "not a fit defect" is also false on two
      measured cases (Context).
- [x] `FROZEN_COMPILE_STALE` claims only what its evidence shows: drop "the
      fit is not biased" from `help.py`, `_final_compile`'s docstring and the
      skill's `diagnostics.md` row, and say what does re-solve (the closing
      stage, an empty stage).
- [x] `Refinement.report` reads the answer frozen with the result, as the
      joint `report(h)` does (`multi._freeze_answer`).
- [x] The joint result is measured on a compile at its answer, as the single
      fit's is, and `MultiHistogramRefinement.report`'s docstring and
      `reference/joint.md` say so.
- [x] #774's zero case: the maintainer's ruling on (a)/(b)/(c), then its
      change or its sentence. **Ruled (c), 2026-10-25**, after the practice
      survey (`docs/practice.md` § Axial divergence at zero) and a probe of
      (a): sizing every zero model at the floor made the gap exactly 0 and
      a default fluorapatite fit 2.0× slower (0.64-0.71 s → 1.32-1.35 s),
      for a gap now 4.8e-5 of the strongest peak. The sentence is in
      `help.py`'s `axial_hl` entry and `Refinement.predict`'s docstring.
      **Re-check when WP-2047 lands**, by the maintainer's instruction: once
      windows follow the parameters between solves, a model at zero could
      size its nodes from the free set (the live derivative) and its windows
      from its value, which may close the gap at no cost. Unmeasured.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_acceptance_si640c.py tests/test_acceptance_fap.py tests/test_fitreport_layers.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

## References

- Issue #272 (2026-09-06; rietx on `origin/main` `2ba7a9a3`).
- WP-1076 (a declared name is a claim); WP-1058 (the stage trajectory).
- `schemas/history.py`'s as-optimised docstring; `docs/manual/using/history.md`.

## Handover log

### 2026-10-25 — closed: the joint fit and every view of a result read the answer; the zero case documented

A result now describes one state wherever it is read. A joint fit's curves and statistics come
from a compile at its answer, as a single fit's have since #432, so its report no longer reads
cut peak tails as unmatched peaks. `report()`, the reflection table, `predict()` and the CIF
writer read the answer saved with the result, so a later fit that is cancelled no longer mixes
its values into the previous result. `FROZEN_COMPILE_STALE` no longer claims the fit is
unbiased: two measured cases contradict that, and its text now says how to re-solve. The large
inherited gap, a plan stopping 9 % above the χ² a re-solve reaches, was already closed for
plans by WP-2002's closing stage, and this session measured that rather than building on the
older finding. A hand-run `run_stage` still has the gap, which is WP-2047's subject.

**Inherited, pruned on arrival** (commit `28e1ef62`): every entry folded into Context, re-checked
at `7e69f974`. WP-1986's and WP-1341's gaps re-measured under the closing stage (Context has the
numbers); the 2026-09-23 reporter claim and the 2026-10-08 "PR #776 open" entry were stale (the
PR merged 2026-10-08); the 2026-10-23 claim that `set_values` leaves `result_` standing was wrong
(`set_values` calls `_invalidate_fit`), so the live-model pairing reached only a cancelled fit.
WP-1432's and WP-1342's instances were folded as one paragraph; WP-1541's boron esd question is
parked in Context, unexamined.

**Done.**
- `FROZEN_COMPILE_STALE`'s help text, `_final_compile`'s docstring and the skill's
  `diagnostics.md` row no longer say "the fit is not biased"; they say a small value or no row
  is not proof of a settled fit, and that one empty stage re-solves (a plan's closing stage does
  it already).
- `Refinement._freeze_answer`, taken where `result_` is built (both runners and the Le Bail
  alternation's kept pass), read by `report()`, `reflection_table()`, `predict()` with no grid
  and `write_cif` (the last two from the code review). Dropped with the result.
- `MultiHistogramRefinement._final_compiles`: one compile per histogram at the answer, the last
  stage's settings, the solve's σ and origin rows carried; `_frozen_compile_diagnostics` is the
  one comparison both runners call; the joint fit tests each histogram and names the worst
  (from the generality judge), with a `(FIT,)` scope row.
- Tasks 2 and 6 closed by the maintainer's ruling (no statistics field; no `judging.md` row).
- #774's zero case ruled (c) after a practice survey (`docs/practice.md` § Axial divergence at
  zero: GSAS-II never computes zero, flooring SH/L at 0.002 in the physics; RIETAN-FP and
  FullProf size from values; TOPAS not read) and a probe of (a). Documented in `help.py`'s axial
  entries and `predict()`'s docstring. The maintainer asked for a re-check when WP-2047 lands;
  the note is in WP-2045's `### Inherited`, since WP-2047 is not on `main` yet.
- `predict()`'s docstring said its two forms differ by the stage-start freeze; since #432 they
  agree bit for bit after a default fit (0 of 5751 channels, fluorapatite).

**Measured** (`[dev]` venv, darwin/arm64, this worktree):
- Closing stage against one more empty stage, fluorapatite tutorial: `mccusker_default` 0.00 %
  (Rwp 0.0945), `mccusker_structural` 0.00 %, `lab_sample_refine` 0.00 %; with
  `closing_window_tol=None` 9.26 %, −1.05 %, −1.08 %.
- Joint WP-1131 size pair, closing off, before the joint compile: reported Rwp 0.09658 / 0.12971,
  38 / 28 unmatched peaks; after: 0.10207 / 0.11839, 0 / 0. Closing on: 0.04078 / 0.08166 either
  way, 0 / 0.
- #774 zero case: 4.8e-5 of the strongest peak today (1.66e-4 on 2026-10-16). Option (a): exactly
  0, and a default fluorapatite fit 0.64-0.71 s → 1.32-1.35 s, Rwp 0.0944624 → 0.0944623.
- After a cancelled second fit, `predict()` differed from `result_.y_calc` by 1041 counts on an
  85 967-count peak before the review's fix; 0 after.
- Counts, `[dev]` venv, darwin/arm64, no other suite running, on the branch merged with
  `origin/main` at `ab5922dd` (WP-2045's PR #1160): fast selection 11 673 passed, 272 skipped,
  27 xfailed in 6:34; slow selection 401 passed, 19 skipped, 16 xfailed, 0 failed in 1:47:37.
  Two tests added, both passes: the fast count was 11 671 on this branch before them, skips
  unchanged at 272. Their local seconds (`tests.added_test_times`): 1.03 s
  (`test_multi_histogram.py::test_a_joint_result_is_measured_on_a_compile_at_its_answer`) and
  0.75 s (`test_run_control.py::test_a_cancelled_second_fit_leaves_the_first_report_alone`),
  neither near the fast tier's tail.

**Code review** (`/code-review high --fix`): findings 1-4, 6, 7 applied (commit `5ee469ad`).
(5), testing each histogram's staleness instead of the sum, was declined here and then taken
on the generality judge's verdict (below). Declined: (8) the
fresh curve is evaluated twice per histogram, once for the comparison and once for `y_calc`; a
forward evaluation is small next to a solve, and avoiding it changes the shared helper's shape.

**Generality** (the `generality-review` judge, on the branch at `5ee469ad`; its sections
with some long cells shortened, the author's answer under each verdict short of "holds").

**1. The joint fit recompiles at its answer (`MultiHistogramRefinement._final_compiles`, multi.py)**

**holds.** The case for acting is much stronger. Every established program that I could check in this repository reports curves built at the final values. The only cost found is one compile per pattern.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides unasked | "the result's curves and statistics from a compile at the values it returns, never the last stage's start-of-stage one" (multi.py comment). Solve, esds, σ and origin rows "stay the solve's" (`_final_compiles` docstring). | It decides which model the reported y_calc, per-pattern Rwp/χ² and the per-pattern report (`report(h)`) are measured on. The as-optimised figure is still on the stage record (`StageResult.cost_final`). The joint path is Rietveld-only (multi.py:1469, :1707), so a hard-coded `mode="rietveld"` loses nothing. | clear |
| 2. Kind | Not stated as a kind. The dispatch calls it "mirroring the single fit's existing `Refinement._final_compile` (#272)". | Kind 1 (arithmetic). A reported curve should be the model evaluated at the reported parameters. Nothing is ranked, and nothing depends on facts outside the pattern. No table row exists to agree or disagree, because the table cannot see an always-on action. | kind 1, unrecorded |
| 3. Case against | — | none found. The figure the solver actually minimised is not lost: it stays on `stages[-1]`. The only visible effect is that the last `stage_end` Rwp now differs from the result's. The test was loosened from `==` to `approx(rel=FROZEN_COMPILE_CHI2_REL/2)` (test_joint_report.py:126-134). | — |
| 4. Case for | WP-1341's numbers, quoted in the WP Context: "38 and 28 unmatched" peaks with the closing stage off, "0 unmatched peaks on each" from a compile at the answer. The removed inherited entry adds "`add_impurity_phase` among the actions". | Strong. Without the recompile, the report told a user to add an impurity phase to a single-phase synthetic. Leaving it to the caller would mean a manual recompile before every report is read. Under default plans the closing stage already hides the gap: "the same five digits" (WP Context). So default joint numbers move only past the fifth digit. No golden file is in the diff. | strong |
| 5. Tier and source | none given | Tier 2 practice, from this repository and not from the programs themselves. practice.md's new section says GSAS-II "windows come from values each evaluation". The `PlanSpec:closing_window_tol` row (_audit.py:2953) says RIETAN-FP's and MAUD's windows also move "every evaluation". Their reported curve is therefore always the model at its values. I did not check FullProf, TOPAS, BGMN or EasyDiffraction. | 2, partly checked |
| 6. Dataset families | One fixture: the WP-1131 size pair (two-wavelength synthetic LaB6, test_multi_histogram.py:490). | One family, synthetic. Its reference is a known truth: one phase, so any unmatched peak is a false finding. That is adequate for a kind-1 act with no threshold. Run-time cost on a joint fit: **none given**. The single fit's cost was measured at 0.024-0.055 s per fit in the 2026-09-24 handover. | adequate |
| 7. Record of firing | The task-2 closure: "which compile produced the figures is a function of `result.mode`". | It always fires, so no field is needed. `FROZEN_COMPILE_STALE` marks a large gap. The frozen cost stays on the last `StageResult`. | adequate |

What would change the verdict: a named workflow that needs the reported χ² to be the minimised objective rather than the value at the answer.

**2. `FROZEN_COMPILE_CHI2_REL` (1e-2) now gates `FROZEN_COMPILE_STALE` on the joint fit, tested on χ² summed over the patterns**

**weak.** The case against the pooled test is stronger. The package's own joint-fit scope table already says a pooled figure can hide one pattern. The fixture this WP measured has per-pattern gaps 30× apart. And the threshold row the dispatch calls audited is not audited.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides unasked | Scope reason: "χ² summed over the histograms, the joint solve's objective (WP-1421)". The dispatch: "A reviewer noted one stale histogram can hide inside the sum; the author kept the pooled test." | It decides whether a joint result carries the finding at all. Pooling also decides that one pattern's gap is judged against every pattern's χ² together. The kept decision has no written reason beyond the scope string. | reason thin |
| 2. Kind | none given. The code row is `Row("FROZEN_COMPILE_STALE", "code")` (_audit.py:573), with no ambiguity field. | Kind 3 in shape: level `info`, it quotes both χ² and stops. But the threshold decides whether the diagnostic exists, which is the generality record's Demotion case ("there is no verdict to keep"). | unrecorded |
| 3. Case against | none given | (a) Package precedent, multi.py:246: `MODEL_FAR_FROM_DATA` is per-pattern because "a pooled Rwp can hide one histogram the model does not describe". (b) On this WP's own fixture with the closing stage off, the quoted Rwp give per-pattern χ² gaps of about 74 % and 2.5 % (my arithmetic). Parameters private to one pattern are fitted by that pattern's χ² alone. That is reasoning, not measured. (c) The threshold does not separate a settled fit from one that stopped short in any case: on the fluorapatite tutorial a 0.8 % gap sat beside a 9.5 % χ² drop on re-solve. | moderate |
| 4. Case for | The scope string: the sum is "the joint solve's objective". | Partly right. A per-pattern test could fire up to N rows, each with an attention cost. Firing rate on joint fits: **none given**. | weak |
| 5. Tier and source | The dispatch: "existing threshold … audited row exists". | **Not so.** `Row("rietx.refine.FROZEN_COMPILE_CHI2_REL", "constant", value=0.01)` has no tier (_audit.py:2280). It is on `UNAUDITED_BASELINE` (:4291), and the code is on it too (:3646) and on `RESPONSE_BASELINE` (:4506). Tier 2: no program has such a diagnostic, since GSAS-II, RIETAN-FP and MAUD re-size windows every evaluation. | unaudited, tier 3 at best |
| 6. Dataset families | For single fits, the constant's comment: Si SRM 640c, FAP, Stephens brucite, a synthetic held-phase ramp, the QPA sample-1 chain. | For single fits: several families, measured against firing rate rather than a known fault. The one known fault (FAP, WP-1986) is a miss. For joint fits: **zero families**. No test makes the joint branch fire. | weak |
| 7. Record of firing | `FROZEN_COMPILE_STALE`, `value` = the relative gap. | It carries no `where`, so it cannot name the pattern responsible. Its row has no `scope` (it sits on `RESPONSE_BASELINE`). | partial |

What would change the verdict: per-pattern gaps measured on joint fits, showing that no single pattern exceeds 1 % while the sum stays under it. Or a written reason why a gap private to one pattern does not matter, plus a test that makes the joint branch fire.

*Author:* taken (commit `0b521af5`). Each pattern's gap is tested and one finding names the worst pattern in its message; the size pair with the closing stage off now fires it on histogram 1 at 17 %, asserted by `test_a_joint_result_is_measured_on_a_compile_at_its_answer`. The judge's 74 % used a compile that ignores the free set, so it is not the pattern's gap. The threshold's tier stays on `UNAUDITED_BASELINE` as it was; this branch adds no row.

**3. The skill and help text: silence is not proof, run one empty stage; "the fit is not biased" removed**

**holds.** The case for the change is stronger. The removed claim has two measured counterexamples, and the new advice is keyed by a code and backed by a practice outside rietx. One sentence of the shared help text is now wrong for joint fits.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides unasked | Skill row and help.py: run one more stage with nothing new freed and compare. | It tells the caller to spend one more stage when the finding fires, and to treat the absence of the finding as saying nothing. | clear |
| 2. Kind | none given | Kind 1 for the advice: re-cycling until nothing moves is what every refiner does. The removal corrects a false statement. | — |
| 3. Case against | none given | The same act fails in two recorded cases on the `closing_window_tol` row (_audit.py:2953): SRM 660c's closing solve 0.908 esd from the fixed point in u, and CPD brucite's S_HKL under TRF. The advice says "compare" rather than "accept", which limits that risk. A joint fit has no `run_stage`, so for it "one more stage" means writing a plan. | weak |
| 4. Case for | WP-1986 (fluorapatite, 0.8 % gap beside a 9.5 % re-solve) and WP-1930 (3.1e4 %, `converged`, "not biased"). | Strong. Two counterexamples against a claim that rested on #272's two good fixtures. BGMN ends every refinement with a closing run by default (Doebelin & Kleeberg 2015, cited on the `closing_window_tol` row; not checked by the judge). | strong |
| 5. Tier and source | — | Prose, so no tier. | — |
| 6. Dataset families | FAP and synthetic Si. | Enough to withdraw a claim, not to set a threshold. | adequate for a withdrawal |
| 7. Record of firing | — | **Defect:** help.py still says "The history node keeps the earlier figure"; a joint fit keeps no history node. | one fix owed |

What would change the verdict: a case where an empty stage moved a well-determined parameter away from a certified reference.

*Author:* the defect is fixed in `0b521af5`.

**4. The axial-divergence sizing floor at zero, documented**

**holds as documentation.** A measured 2× slowdown against a 4.8e-5 effect, ruled by the maintainer. The number is inconsistent within the diff, and the floor's row does not record that rietx sits outside the surveyed practice.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides unasked | help.py: windows sized for 0.02 at zero when refined. | "Windows" understates this: the floor sizes the FCJ nodes too (forward.py:3792-3795). | wording incomplete |
| 2. Kind | Row: "A numerical setting whose domain test fails over part of the domain it claims; tier 3" (_audit.py:1593). | Kind 1, a numerical setting: a usable derivative from zero. The row agrees. | agrees |
| 3. Case against | — | practice.md: "No program read makes a calculation depend on whether a parameter is refined." The `AXIAL_SIZING_FLOOR` row (_audit.py:1583-1599) does not mention the free-set dependence, the survey or the ruling. `MAGNETIC_SIZING_FLOOR` has the same zero-case shape (forward.py:4008-4013) and is not documented here. | moderate |
| 4. Case for | Option (a) 2.0× slower for a 4.8e-5 gap; ruled (c); re-check owed when WP-2047 lands. | Strong. | strong |
| 5. Tier and source | Row: tier 3, approved 2026-10-22. | Unchanged. | as recorded |
| 6. Dataset families | The rutile reproducer; FAP for the cost. | **Defect:** practice.md says 1.66e-4, help.py about 5e-5, the docstring 4.8e-5. | inconsistent |
| 7. Record of firing | none given | No field records that a compile was sized at the floor. | none |

What would change the verdict: a default in TOPAS, BGMN, MAUD or EasyDiffraction that also lets a refine flag reach the curve, or a second specimen putting the gap near the closing stage's tolerance.

*Author:* wording and number fixed in `0b521af5`. The `AXIAL_SIZING_FLOOR` row's text is left as it is: amending a tiered row's grounds is the maintainer's call, and the departure from practice is recorded in `docs/practice.md` and this WP. The magnetic sibling is unmeasured; it is named in WP-2045's note for WP-2047 beside the axial check.

**Gotchas.** `run_stage` has no closing stage, so the guides' quoted gaps (`next.md`,
`stage.md`) still stand and are correct. The joint event-log test now reads the last
`stage_end` Rwp as the as-optimised figure, within half of `FROZEN_COMPILE_CHI2_REL`.

**Next.** None in this WP. When WP-2047 lands, its session folds WP-2045's note and tests the
split sizing at zero (nodes from the free set, windows from the value).

### 2026-09-24 — landed from outside under shape (a); a result is measured on a compile at its own values

`Refinement.fit` and `run_stage` now end with one more compile at the values
the result returns (`Refinement._final_compile`). It is built with the last
stage's own discrete settings (the moving set, c_w and the window slack), so
only the values differ. This is issue #272's fix, live since PR #432 merged
(`09ce2cd1`, closing #272). It came from an outside contributor with no
`WP-NNNN:` prefix and no touch of this file, so this entry is written at the
merge. The WP stays `⬜`: two tasks are open in part, and no session owns it.

**The measurement, and why it took (a) rather than the recommended (b).** The
relative χ² gap between the frozen and the fresh compile was logged on 358
fits, across the acceptance files and the synthetic chains.

- Single-pattern acceptance, maximum per file: si640c 8.4e-5, fap 2.0e-4,
  capillary 6.1e-5, nac 1.6e-4, srm676a 5.2e-4, lab6_cbn 5.5e-4, extra_peaks
  6.4e-4, dispersion 1.1e-3, powderline 1.1e-3, qpa_roundrobin 1.1e-3,
  stephens 2.5e-3, fitreport_layers 2.4e-3.
- Synthetic chains: held_phase 5.2e-3, test_sequential 2.0e-3.
- The QPA sample-1 chain: 1.3-2.1e-2.

(a) costs one compile, 0.055 s on the Si 640c fit (3.7 s) and 0.024 s on FAP.
(b) would have needed the sizing decision to be observable. **No golden
moved.** On Si 640c the fresh compile gives χ² 88 283.25 against the frozen
88 284.16, so the reported Rwp 0.08263 stands. The issue's 89 501.76 is
reproduced exactly by `compile_model(..., moving_paths=None)`. Its 1.38 %
therefore comes from the moving-set sizing claim, not from the
start-of-stage freeze. `results.md` says how to reproduce a result's number.

**What the merge makes possible.** A result's `y_calc`, statistics and
per-point residuals reproduce from a rebuild at `result.parameters`. The
history node keeps its as-optimised metrics. The info finding
`FROZEN_COMPILE_STALE` quotes both χ² when they differ by more than
`FROZEN_COMPILE_CHI2_REL` = 1e-2. At 1e-3 it fired on 74 of the 358 fits; at
1e-2 it fires on 6, all of them in the sample-1 chain.
`sequential.NOT_A_SERIES_FINDING` keeps it out of
`SEQUENTIAL_PERSISTENT_FINDING`.

**What it deliberately does not do.**

- The solve, the covariance and every esd stay the last solve's.
- **The weights stay the solve's.** `result.sigma` is still a lookup of the σ
  the model used (WP-1309), because a measured background widens σ at the
  scale a compile sees. A test pins this on a fit whose last stage moves the
  background scale.
- A **Pawley** result and a **joint** fit (`multi.py` builds its own) get no
  fresh compile. Both report the frozen figures and never carry the row.
  `results.md` and the diagnostics row say so, because round 1 of the review
  asked for it.
- The statistics block has no field naming its compile. The fresh χ² appears
  only in the finding's message, past the threshold. That is task 2 in part.
- There is no `judging.md` row (task 6); the `diagnostics.md` row stands in
  for it.

**Measured on the merged tree** (`origin/main` `2d42303a`
plus #430, #432 and #431; Linux x86_64, 4 cores, python 3.12, `[dev,jax]`):

- Fast suite: 1 failed, 5944 passed, 96 skipped. The failure is
  `test_telemetry.py`'s unwritable-directory case, which fails on main alone
  because the bench runs as root.
- Fast collect with #432 alone on main: 6015 → 6022, +7.
- Full `-m slow`: 2 failed, 188 passed, 9 skipped in 1:32:45. Neither failure
  is #432's. The brucite XPASS(strict) is red on main's own nightly (run 51).
  The held-phase ramp tripped its 60 s runaway guard at 147 s under load. Run
  alone it passes, in 21.4 s on this tree against 20.3 s on main, the difference being the one extra
  compile per pattern.
- `ruff`: clean.

**Next.** Decide whether task 2's "says which compile produced it" still
wants a field now that every non-Pawley, single-histogram result is
fresh-compiled. Then decide whether task 6's `judging.md` row adds anything
the diagnostics row does not already say.

- **2026-09-15** — created, from the 2026-09-15 issue triage (issue #272).
  Checked against the tree: `_build_result` evaluates the stage's own model;
  the as-optimised convention lives in `schemas/history.py` and
  `using/history.md` and was written for nodes, not results. Recommendation
  recorded: state before move.
