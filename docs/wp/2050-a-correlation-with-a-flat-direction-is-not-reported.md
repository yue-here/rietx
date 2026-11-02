# WP-2050 — a correlation with a flat direction is not reported as one

Milestone: unscheduled · Status: ✅ 2026-11-02 — `HIGH_CORRELATION` reports no pair against a direction the data does not determine; brucite's count holds at 35 under rounding nudges (PR #1306)
Track: What fires, and what stays silent
Depends on: —

## Goal

`HIGH_CORRELATION` names only pairs whose ρ the data determines. A pair whose
partner is a member of a flat direction (an esd of order 10³ on a value of
order 10⁻²) is either not reported or reported as that, and the warning count
on a fit no longer moves under a 1e-14 nudge to its start.

## Context

`tests/test_suite_alarms.py::test_the_standards_fire_what_the_pin_says` was red
on the Linux nightly on `deff4c301` (run 40184228951): warnings per result rose
by exactly 0.75 under every purpose against `tests/data/suite_alarms.json`, re-pinned
on an arm64 Mac by WP-2045 the same day. The per-standard codes did not move,
only their counts.

**Measured 2026-10-25** (`deff4c301`, macOS arm64, `[dev]`) by a lane of
WP-2036's session. At the unnudged starts the eight standards carry brucite 36,
zincite 14, fluorite 12, corundum 11, SRM 660c 2, FAP 1, NAC 0 and the LaB6
capillary 0 warnings: 76/8 = 9.5, the pin. Under 1e-14 nudges to one start
value only brucite moves, to 35, 36, 39 or 42, at an Rwp of 0.4690163639 every
time. With brucite's start scale nudged by +4e-14 and the rest unnudged the
module prints exactly Linux's seven lines. Brucite's six extra warnings are all
`HIGH_CORRELATION`: `lor_size` and `lor_strain`, each against `gauss_size`,
`gauss_strain` and `instrument.profile.w`, at ρ 0.991 and 0.988 against the 0.98
limit. Those three partners are an exactly flat triple: values 0, 0 and 0.0132,
each with an esd of about 1124. A ρ against one member of a flat direction is
numerically undetermined, so the count is rounding. The probes are in
`docs/wp/2050-batch/`.

The guard is the pairwise loop in `strategy/staged.py:2083-2089` over
`outcome.correlation`. The esd authority is `statistics.normal_covariance`
(root CLAUDE.md § Invariants: a direction the data does not move has no esd
rather than a small one, and a row on its bound stays in the matrix, WP-1929).
Here no column is gradient-free, so `_cov_free` keeps all three and they come
back with huge finite esds.

The tier of each rule this WP adds: new judgement, unless practice has one.
Which esd marks a direction as flat is a threshold. Read `docs/practice.md`
first, and survey how GSAS-II and TOPAS report a correlation with an
undetermined parameter. The datasets it must hold on are the eight alarm
standards, brucite above all.

**Superseded in part, 2026-11-01** (re-measured on `62034506e`, after
WP-2048 merged; macOS arm64, `[dev]`). The counts reproduce: brucite 36 at
k = 0 and 42 at a +4e-14 scale nudge, 35 at −4, ±1 and +7. Two findings
change the frame.

- **The partner rule alone cannot hold the count.** `lor_size ~ lor_strain`
  is a pair of non-members, and it flips too: −0.995 at k = 0, −0.9975 at +4,
  under the guard at −4. Both columns load weakly on the flat direction, and
  that loading is divided by an eigenvalue rounding sets. With the direction
  projected out the pair reads −0.896 and −0.893.
- **What marks the direction is its eigenvalue, not an esd.** In the
  unit-diagonal normal matrix of the closing stage, the triple's eigenvalue is
  2.7e-15 to 4.9e-14 of the largest across the nudges. That is an 18-fold
  spread, so rounding sets it. The next direction (zero shift with sample
  displacement) holds at 1.3e-10 to 1.4e-10. The forward-difference columns
  are accurate to about `FD_STEP` = 1e-6 relative, so an eigenvalue under
  FD_STEP² = 1e-12 of the largest lies inside the Jacobian's own error.

The test is `statistics.resolved_correlation` (task 1). The guard reads the
correlation with every direction under that cut projected out. A pair with
one member of such a direction is `nan` there and is never thresholded. A pair
of members keeps its full-matrix ρ, which is ±1 to rounding and stays a
`FLAT_DIRECTION`. Simulated in-process on the eight alarm standards
(`docs/wp/2050-batch/simulate.py`), brucite gives 35 warnings at all eight
nudges (k = 0, ±1, ±4, +7, ±20) and the other seven are unchanged at k = 0
and +4. Corundum, zincite and fluorite carry the same unresolved triple, and
none of their reported pairs involves it.

## Non-goals

- Brucite's flat triple itself: the Gaussian size, Gaussian strain and W
  degeneracy is a protocol question for its standard.
- The pin's design. Once brucite's count is stable, re-pin it once.

## Tasks

- [x] Survey practice (above) and pick the test for "this partner's ρ is not
      determined", measured on brucite's triple and on the other seven
      standards, with no pair dropped that a refiner would want reported.
      Survey: `docs/practice.md` § Correlations against a parameter the data
      does not determine. Test: `statistics.resolved_correlation`, cut
      FD_STEP² × |λ|max, members by `discarded_directions`' touched rule;
      `top_correlations` skips a `nan` pair. Settled by Claude under
      established practice (GSAS-II's truncated pseudo-inverse) and the
      measurement above, which chose the cut. GSAS-II's own 1e-6 lost: it
      would also project out the zero-shift/displacement direction at
      1.4e-10, whose pairs hold to 2e-5 under the nudges and which a refiner
      wants reported. Tier: derived (the cut is the Jacobian's accuracy).
- [x] Apply it in the guard loop. Say in the message what was left out and why,
      rather than dropping it silently. `check_guards` reads the resolved
      matrix for the findings and `measured_top_correlations` alike. The
      message clause this task added was dropped by Yue's ruling of
      2026-11-01 (handover log): the withheld pairs are named by
      `resolved_correlation`'s mask, which a nightly test asserts. The cut became absolute,
      n·FD_STEP² on the unit-diagonal matrix (the Frobenius bound on n
      columns' forward-difference error), after corundum's triple sat at
      1.2-1.9e-12 of |λ|max, above the relative FD_STEP².
- [x] Tests: brucite's count is the same at the nudges in
      `docs/wp/2050-batch/`; re-pin `tests/data/suite_alarms.json`.
      `test_suite_alarms.py::test_brucites_correlation_findings_do_not_move_under_a_rounding_nudge`
      (k = 0, ±4; slow), `test_the_closing_stage_names_the_flat_width_triple_unresolved`
      (four round-robin standards; slow) and `tests/test_resolved_correlation.py`. The re-pin
      moves every purpose's warnings per result down by exactly 1/8: the one
      warning brucite lost is `lor_size ~ lor_strain`, whose determined ρ is
      −0.896, under the 0.98 guard.
- [x] Skill: `HIGH_CORRELATION`'s row in `references/diagnostics.md`, if the
      message changes. No message changes after the ruling, so no skill row
      does.

## Acceptance

```sh
.venv/bin/python -m pytest -n auto --dist loadgroup tests/test_suite_alarms.py tests/test_high_correlation_dedup.py
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-2037 (the alarm pin), WP-1929 (a bound row stays in the matrix),
  WP-1110 item 14 (`normal_covariance`), WP-2036 (found it on the nightly).

## Handover log

- **2026-11-02** — closed (PR PRNUM). PR #1306 merged on 2026-11-02, so a fit
  no longer reports a correlation whose value is set by rounding. Every task
  here was already ticked. This entry closes the file and re-measures nothing.
  *Done*: Status ✅, the Priority line deleted, the narrative moved to the
  v1.11 record, a line staged in the 1.11.0 notes under "Numbers that move"
  (the merge had not staged one), the index regenerated. *Next*: none here.
  WP-2036's nightly waited on this WP (its `Depends on:` line).
- **2026-11-01** — ruling applied, PR #1306.

  *Ruled* (Yue, in chat, 2026-11-01: "as you recommend"). (1) Drop the
  clause from `FLAT_DIRECTION`, so its message reads as on `main`, and
  revert every test, skill row, help entry and docs line quoting it. (2)
  Keep the unresolved pairs out of the report: a `HIGH_CORRELATION` pair
  with one unresolved member stays `nan` and unreported, so the only change
  a user sees is one fewer warning on brucite (36 → 35). (3) A nightly test
  calls `statistics.resolved_correlation` on brucite, corundum, zincite and
  fluorite and asserts the Gaussian size, Gaussian strain and W columns
  come back unresolved and brucite's zero-shift/displacement pair does
  not. (4) The cut n·FD_STEP² is approved, its free factor named as a
  module constant with a tier-3 `rietx._audit` row. The design rule behind
  it: a correlation whose value is rounding is not shown to users, and the
  developer's signal is a callable function a nightly test asserts on.

  *Done.* `GuardFinding.flat_direction` and the skill's three
  `diagnostics.md` copies are back to `main`, and the clause's fast test is
  gone (`help.py` and the manual never quoted it).
  `statistics.FD_COLUMN_ERROR` = 1.0 is the per-column error in units of
  FD_STEP, with its tier-3 row (approved 2026-11-01, grounds the margins
  below, evidence from the generality review).
  `test_suite_alarms.py::test_the_closing_stage_names_the_flat_width_triple_unresolved`
  (slow, four parametrised rows, about 5 s in all) wraps `check_guards` to
  take the closing stage's Jacobian and asserts the mask. WP-1460's
  Inherited note and the function's docstring no longer mention a clause.

  *Gates* (macOS arm64, `[dev]`). Acceptance command: 17 passed (13 before,
  plus the four new rows). `test_audit_table.py`, `test_help.py`,
  `test_docs_consistency.py` and `test_resolved_correlation.py` with it: 99
  passed. `tests/audit_delta.py` against `origin/main`: 1 added, 0 new at
  `unaudited`. `python -m tests.reader_output`: exit 0, unchanged. Ruff
  clean. Fast suite: 1 failed, 13194 passed, 310 skipped, 32 xfailed
  (passed+skipped −1, the clause test removed). The failure is the same
  environmental `test_display.py` kernel row as before.

  *Next.* Review and merge PR #1306. Nothing waits on a ruling.

- **2026-11-01** — ghostshift runner, PR #1306. All four tasks landed. Two
  maintainer calls wait before merge (below).

  Brucite's warning count no longer depends on rounding. Before, a 1e-14
  change to one start value gave 35, 36, 39 or 42 warnings; now it gives 35
  at all eight nudges tried. The cause was one direction in the fit that the
  data does not determine: the Gaussian size, the Gaussian strain and W,
  which are exactly degenerate. The correlation guard used to report ρ
  against those three, and those ρ were set by rounding. It now drops them,
  and the FLAT_DIRECTION message says so. The other seven alarm standards
  report what they did before. Every purpose's warnings per result fell by
  exactly 1/8: brucite lost one warning, `lor_size ~ lor_strain`, whose ρ
  with the flat direction removed is −0.896.

  *Done.* `statistics.resolved_correlation` removes from the correlation
  every eigen-direction of the unit-diagonal normal matrix at or below
  n·FD_STEP² (n = live columns). That is the Frobenius bound on n columns
  that each carry a forward-difference error of FD_STEP. It names the columns
  such a direction dominates, using `discarded_directions`' touched test at
  this cut. `check_guards` hands the projected matrix to the
  correlation/flat loop and to `measured_top_correlations` (one matrix, as
  WP-1056 requires). A pair with one unresolved member is `nan`, and
  `top_correlations` skips it. A FLAT_DIRECTION pair of two members gains
  "; ρ against either is not determined and is not reported". There is a
  practice survey in `docs/practice.md`. The skill's FLAT_DIRECTION row is
  updated. `tests/data/suite_alarms.json` is re-pinned.

  *Measured* (macOS arm64, `[dev]`). Brucite gives 35 warnings at scale
  nudges k = 0, ±1, ±4, +7, ±20 (`row4_probe.py`). The other seven standards
  are unchanged at k = 0 and +4. Per stage, the triple's eigenvalue against
  the cut (`perstage.py` in this session's scratch, not committed): the
  closing stage of brucite, corundum, zincite and fluorite reads 0.004-0.47×;
  brucite's 1.4e-10 zero-shift/displacement direction reads ≥ 31×; SRM 660c,
  FAP, NAC and the capillary have nothing within 1000× of it. The relative
  cut FD_STEP²·|λ|max, tried first, misread corundum: its triple sat at
  1.2-1.9e-12 of |λ|max in the later stages. The FLAT_DIRECTION clause is
  the same in 19 of 20 standard-by-nudge cases. In the 20th, brucite at
  k = −4, the seventh stage has the triple at 2.3× the cut. The dedup keeps
  that stage's message for two of the three pairs, so those two lose the
  clause; their count does not change. `python -m tests.reader_output` exit
  0: its fit has no unresolved direction. Fast suite: 1 failed, 13195 passed, 310 skipped, 32 xfailed (`-m "not slow"`, `[dev]`, macOS arm64, alone on the machine through the suite lock). The one failure is `test_display.py::test_a_plot_in_a_kernel_shows_once_and_leaves_the_backend_alone`: this Mac's user Jupyter kernel spec points at a deleted venv, which is unrelated to this branch. Added
  tests: 9 in `tests/test_resolved_correlation.py` (fast) and one slow
  brucite row in `test_suite_alarms.py`. The nine fast tests cost 0.03 s in all (local junit). The slow row ran alone in 6.6 s.

  *Review.* `/code-review high --fix` made 10 findings. Kept: the skill
  wording and `top_correlations`' docstring. Reverted: its change to
  `_correlation_findings` and its hoist of `covariance_jacobian`. The lead
  allowed only `check_guards` and `flat_direction` in `staged.py`, and the
  hoist moved the call out of its LinAlgError guard. Declined, stated as
  limits in `resolved_correlation`'s docstring: the error premise
  (`FD_STEP`'s row records some columns to 2.5e-4); n-scaling (at 60
  columns the cut is 12× under the zero-shift direction); two unresolved
  directions. Declined, out of scope: the joint fit in `multi.py` (the lead's
  file boundary); Pawley (`n_aux`) fits, which skip the projection as
  `check_discarded_directions` does; the shared-eigh refactor (it would touch
  `discarded_directions`, whose bits are pinned).

  *Generality.* The generality-review agent's report is pasted unedited
  into `docs/wp/2050-batch/generality-review.md`, because at about 2 500
  words it would bury this log. All four items came back **weak**. Author's
  answers:
  (1) The cut needs a tier-3 row, with the maintainer's approval, for its
  free factor (the error per column, 1 × FD_STEP). Answer: agreed. A tier-3
  row cannot be written without Yue's dated approval, so the cut stays inline
  and the approval is asked in the PR. The judge's point that the eight-nudge
  count ran under the earlier relative cut is answered by `row4_probe.py`,
  re-run under the shipped cut: 35 at all eight nudges.
  (2) A lone member is withheld silently. Answer: stated in the docstring,
  and moved to WP-1460's Inherited; its set-level finding is the natural
  record.
  (3) No record field names the unresolved set (Rule 4). Answer: that is
  WP-1460's finding too. Adding a result field here would be a second
  reader-output change for Yue; the PR asks.
  (4) The skill sentence was wrong for pairs inside the set. Answer: reworded
  with the judge's wording. `CorrelationPair`'s stale docstring is fixed.

  *Not generalised.* The esds. `lor_size`'s esd moves 55 % across the nudges
  (0.185 against 0.287), and the triple's (≈ 6000) are rounding too. The raw
  correlation feeds `stderr_physical` and QPA propagation, so that belongs to
  the esd authority (`normal_covariance`). No open WP owns it.

  *Next.* (1) Yue: approve or reverse the cut's tier-3 row (below). (2) Yue:
  the FLAT_DIRECTION wording, a reader-output change. (3) Then add the
  `_audit` row with the approval date. If the cut is reversed, the fallback
  is GSAS-II's 1e-6 relative cut, which also drops the zero-shift pairs.
- **2026-10-25** — filed by WP-2036's session after a measurement lane
  reproduced the nightly's alarm red on an arm64 Mac. No open WP owns the
  guard: WP-2037, which made the pin, is closed. Next: the first task.
