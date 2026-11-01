# WP-1547 — the fast tier's tail is cut back, and its report reads CI's seconds

Milestone: unscheduled · Status: ✅ 2026-10-23 — the tail cut and two shards a leg brought a run's slowest fast job to a 14.75-min median over ten main runs
Track: The repo's own process
Depends on: —

## Goal

A readied code PR's fast legs finish in about 20 minutes again, with no
assertion lost: a test leaving the fast tier runs in the nightly. The handover
report on added tests shows what they cost on CI, so the next 5-minute file is
seen before it merges.

## Context

**The symptom.** Weekly median wall clock of main's successful CI runs
(`gh run list --workflow ci.yml --branch main --event push --status success`):

| ISO week | 38 | 39 | 40 | 41 |
|---|---|---|---|---|
| Median min | 16.3 | 20.6 | 24.1 | 35.7 |

A run waits for the slowest of five legs (py3.11-3.14 and jax). Legs of one
run differ by up to 1.6× on the same tree (run 37966391017: py3.13 19.4 min,
py3.12 30.6, jax 36.0), so the run usually draws a slow runner.

**The suite is a normal size.** Counted 2026-10-09 with one script over each
project's HEAD tarball, lines of code excluding blanks, comments and
docstrings:

| Project | Source kLOC | Test kLOC | Test/source | Test functions per source kLOC |
|---|---|---|---|---|
| rietx | 72.5 | 96.7 | 1.33 | 81 |
| astropy | 104.7 | 134.6 | 1.29 | 83 |
| scikit-learn | 82.8 | 121.7 | 1.47 | 66 |
| scipy | 120.7 | 176.4 | 1.46 | 99 |
| lmfit | 4.5 | 6.1 | 1.34 | 85 |

Test code has tracked source at about 1.1× (raw lines) since August. The
codebase grew from 38k raw source lines on 2026-08-01 to 150k on main
1007c9bf, so the count grew with it. The time grew faster than the count.

**Where the time went.** Three main runs whose junit artifacts survive:
36362163974 (2026-09-28), 37100295315 (10-03), 37978210348 (10-09). Each
file's time is divided by its leg's parallelism (test-time over the pytest
step's wall), which cancels the worker change below. Medians of the four
Python legs:

| Snapshot | Tests | Leg wall (min) | Tests over 10 s (wall-min) |
|---|---|---|---|
| 09-28 | 6800 | 20.1 | 12.7 |
| 10-03 | 8219 | 21.7 | 11.9 |
| 10-09 | 9116 | 31.1 | 17.9 |

From 10-03 to 10-09, new files added 7.1 wall-min a leg and existing files
2.0. Three files are 8.1 of the 9.4:

- `test_lebail_alternation.py` (WP-1323, merged 10-02): +5.0. Twelve tests,
  each fitting the 11-BM LaB6 + cBN pattern over 5.1-50° from scratch. Only
  the pattern is a module fixture. Two pairs repeat a fit exactly:
  `_refinement(1.0)` at `_plan(3)` in the history-less marking test and the
  cap-recording test, and `_refinement(1.003)` at `_plan(4)` with telemetry
  in the run-directory test and the pass-ending test.
- `test_magnetic_isotropy.py`: +1.8. It moved −0.7 the week before, so part
  of this is runner noise. Why `isotropy.analyse` is slow is WP-1418's.
- `test_tutorials.py` (WP-1545): +1.3. It executes 23 notebook cases on every
  leg.

The tail's named members from WP-1506 still stand: the 230-group and
every-setting sweeps (`test_the_sweep_over_the_230_settings_at_gamma`, three
230-group tests in `test_magnetic_irreps.py`,
`test_symmetry_orbits.py::test_the_invariant_holds_across_every_setting_gemmi_knows`).
A sample of them could stay fast with the whole sweep nightly. Choose the
sample by trap, never at random: 79 of gemmi's 564 settings were once served
wrong under a correct count (root CLAUDE.md, cell ties). A break in an
unsampled setting would then show the next morning, and the WP states that
trade.

**The report went quiet by a factor of 3-4.** tests/CLAUDE.md § Budgets in
tests makes the fast tier's guard a report (`tests/added_test_times.py`), read
at handover. It fired for the Le Bail tests. WP-1323's handover quoted
18.4-30.7 s for its four slowest, from a local run on a 10-core Mac, and kept
them fast as the only real-pattern cover of the loop. On 2026-10-09's CI legs
the same file's four slowest took 56-131 s each. The report also judges each
test alone, so twelve 1-2 minute tests were never seen as one 5-minute file.
The report stays a report: a failing per-test ceiling would be the timer the
budgets section forbids.

**Two physical cores, so the worker count is not a lever.** GitHub's 4-vCPU
Linux runner has 2 physical cores. `pytest -n auto` counts physical cores
whenever `psutil` imports (xdist's `pytest_xdist_auto_num_workers`), and
`psutil` entered `[dev]` through ipykernel when PR #810 (WP-1544's `notebooks`
extra) merged on 2026-10-07. Test-time over wall fell from 3.84-3.88 to
1.95-1.96 on every leg. Leg wall clock did not move: 29/33/25/29 min on
565e8f1d, the run before, and 28/28/20/32 on 57aa2c1f, the merge. Four
hyperthreaded workers had each run at about half speed. So `-n logical` is
not a fix. One side effect matters here: per-test seconds in junit halved on
10-07, so compare junit across that date only after the division above.

**The re-measure after #857 (2026-10-10).** "Fast suite" step minutes on
main's six successful push runs since #857 merged:

| Run | Merge | py3.11 | py3.12 | py3.13 | py3.14 | jax | Python median |
|---|---|---|---|---|---|---|---|
| 38036573431 | #861 | 28.5 | 26.2 | 16.0 | 15.9 | 30.4 | 21.1 |
| 38038633449 | #860 | 28.4 | 16.6 | 24.1 | 19.9 | 31.2 | 22.0 |
| 38043823874 | #858 | 26.8 | 27.9 | 20.3 | 16.7 | 23.8 | 23.5 |
| 38072781107 | #862 | 27.8 | 26.0 | 15.5 | 25.9 | 23.6 | 25.9 |
| 38079936613 | #863 | 18.4 | 17.5 | 24.3 | 23.8 | 20.1 | 21.1 |
| 38088718957 | #864 | 28.5 | 26.2 | 21.9 | 25.9 | 20.6 | 26.1 |

The four runs before #857 had Python medians of 23.8-31.1. The cut took about
7 minutes off, and every run is still over 20. The median of the six medians
is 22.8. A run waits for its slowest leg, which took 24.3-31.2 min. Leg times
are bimodal by runner. In the junit of the last three runs, a Python leg's
summed test time was 1814-2147 s on three legs and 2798-3352 s on eight, with
one at 2579. With five legs, most runs draw at least one slow runner. py3.11
was the slowest Python leg in 9 of the 12 runs with all four. It alone
resolves numpy 2.4.6 and scipy 1.17.1, since numpy 2.5 dropped 3.11. But it
took 18.4 min in 38079936613, so most of its gap is runner draws.
Sharding halves every leg. Trimming the matrix alone would not help, because
py3.11 and jax stay and set the wall. #857's py3.11 failure was the #243
fixture (fixed by #859), and #859's red was spglib 2.8 (fixed by #861). No
other run went red.

**Sharding constraints (from WP-1506).** Sharding must keep each
`xdist_group` whole. GitHub Free allows 20 concurrent jobs, so five legs
times N shards meets the limit when two PRs are readied together. Sharding
probably comes with a smaller PR matrix (oldest and newest Python per PR, the
middle two nightly). Larger runners need a paid organization plan (1506's
"Considered and not taken").

**For scale.** SciPy's fast Linux jobs take 3-14 min including a C build, and
several run `--timeout=60` per test (`.github/workflows/linux.yml`,
2026-10-09). That is a runaway cap at 60 s, which this repo would read as a
load sensor. The comparison shows the size of their tail, and it is not a
mechanism to copy.

**This is WP-1506's task 7.** 1506's last open item was "from two weeks of
junit timings, choose the next cut". The timings it waited for are the three
snapshots above, and its candidates are the sweeps, sharding and a smaller PR
matrix, all carried here.

**If the nightly is reshaped, take the probe line with it** (WP-1519's note,
carried from 1506 at its close). Each nightly "Record the environment" step
(`full`, `windows`, `macos`) pastes the same line printing
`row_local_product` and `stacked_pinv_exact`. Those two indexing probes pick
an exact slower path on a platform whose BLAS or LAPACK fails them. The
nightly runs at `-q` without `-rs`, so these lines are the only record of
which path each OS took. A third probe or a rename needs three identical
edits, and a missed one drops that platform's answer silently. A YAML anchor
or one script every leg calls would fix it. It is low stakes, and in scope
only if the last task moves Python versions into the nightly.

**After this WP (from WP-2019, 2026-10-21).** The tier grew again after these
tasks: the guide scripts (WP-1986), the automatic profile interval (WP-2002)
and 64 files the shard record lacked. Main run 39589774138 (3437d52) had a
slowest job of 19.6 min, at this WP's bar. [2019](2019-each-fast-leg-runs-what-only-it-can-see.md)
owns the next cut. Its #1095 (merged 2026-10-21) reshaped the per-push matrix:
jax is one unsharded job of the cases that reach jax, and the documentation
runs on the newest leg alone under `RIETX_DOCS`, which replaced this WP's
`RIETX_TUTORIALS`.

## Non-goals

- Why `isotropy.analyse` is slow: WP-1418.
- The nightly's length.
- The docs-only skip and `ci-ok`: WP-1506, live since 2026-09-27.
- The worker count. Measured above, it buys nothing on this runner.

## Tasks

- [x] `test_lebail_alternation.py`: share the two repeated fits through
      module fixtures, and measure whether a narrower 2θ window keeps the
      three shapes the module docstring names (pass 2 worse at exact cells,
      convergence at +0.3 %, no settling at +2 %). Every quoted Rwp is the
      hand loop's at 5.1-50°, so a narrower window re-measures each one. A
      test that still costs over about 30 s on CI says in its docstring why
      it is fast, or moves to `slow`.
- [x] The sweeps: a trap-chosen sample in the fast tier, the whole sweep
      marked `slow`. The commit names the sample and the trap each member
      covers.
- [x] `test_tutorials.py`: run it on one Python leg, or nightly. The
      decision states what a notebook could break on one Python version and
      not another.
- [x] `tests/added_test_times.py`: add a per-file total for the added tests,
      and let `/wp-handover` read the PR's CI `junit-py3.13` artifact when
      one exists, falling back to the local file. tests/CLAUDE.md § Budgets
      in tests gains one clause: local seconds understate CI by 3-4×.
- [x] Re-measure main runs after the above. If the median Python leg is
      still over about 20 min, shard by recorded junit time with groups kept
      whole, and trim the PR matrix to the oldest and newest Python, with
      the middle two in the nightly. (Six runs, not ten: every one was over.)
- [x] Shard each fast leg in two by recorded junit time, every `xdist_group`
      and every file whole (`tests/shards.py`, `tests/shard_times.json`).
- [x] `ci.yml` runs py3.11, py3.14 and jax, two shards each. py3.12 runs in
      the nightly, where `full` already covers 3.13. The nightly's three
      copies of the environment line become one module every leg calls.
- [x] `added_test_times.py` reads a directory of shard files, and
      `/wp-handover` step 7 downloads both py3.14 shards.
- [x] `ci.yml`'s header: one line saying `-n auto` is 2 workers on this
      runner, and that `-n logical` was measured to buy nothing (this WP).
- [x] Skill: none. This changes how the repo is tested, not how rietx is
      driven.
- [x] The nightly runs the fast suite on 3.12 and on 3.13 (`middle`), and
      RELEASING step 4 gates on those two and Windows. `full` is read at a
      cut and does not gate (the maintainer's decision, 2026-10-11).

## Acceptance

- Over ten consecutive successful main runs after the shards land, the
  median run's slowest fast job is 20 min or under. A job is timed from its
  start to its end, setup included, since each shard pays its own. (Amended
  2026-10-10: the bar was the median of four Python legs' "Fast suite" step,
  which no longer exists once a leg is two jobs. A run waits for its slowest
  job, so that is what the bar now reads.)
- Every test that left the fast tier passes once in the nightly's `full` job.
- Each leg's passed+skipped, summed over its two shards, equals the
  unsharded fast count at the same commit. The fast count moves by exactly
  the tests added minus those marked `slow`, quoted with venv and platform.

```sh
gh run list --workflow ci.yml --branch main --event push --status success --limit 10 --json databaseId
gh run view <id> --json jobs   # each "fast …" job's startedAt to completedAt; take the largest
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow" --shard 1/2   # and 2/2
```

## References

- pytest-xdist 3.8, `xdist/plugin.py` `pytest_xdist_auto_num_workers`
  (physical cores when `psutil` imports; `-n logical` for logical).
- SciPy `.github/workflows/linux.yml` (fast jobs, `--timeout=60`).
- Runs 36362163974, 37100295315, 37966391017, 37978210348; PR #810.

## Handover log

### 2026-10-23 — closed: a run's slowest fast job takes about 15 minutes

When this WP opened, a code PR waited 32-37 minutes for CI. After the tail cut
and the split of each leg into two shards, the first ten successful main runs
waited a median 14.75 minutes for their slowest fast job, under the 20-minute
bar. The maintainer decided on 2026-10-23 that the WP closes, which discharges
the wait on the maintainer. The tier has grown since, and the next cut is WP-2019's.

Read from GitHub's REST API (ci.yml, main, push; each job `started_at` to
`completed_at`). #869 merged 2026-10-11T07:16:44Z. The next 24 completed runs,
to 10-12 08:41, were 10 successes and 14 cancelled by a newer push. None failed.

- Item 1 met. Slowest fast job per run, min: 38120969515 14.97,
  38124338257 14.97, 38126808708 14.93, 38149031888 18.45, 38151965750 18.47,
  38177046032 14.57, 38181705837 13.83, 38184006682 14.30, 38219845308 13.62,
  38225077694 12.82. Median 14.75. A jax shard was slowest in 7 runs. All ten
  had one shape, three legs of two shards, nine days before #1095.
- Item 2 met by 38048650490 (10-11 entry), and again by the first nightly
  after the merge, 38136632756 on 12db370b: `full` green, both `middle` jobs too.
- Item 3 met by the 10-11 entry: run 38094285221's shard sums are the base
  legs plus the 27 added, and the local count was 9219 (`[dev]`, macOS arm64).
- Inherited: the grown-tier note is now in Context, its next cut already
  WP-2019's. The two-shapes note is discharged: the window ends before #1095.
- For WP-2019: the five latest main runs (10-22, 10-23) had slowest jobs of
  17.5-22.2 min, three over 20; py3.14's shards took 9.1 and 21.7 min on
  39937040834.

*Next.* Nothing owed here. The shard record refresh and the next cut are WP-2019's.

### 2026-10-11 (2nd session) — the release gate reads 3.12 and 3.13 on their own, and the trim stays

PR #869 merged, and the maintainer took both of its open decisions. The trim
stays: in eight weeks of the four-Python matrix, a middle version failed alone
eight times, and none of the five that reached a test was a language break.
The release gate changed shape. Step 4 had asked for the nightly's `full` job
green, but `full` is red about half the time for reasons that have nothing to
do with the Python version. So the nightly now runs the fast suite on 3.12 and
on 3.13 as jobs of their own, and those two with Windows are the gate.

Done:

- `nightly.yml`: `py312` becomes `middle`, a matrix over 3.12 and 3.13 named
  `fast suite (Linux, Python …)`. Its header says why `full` is not the gate.
- `docs/RELEASING.md` step 4 names the three gating jobs and says `full` is
  read and does not gate. `release.yml`, `ci.yml` and `tests/CLAUDE.md` § CI
  say the same.

Measured (GitHub's API, 2026-10-11):

- Nightly, the 60 runs from 2026-08-22 to 2026-10-10. `full` was red on 27,
  in three stretches, each one test failing on every night:
  `test_acceptance_lab6_cbn` (correlation diagnostic) 08-27 to 09-10,
  `test_acceptance_indexing` (brucite's rank) 09-22 to 09-26, and
  `test_pair_diagnostic_class` on 10-07 and 10-10. Windows was red on 20,
  all Windows-specific (`test_eval_skill`, `test_docs_consistency`'s
  gitignored-link row, `test_runs`, `test_skill_cli`). v1.2.0 and v1.3.0
  shipped inside the first `full` stretch. The other five releases from
  v1.1.0 to v1.7.0 each followed a nightly with every job green.
- Per push, every failed `ci.yml` run from 2026-08-16 to the merge: 84. The
  red fast legs were all four in 35, 3.11 alone in 18, another job in 13,
  and 3.12 or 3.13 without 3.11 or 3.14 in 8. Of those 8, five were tests
  pinned to a float's last digits or one solver path (`test_history`,
  `test_fitreport_layers`, `test_background_peaks`, `test_sequential`,
  `test_cell_runaway_safety`), all on PR branches, each fixed by changing the
  test. Two logs hold no pytest summary. One was `srm660c_lab.py` exiting 1
  on main (run 32567276564), cause not read. Seven of the eight fell between
  08-21 and 08-26.

Gotchas:

- The Windows job runs Python 3.13 as well, so a 3.13 break can show there
  first.
- On a log holding escape codes, `gh api .../jobs/<id>/logs` prints nothing
  and exits 1 unless given `--allow-escape-sequences`.

Next:

1. Check that both `middle` jobs go green on their first nightly. If one
   fails where `full` passed, read its environment step first: each leg now
   prints its numpy and scipy versions.
2. The ten-run read and the record refresh stay as the entry below says.

### 2026-10-11 — each fast leg runs as two shards; the ten-run acceptance waits for the merge

The tail cut in #857 took about seven minutes off a fast leg. Every main run
since still waited 24-31 minutes for its slowest leg. So each leg now runs as
two jobs, and each job takes about half the suite. Files and shared-fixture
groups stay whole, packed by the seconds CI recorded. The per-push matrix
is now the oldest and newest Python plus jax, six jobs a run. Python 3.12
moved to the nightly, where 3.13 already ran in the full suite. A break on a
middle Python alone now shows the next morning. Whether a run now finishes
in 20 minutes is known only after ten main runs on the merged tree.

**Done** (PR #869, branch `wp1547-ten-run-remeasure`):

- The re-measure, in Context: six successful main runs since #857 had Python
  medians of 21.1-26.1 min. The WP asked for ten. All six were over the bar,
  so the rule fired on six.
- `--shard K/N` (`tests/shards.py`, the hook in `tests/conftest.py`). It packs
  units longest first onto the least-loaded shard. A unit is a set of files
  joined by shared `xdist_group` names. The weights are
  `tests/shard_times.json`, taken from main run 38088718957 on 61422693. That
  is the first run after the kernel wheel replaced numba (#864, WP-1940's
  first half). The record has a numpy and a jax profile, because
  `test_cross_backend.py` costs 391 s on the jax leg and 16 s elsewhere.
  `tests/test_shards.py` holds 26 cases. A lane built this.
- A module skipped at import is reported by shard 1 alone (886f5c93). Such
  a module has no item for the split to place. On CI's first sharded run
  every shard counted its skip, and py3.14's two shards summed to 9223 cases
  against the base's 9192 plus 23 added. The eight extra were jax, torch and
  six browser files.
- `ci.yml`: py3.11, py3.14 and jax, two shards each. The artifacts are
  `junit-py3.14-1` and so on.
- `nightly.yml`: a `py312` fast job. `tests/record_environment.py` replaces
  the three pasted copies of the probe line (WP-1519's note, in scope once a
  Python version moved to the nightly). The per-push legs call it too.
- `added_test_times.py` reads a directory. `/wp-handover` step 7 downloads
  `junit-py3.14-*` and passes the directory.
- `docs/RELEASING.md`: step 3 named six required checks, stale since
  WP-1506. Step 4 now also asks for the nightly's `py312` and `full` jobs to
  be green on the release commit. That is a new release bar and needs the
  maintainer's yes.
- Acceptance is amended to read each run's slowest fast job, timed with its
  setup. The old bar read a step that no longer exists.
- Acceptance item 2 is met. Nightly 38048650490 ran on 32a2b473, after #857.
  It ended 1 failed, 9349 passed, 131 skipped, and the failure is unrelated.
  spgrep is in `[dev]`, so no skip path reaches the seven `all-*` cases or
  the wide Le Bail test.
- `/code-review high --fix` made six fixes, committed together as 0230bbd7.
  `tests.shards` refuses a leg missing a shard. The `ci.yml` include comment
  now covers retiring 3.14. `release.yml` and `DESIGN.md` no longer claim
  3.12 and 3.13 per push. The conftest hook got a corrected comment and one
  loop. Declined: weighting the tutorials by the one leg that runs them
  (about a minute on one py3.14 shard), a guard against mixing legs in the
  directory `added_test_times` reads, and the median of two legs being their
  mean.
- Inherited pruned: the #243 note is consumed. Its fix merged as #859, and
  the re-measure counts its red run.
- Forward reference: WP-1930. The nightly after its #849 is red on its
  two-site test.

**Measured:**

- Fast on the final tree, `[dev]`, macOS arm64, Python 3.12, no other
  pytest running: 9041 passed, 177 skipped, 1 xfailed, so 9219 in all. The
  base is 9192 cases in CI's py3.12 and py3.14 junit at 33fe516e (run
  38091884560). The 27 added cases are 26 in `test_shards.py` and 1 in
  `test_added_test_times.py`. Wall 4:36.
- First sharded CI run, 38093251416 on 953c3639, dispatched on the branch.
  One run, so a direction only. Job walls, setup included: py3.11 13.3 and
  15.0 min, py3.14 10.7 and 11.1, jax 15.1 and 16.7. The slowest job was
  16.7 min. Test seconds per shard: py3.11 1497 and 1698, py3.14 1159 and
  1258, jax 1717 and 1924. Shard 2 is the heavier by 8-13 % on every leg.
- Second sharded run, 38094285221 on 886f5c93, with the skip-report fix.
  Each leg's cases summed over its two shards: py3.11 9219, py3.14 9219,
  jax 9231. The base's own legs had 9192, 9192 and 9204, so each moved by
  exactly the 27 added. Job walls: py3.11 11.6 and 11.9 min, py3.14 13.4 and
  13.9, jax 9.7 and 10.6. The slowest job was 13.9 min.
- The end-to-end row cost 4.8 s on CI's py3.14, well short of the tail.
- Collection, same venv, before the last four added cases: 9207 unsharded, 4377 at `1/2` and 4830 at `2/2`. The shards are disjoint and
  their union is the unsharded list. Estimated shard seconds are 1492 and
  1492 under numpy, 1186 and 1186 under jax. The fast tier's one multi-file
  unit is `test_help.py`, `test_landing.py` and `test_manual.py`
  (`manual-build`).
- Added tests, local junit: `test_shards.py` 9.94 s, of which 9.88 s is the
  end-to-end row. It starts pytest three times. The machine was loaded.
- Lane, `session_usage.py lanes`: shard-mechanism, estimate 25, actual 24
  requests, dispatched at 186K. Its re-read was 5K of 9K. Main made 22
  requests while it ran. Lane $1.24, saved −$1.12 (−17 % of the session).
  The selective policy's replay row: −1 % at u = 5K.

**Gotchas:**

- The tutorials weigh about 0 s in the numpy profile, because three of four
  legs skipped them. On py3.14 the shard that draws `test_tutorials.py`
  carries about 119 s more than its estimate.
- A stale record costs balance and never a test. Refresh it with
  `gh run download <main run> -p 'junit-*' -D DIR`, then
  `python -m tests.shards DIR "main run N (sha)"`.
- WP-1940's #867 and #868 move the figure tests onto Rust kernels after this
  record was taken. Balance drifts a little when they land.
- Under xdist the summary line carries no deselected count. Read a shard's
  size from its passed+skipped.
- Only one `lanes:` line was written. The kept items had none, so the trial
  row reads kept 0.

Next:

1. The maintainer decides on RELEASING step 4's new bar.
2. After the merge, read ten consecutive successful main runs: each run's
   slowest fast job, start to end. A median of 20 min or under closes the
   WP. Over it, choose between three shards (nine jobs a run, two runs at
   once) and the tail (`test_magnetic_isotropy`, WP-1418).
3. Check that the nightly's `py312` job runs green once.
4. Refresh the record from a sharded main run if one leg's two shards
   differ by more than a few minutes. The first run had them 0.4-1.7 min apart.

### 2026-10-10 — a fix from WP-1936's session (reconstructed post hoc)

WP-1936's session landed `c46a6679` under this WP's prefix (PR #859, merged
as `ead856cb`). #857's merge had turned main's py3.11 leg red. The commit makes
`test_fit_usable.py`'s #243 reproduction run the first three stages of the
unseeded NAC Le Bail plan, which reach one answer at every nudge. That session
recorded why under `### Inherited` (2026-10-10). No task is ticked. *Next:*
the ten-run re-measure, which #857's merge has unblocked.

### 2026-10-09 (2nd session) — the tail cut lands; the ten-run re-measure waits for the merge

The fast tier's three named costs are cut, and no assertion was lost. The
Le Bail tests now fit under half the angular range and share their fits. All
three behaviours they pin still appear there, at the same starting cells. The
space-group sweeps run a 23-group sample, chosen by trap, on every push. The
whole sweeps run nightly. The tutorials execute on one Python leg instead of
five. Whether this brings a leg back to about 20 minutes is not yet known.
Ten main runs after the merge decide it, and they decide whether sharding is
needed.

**Done** (PR #857, branch `wp1547-fast-tier-cut`, cut fresh from main because
the filing PR #856 had merged):

- Le Bail: `LIMITS` is 5.1-25°. +0.3 % keeps pass 1 (13.845, then 13.865),
  +0.4 % converges over five passes, and +2 % never settles. The slow test
  keeps 5.1-50° (`WIDE_LIMITS`), since its pins were checked on Linux in
  #849. Three module fixtures (`exact`, `worse`, `converging`) share fits,
  each in its own `xdist_group`. History, a run directory and an event
  callback each left the fit bit-identical (Rwp and every parameter, at
  +0.3 % and +0.4 %), so sharing is honest. The converging test accepts pass
  4 or 5 as kept, because at 25° the two are level within
  `LEBAIL_CONVERGED_REL`.
- Sweeps: `tests/space_group_sample.py` holds 23 groups, each named with its
  trap. Six sweeps take `[sample]` fast and `[all-230]`/`[all-564]` slow.
  The real-amplitude count joined the five the WP named: same shape, 41.7 s
  on CI. A new test asserts that the sample covers all 16 (system, centring)
  pairs.
- Tutorials: the py3.14 leg executes them, through a matrix `include`. The
  other legs skip through `RIETX_TUTORIALS=skip`. The trade is stated in
  `test_tutorials.py`'s docstring.
- `added_test_times.py` prints per-file totals and leaves skipped cases out.
  `/wp-handover` step 7 reads CI's `junit-py3.14` when the branch has one.
  `tests/CLAUDE.md` gained the 3-4× clause and stays at its 302-line cap.
- `ci.yml`'s header records that `-n auto` means 2 workers here.
- `/code-review high --fix` made six fixes, committed as one, listed in its
  commit. Declined: renaming the sweep tests. Their ids say which case ran,
  and a rename would move every id this WP quotes.
- Forward references: WP-1418 (sampled magnetic sweeps), WP-1545 (tutorials
  on one leg).

**Measured:**

- Probe fits at the old and new window, run beside each other on a loaded
  machine: +0.3 % took 10.6 s at 50° and 2.7 s at 25°; +0.4 % took 23.1 s
  and 4.4 s. Starts of +0.6 % and above diverge at 25°. A worse-pass start
  holds from +0.30 % to +0.52 %.
- Base run 37988294011 (deed30b5, py3.12 leg): the Le Bail file cost 1076 s
  of test time, not the 590 s of run 37978210348. #849 sits between them.
  The six sweeps cost 156 s and the tutorials 119 s.
- This branch's fast run, `[dev]`, macOS arm64, Python 3.12, load average
  33-47: Le Bail about 31 s of test time; the samples 2-16 s each.
  The two added tests read 0.00 s each, per file too.
- Count: fast passed+skipped 9148 (8975 passed, 172 skipped, 1 xfailed)
  against 9146 at the base (CI py3.12 junit). That is exactly the two added
  tests. The seven `all-*` cases are `slow`, so the full selection moves by
  +9. The full suite was not run: the change is test-only. Every slow case
  it added or touched passed locally: the seven sweeps and the Le Bail wander.

**Gotchas:**

- The worse-pass margin at 25° is 0.020 points of Rwp. Linux and macOS
  disagreed by 0.015 on the discarded pass at 50°. It held on all five legs
  of run 37992022325, the first Linux reading at 25°.
- `tests/CLAUDE.md` sits at its cap; a clause added there pays with a cut.
- **+0.4 % sits on an edge at 25°.** Under PR #855's step for `u` and `v`
  (WP-1936) it comes back worse on pass 2 instead of converging. So the
  converging fixture and the cap test start at −0.15 %, which converges on
  macOS with and without #855. All 13 Le Bail tests pass there on both trees.
  #855 still conflicts in this file as text. Whichever merges second takes
  this branch's version of it.
- **A converging run's pass count is a platform reading.** At −0.15 % on
  main, macOS took five passes to 13.932 and Linux six to 13.905 (run
  37996829339): the paths split at pass 3. #855's own pin at 50° failed on
  its Linux legs the same way, pass 5 against its macOS pass 6. So the
  converging test asserts the shape: at least four passes, each lower than
  the last until a level one, the kept pass last or second-last. Its Rwp
  bar is 1e-3, for a measured spread of 2.7e-4. A test that pins which pass
  a converging alternation stops on senses the platform.
- PR #853 (WP-1418, `isotropy.py`) merges cleanly. The isotropy sweeps, sample
  and full, passed on the merge, so the 140-candidate pin holds.

**CI, run 37992022325** (f16953c7, one run each, so a direction rather
than a measurement; legs on one tree differ by up to 1.6×):

- "Fast suite" step, py3.11/3.12/3.13/3.14 and jax: 30.7, 26.4, 25.0,
  26.1 and 18.9 min. Base run 37988294011: 39.8 (cancelled), 30.8, 35.1,
  28.2 and 35.5. The median Python leg fell from about 33 min to about 26.
- py3.13 test time: 2943 s, with the Le Bail file at 217 s. The base's
  py3.12 total was 3635 s, with the Le Bail file at 1076 s.
  `test_magnetic_isotropy` is now the largest file, at 453 s, from tests
  outside the sweeps (WP-1418's question).
- py3.11 failed one test this branch does not touch:
  `test_fit_usable.py::test_issue_243_reproduction_reads_unusable_while_converged`
  returned `max_iter`, not `converged`. It passed on #849's last py3.11 run
  with the same source and identical package versions. Locally it passes
  with the compiled tier on and off, and its dearest stage used 112 of 400
  evaluations. The fit ends at Rwp 155 %, the #243 shape, so its solver
  path is erratic. The test declares no compiled path, and its owner
  WP-1336 is closed. Not filed yet: the maintainer's call.

Next:

1. Read the new run's py3.11 leg. A pass there supports the flaky reading of
   the `test_fit_usable` failure.
2. After the merge, re-measure ten main runs (the open task). Shard and trim
   the PR matrix only if the median Python leg is still over about 20 min.
3. Then check that each `slow` case added here passed once in the nightly
   `full` job, which acceptance requires.

- **2026-10-09** — Filed. The suite is a normal size for its code, and CI
  slowed because about 60 slow tests grew faster than the rest. The worker
  count is ruled out: halving it changed nothing. The maintainer asked why
  CI takes so long and whether the suite is a normal size. Open WP-1506 owned
  the cut as its task 7, but its scope is the docs-only skip. So the cut moved
  here, and the maintainer had 1506 closed on the same PR (#856). Its open
  WP-1519 note about the nightly probe line now sits in this Context. No forward reference went to 1545: its PR #812 is open, and
  where the tutorials run is this WP's decision. The measurements come from
  `gh run list`, job logs, junit artifacts and peer tarballs, all counted with
  one tokenize-based script. The scripts were scratch and not kept. Docs only:
  no review pass, no suite run beyond the docs job's four files (124 passed,
  macOS arm64, `[dev]`). Next: the Le Bail file, the largest single item at
  5 wall-min a leg. Its re-measured CI leg decides whether the sweeps and
  tutorials are enough or sharding is needed.
