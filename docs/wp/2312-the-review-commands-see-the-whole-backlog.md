# WP-2312 — the review commands see the whole backlog

Milestone: unscheduled · Status: 🔄 2026-11-26 — every listing says when it may be cut off; /pr-review still ranks 30 PRs, and the call that would rank them all is unmeasured
Track: The repo's own process
Depends on: —
Priority: P4 2026-11-26 — process: no number moves, but a triage that ranks part of the backlog read as ranking all of it

## Goal

`/pr-review` and `/issue-review` either rank the whole open backlog or say
how much of it they ranked. No listing they rely on stops at `gh`'s `--limit`
in silence.

## Context

On 2026-11-26 the repository had **84 open PRs** and **191 open issues**.
Of the PRs, 79 came from the recurring contributor and 5 from the
maintainer. The counts came from GitHub search,
`gh api -X GET search/issues -f q='repo:yue-here/rietx is:pr is:open author:<login>'`.
Every listing these commands read asks `gh` for at most `--limit` rows, and
`gh` stops there without saying so.

- **`/pr-review` triage**: `gh pr list --limit 30` with `commits` among its
  fields. It ranked 30 of 84 PRs. The rank was wrong even for those 30, since
  collision degree counted only files shared with PRs the call returned.
  - **Raising the limit is not the fix.** gh 2.89's query nests
    `authors(first:100)` inside `commits(first:100)`; the strings are in its
    binary. GitHub sizes a query from its `first:` arguments, not from the
    data, and refuses one past 500 000 nodes. So each PR costs about
    100 + 100·100 nodes for commits, plus about 100 each for `files`,
    `latestReviews` and the check contexts: roughly 10 400.
  - At 30 rows that is about 310 K nodes. The ceiling is about 48 rows, and
    gh's page of 100 would be about 1.04 M, refused whatever the backlog
    holds. This is derived from the query shape and was **not run**: `gh pr list`
    does not work in the session that wrote this. A first draft of this WP
    set `--limit 200`, and an independent review caught it.
  - The skill now keeps the call that runs, counts the open PRs with a
    `number`-only listing, and says `ranked N of M open` when they differ.
- **The full fix is unbuilt** (task below): rank every PR without gh's
  `commits` field.
  - Rank 1 needs each PR's commit headlines, for a `WP-NNNN:` prefix.
    `gh api graphql --paginate` over
    `pullRequests(states: OPEN, first: 50)`, with
    `commits(first: 100) { totalCount nodes { commit { messageHeadline } } }`,
    costs about 5 050 nodes a page by the same arithmetic.
  - `totalCount` also shows a PR with more than 100 commits, which
    `commits(first:100)` hides today.
  - Collision degree still needs every PR's `files`, at about 100 nodes a PR.
  - The first draft dropped a split like this as "saves nothing". That was
    wrong: it saves the node budget.
- **`wp_claim.open_prs`** (`/wp-start`'s overlap table, `backlog.py`'s open-PR
  column): `--limit 100`, now `OPEN_PR_LIMIT = 200`. Its fields have no
  `commits`, so they cost about 20 K nodes a page.
  - `listing_cut` flags a list of exactly the limit.
  - `pr_open_in` reads a PR missing from a cut list as unknown. Before, a
    ghostshift claim naming such a PR read as closed and was dropped from
    `status`.
- **`backlog.py`'s issue listing**: `--limit 500`, now `ISSUE_LIMIT`. It is
  checked before the issue numbers given narrow the list. With a cut list, a
  given number that is missing prints as "not in the listing", not as
  "not open".
- **`backlog.py`'s merged listing** (`--limit 200`, now `MERGED_LIMIT`)
  needed a guard too. The first draft said the `git log` covered it, but
  `parse_commit_log` skips merge commits, and `/pr-review` merges with
  `--merge`. So a PR's body and its closing references reach the landed
  column only through this listing. `git log --since` also stops at a
  shallow clone's boundary, and cloud sessions clone shallow. `reach_notes`
  says when the listing ends after the oldest open issue, and when the clone
  is shallow.

Considered and dropped:

- **Storing `/pr-review`'s held decisions between runs.** Re-batching a PR
  held because it touches an in-flight WP costs a pass-A line, not a review.
  A stored hold hides the moment that WP's session ends. A "held" comment on
  each PR would post noise under the maintainer's name.
- **Recording `/issue-review`'s unanswered batch acts in the owning WP's
  `### Inherited`.** Drafted, then withdrawn after review, because the record
  had no reader. `### Inherited` is a mailbox that the WP's own session
  prunes. `/issue-review new` skips cited issues, and `all` re-reads one only
  for a newer comment or a landed reference. An unanswered act still dies
  with the scratchpad. A fix needs a reader first: a `Held … not posted`
  trigger in `all`'s re-read, or a column in `backlog.py`.

Caps left as they are, and named so they are not rediscovered:

- Issue comments come back as `comments(first: 100)`. Rank 2 ("no maintainer
  comment") can misread a thread longer than that.
- `files[]` caps at 100 per PR. `/pr-review` already reads `changedFiles`
  beside it.

Tier ([generality § The rule](../milestones/generality.md#the-rule)): none.
This is the repo's process machinery and makes no package decision.

## Non-goals

- `/pr-review`'s throughput. The 500 K context checkpoint and the slow-suite
  gate are unchanged. How many PRs a session clears is limited by the
  maintainer's batch, which is WP-2238's (the decision machinery).
- `/issue-review`'s unanswered acts (above): a reader first, then a record.

## Tasks

- [x] `wp_claim`: `OPEN_PR_LIMIT` (200), `listing_cut`, `pr_open_in`; `status` says when the PR list may be cut off
- [x] `backlog.py`: `ISSUE_LIMIT`, `MERGED_LIMIT`, `reach_notes`, and the cut-list wording for a missing given number
- [x] `/pr-review` triage: the call that runs, a count beside it, `ranked N of M open` when they differ
- [ ] `/pr-review` triage ranks every open PR: the paginated `gh api graphql` call for commit headlines (with `totalCount`) and a listing without `commits` for the rest. Run each once on a machine where gh lists PRs, record nodes, bytes and wall time here, then change the skill
- [x] Tests (`tests/test_workflow_hooks.py`): `test_a_listing_at_gh_s_limit_reads_as_possibly_cut_off`, `test_a_pr_missing_from_a_cut_list_is_unknown_not_closed`, `test_the_table_notes_a_listing_that_reached_gh_s_limit`, `test_the_landed_column_says_how_far_back_it_can_see`
- [x] Skill: none. These are the repo's own review commands, not the agent skill that drives rietx

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_workflow_hooks.py tests/test_docs_consistency.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

The open task adds one measured `/pr-review` triage over the whole backlog.
Its first line names no `ranked N of M`.

## References

- GitHub, *GraphQL API: rate limits and query limits for the GraphQL API*,
  "Node limit": a call may request at most 500 000 total nodes, counted from
  the `first`/`last` arguments.
- gh 2.89.0 (2026-03-26), `gh pr list --json commits`: the query shape quoted
  above, read from the binary's strings.

## Handover log

- **2026-11-26** — created, from a review of how the two review commands behave on a backlog no single session can clear. With 84 open PRs, `/pr-review` triage ranked 30 as if they were all of them, and three other listings could stop at their limit in silence. Each listing now says so when it may be cut off. `/pr-review` still ranks only 30, because the call that ranks every PR is designed but not run. Checked against the tree at dd94fd32. No open WP owns it: of the open WPs in "The repo's own process", 1988 watches a PR after it is opened, 2238 cuts the calls that reach the maintainer, and 1941 moves release notes to fragments. None touches what a listing returns.
    - *Review*: an independent subagent read the first draft. It found the `--limit 200` call over GitHub's node limit, a ghostshift claim dropped on a cut list, the merged-listing gap, and a held-act record with no reader. Each was checked against the code or gh's binary. All are fixed or withdrawn above.
    - *Next*: the open task, on a machine where `gh pr list` runs.
