# WP-2312 — the review commands see the whole backlog

Milestone: unscheduled · Status: 🔄 2026-11-27 — claimed by @yue-here (ghostshift runner): /pr-review triage ranks every open PR
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
  gh orders every PR listing `orderBy: {field: CREATED_AT, direction: DESC}`
  (in its binary), so the 30 were the newest-opened, and the oldest
  unreviewed PRs never reached the rank.
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
  - The first fix kept the call that runs, counted the open PRs with a
    `number`-only listing, and said `ranked N of M open` when they differ.
- **The full fix: one GraphQL query of the skill's own** (built 2026-11-27).
  `.claude/skills/pr-review/triage.graphql` asks for exactly the fields the
  rank reads, in pages of 15, through `gh api graphql --paginate --slurp`.
  `triage.jq` turns the pages into one compact row per PR. It computes
  reviewable lines, collision degree and the governance, execution and
  `WP-NNNN:` evidence, so no file list reaches the session.
  - The plan was two calls: a paginated query for commit headlines, and
    `gh pr list` without `commits` for the rest. Each was run once on
    2026-11-27, with gh 2.103.3 and 84 open PRs (table below). The headline
    query worked. The `gh pr list` call timed out, so the plan changed.
  - **Time is the binding limit, not nodes.** GitHub answers HTTP 502 or 504
    to a request that runs past about 10 s. `mergeStateStatus` alone took
    7.7 s for 50 PRs, so GitHub computes it at about 0.15 s a PR. In the full
    query a PR took 0.17-0.31 s. A page of 15 is at most about 4.7 s at the
    worst rate seen, half the timeout. Settled by Claude under measurement.
  - **One query, not two.** Without bodies and authors, the headlines cost
    100 nodes a PR, and the whole row costs 222. That is 3 330 nodes a page of
    15, under 1 % of the 500 000 limit. A second call would add a join and no
    headroom. Settled by Claude under measurement.
  - `totalCount` on the connection replaces the separate count call. The rows
    fall short of it only if a page is lost.
  - `latestReviews(...) { commit { oid } }` returns the sha when asked: all 15
    reviews on the backlog carried one. gh's own `latestReviews` fragment does
    not ask for `commit`, which is why `gh pr view --json latestReviews`
    prints an empty sha (memory note of 2026-09-18). The skill's skip check
    now reads a field that exists.
  - `commits.totalCount` showed one PR past 100 commits (#1577, 107), and
    `files.totalCount` two past 100 files (#1548, 155; #1838, 193). The rows
    carry both counts so the skill can say what went unread.

  | call (run once, 2026-11-27) | rows | pages | bytes | wall | nodes a page |
  |---|---|---|---|---|---|
  | old triage, `gh pr list --limit 30 … commits` | 30 | 1 | 402 777 | 8.7 s | not measured |
  | `gh pr list --limit 1000`, skill fields without `commits` | 0 | — | — | 10.7 s, HTTP 502 | — |
  | same, with `reviews` added | 0 | — | — | 10.9 s, HTTP 502 | — |
  | headlines only, `first: 50` | 84 | 2 | 145 251 | 2.9 s | 5 050 |
  | `mergeStateStatus` only, `first: 50` | 84 | 2 | 4 069 | 12.3 s (7.7 s a page) | 50 |
  | `files` only, `first: 50` | 84 | 2 | 116 580 | 4.6 s | 5 050 |
  | full query, `first: 100` | 0 | — | — | 10.8 s, HTTP 502 | — |
  | full query, `first: 50` | 0 | — | — | 11.4 s, HTTP 504 | — |
  | full query, `first: 25` | 84 | 4 | 296 304 | 18.5 s (6.5 s worst page) | 5 550 |
  | full query, `first: 20` | 84 | 5 | 296 532 | 20.8 s (6.1 s worst page) | 4 440 |
  | **the skill's call**, `first: 15`, `--paginate --slurp` | 84 | 6 | 296 425 | 16.8 s | 3 330 (arithmetic) |
  | its rows through `triage.jq -c` | 84 | — | 42 201 | — | — |

  Node counts are GitHub's `rateLimit.nodeCount`, except the last, which is
  the arithmetic those counts confirmed. Wall times vary between runs by
  about 2x, so each is one sample.
- **Ghostshift's claim reader is untouched.** It reads `wp_claim.open_prs`,
  a `gh pr list` without `mergeStateStatus` or `commits`, which answered
  84 open PRs the same day.
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
  says when the oldest PR the listing holds was *opened* after the oldest
  open issue, and when the clone is shallow. It reads `createdAt`, not
  `mergedAt`, because of gh's order: a cut list misses a PR opened before its
  oldest row however recently that PR merged. The shallow note fires for
  every shallow clone, even one whose boundary predates the oldest issue. It
  over-warns but hides nothing; reading git's shallow file would fix it.

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
- Commit headlines cap at 100 per PR, and `commitsTotal` shows a PR past it.
  Raising the cap costs nodes on every PR for the one in 84 that needs it.
- `latestReviews` caps at 20, one review per reviewer. The backlog's most
  was 1.

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
- [x] `/pr-review` triage ranks every open PR. Both planned calls were run once and measured (Context's table); the listing without `commits` timed out, so the skill runs one paginated query of its own, `triage.graphql`, read through `triage.jq`
- [x] Tests (`tests/test_workflow_hooks.py`): `test_a_listing_at_gh_s_limit_reads_as_possibly_cut_off`, `test_a_pr_missing_from_a_cut_list_is_unknown_not_closed`, `test_the_table_notes_a_listing_that_reached_gh_s_limit`, `test_the_landed_column_says_how_far_back_it_can_see`, `test_the_triage_rows_carry_what_the_rank_reads`
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
    - *Code review* (`/code-review high --fix`): six findings, four fixed:
      - the merged listing's reach now reads `createdAt` (above), checked against gh's binary;
      - all given issue numbers missing reads "none of those is in the listing", not "no open issues";
      - `status` prints `200+ open` on a cut list;
      - the count call's 1000 is marked a floor.
      Two declined: the shallow note's over-warning (above), and `pr_open_in`
      reading a PR newer than every listed one as unknown, not closed. It errs
      toward keeping a claim, and with creation order a cleverer reading is
      possible but not needed.
    - *Measured*: fast suite (`-m "not slow"`, `[dev]` venv in this worktree, Linux x86-64, 4 cores, nothing else running), run on the branch tree on dd94fd32, before main moved under it. Main (WP-2311's Pawley work) was merged in afterwards. On the merged tree only `test_workflow_hooks.py` and `test_docs_consistency.py` re-ran (179 passed), and the fast matrix on the merged tree is CI's. 15 798 passed, 465 skipped, 30 xfailed in 44 min, a wall clock far above the usual 3-5 min on this container. Four tests added, all in `tests/test_workflow_hooks.py`: 0.06 s together on this run. The base's own count was not re-measured, per `tests/CLAUDE.md` § Running. No full suite: hooks, skills and their tests move no measured number.
    - *Next*: the open task, on a machine where `gh pr list` runs. Build the
      paginated call, measure it, then change the skill.
