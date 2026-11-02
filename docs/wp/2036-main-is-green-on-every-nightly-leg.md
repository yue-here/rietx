# WP-2036 — main is green on every nightly leg: a full suite that finishes, two Windows tooling tests, and answers that move with the platform

Milestone: unscheduled · Status: 🔄 2026-11-02 — claimed by @yue-here (ghostshift runner, main-health): three rows red on the 11-01 nightly, two nights cancelled at the cap
Track: The repo's own process
Depends on: 2045 (the `full` job cannot finish before it); 2048, 2049 and 2050 (three slow rows red by rounding until each lands); 2002 soft, the closing stage that moved most of these; 2012 soft, the LaB6 axial mirror
Priority: P3 2026-11-01 — every task here is done; a green nightly waits on WP-2049 and 2050, and on WP-2048's PR #1292 merging

## Goal

Every job of `nightly.yml` passes on `main`, and the full suite passes on an arm64 Mac.
Each answer a guide page or an acceptance test quotes is either the same on every
platform or quoted only to the precision the platforms share.

## Context

`nightly.yml` runs six jobs at 06:00 UTC. It has been red every night from 2026-10-16
to 2026-10-23, the last run checked (run 39940543791, `3e0dc6f7`). The failures have
four separate causes. They share this WP because they share its acceptance: one green
nightly.

**1. The Linux full suite no longer finishes.** On 2026-10-22 (`d01ae735`) the job
`full suite (Linux, incl. slow acceptance)` ran the whole suite in 1 h 37 min. On
2026-10-23 it reached 32 % at its 150-minute `timeout-minutes` and was cancelled, so it
printed no `--durations` table. Two stretches account for most of it: 7 % → 11 % took
48 min and 11 % → 15 % took 52 min. The four fast jobs took the same time on both days
(Linux 3.12: 15 and 18 min). PR #1085 merged between the two runs, at 23:30 on
2026-10-22. It is WP-2002's single-fit actions, which end every plan in a closing stage
at tight windows. So the full suite has not completed on Linux since the closing stage
landed. The slow tests that #1085 added or moved have therefore never run on Linux on
`main`. On an arm64 Mac the slow selection takes 18-19 min. The job's comment records
an earlier budget: 77 min of the old runtime was indexing-acceptance fixture setup on
the 2-core runner. Cause not measured. `workflow_dispatch` is on, so a run can be
started by hand.

**2. Two Windows-only tooling failures.** Both appear only in `fast suite (Windows)`.
- `tests/test_closed_wp_writes.py`, 5 tests, red every night since 2026-10-17. WP-1994
  shipped `.claude/hooks/closed_wp_writes.py` on 2026-10-16. Each test gets `[]` where
  it expects a closed WP (`assert [] == ['0001-closed.md']`). *Hypothesis, not run*:
  `_git` calls `subprocess.run(..., text=True)` with no `encoding=`, so Windows decodes
  git's UTF-8 output as cp1252. Every byte of ✅ (E2 9C 85) decodes in cp1252, so
  nothing raises. The status then reads `âœ…`, `wp_index.STATUS_RE` never matches, and
  no WP looks closed. Seven more hooks call `subprocess.run(text=True)` without
  `encoding=` (`handover_owed.py`, `session_start.py` ×3, `session_usage.py`,
  `worktree_remove.py`, `worktree_only.py`, `worktree_create.py` ×2).
  `tests/test_portability.py::test_every_text_io_call_names_its_encoding` exists for this
  class and does not see `subprocess.run(text=True)`.
- `tests/test_manual.py::test_the_page_contract_fails_what_it_should`, 2 errors, red
  since at least 2026-10-16: `ValueError: the environment variable is longer than 32767
  characters`, at setup and at teardown. *Hypothesis, not run*: pytest writes each
  test's node id into `PYTEST_CURRENT_TEST`, and this test's parametrize id is the
  page text itself, which runs past Windows' 32 767-character limit. An `ids=` would
  fix it.

**3. Two guide scripts print different numbers on different platforms.**
`tests/test_examples.py::test_every_guide_script_prints_what_its_page_quotes` runs each
`examples/guides/*.py` and checks that its page quotes only lines the script printed.
Linux passes both cases below. macOS CI failed `moment` on 2026-10-22 and `qpa` on
2026-10-23. Windows failed `moment` on 2026-10-23. An arm64 Mac (`[dev,jax]`, Python
3.12) fails both on `882644c1`.
- `qpa`. `docs/docs/guides/qpa.md` quotes `NAC 96.92 ± 2.24 wt%` and `CaF2 3.08 ±
  2.24 wt%`. On the Mac the script prints the same fractions at **± 0.21 wt %**. This is
  not rounding: one esd is ten times the other. The same run prints `HIGH_CORRELATION`
  on `phases.1.scale ~ phases.1.extinction` (ρ = +0.996) and `FLOOR_HIT` on two CaF₂
  Biso values. A near-singular block like that is where an esd depends on how the
  covariance is cut, so the platforms' LAPACK builds are a suspect. On the Mac SciPy
  and numpy link Accelerate, and on Linux OpenBLAS (WP-2002, 2026-10-21: Accelerate's
  `gesdd` failed where OpenBLAS's decomposed). Not measured. Which esd is honest is the
  question, and a user quoting either one is told nothing.
- `moment`. WP-2002 found on 2026-10-22 that the guide's two refinement rounds stop at
  one of two nearby points under a 1e-14 nudge to the start (0.41 or 0.47 esd of scale
  shift; Linux takes one, the Mac the other). It changed the page to quote only what
  both share (`6f1d131d`). The page still fails. On Windows it quotes `|m| = 2.04 ±
  0.05 μB` where the script printed `2.03 ± 0.05`. On the Mac the script stops at
  `examples/guides/moment.py:112`, `assert steps[1][0] < 0.001` (round 2's move in
  |m|).

**4. Four slow tests fail on an arm64 Mac.** They fail on `main` `12f459e5`, which
contains #1085 (darwin/arm64, `[dev,jax]`, nothing else running; full `-m slow`
selection 4 failed, 404 passed, 12 skipped, 14 xfailed in 18 min 23 s). Whether they
fail on Linux is unknown until item 1 is fixed.
- `test_staged_start_invariance.py::test_the_biso_start_does_not_change_the_answer[cpd1a]`:
  Biso starts 0.5 and 1.5 Å² land 0.175 plain esd apart on `instrument.profile.x`
  (bar 0.1; plain esd is the esd without the Bérar-Lelann inflation). WP-2012's
  Inherited notes the cause: cpd-1a's QPA protocol frees the instrument Lorentzian `x`
  and each phase's `lor_size` together. Both go as 1/cosθ, so only their sum is
  determined.
- `…::test_the_axial_sizing_floor_does_not_change_the_answer[lab6]`: `AXIAL_SIZING_FLOOR`
  0.02 against 0.05 lands 8.82 plain esd apart on `instrument.geometry.axial_hl`. This is
  WP-2012's S/L ↔ H/L mirror. The test's lab6 Biso row is already a strict xfail citing
  WP-2012, and this row is not.
- `…::test_the_axial_sizing_floor_does_not_change_the_answer[cpd1a]`: a strict xfail
  that passes (XPASS(strict)). Its reason expects 0.138 plain esd on corundum's cell c
  behind the closing stage, and here it comes in under the bar.
- `test_acceptance_magnetic.py::test_the_150k_null_finds_no_moment`: the null's Rwp is
  0.0991227 against the nuclear-only fit's 0.0992423, 1.2e-3 relative against a bar of
  1e-3. The moment is still reported unsupported. The Rwp assertion is the only one
  that fails.

Items 3 and 4 are one class: a fit with two nearby stopping points, where the platform
picks the point. The local reproduction is a relative nudge of 1e-14 to one start value,
which reproduced Linux's answer on a Mac in WP-1930. A test or page that quotes one
stopping point's digits fails on the other platform whatever the code does.

The full Linux job failed once before in this window, on 2026-10-17:
`test_lebail_alternation.py::test_the_state_the_loop_keeps_is_the_state_a_hand_loop_would_continue_from`.
It passed on every later night, so it is out of scope unless it recurs.

**Since 2026-10-24** (folded from the Inherited notes of WP-2003, 2037, 2043
and 2045 on 2026-10-25):
- **The `full` job's hang was one closing stage, and #1161 cut it.** The
  hostile series' (`test_acceptance_sequential.py`, `chained_all`) cpd-1b warm
  fit stopped at `axial_sl` 557.8 and its closing stage ran to its cap, over
  50 CPU-minutes (WP-2043). WP-2045 made the last declared stage converge, and
  the module now runs whole in 92 s on an arm64 Mac. The Linux before is the
  `c9dde14` run (40116626316), which completed in 1:55:14 with 6252 s of that
  series' fixture setup. A lead WP-2003 measured on a 4-core Linux container
  may still cost Linux time: FCJ node counts that climb to the 512 cap miss
  the `leggauss` cache, and with default BLAS threading one
  `leggauss(444)` took 5.4-6.0 s against 0.014 s on one thread
  (`model/profiles/fcj.py:88-92`; `docs/wp/2003-batch/reseed.md`).
- **The same `c9dde14` run was red on three slow rows**: the Le Bail NaN raise
  (task below, now WP-2048), `test_the_intermediate_tolerance_does_not_change_the_answer[lab6]`
  as XPASS(strict), and the lab6 axial-floor row at 8.820 plain esd.
- **`moment` failed on Linux x86-64 at `1174cbf`** (WP-2037's container,
  `[dev]`): round 1's move in |m| was 0.1034 against the script's `< 0.10`.
- **An extra-peaks assertion holds by 0.3 ppm against an esd of about 51**
  (WP-2043): `tests/test_acceptance_extra_peaks.py:230` asserts that declaring
  the intruder recovers the clean cell more closely than ignoring it, −0.1
  against −0.4 ppm on 1.10.0. A rounding change can reverse it with no physics
  change. What the data supports is that ignoring costs the cell its
  precision (esd ×9.9). Which to assert is the maintainer's call, and the
  docstring's "ignored must not recover" is stale.
- **An indexing answer's axis order moves with the platform** (WP-2043):
  notebook 03's orthorhombic P cell printed a and c swapped on Linux. No prose
  quotes the order, so nothing fails.

### Inherited

- **2026-11-01, from WP-2048** (PR #1292, open at this writing): the
  triclinic Le Bail row no longer raises. A stage whose model goes non-finite
  ends at its start with `STAGE_NOT_FINITE`, and all six nudged starts return
  a finite Rwp on macOS arm64. The row is now parametrised `start`/`nudged`,
  the second in its own xdist group, so the nightly's `full` job runs one more
  slow case (233 s locally under load). Once #1292 merges, the green nightly
  waits on 2049 and 2050 alone.

## Non-goals

- Removing the S/L ↔ H/L mirror or the `x`/`lor_size` degeneracy. Those are WP-2012's.
  This WP marks the rows that fail because of them, citing WP-2012, as the lab6 Biso row
  already does.
- WP-2002's open rulings (the evaluation windows, its sixth round).
- Raising `timeout-minutes` without the durations table that says why. The job's
  timeout is a runaway guard (root CLAUDE.md § Testing headlines).

## Tasks

- [x] Linux full suite: start `nightly.yml` by hand on `main` with `--durations=50`
      reachable (a temporary branch workflow if needed), find what slowed after #1085,
      and fix the cause. Rebudget only if the cost is the closing stage's own and the
      durations table says so. *Cause found by WP-2043: the hostile series' closing
      stage at a runaway answer, which WP-2045 owns. What remains here is the re-run
      and its durations table once 2045 lands.* *Done 2026-10-25 by the
      scheduled nightly on `deff4c301` (run 40184228951): the job completed in
      2:05:47, 4 failed / 12 157 passed / 218 skipped / 41 xfailed. The hostile
      series left the 25 slowest rows. Against 2026-10-22 (1:36:13, 11 586 tests)
      the suite gained 830 tests and 30 min spread across it, with no row the
      closing stage's own, so the limit was not rebudgeted. Its margin is now
      1.19×; the next session reading a timeout reads this table first.*
- [x] Windows `test_manual`: give the page-contract cases `ids=`, and confirm on the
      Windows leg. *Done by WP-2043 (#1146): the long page is `id="over-the-cap"`;
      the Windows suite passed every test on `ac1ee1e`.*
- [x] Windows `closed_wp_writes`: confirm the cp1252 hypothesis on a Mac (run `_git`'s
      decode as `cp1252`), name `encoding="utf-8"` on every `subprocess.run(text=True)`
      in `.claude/hooks/`, and extend `test_every_text_io_call_names_its_encoding` to see
      `subprocess.run(text=True)` and to walk `.claude/hooks/`. *Done by WP-2043
      (#1146): `tests/test_portability.py` walks `.claude/hooks/` and `.claude/skills/`
      and sees text-mode `subprocess` calls.*
- [x] `qpa` guide: find why the esd differs tenfold between Linux and the Mac, decide
      which is honest, and fix the package if the covariance depends on the LAPACK
      build. Change the page only if both values are honest readings of one fit.
      *Done by WP-2044 before 1.10.0. The cause was not LAPACK but GSAS-II's step in
      the Sabine Laue factor at x = 1, which a forward-difference column straddled on
      one platform. E_L is now continuous and the page quotes CaF₂ 3.58 ± 3.53 wt %
      on both.*
- [x] Windows fast job's `timeout-minutes: 45`, before the next cut: `RELEASING.md`
      step 4 reads this job as a gate, and on 1.10.0's release commit it read
      cancelled after the suite had passed (44:29 against 24:23 two hours earlier).
      Rebudget it from the measured range so that it stays a runaway guard.
      `tests/CLAUDE.md` § Budgets in tests says a budget that is not several times
      the cost is a load sensor. *Done 2026-10-25: 120 min, from the last 30
      nightlies' job times (handover entry).*
- [x] The Le Bail NaN raise: reproduce `test_cell_runaway_safety.py::
      test_a_wrong_triclinic_le_bail_fit_raises_no_degenerate_cell_error` (red on
      `c9dde14`'s `full` job, read off the log). If it reproduces it is a raise in a
      shipped path, and it goes to a WP of its own rather than staying here.
      *Reproduced 2026-10-25 at four of six 1e-14 starts on an arm64 Mac; filed
      as [WP-2048](2048-a-non-finite-step-ends-a-stage-rather-than-the-fit.md).
      The row stays red on whichever platform rounds into it until 2048 lands.*
- [x] `moment` guide: make the page and the script's own asserts hold at both stopping
      points, or make the rounds land on one point. *No longer reproduces
      (2026-10-25): every assert held at ten 1e-14 starts on an arm64 Mac (round
      1's move 0.0859-0.0873 μB, scale shift 0.47 esd), the Linux fast legs pass
      it on #1161's CI, and Windows passed every test on `ac1ee1e`. Confirmed or
      reopened by the next green nightly.*
- [x] The four slow tests: re-run on Linux once task 1 lands. Mark the lab6 and cpd1a
      start rows that fail through WP-2012's degeneracies as strict xfails citing it.
      Resolve the cpd1a XPASS. Find whether the closing stage moved the 150 K null's Rwp
      ratio, and fix the fit or the bar on that evidence. *On an arm64 Mac all
      four now hold (2026-10-25, `deff4c301`, `[dev]`): the 150 K null and both
      axial-floor rows pass, and the three start rows that fail carry strict
      xfails citing WP-2002 or WP-2012 (lab6's intermediate-tolerance one since
      made not strict, below). What remains is the Linux reading.*
      *Linux, 2026-10-25 (run 40184228951, `deff4c301`): four rows red, each
      reproduced on the Mac by a 1e-14 start nudge (probes in
      `docs/wp/2049-batch/`, `docs/wp/2050-batch/`). (1) lab6's
      intermediate-tolerance row passed under a strict xfail. The two minima
      are an exact S/L ↔ H/L swap at equal Rwp, and of 49 nudged arm pairs 23
      crossed (8.82 esd) and 26 agreed (7.4e-6), so the mark is now not strict.
      (2) The 150 K null was fitted with a closing stage and compared with a
      reference fitted without one; the 1.2e-3 gap was the closing stage. Both
      are now fitted without one, 1.1e-5 at all 12 nudged starts. (3) The
      planted series' blank frame refines zero shift and U..Y against noise
      when its warm rung is accepted: filed as WP-2049. (4) Brucite's
      `HIGH_CORRELATION` count moves 35-42 by rounding, its partners being a
      flat triple: filed as WP-2050. The Le Bail row passed on Linux this time
      (WP-2048).*
- [x] The extra-peaks ordering (Context, "Since 2026-10-24"). *Ruled by the
      maintainer 2026-10-25: assert the inflated esd, not the ordering. The test
      now asserts the declared cell within 20 ppm of clean and the ignored arm's
      esd over 5× the clean one's (9.9× measured); the validation-matrix row says
      the esd reports the worse fit and measures no bias (McCusker 1999 §10,
      surveyed in `docs/practice.md`).*
- [x] Tests: each fix has a test that fails before it, and the 1e-14 nudge is the
      local check for every platform split. *Each change here is to a test, and
      each was checked at the nudged starts that failed it: the null at 12, the
      lab6 row at 49 pairs, `moment` at 10. The Windows limit has no test; its
      evidence is the job-time table in the handover entry.*
- [x] Skill: none expected, since these fix tests, CI and one esd. If the `qpa` esd
      changes, check `references/` for a quoted QPA esd. *None: no package
      behaviour changed here. WP-2049 and WP-2050 each carry their skill row.*
- [x] The `moment` guide's round-2 bar, red on CI's py3.14 shard 2 in 10 of 19 runs
      on main and branches after #1161 (found stewarding #1165). *The page and the
      script quote the loop's own rule, round 2 under its esd, in place of "under
      0.002 μB": that bar sat between two converged fits with no measured
      cross-platform spread (`tests/CLAUDE.md` § Budgets in tests). The crawl
      behind it went to WP-1334's Inherited.*

**Added 2026-11-02** (the ghostshift main-health runner), from the 2026-11-01
nightly (run 41305369905, `f4db7763`): 3 failed, 14 146 passed, in 1:35:05.

- [x] The Le Bail NaN raise, red again on 11-01. *Nothing to do: WP-2048's
      PR #1292 merged at 16:12 UTC, four hours after that nightly started.*
- [x] `test_the_axial_sizing_floor_does_not_change_the_answer[lab6]` at 8.820
      plain esd, red on five of the seven Linux nightlies that ran it since
      2026-10-24. *The two arms report one answer under swapped S/L and H/L
      labels, which the Finger-Cox-Jephcoat profile cannot tell apart, so the
      comparison now orders the pair first, as `test_seed_invariance._answer`
      already did. Same fix for the intermediate-tolerance row, whose
      non-strict xfail is removed. Both rows pass at all 49 nudged start
      pairs.*
- [ ] `test_magnetic_solve_acceptance.py::test_the_150k_pattern_has_nothing_to_solve`:
      class 3's trial stopped on `max_iter` on Linux after
      `SOLVE_MAX_CONTINUATIONS` (10) continuations.
- [ ] The two cancelled nights (10-30, 10-31): read the job-time table and
      decide the `full` job's `timeout-minutes`.

## Acceptance

One `nightly.yml` run on `main` with all six jobs `success`, and the full suite green on
an arm64 Mac.

```sh
gh run list --workflow nightly.yml --branch main --limit 1
.venv/bin/python -m pytest -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

## References

- Nightly runs 39940543791 (2026-10-23, `3e0dc6f7`) and 39765617812 (2026-10-22,
  `d01ae735`); the Windows job's red nights 2026-10-16 to 2026-10-23.
- PR #1085 (WP-2002, merged `425334ad`); WP-1994 (`closed_wp_writes.py`); WP-2012
  (the two degeneracies); WP-1930 (the 1e-14 nudge).

## Handover log

- **2026-10-25** — The Linux full suite finishes again: the first nightly after
  #1161 ran it in about two hours, and none of the hostile series' old hang is
  left in its slowest tests. It is still red on four slow rows, each a fit with
  two nearby stopping points that rounding picks between. Two of the four were
  the tests' own fault and are fixed here. The other two, and the Le Bail raise
  the WP was asked to reproduce, are defects in the package. Each is now its own
  WP, so this one closes only when those land and a nightly comes back green.
  The Windows job's limit was raising false alarms on slow runners and is raised.

  *Done.* Windows `timeout-minutes` 45 → 120. The extra-peaks test asserts the
  ignored arm's inflated esd instead of an ordering 0.3 ppm wide (the
  maintainer's ruling, after a survey of McCusker 1999 §10 and §12.6 and
  GSAS-II's background peaks, saved to `docs/practice.md`). The 150 K null is
  fitted with no closing stage, like its reference. lab6's
  intermediate-tolerance xfail is not strict. Filed: WP-2048 (a non-finite
  residual raises out of `fit`), WP-2049 (a frame with no seen phase refines
  the instrument's peak terms against noise), WP-2050 (`HIGH_CORRELATION`
  against a flat triple). `moment` no longer reproduces anywhere. Inherited
  folded into Context; forward references to WP-2045 and WP-2012.

  *Measured.*
  - Windows fast job, last 30 nightlies: 11-28 min through 2026-10-15, then
    17-45 min, with two runs on 2026-10-24 two hours apart at 24.9 and 45.1. The 2026-10-22 run was
    2.2× the 2026-10-21 one at every 5 % mark of its progress, so runner speed,
    not one test. 120 is 2.7× the slowest complete pass. On 2026-10-25 it took
    34.6 min.
  - Nightly run 40184228951 (`deff4c301`, Linux 3.13, `[dev,jax]`): five jobs
    green; `full` 4 failed / 12 157 passed / 218 skipped / 41 xfailed in
    2:05:47. On 2026-10-22: 11 443 / 140 / 3 in 1:36:13. The 30 minutes are
    spread across 830 more tests; the Le Bail fit (86 → 331 s) and two guide
    scripts moved most. `full`'s margin under its 150 min is 1.19×.
  - The four rows, reproduced on an arm64 Mac (`[dev]`) by 1e-14 nudges, numbers
    in the task notes and in WP-2049 and WP-2050. The null fix: 1.1e-5 relative
    at 12 nudged starts, against 1.2e-3 at some starts before.
  - Le Bail: 4 of 6 nudged starts raise (WP-2048); `moment` round 1 moves
    0.0859-0.0873 μB at 10 starts against its `< 0.10`.
  - Extra peaks, `deff4c301`: declare −0.131 ppm, ignore −0.422 ppm, exclude
    +0.329 ppm; esds 5.15 (clean), 5.05, 50.80, 4.88 ppm.
  - Fast selection on main `4cfd45984` merged (`[dev]`, macOS arm64):
    11 758 passed, 272 skipped, 28 xfailed in 6:58, nothing else running.
    This WP added no test, so the total is main's; main moved under the branch
    (#1006, #1073, #1111), so no delta against an earlier count is claimed. The
    full selection was not run: every change here is to a test, CI or a doc.
  - One lane (`linux-rows`, estimated 30 requests, ran 61): lane $3.51, saved
    $3.29 against keeping it, +10 % of the session. Session trial row:
    `| 2026-10-24 | de49de8e | 1 | 2 | 0K | 2 | 6K | 0.80 | 1 / 0 | +3.29 | +10% |`
    (the session started on 10-24 with WP-2045; its two kept items are that
    WP's). Selective policy over the replay: −23 %.

  *Review.* `/code-review high` found nine issues. Fixed: the extra-peaks
  module docstring still saying ignoring does not recover, a missing-esd guard,
  a probe's usage text, the null row's history sentence, a stale task note.
  Declined, each with its reason: the two unmarked lab6 siblings (not
  re-measured; to WP-2012's Inherited); the 4 K moment comparison's protocol
  mismatch (bar 35 %, a mismatch of 0.1 %); the `full` limit at 1.19× (the
  WP's non-goal: no raise without a durations table that says why, and this
  one does not); the trial row's date (the tool's, the session's start).

  *Generality.* Not dispatched: `_audit.py` untouched, and the only new numbers
  are test bars and a CI limit, none a package heuristic.

  *Gotchas.* A strict xfail on a row that rounding decides fails on the
  platform that rounds the other way, so it must be not strict. The alarm pin
  cannot hold on both platforms until WP-2050 lands; do not re-pin it from
  either.

  Next: WP-2049 first, since a blank frame's zero shift reported at 4.8σ is a
  wrong number a user can quote; then WP-2050, after which the alarm pin is
  re-written once; then WP-2048. After all three, the next green nightly
  closes this WP. If `full` times out first, read its durations table before
  touching the limit.

  *CI on #1165 (same day).* `tests/test_examples.py::…[moment]` failed on the
  py3.14 shard 2, and on main at `4cfd45984` and seven branches, 10 of 19 runs
  since #1161 merged, 0 of 8 before, on numpy 2.5.4 / scipy 1.18.1 throughout.
  The guide's round 1 now starts with m_y = −1.0191e-6 μB (−0.074 before), and
  from that exact start its one stage crawls 800 evaluations to `STAGE_MAX_ITER`
  at cost 1990.3. From −1.0e-6, 0, ±1e-6, −1e-4 or −1e-3 it converges in 21-45
  to 1983.6 (arm64 Mac, `[dev]`). Every route ends at Rwp 0.104747 and |m|
  2.12546 μB after the closing stage, so round 2's step is where round 1
  stopped: under 1e-5 μB here at 28 nudged starts, under Accelerate and
  OpenBLAS SciPy alike, and 0.002 or more on some Linux runners. The page now
  says round 2 moves less than its esd. Main merged in, `process.md` and
  `practice.md` kept from both sides.

- **2026-10-24** — re-rated P1 → P2 by the maintainer's session after the 1.10.0 cut,
  with no code changed. The P1 reason was the `qpa` esd split, and WP-2044 fixed it
  before the tag. #1146 fixed the two Windows failures, so three tasks are ticked with
  pointers. WP-2045 is now a hard dependency, because the `full` job cannot finish
  until it lands. The same session later ruled 2045's design: the stage before the
  closing stage converges at the solver's tolerance. Two tasks were added from the
  Inherited entries: the Windows job's 45-minute limit, which threatens the next
  release gate, and the Le Bail NaN raise. Next: the Windows limit before the next
  cut. The `full` leg re-run waits on 2045.
- **2026-10-23** — created by the maintainer's `/pr-review` session, which found these
  failures while gating #1122. No open WP owns them as a set. WP-2002 is in flight and
  caused items 1, 3 and 4, but its file is waiting on rulings, and item 2 comes from
  WP-1994, which is closed. WP-2012 owns two of the degeneracies and none of the
  failing rows. Next: task 1, since items 3 and 4 cannot be read on Linux until the full
  job finishes.
