# WP-1988 — A PR put up for review is watched by the session that opened it

Milestone: unscheduled · Status: 🔄 2026-10-23 — hook, steward skill and command edits landed; the hook fired unprompted on #1127, and a red check on #1134 was handled unprompted; whether that meets the acceptance is the maintainer's call
Track: The repo's own process
Depends on: —
Priority: P4 2026-10-16 — process: no number moves, but every WP PR waits on someone noticing it went red or conflicted

## Goal

A WP session's PR stops being left alone at the handover. `/wp-handover` step
12 offered to watch the run; unwatched, a PR goes conflicted or red as soon as
main moves under it, and stays so until the maintainer finds it. A cloud
session has `subscribe_pr_activity`, which delivers CI results, reviews and
merge conflicts into the session that opened the PR. This WP makes the
subscription happen and says how this repo wants the events handled.

## Design

- **A PostToolUse hook, not prose** (`.claude/hooks/pr_subscribe.py`). A hook
  cannot call an MCP tool, so it notices the PR becoming reviewable
  (`gh pr create` without `--draft`, `gh pr ready`, the two `mcp__github__`
  equivalents) and puts the call, owner, repo and number filled in, in front of
  the model as `additionalContext`. It is silent on a draft, on a read, and on
  a failed create, since it names no PR it cannot read off the output.
- **The subscription starts at ready, never at the claim draft.** `/wp-start`
  step 4b's draft is still being written; every event on it is the session's
  own push.
- **`.claude/skills/steward/SKILL.md`** is the repo half. The cloud harness
  reads that path from the PR's head branch before acting on an event, and it
  takes precedence on conventions: merge main in rather than rebase,
  regenerate generated files rather than take a side (pointing at
  `/pr-review`'s bookkeeping sync, never restating it), reproduce a CI failure
  before fixing it, never skip or widen a test, and a substantive fix touches
  the WP file so `session_start.py`'s order rule does not flag a repair.
- **One WP per session survives the handover.** A subscribed session ends on
  *watching <url>*, not *ready for /clear*, and the next WP is a new session.

## Tasks

- [x] `pr_subscribe.py` + its `PostToolUse` registration, tested in
      `tests/test_workflow_hooks.py`.
- [x] `.claude/skills/steward/SKILL.md`.
- [x] `/wp-handover` steps 11-12, `/wp-start` step 4b. ROADMAP's protocol
      step 3 is left alone: it sits at its pinned size cap, and the command
      is the authority it points to.
- [ ] Acceptance: one WP handover in a cloud session subscribes from the hook's
      prompt, and one event on it (a merge conflict or a red check) is handled
      by the skill without the person asking. Record what it cost in context.

## Handover log

- **2026-10-23 (later)** — The event half of the acceptance happened on this
  WP's own PR, #1134. The maintainer merged main into the branch with GitHub's
  web button (`46143e08`), which runs no `wpindex` merge driver. The merged
  `docs/wp/README.md` kept 1988's old 2026-10-16 row beside its new one and
  2002's row after main had closed it, so `docs` and `ci-ok` went red on
  `test_the_wp_index_is_the_generators_output`. Two `check_run.completed`
  events woke the subscribed session with nobody asking. It read the failing
  job's log tail and fast-forwarded to the PR head. It reproduced the failure
  (`wp_index.py --check` stale, the same test red), regenerated the index as
  the steward skill's § Merge conflict says for a web merge, re-ran
  `test_docs_consistency.py` green and pushed that fix with this line.
  *Cost in context:* one wake, one model turn over the whole conversation, plus
  about 150 lines of tool output: the job log's 60-line tail and the
  fast-forward's 86-file diffstat. *Whether this meets the acceptance is
  the maintainer's call.* The hook fired and the event was handled unprompted,
  but #1134 was opened by hand after a closes batch, not through
  `/wp-handover` steps 11-12. The box stays open until that is decided.
- **2026-10-23** — Next (2) is answered, and the acceptance is still open. In a
  cloud session the hook fired unprompted when PR #1127 (the second "WP closes
  2026-10-23" batch) went up through the GitHub MCP `create_pull_request`, not
  `gh`. It named the PR, and the session subscribed and read the steward skill.
  This was a closes batch, not a single WP's `/wp-handover`, so it shows the
  hook firing and not step 11.
  *What woke the session, and what each wake did.* There were three wakes,
  each one model turn over the whole conversation at end-of-session size. That
  re-read, not the event, is the dominant cost. (1) `subscription.created`: one
  check-runs read, with CI in progress, and nothing to do. (2)
  `check_suite.completed`: the check runs and the PR read. Every job had
  passed (`docs` skipped, since a test file changed), and the PR was
  mergeable, so it waited on the maintainer. (3)
  `pull_request.closed` (merged): the safety-net check-in was cancelled. No
  conflict and no red check arrived, so the acceptance box stays open. It
  needs a PR that goes red or conflicted while watched.
- **2026-10-16** — Filed: no open WP owns PR follow-through (1506 and 1547 are
  CI's side, 1507 the index). A session that puts its PR up for review now
  gets told to subscribe to it, with the number filled in, and the repo says
  how conflicts and red checks on it are handled. Nothing has been watched
  under it yet, so whether the cost of being woken at handover-size context is
  worth it is unmeasured; this WP's own PR is the first candidate.
  *Done*: the hook, its registration and tests; the steward skill; the two
  commands. `/code-review high --fix` found seven real misses in the hook's
  command reading (multi-line commands, heredoc bodies, shell keywords and
  subshells, an escaped newline joining the owner name, a cited PR URL in an
  MCP body winning over the new PR's own) and fixed all seven, reusing
  `no_top_level_cd.py`'s heredoc stripper and keyword list rather than a second
  splitter. Declined: the matcher includes `Bash`, so every Bash call starts
  one more python3; narrowing it means a matcher on the command, which the
  harness does not offer, and the two PreToolUse Bash hooks already pay it.
  *Measured* (Linux x86-64, 4 cores, `[dev]`, main merged in at `0367ccb`,
  alone on the machine): fast selection 10684 passed, 203 skipped, 2 xfailed;
  this WP added 19 cases, all passes, no skip, 0.17 s in total
  (`tests.added_test_times`, local junit; the PR has had no CI run yet).
  *Gotchas*: filed as 1987, which main took the same day for the kernel-gate
  WP; renumbered, and the branch's two pushed commits were reworded (no PR
  existed yet), since `session_start.py` attributes commits by prefix and
  would have charged them to the other WP. **The hook did not fire on this
  PR's own create**: a session's hooks come from the settings it started with,
  here the main checkout's, which lack it until this merges. A worktree
  entered mid-session does not swap them (a `no_top_level_cd` refusal late
  in the session is no evidence otherwise, since main's settings carry that
  hook too). So this PR was subscribed by hand, as step 11 now says.
  Next: (1) watch this PR under the skill and record what each wake cost;
  (2) on the first cloud WP session after merge, check the hook fires unprompted; (3) if a
  wake is too dear, narrow the skill to merge conflicts and red CI and leave
  reviews to the person.
