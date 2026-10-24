#!/usr/bin/env python3
"""WorktreeCreate hook: make the worktree Claude Code asked for, with its venv.

Claude Code hands the creation to this hook whenever one is configured — for
``claude -w``, ``EnterWorktree``, a subagent with ``isolation: worktree`` — and
uses whatever path it prints as the session's working directory.  Two things
are gained over the built-in creation, and they are why this file exists:

* **The venv is built here**, so a fresh tree is ready to test in the minute
  ``uv`` takes from a warm cache, and no session forgets it (a worktree
  running the main checkout's venv measures the main checkout's code —
  tests/CLAUDE.md § Quoting numbers).
* **Memory stays shared**: a worktree made by this hook keeps its transcript
  and auto-memory at the launch directory (docs, worktrees § Resume), where
  the built-in path gives each tree an empty memory of its own.

The branch is named after the worktree — ``wp1208-foo`` is the branch
``wp1208-foo``, the repo's convention — cut from ``origin/main`` after a fetch;
an existing branch of that name is checked out instead, which is how a session
resumes work on a branch after its tree was removed.  Failure to build the venv
is reported on stderr and does not block the tree: ``/wp-start`` step 4 sees
the hook's flag and builds it.  Any other failure exits nonzero, which is the
one blocking exit for this event.

**A WP another live session is working is refused here**, and this is the only
place in the session workflow that refuses rather than reports.  Two reasons it
earns the exception.  The trigger is narrow and observable — a ``claude``
process whose cwd is inside a tree that names the same WP — so it cannot fire
on a branch someone left behind, which is the false alarm that would teach the
reader to ignore it.  And this is the moment before the cost is paid: past it a
session spends hours duplicating work it will discover at handover, and git's
own refusal (a branch cannot be checked out in two worktrees) catches only the
case where both sessions chose the same *name*.

Git's refusal is also why the check is not merely advisory: the two mechanisms
answer the same question, and leaving the wider one advisory would mean the
narrower accident is blocked while the broader one is waved through.

A refusal names the release verb, because a refusal with no way past it is a
trap: a session parked idle in a tree it has finished with would block the next
one for ever.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

_HOOKS = str(Path(__file__).resolve().parent)  # appended, never inserted: a
if _HOOKS not in sys.path:  # loose script here must not shadow a stdlib module
    sys.path.append(_HOOKS)
import session_start  # noqa: E402  (sibling hooks, not a package)
import wp_claim  # noqa: E402

VENV = session_start.VENV_FIX  # names the architecture on an arm64 Mac (python_request)


def sh(*args: str, cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(args, cwd=cwd, capture_output=True, encoding="utf-8", errors="replace")
    if check and proc.returncode != 0:
        raise RuntimeError(f"{' '.join(args)}: {proc.stderr.strip()}")
    return proc


def clash_refusal(root: Path, wp: str) -> str:
    """The refusal message for *wp*, or "" when no live session holds it.

    Kept separate from the hook body so the decision is a pure function of the
    three scans, and so the tests drive it without making a worktree.
    """
    trees = wp_claim.worktree_branches(root)
    holders = wp_claim.occupancy(
        trees,
        session_start.live_sessions(),
        session_start._ancestors(),
        wp_claim.read_claims(root),
        wp_claim.main_checkout(trees),
    )
    held = [h for h in holders if h.held and h.wp == wp]
    if not held:
        return ""
    main = wp_claim.main_checkout(trees)
    where = "\n".join(f"  {wp_claim.describe(h, main)}" for h in held)
    release = "\n".join(
        f"  python3 .claude/hooks/wp_claim.py release --worktree {h.worktree}" for h in held
    )
    return (
        f"WP-{wp} is already being worked by a live session:\n{where}\n"
        "Two sessions on one WP duplicate the work and collide at handover.\n"
        "Pick another WP (/wp-start step 2 prints the whole table), or, if that\n"
        f"session is finished with it, release the claim:\n{release}"
    )


def main() -> int:
    payload = json.loads(sys.stdin.buffer.read())
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or Path.cwd())
    name = payload.get("name")
    if not name:
        raise KeyError(f"no worktree name in payload (keys: {sorted(payload)})")
    # Claude Code names the tree and (2.1.246, measured) sends no path; its own
    # location is .claude/worktrees/<name> under the launch checkout, kept here
    # so `EnterWorktree` with `path` and the gitignore rule still apply.
    path = Path(payload.get("path") or root / ".claude" / "worktrees" / name).resolve()

    # Before the tree exists, so a refusal leaves nothing half-made.
    wp = wp_claim.wp_from_name(name)
    if wp is not None:
        refusal = clash_refusal(root, wp)
        if refusal:
            raise RuntimeError(refusal)

    sh("git", "fetch", "-q", "origin", "main", cwd=root, check=False)
    if sh("git", "rev-parse", "--verify", "-q", f"refs/heads/{name}", cwd=root, check=False).returncode == 0:
        sh("git", "worktree", "add", str(path), name, cwd=root)
    else:
        sh("git", "worktree", "add", "-b", name, str(path), "origin/main", cwd=root)

    # The claim, written from the name the tree was given.  It is what
    # ``/wp-start`` step 2 and the session-start scan read, and writing it here
    # is what keeps it off the list of things a session can forget.  Failing to
    # write it costs the sharpened answer, never the tree, because the branch
    # name still says which WP this is (``wp_claim`` docstring).
    if wp is not None:
        try:
            wp_claim.write_claim(root, path, wp, by="worktree")
        except OSError as exc:
            print(f"worktree {name}: claim not written ({exc})", file=sys.stderr)

    venv = subprocess.run(VENV, shell=True, cwd=path, capture_output=True, encoding="utf-8", errors="replace")
    if venv.returncode != 0:
        print(f"worktree {name}: venv build failed — run `{VENV}` there:\n{venv.stderr}", file=sys.stderr)
    else:
        claimed = f", claimed WP-{wp}" if wp else ""
        print(f"worktree {name}: branch {name} from origin/main, [dev] venv built{claimed}", file=sys.stderr)
    print(path)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"worktree_create: {exc}", file=sys.stderr)
        sys.exit(1)
