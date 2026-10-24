#!/usr/bin/env python3
"""PreToolUse gate: work happens in a worktree, never in the main checkout.

Sessions launched in one checkout share its HEAD, index, stash and working
tree, so one session's ``checkout``, ``reset --hard`` or ``git add -A`` lands
in another's work — four times on 2026-08-26, with four live sessions in the
main checkout at once.  Prose about this lost every time; a gate does not.

So the main checkout is **read-only for a session**.  An ``Edit``/``Write``/
``NotebookEdit`` whose file lives in it, or a ``Bash`` command that would move
its HEAD or index, is refused with the one-line fix: ``EnterWorktree`` (or
``claude -w`` from the terminal).  Reads, ``gh``, fetches and tests are
untouched, a worktree under ``.claude/worktrees/`` is not the main checkout,
and a file outside any repository is nobody's.

**Only this checkout.**  The rationale above is about the repository the session
was launched in, so that is the only one guarded (WP-1410): auto memory, a
configuration repo, an unrelated clone are all somebody else's problem.  Before
scoping, any repository's main checkout matched, which refused every ``Write``
to ``~/.claude`` auto memory once that directory was symlinked into a repo.

Stdlib-only and **fails open**: any internal error lets the call through,
because a bricked session costs more than a missed refusal.  It says so where
the session can read it, because a gate disabled by a typo is indistinguishable
from a working one otherwise.  That channel is exit **1**, not 0: a
``PreToolUse`` hook's stderr reaches the user only on a non-zero, non-2 exit,
which Claude Code renders as a hook error and runs the tool anyway.  On exit 0
stderr goes to the debug log, where nobody is looking.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

EDIT_TOOLS = {"Edit", "Write", "NotebookEdit", "MultiEdit"}
# git verbs that move HEAD, the index or the working tree of the tree they run in
MUTATING = re.compile(
    r"(?:^|[;&|(\s])git\s+(?:-c\s+\S+\s+)*"
    r"(commit|checkout|switch|reset|stash|merge|rebase|cherry-pick|revert|add|rm|mv|restore|am|apply|clean)\b"
)

REASON = """Refused: this would change the main checkout, which sessions share.
Work in a worktree instead, set up the way this project's /wp-start sets one up
(EnterWorktree, or start the session with `claude -w <name>`). The main checkout
is read-only for a session: %s"""


def _git(cwd: Path, *args: str) -> Optional[str]:
    try:
        proc = subprocess.run(
            ["git", "-C", str(cwd), *args], capture_output=True, encoding="utf-8", errors="replace", timeout=10
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


def _existing_dir(path: Path) -> Path:
    for p in [path, *path.parents]:
        if p.is_dir():
            return p
    return Path("/")


def main_checkout_of(cwd: Path) -> Optional[Path]:
    """The main checkout's root for the repository ``cwd`` is in, else None."""
    common = _git(cwd, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if not common:
        return None
    return Path(common).resolve().parent


def session_main_checkout(payload: dict) -> Optional[Path]:
    """The main checkout of the repository this session runs in, or None.

    Read from the payload's ``cwd`` and nowhere else: it is the same signal the
    Bash branch already tests, and it travels with the call.  ``CLAUDE_PROJECT_DIR``
    looks like a better answer and is not — it describes the *process*, so under a
    test harness, or any caller whose cwd is elsewhere, it scopes the gate to a
    repository the payload never mentioned and quietly allows an edit that should
    have been refused.  No ``cwd`` means no claim about the session, and the gate
    falls back to guarding every main checkout, which fails closed.
    """
    cwd = payload.get("cwd")
    return main_checkout_of(_existing_dir(Path(cwd))) if cwd else None


def is_in_main_checkout(path: Path, session_main: Optional[Path] = None) -> bool:
    """True when ``path`` belongs to the main checkout's own tree (not a worktree of it).

    Scoped to ``session_main`` when given: this gate exists because sessions
    launched in ONE checkout share its HEAD, index and tree, so it has no
    business refusing edits to a different repository.  Unscoped it also refused
    ~/.claude auto-memory once that directory was symlinked into a repo, and
    every unrelated repo a session legitimately touches.
    """
    where = _existing_dir(path.resolve())
    top = _git(where, "rev-parse", "--show-toplevel")
    main = main_checkout_of(where)
    if not top or main is None or Path(top).resolve() != main:
        return False
    return session_main is None or main == session_main


def refusal(payload: dict) -> Optional[str]:
    """The reason to refuse this tool call, or None to let it through."""
    tool = payload.get("tool_name")
    tool_input = payload.get("tool_input") or {}
    if tool in EDIT_TOOLS:
        target = tool_input.get("file_path") or tool_input.get("notebook_path")
        if target and is_in_main_checkout(Path(target), session_main_checkout(payload)):
            return REASON % f"`{target}`"
        return None
    if tool == "Bash":
        command = tool_input.get("command") or ""
        m = MUTATING.search(command)
        if not m or " -C " in command:
            return None
        cwd = Path(payload.get("cwd") or Path.cwd())
        if is_in_main_checkout(cwd):
            return REASON % f"`git {m.group(1)}` in {cwd}"
    return None


def main() -> int:
    payload = json.loads(sys.stdin.buffer.read())
    reason = refusal(payload)
    if reason is None:
        return 0
    print(reason, file=sys.stderr)
    return 2  # the blocking exit code; stderr goes back to the session


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # fail open, deliberately: see the module docstring
        # ...but say so.  A gate disabled by a typo looks exactly like a working
        # one: the first draft of the scoping fix referenced an unimported ``os``
        # and every case passed as allowed, the main checkout included (WP-1410).
        print(f"worktree_only: gate disabled by {type(exc).__name__}: {exc}", file=sys.stderr)
        # 1, not 0: only a non-zero, non-2 exit puts this line in front of the
        # session.  It is still fail-open — Claude Code calls it a non-blocking
        # hook error and runs the tool.  2 is the code that would block.
        sys.exit(1)
