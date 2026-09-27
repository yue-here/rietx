# WP-1506 — a planning-doc PR runs the tests that read it, and CI gates on one check

Milestone: unscheduled · Status: 🔄 2026-09-27 — claimed by @yue-here
Depends on: — (the branch-protection change is the maintainer's, by hand)
Priority: P2 2026-09-27 — was P4: the maintainer raised it the day it was filed; a planning-doc PR waits 20-22 min for a suite that cannot see its diff

## Goal

A PR that changes only planning documents reports green in about two minutes,
after running the tests that read those documents. Every code PR records its
per-test timings, so the next cut to CI time is chosen from numbers.

## Context

**The regression.** WP-1002 (2026-07-29, commit 2e6e89b6) gave `ci.yml` a
`paths-ignore` list for planning docs. WP-1003 (2026-08-16, commit 1a77e293)
removed it at the visibility flip. The fast jobs had become branch-protection
required checks, and a workflow skipped by a path filter never reports them,
so a docs-only PR could not have merged. Nothing replaced the skip. Every
planning-doc PR has run the whole matrix since, once when readied and again
on main after the merge.

**Measured 2026-09-27.** Merged PRs from 2026-08-27 to 2026-09-27, each read
as `git diff --name-only <merge>^1 <merge>` over origin/main's first parent:

- 232 PRs merged. 49 changed only files under `docs/wp/`, `docs/milestones/`,
  `docs/releases/`, `docs/ROADMAP.md`, `docs/DESIGN.md` and
  `tests/test_docs_consistency.py`. Adding the CLAUDE.md files and the skill
  copies makes 53. Tests read those four extra (`test_skill.py`, the manual
  build), so they stay on the code side.
- A readied PR runs 6 jobs. Wall time was 20-22 min over the last ten
  non-draft runs. Runner queue wait was 2-46 s, so GitHub Free's limit of 20
  concurrent jobs did not bind.
- The fast legs took 12-21 min each. On one commit (run 36303484975) py3.14
  took 12:03 and py3.11 20:12. Install steps took 1-3 s, so the uv cache
  works. Collection takes 1.6 s locally. The time is the tests.
- Locally the fast selection is 1 372 worker-seconds (junit `time` with
  `-o junit_duration_report=total`, 10-core Mac, another session running,
  2:40 wall). The 50 slowest tests take 52% of it. The 6 434 tests under 1 s
  take 26%. The longest xdist group is 82 s (`indexing-ceiling`), so no group
  sets the wall clock.
- For scale: WP-1002 measured the fast leg at about 3 min on 2026-07-29,
  and WP-1003 put the jax leg at about 10 min on 2026-08-16.

**Why the fix needs a summary check.** `ci.yml`'s header (commit 44847142)
records two facts. A job skipped by a job-level `if` reports success. A
skipped *matrix* job does not expand: it reports once, under the literal name
`fast py${{ matrix.python }}`. The required contexts on 2026-09-27 are
`lint`, `fast py3.11` to `fast py3.14` and `fast jax`, with `strict: false`
(`gh api repos/yue-here/rietx/branches/main/protection`). Skipping those jobs
on a docs PR would leave four required contexts that never appear, and the
PR could not merge.

The standard answer is one summary job. It `needs:` every gating job, runs
`if: always()`, and fails when any needed job failed or was cancelled. Branch
protection then requires `lint` and that job only. `re-actors/alls-green`
packages this with an `allowed-skips` input; a short shell step over
`toJSON(needs)` does the same. Once only the summary is required, the matrix
can be sharded or trimmed without touching branch protection again.

**Which tests read the planning docs is measured, not grepped.** A text
search for `ROADMAP|docs/wp|milestones|releases|DESIGN.md` hits 16 test files,
most of them in comments. An audit hook (`sys.addaudithook`, event `open`,
in a throwaway plugin) over one fast run lists the test files that open a
path in the planning set. That list is the docs job's selection. Expect
`test_docs_consistency.py`, `test_no_stale_name.py` and
`test_workflow_hooks.py` among them.

**The draft guard stays.** A draft PR runs lint alone, and `gh pr ready`
fires the gating run. The summary job has to pass a matrix skipped because
the PR is a draft. That is safe because a draft cannot merge.

**The fast tier grows by its tail.** Half the time is 50 tests. The repo
forbids a wall-clock assertion in a test (tests/CLAUDE.md § Budgets in
tests), so the guard is a report. The fast jobs upload junit timings, and
`/wp-handover` reads the rows for tests the branch added. Named members of
the tail today, in local serial seconds:

- Two tests in `test_magnetic_isotropy.py` each compute `isotropy.analyse` on
  F m -3 m: 26 s alone, about 70 s under suite load. This is folded into
  [1418](1418-the-magnetic-structure-is-determined.md)'s Inherited, since
  that WP owns the function.
- The 230-group and every-setting sweeps take 128 s together (9%).
  `test_the_sweep_over_the_230_settings_at_gamma` takes 44 s. Three
  230-group tests in `test_magnetic_irreps.py` take 67 s. And
  `test_symmetry_orbits.py::test_the_invariant_holds_across_every_setting_gemmi_knows`
  takes 17 s. A sample could stay in the fast tier with the whole sweep
  nightly. A break in an unsampled group would then show the next morning,
  and the WP states that trade rather than assuming it. Choose the sample by
  trap, never at random: 79 of gemmi's 564 settings were once served wrong
  under a correct count (root CLAUDE.md, cell ties).

**Considered and not taken:**

- A merge queue. GitHub offers it only on organization-owned repos, and
  yue-here/rietx belongs to a personal account. Moving the repo to a free
  organization would make it available.
- Larger runners. They need a Team or Enterprise organization plan and are
  always billed per minute.
- A self-hosted runner. GitHub advises against one on a public repo, since a
  fork's PR can run code on it, and contributors work from forks.
- Workflow-level path filters. WP-1003 removed them for the reason above.

## Non-goals

- The GUI dist and its write path to main: WP-1313. Its branch-protection
  change and this one are both the maintainer's, by hand, and are cheapest
  done in one sitting.
- Why `isotropy.analyse` is slow: WP-1418.
- The nightly's length: 1:40 for the Linux full suite on 2026-09-26, most of
  it indexing-acceptance fixture setup.
- The ROADMAP and cap conflicts: WP-1507.

## Tasks

- [x] Measure which test files open a planning-set path, with the audit hook
      over one fast run. Record the planning set and the list in `ci.yml`,
      beside the jobs that use them.
- [x] `ci.yml`: a `changes` job, using `git diff --name-only` against the PR
      base, or against `github.event.before` on a push. Add a `docs` job
      running the measured list, gate the matrix jobs on `changes`, and add
      the `ci-ok` summary job. In this commit the matrix still runs on every
      PR, so nothing is skipped while protection still names the matrix.
- [ ] By hand, maintainer: branch protection requires `lint` and `ci-ok`.
      This WP carries the written instruction, as WP-1313 does.
- [ ] Turn the skip on. Check a planning-only PR (`ci-ok` green in about two
      minutes) and a code PR (`ci-ok` waits for every leg). Make one leg fail
      on purpose once and confirm `ci-ok` goes red (tests/CLAUDE.md § Guards
      that go quiet instead of red).
- [x] ~~Main pushes: a planning-only merge skips the matrix the same way.~~
      Not taken, 2026-09-27. `ci.yml` cancels a run when the next push to
      its ref arrives. 51 of main's 240 runs in the month to 2026-09-27 were
      cancelled that way. A docs-only merge that skipped the matrix would then
      leave the cancelled code merge untested. Nobody waits on a main run, so
      the skip there would save runner minutes only.
- [x] The fast jobs upload their junit timings (`--junitxml`,
      `-o junit_duration_report=total`). `/wp-handover` reads the rows for
      the tests the branch added. The rule goes in tests/CLAUDE.md § Budgets
      in tests.
- [ ] From two weeks of those timings, choose the next cut and record its
      numbers. The options are sampling the named sweeps, sharding, or fewer
      Pythons on a PR. Sharding must keep each `xdist_group` whole. Five legs
      times N shards meets the 20-job limit when two PRs are readied
      together, so sharding probably comes with a smaller PR matrix.
- [x] tests/CLAUDE.md § CI and `ci.yml`'s header say what gates now.
- [x] Skill: none. This changes how the repo is tested, not how rietx is
      driven.

## By hand: branch protection

The maintainer makes this change once, by hand. It replaces the five matrix
contexts with `ci-ok` and keeps `lint`. App 15368 is GitHub Actions, and
naming it stops another app's status from satisfying the check.

```sh
gh api -X PATCH repos/yue-here/rietx/branches/main/protection/required_status_checks \
  --input - <<'EOF'
{"strict": false, "checks": [{"context": "lint", "app_id": 15368},
                             {"context": "ci-ok", "app_id": 15368}]}
EOF
```

In the web UI it is Settings → Branches → `main` → "Require status checks to
pass": remove the four `fast py3.x` rows and `fast jax`, then add `ci-ok`.

Do it in the same sitting as the merge that turns the skip on, in either
order. Between the two acts a docs-only PR waits for contexts that never
report, and nothing else is harmed. After the change, an open PR whose
branch predates `ci-ok` reports no such check. It can merge once `main` is
merged into it.

## Acceptance

- A PR touching only `docs/wp/**` shows `ci-ok` green within about two
  minutes, with the docs job's tests run and passed.
- A PR touching `src/` shows `ci-ok` pending until every leg finishes, and
  red when a leg fails (checked once on purpose).
- The required contexts are `lint` and `ci-ok`:

```sh
gh api repos/yue-here/rietx/branches/main/protection --jq .required_status_checks.contexts
gh run list --workflow ci.yml --limit 10 --json headBranch,conclusion,createdAt,updatedAt
.venv/bin/python -m pytest tests/test_docs_consistency.py
```

## References

- docs.github.com: "Troubleshooting required status checks" (a skipped job
  reports success, a filtered workflow reports nothing); "Managing a merge
  queue" (organization-owned repos only); "Larger runners" (Team and
  Enterprise plans only).
- `re-actors/alls-green`, a GitHub Action for the summary job.
- Commits 2e6e89b6 (WP-1002's `paths-ignore`), 1a77e293 (WP-1003 removed
  it), f147e0ea and 44847142 (the draft guard, and what a skipped matrix
  reports).

## Handover log

- **2026-09-27** — Created by the session the maintainer asked to find where
  the repo's CI and merge drag comes from. The docs-only skip was a
  regression: WP-1003 removed it for a reason that a summary check answers.
  The measurements above are that session's, taken from `gh run list`, the
  job logs, and one local fast run with junit timings. Next: the audit-hook
  measurement, then `ci-ok` with the matrix still unconditional.
