# WP-2077 — The WP workflow sees ghostshift's runners

Milestone: unscheduled · Status: ⬜
Track: The repo's own process
Depends on: —
Priority: P3 2026-11-02 — `/wp-start` offers a live runner's tree to resume as dormant; reading `claim.py list` by hand is the workaround

## Goal

The repo's session workflow knows that ghostshift exists. `wp_claim.py status` and the
worktree create hook's refusal treat a WP a live ghostshift claim holds as held, naming the
claim's owner. `tests/CLAUDE.md`, `docs/RELEASING.md` and the four merge-owning skills say
what a shift does in their territory.

## Context

**Ghostshift** is the claude-config skill (`~/Code/claude-config/skills/ghostshift/SKILL.md`)
that works a repo's maintenance unattended. One lead process, whose cwd is the main checkout,
launches background *runners*. A runner is a subagent in an Agent-isolation worktree named
`agent-<id>`, on a branch cut by the runner itself (`wp<NNNN>-<slug>`). This WP reads that
skill and its `bin/` scripts and edits neither.

1. **A live runner's tree reads as dormant.** `wp_claim.py` derives a held claim from a
   `claude` process whose cwd is inside the tree (root CLAUDE.md, "A claim is held by a
   worktree"). A runner has no such process: its process is the lead's, in the main
   checkout. So `/wp-start` step 2 lists the runner's tree as `dormant`, which that step calls
   "often what you want", and offers it for resuming. Measured 2026-11-02: `status` printed
   WP-1977, WP-2067 and WP-2076 dormant in `agent-*` trees while `claim.py list` showed live
   claims on the first two.

   Ghostshift's own claims are refs on origin: `refs/ghostshift/claims/<item>`, with item
   `wp-<N>`, `issue-<N>` or `pr-<N>` (and free-form ones such as `main-health`). Each points at
   a parentless commit whose message is JSON `{owner, item, taken, pr, at}`; `taken` is epoch
   seconds. A claim is free once its PR has merged or closed, or with no PR 24 h after
   `taken` (`claim.py` docstring). Read the refs with git (a fetch of
   `+refs/ghostshift/claims/*` into the same local namespace `claim.py` uses, then
   `for-each-ref`); import nothing from claude-config. `ls-remote` on the namespace took
   0.58 s on 2026-11-02, so the network read stays out of the SessionStart hook.
2. **A queued suite looks like a running one.** `tests/CLAUDE.md`'s "observe rather than
   reserve" paragraph tells a session to look for a running suite with `ps` before starting
   one. A runner queues its full suites through ghostshift's `bin/serial.py`, which holds a
   machine-wide lock and also waits while `ps` shows a `python -m pytest` outside it. A `ps`
   line naming `serial.py` is a queued waiter.
3. **`docs/RELEASING.md` calls itself the authority but lacks the post-release steps.**
   `docs/ROADMAP.md`'s release rule holds them: finish `milestones/vX.Y.md`'s ship block,
   check README's claims, move `pyproject.version` to the next minor's `.dev0` and open that
   version's record. Ghostshift's runner brief points a release runner at ROADMAP for them.
4. **Who merges.** `wp-handover`, `steward`, `issue-review` and `pr-review` each say merging
   is the maintainer's call. A shift lead also merges a PR its checks find clear-cut, under
   the user's standing permission of 2026-10-31 (ghostshift SKILL.md §4). Each skill gains
   one line saying so and nothing else about who merges.

Tier: no heuristic enters `rietx._audit`; this is workflow tooling under `.claude/` and docs.

## Non-goals

- Editing claude-config, ghostshift's claim format or its scripts.
- WP-2046 (the claim check misreads a contributor PR's body); that is the PR half.
- Reporting ghostshift claims from the SessionStart hook, which stays offline.

## Tasks

- [ ] `wp_claim.py`: read ghostshift claim refs; `status` reports a WP a live claim holds as
      held, naming the owner; `worktree_create.py`'s refusal fires on one. Test with a fake
      claim ref in a scratch repo. Measure the added cost on session start.
- [ ] `tests/CLAUDE.md`: the `serial.py` sentence.
- [ ] `docs/RELEASING.md`: the post-release steps as numbered steps after step 8; ROADMAP's
      release rule points there.
- [ ] The four skills: one line each on a shift lead's merges.
- [ ] Skill: none. Nothing here reaches an agent driving rietx.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_workflow_hooks.py tests/test_docs_consistency.py tests/test_skill_claims.py
.venv/bin/python -m ruff check src tests examples
```

## References

`~/Code/claude-config/skills/ghostshift/SKILL.md` §2, §4 and the Runner brief;
`bin/claim.py`, `bin/serial.py` there.

## Handover log

- **2026-11-02** — created. No open WP owns this: WP-2046 is the open-PR half of the claim
  check, and WP-1941 is release notes, not the release steps.
