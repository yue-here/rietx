# WP-2313 — the bench reads what the GUI build runs

Milestone: unscheduled · Status: 🔄 2026-11-28 — claimed by @yue-here (ghostshift runner)
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

**Settled 2026-11-28: the widened list batches in the `all` mode, like the
rest of the list.** Settled by Claude under pass A's written rule and a
measurement. The two texts do not conflict. Step 4's read applies in every
mode. Pass A is the unattended mode's treatment of the same list, and it
batches every path on it, because "an unattended queue is the wrong place to
decide that is fine" (`30a4dabe8`, 2026-08-26). Since WP-2312 one pattern feeds
both. The measurement says the batch costs nothing seen so far: since
2026-08-01 the GUI build's files took 9 commits on `main` and
`docs/docs/conf.py` took 16, none from an outside author. The alternative was a
second tier that only requires the read. It loses because it makes two lists
for one job with no measured cost to pay for it. If outside PRs start editing
these files, narrow on that count, as `156a274d4` did for `.claude/`.

**What the step-5 ladders execute** (measured on the tree, 2026-11-28), beyond
the code a PR is reviewed for:

- **Every ladder**: the venv install runs `pyproject.toml`'s build backend
  (hatchling, no custom hook, so a `hatch_build.py` acts only through a
  `pyproject.toml` edit). pytest reads `pyproject.toml` and imports every
  `conftest.py`. `ruff` reads its config and runs nothing. No `setup.py` exists,
  and hatchling would not run one. The pattern keeps it at no cost.
- **`gui/`**: `npm ci` installs what `gui/package-lock.json` resolves under
  `gui/.npmrc` if one appears. One package carries an install script,
  `fsevents`. `npm run build` runs `gui/package.json`'s `build` script, which
  runs `gui/scripts/vendor.py` and `gui/scripts/build_info.py` under the system
  `python3` and loads `gui/vite.config.ts` and `gui/svelte.config.js`. Vite also
  loads a `postcss.config.*` or `.postcssrc*` by convention, and vitest a
  `vitest.config.*`. `svelte-check` reads `svelte.config.js`.
- **docs/docs**: the `-W` sphinx build executes `docs/docs/conf.py`, which
  imports `docs/reference_pages.py`, `docs/sphinx_shared.py` and three local
  extensions (`markdown_twin`, `py_fields`, `py_highlight`).
  `test_manual_api.py` runs the manual's python blocks.

Deliberately left off the list: the modules `conf.py` imports and the
manual's python blocks. They are code the PR is reviewed for, read in step 2's
diff like `src/`. `reference_pages.py` and `sphinx_shared.py` carry the
manual's constants and generated pages, and the outside contributor edits
them beside feature work (13 commits since 2026-08-01). Batching them would
hold feature PRs, the mistake `156a274d4` corrected for `.claude/`. A new
extension acts only through a `conf.py` edit, which the list holds.

Tier ([generality § The rule](../milestones/generality.md#the-rule)): none.
This is the repo's process machinery and makes no package decision.

## Tasks

- [x] List the files the step 5 ladders execute, `gui/` and docs builds included
- [ ] Widen step 4's list and `triage.jq`'s `execution` pattern together
- [ ] Extend `test_the_triage_rows_carry_what_the_rank_reads` with a `gui/package.json` row
- [ ] Skill: none. These are the repo's own review commands

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_workflow_hooks.py tests/test_docs_consistency.py -n auto --dist loadgroup
```

## Handover log

- **2026-11-27** — filed from WP-2312's code review. No open WP owns `/pr-review`'s execution list: WP-2312 is closing, 1988 watches a PR after it opens, and 2238 cuts the calls that reach the maintainer.
