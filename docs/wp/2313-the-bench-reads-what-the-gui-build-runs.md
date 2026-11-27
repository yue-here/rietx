# WP-2313 — the bench reads what the GUI build runs

Milestone: unscheduled · Status: ⬜
Track: The repo's own process
Depends on: —
Priority: P3 2026-11-27 — process: an outside PR's npm scripts can run in the `/pr-review` bench unread; rare, since few PRs edit `gui/package.json`

## Goal

`/pr-review` reads every file the bench will execute before it executes it,
the GUI build's included.

## Context

`/pr-review` step 4 says "read before you execute". It lists the files whose
hunks are read first: `pyproject.toml`, `setup.py`, any `conftest.py`,
`.github/**`, `.claude/hooks/**` and `.claude/settings*.json`. Pass A of the
`all` mode batches a PR touching one of them. Since WP-2312 the triage row's
`execution` field is computed from the same list
(`.claude/skills/pr-review/triage.jq`).

The `gui/`-only ladder of step 5 runs `npm --prefix gui ci && npm --prefix gui
run build`. That executes `gui/package.json`'s scripts, the lockfile's
packages' install scripts, the Vite and Svelte config, and `gui/scripts/`.
None of those is on the list. An outside PR that edits only them is neither
read first nor batched.

Found by `/code-review high` on WP-2312's branch (2026-11-27). WP-2312 left it
alone: it was pre-existing and outside that WP's listings.

Open question for the session that takes it: whether a widened list sends
every PR touching `gui/package.json` to the maintainer's batch, or only
requires the read. Step 4's text says the read; pass A's says the batch.

Tier ([generality § The rule](../milestones/generality.md#the-rule)): none.
This is the repo's process machinery and makes no package decision.

## Tasks

- [ ] List the files the step 5 ladders execute, `gui/` and docs builds included
- [ ] Widen step 4's list and `triage.jq`'s `execution` pattern together
- [ ] Extend `test_the_triage_rows_carry_what_the_rank_reads` with a `gui/package.json` row
- [ ] Skill: none. These are the repo's own review commands

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_workflow_hooks.py tests/test_docs_consistency.py -n auto --dist loadgroup
```

## Handover log

- **2026-11-27** — filed from WP-2312's code review. No open WP owns `/pr-review`'s execution list: WP-2312 is closing, 1988 watches a PR after it opens, and 2238 cuts the calls that reach the maintainer.
