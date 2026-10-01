# WP-1903 — The lane trial decides whether a WP session sends long items to subagents

Milestone: unscheduled · Status: ⬜
Track: The repo's own process
Depends on: —
Priority: P4 2026-10-01 — was P3 (cost only: the replay put the saving at about a fifth of a WP session's bill): down a rung until three trial rows are in the record

## Goal

At least three WP sessions have run under `/wp-lanes`, and their measurements
are in the record. On that evidence the lane rule goes into `/wp-start` step
6b, changes and is tried again, or is withdrawn with the reason written down.

## Context

**What exists** (PR #586, 2026-10-01).

- `docs/milestones/process.md` § Lanes within a WP is the record. It holds the
  replay over 174 WP sessions, the crossover table and the trial table this
  WP reads. Read that section first. It is about 1,000 words.
- `.claude/hooks/session_usage.py` reads Claude Code's transcripts under
  `~/.claude/projects`. `baseline` re-runs the replay, and its `--u`, `--mo`
  and `--d` options take measured values in place of the assumed ones.
  `lanes <session-id>` measures one trial session. `context <session-id>`
  prints the main context now. A session's id is the name of the directory
  that holds its scratchpad. `tests/test_session_usage.py` pins it.
- `/wp-lanes NNNN` starts a WP session in place of `/wp-start NNNN`. It runs
  `/wp-start`, then sends an item to a lane when the main context is over 150K
  and the item's estimate is 20 or more requests. One lane runs at a time, in
  the session's worktree. The lane does not commit. The main session checks
  its diff, re-runs its tests and commits.
- `/wp-handover` step 3b runs the measurement whenever a session dispatched
  lanes. It puts the tables in that WP's handover entry and appends one row to
  the record's trial table.

**What the replay predicted.** Laning every item saved 20% or cost 4% of the
modelled reads and writes, depending on *u*. The selective policy above saved
19-28%, and 11-21% under heavier checking or one lane in five redone. Sessions
peaking under 300K saved about 1%. The replay is a model over real
trajectories, and five of its inputs are guesses:

| input | assumed | what the trial row calls it |
|---|---|---|
| *u*, code a lane re-reads that the main session held | 0-40K | re-read (*u*) |
| main-session requests to dispatch and check one lane | 5 | main requests per lane |
| tokens a lane leaves in the main context | 8K | left in main |
| how well a session guesses an item's length | exact | actual / estimated requests |
| how often a lane's work is fixed or redone | never | lanes fixed / redone |

**What the rows cannot show.** Whether lane-written code is as good. Read it
off each trial session's handover entry: the findings `/wp-handover` step 6
raised on lane-written diffs, and anything the lane prompt failed to carry. A
lane loads the CLAUDE.md files but no MEMORY.md, so a forgotten memory rule
shows up there.

**Gotchas.**

- The transcripts live only on the machine that ran the session, and Claude
  Code deletes old ones (`cleanupPeriodDays`). Run the evaluation on the
  maintainer's machine, before the trial sessions age out. Each row is also
  committed to the record, so the summary survives either way.
- *In-session $* and *saved $* rest on the same model as the replay. The lane
  side is measured. The window from dispatch to commit counts every main
  request as lane overhead, which favours keeping the item.
- A trial session that never passes 150K dispatches nothing. Its `lanes:
  keep` lines still measure estimate accuracy, but the measurement only runs
  when a lane was dispatched. Pick trial WPs with several implement-and-test
  items, and expect long sessions.
- `baseline` re-reads whatever transcripts the machine holds, so its numbers
  drift from the record's. Quote the run's date with them.

## Non-goals

- Lanes for reading. `/wp-start` step 6b already delegates reads above ~50 KB.
- Parallel lanes or lanes in separate worktrees. They save wall-clock time,
  not tokens, and their test runs would compete on one machine.
- Sonnet or Haiku lanes. Their cache reads cost the same as Opus or half of
  it, and the model follows the judgement an item needs.
- `/pr-review`'s delegation. It has its own measurement (#548).

## Tasks

- [ ] Wait for three trial rows, with at least six lanes among them. Each
      comes from a WP session started with `/wp-lanes NNNN`. Those sessions
      commit their rows under their own WP numbers.
- [ ] Re-run the replay with the trial's medians,
      `python3 .claude/hooks/session_usage.py baseline --u U --mo MO --d D`,
      and put its output in this WP's handover entry with the run's date.
- [ ] Read each trial session's handover entry for the quality evidence
      above. List the review findings on lane-written code, and what the lane
      prompts lacked.
- [ ] Decide, then land the decision:
      - **adopt**: move the rule into `/wp-start` step 6b with thresholds read
        off the re-run's crossover table, delete `/wp-lanes`, and keep
        `/wp-handover` step 3b, since it only fires when lanes ran;
      - **adjust**: change the thresholds or the lane prompt in `/wp-lanes`,
        and ask for more trial rows;
      - **withdraw**: delete `/wp-lanes` and `/wp-handover` step 3b, keep
        `session_usage.py`, and close this WP 🛑 with the reason.
- [ ] Write the decision and its evidence at the end of process.md § Lanes
      within a WP.
- [ ] Skill: none. The agent skill is for driving rietx, and this is a rule
      for changing it (root CLAUDE.md § Roadmap, the three destinations).

**A bar to start from**, proposed 2026-10-01 and not yet agreed with the
maintainer. Adopt if the re-run's selective row saves at least 10%, at most
one lane in five was redone, and the findings on lane-written code are no
worse than usual. The 10% is half the replay's middle figure, chosen to leave
room for what the model leaves out. Confirm or replace it before deciding.

## Acceptance

The decision is written into the record with the trial rows and the re-run
behind it, and the commands and tests agree with it:

```sh
python3 .claude/hooks/session_usage.py baseline --u U --mo MO --d D
.venv/bin/python -m pytest tests/test_session_usage.py tests/test_docs_consistency.py tests/test_workflow_hooks.py -n auto --dist loadgroup
```

## References

- `docs/milestones/process.md` § What a session's reading costs (#548, the
  cache-read mechanism and the reading bars) and § Lanes within a WP (#586).
- Prices: Opus 5.5 $4 input, $20 output, $0.20 cache read, $5 5-minute write,
  $8 1-hour write per million tokens. Sonnet 5.5 $2, $10, $0.20, $2.50, $4.
  Haiku 4.5 $1, $5, $0.10, $1.25, $2. They are `PRICES` in the script.

## Handover log

- **2026-10-01** — created. No open WP owns session token economics. 1506 and
  1507, the two open ones on this track, are about CI and the WP index.

  This session measured whether subagents could make a WP session cheaper, and
  built a trial to test the answer on real work. Over 174 sessions, re-reading
  the context is two-thirds of the bill, and most of it is accumulation. A
  replay says that sending only long items, late in a session, to subagents
  saves about a fifth. Sending every item is fragile. Nothing in the package
  changed.

  *Done* (PR #586, four commits): `session_usage.py` with its tests, the
  record section, `/wp-lanes`, and `/wp-handover` step 3b. `/wp-lanes` began
  as a command to run after `/wp-start`. The maintainer pointed out that a
  session runs its checklist straight through after `/wp-start`, so it became
  the entry point, and the measurement moved into the handover, which the
  session invokes itself.

  *Measured*: the record's numbers, from `baseline` on 2026-10-01. Fast
  selection 7,072 passed, 157 skipped (`.venv` with `[dev]`, macOS). CI was
  green on the PR head `b94e4fad`.

  *Gotchas*: the first CI run failed on `test_portability`, which rejects any
  text I/O without `encoding=` in every test file. Run the fast selection
  before pushing a new test file.

  *Next*: merge #586, then start three or four WP sessions with
  `/wp-lanes NNNN`. Once three rows are in, run `/wp-start 1903`.
