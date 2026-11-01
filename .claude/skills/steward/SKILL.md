---
name: steward
description: Drive a WP pull request this session put up for review to green and mergeable — merge conflicts, red CI, review comments — read before acting on any GitHub event on it, and after subscribing to it (WP-1988)
---

A PR this session readied (`/wp-handover` step 11) is this session's until it
merges or closes. `.claude/hooks/pr_subscribe.py` prompts the subscription the
moment it goes up; this file says how the events it delivers are handled
**here**, on top of the harness's own drive-to-green rules, which it never
loosens. Outside PRs are `/pr-review`'s, never this.

## Scope and lifetime

- **A reviewable PR, never a draft.** `/wp-start` step 4b's claim draft is
  still being written, and every event on it is the session's own push.
- **One WP per session holds after the handover too.** A subscribed session is
  that PR's steward and starts no other WP; the next WP is a new session. It
  ends with **watching <PR url>**, not *ready for /clear*: the events arrive
  in this session.
- **Stop** when the PR merges or closes, or the person says so:
  `unsubscribe_pr_activity`, one line to the person, nothing pushed after.

## On every event

Work in the WP's worktree (`EnterWorktree` with its `path` when the session
has left it): the main checkout is read-only, and `git push origin HEAD`
from the worktree is the only push. `git fetch origin main` first, every time — a
concurrent `/pr-review` merges all day, so a main fetched at the last event is
stale. Then read the whole PR on its current head (mergeable state, CI on the
latest commit, open threads) and act on every open item, in this order.

### 1. Merge conflict

**Merge main in; never rebase or force-push** a branch that has been
reviewed — `/pr-review`'s next round diffs from the last-reviewed sha, and a
rewritten one may no longer merge onto main, leaving it a patch-by-patch
comparison (`.claude/skills/pr-review/SKILL.md` § Reviewing one PR, step 1).
`git merge origin/main`, message
`Merge main; <what was synced>`. Resolve by regenerating, never by taking a
side, where the file is built from others:

- `docs/wp/README.md` — `python3 .claude/hooks/wp_index.py` (the `wpindex`
  driver usually merges it clean; GitHub's web merge runs no driver).
- The schema number and `docs/releases/<next>.md` — exactly as the **Sync a
  bookkeeping conflict yourself** paragraph of `.claude/skills/pr-review/SKILL.md`
  says; it is the one authority, so it is not restated here.
- `src/rietx/gui/static/**` (marked `-merge`) — rebuild with
  `npm --prefix gui ci && npm --prefix gui run build`; `gui/src/tokens.css`
  with `.venv/bin/python -m rietx.viz.theme > gui/src/tokens.css`.
- The skill's committed copies — `.venv/bin/rietx skill --install . --copy`.

A conflict where both sides changed the same logic and either choice loses
behaviour is the person's: say what conflicts and stop.

### 2. Red CI

Branch protection requires `lint` and `ci-ok` (`tests/CLAUDE.md` § CI). Read
the failing job's log, then check the same job on main's newest `ci.yml` run:
red there too is not this PR's (the harness's standing-down rule). Otherwise
**reproduce it locally first** — the job's own command, on main merged in —
then fix, then show the same command passing.

- Before any push: ruff, the touched test files, and
  `tests/test_docs_consistency.py` when a planning file moved. The full suite
  is not a PR gate here and never runs for an event.
- **Never skip, `slow`-mark, xfail or widen a budget or tolerance to get
  green.** A budget that fires under CI load is a load sensor
  (`tests/CLAUDE.md` § Budgets in tests): fix the test's scope, and say so.
- A pin that moved because main moved (a count, a schema number, a skill cap)
  is a merge consequence: re-measure on the merged tree, never copy a side.
- An edit to an audit-table row's tier, evidence or value, or to
  `UNAUDITED_BASELINE` (`src/rietx/_audit.py`), goes back through the
  `generality-review` judge before the push, as `/wp-handover` step 7
  dispatches it (WP-2014).

### 3. Review comments

The harness's rules hold as written; one addition. `/pr-review` is the
maintainer's bench: a review it posts on this PR is a human-directed one, so
its asks are this session's to answer on the thread.

## What a fix commit carries

- The WP's prefix, `WP-NNNN:`, like every other commit on the branch.
- **A substantive fix touches the WP file in the same push**: one line under
  the newest handover entry saying what CI or the review found and what
  changed. `.claude/hooks/session_start.py`'s order rule flags a non-merge
  commit outside `docs/` and `.claude/` that lands after the WP file was last
  touched, and the successor would spend its first act on a repair that was
  not owed. A pure merge or a regenerated index needs no line.
- A PR body that quotes counts the fix moved is edited to the new numbers,
  with the venv and platform.

## Never

Merge, approve, `gh pr ready --undo`, close and reopen, push an empty commit,
re-run a job more than once, or cancel a run that is not this PR's. Whether
green is enough is the maintainer's call (`/wp-handover` step 11).
