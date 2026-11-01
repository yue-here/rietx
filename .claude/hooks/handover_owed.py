#!/usr/bin/env python3
"""Stop gate: a WP session's last act is ``/wp-handover``, not a summary of it.

The trigger used to survive on prose alone, and prose lost the moment it left
the context.  ``/wp-start`` step 2 read the whole of ``docs/ROADMAP.md``, whose
§ Session protocol step 3 says *End — or whenever interruption threatens — run
``/wp-handover``*; on 2026-09-01 that read was narrowed to the "Current focus"
section (commit ``3a273141``, 13k tokens to 1k) and the protocol stopped
arriving with it.  The **next two sessions both missed the handover** — WP-1324
stopped at "work is complete and committed", WP-1131 at "closed and handed
over … ready for /clear" having done the recording by hand — and the user had
to ask "did you run /wp-handover" in each.  Neither had run the checklist's
step 9 (``/code-review medium --fix``) or step 10 (verify against merged main).

So the trigger is measured here instead of remembered.  A **nudge, not a
gate**: the hook blocks one stop, says what is owed, and lets a session that
is not finished say so and carry on.

It fires only when every one of these holds, which is the end-state of a WP
session and almost nothing else:

* the tree is a worktree whose branch names a WP (``wp1131-…``);
* the branch adds at least one commit to ``origin/main``;
* the branch is **at rest** — working tree clean, nothing unpushed — which is
  where a session lands when it believes it is done, and is not where it sits
  between checklist items;
* this session's transcript shows no ``/wp-handover`` invocation;
* it has not already nudged for this HEAD (one stamp per commit, so a session
  that says "not finished" is not asked again until it lands more work).

``stop_hook_active`` is honoured on top of all that: the hook never blocks two
stops in a row, so a wrong call costs one turn and can never loop.  Stdlib-only
and **fails open**, like ``worktree_only.py``: any internal error lets the stop
through, because a session that cannot end costs more than a missed nudge.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

STAMP_NAME = "wp-handover-nudge"
_WP_BRANCH_RE = re.compile(r"wp-?(\d{4})", re.IGNORECASE)
# A Skill call (the command's name as the ``skill`` key of a tool input) or the
# typed slash command (``<command-name>`` carrying it).  The
# bare word is not enough: a session that only *reads* the command file, or
# names it in prose, has not run it — which is exactly the failure above.
#
# Both sentinels are assembled from fragments so that **this file's own source
# contains neither of them**.  Spelled out, they match the transcript of any
# session that reads, greps or edits this hook or its tests, which silences the
# nudge for the rest of that session — measured on the session that wrote it
# (2026-09-02), whose own transcript matched before this line was split.
#
# A Skill call in a worktree session may carry the tree as a prefix,
# ``.claude/worktrees/<tree>:<name>``.  While the ritual was a command that call
# failed and the session retried bare; since it became a skill (PR #1209) the
# prefixed call succeeds and is the only one in the transcript.
_NAME = "wp-" + "handover"
_HANDOVER_RAN_RE = re.compile(
    r'"skill"\s*:\s*"(?:[^"]*:)?' + _NAME + r'"|<command-' + "name>/" + _NAME
)

REASON = """Stop paused: WP-{wp} has {n} commit(s) on `{branch}`, the branch is clean and \
pushed, and this session has not run /wp-handover.

If this session's scope on WP-{wp} is finished, run `/wp-handover {wp}` now. The \
command carries steps a written summary does not: ticking the checklist, the entry \
in the two forms the session-start scan can read, forward references into other WPs, \
the diff review (`/code-review medium --fix`), the verify pass against merged main, \
and the pull request. Doing those from memory is what this gate exists to catch — \
the two sessions before it landed both reported "handed over" without them.

If you are NOT finished, say in one line what remains and carry on; this will not \
ask again until more work lands."""


def _git(root: Path, *args: str) -> Optional[str]:
    try:
        # 5 s, not 10: ``nudge`` makes up to seven of these inside the hook's
        # own 15 s budget (.claude/settings.json), and a git call slow enough
        # to matter is one more reason to let the stop through.
        proc = subprocess.run(
            ["git", *args], cwd=root, capture_output=True, encoding="utf-8", errors="replace", timeout=5
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return proc.stdout.rstrip("\n") if proc.returncode == 0 else None


def base_ref(root: Path) -> str:
    """``origin/main`` where there is one, else the local ``main``."""
    if _git(root, "rev-parse", "--verify", "-q", "origin/main") is not None:
        return "origin/main"
    return "main"


def commits_ahead(root: Path) -> int:
    """How many commits this branch adds to ``origin/main``, merges excluded.

    Any commit, not only a ``WP-NNNN:``-prefixed one: the branch name is what
    says which WP this is, and a WP session whose every commit was ritual
    (``docs:``, ``tooling:`` — 39 of the last 400 on main) owes its handover
    exactly as much.  Requiring the prefix would have left this hook silent on
    the two branches that introduced it.
    """
    count = _git(root, "rev-list", "--count", "--no-merges", f"{base_ref(root)}..HEAD")
    try:
        return int(count)
    except (TypeError, ValueError):
        return 0


def at_rest(root: Path) -> bool:
    """Clean working tree, and every commit on this branch pushed to its upstream.

    Unpushed work is a session mid-flight: ``/wp-handover`` itself is what
    pushes and opens the PR, so a branch that is level with its upstream has
    either been handed over or been finished by hand — the second is the case
    worth interrupting.
    """
    if _git(root, "status", "--porcelain"):
        return False
    if _git(root, "rev-parse", "--verify", "-q", "@{upstream}") is None:
        return False
    return _git(root, "rev-list", "--count", "@{upstream}..HEAD") == "0"


def handover_ran(transcript: Optional[str]) -> bool:
    """True when this session's transcript records a ``/wp-handover`` invocation.

    A missing or unreadable transcript reads as "ran": the hook must not block
    on a signal it could not measure.
    """
    if not transcript:
        return True
    try:
        with open(transcript, encoding="utf-8", errors="replace") as fh:
            return any(_HANDOVER_RAN_RE.search(line) for line in fh)
    except OSError:
        return True


def _stamp_path(root: Path) -> Optional[Path]:
    git_dir = _git(root, "rev-parse", "--path-format=absolute", "--git-dir")
    return Path(git_dir) / STAMP_NAME if git_dir else None


def already_nudged(root: Path, head: str, session_id: str) -> bool:
    path = _stamp_path(root)
    if path is None:
        return False
    try:
        return path.read_text(encoding="utf-8").strip() == f"{session_id} {head}"
    except OSError:
        return False


def record_nudge(root: Path, head: str, session_id: str) -> None:
    path = _stamp_path(root)
    if path is None:
        return
    try:
        path.write_text(f"{session_id} {head}\n", encoding="utf-8")
    except OSError:  # a read-only git dir is no reason to skip the nudge
        pass


def nudge(payload: dict) -> Optional[str]:
    """The reason to hold this stop open, or None to let the turn end."""
    if payload.get("stop_hook_active"):
        return None
    root = Path(payload.get("cwd") or Path.cwd())
    branch = _git(root, "rev-parse", "--abbrev-ref", "HEAD")
    named = _WP_BRANCH_RE.search(branch) if branch else None
    if named is None:
        return None
    n = commits_ahead(root)
    if n == 0:
        return None
    if not at_rest(root):
        return None
    head = _git(root, "rev-parse", "HEAD") or ""
    session_id = str(payload.get("session_id") or "")
    if already_nudged(root, head, session_id):
        return None
    if handover_ran(payload.get("transcript_path")):
        return None
    record_nudge(root, head, session_id)
    # The **branch** names the WP this session is on; a commit subject need not
    # (a session that touched a second WP would send the handover there).
    return REASON.format(wp=named.group(1), n=n, branch=branch)


def main() -> int:
    payload = json.loads(sys.stdin.buffer.read())
    reason = nudge(payload)
    if reason is None:
        return 0
    print(reason, file=sys.stderr)
    return 2  # the blocking exit code; stderr goes back to the session


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # fail open, deliberately: see the module docstring
        sys.exit(0)
