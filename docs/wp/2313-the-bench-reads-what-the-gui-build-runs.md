# WP-2313 — the bench reads what the GUI build runs

Milestone: unscheduled · Status: ✅ 2026-11-28 — /pr-review reads first, and the all mode batches, the GUI and docs builds' machinery and the Python side's other install-time config (PR #1877)
Track: The repo's own process
Depends on: —

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
  (hatchling, no custom hook today). Hatchling also merges a `hatch.toml` beside
  `pyproject.toml` (`hatchling/metadata/core.py`, `ProjectMetadata.hatch`), so a
  `hatch_build.py` hook can be switched on from either file. uv reads a project
  `uv.toml`, whose index settings decide where every package comes from, as
  `gui/.npmrc` does for npm. pytest reads `pyproject.toml` and imports every
  `conftest.py`. A `pytest.ini` or `.pytest.ini` takes precedence over
  `pyproject.toml`, while a `tox.ini` or `setup.cfg` ranks below it and so
  cannot displace the config there. `ruff` reads its config and runs nothing.
  None of `setup.py`, `hatch.toml`, `uv.toml` or the two pytest files exists,
  and hatchling would not run a `setup.py`. The pattern holds them all at no
  cost.
- **The bench session itself**: a Claude Code session started in the bench
  reads `.claude/settings*.json` and a root `.mcp.json`, whose servers run
  commands once approved. Neither file is a build file, but both are config
  the bench obeys, so `.mcp.json` joins the settings files.
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
- [x] Widen step 4's list and `triage.jq`'s `execution` pattern together
- [x] Extend `test_the_triage_rows_carry_what_the_rank_reads` with a `gui/package.json` row
- [x] Skill: none. These are the repo's own review commands

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_workflow_hooks.py tests/test_docs_consistency.py -n auto --dist loadgroup
```

## Handover log

- **2026-11-28** — closed, PR #1877. Before this, `/pr-review` could build a
  contributor's GUI change on the maintainer's machine without first reading
  the npm scripts, lockfile and config that the build runs. Those files now
  sit on the list the bench reads first, and the unattended `all` mode holds
  any PR touching them for the maintainer, like the rest of the list. The code
  review found the same gap on the Python side: three config files can change
  what the venv install or pytest runs, and none was listed. A ghostshift
  runner did this session, from a draft opened at the start.
  - *Done*: `triage.jq`'s `execution` pattern gains `gui/package.json`, its
    lockfile, `gui/.npmrc`, gui's top-level config files, `gui/scripts/`,
    `docs/docs/conf.py`, `hatch.toml`, `uv.toml`, `pytest.ini`/`.pytest.ini`
    and `.mcp.json`. Step 4 now points at that pattern instead of restating
    it, and says how to read a lockfile hunk. Pass A's line names the pattern.
    The triage-row test pins every new alternation, plus two negatives: a
    config-named file under `gui/src/`, and `tox.ini`.
  - *Settled*: the open question. The widened list batches. Grounds and the
    rejected second tier are in Context.
  - *Measured*: authorship on `main` since 2026-08-01. The GUI build's files
    took 9 commits and `docs/docs/conf.py` took 16, with no outside author
    among them. `reference_pages.py` and `sphinx_shared.py` took 13 outside
    commits, which is why they stay off. In the lockfile only `fsevents`
    carries an install script.
  - *Review*: `/code-review high --fix` made six findings. Five were
    accepted: `hatch.toml`, `uv.toml` and the pytest ini files joined the
    pattern, the WP's ladder note was corrected, and the test now pins each
    new row. `tox.ini` and `setup.cfg` were dropped again, since pytest ranks
    them below `pyproject.toml`. The sixth, `.mcp.json`, came back as
    pre-existing and outside scope. It was taken here anyway, because it is
    the settings files' sibling and no outside PR has carried one.
  - *Tests*: the acceptance command, `tests/test_workflow_hooks.py` and `tests/test_docs_consistency.py`, gave 180 passed, 0 skipped (this worktree's `[dev]` venv, CPython 3.12.10, macOS arm64), on the final tree. The change adds no test, so the count moved by none. CI's lint job, run here step for step, exited 0 at every step.
  - *Next*: none. Should outside PRs start editing these files, count them
    and narrow the list, as `156a274d4` did for `.claude/`.
- **2026-11-27** — filed from WP-2312's code review. No open WP owns `/pr-review`'s execution list: WP-2312 is closing, 1988 watches a PR after it opens, and 2238 cuts the calls that reach the maintainer.
