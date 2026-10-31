# WP-2019 — each fast leg runs what only it can see, and the tail is cut again

Milestone: unscheduled · Status: 🔄 2026-10-21 — six of seven tasks landed (PR #1095, the shard record after it); the ten-run acceptance reads main after the record merges
Track: The repo's own process
Depends on: —
Priority: P2 2026-10-23 — was P3: three of the five latest main runs have a slowest fast job over 20 min on the refreshed shard record; the wait 1547 was P2 for is back

## Goal

A per-push run waits about 15 minutes for its slowest fast job, with every
fast case still run per push on at least one leg. A case that leaves the fast
tier runs in the nightly instead. The jax leg runs the cases jax changes, the
documentation runs once, and no test pays for a computation it never reads.

## Context

**The trend.** These are job walls, setup included. WP-1547's first sharded
run was 38093251416 (2026-10-11, 9219 cases):

| Leg | 10-11 (min) | 10-21 (min) |
|---|---|---|
| py3.11 | 13.3 / 15.0 | 13.7 / 14.7 |
| py3.14 | 10.7 / 11.1 | 13.9 / 14.6 |
| jax | 15.1 / 16.7 | 19.6 / 16.9 |

The 10-21 column is main run 39589774138 at 3437d52, 11 100 cases. A run waits
for its slowest job, which is now the jax leg.

**Where the seconds are.** Measured 2026-10-21 on main 3437d52 under these
conditions:

- Linux x86-64, Python 3.12, `[dev]`, rietx-kernels 1.3.0 loaded;
- 4 cores, with no other pytest running;
- `-m "not slow" --durations=0` with a junit file.

Result: 10 895 passed, 203 skipped, 2 xfailed, in 26:56 wall and 6 294
worker-seconds.

- The cost is concentrated: 108 tests (1 %) take 61 % of the seconds, and the
  8 567 tests under 0.1 s sum to 91 s.
- Setup is 569 s (9 %) and call is 5 708 s. So the cost is in test bodies, and
  fixtures rebuilt per worker are a small lever.

Local seconds are not CI's: across the 59 files over 10 s in both, the ratio of
this machine to the shard record had a median of 1.21 (interquartile range
0.88–1.67). So the figures below rank the items; they do not price them on CI.

| Item | Here (worker-s) | Share |
|---|---|---|
| The guide and example scripts (`test_examples.py`) | 731 | 11.6 % |
| Indexing searches, six files (see E) | 803 | 12.8 % |
| The automatic profile interval | 525 | 8.3 % |
| Manual builds, manual API, help anchors | 215 | 3.4 % |
| Tutorials (CI: newest leg only) | 216 | 3.4 % |
| One test, `test_cell_runaway_safety` (see D) | 217 | 3.4 % |

**A. The jax leg runs the whole fast tier, and jax changes a few files.**
- In this tree's numpy-only run, 73 cases skip with "could not import 'jax'":
  - `test_cross_backend` 46;
  - `test_backend_conformance` 21;
  - `test_derived_block`, `test_rotation` and `test_voigt` 2 each.
- `test_backend_jax` skips at collection.
- `test_backend_shim` and `test_capabilities` read the backend registry.
- In `src/`, jax is imported only under `backend/` and in
  `optimize/least_squares.py`'s `backend == "jax"` branch.
- Those files are 573 of the 2 408 recorded jax-leg seconds, 24 %
  (`tests/shard_times.json`, profile `jax`).
- What a full-tier jax leg gives per push and selection would drop:
  - the whole tier on 3.13;
  - the `[dev,jax]` dependency resolution.

  Both stay in the nightly: `full` is `[dev,jax]` on 3.13, and `middle` runs
  3.13.
- A hand-kept file list rots the way `features["indexing"]` did (WP-1037). So
  derive the selection from what the cases import or skip on. Then add a guard
  so that a new test needing jax cannot fall outside the selection and run
  nowhere per push.

**B. The documentation runs on every leg.**
- `test_examples.py` runs each `examples/guides/*.py` script as a fresh
  subprocess, and the scripts run real fits. Those are the 23 guide cases WP-1986
  added on 2026-10-17: 617 s, median 14.5 s, the slowest `interval` at 83 s,
  then `qpa` 78 s, `stage` 73 s and `hold` 63 s.
- The module docstring's cost model (3.5 s and 3.3 s) predates them.
- `test_manual`'s Sphinx build is 81 s.
- The tutorials already run on the newest leg alone, through `RIETX_TUTORIALS`
  (WP-1547), with the reason stated in `tests/test_tutorials.py`. The same
  switch suits the guides and the builds, keeping them per push.

**C. The automatic profile interval** (WP-2002, B2 ruled option 2 on
2026-10-19: it runs on the answer stage for each moment angle the stationary
test passes).
- **Whole-tier effect.** I re-ran the whole fast tier with
  `strategy.parameter_interval.attach_stationary_intervals` replaced by a no-op
  (a throwaway `-p` plugin; nothing in the tree changed):
  - worker-seconds fell from 6 294 to 5 769;
  - wall time fell from 26:56 to 24:28;
  - `test_stationary_moment_angle` saved 352 s, and `test_magnetic_moment_frame`
    saved 82 s;
  - other files moved only within noise.
- **Five cases failed without it**, the five that assert on the interval:
  - `test_magnetic_moment_frame::test_an_angle_the_data_cannot_see_stops_its_interval_at_half_a_turn`
  - `test_stationary_moment_angle::test_a_stop_beside_the_symmetry_direction_leaves_the_angles_out`
  - `test_stationary_moment_angle::test_an_angle_without_an_esd_still_has_a_profile_interval[0.0]`
  - `test_stationary_moment_angle::test_an_angle_without_an_esd_still_has_a_profile_interval[1e-14]`
  - `test_stationary_moment_angle::test_a_left_out_angle_carries_its_interval_and_the_history_gains_no_node`
- **What is recoverable.** Those five carry about 230 of the 434 s and keep
  them. The other 21 cases in the two files pay about 200 s for intervals they
  never read.
- **One fit.** `test_stationary_moment_angle._fit(0.0, seed=4)` takes 3.4 s with
  the no-op and 52.1 s without it. cProfile puts 94 % of it in
  `attach_stationary_intervals`, which makes 116 `run_stage` calls.
- The module docstring still says "about half a second a fit".
- The private switch exists: `Refinement._auto_intervals`, which `_trial` and
  `strategy/magnetic.py` set to `False`.

**D. One test is 3.4 % of the tier.**
`test_cell_runaway_safety::test_a_wrong_triclinic_le_bail_fit_raises_no_degenerate_cell_error`
takes 217 s, the longest case in the tier.
- It runs two TRF Le Bail plans on a wrong P 1 cell.
- It asserts that Rwp is finite and positive: the claim is that
  `DegenerateCellError` no longer escapes `fit`.
- The module carries one `pytestmark` xdist group, so the module's 226 s sits
  on one worker.
- Its own comment says the trajectory is rounding-chosen: Rwp read 0.33,
  127.7 and 7.8e6 at starts 1e-14 apart, and once 1.1e9 on Linux CI.

**E. Repeats read off the code, not yet measured one by one.** A test-suite
review on 2026-10-21 listed these from reading the code; measure each before
cutting it.
- `test_indexing_engines.py:1568-1584` reruns searches that `:742` and `:1061`
  already run.
- `test_background_auto.py` runs the same `_absorption_fit` at `:1363` and
  `:1461`, and the same Si640c order scan at `:897` and `:930`.
- `test_recipe.py`'s `written` module fixture was set up four times in the
  measured run, about 26 s. Its consumers carry no `xdist_group`.
- Several indexing tests run a full multi-engine `index_pattern` and then read
  only provenance notes or the event ladder: `test_indexing_ceiling.py:276-334`
  and `test_indexing_priors`. The six indexing files are 803 s here.

**F. The shard record is stale.**
- `tests/shard_times.json` is from run 38088718957 (2026-10-12) and lacks 64
  files. Each missing file weighs the median 2.35 s.
- Missing ones that matter: `test_stationary_moment_angle` (399 s here),
  `test_indexing_inliers` (175), `test_parametric_series` (87) and
  `test_distortion_modes` (82).
- `test_examples` is recorded at 81.4 s against 731 here.
- `python -m tests.shards DIR` rewrites the record from a run's `junit-*`
  artifacts (its docstring). A stale record costs balance, never a test
  (tests/CLAUDE.md § CI). The 10-21 jax shards were 19.6 and 16.9 min.

**Not worth reopening.**
- **Worker count:** `-n logical` buys nothing on the 2-core runner (WP-1547).
- **A jax compile cache:** warm 8:18 against cold 8:12 (`ci.yml`).
- **Blanket xdist groups:** setup is 9 % of the tier.

### Inherited

- **2026-10-31, from [WP-2065](2065-a-hung-fast-job-names-its-test.md) (issue
  #1249): the cap cancels since 30 Oct were one case, now `slow`.** 8 of 788
  `fast` jobs printed `[ 99%]` and then nothing until the 40-min cap, main's
  push run 41141605322 among them. The case was `test_subgroups.py`'s
  `…denominator_bound[P -1-53]`, 629 s (3.11) and 812 s (3.14) on main run
  41045940948's passing shard 1/2. PR #1254 (`2c2e23666`) moved it and its
  p = 29 sibling (101-129 s) to the nightly and refreshed the record, on which
  19 files had been missing: they put 18.1 min on py3.11's shard 1 against
  2.2 min on shard 2. The ten-run acceptance here reads runs on a tree with
  both changes, or leaves the cancels out and says how many.
- **2026-10-23, from [1547](1547-the-fast-tiers-tail.md) (closed): main's slowest
  fast job is over 20 min again on three of the five latest runs.** Job walls,
  `started_at` to `completed_at`, from GitHub's REST API: 39865423926 17.6 min
  (py3.11 1/2), 39867656769 22.2 (py3.14 2/2), 39878630013 21.9 (py3.14 2/2),
  39930844656 17.5 (py3.11 1/2), 39937040834 21.7 (py3.14 2/2). On 39937040834
  py3.14's shards took 9.1 and 21.7 min and the jax job 8.6. So the imbalance
  survives the record refreshed in #1098 (merged 2026-10-22), whose predicted
  py3.14 split was 22.8 / 23.0, and all five runs are on that record. 1547 closed on its first ten
  runs after #869 (median 14.75 min).

## Non-goals

- **Why `isotropy.analyse` is slow, and the fast tier computing the F m -3 m
  analysis twice:** WP-1418, whose `### Inherited` (from 1506, 2026-09-27)
  leaves the test-fixture-or-faster-`analyse` choice to it. Measured here:
  116.5 s and 142.0 s for the two cases.
- **Whether the profile interval runs by default:** WP-2002's B2. This WP stops
  tests paying for it where they do not read it. It does not change what a
  user's fit computes.
- **The nightly's red, the release gate, and the review's tolerance and oracle
  findings of 2026-10-21:** not filed here.

## Tasks

- [x] **Refresh the shard record.** Rewrite `tests/shard_times.json` from the
      latest green main run's junit artifacts, both profiles. The commit names
      the run. *Superseded in part 2026-10-21: one profile, `numpy`, since the
      jax job no longer shards (next item). Done 2026-10-21 from main run
      39687915804 (ed299ba3d), the first after #1095: 269 files, 2784 s. The
      py3.14 shards there were 9.6 and 14.9 min.*
- [x] **Select the jax leg's cases.**
  - Derive the selection from what each case imports or skips on, and run the
    leg as one job.
  - Add a guard that fails when a case needs jax and falls outside the
    selection.
  - `ci.yml`'s header says what the leg no longer covers per push and where it
    runs instead (`full`, `middle`).
  - *Done 2026-10-21: `tests/jax_cases.py` (three rules read off the code),
    `--jax-cases` in `conftest`, and the guard there on every leg without jax.
    The record's `jax` profile went with the shards.*
- [x] **Run the documentation on one leg.**
  - The guide scripts and the manual builds run on the newest per-push leg
    with the tutorials, and skip elsewhere through the same switch pattern as
    `RIETX_TUTORIALS`, so passed+skipped holds on every leg.
  - The decision says what a guide could break on one Python version and not
    another.
  - `test_examples.py`'s docstring gets its cost model re-measured.
  - *Done 2026-10-21: one switch, `RIETX_DOCS` (it replaces
    `RIETX_TUTORIALS`), in `tests/documentation.py`, which holds the decision.
    The builds skip in their session fixtures, so their readers in
    `test_help.py` skip with them. `test_documentation_switch.py` runs a case
    from each site under the switch.*
- [x] **Stop the interval cost where nothing reads it.**
  - The 21 cases that do not assert on the interval stop computing it, through
    the switch WP-2002 settles (see its Inherited).
  - The five that assert on it keep it.
  - `test_stationary_moment_angle.py`'s docstring cost is corrected.
  - *Done 2026-10-21 through `Refinement._auto_intervals`, the only switch
    there is: 2002's open branch keeps it private, and a public one would be
    a rename here. Both files' `_fit` helpers default it off, and the five
    readers pass `intervals=True`. `refine_sequential` takes no switch, so
    `test_a_series_moment_row_states_the_written_back_moment` still pays for
    one pattern's intervals (5.6 s).*
- [x] **Cut `test_cell_runaway_safety`'s triclinic Le Bail case.** Test the
      reset directly, or mark it `slow` and see it pass once in the nightly's
      `full`. *Marked `slow` (2026-10-21): the reset of this cell and the reset
      inside `fit` are asserted per push by other rows. The nightly pass is
      still owed (Acceptance).*
- [x] **Measure and cut the repeats in E.** Measure each one first. Share a
      repeat through a module fixture carrying its `xdist_group` where the
      measurement says it pays. Put a wiring-only indexing assertion on one
      engine or a stub. The ranking claims stay on full searches.
      *Done 2026-10-21: three of four cut, 285.6 → 164.2 worker-s over the
      four files. `test_background_auto`'s repeats measured under 0.2 s each
      and were left (E had paired the wrong fits). The indexing wiring tests
      cost the ambiguity sweep, not the search, so the lever was
      `max_candidates`, with one engine only alongside it. The priors row
      went back to its full search at review: it also asserts the engines'
      rank-1 candidate, a ranking claim.*
- [ ] **Re-measure.** Run the fast tier on the final tree locally (venv and
      platform quoted) and read ten main runs (Acceptance).
- [x] **Skill:** none. This changes how the repo is tested, not how rietx is
      driven.

## Acceptance

- **Wall clock.** Over ten consecutive successful main runs after the CI
  changes land, the median run's slowest fast job takes 15 min or less. A job
  is timed from start to end, setup included (WP-1547's reading).
- **Counts.** Each leg's passed+skipped, summed over its shards, equals the
  unsharded fast count at the same commit. Every fast case runs on at least one
  per-push leg. A case moved to `slow` passes once in the nightly's `full`.
- **The jax job.** Its passed count for cases that skip without jax equals the
  full-tier jax leg's at the same commit.

```sh
gh run list --workflow ci.yml --branch main --event push --status success --limit 10 --json databaseId
gh run view <id> --json jobs   # each "fast …" job's startedAt to completedAt; take the largest
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow" --shard 1/2   # and 2/2
```

## References

- [WP-1547](1547-the-fast-tiers-tail.md): the shards, the tutorial switch, and
  the acceptance reading reused here.
- WP-2002's `2002-batch/rulings.md` § B2: the interval's ruling.
- Runs 38093251416 (10-11), 38088718957 (the shard record), and 39589774138
  (10-21).

## Handover log

### 2026-10-21 (3rd session) — the shard record is refreshed from the first run after #1095

The shard record now holds every fast file at what it cost on CI after this
WP's changes. The previous record was ten days old and lacked 64 files. Under
the new record the slowest leg's two shards should come out nearly even. The
other leg gets less even, and its heavier shard should still finish no later
than the slowest leg's. Nothing here is measured as a job wall yet. The ten
runs of the Acceptance read that.

- **Done** (c13779f8a): `tests/shard_times.json` rewritten by
  `python -m tests.shards DIR` from main run 39687915804 (ed299ba3d, green).
  That is the first main run after #1095. It holds 269 files and 2784 s, in
  the `numpy` profile alone.
- **Measured.**
  - Run 39687915804's job walls, setup included: py3.11 10.6 and 10.7 min,
    py3.14 9.6 and 14.9 min, jax 7.4 min.
  - Predicted balance. Each record's shard 1 was collected locally
    (`--collect-only -m "not slow" --shard 1/2`, `[dev]`, macOS arm64,
    Python 3.12). Both splits were weighed by that run's per-file seconds.
    The figures are test-seconds summed over the workers. They rank the
    splits and do not time a job.

    | Leg | Old record (shard 1 / 2) | New record (shard 1 / 2) |
    |---|---|---|
    | py3.14 | 28.3 / 17.5 min | 22.8 / 23.0 min |
    | py3.11 | 19.8 / 19.6 min | 22.9 / 16.6 min |

  - py3.11 loses balance because one split serves both legs. The record
    weighs the documentation files at py3.14's cost, and py3.11 skips them.
    The heaviest of the four shards still falls from 28.3 to 23.0.
  - Files the Context listed as missing or stale now read:
    `test_stationary_moment_angle` 82.8 s, `test_indexing_inliers` 95.3,
    `test_parametric_series` 29.8, `test_distortion_modes` 37.6 and
    `test_examples` 330.3. `test_magnetic_isotropy` is the largest at 388.0.
  - `tests/test_shards.py` passed, 28 of 28 (`[dev]`, macOS arm64,
    Python 3.12). No test was added, so no count moved.
- **Review.** `/code-review` was skipped: the branch changes a JSON record and
  this WP file, with no code to read.
- **Gotchas:** `pytest --collect-only -q` prints per-file counts, not node
  ids, because `addopts` already carries one `-q`.
- **Next**, in this order:
  1. After this merges, read ten main runs (Acceptance). Runs before the
     merge measure the old record.
  2. See `test_a_wrong_triclinic_le_bail_fit_raises_no_degenerate_cell_error`
     pass once in the nightly's `full`.
  3. If the slowest job is still over 15 min, the levers stay as below:
     `test_magnetic_isotropy` (1418's) and the documentation's own cost on
     the newest leg. A per-leg record would balance py3.11 too. It earns its
     place only if py3.11 becomes the slowest job.

### 2026-10-21 (2nd session) — each leg runs what only it can see; the record is still the old one

Each per-push job now does the part only it can do. The jax job runs the
handful of cases that reach jax instead of the whole tier again, and a guard
on every other leg makes sure none of those cases quietly runs nowhere. The
tutorials, guide scripts and manual builds execute on the newest Python
alone. Tests no longer pay for a profile interval they never read, the
tier's single longest case moved to the nightly, and three measured repeats
are shared. What this does to CI's wall clock is not known yet, for two
reasons: the shard record could not be refreshed (this environment cannot
download CI artifacts), and the WP's acceptance reads ten main runs after
the merge.

- **Done** (PR #1095): tasks 2-6 and the skill line. A WP-2003 handover
  repair also rides this branch (f036bf9).
  - `tests/jax_cases.py`: a case reaches jax by a parameter, its own code or
    a fixture's naming jax, or its module importing or skipping on jax at
    import. `--jax-cases` selects it, and `conftest` fails a jax skip outside
    the selection wherever jax cannot be found. The guard was made to fail on
    `test_rotation`'s two jax rows.
  - `ci.yml`: `fast jax` is one unsharded job, and its header says what it no
    longer covers per push and where that runs instead.
  - `tests/documentation.py`: `RIETX_DOCS` replaces `RIETX_TUTORIALS`.
  - Interval: off by default in both moment-angle `_fit` helpers.
  - Triclinic runaway case: marked `slow`.
  - Repeats: `recovered` in `test_indexing_engines`, a `recipe-tables` group,
    and `max_candidates` on the indexing wiring rows.
  - Shard record: the `jax` profile is gone. The record weighs a file from the
    legs that ran the most of its cases, each leg on a clock built from files
    every leg ran alike. Otherwise the documentation, now on one leg, would be
    halved where it runs.
- **Measured** (`[dev]`, Linux x86-64, Python 3.12, 4 cores, nothing else
  running):
  - **Fast tier on the final tree** (`6848e61`; later commits touch `docs/` only): 11 010 passed, 203 skipped,
    3 xfailed, 22:57 wall.
    - 5 446 worker-s, against Context's 6 294 at 3437d52; main has moved
      since, so that ranks and does not price.
    - The documentation is 956 of it.
  - **Count:** +51 `test_jax_cases`, +2 `test_documentation_switch`, +2
    `test_shards` rows, −1 to `slow`, so a net +54. No new skip in the tier.
  - **The added tests** cost 16.0 s: `test_jax_cases` 13.3 s (its subprocess
    rows), `test_documentation_switch` 2.7 s. Neither joins the tail.
  - **Jax rows on `.venv`:** 74 jax skips (73 cases and one module), all
    inside the selection.
  - **A throwaway `[dev,jax]` venv** (Python 3.13, jax 0.12.0): the selection
    is 86 passed and 5 skipped, none of the skips for jax.
  - **Repeats:** 285.6 → 164.2 worker-s over the four files the lane
    measured. The priors row was then put back to its full search, so its
    ~15 s returns.
  - **Interval:** 3.4 s a fit without it, against 52.1 s with it.
  - **The case moved to `slow`** passes locally under `-m slow`: 1 passed in
    41.9 s alone, on a quiet machine. The 217 s in Context was its time inside
    the loaded `-n 4` tier, so the saving per push is less than that figure.
  - **Guides:** 614 s, median 13.8 s.
  - **Lanes** (`session_usage.py lanes`):

    | lane | est | requests | main at dispatch | lane $ | saved $ |
    |---|---|---|---|---|---|
    | jax-selection | 30 | 110 | 249K | 8.41 | −0.45 |
    | repeats | 35 | 95 | 383K | 6.41 | +3.57 |

    Trial row +3.13 (+9 %). Selective policy at 300K-450K peak: −7 % over two
    sessions.
- **Review** (`/code-review high --fix`): four fixes taken, in 886325f and
  6848e61.
  - The record's clock now reads case counts (my first version still halved
    the guides).
  - One shared guard for both hooks.
  - The CI concurrency sentence.
  - The priors row's narrowing was reverted, not strengthened, because it
    also asserts the engines' rank 1.

  Declined:
  - `jax_importable` uses `find_spec`. A real import probe would import jax at
    collection.
  - A method with a column-0 string literal cannot be dedented, so rule (b)
    misses it. The guard still catches the case.
  - `test_manual_api` executes Part 1's python blocks on every leg, and the
    switch does not reach it. That is a scope call for the next session.
- **Gotchas:**
  - **Artifacts:** `gh run download` cannot reach
    `*.blob.core.windows.net` from this environment, and neither can the
    GitHub MCP's download URL.
  - **Biggest file:** `test_magnetic_isotropy` is the tier's largest file
    (968 worker-s), and a shard takes it whole. Forwarded to 1418.
  - **A clashing WP-2019:** WP-2002's open branch files its own WP-2019, and
    no test refuses a duplicate number. Forwarded to 2002, and suggested as a
    task.
  - **One-engine indexing:** a one-engine `index_pattern` sweeps every
    candidate for ambiguity and runs about 2× an all-engine one
    (`consensus.checked_indices`). Suggested as a task, no owner WP found.
- **Next**, in this order:
  1. Refresh the shard record from a green main run once the artifact host is
     reachable. Run `python -m tests.shards DIR`, one profile, under the new
     weighting. Without it the shards stay unbalanced: the latest main run's
     py3.14 shards were 18.0 and 8.5 min.
  2. After #1095 merges, read ten main runs (Acceptance).
  3. See `test_a_wrong_triclinic_le_bail_fit_raises_no_degenerate_cell_error`
     pass once in the nightly's `full`.
  4. If the slowest job is still over 15 min, the levers left are
     `test_magnetic_isotropy` (1418's) and the documentation's own cost on
     the newest leg.
- **CI fix (PR #1095, run 39682111529):**
  - `test_a_real_run_fails_each_jax_skip_the_selection_cannot_see` failed on
    py3.11 2/2 and py3.14 2/2 and passed locally.
  - The cause: GitHub Actions sets `CI`, and there pytest prints a short-summary
    line whole, with ` - <message>` after the node id. Elsewhere it cuts the
    message to the terminal or drops it.
  - So the assertions now read the node id before ` - `, and count the guard's
    message in the long-form sections only.
  - Reproduced with `CI=true`; both modes now pass 51 of 51.

- **2026-10-21** — Created from a test-suite review session, which asked where
  the fast tier's time goes and measured it rather than reading it off the
  shard record.
  - **Why a new WP.** No open WP owns this. 1547 (🔄) has every task checked
    and waits on a ten-run acceptance that reads its 10-11 cut. This is the
    next round:
    - two of its causes landed after that cut: the guides on 10-17 and the
      interval ruling on 10-19;
    - two of its levers 1547 did not weigh: selecting the jax leg's cases, and
      running the documentation on one leg.
  - **Left with their owners.** The isotropy repeat is 1418's and the
    interval's default is 2002's. This session left Inherited notes in 2002
    and 1547.
  - **Not kept.** The junit files and the throwaway plugin were session-local.
    The numbers in Context are the record.
  - **Handover.** The branch is prose-only (`docs/wp/` alone):
    - `/code-review` was skipped, having no code to read;
    - no tests were added, so no count moved;
    - the files CI's `docs` job runs passed, 240 of 240 (Linux x86-64,
      Python 3.12, `[dev]`);
    - `closed_wp_writes` reported nothing.
  - **Next.** The shard refresh and the jax selection, which need no test
    rewrite.
