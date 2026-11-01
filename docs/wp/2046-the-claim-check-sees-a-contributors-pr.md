# WP-2046 — The claim check sees a contributor's PR on the WP it runs for

Milestone: unscheduled · Status: ⬜
Track: The repo's own process
Depends on: —
Priority: P3 2026-10-24 — a check that returned a false all-clear on a 1 764-line contributor PR; reading the PR list by hand is the workaround, and `/wp-start` step 2 already asks for it

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

### Inherited

(none)

## Non-goals

- Refusing on an overlap. This tier reports (root `CLAUDE.md`).
- The local half of the check (worktrees and live sessions), which saw nothing wrong here.

## Tasks

- [ ] Choose the issue set the overlap match reads (title only, title plus closing keywords, or
      another rule) on the day's open PRs. Quote rows and #941's links beside today's 24, and
      name each PR the rule drops from the table.
- [ ] A WP is named outright only by the title, the branch or a WP file the PR edits. A body
      mention is a reference, and the issue chain still runs for it.
- [ ] Drop `#N` that are pull requests from the overlap match.
- [ ] The own-PR filter drops the session's own PR by head branch, never every row of its WP.
- [ ] Tests in `tests/test_workflow_hooks.py` beside the existing overlap tests (`:1110-1190`).
      #941's shape (a body naming another WP first, the issue in the title) reaches the WP
      citing that issue. From that WP's tree, a contributor's PR on it still shows and the
      tree's own PR does not. Fail each on purpose once against today's code.
- [ ] Skill: none. The rietx skill drives the package, and this is a repo hook.

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

- **2026-10-24** — created, from the `/wp-start 1956` session that the check gave a false
  all-clear (checked against `origin/main` `10fff0dbd`). No open WP owns `wp_claim.py`.
  WP-1422 built it and is closed, and WP-1118, 1421, 1506, 2002 and 2043 mention it only in
  passing. The
  three-rule table was measured by a scratch script over `gh pr list` and
  `wp_issue_citations`. *Next:* the first task, on whatever PRs are open that day.
