#!/usr/bin/env python3
"""PreToolUse gate: a ``cd`` must live inside a subshell.

The Bash tool's working directory **persists between calls**, and the shell it
persists in is shared with the user's own ``!`` commands.  So a ``cd`` written
for one command silently retargets every later one, in this session and in the
user's hands, and nothing in ordinary output names the tree it landed in.  Two
measured cases, both in this repo:

* 2026-08-26, ``/pr-review``'s first outing — a ``cd`` added to a ``gh pr list``
  that did not need one sent the next four commands, ``reset --hard`` among
  them, into the user's main checkout instead of the bench worktree.
* 2026-08-26, same day, after the rule was written down — the session ended with
  the shell parked in the bench, and the *user's* next ``gh pr create`` failed
  with ``not on any branch``, because the bench runs detached.

The rule was prose in two places by then and lost anyway: over the seven
sessions preceding this hook, 125 of 660 Bash calls carried a top-level ``cd``
and **not one** used a form that does not persist.  Thirty-seven of those were
``cd`` back to the project root, which is a session undoing its own damage.
Hence a gate.

**What is allowed.** ``(cd X && ...)`` and ``$(cd X && ...)``, because a
subshell's chdir dies with the subshell; a ``cd`` inside a heredoc body, which
is script text being written, not a command being run; a ``cd`` inside quotes,
which is an argument (``bash -c "cd x && y"`` is another process); and the one
bare repair, ``cd <project root>`` alone, which cannot retarget anything because
there is nothing after it.  A brace group is **not** a subshell — ``{ cd x; }``
persists, and is refused.

**What it is not.** Not a claim that ``cd`` is wrong: it is a claim that the
target belongs in the command rather than in invisible session state.  Most
callers have a flag and should use it — ``git -C``, ``npm --prefix``,
``uv --directory``, ``pytest <path>`` — and the subshell is what covers the rest
(a venv build, ``.venv/bin/python`` against a relative path).

Stdlib-only, no network, and **fails open**: any internal error exits 0 and lets
the command through.  A parser bug here would otherwise brick every Bash call in
the project until someone edited settings.json, and this gate is worth less than
that costs.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

# ``<<TAG``/``<<-TAG``/``<<'TAG'``/``<<"TAG"``, but never the ``<<<`` herestring:
# the character class cannot match ``<``, so ``<<<foo`` falls through.
HEREDOC = re.compile(r"<<-?[ \t]*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")

# Words that open a command position without being the command.
KEYWORDS = frozenset(
    {"if", "then", "elif", "else", "fi", "while", "until", "for", "do", "done",
     "case", "esac", "{", "}", "!", "time", "select"}
)
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
WORD_END = " \t\n;&|()<>"

REASON = """Refused: this command changes the shell's working directory, and that
change outlives the call. The Bash tool keeps one shell, and the user's own `!`
commands run in it too, so a bare `cd` retargets later commands in both hands
with nothing in their output naming the tree.

Put the target in the command instead:

  git -C DIR ...            npm --prefix DIR ...        uv --directory DIR ...
  pytest DIR/tests/...      .venv/bin/python -m ...     (any tool's own flag)

Or wrap it, where the tool has no flag and the cwd is genuinely load-bearing:

  (cd DIR && ./configure && make)

A subshell's chdir dies with the subshell, so the next call still starts where
this one did. The refused `cd` was: %s"""


def strip_heredocs(command: str) -> str:
    """Blank out heredoc *bodies*, keeping the lines that open them.

    A session writes scripts constantly (``cat > x.py <<'PY'``), and a ``cd`` in
    that text is data.  Counting it is the false positive that would cost more
    than the bug: a first pass without this flagged 23 commands in one session
    of which 3 were real.
    """
    lines = command.split("\n")
    kept: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        kept.append(line)
        i += 1
        for match in HEREDOC.finditer(line):
            tag = match.group(2)
            while i < len(lines) and lines[i].strip() != tag:
                i += 1
            i += 1  # the terminator line itself
    return "\n".join(kept)


def top_level_cds(command: str) -> list[str]:
    """Return the target of every ``cd`` that would outlive the call.

    One pass, tracking quote state and paren depth.  ``(`` and ``$(`` both open a
    subshell, so anything at depth > 0 is somebody else's working directory.
    """
    src = strip_heredocs(command)
    found: list[str] = []
    depth = 0
    at_start = True
    i, n = 0, len(src)

    while i < n:
        ch = src[i]

        if ch == "\\":
            i += 2
            at_start = False
        elif ch == "'":
            end = src.find("'", i + 1)
            i = n if end < 0 else end + 1
            at_start = False
        elif ch == '"':
            j = i + 1
            while j < n and src[j] != '"':
                j += 2 if src[j] == "\\" else 1
            i = j + 1
            at_start = False
        elif ch == "`":
            end = src.find("`", i + 1)
            i = n if end < 0 else end + 1
            at_start = False
        elif ch == "#" and (at_start or src[i - 1] in " \t"):
            # A `#` opens a comment wherever it begins a *word*, not only in
            # command position: `git log # note; cd /tmp` is one comment, and
            # reading only the `at_start` case flagged the `cd` in it and
            # refused the call.  `echo a#b` is still a literal, because there
            # the previous character is not a separator.
            end = src.find("\n", i)
            i = n if end < 0 else end
        elif ch == "$" and i + 1 < n and src[i + 1] == "(":
            depth += 1
            i += 2
            at_start = True
        elif ch == "(":
            depth += 1
            i += 1
            at_start = True
        elif ch == ")":
            depth = max(0, depth - 1)
            i += 1
            at_start = False
        elif ch in ";&|\n":
            i += 1
            at_start = True
        elif ch in " \t":
            i += 1
        elif ch in "<>":
            i += 1  # a redirect stays inside the command it belongs to
        else:
            j = i
            while j < n and src[j] not in WORD_END:
                j += 1
            if j == i:  # never advanced: an unhandled WORD_END char would spin here
                i += 1
                continue
            word = src[i:j]
            if at_start and (word in KEYWORDS or ASSIGNMENT.match(word)):
                i = j  # still a command position: `FOO=bar cd x`, `then cd x`
                continue
            if at_start and word == "cd" and depth == 0:
                k = j
                while k < n and src[k] in " \t":
                    k += 1
                if k < n and src[k] == "(":
                    i = j  # `cd() { ... }` defines a function; it does not chdir
                    at_start = False
                    continue
                m = k
                while m < n and src[m] not in " \t\n;&|":
                    m += 1
                found.append(src[k:m] or "~")
            i = j
            at_start = False

    return found


def is_root_repair(command: str, targets: list[str]) -> bool:
    """True for ``cd <project root>`` and nothing else on the line.

    The documented way back after something else moved the shell.  It is safe
    for the reason the rest is not: no command follows it, so there is nothing
    for it to retarget, and it moves toward the default rather than away.
    """
    if len(targets) != 1:
        return False
    if strip_heredocs(command).strip() != f"cd {targets[0]}":
        return False
    root = os.environ.get("CLAUDE_PROJECT_DIR") or str(Path(__file__).resolve().parents[2])
    target = targets[0].strip("\"'")
    if target in ("$CLAUDE_PROJECT_DIR", "${CLAUDE_PROJECT_DIR}"):
        return True
    try:
        return Path(os.path.expandvars(target)).resolve() == Path(root).resolve()
    except OSError:
        return False


def main() -> int:
    payload = json.loads(sys.stdin.buffer.read())
    if payload.get("tool_name") != "Bash":
        return 0
    command = (payload.get("tool_input") or {}).get("command") or ""
    targets = top_level_cds(command)
    if not targets or is_root_repair(command, targets):
        return 0
    print(REASON % ", ".join(f"`cd {t}`" for t in targets), file=sys.stderr)
    return 2  # the blocking exit code; stderr goes back to the session


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # fail open, deliberately: see the module docstring
        sys.exit(0)
