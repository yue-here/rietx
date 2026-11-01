#!/usr/bin/env python3
"""Lines this branch adds to WPs that were already closed (WP-1994).

No session reads a ✅/🛑 WP file again. Protocol step 1 sends a session to the
one WP it is working, and `/wp-start` never offers a closed one. So a note
written into a closed WP is a note no one will read. `/wp-handover` step 5 and
`docs/wp/TEMPLATE.md` both say so in prose, and the prose did not hold:

* WP-0406 put its joint-fit restraint deferral into WP-0308's
  `### Inherited` three days after 0308 closed. The code's refusal pointed
  readers at that closed file for 81 days, until WP-1995 took it.
* WP-1907's handover wrote "WP-1903's Inherited has both" about two tool
  defects after 1903 was marked ✅. It was read only because 1903 happened to
  be worked again the next day.

`test_docs_consistency.py` catches neither. It asks only whether a WP closed
after 2026-07-31 still carries an `### Inherited` heading. The first write
went to an older WP, and the second was prose in a handover log. Only a diff
sees either, so this compares the branch with its merge-base with the target:

    python3 .claude/hooks/closed_wp_writes.py            # target origin/main
    python3 .claude/hooks/closed_wp_writes.py --base REF # target REF

A WP file is reported when it is ✅ or 🛑 at the merge-base *or* at the
target's tip, the branch has not reopened it, and the branch adds lines to it
net of the lines it removes. The tip counts because the note lands where the
branch merges: a WP another session closes after this branch forked is closed
by the time the note arrives. A rename sweep that rewrites a line in place adds
nothing, and reopening a WP (its Status changed to ⬜/🔄 on this branch) is how
a closed WP gets read again, so neither is reported. A renamed WP file is
compared with its old name. Uncommitted edits count, because the check runs
before the last commit as well as after it.

A report is a question, not a refusal: correcting a closed WP's own record is
legitimate (WP-1041 superseding 1026's scoreboard). Exit 1 when anything is
reported, so a handover cannot pass it unread; exit 2 when git cannot answer.
Stdlib only, like every hook here.
"""

from __future__ import annotations

import argparse
import difflib
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn, Optional

_HOOKS = str(Path(__file__).resolve().parent)  # appended, never inserted: a
if _HOOKS not in sys.path:  # loose script here must not shadow a stdlib module
    sys.path.append(_HOOKS)
import wp_index  # noqa: E402  (sibling hook, not a package)

ROOT = wp_index.ROOT


@dataclass(frozen=True)
class Write:
    """One closed WP and the lines this branch adds to it."""

    file: str
    glyph: str
    lines: tuple[str, ...]


def _git(root: Path, *args: str) -> Optional[str]:
    try:
        proc = subprocess.run(
            ["git", *args], cwd=root, capture_output=True, encoding="utf-8", errors="replace", timeout=30
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return proc.stdout if proc.returncode == 0 else None


def glyph_of(text: str) -> Optional[str]:
    """The Status glyph in a WP file's header, or None if it has none."""
    status = wp_index.STATUS_RE.search(text.split("\n## ", 1)[0])
    return status.group("glyph") if status else None


def net_added(old: str, new: str) -> list[str]:
    """Non-blank lines `new` adds to `old`, net of the lines each hunk removes.

    A hunk that rewrites k lines into k (a rename) adds none; one that rewrites
    k into k + n adds its last n. Which n lines is a guess, and only the report
    reads it.
    """
    a, b = old.splitlines(), new.splitlines()
    out: list[str] = []
    matcher = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag in ("insert", "replace"):
            extra = (j2 - j1) - (i2 - i1)
            if extra > 0:
                out += [line for line in b[j2 - extra:j2] if line.strip()]
    return out


def _fail(message: str) -> NoReturn:
    """Exit 2, so a git failure never reads as exit 1's report."""
    print(f"closed_wp_writes: {message}", file=sys.stderr)
    raise SystemExit(2)


def _changed(root: Path, base: str) -> list[tuple[str, str]]:
    """(path at `base`, path now) for every WP file the working tree changes.

    ``-z`` keeps a path whole whatever it contains, and ``-M`` pairs a renamed
    file with its old name, which is the one `base` knows it by.
    """
    out = _git(root, "diff", "--name-status", "-z", "-M", base, "--",
               str(wp_index.WP_DIR))
    if out is None:
        _fail(f"git diff against {base!r} failed")
    fields = out.split("\0")
    pairs, i = [], 0
    while i < len(fields) and fields[i]:
        status = fields[i]
        if status[0] in "RC":
            pairs.append((fields[i + 1], fields[i + 2]))
            i += 3
        else:
            pairs.append((fields[i + 1], fields[i + 1]))
            i += 2
    return pairs


def scan(root: Path, base: str, tip: Optional[str] = None) -> list[Write]:
    """Every WP file closed at `base` or `tip` that the working tree adds to."""
    found = []
    for then, name in _changed(root, base):
        path = Path(name)
        if path.parent != wp_index.WP_DIR or not path.name[:4].isdigit():
            continue
        old = _git(root, "show", f"{base}:{then}")
        if old is None or not (root / path).exists():
            continue  # new, or deleted, on this branch
        was = glyph_of(old)
        upstream = None
        if tip is not None:
            at_tip = _git(root, "show", f"{tip}:{then}")
            upstream = glyph_of(at_tip) if at_tip is not None else None
        new = (root / path).read_text(encoding="utf-8")
        now = glyph_of(new)
        if was not in wp_index.CLOSED and upstream not in wp_index.CLOSED:
            continue
        if now not in wp_index.CLOSED and now != was:
            continue  # reopened on this branch
        lines = net_added(old, new)
        if lines:
            glyph = was if was in wp_index.CLOSED else upstream
            found.append(Write(path.name, glyph, tuple(lines)))
    return found


def target_ref(root: Path) -> str:
    """``origin/main``, or ``main`` without a remote."""
    for ref in ("origin/main", "main"):
        if _git(root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"):
            return ref
    _fail("no origin/main or main to compare with")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--base", help="the branch this one merges into "
                                       "(default: origin/main); the diff is "
                                       "against the merge-base with it")
    args = parser.parse_args(argv)
    # The report prints a WP's ✅, which cp1252 cannot encode, so on Windows a
    # piped stdout would raise UnicodeEncodeError at the first closed WP found.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    tip = args.base or target_ref(ROOT)
    base = _git(ROOT, "merge-base", "HEAD", tip)
    if not base:
        _fail(f"no merge-base between HEAD and {tip!r}")
    found = scan(ROOT, base.strip(), tip)
    if not found:
        print("closed_wp_writes: this branch adds nothing to a closed WP")
        return 0
    print(f"closed_wp_writes: this branch adds lines to {len(found)} closed "
          "WP(s), which no session reads again:")
    for w in found:
        print(f"  {w.file} [{w.glyph}] +{len(w.lines)}: {w.lines[0].strip()[:100]}")
    print("A note that asks for work goes to the open WP that owns it, or to a "
          "new one (fold first: docs/wp/TEMPLATE.md's header). A correction to "
          "the closed WP's own record may stay: say so in the handover entry.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
