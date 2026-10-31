# WP-2065 — a hung fast job names its test, and the hang is fixed

Milestone: unscheduled · Status: 🔄 2026-10-31 — the cause was one 10-13 min case, now `slow` on main (PR #1254); both fast jobs set `faulthandler_timeout` (PR #1256); acceptance waits on twenty fast jobs
Track: The repo's own process
Depends on: —
Priority: P1 2026-10-31 — a required check red on main: the `fast` job hangs at `[ 99%]` and is cancelled at its 40-min cap, 8 times in about 15 hours, main's own push run among them; every PR it hits waits 40 min and reruns

## Goal

A fast CI job that stops making progress names the test it is stuck in, in
the job log, before the cap kills it. The hang behind #1249 is found and
fixed, so the `fast` jobs finish on their own again.

## Context

**The symptom** (#1249, filed 2026-10-31 by mustachefeeling). A `fast` job
prints `[ 99%]`, prints nothing for about 13.5 minutes, and the runner
cancels it at `timeout-minutes: 40` (`.github/workflows/ci.yml`, the `fast`
job). The cancel kills the xdist workers before pytest reports, and the `-q`
dots name nothing, so no log says which test hung. Sibling shards of the same
run finish in 10-34 min. It is intermittent: main's push run at `e016f187d`
passed, the one at `d35ffeda7` (run 41141605322) hung.

**Measured at triage** (2026-10-31, `gh run list --workflow ci.yml`, the
latest 200 runs; a `fast` job counted when cancelled at ≥ 39 min):

| created (UTC) | run | branch | job |
|---|---|---|---|
| 10-30 14:12 | 41069851182 | feat/wp2030-part2-ceiling-window | fast py3.11 1/2 |
| 10-30 15:25 | 41080601129 | pr/solve-engine-s2a | fast py3.14 2/2 |
| 10-30 22:58 | 41141605322 | main | fast py3.11 1/2 |
| 10-31 00:51 | 41152445053 | wp2033/declared-z-filter | fast py3.11 1/2 |
| 10-31 00:58 | 41152975513 | fix/wp1958-followups | fast py3.11 1/2 |
| 10-31 01:51 | 41157350326 | wp1924-dichotomy-memory-bound | fast py3.11 1/2 |
| 10-31 04:48 | 41170014530 | feat/941-followups | fast py3.11 1/2 |
| 10-31 05:29 | 41172806542 | wp1419/c2-derived-cell | fast py3.11 1/2 |

8 of 788 `fast` jobs in the window, every one since 30 Oct 14:12Z. The
issue counts none between 24 and 30 Oct. Its follow-up comment adds a ninth
of a different shape: `fast py3.11 2/2` on #1206 at `819ff531` (run
41168160456) printed `[ 99%]` at 04:39Z and was cancelled at 05:00Z, so the
test moves between shards with the split. Seven of the eight are shard 1/2 on
3.11, one is 2/2 on 3.14. A local fast suite on macOS and on a Linux
workstation finished normally on the same heads (the issue's report, not
re-measured).

**Two suspects for the onset, neither checked.** *(Superseded in part 2026-10-31: the first held, a case #1189 added; Tasks and the handover log say which.)*

1. *A merge.* Main took eleven merges between 30 Oct 10:30 and 11:08Z
   (`a25650ed1` … `e016f187d`: #1232, #1228, #1138, #1227, #1163, #1202,
   #1194, #1189, #1222, #1123, #1107). The first hang is three hours later.
   A branch hangs only if its base carries the cause, so each hung run's
   merge base against main bounds the window.
2. *A dependency release.* `uv pip install -e ".[dev]"` resolves afresh each
   run, and only pytest is capped (`<9.2`, for pytest-xdist#1386). The
   install step's log lists every resolved version, so a hung run's list
   diffed against a passing run's from 30 Oct 11:00Z answers this in one
   read. `tests/record_environment.py` prints only numpy and scipy.

**Naming the test.** pytest's built-in `faulthandler_timeout` ini option
dumps every thread's traceback when one test runs past it. It adds no
dependency and leaves the test running, so the 40-min cap stays the runaway
guard `ci.yml`'s header asks for. Two facts to establish before relying on
it. (a) Under xdist the dump is written by the worker, and whether it reaches
the job log through execnet has to be shown with a planted sleeping test in a
CI run, not assumed. (b) The value sits above the slowest passing test,
read off the junit artifacts each `fast` job uploads (`junit-py*`, 30-day
retention), and well under the 13.5 min of silence. The alternative is
`pytest-timeout` with `timeout_method = "thread"`: a new dev dependency,
and it ends the run with a named failure rather than letting the cap fire.
Practice: both are the documented pytest answers to a hung test
(docs.pytest.org, "faulthandler"; the pytest-timeout README). Neither was
checked against a CI log at triage.

**Rules this WP touches.** A wall-clock budget in a test is a runaway guard,
never a timer (root CLAUDE.md § Commands). `--dist loadgroup` is required,
and `tests/conftest.py` refuses a run without it. The shard record
(`tests/shard_times.json`, `tests/shards.py`) deals whole files and groups.
So a hung test's shard follows the record, which a branch may refresh.

### Inherited

## Non-goals

- The fast jobs' wall time: WP-2019 owns it. Its ten-run acceptance reads
  main's runs, and a run this hang cancelled is not a slow run.
- The nightly's legs: WP-2036.

## Tasks

- [x] **Name the test.** Set `faulthandler_timeout` for the `fast` and
  `fast-jax` jobs (on the command line in `ci.yml`, or in
  `[tool.pytest.ini_options]` if a local run should dump too). Prove the
  dump reaches the job log with a planted sleeping test on a throwaway
  branch, then drop the plant. *Done 2026-10-31: `-o faulthandler_timeout=600`
  on both jobs' command lines. Shown locally under `-n 2`: a planted 6 s
  sleep at a 3 s timeout printed its file, line and function through
  xdist. The CI-log proof is open (handover).*
- [x] **Find the onset.** Diff a hung run's install log against a passing
  one's; bound the merge window by the hung runs' merge bases. Say which
  suspect held, with the run ids. *Done 2026-10-31: suspect 1, a merge.
  #1189 (`20e335247`, 30 Oct 10:32Z) added
  `test_subgroups.py::…denominator_bound[P -1-53]`, which took 629 s
  (3.11) and 812 s (3.14) on main run 41045940948's passing shard 1/2.
  The dependency suspect was not needed.*
- [x] **Fix the hang** at its mechanism, and look for siblings: any other
  test that waits on a thread, a subprocess, a lock or a socket without a
  timeout of its own. *Done 2026-10-31: no hang. The case is slow, and it is
  slow by design: P −1 keeps every sublattice invariant, so the series is
  p(p² + p + 1) subgroups, 151 739 at p = 53. Main's `2c2e23666` (PR #1254,
  merged the same day) marked both P −1 rows `slow`, and this branch took it
  over its own p = 53-only edit. The hexagonal p = 29 rows keep the bound
  covered per push. Siblings: no other fast case on that run exceeds 152 s.*
- [x] **Tests**: a case that fails, not hangs, if the mechanism comes back,
  where one can be written. *None written: a per-case time gate is what
  tests/CLAUDE.md declines (the tail's guard is a report, WP-1506). The
  faulthandler dump is the check.*
- [x] **Skill:** none. This changes how the repo is tested, not how rietx
  is driven.

## Acceptance

Twenty consecutive `fast` jobs on main and PR runs with no cap cancel,
counted by the script that built the table above (`gh run list --workflow
ci.yml`, then each run's jobs). And the planted-test run's log, linked in the
handover, showing the dump with the test id.

```sh
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- #1249 (the report and its follow-up comment); #745 (a closed earlier
  report of cancels at a 30-min guard, 2026-10-06).
- pytest docs, "faulthandler"; pytest-timeout README.

## Handover log

- **2026-10-31** — the fix. There was no hang. One fast-tier case from #1189
  enumerates 151 739 subgroups and runs 10-13 minutes on a CI runner. Placed
  last on a worker, or on a slower runner, it alone carried its shard past the
  40-min cap, with `[ 99%]` and then silence. It now runs in the nightly. Per
  push, the hexagonal rows check the same bound. A case that runs past 10
  minutes now prints its own stack in the job log, so the next one names
  itself. Nothing is lost from the nightly.
  *Done*: `ci.yml`'s `fast` and `fast-jax` jobs pass
  `-o faulthandler_timeout=600`. The test edit was overtaken: the shard-refresh
  session's `2c2e23666` (PR #1254) marked both P −1 rows `slow` and merged
  first, so the merge of main took main's file whole. This branch's net change
  to the tests is nil.
  *Measured*: main run 41045940948 (`e016f187d`, passing), junit artifacts.
  `[P -1-53]` took 629.3 s on 3.11 shard 1/2 and 812.2 s on 3.14. The next
  slowest case on any leg was 151.5 s (a guide script, 3.14 2/2), which set
  the 600 s timeout. `test_subgroups.py` totalled 13.1 min (3.11) and 16.9 min
  (3.14). The series is p(p² + p + 1) subgroups, so p = 29 → 53 is 6.0×
  against CI's 6.3×. On #1254's run 41190396091 (the refreshed record), shard
  1/2 reached `[ 98%]` 17.5 min in and then printed nothing for 22.5 min, so
  rebalancing alone does not fix it. Locally (macOS arm64, `[dev]`, Python
  3.12, load average 29-39 from other sessions, so no timing is quotable):
  `pytest -n auto --dist loadgroup -m "not slow" tests/test_docs_consistency.py
  tests/test_subgroups.py tests/test_shards.py` gave 342 passed. The `slow`
  selection collects the p = 53 row. Ruff is clean. faulthandler under xdist:
  a planted 6 s sleep at a 3 s timeout, under `-n 2`, printed its file, line
  and function to the controller's terminal. Counts: the fast tier loses
  exactly one case, which the full suite still runs. The full selection was
  not run (machine busy; § Running).
  *Ruled out*: a faster exact `_maximal_invariant` (a line is maximal unless
  an invariant plane holds it). It matched the old rule on 438 cases across
  73 generator sets, p = 2-13, but saved 1 s at p = 29 (1.45 s → 0.47 s), so
  it was reverted. A supercell row at p = 53 cost 27 s and proved nothing p =
  29 does not, so it was not added.
  *Review*: `/code-review high --fix` over `origin/main..HEAD` found one item
  and fixed it (`e32be41cd`): `ci.yml`'s comment quoted the slowest case as a
  figure, and it now quotes a range. Checked and clear: no `faulthandler`
  opt-out in `pyproject.toml` or the conftest, and the nightly `full` job (a
  150-min cap, unsharded) already ran this case.
  *Audits*: no CLAUDE.md edit; no `_audit.py` change and no package
  heuristic added (the 600 s is CI configuration), so no generality judge.
  *Next*: (1) the CI-log proof of the dump, which needs a planted case on a
  throwaway PR (a maintainer's call, since it costs a CI run); (2) the
  acceptance, twenty `fast` jobs with no cap cancel, read with the triage's
  script once this merges; then close.
  *Posted*: the reply to the reporter on #1249 (the cause, PR #1254's move,
  PR #1256's dump), approved by the maintainer:
  https://github.com/yue-here/rietx/issues/1249#issuecomment-6542880199
- **2026-10-31** — created, from the 2026-10-31 issue triage (issue #1249).
  Checked against the tree at `766c3505d`: `ci.yml`'s `fast` job still caps
  at 40 min and sets no `faulthandler_timeout`, no `pytest-timeout` is a
  dependency, and the 8 cap cancels above were counted from CI that day. No
  open WP owns it: WP-2019 owns the fast jobs' speed and WP-2036 the
  nightly, and neither covers a test that never finishes. Next: the first
  task, since nothing else can start until a log names the test.
