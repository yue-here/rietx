#!/usr/bin/env python3
"""PostToolUse nudge: a PR this session puts up for review is one it watches.

``/wp-handover`` step 12 used to *offer* to watch the run.  Unwatched, a PR
sits conflicted or red from the moment main moves under it (a concurrent
``/pr-review`` merges other people's work all day) until the maintainer finds
it.  A cloud session can do better
than offer: ``subscribe_pr_activity`` delivers the PR's CI results, reviews and
merge conflicts into the session that opened it, and
``.claude/skills/steward/SKILL.md`` says how this repo wants them handled.

A hook cannot call an MCP tool, so this one does the part prose kept losing
(WP-1988): it notices the PR going up and puts the subscription in front of the
model, with the owner, repo and number already read off the tool's output.

It fires on the two acts that make a PR **reviewable**, never on a draft:

* ``gh pr create`` without ``--draft``/``-d``, and ``gh pr ready`` without
  ``--undo``;
* ``mcp__github__create_pull_request`` with ``draft`` not true, and
  ``mcp__github__update_pull_request`` with ``draft: false``.

The draft ``/wp-start`` step 4b opens is a *claim*: the session is still
working, CI runs lint alone, and every event on it would be the session's own
push echoed back.  The subscription starts where the gating run does.

It stays silent unless it can name the PR — a ``…/pull/N`` URL or an
``owner/repo#N`` in the output, or the number in the MCP call's input — because
a create that failed prints neither, and a nudge about a PR that does not
exist is the false alarm that teaches the reader to skip the line.  Without the
tool (a local session) the context says to offer instead, so the one prompt
covers both.

Stdlib-only and **fails open**, like ``worktree_only.py``: an internal error
lets the call stand, and says so on exit 1 — the channel on which a
non-blocking hook's stderr reaches the user.
"""

from __future__ import annotations

import json
import re
import shlex
import sys
from pathlib import Path
from typing import Optional

_HOOKS = str(Path(__file__).resolve().parent)  # appended, never inserted: a
if _HOOKS not in sys.path:  # loose script here must not shadow a stdlib module
    sys.path.append(_HOOKS)
from no_top_level_cd import KEYWORDS, strip_heredocs  # noqa: E402  (sibling hook)

_URL_RE = re.compile(r"https://github\.com/([\w.-]+)/([\w.-]+)/pull/(\d+)")
_REF_RE = re.compile(r"\b([\w.-]+)/([\w.-]+)#(\d+)\b")

PROMPT = """This session just put {ref} up for review.

If the `subscribe_pr_activity` tool is available (cloud sessions; load it with
ToolSearch if it is deferred), call it now with owner="{owner}", repo="{repo}",
pullNumber={number}, and handle every event it delivers by
`.claude/skills/steward/SKILL.md` (read it from the PR's head branch). Say in
your report that the session is watching the PR. Without the tool, offer the
person to watch the run instead (/wp-handover step 12)."""


def _segments(command: str) -> list[list[str]]:
    """The command's simple commands, split on newlines, ``;``, ``&&``, ``||``,
    ``|`` and parentheses.

    Heredoc bodies are data (``no_top_level_cd.strip_heredocs``): a PR body
    saying "--draft" is not the flag, and an apostrophe in one must not leave
    shlex an unclosed quote.  A command shlex still cannot read is split
    naively rather than dropped, since silence here is the miss this hook exists
    to prevent.
    """
    src = strip_heredocs(command).replace("\\\n", " ").replace("\n", ";")
    seps = set(";&|()")
    try:
        lex = shlex.shlex(src, posix=True, punctuation_chars="();&|")
        lex.whitespace_split = True
        tokens = list(lex)
    except ValueError:
        tokens = [t for t in re.split(r"([;&|()]+)|\s+", src) if t]
    out: list[list[str]] = [[]]
    for tok in tokens:
        if tok and set(tok) <= seps:
            out.append([])
        else:
            out[-1].append(tok)
    return [seg for seg in out if seg]


def _gh_pr_verb(seg: list[str]) -> Optional[str]:
    """``create``/``ready`` when ``seg`` makes a PR reviewable, else None."""
    words = list(seg)
    while words and (words[0] in KEYWORDS or re.match(r"^\w+=", words[0])):
        words.pop(0)  # FOO=bar gh …, then gh …
    if words[:1] != ["gh"]:  # the command word, never an argument (`echo gh pr ready`)
        return None
    rest = words[1:]
    while rest[:1] in (["-R"], ["--repo"]):  # gh's one global flag before the verb
        rest = rest[2:]
    if rest[:2] == ["pr", "create"]:
        flags = rest[2:]
        if "--draft" in flags or "-d" in flags or "--draft=true" in flags:
            return None
        return "create"
    if rest[:2] == ["pr", "ready"]:
        return None if "--undo" in rest[2:] else "ready"
    return None


def _text(response: object) -> str:
    """The response's strings joined, never JSON-escaped.

    ``json.dumps`` would turn a newline into the two characters ``\\n``, and the
    ``n`` then joins the next word: ``…\\nyue-here/rietx#1013`` read as owner
    ``nyue-here``.
    """
    if isinstance(response, str):
        return response
    if isinstance(response, dict):
        if isinstance(response.get("text"), str):  # an MCP content block
            return response["text"]
        return "\n".join(_text(v) for v in response.values())
    if isinstance(response, list):
        return "\n".join(_text(b) for b in response)
    return str(response)


def _ref_in(text: str) -> Optional[tuple[str, str, int]]:
    m = _URL_RE.search(text) or _REF_RE.search(text)
    return (m.group(1), m.group(2), int(m.group(3))) if m else None


def _created_pr(text: str, owner: object, repo: object) -> Optional[tuple[str, str, int]]:
    """The PR a create call returned, read by key before any free-text search.

    The full PR object carries ``body`` ahead of ``html_url``, so a body citing
    another PR's URL would win a search of the whole text.
    """
    for line in [text, *text.splitlines()]:
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if not isinstance(obj, dict):
            continue
        for key in ("html_url", "url"):
            m = _URL_RE.fullmatch(str(obj.get(key, "")))
            if m:
                return (m.group(1), m.group(2), int(m.group(3)))
        if isinstance(obj.get("number"), int) and owner and repo:
            return (str(owner), str(repo), obj["number"])
    return _ref_in(text)


def target(payload: dict) -> Optional[tuple[str, str, int]]:
    """``(owner, repo, number)`` of a PR this call made reviewable, else None."""
    tool = payload.get("tool_name", "")
    tin = payload.get("tool_input") or {}
    out = _text(payload.get("tool_response", ""))
    if tool == "Bash":
        verbs = [v for v in map(_gh_pr_verb, _segments(tin.get("command", ""))) if v]
        return _ref_in(out) if verbs else None
    if tool == "mcp__github__create_pull_request":
        if tin.get("draft") is True:
            return None
        return _created_pr(out, tin.get("owner"), tin.get("repo"))
    if tool == "mcp__github__update_pull_request":
        if tin.get("draft") is not False:
            return None
        try:
            return (tin["owner"], tin["repo"], int(tin["pullNumber"]))
        except (KeyError, TypeError, ValueError):
            return None
    return None


def main() -> int:
    try:
        payload = json.loads(sys.stdin.buffer.read())
        found = target(payload)
    except Exception as exc:  # fail open, visibly
        print(f"pr_subscribe hook failed open: {exc!r}", file=sys.stderr)
        return 1
    if found is None:
        return 0
    owner, repo, number = found
    context = PROMPT.format(
        ref=f"{owner}/{repo}#{number}", owner=owner, repo=repo, number=number
    )
    json.dump(
        {"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": context}},
        sys.stdout,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
