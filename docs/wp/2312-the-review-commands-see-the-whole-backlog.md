# WP-2312 — the review commands see the whole backlog

Milestone: unscheduled · Status: 🔄 2026-11-26 — drafted; the larger triage call is unmeasured
Track: The repo's own process
Depends on: —
Priority: P4 2026-11-26 — process: no number moves, but a triage that ranks part of the backlog reads as ranking all of it

## Goal

`/pr-review` and `/issue-review` either rank the whole open backlog or say that
they could not. Neither one ranks a list that `gh` cut off silently.

## Context

On 2026-11-26 the repository had **84 open PRs** (79 from the recurring
contributor, 5 from the maintainer) and **191 open issues** (GitHub search
counts). Each listing these commands rely on asks `gh` for at most `--limit`
rows, and `gh` stops at that limit without saying so:

- `/pr-review` triage: `gh pr list --limit 30`. So the command ranked 30 of 84
  PRs, and the rank was wrong for the 30 it did see as well as missing the
  rest. Collision degree (files shared with *other open PRs*) counted only the
  PRs returned, and which PRs were left out was decided by gh's list order,
  not by the rank.
- `wp_claim.open_prs` (the `/wp-start` overlap table and `backlog.py`'s
  "open PR" column): `--limit 100`. 84 open, so close to the limit.
- `backlog.py`'s issue listing: `--limit 500`. 191 open, so not close yet.
- `backlog.py`'s merged-PR listing (`--limit 200`) needs no guard: a `git log`
  back to the oldest open issue covers anything older (`main`,
  `commit_references`).

Considered and dropped:

- **A light listing of every PR plus heavy fields for the queue alone.** It
  saves nothing. Rank 1 needs every PR's commit headlines (a `WP-NNNN:`
  prefix), and collision degree needs every PR's files, so the heavy fields
  are needed for all of them.
- **Storing `/pr-review`'s held decisions between runs.** Re-batching a PR
  held because it touches an in-flight WP costs a pass-A line, not a review.
  A stored hold also hides the moment the WP's session ends, and the durable
  form suggested at first, a "held" comment on each PR, would post noise
  under the maintainer's name.

Kept from the second item: `/issue-review`'s drafted public acts are lost
from the scratchpad at `/clear`, and an unanswered one used to leave no
trace. The skill now records the act owed and the question that held it, not
the draft text.

Tier ([generality § The rule](../milestones/generality.md#the-rule)): none.
This is process machinery and changes no package decision.

## Non-goals

- `/pr-review`'s throughput: the 500 K context checkpoint and the slow-suite
  gate are unchanged. How many PRs a session clears is limited by the
  maintainer's batch, not by this listing, and the batch is WP-2238's (the decision machinery).
- Pagination past `gh pr list --limit`. A raised limit plus a stop at the
  limit is enough until a measured run shows the call failing.

## Tasks

- [x] `wp_claim.OPEN_PR_LIMIT` and `listing_cut`; `status` says when the PR list may be cut off
- [x] `backlog.py`: `ISSUE_LIMIT`, and a note for each listing that reached its limit, read before `only` narrows the issues
- [x] `/pr-review` triage: `--limit 200`, and a call that returns exactly the limit is a stop
- [x] `/issue-review`: an act the batch leaves unanswered is recorded (the owning WP's `### Inherited`, else the PR body's held list)
- [ ] Measure the `--limit 200` triage call once on a machine where `gh pr list` runs (wall time, bytes, and whether GitHub answers), and record it here
- [x] Tests: `test_a_listing_at_gh_s_limit_reads_as_possibly_cut_off`, `test_the_table_notes_a_listing_that_reached_gh_s_limit` (`tests/test_workflow_hooks.py`)
- [x] Skill: none. These are the repo's own review commands, not the agent skill that drives rietx

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_workflow_hooks.py tests/test_docs_consistency.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

and the measurement task's numbers, from one run of `/pr-review` triage.

## Handover log

- **2026-11-26** — created, from a review of how the two review commands behave on a backlog no single session can clear. With 84 open PRs, `/pr-review` triage saw only 30 and ranked them as if they were all of them. Both commands now either see everything or say they may not. Checked against the tree at dd94fd32. No open WP owns it: of the open WPs in the "The repo's own process" track, 1988 watches a PR after it is opened, 2238 cuts how many calls reach the maintainer, and 1941 moves release notes to fragments. None touches what a listing returns. Next: the measurement task.
