# WP-2046 — The claim check sees a contributor's PR on the WP it runs for

Milestone: unscheduled · Status: ✅ 2026-11-02 — the claim check lists a contributor's PR on the WP it runs for; a body mention no longer counts as a PR's claim (PR #1318)
Track: The repo's own process
Depends on: —

## Goal

`python3 .claude/hooks/wp_claim.py status NNNN` names every open pull request that touches
WP-NNNN. That includes a contributor's PR whose body mentions other WPs in passing, and it
holds when the command runs from WP-NNNN's own tree.

## Context

**What happened.** On 2026-10-24 `/wp-start 1956` ran the claim check from the
`wp2041-tutorial-abstain` tree and again from a fresh WP-1956 tree. Both times it printed
"23 open, none touching WP-1956 other than this session's". PR #941 was open, from
mustachefeeling's fork. It builds the whole of WP-1956, had been through four review rounds, and
its title cites #916, the issue WP-1956 was filed from. The session nearly duplicated it. Two
defects, either one enough on its own:

1. **A body mention is read as a claim.** `open_prs` (`.claude/hooks/wp_claim.py:466`) takes
   the first `WP-NNNN` anywhere in the title or body as the WP the PR names outright. Then
   `overlaps` (`:530-533`) skips the issue chain for any PR with a named WP. #941's body
   mentions WP-1325 first, in passing, so the check filed #941 under WP-1325 alone. It never
   asked whether #916 led anywhere.
2. **The own-PR filter drops a whole WP.** `overlaps(..., mine)` filters by WP number (`:531`,
   `:535`), and `status` sets `mine` to the WP of the tree it runs in (`:637`). So from
   WP-1956's tree, every PR that names WP-1956 or reaches it through an issue is dropped. The
   docstring says the filter drops "this session's own PR". Identify that PR by its head
   branch, which is the tree's branch.

**Measured 2026-10-24 on the 23 open PRs** (scratch script, not committed). 22 carry a named WP,
and 6 of those came from body text alone. 19 PRs reach WPs through an issue that the table
never shows.

**The skip also keeps the table readable, so the fix is a design choice.** Rows the table
would print on the same 23 PRs:

| rule | rows | #941 linked to |
|---|---|---|
| today | 24 | WP-1325 |
| a WP is named only by the title, the branch or a WP file the PR edits; every `#N` in title and body | 87 | 18 WPs |
| as above, but only the title's `#N`, and a number that is itself a PR dropped | 34 | WP-1511, 1956, 1968, 2041 (the four WPs citing #916) |

The flood has three sources. A contributor's body cites many numbers (#941's cites six).
`_ISSUE_RE` (`:420`) reads every `#N`, PR numbers included. And WP files cite PR numbers
too (WP-1956 cites #941 four times). The third rule showed 21 PRs of 23. Whether the two
it dropped hid a real overlap is part of the first task. Closing keywords in the body
(`Closes #N`) are the obvious addition to the title's numbers, and are not yet measured.

**Measured 2026-11-02 on the 23 open PRs** (the first task; scratch scripts over `gh pr list`,
one GraphQL call classifying the 53 numbers they cite as 34 PRs and 19 issues). #941 had
closed, so its links come from `gh pr view 941` run through the same code.

| rule | rows | PRs shown | #941 linked to |
|---|---|---|---|
| today | 23 | 23 | WP-1325 |
| named only by title, else every WP file edited, else branch; the title's `#N` and GitHub's closing references, PR numbers dropped | 35 | 22 (drops #1284) | WP-1511, 1956, 1968, 2041, 2046 |
| as above, plus a "mentions it" row for each WP the body names, when nothing names the PR outright (**chosen**) | 37 | 23 | the five above, plus 1043, 1325, 1446, 1449, 2001 by mention |
| as above, with the body's mentions on every PR | 62 (a WP reached two ways counted twice) | 23 | as above |
| the chosen rule, but a title's PR number kept | 42 | 23 | as above |

The dropped PR hid a real overlap. #1284's title cites #1257, which is a PR, and its body says
"Part of WP-1918". A title-and-closing rule alone puts it nowhere. Kept as a mention, it
reaches WP-1918 and nothing else. Keeping its title's PR number instead links it to five WPs,
because WP-1918, 1956, 1958, 2028 and 2033 all cite #1257, and only WP-1918 is real.
Body mentions on every PR flood the table, since a WP PR's handover-written body cites many
WPs. GitHub's closing references and a `Closes #N` regex gave the same rows; the code reads
GitHub's (`closingIssuesReferences`), which excludes PRs by construction.

**Rules that bind it.**

- `tests/CLAUDE.md` § Running: a check that silently finds nothing returns a false all-clear
  every time, which is worse than no check. Make each guard fail on purpose once.
- Root `CLAUDE.md`: an issue link is evidence of overlap and never proof of a clash. This tier
  reports, and `EnterWorktree` never refuses on it. It needs the network, so it lives in
  `/wp-start` and never in the SessionStart hook.
- A second consumer reads the same parse. `.claude/skills/issue-review/backlog.py` builds its
  "open PRs citing it" column from `PullRequest.issues` (`backlog.py:173`, `:368`). Narrow the
  issue set inside the overlap match, or add a field beside `issues`, rather than changing what
  `issues` holds.
- `/wp-start` step 2 (`.claude/commands/wp-start.md`) describes the PR → issue → WP chain in
  prose. Update it if the chain's input changes.

The tier of each rule this WP adds: none in `rietx._audit`'s scope. This is a repo hook, and the
package makes no decision here.

## Non-goals

- Refusing on an overlap. This tier reports (root `CLAUDE.md`).
- The local half of the check (worktrees and live sessions), which saw nothing wrong here.

## Tasks

- [x] Choose the issue set the overlap match reads (title only, title plus closing keywords, or
      another rule) on the day's open PRs. Quote rows and #941's links beside today's 24, and
      name each PR the rule drops from the table. *(Context § Measured 2026-11-02.)*
- [x] A WP is named outright only by the title, the branch or a WP file the PR edits. A body
      mention is a reference, and the issue chain still runs for it.
- [x] Drop `#N` that are pull requests from the overlap match.
- [x] The own-PR filter drops the session's own PR by head branch, never every row of its WP.
- [x] Tests in `tests/test_workflow_hooks.py` beside the existing overlap tests (`:1110-1190`).
      #941's shape (a body naming another WP first, the issue in the title) reaches the WP
      citing that issue. From that WP's tree, a contributor's PR on it still shows and the
      tree's own PR does not. Fail each on purpose once against today's code.
- [x] Skill: none. The rietx skill drives the package, and this is a repo hook.

## Acceptance

From a tree on WP-1956 while #941 is open, `python3 .claude/hooks/wp_claim.py status 1956` lists
#941. The table's row count on the day's open PRs is quoted beside the 24 measured here.

```sh
.venv/bin/python -m pytest tests/test_workflow_hooks.py
python3 .claude/hooks/wp_claim.py status
```

## References

- PR #941 (the miss), issue #916.
- WP-1422 (✅), which built the check and its PR → issue → WP chain.

## Handover log

- **2026-11-02** — closed (PR PRNUM). PR #1318 merged on 2026-11-02 as `472c302e0`. From a
  WP's own tree, `/wp-start`'s claim check now lists a contributor's open PR on that WP. Every
  task was already ticked, and this entry closes the file without re-measuring anything.
  *Done*: Status ✅, the Priority line and the empty `### Inherited` section deleted, the
  narrative moved to the v1.11 record, the index regenerated. The conflict with PR #1312
  (WP-2077) that the entry below foresaw was resolved in #1312's merge of main (`184435602`).
  `status` passes the tree's branch to `overlaps` there. No release note: the change is a
  repo hook, and the package is untouched. *Next*: none here. No open WP depends on this one.
- **2026-11-02** — all six tasks landed, PR #1318 (a ghostshift runner's session). `/wp-start`'s
  claim check now shows a contributor's PR on the WP it runs for. It no longer takes a WP that
  a PR's body mentions in passing as the PR's claim. Run from a WP's own tree, it hides only
  that tree's PR, never every PR on the WP. On the day's 23 open PRs the table grew from 23
  rows to 37 and lists every PR. PR #941 had closed by today, so the acceptance ran on its
  stored text and on a test of its shape, not live.

  *Done.* `open_prs` (`.claude/hooks/wp_claim.py`) fills four new `PullRequest` fields. `wps`
  holds the WPs named outright: the title's, else every WP file edited, else the branch's.
  `mentions` holds the body's WPs. `chain` holds the title's `#N` plus GitHub's
  `closingIssuesReferences`, less every number GitHub says is a PR, and is empty when `wps`
  is not. `fork` is `isCrossRepository`. `wp` is gone, replaced by `wps`. `issues` is
  unchanged, so `backlog.py`'s column reads what it did. `_pull_requests_among` asks one
  GraphQL `issueOrPullRequest` query for the numbers in titles that name no WP. When gh
  cannot answer, the numbers stay in the chain, which adds rows and never loses one.
  `overlaps(prs, citations, branch)` drops the PR whose head branch is this tree's and is not
  a fork. A PR with named WPs gets those rows only. One without gets a row per WP, its reasons
  joined ("mentions it and issue #562"). `describe_pull_request` prints each WP with its own
  reason when the reasons differ. `_status` reads the tree's full branch with
  `git symbolic-ref`, because `worktree_branches` keeps only the last path segment. `/wp-start`
  step 2's prose says what the chain now reads.

  *Review.* `/code-review high --fix` found 7 and fixed 4 (commit `8ce8a26f0`). `gh api
  graphql` exits 1 when one number does not resolve, which voided the whole classification,
  so `_gh` takes `partial=True` there. A closing reference to another repository's issue is
  no longer followed. Only titles naming no WP are classified. `Overlap.via`'s comment lists
  its forms. Declined, each in a line: a body's non-closing `#N` ("Part of #283") is no longer
  followed, which is the rule the first task measured and chose; a detached HEAD shows the
  tree's own PR, which errs towards too much; `mentions` subtracting `wps` is redundant and
  harmless.

  *Measured.* The first task's table is in Context § Measured 2026-11-02. The new tests'
  behavioural assertions ran against `origin/main`'s `wp_claim.py` through a scratch script:
  the #941 shape, the contributor PR seen from its WP's tree, a title PR number followed, and
  the second WP file all fail there and pass here. `tests/test_workflow_hooks.py`: 110 passed
  ([dev], darwin arm64), 103 on main plus 7 added, 0.84 s for the seven (one local run).
  Fast selection: 13291 passed, 310 skipped, 32 xfailed in 8:37 ([dev], darwin arm64, through
  the ghostshift serialiser). It may have collected before the review fixes landed. The one
  file those fixes touch re-ran green on the final tree. `python -m tests.reader_output`:
  exit 0, unchanged. Full suite not run: the change is a repo hook and moves no measured
  number.

  *Gotchas.* PR #1312 (WP-2077, ghostshift runners) rewrites `_status` too, moving the
  `mine = …` line above the local table. Whichever merges second resolves one textual
  conflict. Keep `mine` keyed on the WP for 2077's runner marker, and pass `branch` to
  `overlaps`. #1312 also adds an `### Inherited` note to this WP file saying so. The
  branch-name regex still reads no WP from a contributor branch like `wp2028/joint-screens`,
  since `/` is not a separator there. Not changed: every such PR names its WP in its title
  today.

  *Next:* review and merge #1318, then close this WP (✅, Priority line deleted, narrative to
  the v1.11 record).

- **2026-10-24** — created, from the `/wp-start 1956` session that the check gave a false
  all-clear (checked against `origin/main` `10fff0dbd`). No open WP owns `wp_claim.py`.
  WP-1422 built it and is closed, and WP-1118, 1421, 1506, 2002 and 2043 mention it only in
  passing. The
  three-rule table was measured by a scratch script over `gh pr list` and
  `wp_issue_citations`. *Next:* the first task, on whatever PRs are open that day.
